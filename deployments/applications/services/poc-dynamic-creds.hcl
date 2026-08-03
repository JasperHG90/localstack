### S2 SPIKE — THROWAWAY. Destroyed at the end of the spike.
###
### Batch, not service: both tasks run to completion and a service job would
### restart them in a loop. The alloc reports `running` for the ~7 minutes the
### pool task idles, which is when the acceptance check observes it.
job "s2-poc-dynamic-creds" {
  datacenters = ["localstack"]
  type        = "batch"
  namespace   = "default"

  group "poc" {
    count = 1

    restart {
      attempts = 0
      mode     = "fail"
    }

    ### Proves the minted user can do memex's work: a read against a table
    ### memex already owns, then the create/insert/select/drop round-trip a
    ### migration runs. Ownership of the scratch table is recorded, not
    ### assumed — that is the half of R3's failure mode 4 this spike settles.
    task "grant-test" {
      driver = "podman"

      vault {
        role = "${vault_role}"
      }

      ### `.Data.username`, not `.Data.data.username`. KV2 nests its payload
      ### under `data`; a dynamic credential does not.
      template {
        data        = <<EOF
PGUSER="{{ with secret "${creds_path}" }}{{ .Data.username }}{{ end }}"
PGPASSWORD="{{ with secret "${creds_path}" }}{{ .Data.password }}{{ end }}"
EOF
        destination = "secrets/db.env"
        env         = true
      }

      template {
        data        = <<EOF
set -euo pipefail
echo "S2 == identity =="
psql -tAc "select current_user || ' member_of=' || array_to_string(array(select rolname from pg_roles where pg_has_role(current_user, oid, 'member')), ',')"

echo "S2 == read an existing memex-owned table =="
psql -v ON_ERROR_STOP=1 -tAc "select 'entities rows=' || count(*) from entities"

echo "S2 == migration round-trip on a scratch table =="
psql -v ON_ERROR_STOP=1 -c "create table s2_poc_scratch (id int primary key, note text)"
psql -v ON_ERROR_STOP=1 -tAc "select 'scratch owner=' || tableowner from pg_tables where tablename = 's2_poc_scratch'"
psql -v ON_ERROR_STOP=1 -c "insert into s2_poc_scratch values (1, 'written by a vault-minted user')"
psql -v ON_ERROR_STOP=1 -tAc "select 'read back: ' || note from s2_poc_scratch where id = 1"
psql -v ON_ERROR_STOP=1 -c "drop table s2_poc_scratch"

echo "S2 == grant test passed =="
EOF
        destination = "local/grant-test.sh"
      }

      env {
        PGHOST     = "${postgres_host}"
        PGDATABASE = "${database}"
        PGSSLMODE  = "disable"
      }

      config {
        image   = "docker.io/library/postgres:18"
        command = "bash"
        args    = ["/local/grant-test.sh"]
      }

      resources {
        cpu    = 200
        memory = 128
      }
    }

    ### Holds a pooled connection past the role's max_ttl so the rotation
    ### failure has a subject. A psql loop cannot show this: it opens a fresh
    ### connection per invocation, which is the one case that never fails.
    task "pool-test" {
      driver = "podman"

      vault {
        role = "${vault_role}"
      }

      ### change_mode = "noop" is the point of the experiment. The default,
      ### "restart", would kill this task the moment its credential expired —
      ### which is one of the mitigations the spike is meant to characterize,
      ### not the failure it is meant to observe.
      template {
        data        = <<EOF
PGUSER="{{ with secret "${creds_path}" }}{{ .Data.username }}{{ end }}"
PGPASSWORD="{{ with secret "${creds_path}" }}{{ .Data.password }}{{ end }}"
EOF
        destination = "secrets/db.env"
        env         = true
        change_mode = "noop"
      }

      template {
        data        = <<EOF
import os
import time

import psycopg
from psycopg_pool import ConnectionPool

IDLE = int(os.environ["S2_IDLE_SECONDS"])

pool = ConnectionPool(conninfo="", min_size=1, max_size=1, open=True)

with pool.connection() as conn:
    who = conn.execute("select current_user").fetchone()[0]
print("S2 pool: opened as", who, flush=True)

print("S2 pool: idling", IDLE, "seconds, past the role max_ttl", flush=True)
time.sleep(IDLE)

try:
    with pool.connection() as conn:
        rows = conn.execute("select count(*) from entities").fetchone()[0]
    print("S2 pool: HELD connection still works after expiry, rows =", rows, flush=True)
except Exception as error:
    print("S2 pool: HELD connection FAILED after expiry:", type(error).__name__, error, flush=True)

try:
    with psycopg.connect() as conn:
        conn.execute("select 1")
    print("S2 pool: FRESH connect still works after expiry", flush=True)
except Exception as error:
    print("S2 pool: FRESH connect FAILED after expiry:", type(error).__name__, error, flush=True)

print("S2 == pool test done ==", flush=True)
EOF
        destination = "local/pool_test.py"
        change_mode = "noop"
      }

      env {
        PGHOST               = "${postgres_host}"
        PGDATABASE           = "${database}"
        PGSSLMODE            = "disable"
        S2_IDLE_SECONDS      = "${idle_seconds}"
        PIP_ROOT_USER_ACTION = "ignore"
      }

      config {
        image   = "docker.io/library/python:3.12-slim"
        command = "bash"
        args = [
          "-c",
          "pip install --quiet --no-cache-dir 'psycopg[binary,pool]' && python /local/pool_test.py",
        ]
      }

      resources {
        cpu    = 200
        memory = 256
      }
    }
  }
}
