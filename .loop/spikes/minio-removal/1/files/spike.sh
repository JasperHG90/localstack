#!/usr/bin/env bash
# Spike: can terraform drop minio_* resources from state with `removed` blocks
# when provider "minio" and its required_providers entry are gone and MinIO is down.
# Exit 0 only if plan+apply succeed in that state, state ends empty, and the
# bucket+object still exist on MinIO afterward.
set -uo pipefail
S=/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/spike-removal-1
W=$S/work
export TF_PLUGIN_CACHE_DIR=$HOME/.terraform.d/plugin-cache TF_IN_AUTOMATION=1 MC_CONFIG_DIR=$S/mc
export MC_HOST_spike=http://admin:adminpass123@localhost:19000
C=spike-rm-minio
cleanup() { docker rm -f $C >/dev/null 2>&1; docker volume rm spike-rm-minio-data >/dev/null 2>&1; rm -rf $W $S/mc; }
trap cleanup EXIT
cleanup
docker run -d --name $C -e MINIO_ROOT_USER=admin -e MINIO_ROOT_PASSWORD=adminpass123 \
  -p 19000:9000 -v spike-rm-minio-data:/data pgsty/minio:latest server /data >/dev/null || exit 3
for i in $(seq 30); do curl -sf localhost:19000/minio/health/live && break; sleep 1; done
mkdir -p $W/modules/bucket

cat > $W/modules/bucket/main.tf <<'TF'
terraform {
  required_providers {
    minio = { source = "aminueza/minio", version = "~>3.8.0" }
  }
}
variable "name" { type = string }
variable "writers" { type = list(string) }
resource "minio_s3_bucket" "bucket" {
  bucket = var.name
  acl    = "private"
}
resource "minio_iam_policy" "policy_read_write" {
  name   = "${var.name}_rw"
  policy = jsonencode({ Version = "2012-10-17", Statement = [{ Effect = "Allow", Action = ["s3:*"], Resource = ["arn:aws:s3:::${minio_s3_bucket.bucket.id}/*"] }] })
}
resource "minio_iam_user_policy_attachment" "bucket_writer" {
  for_each    = toset(var.writers)
  user_name   = each.key
  policy_name = minio_iam_policy.policy_read_write.id
}
TF

cat > $W/main.tf <<'TF'
terraform {
  required_providers {
    minio = { source = "aminueza/minio", version = "~>3.8.0" }
  }
}
provider "minio" {
  minio_server   = "localhost:19000"
  minio_user     = "admin"
  minio_password = "adminpass123"
}
resource "minio_iam_user" "users" {
  for_each = toset(["tester"])
  name     = each.key
}
resource "minio_accesskey" "users" {
  for_each = minio_iam_user.users
  user     = each.value.name
}
resource "minio_iam_policy" "wi" {
  name   = "wi"
  policy = jsonencode({ Version = "2012-10-17", Statement = [{ Effect = "Allow", Action = ["s3:GetObject"], Resource = ["arn:aws:s3:::*"] }] })
}
module "buckets" {
  for_each = toset(["alpha", "beta"])
  source   = "./modules/bucket"
  name     = each.key
  writers  = [minio_iam_user.users["tester"].name]
}
TF

cd $W
echo "=== phase 1: init + apply with provider"
terraform init -input=false -no-color >/dev/null || exit 3
terraform apply -auto-approve -input=false -no-color | tail -2 || exit 3
mc cp $W/main.tf spike/alpha/obj.txt >/dev/null || exit 3
echo "state before:"; terraform state list -no-color

echo "=== phase 2: removed blocks, no provider block, no required_providers, MinIO stopped"
rm -rf $W/modules
cat > $W/main.tf <<'TF'
removed {
  from = module.buckets
  lifecycle { destroy = false }
}
removed {
  from = minio_iam_user.users
  lifecycle { destroy = false }
}
removed {
  from = minio_accesskey.users
  lifecycle { destroy = false }
}
removed {
  from = minio_iam_policy.wi
  lifecycle { destroy = false }
}
TF
docker stop $C >/dev/null
curl -s -m 3 localhost:19000/minio/health/live && echo "MinIO still reachable" && exit 3
echo "MinIO unreachable: ok"
rc=0
terraform init -input=false -no-color 2>&1 | tail -5; [ ${PIPESTATUS[0]} -eq 0 ] || { echo "INIT FAILED"; rc=1; }
terraform plan -input=false -no-color -out=$W/p.tfplan 2>&1; [ ${PIPESTATUS[0]} -eq 0 ] || { echo "PLAN FAILED"; rc=1; }
[ $rc -eq 0 ] && { terraform apply -input=false -no-color $W/p.tfplan 2>&1; [ ${PIPESTATUS[0]} -eq 0 ] || { echo "APPLY FAILED"; rc=1; }; }
n=$(terraform state list 2>/dev/null | wc -l); echo "resources left in state: $n"
[ "$n" -eq 0 ] || rc=1
echo "providers in state after:"; terraform providers -no-color 2>&1 | tail -6

echo "=== phase 3: MinIO back up, data intact"
docker start $C >/dev/null
for i in $(seq 30); do curl -sf localhost:19000/minio/health/live && break; sleep 1; done
mc ls spike/ || rc=1
mc stat spike/alpha/obj.txt >/dev/null && echo "object alpha/obj.txt present" || { echo "object missing"; rc=1; }
mc admin user list spike | grep -q tester && echo "user tester present" || { echo "user missing"; rc=1; }
mc admin policy list spike | grep -E '^(wi|alpha_rw|beta_rw)$' | sort | tr '\n' ' '; echo
docker rm -f $C >/dev/null; docker volume rm spike-rm-minio-data >/dev/null
echo "exit $rc"; exit $rc
