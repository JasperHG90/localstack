#!/usr/bin/env bash
# Spike: does hashicorp/aws manage buckets + IAM users/keys/inline policies on SeaweedFS's
# embedded IAM API, with a clean second plan? Also probes aminueza/minio. Exit 0 = risk does not hold.
set -u
NAME=spike-swfs-bkt-1
IMG=chrislusf/seaweedfs:4.48
W=$(mktemp -d "$HOME/.spike-swfs-XXXX")
export TF_PLUGIN_CACHE_DIR=$HOME/.terraform.d/plugin-cache TF_IN_AUTOMATION=1
cleanup() { docker rm -f $NAME >/dev/null 2>&1; rm -rf "$W"; }
trap cleanup EXIT
cat > "$W/s3.json" <<J
{"identities":[{"name":"admin","credentials":[{"accessKey":"spikeadmin","secretKey":"spikeadminsecret"}],"actions":["Admin","Read","Write","List","Tagging"]}]}
J
chmod 644 "$W/s3.json"

start() { # $1 = extra flags
  docker rm -f $NAME >/dev/null 2>&1
  docker run -d --name $NAME -p 127.0.0.1::8333 -v "$W/s3.json:/s3.json:ro" $IMG \
    server -dir=/data -s3 -s3.config=/s3.json $1 >/dev/null
  wait_up
}
wait_up() {
  PORT=$(docker port $NAME 8333/tcp | head -1 | sed 's/.*://')
  for i in $(seq 60); do curl -s -o /dev/null "http://127.0.0.1:$PORT/" && break; sleep 1; done
  sleep 3; echo "s3 on port $PORT"
}

mkaws() { mkdir -p "$W/aws"; cat > "$W/aws/main.tf" <<'T'
terraform {
  required_providers {
    aws = { source = "hashicorp/aws", version = "~> 6.0" }
  }
}
variable "endpoint" {}
provider "aws" {
  region                      = "us-east-1"
  access_key                  = "spikeadmin"
  secret_key                  = "spikeadminsecret"
  skip_credentials_validation = true
  skip_requesting_account_id  = true
  skip_metadata_api_check     = true
  skip_region_validation      = true
  s3_use_path_style           = true
  endpoints {
    s3  = var.endpoint
    iam = var.endpoint
  }
}
locals { apps = toset(["alpha", "beta"]) }
resource "aws_s3_bucket" "b" {
  for_each = local.apps
  bucket   = "spike-${each.key}"
}
resource "aws_iam_user" "u" {
  for_each = local.apps
  name     = "spike-${each.key}"
}
resource "aws_iam_access_key" "k" {
  for_each = local.apps
  user     = aws_iam_user.u[each.key].name
}
resource "aws_iam_user_policy" "p" {
  for_each = local.apps
  name     = "spike-${each.key}-rw"
  user     = aws_iam_user.u[each.key].name
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["s3:*"]
      Resource = [aws_s3_bucket.b[each.key].arn, "${aws_s3_bucket.b[each.key].arn}/*"]
    }]
  })
}
output "keys" { value = { for k, v in aws_iam_access_key.k : k => v.id } }
T
}
tf() { terraform -chdir="$1" "${@:2}" -no-color; }

echo "=== PHASE 0: default flags (s3.iam.readOnly default) - can IAM be written at all? ==="
start ""
mkaws
tf "$W/aws" init -input=false >/dev/null || { echo "aws init failed"; exit 2; }
tf "$W/aws" apply -auto-approve -input=false -var endpoint=http://127.0.0.1:$PORT 2>&1 | grep -E 'Error|error|Creation complete|Apply complete' | head -20
rm -f "$W/aws/terraform.tfstate"*

echo; echo "=== PHASE 1: -s3.iam.readOnly=false, aws provider apply ==="
start "-s3.iam.readOnly=false"
tf "$W/aws" apply -auto-approve -input=false -var endpoint=http://127.0.0.1:$PORT > "$W/apply.log" 2>&1; A=$?
grep -E 'Error|error|Creation complete|Apply complete|with aws' "$W/apply.log" | head -40
echo "apply exit $A"

echo; echo "=== PHASE 2: second plan ==="
tf "$W/aws" plan -detailed-exitcode -input=false -var endpoint=http://127.0.0.1:$PORT > "$W/plan2.log" 2>&1; P2=$?
grep -vE '^\s*$|Refreshing|Reading|Read complete' "$W/plan2.log" | head -60
echo "second plan detailed exit $P2 (0 = clean, 2 = changes)"

echo; echo "=== PHASE 3: restart container, plan again (IAM persistence) ==="
docker restart $NAME >/dev/null; wait_up
tf "$W/aws" plan -detailed-exitcode -input=false -var endpoint=http://127.0.0.1:$PORT > "$W/plan3.log" 2>&1; P3=$?
grep -vE '^\s*$|Refreshing|Reading|Read complete' "$W/plan3.log" | head -40
echo "post-restart plan detailed exit $P3"

echo; echo "=== PHASE 4: aminueza/minio ~> 3.8 against the same server ==="
mkdir -p "$W/minio"; cat > "$W/minio/main.tf" <<'T'
terraform {
  required_providers {
    minio = { source = "aminueza/minio", version = "~> 3.8" }
  }
}
variable "server" {}
provider "minio" {
  minio_server   = var.server
  minio_user     = "spikeadmin"
  minio_password = "spikeadminsecret"
  minio_region   = "us-east-1"
}
resource "minio_s3_bucket" "b" { bucket = "spike-gamma" }
resource "minio_iam_user" "u" { name = "spike-gamma" }
resource "minio_iam_policy" "p" {
  name   = "spike-gamma-rw"
  policy = jsonencode({ Version = "2012-10-17", Statement = [{ Effect = "Allow", Action = ["s3:*"], Resource = ["arn:aws:s3:::spike-gamma", "arn:aws:s3:::spike-gamma/*"] }] })
}
resource "minio_iam_user_policy_attachment" "a" {
  user_name   = minio_iam_user.u.name
  policy_name = minio_iam_policy.p.name
}
T
tf "$W/minio" init -input=false >/dev/null || echo "minio init failed"
tf "$W/minio" apply -auto-approve -input=false -var server=127.0.0.1:$PORT > "$W/minio.log" 2>&1; M=$?
grep -E 'Error|error|Creation complete|Apply complete|with minio' "$W/minio.log" | head -30
echo "minio apply exit $M"
if [ $M -eq 0 ]; then tf "$W/minio" plan -detailed-exitcode -input=false -var server=127.0.0.1:$PORT >/dev/null 2>&1; echo "minio second plan exit $?"; fi

echo; echo "SUMMARY aws_apply=$A aws_plan2=$P2 aws_plan_after_restart=$P3 minio_apply=$M"
[ $A -eq 0 ] && [ $P2 -eq 0 ] && [ $P3 -eq 0 ]
