eval: U4-upgrade-consul-2x

**Definition of Done:** the repo's Consul pin moves from `1.22.6-1` to the
current 2.x, a snapshot helper and justfile recipe ship, and a runbook ships
that an operator can follow cold to upgrade the one server and then the
clients. **The loop writes the pin, the helper and the runbook. It never
touches the cluster.**

**This is the most dangerous ticket in the epic, and the reason is not the
upgrade.** Consul holds three things at once: Vault's entire storage backend
(`vault.hcl.j2:11-15`, 272 keys under `vault/`), both Terraform states
(`backend "consul" {}` in each root, two KV keys), and the service catalog
that HAProxy routing and every `data "consul_service"` lookup read. Getting
Consul wrong destroys every secret and the config-to-infrastructure mapping
simultaneously.

**And nothing backs it up today.** A repo-wide search for `consul snapshot` /
`snapshot save` / `snapshot agent` returns nothing. `backup-minio` and
`backup-postgres` cover their own data and not this. So the first snapshot
this ticket takes is the first one that has ever existed, which makes rows 2
and 3 the highest-value rows in the marker — they matter whether or not the
upgrade ever happens.

**One server, one raft peer**, so there is no rolling upgrade: the restart is
a hard Consul outage. What Vault does during that window is **unknown**, and
row 6 refuses to let it be guessed.

| Behavior | Input | Expected | Scorer | Threshold |
| --- | --- | --- | --- | --- |
| The pin moves, and nothing else does | `git diff` over the branch | Only the Consul version changes in U1's pin mechanism. `vault`, `nomad` and `nomad-driver-podman` untouched | deterministic check (only the Consul pin changed) | 100% |
| **A snapshot exists, and it is the first one ever** | Read the helper and its justfile recipe; run it | `scripts/consul_snapshot.sh` (or equivalent) takes a snapshot with the **management** token from `/opt/consul/bootstrap_token`, writes it to a stated location, and the recipe invokes it. The default agent token lacks `operator:read` (403 reproduced) and snapshot requires management, so a helper built on the default token fails exactly when needed | deterministic check (helper runs, uses management token, produces a snapshot) | 100% |
| **The restore is REHEARSED, not merely planned** | Read the runbook ordering; then the rehearsal output at apply time | Snapshot, then a proven restore into a scratch 1.22.6 instance, then the upgrade — three distinct numbered steps in that order. The snapshot carries Vault's whole barrier and both Terraform states, so an unexercised restore is a hope, not a rollback. Where the rehearsal runs is stated explicitly, because the artifact is secret material | deterministic check (rehearsal is its own step and precedes the upgrade) | 100% |
| **A second snapshot is taken after the upgrade verifies** | Read the runbook | A 2.0.2 snapshot is taken immediately after verification. `snapshot restore` only restores into the version that took the snapshot, so without this the cluster spends the following weeks holding a backup that can only be restored by first downgrading. Stating this is what makes the requirement legible rather than ritual | deterministic check (post-upgrade snapshot step present with its reason) | 100% |
| **Install and restart are separate, individually verified steps** | Read the runbook | `apt install` and `systemctl restart consul` appear as distinct actions with their own verification. The Consul deb postinst does **not** restart the service (verified in `/var/lib/dpkg/info/consul.postinst`), so this is genuinely controllable — and treating them as one step forfeits the only pause point in the whole procedure | deterministic check (install and restart separate, each verified) | 100% |
| **What Vault does during the Consul outage is OBSERVED, not assumed** | Read the runbook; then the rehearsal output | The runbook contains a controlled step that stops Consul briefly with `journalctl -fu vault` running, records what Vault actually does — seals, errors, blocks, recovers — and that observation is written into the runbook before the real upgrade. Vault has `Restart=on-failure` and no `After=consul.service`, so a crash returns it **sealed**. This is the single largest unknown in the ticket and the plan refuses to guess it | deterministic check (controlled observation step present; result recorded) | 100% |
| **The runbook never sends anyone through the install playbook** | `grep -n "just bootstrap\|install_dependencies" <runbook>` | No match, with the reason stated: `install_dependencies.yml:8-13` plus the reboot handler makes that a fleet-wide dist-upgrade. Same constraint class as F9's runbook | deterministic check (no playbook invocation; reason stated) | 100% |
| A stale apt cache cannot silently no-op the install | Read the runbook | It refreshes the apt cache per node before installing, and verifies the candidate version afterwards. `radxa` and `orange_pi_4a` were observed still offering candidate `1.22.6-1` from a stale cache, which would make the install a **silent no-op** — the operator would believe the node upgraded when nothing changed | deterministic check (cache refresh plus candidate verification per node) | 100% |
| Server first, then clients one at a time | Read the runbook ordering | Server before clients; the client rollout sequential and verified between hosts. With one server there is no leader ordering to respect, but sequencing the clients is what keeps a failure attributable to one node | deterministic check (order and one-at-a-time constraint stated) | 100% |
| **Post-upgrade: the catalog is intact** *(operator, at apply)* | `GET /v1/catalog/services` against a pre-upgrade census | All 25 services and 39 registrations return, matching the census taken before the upgrade. A census taken beforehand is required; comparing against memory is how a silent loss gets missed | deterministic check (service and registration counts match the pre-upgrade census) | 100% |
| **Post-upgrade: Vault and Terraform state both survived** *(operator, at apply)* | `vault status`; then `terraform plan` in each root | Vault unsealed and serving, with its 272 `vault/` keys intact. `terraform plan` in **both** roots produces no spurious diff, proving the state keys survived. These are the two things a Consul mistake destroys, and neither is visible from Consul's own health output | deterministic check (Vault unsealed and serving; both roots plan clean) | 100% |
| ACL filtering behaves as before | With no token and with a brokered `consul/creds/deploy` token: `GET /v1/catalog/services` | Same shape as before the upgrade: anonymous returns all 25 (because `tokens.default` is the agent token at `consul.hcl.j2:29-31`, despite `default_policy = "deny"`), the brokered token returns its filtered subset. **This ticket does not fix that**; it verifies the upgrade did not silently change it, since ACL semantics are exactly the kind of thing a major version moves | deterministic check (both responses match pre-upgrade behavior) | 100% |
| Rollback is executable, not aspirational | Read the rollback section | It states the real procedure: reinstall 1.22.6, wipe the data directory, restore the 1.22.6 snapshot — because `snapshot restore` only restores into the version that took it. Anything vaguer is not a rollback | deterministic check (rollback names version, data-dir wipe and restore) | 100% |
| The runbook is followable cold and its prose passes the gates | Read it end to end; run the doc slop scan | "Before you start" naming the two things separating a clean apply from an outage, copy-pasteable blocks with expected output, verification that discriminates (negative controls, not just green checks), explicit Rollback. Prose wrapped at 80, zero em dashes, no British spellings, every cited path real | model + rubric (adversarial review agent) | 4/5 |
| The repo gate passes | `just worktree_setup <path>`, then `just pre_commit` | All Passed. It is green today, so any failure is this change's. Nothing silenced | deterministic check (`just pre_commit` all Passed) | 100% |

signed-off-by: JasperHG90 2026-07-31
