eval: U2-upgrade-vault-2x

**Definition of Done:** the repo's Vault pin moves from `1.21.4-1` to the
current 2.x, and a runbook ships that an operator can follow cold to perform
the upgrade on the single manager, including a rehearsed restore and a real
rollback path. **The loop writes the pin and the runbook. It never touches the
cluster.** The upgrade itself is the operator's, and this marker's live rows
are their close-out checks.

**Settled during planning, so the ticket stays a version bump:** Vault 2.x
still supports the Consul storage backend. Verified four ways — the v2.x docs
page marks it "HashiCorp Supported", it appears in none of the deprecation
tables, the 2.0.0 CHANGELOG carries a live bugfix against it, and the running
server reports `storage_type: consul` with `ha_enabled: true`. No storage
migration is in scope.

**The open question that can block this ticket, and row 4 is why it must be
settled empirically.** Vault 2.0.1 rejects wildcards in *rendered* identity
templates. `vault_nomad_workloads.hcl.j2:1,9` puts a literal `/*` after a
rendered template. The published example covers only a wildcard inside the
rendered value, so both readings survive the text. If the strict reading is
right, **sixteen of nineteen jobs lose their secret reads the moment Vault
restarts**, including `haproxy`, which renders the edge certificate. Settle it
on an isolated restored instance before touching the manager, not by reading
docs.

**Why the rollback rows are heavy.** Vault does not support automatic
rollback, the apt repo prunes old versions, and a full `consul snapshot
restore` would silently roll back the Terraform state too, because both roots
use `backend "consul" {}`.

| Behavior | Input | Expected | Scorer | Threshold |
| --- | --- | --- | --- | --- |
| The pin moves, and nothing else does | `git diff` over the branch | The Vault version in U1's pin mechanism becomes the current 2.x apt version string, re-verified at implementation time. `nomad`, `consul` and `nomad-driver-podman` pins are UNCHANGED — this ticket upgrades one component | deterministic check (only the Vault pin changed) | 100% |
| Every version claim in the runbook carries its source, re-checked | Read the runbook; follow each cited source | Each 2.x claim names where it came from and was re-verified at implementation time, not copied from the plan. The plan's facts were checked 2026-07-31 and a newer patch may exist by then | model + rubric (adversarial review agent) | 4/5 |
| **Restore is REHEARSED before the upgrade, not merely taken** | Read the runbook's ordering | Backup and rehearsed-restore are two separate numbered steps, the rehearsal happens on an isolated instance, and the upgrade step comes after it. A backup nobody has restored is a hope, and Vault's own upgrade doc asks for the rehearsal | deterministic check (rehearsal is its own step and precedes the upgrade) | 100% |
| **The wildcard question is answered empirically before the manager is touched** | Read the runbook; then, at apply time, the rehearsal output | The runbook contains a step that loads the real `nomad-workloads` policy into the isolated 2.x instance and proves a templated read still resolves. Its outcome gates the upgrade: if wildcards after a rendered template are rejected, the runbook says STOP and hands off to a policy rewrite rather than continuing. Sixteen of nineteen jobs ride on this | deterministic check (empirical wildcard step present and gating) | 100% |
| **The old .deb is cached before anything changes** | Read the runbook step order | `vault_1.21.4-1_<arch>.deb` is downloaded and its presence verified BEFORE the upgrade begins. Vault has no automatic rollback and the apt repo prunes old versions, so without the cached package the documented rollback is not executable at all | deterministic check (cache step precedes upgrade; presence asserted) | 100% |
| **Rollback does not use a full Consul snapshot restore** | Read the rollback section | Rollback restores Vault's data via a scoped path (a `vault/` prefix import), NOT `consul snapshot restore`. Both Terraform roots use `backend "consul" {}`, so a full restore silently rolls the Terraform state back to snapshot time along with Vault. The runbook must say why | deterministic check (scoped restore; full snapshot restore explicitly ruled out) | 100% |
| The unseal path is stated, with its real risk | Read the runbook | It states that `bootstrap/roles/vault_server/tasks/main.yml:135-161` unseals automatically from `/opt/vault/init.json`, so shards are not needed in hand, AND that this file is a single point of total compromise. It references the path and never prints a key or token value | deterministic check (auto-unseal explained; no key/token value printed) | 100% |
| **The policy is not rewritten by the upgrade** | Read the runbook's live procedure | It names exact commands and does not reach for the bootstrap playbook, whose run would re-template the `nomad-workloads` policy as a side effect. F9 is merged but unapplied, so the repo template and live Vault currently disagree by design (three blocks versus six) and an incidental re-template would apply F9 unannounced | deterministic check (no playbook invocation; explicit commands only) | 100% |
| **Post-upgrade: Vault is unsealed and its auth surface intact** *(operator, at apply)* | `vault status`; `vault auth list`; `vault policy list`; `vault list auth/jwt-nomad/role` | Unsealed. `jwt-nomad/` present with both roles (`nomad-workloads`, `acme`). Policies `nomad-workloads` and `acme-tls-write` present. Version reports 2.x | deterministic check (unsealed; mounts, roles and policies intact) | 100% |
| **Post-upgrade: a real workload renews a token** *(operator, at apply)* | Confirm a `nomad-workloads` job obtains a Vault token and renders its template | Succeeds. This is the check that catches the wildcard defect if the rehearsal missed it. **Re-check at T+10 minutes**: a Vault template that cannot authenticate blocks and retries silently rather than failing, so an immediate pass proves little | deterministic check (token obtained and template rendered, re-checked at T+10) | 100% |
| **Post-upgrade: the edge still serves TLS** *(operator, at apply)* | `curl -sI https://vault.lab.orangecluster.nl` and one other routed host | Both succeed. `haproxy` renders the edge certificate from Vault through the shared policy, so this is the check that catches the worst outcome before it becomes an outage | deterministic check (edge serving over TLS) | 100% |
| The runbook is followable cold | Read it end to end as someone who has not seen this ticket | Status line up front; a "Before you start" section whose points are the difference between a clean apply and an outage; numbered steps with copy-pasteable commands and expected outputs; explicit rollback; an "Afterwards" section. Plain language, active voice, prose wrapped at 80 | model + rubric (adversarial review agent) | 4/5 |
| The repo gate passes | `just worktree_setup <path>`, then `just pre_commit` | All Passed. No gate silenced; any pre-existing failure surfaced is fixed rather than worked around | deterministic check (`just pre_commit` all Passed) | 100% |

signed-off-by: JasperHG90 2026-07-31
