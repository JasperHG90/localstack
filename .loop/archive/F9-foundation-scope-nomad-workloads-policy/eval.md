eval: F9-foundation-scope-nomad-workloads-policy

**Definition of Done:** the shared `nomad-workloads` Vault policy no longer
grants every workload read/create/update on `bootstrap/data/*` (the GitHub PAT
and the Tailscale auth key) nor `list` on `secret/metadata/*` cluster-wide,
the narrowed policy is live on the Vault server via the Ansible bootstrap run,
and **every job that held the policy before still renders its own Vault
templates afterwards**.

**Why the negative check is the whole ticket.** A Vault template that loses a
grant does NOT fail fast: it blocks and retries forever, so the allocation sits
`pending` and the job looks merely slow. Rows 3, 4 and 7 exist because "it did
not obviously break" is indistinguishable from "it is silently blocked" for the
first several minutes.

**The verification population is fifteen, not three.** Read live 2026-07-30 via
`nomad job inspect` over all 19 jobs: fifteen hold the default role
(`Role: ""`) — `backup-minio`, `backup-postgres`, `bifrost`, `grafana`,
`haproxy`, `hermes`, `loki`, `memex`, `minio`, `mlflow`, `phoenix`, `postgres`,
`prometheus`, `talat-consumer`, `talat-shim`. `acme` has its own role
(`Role: acme`). `nats`, `node-exporter` and `promtail` carry no `vault` block.
**`haproxy` is in the population and matters most**: it renders the edge TLS
PEM from Vault, so a blocked template there drops every routed service.
**`talat-consumer` and `talat-shim` have NO job file in this repository**, so a
population derived from `grep -rl 'vault {' deployments/` silently misses two
live holders.

**Prerequisite for row 2:** the harness `$VAULT_TOKEN` is root and bypasses
policy, so it cannot prove a denial. Every permit/deny row must use a token
minted through `jwt-nomad` for a job holding only `nomad-workloads`.

| Behavior | Input | Expected | Scorer | Threshold |
| --- | --- | --- | --- | --- |
| **The bootstrap write grant is gone** | With a WI token for an ordinary job (NOT the root harness token): `vault kv get -mount=bootstrap github` and `vault kv put -mount=bootstrap github/probe x=y` | Both denied, **403**. The write is the sharper half: the Tailscale auth key admits a device to the tailnet, and today every workload can overwrite it | deterministic check (403 on both read and write) | 100% |
| **The denial is proven with a non-root token** | `vault token lookup` on the token used in row 1 | Its `policies` contain `nomad-workloads` and NOT `root`. A 403 from a root token is impossible, so a row that passes with the harness token has proven nothing | deterministic check (token is non-root, carries nomad-workloads) | 100% |
| **Every one of the fifteen holders still renders its templates** | For all fifteen jobs named above: `nomad job status <job>` and `nomad alloc status <alloc>` | Every job has a running allocation with no template-render error and no task stuck `pending`. Explicitly includes `haproxy`, `talat-consumer` and `talat-shim`. Spot-checking three jobs is NOT sufficient: the grant being removed is cluster-wide | deterministic check (all fifteen healthy, none pending on templates) | 100% |
| **Checked late, not just immediately** | Re-run the row 3 sweep **at least 10 minutes** after the bootstrap run | Still no allocation pending on template rendering. A blocked Vault template retries silently, so an immediate check passes against a job that will never render | deterministic check (clean sweep at T+10min) | 100% |
| **haproxy still serves the edge TLS certificate** | `curl -sI https://vault.lab.orangecluster.nl` and one other routed host | HTTP 200 (or the expected redirect), served over the Let's Encrypt wildcard. haproxy reads its PEM from `secret/data/default/haproxy/tls` through the shared policy, so this is the row that catches the worst failure mode before it becomes an outage | deterministic check (edge still serving TLS) | 100% |
| **`acme` is unaffected** | `vault read auth/jwt-nomad/role/acme`; `nomad job status acme` | Its `token_policies` still carry `nomad-workloads` AND `acme-tls-write`, and the job is unchanged. `acme` is the one job with a dedicated role and the pattern any future consumer would copy; this ticket must not disturb it | deterministic check (role and job unchanged) | 100% |
| **The metadata-list decision is recorded AND matches reality** | Read the plan's requirement 4 resolution, then run `vault list secret/metadata` with the row-1 token | The plan states explicitly whether cluster-wide metadata list was narrowed, and the live behavior matches that statement. Either outcome is acceptable; a plan that is silent, or that disagrees with the cluster, is not | model + rubric (adversarial review agent) | 4/5 |
| **Guardrail: the policy file changed, and only where intended** | `git diff -- bootstrap/roles/nomad_server/templates/vault_nomad_workloads.hcl.j2` | The `bootstrap/data/*` and `bootstrap/metadata/*` blocks are removed or narrowed. The job-scoped `secret/data/{{ns}}/{{job_id}}` grants are UNTOUCHED. Removing those breaks all fifteen holders at once | deterministic check (bootstrap blocks changed, job-scoped grants intact) | 100% |
| **Guardrail: no new broad grant replaces the old one** | Read the rendered policy: `vault policy read nomad-workloads` | No path in the resulting policy is unscoped by namespace and job id, except any the plan explicitly justifies. The failure mode is narrowing one grant while widening another to keep something working | model + rubric (adversarial review agent) | 4/5 |
| The repo gate passes | `just worktree_setup <path>`, then `just pre_commit` | All Passed. The worktree step comes first or `terraform-validate` dies on the gitignored `.ssh/id_rsa` read at `services.tf:290` | deterministic check (`just pre_commit` green) | 100% |
| The rollback path is written down before the run | Read the ticket's runbook section | It states the exact command to restore the previous policy and re-run the bootstrap task, and who runs it. This change is applied by an Ansible run against a live Vault, not by the loop, and a policy narrowed wrongly blocks templates across the cluster | model + rubric (adversarial review agent) | 4/5 |

signed-off-by: jasperginn 2026-07-30
