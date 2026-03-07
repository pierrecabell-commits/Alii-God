#!/usr/bin/env python3
"""
Alii Storage Client - MinIO wrapper using boto3
Load credentials from .env only - never hardcode.
"""
import os
import sys
import json
import argparse
from datetime import datetime
from pathlib import Path

MINIO_ENDPOINT = "http://localhost:9000"
DEFAULT_BUCKET = "alii-data"


def get_client():
    """Create boto3 S3 client pointing at MinIO."""
    try:
        from dotenv import load_dotenv
        load_dotenv(str(Path(os.environ.get("ALII_WORKDIR", str(Path(__file__).resolve().parent))) / ".env"))
    except ImportError:
        pass

    import boto3
    from botocore.config import Config

    user = os.environ.get("MINIO_ROOT_USER")
    password = os.environ.get("MINIO_ROOT_PASSWORD")
    if not user or not password:
        raise ValueError("MINIO_ROOT_USER and MINIO_ROOT_PASSWORD must be set in .env")

    return boto3.client(
        "s3",
        endpoint_url=MINIO_ENDPOINT,
        aws_access_key_id=user,
        aws_secret_access_key=password,
        config=Config(signature_version="s3v4"),
        region_name="us-east-1",
    )


def ensure_bucket(client, bucket: str = DEFAULT_BUCKET):
    """Create bucket if it doesn't exist."""
    try:
        client.head_bucket(Bucket=bucket)
    except Exception:
        client.create_bucket(Bucket=bucket)
        print(f"Created bucket: {bucket}")


def upload_file(local_path: str, key: str = None, bucket: str = DEFAULT_BUCKET):
    """Upload a file to MinIO."""
    client = get_client()
    ensure_bucket(client, bucket)
    key = key or Path(local_path).name
    client.upload_file(local_path, bucket, key)
    print(f"Uploaded {local_path} -> s3://{bucket}/{key}")
    return f"s3://{bucket}/{key}"


def download_file(key: str, local_path: str, bucket: str = DEFAULT_BUCKET):
    """Download a file from MinIO."""
    client = get_client()
    client.download_file(bucket, key, local_path)
    print(f"Downloaded s3://{bucket}/{key} -> {local_path}")


def list_files(bucket: str = DEFAULT_BUCKET, prefix: str = "") -> list:
    """List files in a bucket."""
    client = get_client()
    ensure_bucket(client, bucket)
    response = client.list_objects_v2(Bucket=bucket, Prefix=prefix)
    return [obj["Key"] for obj in response.get("Contents", [])]


def put_json(data: dict, key: str, bucket: str = DEFAULT_BUCKET):
    """Write JSON data directly to MinIO."""
    import io
    client = get_client()
    ensure_bucket(client, bucket)
    body = json.dumps(data, indent=2).encode("utf-8")
    client.put_object(Bucket=bucket, Key=key, Body=body, ContentType="application/json")
    print(f"Stored JSON -> s3://{bucket}/{key}")


def get_json(key: str, bucket: str = DEFAULT_BUCKET) -> dict:
    """Read JSON data from MinIO."""
    client = get_client()
    response = client.get_object(Bucket=bucket, Key=key)
    return json.loads(response["Body"].read().decode("utf-8"))


def run_test():
    """Run a full upload/download round-trip test."""
    print("=== MinIO Storage Test ===")
    client = get_client()
    print("Connected to MinIO OK")

    ensure_bucket(client, DEFAULT_BUCKET)
    print(f"Bucket '{DEFAULT_BUCKET}' ready")

    # Write test JSON
    test_data = {"test": True, "timestamp": datetime.now().isoformat(), "message": "Alii storage OK"}
    put_json(test_data, "test/health_check.json")

    # Read it back
    result = get_json("test/health_check.json")
    assert result["test"] is True, "Round-trip test failed"
    print(f"Round-trip test PASS: {result['message']}")

    # List files
    files = list_files()
    print(f"Files in '{DEFAULT_BUCKET}': {files}")

    print("=== Storage Test PASS ===")
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Alii Storage Client")
    parser.add_argument("--test", action="store_true", help="Run round-trip test")
    parser.add_argument("--upload", help="Upload file path")
    parser.add_argument("--download", help="Download key")
    parser.add_argument("--key", help="Object key")
    parser.add_argument("--list", action="store_true", help="List files")
    args = parser.parse_args()

    if args.test:
        run_test()
    elif args.upload:
        upload_file(args.upload, args.key)
    elif args.download:
        download_file(args.download, args.key or args.download.split("/")[-1])
    elif args.list:
        files = list_files()
        print("\n".join(files) if files else "(empty)")
    else:
        parser.print_help()
