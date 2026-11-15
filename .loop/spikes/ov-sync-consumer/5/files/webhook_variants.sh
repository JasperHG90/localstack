#!/usr/bin/env bash
# Spike ov-sync-consumer risk 2(a), control for spike 4 (which saw the webhook
# dial from 127.0.0.1 and fail). Variant A keeps every seaweedfs.hcl arg and
# puts the listener on loopback in the seaweed container's network namespace
# (a sidecar in the same Nomad group). Variant B drops -ip.bind and posts to
# another container. Below: does the SeaweedFS 4.48 filer webhook fire,
# filtered to /buckets/ov-sync/ and bearer-authed, when weed runs with the exact
# args of deployments/infrastructure/services/seaweedfs.hcl (loopback -ip and
# -ip.bind, S3 on 0.0.0.0, -s3.iam.config with defaultEffect Deny), posting to
# a listener in ANOTHER container? Exits 0 only when it does.
set -u
P=ovc2
NET=$P-net
IMG=docker.io/chrislusf/seaweedfs:4.48
AWS_IMG=amazon/aws-cli:2.27.0
TOKEN=spike-bearer-$RANDOM$RANDOM
AK=AKIASPIKEADMIN0000001
SK=spikeSecretKey0000000000000000000000001
W=$(mktemp -d)
chmod 755 "$W"

cleanup() {
  docker rm -f $P-seaweed $P-listener >/dev/null 2>&1
  docker network rm $NET >/dev/null 2>&1
  rm -rf "$W"
}
trap cleanup EXIT
cleanup >/dev/null 2>&1; W=$(mktemp -d); chmod 755 "$W"

mkdir -p "$W/secrets" "$W/local" "$W/etc" "$W/data"
cat >"$W/secrets/s3.json" <<EOF
{"identities":[{"name":"admin","credentials":[{"accessKey":"$AK","secretKey":"$SK"}],"actions":["Admin","Read","Write","List","Tagging"]}]}
EOF
# Same members as local.seaweedfs_iam in services.tf, with one keyless job.
SIGN=$(head -c 32 /dev/urandom | base64)
cat >"$W/secrets/iam.json" <<EOF
{"sts":{"tokenDuration":"1h","maxSessionLength":"12h","issuer":"seaweedfs-sts","signingKey":"$SIGN"},"policy":{"defaultEffect":"Deny"},"providers":[{"name":"nomad","type":"oidc","enabled":true,"config":{"issuer":"https://nomad.lab.orangecluster.nl","clientId":"seaweedfs"}}],"policies":[{"name":"ov-sync-consumer","document":{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Action":["s3:*"],"Resource":["arn:aws:s3:::ov-sync","arn:aws:s3:::ov-sync/*"]}]}}],"roles":[{"roleName":"ov-sync-consumer","roleArn":"arn:aws:iam::role/ov-sync-consumer","trustPolicy":{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"Federated":"nomad"},"Action":"sts:AssumeRoleWithWebIdentity","Condition":{"StringEquals":{"oidc:nomad_job_id":"ov-sync-consumer"},"StringLike":{"oidc:sub":"global:default:ov-sync-consumer:*"}}}]},"attachedPolicies":["ov-sync-consumer"]}]}
EOF
printf '[master.volume_growth]\ncopy_1 = 2\n' >"$W/local/master.toml"
cat >"$W/etc/notification.toml" <<EOF
[notification.webhook]
enabled = true
endpoint = "ENDPOINT"
bearer_token = "$TOKEN"
path_prefixes = ["/buckets/ov-sync/"]
EOF
cat >"$W/listener.py" <<'EOF'
import json, sys
from http.server import BaseHTTPRequestHandler, HTTPServer
class H(BaseHTTPRequestHandler):
    def do_POST(self):
        body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
        try:
            parsed = json.loads(body)
        except Exception:
            parsed = None
        print(json.dumps({"path": self.path, "auth": self.headers.get("Authorization"),
                          "ctype": self.headers.get("Content-Type"),
                          "json": parsed, "raw": None if parsed is not None else body.decode(errors="replace")}),
              flush=True)
        self.send_response(200); self.end_headers()
    def log_message(self, *a): pass
HTTPServer(("0.0.0.0", 20500), H).serve_forever()
EOF


run_variant() {  # $1 name, $2 endpoint, $3 "sidecar"|"separate", $4 ip.bind flag or ""
  cleanup_c
  rm -rf "$W/data"; mkdir -p "$W/data"
  sed "s#ENDPOINT#$2#" "$W/etc/notification.toml.in" >"$W/etc/notification.toml"
  docker network create $NET >/dev/null
  docker run -d --name $P-seaweed --network $NET \
    -v "$W/secrets:/secrets:ro" -v "$W/data:/data" \
    -v "$W/local/master.toml:/etc/seaweedfs/master.toml:ro" \
    -v "$W/etc/notification.toml:/etc/seaweedfs/notification.toml:ro" \
    $IMG server -dir=/data -s3 -s3.port=8333 -s3.config=/secrets/s3.json \
    -s3.iam.config=/secrets/iam.json -s3.iam.readOnly=false \
    -s3.port.iceberg=0 -s3.port.lance=0 \
    -ip=127.0.0.1 $4 -s3.ip.bind=0.0.0.0 \
    -metricsIp=0.0.0.0 -metricsPort=9327 -volume.max=0 \
    -master.volumeSizeLimitMB=1024 -master.volumePreallocate=false >/dev/null
  if [ "$3" = sidecar ]; then LNET="container:$P-seaweed"; else LNET=$NET; fi
  docker run -d --name $P-listener --network $LNET -v "$W/listener.py:/l.py:ro" \
    python:3.12-alpine python -u /l.py >/dev/null
  for i in $(seq 1 60); do
    docker run --rm --network $NET busybox:1.37 wget -q -T2 -O- http://$P-seaweed:8333/healthz >/dev/null 2>&1 && break
    sleep 1
  done
  echo "===== variant $1: endpoint $2, listener $3, bind flag '${4:-none}'"
  docker exec $P-seaweed netstat -tln | grep LISTEN
  aws s3 mb s3://ov-sync >/dev/null; aws s3 mb s3://other >/dev/null
  aws s3 cp /w/a.md s3://ov-sync/docs/a.md >/dev/null
  aws s3 cp /w/a.md s3://other/docs/b.md >/dev/null
  aws s3 cp /w/a.md s3://ov-sync/docs/a.md >/dev/null
  aws s3 rm s3://ov-sync/docs/a.md >/dev/null
  sleep 8
  echo "-- webhook errors in seaweed log"
  docker logs $P-seaweed 2>&1 | grep -E 'webhook_queue.go:195' | cut -c1-220 | head -3
  echo "-- listener received"
  docker logs $P-listener 2>&1 | tee "$W/events-$1.jsonl"
  python3 - "$W/events-$1.jsonl" "$TOKEN" "$1" <<'PY'
import json, sys
ev = [json.loads(l) for l in open(sys.argv[1]) if l.startswith("{")]
tok = sys.argv[2]; blob = json.dumps(ev)
checks = {
    "some events arrived": len(ev) > 0,
    "every post is JSON": all(e["json"] is not None for e in ev),
    "every post has the bearer header": all(e["auth"] == f"Bearer {tok}" for e in ev),
    "an event names ov-sync/docs/a.md": "a.md" in blob and "ov-sync" in blob,
    "a delete event arrived": any("delete" in json.dumps(e["json"]).lower() for e in ev),
    "nothing from bucket other": "/buckets/other" not in blob and "b.md" not in blob,
}
for k, v in checks.items():
    print(("PASS " if v else "FAIL ") + k)
print("event count:", len(ev))
if ev and isinstance(ev[0]["json"], dict):
    print("keys:", sorted(ev[0]["json"].keys()))
    for e in ev: print("  ", {k: e["json"].get(k) for k in ("event_type", "key")})
open(f"/tmp/ovc2-{sys.argv[3]}.ok", "w").write("1" if all(checks.values()) else "0")
PY
}

cleanup_c() {
  docker rm -f $P-seaweed $P-listener >/dev/null 2>&1
  docker network rm $NET >/dev/null 2>&1
}
mv "$W/etc/notification.toml" "$W/etc/notification.toml.in"
aws() {
  docker run --rm --network $NET -e AWS_ACCESS_KEY_ID=$AK -e AWS_SECRET_ACCESS_KEY=$SK \
    -e AWS_DEFAULT_REGION=us-east-1 -v "$W:/w" $AWS_IMG \
    --endpoint-url http://$P-seaweed:8333 "$@"
}
echo "# spike" >"$W/a.md"
rm -f /tmp/ovc2-A.ok /tmp/ovc2-B.ok
run_variant A "http://127.0.0.1:20500/events" sidecar "-ip.bind=127.0.0.1"
run_variant B "http://$P-listener:20500/events" separate ""
A=$(cat /tmp/ovc2-A.ok); B=$(cat /tmp/ovc2-B.ok); rm -f /tmp/ovc2-A.ok /tmp/ovc2-B.ok
echo "===== A (job args, loopback sidecar) ok=$A; B (no -ip.bind, other container) ok=$B"
[ "$A" = 1 ] && [ "$B" = 1 ]
