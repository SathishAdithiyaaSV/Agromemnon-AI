"""
Step 2: Upload the prepared scheme docs (+ metadata sidecars) to S3.

This bucket becomes the data source for the Bedrock Knowledge Base.
Uses your friend's AWS credentials — make sure your shell already has
AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY / AWS_SESSION_TOKEN (or an
AWS_PROFILE) set for that account before running this.

Usage:
    python 02_upload_to_s3.py ./out my-hackathon-scheme-docs-bucket ap-south-1
"""

import sys
from pathlib import Path

import boto3


def main(local_dir: str, bucket: str, region: str):
    s3 = boto3.client("s3", region_name=region)

    # Create the bucket if it doesn't exist yet.
    try:
        if region == "us-east-1":
            s3.create_bucket(Bucket=bucket)
        else:
            s3.create_bucket(
                Bucket=bucket,
                CreateBucketConfiguration={"LocationConstraint": region},
            )
        print(f"Created bucket {bucket}")
    except s3.exceptions.BucketAlreadyOwnedByYou:
        print(f"Bucket {bucket} already exists, reusing it")
    except Exception as e:
        print(f"Note: bucket create skipped/failed ({e}); assuming it already exists")

    src = Path(local_dir)
    files = list(src.glob("*.txt")) + list(src.glob("*.txt.metadata.json"))
    print(f"Uploading {len(files)} files to s3://{bucket}/schemes/ ...")

    for i, fp in enumerate(files, 1):
        key = f"schemes/{fp.name}"
        s3.upload_file(str(fp), bucket, key)
        if i % 200 == 0:
            print(f"  {i}/{len(files)} uploaded")

    print("Done.")
    print(f"Data source location for the Knowledge Base: s3://{bucket}/schemes/")


if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Usage: python 02_upload_to_s3.py ./out <bucket-name> <region>")
        sys.exit(1)
    main(sys.argv[1], sys.argv[2], sys.argv[3])