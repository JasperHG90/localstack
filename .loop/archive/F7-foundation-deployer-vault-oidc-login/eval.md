eval: F7-foundation-deployer-vault-oidc-login

**Rewritten 2026-07-31** alongside the plan's replan, against the seven
required fixes in
`.loop/verdicts/F7-foundation-deployer-vault-oidc-login.plan-validator.md`.

**The row that had to go.** The previous marker's guardrail asserted that
`vault write sys/policies/acl/xyz` returning 403 proves the policy correct. It
does not. Writing `sys/policies/acl/*` is a **legitimate deployer action**:
`vault_policy.acme_tls_write` (`acme.tf:41`) and this ticket's own `deployer`
policy both need it. That row certified the broken result green, and a policy
built to satisfy it could not `terraform plan` its own root. The verdict called
this the plan's most dangerous defect.

**The scope also shrank.** The previous marker scored an "operator OIDC login".
There is no OIDC login here: the operator chose `userpass` and F2 shipped it on
2026-07-31, so the front door exists and this ticket authors only the policy
and the human read role.

**The trap.** Every row that reads the policy document is satisfiable by a
policy that does not work. Only the rows that run `terraform plan` under a real
`deployer` token, and the ones that probe capabilities from that token rather
than reading its HCL, can catch that.

| Behavior | Input | Expected | Scorer | Threshold |
|----------|-------|----------|--------|-----------|
| **A `deployer` token can plan the infrastructure root** | Obtain a token carrying only the `deployer` policy, then `terraform plan` in `deployments/infrastructure` with it | Exit 0. **This is the row that would have caught the original defect.** The old policy forbade `sys/*` and `auth/*`, which that root writes via `vault_mount.kvv2` (`secrets.tf:2`) and `vault_auth_backend.userpass` (`auth_userpass.tf:13`), so it could not plan the root it exists to deploy. No amount of reading the policy document detects this | deterministic check (`terraform plan` exits 0 under a deployer-only token) | 100% |
| **A `deployer` token can plan the applications root** | Same token, `terraform plan` in `deployments/applications` | Exit 0. A separate row because that root reads KV2 through `ephemeral` and `data` blocks rather than resources, which the prefix grant must also cover. A policy tuned only against the infrastructure root passes the row above and fails here | deterministic check (`terraform plan` exits 0) | 100% |
| **`sudo` is on `sys/auth/*` and nowhere else** | Read the rendered policy; then with a `deployer` token run `vault auth enable -path=probe-f7 userpass` and clean up | The auth mount is created, proving the `sudo` landed, AND `sudo` appears on no other path in the document. Measured 2026-07-31: enabling an auth method is refused without `sudo`; enabling a **secrets** mount is not, so `sys/mounts/*` must NOT carry it. `sudo` spread wider than one path is privilege this ticket does not need | deterministic check (auth enable succeeds; `sudo` on exactly one path) | 100% |
| **Guardrail: a real privilege escalation is denied** | With a `deployer` token: `vault token create -policy=root`, and a write to `sys/policies/acl/not-ours` | Both denied. These are genuinely out of scope, unlike the `sys/policies/acl/*` write the old marker used. **The second is the discriminating one:** it proves `sys/policies/acl/` is scoped to the policies the deployer owns rather than granted wholesale, and a `sys/policies/acl/*` wildcard fails it while passing every other row here | deterministic check (both denied) | 100% |
| **Positive control in the same family** | With the same token, write `sys/policies/acl/acme-tls-write` and `sys/policies/acl/deployer` | Both succeed. Without this, the guardrail above passes against a policy that denies the whole family, which breaks `terraform apply` on `acme.tf:41`. A denial row without its matching permission row cannot tell correctly-scoped from broken | deterministic check (both writes succeed) | 100% |
| **The KV2 prefix is a boundary, not decoration** | With a `deployer` token: read `secret/data/default/grafana/admin`, then attempt `secret/data/bootstrap/github` and `secret/metadata/otherns/thing` | The `default/` read succeeds; both others are denied. The plan grants the prefix `secret/data/default/*` rather than 22 enumerated names, because the list churns every ticket and a stale list dies halfway through an apply. This row is what stops the prefix widening to the whole mount, and it mirrors the boundary F9 established | deterministic check (`default/` allowed; `bootstrap/` and other namespaces denied) | 100% |
| **The brokered creds reads work** | With a `deployer` token: `vault read nomad/creds/deploy` and `vault read consul/creds/deploy` | Both mint. F5 and F6 are `done` and both paths are live, verified 2026-07-31, so this is exercisable now rather than deferred to a future ticket as the previous marker assumed | deterministic check (both creds paths mint under the deployer token) | 100% |
| **A human read role exists and is genuinely read-only** | Obtain a token from the new read role, then `nomad job status` and `nomad node status` (expect success), and `nomad alloc exec` plus `nomad job run` (expect denied) | Reads succeed; writes and exec are denied. This role exists because `deploy` withholds `list-jobs`, so a monitoring panel built on it shows denied in both headline widgets (`D4` Q2). A role that also permits exec has recreated `developer` under a new name | deterministic check (reads allowed; submit-job and alloc-exec denied) | 100% |
| **The read policy is authored in Ansible, not Terraform** | `grep -rn 'nomad_acl_policy' deployments/**/*.tf` and the Ansible role | The read policy is applied by Ansible, following the `developer` precedent at `bootstrap/roles/nomad_server/tasks/main.yml:182-184`. **A brokered `nomad/creds/*` token is `type: client` and cannot write Nomad ACL policies**; only a management token can. So a Terraform `nomad_acl_policy` can never be applied by the deployer it defines. That circularity is what blocked F8 | deterministic check (read policy in Ansible; not a Terraform resource) | 100% |
| **A real login carries the policy** | `vault login -method=userpass username=operator`, then `vault token lookup` | The token's policies include `deployer` and its `entity_id` is non-empty. Bind via the entity or a group it belongs to, never by hardcoding a token. F2 created that entity at `351f302a-…` with `token_policies = []`, which is why every broker call 403s today | deterministic check (login yields a deployer-carrying token with non-empty entity_id) | 100% |
| **Guardrail: the policy is not root-equivalent** | Read the rendered policy | No `path "*"`, no bare `path "sys/*"` or `path "auth/*"` wildcard, and no capability set padded to make a failing row pass. The whole point is a policy that can deploy and do nothing else, and the tempting fix for every failing row above is to widen a path | model + rubric (adversarial review agent) | 5/5 |
| **Guardrail: no secret literal in the diff** | `git diff <base>..HEAD -- '*.tf' '*.tfvars' '*.yml'` piped to a pattern match for token and password literals | No match. Do NOT score with `detect-private-key`: it matches a fixed blocklist of PEM headers and passes against a Vault token, which F2's marker records as a shipped false green | deterministic check (pattern match over the diff, expected empty) | 100% |
| **`vars/prod.tfvars` is untouched** | `git status` and the diff | Only `vars/prod.tfvars.example` changed. The real tfvars is git-ignored (`.gitignore:12`) and cannot be committed, so a diff that appears to edit it has either force-added an ignored file or written a path nobody else has | deterministic check (only the `.example` changed) | 100% |
| The repo gate passes | `just worktree_setup <path>`, then `just pre_commit` | All Passed | deterministic check (`just pre_commit` all Passed) | 100% |

signed-off-by: PENDING
