#!/bin/bash
# Do tempo's minio-go STS path and loki/registry's shell credential_process
# helper work UNCHANGED against SeaweedFS 4.48's AssumeRoleWithWebIdentity?
# Exits 0 only if both unchanged clients get credentials. Run from repo root.
set -u
D=/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/spike-wi-2
GOC=$HOME/.cache/spike-go
NET=spike-wi-2-net
ROLE=spike-swfs-wi-2      # roles + trust policy, no policyClaim
CLAIM=spike-swfs-wi-2c    # same, plus policyClaim=nomad_job_id
cleanup() { docker rm -f spike-issuer-wi-2 $ROLE $CLAIM >/dev/null 2>&1; docker network rm $NET >/dev/null 2>&1; rm -rf "$W"; }
W=$(mktemp -d -p "$D"); trap cleanup EXIT
docker network create $NET >/dev/null

docker run -d --name spike-issuer-wi-2 --network $NET --network-alias issuer -v $D/issuer.py:/issuer.py:ro \
  python:3.12-alpine sh -c 'pip install -q "pyjwt[crypto]" 2>/dev/null && python /issuer.py' >/dev/null
for n in $ROLE $CLAIM; do
  f=iam-role.json; [ $n = $CLAIM ] && f=iam-claim.json
  docker run -d --name $n --network $NET -v $D/$f:/iam.json:ro chrislusf/seaweedfs:4.48 \
    mini -dir=/data -s3.port=8333 -s3.iam.config=/iam.json >/dev/null
done
for i in $(seq 90); do docker run --rm --network $NET busybox:1.37 wget -q -O /dev/null http://issuer:8080/.well-known/jwks.json 2>/dev/null && break; sleep 2; done
for n in $ROLE $CLAIM; do for i in $(seq 60); do docker run --rm --network $NET busybox:1.37 sh -c "wget -q -O /dev/null http://$n:8333/ 2>&1 | grep -qv 'refused\|bad address'" && break; sleep 2; done; done
sleep 5
docker run --rm --network $NET busybox:1.37 wget -q -O - 'http://issuer:8080/mint?job=tempo' > $W/tempo.jwt
echo "JWT claims: $(cut -d. -f2 $W/tempo.jwt | tr '_-' '/+' | base64 -d 2>/dev/null)"

# The helper exactly as rendered from loki.hcl: strip heredoc indent, undo
# Terraform's $$ escape, point ${minio_host}:9000 at the target.
awk '/#!\/bin\/sh/{p=1} p&&/^        EOF/{exit} p' deployments/applications/services/loki.hcl \
  | sed -e 's/^        //' -e 's/\$\$/$/g' > $W/helper.tmpl
cmp <(sed -n '/#!\/bin\/sh/,/^        EOF/p' deployments/applications/services/registry.hcl | sed '$d' | sed -e 's/^        //' -e 's/\$\$/$/g') $W/helper.tmpl \
  && echo "registry.hcl helper is byte-identical to loki.hcl's"

helper() { # name host extra-query
  sed -e "s|\${minio_host}:9000|$2:8333|" -e "s|WebIdentityToken=|${3//&/\\&}WebIdentityToken=|" $W/helper.tmpl > $W/h-$1.sh
  out=$(docker run --rm --network $NET -v $W/h-$1.sh:/h.sh:ro -v $W/tempo.jwt:/secrets/nomad_minio.jwt:ro busybox:1.37 sh /h.sh 2>&1)
  rc=$?; echo "[helper $1] exit $rc: $(echo "$out" | sed -E 's/"(SecretAccessKey|SessionToken)":"[^"]*"/"\1":"..."/g' | head -c 400)"; return $rc
}
raw() { docker run --rm --network $NET curlimages/curl:8.11.1 -s -w ' [HTTP %{http_code}]' -X POST "http://$1:8333/?Action=AssumeRoleWithWebIdentity&Version=2011-06-15&$2WebIdentityToken=$(cat $W/tempo.jwt)" | sed -E 's/<(SecretAccessKey|SessionToken)>[^<]*/<\1>.../g' | head -c 900; echo; }

echo; echo "== shell helper (loki, registry) =="
helper unchanged-claimsrv $CLAIM ""; H0=$?
helper unchanged-rolesrv $ROLE ""
helper sessname-claimsrv $CLAIM "RoleSessionName=loki&"
helper roleArn-rolesrv $ROLE "RoleArn=arn:aws:iam::role/tempo&"
helper roleArn+sessname-rolesrv $ROLE "RoleArn=arn:aws:iam::role/tempo&RoleSessionName=loki&"
helper sentinel+sessname-claimsrv $CLAIM "RoleArn=arn:aws:iam:::role/sts-claim-based&RoleSessionName=loki&"
echo "-- raw error body, unchanged request, claim server:"; raw $CLAIM ""
echo "-- raw error body, unchanged request, role server:"; raw $ROLE "RoleSessionName=loki&"
echo "-- raw error body, RoleArn but no RoleSessionName, role server:"; raw $ROLE "RoleArn=arn:aws:iam::role/tempo&"
echo "-- raw success body (element names the sed reads):"; raw $CLAIM "RoleSessionName=loki&"

echo; echo "== minio-go v7.1.0 credentials.IAM as tempo 2.10.8 configures it =="
docker run --rm -u $(id -u):$(id -g) -e HOME=/tmp -e GOMODCACHE=/gocache/mod -e GOCACHE=/gocache/build -e GOFLAGS=-mod=mod \
  -v $GOC:/gocache -v $D:/src:ro -w /src golang:1.25-alpine sh -c 'CGO_ENABLED=0 go build -o /gocache/stsclient .' || exit 3
goc() { # name host role-arn
  out=$(docker run --rm --network $NET -e AWS_WEB_IDENTITY_TOKEN_FILE=/secrets/nomad.jwt -e TEST_IAM_ENDPOINT=http://$2:8333 \
    -e S3_ENDPOINT=$2:8333 ${3:+-e AWS_ROLE_ARN=$3} -v $GOC/stsclient:/stsclient:ro -v $W/tempo.jwt:/secrets/nomad.jwt:ro alpine:3 /stsclient 2>&1)
  rc=$?; echo "[minio-go $1] exit $rc: $(echo "$out" | tr '\n' ' ' | head -c 400)"; return $rc
}
goc no-roleArn-claimsrv $CLAIM ""; G0=$?
goc no-roleArn-rolesrv $ROLE ""
goc roleArn-rolesrv $ROLE arn:aws:iam::role/tempo
goc sentinel-claimsrv $CLAIM arn:aws:iam:::role/sts-claim-based

echo; echo "unchanged helper exit=$H0, unchanged minio-go exit=$G0"
[ $H0 = 0 ] && [ $G0 = 0 ]
