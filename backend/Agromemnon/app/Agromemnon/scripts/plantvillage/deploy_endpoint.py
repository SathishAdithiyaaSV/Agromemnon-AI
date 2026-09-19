"""Deploy the trained classifier to a SageMaker Serverless Inference endpoint.

Serverless rather than a provisioned instance: leaf photos arrive in bursts and
then not at all for hours, and a provisioned ml.m5.large bills around $60/month to
sit idle. Serverless bills per request plus cold-start compute, which for a demo
and for real smallholder traffic is the difference between cents and tens of
dollars. The tradeoff is a cold start of a few seconds on the first request, which
the agent absorbs inside its own tool-call latency.

Usage:
    python deploy_endpoint.py --model-data s3://.../output/model.tar.gz
"""

import argparse
import json
import os
import sys
from pathlib import Path

SOURCE_DIR = Path(__file__).parent / "src"

DEFAULT_ENDPOINT_NAME = "agromemnon-leaf-disease"
FRAMEWORK_VERSION = "2.3.0"
PY_VERSION = "py311"

# MobileNetV3-Small plus the torch runtime fits comfortably in 3 GB. Serverless
# memory also scales the vCPU allocation, so this is the latency knob as well.
MEMORY_MB = 3072
MAX_CONCURRENCY = 5


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--model-data", help="S3 URI of model.tar.gz (from launch_training.py).")
    parser.add_argument("--role", help="SageMaker execution role ARN.")
    parser.add_argument("--region", default=os.environ.get("AWS_REGION", "us-east-1"))
    parser.add_argument("--endpoint-name", default=DEFAULT_ENDPOINT_NAME)
    parser.add_argument("--memory-mb", type=int, default=MEMORY_MB)
    parser.add_argument("--max-concurrency", type=int, default=MAX_CONCURRENCY)
    args = parser.parse_args()

    try:
        import boto3
        import sagemaker
        from sagemaker.pytorch import PyTorchModel
        from sagemaker.serverless import ServerlessInferenceConfig
    except ImportError:
        print("This script needs the SageMaker SDK: pip install -r requirements-dev.txt", file=sys.stderr)
        return 1

    model_data = args.model_data
    if not model_data:
        output = Path("training-output.json")
        if not output.exists():
            print("Pass --model-data, or run launch_training.py first.", file=sys.stderr)
            return 1
        model_data = json.loads(output.read_text())["model_data"]
        print(f"Using model artefact from training-output.json: {model_data}")

    session = sagemaker.Session(boto_session=boto3.Session(region_name=args.region))
    role = args.role or sagemaker.get_execution_role(session)

    model = PyTorchModel(
        model_data=model_data,
        role=role,
        entry_point="inference.py",
        source_dir=str(SOURCE_DIR),
        framework_version=FRAMEWORK_VERSION,
        py_version=PY_VERSION,
        sagemaker_session=session,
        name=None,
    )

    print(f"Deploying to serverless endpoint '{args.endpoint_name}' ...")
    model.deploy(
        endpoint_name=args.endpoint_name,
        serverless_inference_config=ServerlessInferenceConfig(
            memory_size_in_mb=args.memory_mb,
            max_concurrency=args.max_concurrency,
        ),
    )

    print(f"\nEndpoint live: {args.endpoint_name}")
    print("Set it on the agent runtime:")
    print(f'  LEAF_DISEASE_ENDPOINT={args.endpoint_name}')
    print(f'  LEAF_DISEASE_REGION={args.region}')
    print("\nThose two names are already wired into agentcore/agentcore.json — update the")
    print("values there if you changed the endpoint name, then run `agentcore deploy`.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
