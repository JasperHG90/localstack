eval: F6-foundation-vault-consul-secrets-engine

Definition of Done: Vault's Consul secrets engine mints a short-lived, least-privilege Consul ACL token (state-KV write under `terraform/` plus service reads only), replacing the deployer's static Consul bootstrap token.

| Behavior | Input | Expected | Scorer | Threshold |
|----------|-------|----------|--------|-----------|
| The Consul secrets engine is mounted in Vault | `vault secrets list -format=json \| jq -e '."consul/"'` | Exit 0; the returned object has `"type": "consul"` | Deterministic check | 100% |
| The engine access is configured | `vault read consul/config/access` | Exit 0; shows the configured Consul `address` and scheme | Deterministic check | 100% |
| The `deploy` role exists with a bounded TTL | `vault read -format=json consul/roles/deploy` | Exit 0; `.data` names the attached scoped policy; `ttl`/`max_ttl` in ~1800-3600s | Deterministic check | 100% |
| Brokering yields a short-lived token | `vault read -format=json consul/creds/deploy` | Exit 0; returns `.data.token` (a Consul SecretID); `lease_duration` in ~1800-3600s, not infinite | Deterministic check | 100% |
| Positive capability: the token can write/read the Terraform state prefix | With the brokered token: `consul kv put terraform/_f6probe ok && consul kv get terraform/_f6probe` (then `consul kv delete terraform/_f6probe`) | Exit 0; prints `ok`, proving the token satisfies the state backend | Deterministic check | 100% |
| Positive capability: the token resolves the deployer's service reads | With the brokered token: `consul catalog service minio` and `consul catalog service postgres-db` | Exit 0; each returns the service's node(s) | Deterministic check | 100% |
| Guardrail: out-of-scope write and ACL management are denied | With the brokered token: `consul kv put not-terraform/_f6probe nope`; `consul acl token list` | Each returns permission denied / HTTP 403, proving the token lacks the bootstrap token's global-write/management power | Deterministic check | 100% |
