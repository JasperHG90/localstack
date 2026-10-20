"""One-way check that each durable MinIO bucket is fully in its GCS backup prefix.

Listing only: no object bodies are read. Exits 1 on any file missing or
differing in size, or any MinIO directory key whose directory is absent in GCS.
rclone's GCS encoding stores LF and CR in names as U+240A and U+240D, so GCS
names are decoded before comparing.
"""
import json
import os
import sys

import boto3
from google.cloud import storage
from google.oauth2 import service_account

s3 = boto3.client("s3", endpoint_url="http://192.168.2.29:9000", aws_access_key_id=os.environ["MINIO_AK"], aws_secret_access_key=os.environ["MINIO_SK"], region_name="us-east-1")
info = json.loads(os.environ["GCS_SA_JSON"])
gcs = storage.Client(credentials=service_account.Credentials.from_service_account_info(info), project=info["project_id"])


def decode(name: str) -> str:
    return name.replace("␊", "\n").replace("␍", "\r")


bad = 0
for bucket in ["openviking", "registry", "models", "datalake"]:
    src = {o["Key"]: o["Size"] for p in s3.get_paginator("list_objects_v2").paginate(Bucket=bucket) for o in p.get("Contents", [])}
    prefix = f"minio/{bucket}/"
    dst = {decode(b.name.removeprefix(prefix)): b.size for b in gcs.list_blobs("localstack-cluster-backups", prefix=prefix)}
    files = {k: v for k, v in src.items() if not k.endswith("/")}
    markers = {k for k in src if k.endswith("/")}
    dst_files = {k: v for k, v in dst.items() if not k.endswith("/")}
    dst_dirs = {k for k in dst if k.endswith("/")}
    for k in dst_files:
        parts = k.split("/")[:-1]
        dst_dirs |= {"/".join(parts[: i + 1]) + "/" for i in range(len(parts))}
    missing = [k for k in files if k not in dst_files]
    differ = [k for k in files if k in dst_files and dst_files[k] != files[k]]
    lost = [m for m in markers if m not in dst_dirs]
    print(f"{bucket:11} minio {len(files):>6} files {sum(files.values()):>11} B, {len(markers):>5} dir keys | "
          f"gcs {len(dst_files):>6} files {sum(dst_files.values()):>11} B, {len(dst) - len(dst_files):>4} markers | "
          f"missing {len(missing)} differ {len(differ)} dirs lost {len(lost)}")
    for k in (missing + differ + lost)[:5]:
        print(f"  {k!r}")
    bad += len(missing) + len(differ) + len(lost)
sys.exit(1 if bad else 0)
