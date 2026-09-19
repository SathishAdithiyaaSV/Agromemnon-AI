"""SageMaker training entry point: tomato leaf disease classifier.

Transfer-learns MobileNetV3-Small on the PlantVillage tomato subset. The backbone
is chosen for what happens after training: the model serves from a SageMaker
*serverless* endpoint, which cold-starts by loading the weights on every scale-up.
MobileNetV3-Small is ~6 MB and loads in well under a second, where a ResNet50 at
~100 MB pushes a cold request past the farmer-facing latency budget for a few
points of accuracy that PlantVillage's clean studio images do not need.

Two-stage schedule: train the new head with the backbone frozen, then unfreeze and
fine-tune everything at a tenth of the learning rate. Fine-tuning from the start
destroys the pretrained features while the randomly-initialised head emits large
gradients.

Artefacts written to SM_MODEL_DIR:
    model.pth    — state_dict
    classes.json — label order, so inference never has to re-derive it
"""

import argparse
import json
import os
import time
from pathlib import Path

import torch
from torch import nn
from torch.utils.data import DataLoader
from torchvision import datasets, models, transforms

IMAGE_SIZE = 224
# ImageNet statistics: the backbone was pretrained under this normalisation, and
# inference.py must repeat these exact numbers.
MEAN = (0.485, 0.456, 0.406)
STD = (0.229, 0.224, 0.225)


def build_transforms() -> tuple:
    """Augment training images; leave validation deterministic.

    PlantVillage photographs every leaf flat, centred and evenly lit against a
    uniform background. A farmer's phone photo is none of those things, so the
    training augmentation deliberately over-rotates and jitters colour to stop the
    model keying on the studio conditions instead of the lesions.
    """
    train = transforms.Compose([
        transforms.RandomResizedCrop(IMAGE_SIZE, scale=(0.7, 1.0)),
        transforms.RandomHorizontalFlip(),
        transforms.RandomVerticalFlip(),
        transforms.RandomRotation(30),
        transforms.ColorJitter(brightness=0.3, contrast=0.3, saturation=0.3, hue=0.05),
        transforms.ToTensor(),
        transforms.Normalize(MEAN, STD),
    ])
    validate = transforms.Compose([
        transforms.Resize(int(IMAGE_SIZE * 1.14)),
        transforms.CenterCrop(IMAGE_SIZE),
        transforms.ToTensor(),
        transforms.Normalize(MEAN, STD),
    ])
    return train, validate


def build_model(num_classes: int) -> nn.Module:
    model = models.mobilenet_v3_small(weights=models.MobileNet_V3_Small_Weights.IMAGENET1K_V1)
    in_features = model.classifier[-1].in_features
    model.classifier[-1] = nn.Linear(in_features, num_classes)
    return model


def set_backbone_trainable(model: nn.Module, trainable: bool) -> None:
    for parameter in model.features.parameters():
        parameter.requires_grad = trainable


def run_epoch(model, loader, criterion, optimizer, device) -> tuple[float, float]:
    """One pass. Trains when an optimizer is given, evaluates when it is None."""
    training = optimizer is not None
    model.train(training)

    total_loss, correct, seen = 0.0, 0, 0
    with torch.set_grad_enabled(training):
        for images, labels in loader:
            images, labels = images.to(device), labels.to(device)
            outputs = model(images)
            loss = criterion(outputs, labels)

            if training:
                optimizer.zero_grad()
                loss.backward()
                optimizer.step()

            total_loss += loss.item() * labels.size(0)
            correct += (outputs.argmax(1) == labels).sum().item()
            seen += labels.size(0)

    return total_loss / max(seen, 1), correct / max(seen, 1)


def per_class_accuracy(model, loader, classes, device) -> dict[str, float]:
    """Accuracy for each class separately.

    Overall accuracy hides the failure that matters: a model can score 95% while
    never once identifying the class a farmer most needs telling apart.
    """
    model.eval()
    correct = [0] * len(classes)
    total = [0] * len(classes)

    with torch.no_grad():
        for images, labels in loader:
            predictions = model(images.to(device)).argmax(1).cpu()
            for label, prediction in zip(labels.tolist(), predictions.tolist()):
                total[label] += 1
                correct[label] += int(label == prediction)

    return {name: (correct[i] / total[i] if total[i] else 0.0) for i, name in enumerate(classes)}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--epochs", type=int, default=8)
    parser.add_argument("--head-epochs", type=int, default=2, help="Epochs with the backbone frozen.")
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--lr", type=float, default=1e-3)
    parser.add_argument("--weight-decay", type=float, default=1e-4)
    parser.add_argument("--num-workers", type=int, default=4)
    parser.add_argument("--train-dir", default=os.environ.get("SM_CHANNEL_TRAIN", "/opt/ml/input/data/train"))
    parser.add_argument("--val-dir", default=os.environ.get("SM_CHANNEL_VAL", "/opt/ml/input/data/val"))
    parser.add_argument("--model-dir", default=os.environ.get("SM_MODEL_DIR", "/opt/ml/model"))
    args = parser.parse_args()

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"device={device} torch={torch.__version__}", flush=True)

    train_transform, val_transform = build_transforms()
    train_set = datasets.ImageFolder(args.train_dir, train_transform)
    val_set = datasets.ImageFolder(args.val_dir, val_transform)

    # ImageFolder derives labels from sorted directory names. If the two splits
    # disagree, the validation labels silently point at the wrong classes.
    if train_set.classes != val_set.classes:
        raise SystemExit(f"class mismatch: train={train_set.classes} val={val_set.classes}")

    classes = train_set.classes
    print(f"{len(classes)} classes, {len(train_set)} train / {len(val_set)} val images", flush=True)

    train_loader = DataLoader(train_set, batch_size=args.batch_size, shuffle=True,
                              num_workers=args.num_workers, pin_memory=(device.type == "cuda"))
    val_loader = DataLoader(val_set, batch_size=args.batch_size, shuffle=False,
                            num_workers=args.num_workers, pin_memory=(device.type == "cuda"))

    model = build_model(len(classes)).to(device)
    criterion = nn.CrossEntropyLoss(label_smoothing=0.05)

    best_accuracy = 0.0
    model_dir = Path(args.model_dir)
    model_dir.mkdir(parents=True, exist_ok=True)
    weights_path = model_dir / "model.pth"
    started = time.time()

    for epoch in range(1, args.epochs + 1):
        frozen = epoch <= args.head_epochs
        set_backbone_trainable(model, not frozen)

        # Rebuild the optimizer at the unfreeze boundary: the newly trainable
        # backbone parameters are not in the frozen-stage optimizer's param group,
        # so reusing it would leave the backbone unchanged despite requires_grad.
        if epoch == 1 or epoch == args.head_epochs + 1:
            lr = args.lr if frozen else args.lr / 10
            optimizer = torch.optim.AdamW(
                [p for p in model.parameters() if p.requires_grad], lr=lr, weight_decay=args.weight_decay
            )
            print(f"stage: {'head only' if frozen else 'full fine-tune'} at lr={lr}", flush=True)

        train_loss, train_accuracy = run_epoch(model, train_loader, criterion, optimizer, device)
        val_loss, val_accuracy = run_epoch(model, val_loader, criterion, None, device)

        print(
            f"epoch {epoch}/{args.epochs} "
            f"train_loss={train_loss:.4f} train_acc={train_accuracy:.4f} "
            f"val_loss={val_loss:.4f} val_acc={val_accuracy:.4f}",
            flush=True,
        )

        # Keep the best epoch, not the last: the full fine-tune stage can overfit
        # and end below the peak it passed through.
        if val_accuracy >= best_accuracy:
            best_accuracy = val_accuracy
            torch.save(model.state_dict(), weights_path)

    model.load_state_dict(torch.load(weights_path, map_location=device))
    by_class = per_class_accuracy(model, val_loader, classes, device)

    (model_dir / "classes.json").write_text(json.dumps(classes, indent=2) + "\n")
    (model_dir / "metrics.json").write_text(json.dumps({
        "best_val_accuracy": best_accuracy,
        "per_class_val_accuracy": by_class,
        "epochs": args.epochs,
        "architecture": "mobilenet_v3_small",
        "image_size": IMAGE_SIZE,
        "training_seconds": round(time.time() - started, 1),
    }, indent=2) + "\n")

    print(f"\nbest val_acc={best_accuracy:.4f}  ({time.time() - started:.0f}s)")
    for name, accuracy in sorted(by_class.items(), key=lambda kv: kv[1]):
        print(f"  {name:<52} {accuracy:.3f}")


if __name__ == "__main__":
    main()
