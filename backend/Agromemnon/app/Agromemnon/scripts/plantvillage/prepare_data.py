"""Build the PlantVillage tomato subset and upload it to S3 for SageMaker training.

PlantVillage ships 38 classes across 14 crops. Training all of them needs a GPU
instance and an hour; the ten tomato classes cover the diseases an Indian farmer
actually photographs (blights, leaf curl virus, spider mites) and train to a
usable accuracy on a single CPU/GPU instance in minutes. Scope is a constant
below, so widening to another crop is a one-line change.

The dataset is capped per class on purpose. PlantVillage is close to balanced but
some classes hold 5000+ images, and the long tail adds training time without
moving validation accuracy much on a transfer-learned backbone.

Usage:
    python prepare_data.py --source ~/PlantVillage-Dataset/raw/color --bucket my-bucket
    python prepare_data.py --download --bucket my-bucket        # clones the dataset first
"""

import argparse
import json
import os
import random
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import boto3
from botocore.exceptions import BotoCoreError, ClientError

# The upstream directory names, verbatim. They are the label set the trained model
# emits, so they must not be prettified here — tools/leaf_disease.py maps them to
# farmer-facing names and treatments, and the two sides have to agree exactly.
TOMATO_CLASSES = (
    "Tomato___Bacterial_spot",
    "Tomato___Early_blight",
    "Tomato___Late_blight",
    "Tomato___Leaf_Mold",
    "Tomato___Septoria_leaf_spot",
    "Tomato___Spider_mites Two-spotted_spider_mite",
    "Tomato___Target_Spot",
    "Tomato___Tomato_Yellow_Leaf_Curl_Virus",
    "Tomato___Tomato_mosaic_virus",
    "Tomato___healthy",
)

DATASET_REPO = "https://github.com/spMohanty/PlantVillage-Dataset.git"
# The repo holds colour, greyscale and segmented copies of the same images. Only
# the colour set matches what a phone camera produces.
COLOR_SUBDIR = Path("raw") / "color"

IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".JPG", ".JPEG", ".PNG"}
DEFAULT_PREFIX = "plantvillage/tomato"


def clone_dataset(into: Path) -> Path:
    """Shallow-clone PlantVillage and return the colour image directory."""
    target = into / "PlantVillage-Dataset"
    if not target.exists():
        print(f"Cloning {DATASET_REPO} (shallow, ~2 GB) ...", flush=True)
        subprocess.run(
            ["git", "clone", "--depth", "1", DATASET_REPO, str(target)],
            check=True,
        )
    source = target / COLOR_SUBDIR
    if not source.is_dir():
        raise SystemExit(f"cloned repo has no {COLOR_SUBDIR} directory at {source}")
    return source


def resolve_source(source: Path) -> Path:
    """Accept either the colour directory itself or the repo root above it."""
    if (source / COLOR_SUBDIR).is_dir():
        return source / COLOR_SUBDIR
    return source


def collect(source: Path, per_class: int, seed: int) -> dict[str, list[Path]]:
    """Pick up to `per_class` images for each tomato class, deterministically."""
    rng = random.Random(seed)
    selected: dict[str, list[Path]] = {}
    missing = []

    for name in TOMATO_CLASSES:
        directory = source / name
        if not directory.is_dir():
            missing.append(name)
            continue
        images = sorted(p for p in directory.iterdir() if p.suffix in IMAGE_SUFFIXES)
        rng.shuffle(images)
        selected[name] = images[:per_class]

    if missing:
        raise SystemExit(
            f"{source} is missing {len(missing)} expected class folder(s): {missing[:3]}...\n"
            "Point --source at the PlantVillage 'raw/color' directory."
        )
    return selected


def stage(selected: dict[str, list[Path]], staging: Path, val_fraction: float, seed: int) -> dict:
    """Copy the chosen images into train/ and val/ trees, split per class.

    Splitting inside each class rather than over the pooled list keeps every class
    present in validation; a pooled split can drop a small class out of val entirely
    and make the reported accuracy meaningless for it.
    """
    rng = random.Random(seed)
    counts = {"train": {}, "val": {}}

    for name, images in selected.items():
        images = list(images)
        rng.shuffle(images)
        cut = max(1, round(len(images) * val_fraction))
        splits = {"val": images[:cut], "train": images[cut:]}

        for split, members in splits.items():
            destination = staging / split / name
            destination.mkdir(parents=True, exist_ok=True)
            for image in members:
                shutil.copy2(image, destination / image.name)
            counts[split][name] = len(members)

    return counts


def upload(staging: Path, bucket: str, prefix: str, region: str) -> str:
    s3 = boto3.client("s3", region_name=region)
    uploaded = 0
    for path in sorted(staging.rglob("*")):
        if not path.is_file():
            continue
        key = f"{prefix.rstrip('/')}/{path.relative_to(staging).as_posix()}"
        s3.upload_file(str(path), bucket, key)
        uploaded += 1
        if uploaded % 250 == 0:
            print(f"  uploaded {uploaded} files ...", flush=True)
    print(f"  uploaded {uploaded} files", flush=True)
    return f"s3://{bucket}/{prefix.rstrip('/')}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--source", type=Path, help="PlantVillage raw/color directory (or the repo root).")
    parser.add_argument("--download", action="store_true", help="Clone the dataset instead of using --source.")
    parser.add_argument("--bucket", required=True, help="S3 bucket to upload the prepared subset into.")
    parser.add_argument("--prefix", default=DEFAULT_PREFIX, help=f"Key prefix (default: {DEFAULT_PREFIX}).")
    parser.add_argument("--region", default=os.environ.get("AWS_REGION", "us-east-1"))
    parser.add_argument("--per-class", type=int, default=400, help="Cap on images per class (default: 400).")
    parser.add_argument("--val-fraction", type=float, default=0.2)
    parser.add_argument("--seed", type=int, default=13)
    parser.add_argument("--keep-staging", action="store_true", help="Do not delete the local staging copy.")
    args = parser.parse_args()

    if not args.download and not args.source:
        parser.error("pass --source <dir> or --download")
    if not 0.0 < args.val_fraction < 1.0:
        parser.error("--val-fraction must be between 0 and 1")

    workdir = Path(tempfile.mkdtemp(prefix="plantvillage-"))
    try:
        source = clone_dataset(workdir) if args.download else resolve_source(args.source)
        print(f"Reading from {source}")

        selected = collect(source, args.per_class, args.seed)
        total = sum(len(v) for v in selected.values())
        print(f"Selected {total} images across {len(selected)} classes")

        staging = workdir / "staged"
        counts = stage(selected, staging, args.val_fraction, args.seed)
        for name in TOMATO_CLASSES:
            print(f"  {name:<52} train={counts['train'][name]:>4}  val={counts['val'][name]:>4}")

        print(f"Uploading to s3://{args.bucket}/{args.prefix} ...")
        uri = upload(staging, args.bucket, args.prefix, args.region)

        manifest = {
            "classes": list(TOMATO_CLASSES),
            "counts": counts,
            "s3_uri": uri,
            "per_class_cap": args.per_class,
            "val_fraction": args.val_fraction,
            "seed": args.seed,
        }
        Path("dataset-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")

        print(f"\nDone. train={uri}/train  val={uri}/val")
        print("Wrote dataset-manifest.json; pass the URI to launch_training.py --data-uri")
        if args.keep_staging:
            print(f"Staging kept at {staging}")
        return 0
    except (BotoCoreError, ClientError) as error:
        print(f"S3 upload failed: {error}", file=sys.stderr)
        return 1
    finally:
        if not args.keep_staging:
            shutil.rmtree(workdir, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
