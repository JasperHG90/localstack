"""Copy every key under PREFIX from bucket SRC to DST key for key (dir markers,
.abstract.md and .overview.md included), and no parent
marker above PREFIX, then list both. Args: endpoint src dst prefix"""
import sys
import boto3
ep, src, dst, prefix = sys.argv[1:5]
s = boto3.client("s3", endpoint_url=ep, region_name="us-east-1",
                 aws_access_key_id="SPIKEADMINKEY0000001",
                 aws_secret_access_key="spikeAdminSecret0000000000000000000000001")


def keys(b):
    out = {}
    for p in s.get_paginator("list_objects_v2").paginate(Bucket=b, Prefix=prefix):
        for o in p.get("Contents", []):
            out[o["Key"]] = o["Size"]
    return out


before = keys(src)
for k in sorted(before):
    # SeaweedFS refuses CopyObject on a directory marker, so read and write each key.
    s.put_object(Bucket=dst, Key=k, Body=s.get_object(Bucket=src, Key=k)["Body"].read())
after = keys(dst)
for k in sorted(before):
    print("COPIED" if after.get(k) == before[k] else "MISSING", k, before[k])
print(f"src {len(before)} keys ({sum(k.endswith('/') for k in before)} dir markers, "
      f"{sum(k.endswith('.abstract.md') for k in before)} .abstract.md, "
      f"{sum(k.endswith('.overview.md') for k in before)} .overview.md); dst has {len(after)}")
ok = before and after == before and any(k.endswith(".overview.md") for k in before)
sys.exit(0 if ok else 1)
