"""After the first backup from SeaweedFS: every file on SeaweedFS is in GCS at the same size.

Directory markers are compared as directories (rclone writes them only where
needed), files key by key. Exits 1 on any file missing from GCS or differing.
"""
import json
import os
import sys

import boto3
from google.cloud import storage
from google.oauth2 import service_account

s3 = boto3.client("s3", endpoint_url="http://192.168.2.29:8333", aws_access_key_id=os.environ["SW_AK"],
                  aws_secret_access_key=os.environ["SW_SK"], region_name="us-east-1")
info = json.loads(os.environ["GCS_SA_JSON"])
gcs = storage.Client(credentials=service_account.Credentials.from_service_account_info(info), project=info["project_id"])
bad = 0
for b in ["openviking", "registry", "models", "datalake"]:
    prefix = f"minio/{b}/"
    dst = {x.name.removeprefix(prefix).replace("␊", "\n").replace("␍", "\r"): x.size
           for x in gcs.list_blobs("localstack-cluster-backups", prefix=prefix)}
    src = {o["Key"]: o["Size"] for p in s3.get_paginator("list_objects_v2").paginate(Bucket=b) for o in p.get("Contents", [])}
    files = {k: v for k, v in src.items() if not k.endswith("/")}
    gfiles = {k: v for k, v in dst.items() if not k.endswith("/")}
    missing = [k for k in files if k not in gfiles]
    differ = [k for k in files if k in gfiles and gfiles[k] != files[k]]
    extra = [k for k in gfiles if k not in files]
    print(f"{b:11} seaweedfs {len(files):>6} files | gcs {len(gfiles):>6} files | missing in gcs {len(missing)} differ {len(differ)} extra in gcs {len(extra)}")
    bad += len(missing) + len(differ) + len(extra)
sys.exit(1 if bad else 0)
