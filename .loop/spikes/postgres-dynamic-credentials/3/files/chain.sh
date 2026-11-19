#!/usr/bin/env bash
# Risk 3 (a): does the S2 write-only chain still validate and apply in ONE apply on
# today's pins (cyrilgdn/postgresql 1.26.0, hashicorp/vault 5.3.0), leaving zero
# copies of the password in state? Throwaway root, LOCAL state, every object
# prefixed spike_r3, destroyed at the end. Exits 0 only when the chain works.
set -uo pipefail
eval "$(localstack env 2>/dev/null)"
export TF_IN_AUTOMATION=1
ROOT=/tmp/claude-1000/-home-vscode-workspace/5b5de334-808c-4b22-977c-aa8f1886ca6d/scratchpad/spike-r3/tfroot
rm -rf "$ROOT"; mkdir -p "$ROOT"; cd "$ROOT"
fail=0; bad() { echo "FAIL: $*"; fail=1; }

cat > main.tf <<'EOF'
terraform {
  required_providers {
    vault      = { source = "hashicorp/vault", version = "5.3.0" }
    postgresql = { source = "cyrilgdn/postgresql", version = "1.26.0" }
    random     = { source = "hashicorp/random", version = "3.9.0" }
    consul     = { source = "hashicorp/consul", version = "~>2.22.0" }
  }
}

provider "vault" {}
provider "consul" {
  address    = "192.168.2.30:8500"
  datacenter = "localstack"
}

data "consul_service" "postgres" {
  name       = "postgres-db"
  datacenter = "localstack"
}

ephemeral "vault_kv_secret_v2" "postgres_admin" {
  mount = "secret"
  name  = "default/postgres/localstack"
}

provider "postgresql" {
  host            = data.consul_service.postgres.service[0].node_address
  port            = "5432"
  username        = ephemeral.vault_kv_secret_v2.postgres_admin.data.username
  password        = ephemeral.vault_kv_secret_v2.postgres_admin.data.password
  sslmode         = "disable"
  connect_timeout = 15
}

locals { version = "1" }

ephemeral "random_password" "admin" {
  length  = 32
  special = false
}

resource "postgresql_role" "admin" {
  name                = "spike_r3_admin"
  login               = true
  password_wo         = ephemeral.random_password.admin.result
  password_wo_version = local.version
}

resource "vault_kv_secret_v2" "admin" {
  mount               = "secret"
  name                = "spike_r3/admin"
  disable_read        = true
  delete_all_versions = true
  data_json_wo = jsonencode({
    username = postgresql_role.admin.name
    password = ephemeral.random_password.admin.result
  })
  data_json_wo_version = local.version
}

resource "vault_mount" "db" {
  path = "spike_r3_database"
  type = "database"
}

resource "vault_database_secret_backend_connection" "pg" {
  backend       = vault_mount.db.path
  name          = "spike_r3"
  allowed_roles = []
  postgresql {
    connection_url      = "postgresql://{{username}}:{{password}}@${data.consul_service.postgres.service[0].node_address}:5432/postgres?sslmode=disable"
    username            = postgresql_role.admin.name
    password_wo         = ephemeral.random_password.admin.result
    password_wo_version = local.version
  }
}
EOF

cleanup() {
  echo "== destroy"
  terraform destroy -auto-approve -no-color >destroy.log 2>&1 || { tail -20 destroy.log; bad "destroy"; }
  grep -E 'Destroy complete' destroy.log
  echo "== gone?"
  vault secrets list -format=json | grep -q '"spike_r3_database/"' && bad "mount still there" || echo "mount spike_r3_database/: gone"
  vault kv metadata get -mount=secret spike_r3/admin >/dev/null 2>&1 && bad "kv still there" || echo "kv secret/spike_r3/admin: gone"
  n=$(pgq "select count(*) from pg_roles where rolname='spike_r3_admin'")
  [ "$n" = "0" ] && echo "pg role spike_r3_admin: gone" || bad "pg role still there ($n)"
}

pgq() {  # query as the localstack admin
  PGH="$PGH" PGU="$(vault kv get -mount=secret -field=username default/postgres/localstack)" \
  PGP="$(vault kv get -mount=secret -field=password default/postgres/localstack)" Q="$1" \
  uv run --quiet --no-project --with 'psycopg[binary]' python -I -c '
import os, psycopg
with psycopg.connect(host=os.environ["PGH"], user=os.environ["PGU"], password=os.environ["PGP"], dbname="postgres", connect_timeout=10) as c:
    print(c.execute(os.environ["Q"]).fetchone()[0])'
}
PGH=$(curl -s -H "X-Consul-Token: ${CONSUL_HTTP_TOKEN}" "${CONSUL_HTTP_ADDR}/v1/catalog/service/postgres-db" | python3 -c 'import json,sys; print(json.load(sys.stdin)[0]["Address"])')

echo "== init"
terraform init -no-color -input=false >init.log 2>&1 || { tail -20 init.log; echo "FAIL: init"; exit 2; }
grep -E 'Installed|Installing' init.log
echo "== validate"
terraform validate -no-color || { echo "FAIL: validate"; exit 3; }

trap cleanup EXIT
echo "== apply (one apply, no targets)"
if terraform apply -auto-approve -no-color -input=false >apply.log 2>&1; then
  grep -E 'Apply complete|Creation complete' apply.log
else
  tail -30 apply.log; bad "apply"
fi

echo "== password from KV (written by data_json_wo)"
PW=$(vault kv get -mount=secret -field=password spike_r3/admin 2>/dev/null)
[ ${#PW} -eq 32 ] && echo "kv password length ${#PW}" || bad "kv password missing/len ${#PW}"

echo "== role accepts the KV password (password_wo reached Postgres)"
PGH="$PGH" PW="$PW" uv run --quiet --no-project --with 'psycopg[binary]' python -I -c '
import os, psycopg
with psycopg.connect(host=os.environ["PGH"], user="spike_r3_admin", password=os.environ["PW"], dbname="postgres", connect_timeout=10) as c:
    print("login ok as", c.execute("select current_user").fetchone()[0])' || bad "role login with KV password"

echo "== vault connection (verify_connection passed at apply)"
vault read -format=json spike_r3_database/config/spike_r3 \
  | python3 -c 'import json,sys; d=json.load(sys.stdin)["data"]; print("username", d["connection_details"]["username"], "verify", d["verify_connection"])' || bad "connection read"

echo "== state: copies of the password"
n=$(grep -c -F "$PW" terraform.tfstate); echo "occurrences of password in terraform.tfstate: $n (bytes: $(wc -c <terraform.tfstate))"
[ "$n" = "0" ] || bad "password in state"
for f in terraform.tfstate.backup .terraform/terraform.tfstate apply.log; do
  [ -f "$f" ] && { m=$(grep -c -F "$PW" "$f"); echo "occurrences in $f: $m"; [ "$m" = "0" ] || bad "password in $f"; }
done
echo "== state: password/data attribute values"
python3 - <<'PY'
import json
s = json.load(open("terraform.tfstate"))
def walk(o, p=""):
    if isinstance(o, dict):
        for k, v in o.items(): yield from walk(v, f"{p}.{k}")
    elif isinstance(o, list):
        for i, v in enumerate(o): yield from walk(v, f"{p}[{i}]")
    else: yield p, o
for r in s["resources"]:
    for inst in r["instances"]:
        for path, v in walk(inst["attributes"]):
            leaf = path.rsplit(".", 1)[-1].split("[")[0]
            if "password" in leaf or leaf.startswith("data"):
                print(f'{r["type"]}.{r["name"]}{path} = {v!r}')
PY

echo "== second plan (unchanged versions must be a no-op)"
terraform plan -detailed-exitcode -no-color -input=false >plan2.log 2>&1; rc=$?
grep -E 'No changes|Plan:' plan2.log; echo "plan rc=$rc"
[ $rc -eq 0 ] || { tail -30 plan2.log; bad "second plan not clean"; }

trap - EXIT
cleanup
echo "fail=$fail"
exit $fail
