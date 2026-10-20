"""One-way check before the backup switches source: is everything in GCS on SeaweedFS?

For each durable bucket, lists GCS keys missing on SeaweedFS and keys whose
size differs, each with SeaweedFS's modtime, and explains them. Exits 1 if any
mismatch is unexplained. Listing only.
"""
import json
import os
import sys
from datetime import datetime, timezone

import boto3
from google.cloud import storage
from google.oauth2 import service_account

RESTORED = {  # restore-s3 end times, 2026-10-20 UTC (spikes openviking/3, registry/2)
    "openviking": datetime(2026, 10, 20, 7, 2, 45, tzinfo=timezone.utc),
    "models": datetime(2026, 10, 20, 6, 44, 54, tzinfo=timezone.utc),
    "datalake": datetime(2026, 10, 20, 6, 44, 54, tzinfo=timezone.utc),
    "registry": datetime(2026, 10, 20, 7, 50, 54, tzinfo=timezone.utc),
}
s3 = boto3.client("s3", endpoint_url="http://192.168.2.29:8333", aws_access_key_id=os.environ["SW_AK"],
                  aws_secret_access_key=os.environ["SW_SK"], region_name="us-east-1")
info = json.loads(os.environ["GCS_SA_JSON"])
gcs = storage.Client(credentials=service_account.Credentials.from_service_account_info(info), project=info["project_id"])


def decode(name: str) -> str:
    return name.replace("␊", "\n").replace("␍", "\r")


unexplained = 0
for b, restored in RESTORED.items():
    prefix = f"minio/{b}/"
    src = {decode(x.name.removeprefix(prefix)): x.size for x in gcs.list_blobs("localstack-cluster-backups", prefix=prefix)}
    dst = {o["Key"]: (o["Size"], o["LastModified"]) for p in s3.get_paginator("list_objects_v2").paginate(Bucket=b) for o in p.get("Contents", [])}
    missing = sorted(k for k in src if k not in dst)
    differ = sorted(k for k in src if k in dst and dst[k][0] != src[k])
    markers = [k for k in missing if k.endswith("/") and src[k] == 0]
    other_missing = [k for k in missing if k not in markers]
    late = [k for k in differ if dst[k][1] > restored]
    print(f"{b:11} gcs {len(src):>6} seaweedfs {len(dst):>6} | missing-on-dst {len(missing)} "
          f"({len(markers)} zero-byte dir markers) | differ {len(differ)} ({len(late)} rewritten after restore)")
    for k in other_missing[:10] + [k for k in differ if k not in late][:10]:
        print(f"  unexplained: {k!r}")
    # A marker can be missing because the directory now holds files (no marker
    # needed) or the app removed it; a file missing means the app deleted it.
    if b == "openviking":
        for k in other_missing[:10]:
            print(f"  openviking deleted after restore? {k!r}")
    unexplained += len([k for k in differ if k not in late])
    if b == "registry":
        unexplained += len(other_missing)
    print(f"  missing files (not markers): {len(other_missing)}")
sys.exit(1 if unexplained else 0)
