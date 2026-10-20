# probe.py PHASE PORT OVID OVSECRET BKID BKSECRET: access checks for the openviking and backup keys.
import sys, boto3
from botocore.config import Config
phase, port, ovid, ovsec, bkid, bksec = sys.argv[1:7]
cfg = Config(retries={"max_attempts": 1}, s3={"addressing_style": "path"})
def s3(ak, sk):
    return boto3.client("s3", endpoint_url=f"http://127.0.0.1:{port}", aws_access_key_id=ak,
                        aws_secret_access_key=sk, region_name="us-east-1", config=cfg)
admin = s3("SPIKEADMINKEY0000001", "spikeAdminSecret0000000000000000000000001")
ov, bk = s3(ovid, ovsec), s3(bkid, bksec)
fails = 0
def want(expect, label, fn):
    global fails
    try:
        msg = str(fn())[:80]; got = True
    except Exception as e:
        msg = f"{type(e).__name__}: {str(e)[:140]}"; got = False
    fails += got != expect
    print(f"{'PASS' if got == expect else 'FAIL'} [{phase}] {label} ({'allowed' if got else 'denied'}) {msg}")
def keys(c, b):
    return sorted(o["Key"] for o in c.list_objects_v2(Bucket=b).get("Contents", []))
def put(c, b, k): return c.put_object(Bucket=b, Key=k, Body=b"x")["ResponseMetadata"]["HTTPStatusCode"]
def get(c, b, k): return c.get_object(Bucket=b, Key=k)["Body"].read()
def delete(c, b, k):
    c.delete_object(Bucket=b, Key=k)
    if k in keys(admin, b):
        raise RuntimeError("delete returned ok but object still there")
    return "deleted"
want(False, "unknown key refused", lambda: s3("NOPEKEY0000000000000", "nope").list_buckets())
if phase == "step1":
    want(True, "ov put openviking/old1", lambda: put(ov, "openviking", "old1"))
    want(True, "ov put openviking/old2", lambda: put(ov, "openviking", "old2"))
    want(True, "ov get openviking/old1", lambda: get(ov, "openviking", "old1"))
    want(True, "ov list openviking", lambda: keys(ov, "openviking"))
    want(True, "ov delete openviking/old2", lambda: delete(ov, "openviking", "old2"))
    want(False, "ov put loki", lambda: put(ov, "loki", "x"))
    want(True, "backup get openviking/old1", lambda: get(bk, "openviking", "old1"))
else:
    want(False, "ov put openviking/new", lambda: put(ov, "openviking", "new"))
    want(False, "ov get openviking/old1", lambda: get(ov, "openviking", "old1"))
    want(False, "ov list openviking", lambda: keys(ov, "openviking"))
    want(False, "ov delete openviking/old1", lambda: delete(ov, "openviking", "old1"))
    want(True, "admin still sees openviking/old1", lambda: get(admin, "openviking", "old1"))
    want(True, "ov put openviking-v2/a", lambda: put(ov, "openviking-v2", "a"))
    want(True, "ov put openviking-v2/b", lambda: put(ov, "openviking-v2", "b"))
    want(True, "ov get openviking-v2/a", lambda: get(ov, "openviking-v2", "a"))
    want(True, "ov list openviking-v2", lambda: keys(ov, "openviking-v2"))
    want(True, "ov delete openviking-v2/b", lambda: delete(ov, "openviking-v2", "b"))
    want(False, "ov put loki", lambda: put(ov, "loki", "x"))
    want(True, "backup get openviking/old1", lambda: get(bk, "openviking", "old1"))
    want(True, "backup get openviking-v2/a", lambda: get(bk, "openviking-v2", "a"))
    want(True, "backup list openviking-v2", lambda: keys(bk, "openviking-v2"))
print(f"RESULT {phase} fails={fails}")
sys.exit(1 if fails else 0)
