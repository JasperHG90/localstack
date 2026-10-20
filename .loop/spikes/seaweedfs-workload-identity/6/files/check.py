"""After the probes: the probe's object, the admin key, and a static-key user."""
import os
import sys

import boto3
from botocore.exceptions import ClientError

EP = "http://192.168.2.29:8333"


def s3(ak: str, sk: str):
    return boto3.client("s3", endpoint_url=EP, aws_access_key_id=ak, aws_secret_access_key=sk, region_name="us-east-1")


admin = s3(os.environ["AK"], os.environ["SK"])
keys = sorted(o["Key"] for o in admin.list_objects_v2(Bucket="wi-probe").get("Contents", []))
body = admin.get_object(Bucket="wi-probe", Key="from-wi-probe")["Body"].read() if "from-wi-probe" in keys else b""
print("wi-probe bucket holds:", keys, body)
ok = keys == ["from-wi-probe"] and body == b"written by wi-probe"
print("admin lists:", sorted(b["Name"] for b in admin.list_buckets()["Buckets"]))
loki = s3(os.environ["LOKI_AK"], os.environ["LOKI_SK"])
loki.put_object(Bucket="loki", Key="verify/static", Body=b"x")
got = loki.get_object(Bucket="loki", Key="verify/static")["Body"].read()
try:
    loki.get_object(Bucket="tempo", Key="anything")
    other = "allowed"
except ClientError as e:
    other = e.response["Error"]["Code"]
loki.delete_object(Bucket="loki", Key="verify/static")
print("static loki key: own bucket put/get", got == b"x", "| tempo:", other)
ok &= got == b"x" and other in ("AccessDenied", "403")
sys.exit(0 if ok else 1)
