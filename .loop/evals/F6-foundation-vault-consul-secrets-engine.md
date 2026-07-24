eval: F6-foundation-vault-consul-secrets-engine

Definition of Done: Vault's Consul secrets engine mints a short-lived, least-privilege Consul ACL token (state-KV write under `terraform/` plus service reads only), replacing the deployer's static Consul bootstrap token.

| Behavior | Input | Expected | Scorer | Threshold |
|----------|-------|----------|--------|-----------|
| The Consul secrets engine is mounted in Vault | `vault secrets list -format=json \| jq -e '."consul/"'` | Exit 0; the returned object has `"type": "consul"` | Deterministic check | 100% |
| The engine access is configured | `vault read consul/config/access` | Exit 0; shows the configured Consul `address` and scheme | Deterministic check | 100% |
| The `deploy` role exists with a bounded TTL | `vault read -format=json consul/roles/deploy` | Exit 0; `.data` names the attached scoped policy; `ttl`/`max_ttl` in ~1800-3600s | Deterministic check | 100% |
| Brokering yields a short-lived token | `vault read -format=json consul/creds/deploy` | Exit 0; returns `.data.token` (a Consul SecretID); `lease_duration` in ~1800-3600s, not infinite | Deterministic check | 100% |
| Positive capability: the token can write/read the Terraform state prefix | With the brokered token: `consul kv put terraform/_f6probe ok && consul kv get terraform/_f6probe` (then `consul kv delete terraform/_f6probe`) | Exit 0; prints `ok`, proving the token satisfies the state backend | Deterministic check | 100% |
| Positive capability: the token resolves the deployer's service reads | With the brokered token: `consul catalog nodes -service=minio` and `consul catalog nodes -service=postgres-db` (equivalently `GET /v1/catalog/service/<name>`, which is what the `consul_service` data source calls) | Exit 0 / HTTP 200; each returns the service's node(s) and address | Deterministic check | 100% |
| Guardrail: out-of-scope write and ACL management are denied | With the brokered token: `consul kv put not-terraform/_f6probe nope`; `consul acl token list` | Each returns permission denied / HTTP 403, proving the token lacks the bootstrap token's global-write/management power | Deterministic check | 100% |

## Live eval run — F6 acceptance (2026-07-24, cluster 192.168.2.30)

Deployed via `ansible-playbook playbooks/enable_consul_secrets.yml` (engine
+ config/access + scoped `deploy` policy) then `terraform apply
-target=vault_consul_secret_backend_role.deploy` on the infrastructure root.
All seven behaviors pass.

1. **Engine mounted** — `vault secrets list` shows `consul/ -> {"type":"consul","accessor":"consul_f4bbdbda"}`. PASS.
2. **Access configured** — `vault read consul/config/access` → `address = 127.0.0.1:8500`, `scheme = http`. PASS.
3. **Role + bounded TTL** — `consul/roles/deploy` → `consul_policies = ["deploy"]`, `ttl = 1800`, `max_ttl = 3600`. PASS.
4. **Short-lived token** — `consul/creds/deploy` returns a `.data.token` with `lease_duration = 1800` (not infinite). PASS.
5. **Positive: state KV** — brokered token: `consul kv put terraform/_f6probe ok && consul kv get` → prints `ok`. Scratch key deleted after. PASS.
6. **Positive: service reads** — brokered token resolves both services: `consul catalog nodes -service=minio` → node `orange_pi_4a`; `-service=postgres-db` → node `firebat`; `GET /v1/catalog/service/<name>` → HTTP 200 with node addresses (the `node_prefix "" {read}` grant is required and sufficient). PASS. (The original marker command `consul catalog service <name>` is not a valid Consul subcommand — corrected above.)
7. **Guardrail: denied** — brokered token: `consul kv put not-terraform/_f6probe` → `403 Permission denied ... lacks permission 'key:write'`; `consul acl token list` → `403 Permission denied ... lacks permission 'acl:read'`. The token carries none of the bootstrap token's global-write/management power. PASS.

Known follow-up (relayed to F8, requirement 9): the `session_prefix
"terraform/"` grant is inert for Terraform state locking (Consul session
ACLs key on node name, not KV prefix); F8 must change it to `session_prefix
""` and verify a real state-locking cycle at cutover. Eval 5 above is a raw
`kv put/get` with no `-lock`, so it does not exercise that path.
