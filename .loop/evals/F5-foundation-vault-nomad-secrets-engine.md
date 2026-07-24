eval: F5-foundation-vault-nomad-secrets-engine

Definition of Done: Vault's Nomad secrets engine mints a short-lived Nomad ACL token that can deploy this repo's `nomad_job` and `nomad_dynamic_host_volume` resources (via `submit-job`/`read-job` plus the namespace `host-volume-*` management capabilities), purpose-scoped so it lacks the `developer` policy's `alloc-exec`/`node`/`agent`/`operator` and other debugging capabilities (see the F5 ticket Amendment), replacing the deployer's static Nomad bootstrap token.

| Behavior | Input | Expected | Scorer | Threshold |
|----------|-------|----------|--------|-----------|
| The Nomad secrets engine is mounted in Vault | `vault secrets list -format=json \| jq -e '."nomad/"'` | Exit 0; the returned object has `"type": "nomad"` | Deterministic check | 100% |
| The engine is configured with a management token | `vault read -format=json nomad/config/access \| jq -e '.data.address'` | Exit 0; prints the Nomad address (the management token is not readable back, by design) | Deterministic check | 100% |
| The `deploy` role carries only the `deploy` policy with a bounded TTL | `vault read -format=json nomad/role/deploy` | `.data.policies` is exactly `["deploy"]`; token type is not `management`; role `ttl` <= 3600s | Deterministic check | 100% |
| Brokering mints a short-lived, renewable token | `vault read -format=json nomad/creds/deploy` | Exit 0; returns `.data.secret_id` and `.data.accessor_id`; `lease_duration` in ~1800-3600s; `lease_id` set (renewable) | Deterministic check | 100% |
| Positive capability: the minted token can submit/read jobs on `default` | `NOMAD_TOKEN=<minted> nomad job plan deployments/infrastructure/services/minio.hcl` | Plan renders; exit 0 or 1 (plan with changes), never an auth/permission error | Deterministic check | 100% |
| Positive capability: the minted token can manage the infra root's dynamic host volumes | `NOMAD_TOKEN=<minted> nomad volume status -type host` | Lists the dynamic host volumes (exit 0), not ACL-filtered to empty — so `terraform apply`/refresh of the `nomad_dynamic_host_volume` resources will not fail on read | Deterministic check | 100% |
| Guardrail: out-of-scope actions are denied to the minted token | With the minted token: `nomad alloc exec …`, `nomad node status`, `nomad operator raft list-peers` | Each returns permission denied (HTTP 403), proving the policy lacks the `developer` debugging/cluster capabilities | Deterministic check | 100% |
| Guardrail: the existing `developer` policy is untouched | `nomad acl policy info developer` (ambient management token) | The original `developer` capabilities are still listed; F5 neither edited nor removed it | Deterministic check | 100% |
