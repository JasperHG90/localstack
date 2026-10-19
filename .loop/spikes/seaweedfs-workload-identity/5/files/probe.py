# probe.py PHASE S3PORT ISSUERPORT TFKEYID TFSECRET : admin, terraform key and STS checks.
import sys, re, urllib.request, urllib.error, boto3
from botocore.config import Config
phase, port, iport, tfid, tfsec = sys.argv[1:6]
ep = f"http://127.0.0.1:{port}"
cfg = Config(retries={"max_attempts": 1}, s3={"addressing_style": "path"})
def s3(ak, sk, tok=None):
    return boto3.client("s3", endpoint_url=ep, aws_access_key_id=ak, aws_secret_access_key=sk,
                        aws_session_token=tok, region_name="us-east-1", config=cfg)
fails = 0
def want(ok_expected, label, fn):
    global fails
    try:
        r = fn(); got = True; msg = str(r)[:80]
    except Exception as e:
        got = False; msg = f"{type(e).__name__}: {str(e)[:160]}"
    good = got == ok_expected
    fails += not good
    print(f"{'PASS' if good else 'FAIL'} [{phase}] {label} ({'allowed' if got else 'denied'}) {msg}")
def put_get(c, b, k):
    c.put_object(Bucket=b, Key=k, Body=b"x-" + k.encode())
    assert c.get_object(Bucket=b, Key=k)["Body"].read() == b"x-" + k.encode(); return "put+get ok"
def mint(job):
    return urllib.request.urlopen(f"http://127.0.0.1:{iport}/mint?job={job}").read().decode()
def sts(job, role="arn:aws:iam::role/wi-probe"):
    url = (f"{ep}/?Action=AssumeRoleWithWebIdentity&Version=2011-06-15&RoleArn={role}"
           f"&RoleSessionName={job}&WebIdentityToken={mint(job)}")
    try:
        body = urllib.request.urlopen(urllib.request.Request(url, data=b"", method="POST")).read().decode()
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"HTTP {e.code}: {e.read().decode()[:120]}")
    g = lambda t: re.search(f"<{t}>([^<]+)</{t}>", body).group(1)
    return g("AccessKeyId"), g("SecretAccessKey"), g("SessionToken")

admin = s3("SPIKEADMINKEY0000001", "spikeAdminSecret0000000000000000000000001")
want(False, "unknown key refused", lambda: s3("NOPEKEY0000000000000", "nope").list_buckets())
if phase == "first":
    want(True, "1 admin create bucket adminb", lambda: admin.create_bucket(Bucket="adminb")["ResponseMetadata"]["HTTPStatusCode"])
    want(True, "1 admin create bucket wi-probe", lambda: admin.create_bucket(Bucket="wi-probe")["ResponseMetadata"]["HTTPStatusCode"])
want(True, "1 admin put/get adminb", lambda: put_get(admin, "adminb", f"a-{phase}"))
want(True, "1 admin lists buckets", lambda: sorted(b["Name"] for b in admin.list_buckets()["Buckets"]))
if tfid != "-":
    tf = s3(tfid, tfsec)
    want(True, "2 terraform key put/get tfapp", lambda: put_get(tf, "tfapp", f"t-{phase}"))
    want(False, "2 terraform key put adminb", lambda: tf.put_object(Bucket="adminb", Key="t", Body=b"x"))
    want(False, "2 terraform key get adminb", lambda: tf.get_object(Bucket="adminb", Key=f"a-{phase}")["Body"].read())
    want(False, "2 terraform key put wi-probe", lambda: tf.put_object(Bucket="wi-probe", Key="t", Body=b"x"))
    want(False, "2 terraform key create bucket", lambda: tf.create_bucket(Bucket=f"tfnew-{phase}"))
    want(True, "1 admin reads tfapp object", lambda: admin.get_object(Bucket="tfapp", Key=f"t-{phase}")["Body"].read())
    c = {}
    want(True, "3 STS wi-probe token -> wi-probe role", lambda: c.setdefault("k", sts("wi-probe"))[0])
    if "k" in c:
        w = s3(*c["k"])
        want(True, "3 STS creds put/get wi-probe", lambda: put_get(w, "wi-probe", f"w-{phase}"))
        want(False, "3 STS creds put tfapp", lambda: w.put_object(Bucket="tfapp", Key="w", Body=b"x"))
        want(False, "3 STS creds put adminb", lambda: w.put_object(Bucket="adminb", Key="w", Body=b"x"))
    want(False, "3 STS wi-probe-other token -> wi-probe role", lambda: sts("wi-probe-other")[0])
print(f"RESULT {phase} fails={fails}")
sys.exit(1 if fails else 0)
