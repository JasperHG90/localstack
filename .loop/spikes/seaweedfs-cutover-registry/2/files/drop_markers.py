"""Delete the zero-byte directory markers restore-s3 wrote into SeaweedFS's registry bucket.

MinIO's registry bucket holds no `dir/` keys (spike:backup-durable-buckets/3);
the restore's --s3-directory-markers adds one per directory. Only zero-byte keys
ending in `/` are deleted, after checking MinIO has none.
"""
import os
import sys

import boto3


def client(ep: str, ak: str, sk: str):
    return boto3.client("s3", endpoint_url=ep, aws_access_key_id=ak, aws_secret_access_key=sk, region_name="us-east-1")


def listing(c) -> dict[str, int]:
    return {o["Key"]: o["Size"] for p in c.get_paginator("list_objects_v2").paginate(Bucket="registry") for o in p.get("Contents", [])}


sw = client("http://192.168.2.29:8333", os.environ["SW_AK"], os.environ["SW_SK"])
mn = client("http://192.168.2.29:9000", os.environ["MN_AK"], os.environ["MN_SK"])
src, dst = listing(mn), listing(sw)
src_markers = [k for k in src if k.endswith("/")]
markers = sorted(k for k, size in dst.items() if k.endswith("/") and size == 0)
print(f"minio: {len(src)} keys, {len(src_markers)} dir keys | seaweedfs: {len(dst)} keys, {len(markers)} zero-byte dir keys")
if src_markers:
    sys.exit("MinIO has directory keys; not deleting anything")
for k in markers:
    sw.delete_object(Bucket="registry", Key=k)
after = listing(sw)
files_match = {k: v for k, v in after.items()} == src
print(f"deleted {len(markers)}; seaweedfs now {len(after)} keys; same keys and sizes as minio: {files_match}")
sys.exit(0 if files_match else 1)
