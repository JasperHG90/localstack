"""Per-bucket isolation in SeaweedFS: static s3.config actions vs IAM user policy."""
import json, sys, time, boto3
from botocore.config import Config
from botocore.exceptions import ClientError

EP = sys.argv[1]
CFG = Config(retries={"max_attempts": 1}, s3={"addressing_style": "path"})

def s3(ak, sk):
    return boto3.client("s3", endpoint_url=EP, aws_access_key_id=ak, aws_secret_access_key=sk, region_name="us-east-1", config=CFG)

def iam(ak, sk):
    return boto3.client("iam", endpoint_url=EP, aws_access_key_id=ak, aws_secret_access_key=sk, region_name="us-east-1", config=CFG)

def attempt(fn):
    try:
        r = fn()
        return "ok", r
    except ClientError as e:
        return e.response["Error"]["Code"], None

admin = s3("ADMINKEY", "ADMINSECRET")
for b in ("bkt-a", "bkt-b"):
    admin.create_bucket(Bucket=b)
    admin.put_object(Bucket=b, Key="seed.txt", Body=b"seed")

# Mechanism B: IAM API users with inline policies.
im = iam("ADMINKEY", "ADMINSECRET")
def bucket_policy(actions):
    return json.dumps({"Version": "2012-10-17", "Statement": [
        {"Effect": "Allow", "Action": actions, "Resource": ["arn:aws:s3:::bkt-a", "arn:aws:s3:::bkt-a/*"]}]})
creds = {"static": {"writer-a": ("WRITERAKEY", "WRITERASECRET"), "reader-a": ("READERAKEY", "READERASECRET")}, "iam": {}}
policies = {"writer-a": ["s3:GetObject", "s3:PutObject", "s3:DeleteObject", "s3:ListBucket"],
            "reader-a": ["s3:GetObject", "s3:ListBucket"]}
for user, acts in policies.items():
    name = "iam-" + user
    im.create_user(UserName=name)
    k = im.create_access_key(UserName=name)["AccessKey"]
    im.put_user_policy(UserName=name, PolicyName="p", PolicyDocument=bucket_policy(acts))
    creds["iam"][user] = (k["AccessKeyId"], k["SecretAccessKey"])
    print("IAM get_user_policy", name, im.get_user_policy(UserName=name, PolicyName="p")["PolicyDocument"])
time.sleep(3)  # let identity changes propagate

def ops(c, bucket):
    return {
        "put": lambda: c.put_object(Bucket=bucket, Key="x.txt", Body=b"x"),
        "get": lambda: c.get_object(Bucket=bucket, Key="seed.txt")["Body"].read(),
        "list": lambda: c.list_objects_v2(Bucket=bucket),
        "delete": lambda: c.delete_object(Bucket=bucket, Key="x.txt" if bucket == "bkt-a" else "seed.txt"),
    }

expect = {
    "writer-a": {"bkt-a": dict(put=True, get=True, list=True, delete=True), "bkt-b": dict(put=False, get=False, list=False, delete=False)},
    "reader-a": {"bkt-a": dict(put=False, get=True, list=True, delete=False), "bkt-b": dict(put=False, get=False, list=False, delete=False)},
}
verdict = {}
for mech in ("static", "iam"):
    bad = 0
    for user, per in expect.items():
        c = s3(*creds[mech][user])
        if user == "reader-a":  # give reader something to fail deleting
            admin.put_object(Bucket="bkt-a", Key="x.txt", Body=b"x")
        for bucket, want in per.items():
            fns = ops(c, bucket)
            for op in ("put", "get", "list", "delete"):
                got, _ = attempt(fns[op])
                allowed = got == "ok"
                flag = "PASS" if allowed == want[op] else "FAIL"
                bad += flag == "FAIL"
                print(f"{mech:6} {user:8} {op:6} {bucket}: want {'allow' if want[op] else 'deny ':5} got {got:14} {flag}")
        st, r = attempt(lambda: c.list_buckets())
        names = [b["Name"] for b in r["Buckets"]] if r else None
        print(f"{mech:6} {user:8} ListBuckets: {st} {names}")
        st, _ = attempt(lambda: c.get_bucket_location(Bucket="bkt-a"))
        print(f"{mech:6} {user:8} GetBucketLocation a: {st}")
    verdict[mech] = bad
    print(f"== {mech}: {bad} mismatches")
# Seed objects in b must survive writer-a/reader-a deletes.
print("bkt-b/seed.txt still present:", attempt(lambda: admin.head_object(Bucket="bkt-b", Key="seed.txt"))[0])
sys.exit(0 if verdict["iam"] == 0 else 1)
