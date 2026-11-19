"""
Optional S3 Upload Utility
Uploads assets in assets/catalog/ to a private S3 bucket using the AWS SDK
default credential chain (IAM roles, environment variables, or ~/.aws/credentials).

DO NOT upload automatically without explicit --confirm flag.
Default mode is DRY-RUN.
"""

import os
import sys
import argparse
import mimetypes
from pathlib import Path
import boto3
from botocore.exceptions import BotoCoreError, ClientError

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


def upload_catalog_images(
    bucket_name: str,
    assets_dir: str = "assets/catalog",
    region: str = "us-east-1",
    dry_run: bool = True
):
    assets_path = Path(assets_dir)
    if not assets_path.exists():
        print(f"Assets directory not found at: {assets_dir}")
        return

    print("=" * 60)
    print(f"S3 Product Image Upload ({'DRY-RUN' if dry_run else 'LIVE UPLOAD'})")
    print(f"Target S3 Bucket: {bucket_name}")
    print(f"AWS Region:       {region}")
    print(f"Source Directory: {assets_path}")
    print("=" * 60)

    s3_client = None
    if not dry_run:
        # Default credential chain
        s3_client = boto3.client("s3", region_name=region)

    upload_count = 0
    total_bytes = 0

    for file_path in assets_path.rglob("*"):
        if file_path.is_file():
            # Create S3 key matching 'catalog/...'
            rel_path = file_path.relative_to(assets_path.parent)
            s3_key = str(rel_path.as_posix())
            content_type, _ = mimetypes.guess_type(str(file_path))
            content_type = content_type or "application/octet-stream"
            file_size = file_path.stat().st_size
            total_bytes += file_size

            print(f"  [{'DRY-RUN' if dry_run else 'UPLOAD'}] {file_path} -> s3://{bucket_name}/{s3_key} ({content_type}, {file_size:,} bytes)")

            if not dry_run and s3_client:
                try:
                    with open(file_path, "rb") as f:
                        s3_client.put_object(
                            Bucket=bucket_name,
                            Key=s3_key,
                            Body=f,
                            ContentType=content_type,
                            ServerSideEncryption="AES256"
                        )
                except (BotoCoreError, ClientError) as e:
                    print(f"    ERROR uploading {s3_key}: {e}")
                    raise

            upload_count += 1

    print("-" * 60)
    print(f"Summary: {upload_count} files processed ({total_bytes / 1024:.1f} KB).")
    if dry_run:
        print("Note: DRY-RUN completed. No files were uploaded to AWS.")
        print("To execute live upload, pass: python scripts/upload_s3.py --bucket <your-bucket> --confirm")
    else:
        print(f"Successfully uploaded {upload_count} files to s3://{bucket_name}/")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Upload catalog image assets to private S3 bucket")
    parser.add_argument("--bucket", default=os.getenv("S3_BUCKET_NAME", "eks-beverage-store-catalog"), help="S3 bucket name")
    parser.add_argument("--region", default=os.getenv("AWS_REGION", "us-east-1"), help="AWS Region")
    parser.add_argument("--assets-dir", default="assets/catalog", help="Path to assets folder")
    parser.add_argument("--confirm", action="store_true", help="Perform actual live upload (defaults to dry-run)")

    args = parser.parse_args()
    upload_catalog_images(
        bucket_name=args.bucket,
        assets_dir=args.assets_dir,
        region=args.region,
        dry_run=not args.confirm
    )

