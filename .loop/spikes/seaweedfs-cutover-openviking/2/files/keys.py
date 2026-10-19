# Prints the number of keys and of keys ending in "/" in one S3 bucket.
import sys, boto3
from botocore.config import Config
ep, bucket, ak, sk = sys.argv[1:5]
s3 = boto3.client("s3", endpoint_url=ep, aws_access_key_id=ak, aws_secret_access_key=sk,
                  region_name="us-east-1", config=Config(s3={"addressing_style": "path"}))
keys = [o["Key"] for p in s3.get_paginator("list_objects_v2").paginate(Bucket=bucket) for o in p.get("Contents", [])]
m = sorted(k for k in keys if k.endswith("/"))
print(f"{bucket}: {len(keys)} keys, {len(m)} end in '/': {' '.join(m)}")
