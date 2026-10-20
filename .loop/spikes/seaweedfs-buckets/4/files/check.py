"""Live checks for seaweedfs-buckets: bucket list, per-user isolation, backup read-only.

Reads keys from `terraform show -json` on stdin; nothing is written to disk.
"""
import json
import os
import sys

import boto3
from botocore.exceptions import ClientError

EP = "http://192.168.2.29:8333"
state = json.load(sys.stdin)
res = state["values"]["root_module"]["resources"]
keys = {r["index"] if "index" in r else "backup": (r["values"]["id"], r["values"]["secret"])
        for r in res if r["type"] == "aws_iam_access_key"}
policies = {r.get("index", "backup"): json.loads(r["values"]["policy"]) for r in res if r["type"] == "aws_iam_user_policy"}


def client(ak: str, sk: str):
    return boto3.client("s3", endpoint_url=EP, aws_access_key_id=ak, aws_secret_access_key=sk, region_name="us-east-1")


def allowed(fn) -> bool:
    try:
        fn()
        return True
    except ClientError as e:
        code = e.response["Error"]["Code"]
        if code in ("AccessDenied", "403", "Forbidden"):
            return False
        raise


admin = client(os.environ["AK"], os.environ["SK"])
buckets = sorted(b["Name"] for b in admin.list_buckets()["Buckets"])
print("admin sees:", buckets)
ok = buckets == ["datalake", "loki", "models", "openviking", "registry", "tempo"]
for b in buckets:
    admin.put_object(Bucket=b, Key="verify/seed", Body=b"seed")

for user, (ak, sk) in sorted(keys.items()):
    pol = policies[user]["Statement"][0]
    own = sorted({r.split(":::")[1].split("/")[0] for r in pol["Resource"]})
    writer = pol["Action"] == ["s3:*"]
    c = client(ak, sk)
    other = next(b for b in buckets if b not in own)
    row = []
    for b in own:
        can_read = allowed(lambda: c.get_object(Bucket=b, Key="verify/seed"))
        can_list = allowed(lambda: c.list_objects_v2(Bucket=b, Prefix="verify/"))
        can_write = allowed(lambda: c.put_object(Bucket=b, Key=f"verify/{user}", Body=b"x"))
        # MinIO's readers get GetObject only; the backup user also lists, to sync.
        good = can_read and can_write == writer and can_list == (writer or user == "backup")
        ok &= good
        row.append(f"{b}: read={can_read} list={can_list} write={can_write}{'' if good else ' WRONG'}")
    denied = not allowed(lambda: c.get_object(Bucket=other, Key="verify/seed")) and not allowed(
        lambda: c.put_object(Bucket=other, Key=f"verify/{user}", Body=b"x"))
    ok &= denied
    print(f"{user:16} {'writer' if writer else 'reader'} | " + "; ".join(row) + f" | {other} denied={denied}")

for b in buckets:
    for o in admin.list_objects_v2(Bucket=b, Prefix="verify/").get("Contents", []):
        admin.delete_object(Bucket=b, Key=o["Key"])
print("cleaned up verify/ keys")
sys.exit(0 if ok else 1)
