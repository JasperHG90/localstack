#!/bin/bash
# With the fixes the plan names, do both clients get creds and write to their
# own bucket against per-job trust-policy roles, and get refused on the other
# job's role? Exits 0 only if all checks hold. Run from repo root.
set -u
D=/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/spike-wi-4
GOC=$HOME/.cache/spike-go
NET=spike-wi-4-net; S=spike-swfs-wi-4; I=spike-issuer-wi-4
R=arn:aws:iam::role
cleanup() { docker rm -f $I $S >/dev/null 2>&1; docker network rm $NET >/dev/null 2>&1; rm -rf "$W"; }
W=$(mktemp -d -p "$D"); trap cleanup EXIT
docker network create $NET >/dev/null
docker run -d --name $I --network $NET --network-alias issuer -v $D/issuer.py:/issuer.py:ro \
  python:3.12-alpine sh -c 'pip install -q "pyjwt[crypto]" 2>/dev/null && python /issuer.py' >/dev/null
docker run -d --name $S --network $NET -v $D/iam.json:/iam.json:ro chrislusf/seaweedfs:4.48 \
  mini -dir=/data -s3.port=8333 -s3.iam.config=/iam.json >/dev/null
for i in $(seq 90); do docker run --rm --network $NET busybox:1.37 wget -q -O /dev/null http://issuer:8080/.well-known/jwks.json 2>/dev/null && break; sleep 2; done
for i in $(seq 60); do
  docker exec $S sh -c 'printf "s3.bucket.create -name loki\ns3.bucket.create -name tempo\n" | weed shell' >/dev/null 2>&1
  docker exec $S sh -c 'echo s3.bucket.list | weed shell 2>&1' | grep -q tempo && break; sleep 2
done
echo "buckets: $(docker exec $S sh -c 'echo s3.bucket.list | weed shell 2>&1' | grep -E 'loki|tempo' | tr '\n' ' ')"
for j in loki tempo; do docker run --rm --network $NET busybox:1.37 wget -q -O - "http://issuer:8080/mint?job=$j" > $W/$j.jwt; done

docker run --rm -u $(id -u):$(id -g) -e HOME=/tmp -e GOMODCACHE=/gocache/mod -e GOCACHE=/gocache/build -e GOFLAGS=-mod=mod \
  -v $GOC:/gocache -v $D:/src:ro -w /src golang:1.25-alpine sh -c 'CGO_ENABLED=0 go build -o /gocache/stsclient4 .' || exit 3

# loki.hcl's helper as rendered, plus the fix: &RoleArn=<role>&RoleSessionName=<job>.
awk '/#!\/bin\/sh/{p=1} p&&/^        EOF/{exit} p' deployments/applications/services/loki.hcl \
  | sed -e 's/^        //' -e 's/\$\$/$/g' > $W/helper.tmpl
grep -q 'WebIdentityToken=\${jwt}"' $W/helper.tmpl || { echo "helper template changed"; exit 3; }
FAIL=0
expect() { # want(ok|fail) label rc
  if { [ $1 = ok ] && [ $3 = 0 ]; } || { [ $1 = fail ] && [ $3 != 0 ]; }; then echo "PASS $2"; else echo "FAIL $2"; FAIL=1; fi
}
helper() { # label token role bucket
  sed -e "s|\${minio_host}:9000|$S:8333|" -e "s|WebIdentityToken=\${jwt}\"|WebIdentityToken=\${jwt}\&RoleArn=$3\&RoleSessionName=loki\"|" $W/helper.tmpl > $W/h.sh
  out=$(docker run --rm --network $NET -v $W/h.sh:/h.sh:ro -v $W/$2.jwt:/secrets/nomad_minio.jwt:ro busybox:1.37 sh /h.sh 2>&1)
  rc=$?; echo "[helper $1] exit $rc: $(echo "$out" | sed -E 's/"(SecretAccessKey|SessionToken)":"[^"]*"/"\1":"..."/g' | head -c 300)"
  [ $rc = 0 ] || return $rc
  echo "$out" > $W/creds.json
  out=$(docker run --rm --network $NET -e CREDS_JSON=/creds.json -e S3_ENDPOINT=$S:8333 -e BUCKET=$4 \
    -v $GOC/stsclient4:/c:ro -v $W/creds.json:/creds.json:ro alpine:3 /c 2>&1)
  rc=$?; echo "[helper $1 put] exit $rc: $(echo "$out" | tr '\n' ' ' | head -c 300)"; return $rc
}
goc() { # label token role bucket
  out=$(docker run --rm --network $NET -e AWS_WEB_IDENTITY_TOKEN_FILE=/secrets/nomad.jwt -e TEST_IAM_ENDPOINT=http://$S:8333 \
    -e S3_ENDPOINT=$S:8333 -e AWS_ROLE_ARN=$3 -e BUCKET=$4 -v $GOC/stsclient4:/c:ro -v $W/$2.jwt:/secrets/nomad.jwt:ro alpine:3 /c 2>&1)
  rc=$?; echo "[minio-go $1] exit $rc: $(echo "$out" | tr '\n' ' ' | head -c 300)"; return $rc
}
echo "== (a) shell helper (loki.hcl) with RoleArn + RoleSessionName"
helper "loki token, LokiRole, put loki" loki $R/LokiRole loki; expect ok "a1 helper loki->LokiRole gets creds and puts to loki" $?
helper "loki token, TempoRole" loki $R/TempoRole tempo; expect fail "a2 helper loki->TempoRole refused" $?
echo "== (b) minio-go v7.1.0 with AWS_ROLE_ARN"
goc "tempo token, TempoRole, put tempo" tempo $R/TempoRole tempo; expect ok "b1 minio-go tempo->TempoRole gets creds and puts to tempo" $?
goc "loki token, TempoRole" loki $R/TempoRole tempo; expect fail "b2 minio-go loki->TempoRole refused" $?
echo "-- raw STS answer for loki token asking TempoRole:"
docker run --rm --network $NET curlimages/curl:8.11.1 -s -w ' [HTTP %{http_code}]' -X POST \
  "http://$S:8333/?Action=AssumeRoleWithWebIdentity&Version=2011-06-15&RoleArn=$R/TempoRole&RoleSessionName=loki&WebIdentityToken=$(cat $W/loki.jwt)" | head -c 600; echo
exit $FAIL
