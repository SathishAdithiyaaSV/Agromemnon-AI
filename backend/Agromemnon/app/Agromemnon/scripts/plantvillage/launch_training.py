"""Launch the SageMaker training job for the tomato leaf disease classifier.

Run after prepare_data.py has staged the subset in S3. Prints the model artefact
URI that deploy_endpoint.py needs.

Usage:
    python launch_training.py --data-uri s3://my-bucket/plantvillage/tomato
"""

import argparse
import json
import os
import sys
from pathlib import Path

SOURCE_DIR = Path(__file__).parent / "src"

# ml.g4dn.xlarge trains the 8-epoch schedule in a few minutes. ml.c5.2xlarge is the
# CPU fallback for accounts with no GPU quota — roughly 20 minutes, same accuracy.
DEFAULT_INSTANCE = "ml.g4dn.xlarge"
FRAMEWORK_VERSION = "2.3.0"
PY_VERSION = "py311"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--data-uri", help="S3 prefix holding train/ and val/ (from prepare_data.py).")
    parser.add_argument("--role", help="SageMaker execution role ARN. Defaults to the notebook/session role.")
    parser.add_argument("--region", default=os.environ.get("AWS_REGION", "us-east-1"))
    parser.add_argument("--instance-type", default=DEFAULT_INSTANCE)
    parser.add_argument("--epochs", type=int, default=8)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--lr", type=float, default=1e-3)
    parser.add_argument("--job-name", default=None)
    parser.add_argument("--wait", action="store_true", default=True)
    parser.add_argument("--no-wait", dest="wait", action="store_false")
    args = parser.parse_args()

    try:
        import boto3
        import sagemaker
        from sagemaker.pytorch import PyTorch
    except ImportError:
        print("This script needs the SageMaker SDK: pip install -r requirements-dev.txt", file=sys.stderr)
        return 1

    data_uri = args.data_uri
    if not data_uri:
        manifest = Path("dataset-manifest.json")
        if not manifest.exists():
            print("Pass --data-uri, or run prepare_data.py first to produce dataset-manifest.json",
                  file=sys.stderr)
            return 1
        data_uri = json.loads(manifest.read_text())["s3_uri"]
        print(f"Using data URI from dataset-manifest.json: {data_uri}")

    session = sagemaker.Session(boto_session=boto3.Session(region_name=args.region))
    role = args.role or sagemaker.get_execution_role(session)

    estimator = PyTorch(
        entry_point="train.py",
        source_dir=str(SOURCE_DIR),
        role=role,
        framework_version=FRAMEWORK_VERSION,
        py_version=PY_VERSION,
        instance_count=1,
        instance_type=args.instance_type,
        sagemaker_session=session,
        base_job_name="agromemnon-leaf-disease",
        hyperparameters={
            "epochs": args.epochs,
            "batch-size": args.batch_size,
            "lr": args.lr,
            # SageMaker's CPU instances report more vCPUs than the DataLoader can
            # usefully feed; 4 workers avoids the shared-memory exhaustion that a
            # higher count triggers inside the container.
            "num-workers": 4,
        },
        # Surfaced in the SageMaker console and CloudWatch so a job can be judged
        # without reading the raw log.
        metric_definitions=[
            {"Name": "val:accuracy", "Regex": r"val_acc=([0-9\.]+)"},
            {"Name": "train:accuracy", "Regex": r"train_acc=([0-9\.]+)"},
            {"Name": "val:loss", "Regex": r"val_loss=([0-9\.]+)"},
        ],
    )

    estimator.fit(
        {"train": f"{data_uri.rstrip('/')}/train", "val": f"{data_uri.rstrip('/')}/val"},
        job_name=args.job_name,
        wait=args.wait,
    )

    if not args.wait:
        print(f"Training job started: {estimator.latest_training_job.name}")
        return 0

    artifact = estimator.model_data
    Path("training-output.json").write_text(json.dumps({
        "job_name": estimator.latest_training_job.name,
        "model_data": artifact,
        "region": args.region,
    }, indent=2) + "\n")

    print(f"\nModel artefact: {artifact}")
    print("Wrote training-output.json; run deploy_endpoint.py next.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
