eval: F7-foundation-deployer-vault-oidc-login

Definition of Done: The deployer authenticates to Vault via operator OIDC login and carries a scoped `deployer` policy that is not root-equivalent, replacing the static Vault root token.

| Behavior | Input | Expected | Scorer | Threshold |
|----------|-------|----------|--------|-----------|
| The `deployer` policy lists exactly its scoped paths | `vault policy read deployer` | Shows the KV2 `default/*` data + metadata blocks, `nomad/creds/deploy`, `consul/creds/deploy`, `database/creds/*`; and NO `path "*"`, NO `sys/*` write, NO `identity/*`/`auth/*` write | Deterministic check | 100% |
| Positive capability: a `deployer` token reads/writes the KV2 paths it manages | With a `deployer`-scoped token: `vault kv get <mount>/default/minio/localstack` and a `vault kv put` to a `default/*` test path | Both exit 0 | Deterministic check | 100% |
| Guardrail: an out-of-scope path is denied to a `deployer` token | With the same token: `vault write sys/policies/acl/xyz policy=-` (or `vault token create -policy=root`) | HTTP 403 / permission denied, proving the policy is not root-equivalent | Deterministic check | 100% |
| Operator OIDC login yields a `deployer` (not root) token | `vault login -method=oidc` (against the resolved OIDC issuer, per Q1) | Login completes; the resulting token's `token_policies` include `deployer` and do NOT include `root` | Deterministic check | 100% |
| The loop gate is green | `just pre_commit` | Exit 0 (fmt + offline `terraform validate` + secret scan pass) | Deterministic check | 100% |
| The plan wires the policy and OIDC auth with no secret literal | `terraform -chdir=deployments/infrastructure plan` | `vault_policy.deployer` and the OIDC auth-backend/role resources are planned; no `client_secret` literal appears in the diff | Deterministic check | 100% |
