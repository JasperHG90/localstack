#!/usr/bin/env bash
# Spike: can a SeaweedFS admin identity come from a static -s3.config file,
# can that admin drive the embedded IAM API, and do API-made users survive a
# restart beside the file-supplied admin? Exits 0 only if all three hold.
set -euo pipefail
IMG=chrislusf/seaweedfs:4.48
NAME=spike-swfs-svc-2
W=$(mktemp -d)
trap 'docker rm -f -v "$NAME" >/dev/null 2>&1 || true; rm -rf "$W"' EXIT

cat >"$W/s3.json" <<'EOF'
{
  "identities": [
    {
      "name": "admin",
      "credentials": [{"accessKey": "SPIKEADMINKEY0000001", "secretKey": "spikeAdminSecret0000000000000000000000001"}],
      "actions": ["Admin", "Read", "Write", "List", "Tagging"]
    }
  ]
}
EOF
cat "$W/s3.json"

docker rm -f -v "$NAME" >/dev/null 2>&1 || true
docker create --name "$NAME" -p 127.0.0.1::8333 "$IMG" \
  server -dir=/data -ip.bind=0.0.0.0 -master.volumeSizeLimitMB=64 \
  -s3 -s3.port=8333 -s3.config=/s3.json -s3.iam.readOnly=false >/dev/null
docker cp "$W/s3.json" "$NAME:/s3.json"
docker start "$NAME" >/dev/null

wait_up() {
  PORT=$(docker port "$NAME" 8333/tcp | head -1 | sed 's/.*://')
  for _ in $(seq 60); do
    code=$(curl -s -o /dev/null -w '%{http_code}' "http://127.0.0.1:$PORT/" || true)
    [ "$code" != "000" ] && [ "$code" != "503" ] && { echo "s3 up on $PORT (http $code)"; return 0; }
    sleep 1
  done
  docker logs "$NAME" 2>&1 | tail -40; return 1
}

cat >"$W/probe.py" <<'EOF'
import json, sys, time, boto3
from botocore.config import Config
phase, port = sys.argv[1], sys.argv[2]
ep = f"http://127.0.0.1:{port}"
cfg = Config(retries={"max_attempts": 1}, s3={"addressing_style": "path"})
def cli(svc, ak, sk):
    return boto3.client(svc, endpoint_url=ep, aws_access_key_id=ak,
                        aws_secret_access_key=sk, region_name="us-east-1", config=cfg)
ADMIN = ("SPIKEADMINKEY0000001", "spikeAdminSecret0000000000000000000000001")
ok = True
def check(label, fn):
    global ok
    try:
        r = fn(); print(f"PASS {label}: {r}")
        return r
    except Exception as e:
        ok = False; print(f"FAIL {label}: {type(e).__name__}: {e}")
s3a, iam = cli("s3", *ADMIN), cli("iam", *ADMIN)
try:
    cli("s3", "NOPEKEY", "nopesecret").list_buckets(); ok = False; print("FAIL bad key was accepted")
except Exception as e:
    print(f"PASS bad key refused: {type(e).__name__}")
if phase == "first":
    check("admin create bucket", lambda: s3a.create_bucket(Bucket="spike")["ResponseMetadata"]["HTTPStatusCode"])
    check("admin put object", lambda: s3a.put_object(Bucket="spike", Key="a.txt", Body=b"hi")["ETag"])
    check("iam CreateUser", lambda: iam.create_user(UserName="app")["User"]["UserName"])
    k = check("iam CreateAccessKey", lambda: iam.create_access_key(UserName="app")["AccessKey"])
    pol = {"Version": "2012-10-17", "Statement": [{"Effect": "Allow",
           "Action": ["s3:GetObject", "s3:PutObject", "s3:ListBucket"],
           "Resource": ["arn:aws:s3:::spike", "arn:aws:s3:::spike/*"]}]}
    check("iam PutUserPolicy", lambda: iam.put_user_policy(UserName="app", PolicyName="p",
          PolicyDocument=json.dumps(pol))["ResponseMetadata"]["HTTPStatusCode"])
    if k:
        open(sys.argv[3], "w").write(json.dumps([k["AccessKeyId"], k["SecretAccessKey"]]))
        time.sleep(2)
        s3u = cli("s3", k["AccessKeyId"], k["SecretAccessKey"])
        check("app key reads spike/a.txt", lambda: s3u.get_object(Bucket="spike", Key="a.txt")["Body"].read())
        try:
            s3u.create_bucket(Bucket="other"); ok = False; print("FAIL app key could create bucket")
        except Exception as e:
            print(f"PASS app key denied CreateBucket: {type(e).__name__}")
else:
    ak, sk = json.load(open(sys.argv[3]))
    check("admin still lists buckets", lambda: [b["Name"] for b in s3a.list_buckets()["Buckets"]])
    check("admin still reads object", lambda: s3a.get_object(Bucket="spike", Key="a.txt")["Body"].read())
    check("iam ListUsers", lambda: [u["UserName"] for u in iam.list_users()["Users"]])
    check("iam GetUserPolicy app", lambda: iam.get_user_policy(UserName="app", PolicyName="p")["PolicyName"])
    s3u = cli("s3", ak, sk)
    check("app key still reads after restart", lambda: s3u.get_object(Bucket="spike", Key="a.txt")["Body"].read())
print("RESULT", phase, "ok" if ok else "FAILED")
sys.exit(0 if ok else 1)
EOF

PY() { uv run -q --no-project --with boto3 python3 -I "$W/probe.py" "$@"; }

docker exec "$NAME" ls -l /s3.json
wait_up
sleep 3
echo "== phase 1: fresh start"
rc1=0; PY first "$PORT" "$W/key.json" || rc1=$?
docker exec "$NAME" sh -c 'echo "s3.configure" | weed shell -master=localhost:9333 2>/dev/null' | head -40 || true

echo "== phase 2: docker restart, same static file"
docker restart "$NAME" >/dev/null
wait_up
sleep 3
rc2=0; PY second "$PORT" "$W/key.json" || rc2=$?
docker logs "$NAME" 2>&1 | grep -iE 'identit|s3.config|iam|static' | head -20 || true
echo "rc1=$rc1 rc2=$rc2"
[ "$rc1" = 0 ] && [ "$rc2" = 0 ]
