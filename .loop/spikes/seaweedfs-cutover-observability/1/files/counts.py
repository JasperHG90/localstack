"""Object counts per bucket on SeaweedFS and MinIO (listing only)."""
import os
import sys

import boto3


def count(ep: str, ak: str, sk: str, bucket: str) -> int:
    s3 = boto3.client("s3", endpoint_url=ep, aws_access_key_id=ak, aws_secret_access_key=sk, region_name="us-east-1")
    return sum(len(p.get("Contents", [])) for p in s3.get_paginator("list_objects_v2").paginate(Bucket=bucket))


for b in sys.argv[1:]:
    sw = count("http://192.168.2.29:8333", os.environ["SW_AK"], os.environ["SW_SK"], b)
    mn = count("http://192.168.2.29:9000", os.environ["MN_AK"], os.environ["MN_SK"], b)
    print(f"{b:11} seaweedfs {sw:>7}  minio {mn:>7}")
