# F5 eval transcript — Vault Nomad secrets engine

Recorded against the live cluster (`VAULT_ADDR`, `NOMAD_ADDR` from
`.devcontainer/.env`). Engine config established by the Ansible
`nomad_server` role; the `deploy` role + policy by
`terraform -chdir=deployments/infrastructure apply`. All commands below
are read-only scorers except the single `vault read nomad/creds/deploy`
mint. All 7 rows pass.

## 1. Engine mounted (`type: nomad`)

```
$ vault secrets list -format=json | jq -e '."nomad/".type'
"nomad"
```

## 2. Engine configured with a management token

```
$ vault read -format=json nomad/config/access | jq -e '.data.address'
"http://127.0.0.1:4646"
```

## 3. `deploy` role carries only the `deploy` policy, client type

```
$ vault read -format=json nomad/role/deploy | jq '.data'
{ "global": false, "policies": ["deploy"], "type": "client" }
```

Lease TTL is a mount property (`nomad/config/lease`, ttl=1800 max=3600),
not a role field — the `vault_nomad_secret_role` schema has no `ttl`.

The live `deploy` Nomad ACL policy:

```
namespace "default" {
  capabilities = ["submit-job", "read-job",
    "host-volume-create", "host-volume-register",
    "host-volume-read", "host-volume-write", "host-volume-delete"]
}
```

The `host-volume-*` capabilities are namespace-level (they govern managing
dynamic host volumes), discovered empirically on Nomad v2.0.3 — a
`host_volume "*" { policy = "write" }` block does NOT grant this (its only
valid capabilities are `mount-readonly` / `mount-readwrite`, which govern a
job mounting a volume, not managing the volume resource).

## 4. Mint is short-lived and renewable

```
$ vault read -format=json nomad/creds/deploy | jq '{lease_id, lease_duration, renewable}'
{ "lease_id": "nomad/creds/deploy/…", "lease_duration": 1800, "renewable": true }
```

`.data.secret_id` and `.data.accessor_id` both present.

## 5. Positive capability — the minted token can submit/read jobs

```
$ NOMAD_TOKEN=<minted> nomad job plan <rendered minio.hcl>   # submit-job
exit 0, plan renders (no ACL error)
$ NOMAD_TOKEN=<minted> nomad job status -short minio         # read-job
exit 0
```

minio.hcl is a Terraform template (`${minio_secret}`); the single var is
rendered before `nomad job plan` so the plan exercises submit-job rather
than failing on an unresolved template var.

## 5b. Positive capability — the minted token can manage the 8 dynamic host volumes

```
$ NOMAD_TOKEN=<minted> nomad volume status -type host
Dynamic Host Volumes
ID        Name             Namespace  Plugin ID  ...  State
…         memex_data       default    mkdir           ready
…         hermes_data      …                          ready
…         loki_data / postgres / grafana_data / nats_data / prometheus_data / minio_data
```

All 8 volumes listed (exit 0), not ACL-filtered to empty — so a
`terraform apply`/refresh of the `nomad_dynamic_host_volume` resources in
the infrastructure root will not fail on read. `developer` cannot do this
(it has no namespace `host-volume-*` capabilities); only the management
token and this `deploy` policy can.

## 6. Negative capability (core proof) — out-of-scope actions denied

```
$ NOMAD_TOKEN=<minted> nomad alloc exec -task minio <alloc> /bin/sh   -> permission denied
$ NOMAD_TOKEN=<minted> nomad node status                              -> permission denied
$ NOMAD_TOKEN=<minted> nomad operator raft list-peers                 -> permission denied
```

Proves the `deploy` policy is strictly narrower than `developer`, which
would allow all three.

## 7. `developer` policy untouched

```
$ nomad acl policy info developer   # ambient management token
… still lists submit-job, read-job, list-jobs, dispatch-job, read-logs,
read-fs, alloc-exec, alloc-lifecycle, alloc-node-exec, host_volume "*"
write, node/agent/operator read — unchanged.
```
