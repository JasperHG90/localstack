eval: F8-foundation-deployer-provider-cutover

Definition of Done: Both Terraform roots init/plan/apply cleanly using only Vault-brokered tokens, with no static god-mode token remaining in the repo.

| Behavior | Input | Expected | Scorer | Threshold |
|----------|-------|----------|--------|-----------|
| Dry proof: `init` reaches Consul state with a brokered backend token | With the operator's F7 Vault session active, `terraform init` on both roots using a brokered backend token (not `${CONSUL_TOKEN}`) | Init succeeds on both roots; state is reachable | Deterministic check | 100% |
| Dry proof: `plan` succeeds on both roots via the brokered provider tokens | `terraform plan` on `deployments/infrastructure` and `deployments/applications` | Exit 0 on each; no auth error; no perpetual diff introduced by the rewrite | Deterministic check | 100% |
| Live reconcile: the infrastructure root applies cleanly | `just apply` on `deployments/infrastructure` via the brokered path only | Exit 0; no unexpected diff; no auth error | Deterministic check | 100% |
| Live reconcile: the applications root applies cleanly | `just apply` on `deployments/applications` via the brokered path only | Exit 0; clean reconcile (this root's full-apply duration bounds the required lease TTL) | Deterministic check | 100% |
| Guardrail: no static privileged token remains in the repo | `git grep -nE 'NOMAD_TOKEN\|CONSUL_HTTP_TOKEN\|CONSUL_TOKEN\|VAULT_TOKEN'` over tracked files | Only intended references (address/comment lines); `.env.example` and both justfiles no longer bind these to a static value | Deterministic check | 100% |
| Guardrail: Vault is the only directly-authenticated provider | Grep both `providers.tf` files | `nomad` and `consul` provider `token` fields are sourced from Vault reads; `provider "vault"` remains `{}` | Deterministic check | 100% |
| The loop gate is green | `just pre_commit` | Exit 0 (terraform fmt + offline validate + secret scan pass) | Deterministic check | 100% |
