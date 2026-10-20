"""List every key in openviking-v2 and print _system JSON bodies. Arg: s3 endpoint."""
import sys
import boto3
s = boto3.client("s3", endpoint_url=sys.argv[1], region_name="us-east-1",
                 aws_access_key_id="SPIKEADMINKEY0000001",
                 aws_secret_access_key="spikeAdminSecret0000000000000000000000001")
for p in s.get_paginator("list_objects_v2").paginate(Bucket="openviking-v2"):
    for o in p.get("Contents", []):
        k = o["Key"]
        print("KEY", k, o["Size"])
        if "_system" in k and k.endswith(".json") and o["Size"]:
            print("   ", s.get_object(Bucket="openviking-v2", Key=k)["Body"].read()[:400].decode(errors="replace"))
