eval: U3-upgrade-nomad-2x

**Definition of Done:** the repo's Nomad pin moves from `1.11.3-1` to the
current 2.x, and a runbook ships that an operator can follow cold to upgrade
the single server and then the clients, in place, with a mandatory pre-upgrade
snapshot and an honest statement that downgrade is unsupported. **The loop
writes the pin, any config, and the runbook. It never touches the cluster.**

**Two things changed after this plan was written; the marker reflects them.**
First, the plan observed the cluster degraded — four of five clients `down`,
twelve jobs `pending` — and made the missing `advertise` block a prerequisite.
That was fixed outside the loop on 2026-07-31 (commit `c744b92`): both
templates now pin advertise addresses, and the live manager was patched and
restarted, after which all five nodes returned `ready` and all 19 jobs
`running`. So the plan's degraded-state text is stale, and the healthy cluster
is the baseline. **The clients still run the old config**, so their template
fix lands with whatever run applies it.

Second, the plan's own OQ-2 argues the given `depends_on` is backwards: Nomad's
compatibility table covers Vault 1.18.0+ through 1.20.0+ with no Vault 2.0
column, so Nomad 2.0.4 against the live Vault 1.21.4 is documented-supported
while nothing involving Vault 2.x is. **This marker does not settle that
ordering** — it is an operator decision. It scores the upgrade whichever order
runs.

| Behavior | Input | Expected | Scorer | Threshold |
| --- | --- | --- | --- | --- |
| The change is pin, config and docs only | `git diff` over the branch | No new Ansible task performs the upgrade. `just pre_commit` cannot verify a cluster and the loop cannot reach one, so an automated upgrade task would be unverifiable by construction. `vault`, `consul` and `nomad-driver-podman` pins unchanged except where the driver must move in lockstep | deterministic check (pin/config/docs only; no upgrade task) | 100% |
| **The runbook never sends anyone through `just bootstrap`** | `grep -n "just bootstrap\|configure_hashistack_server" <runbook>` | No match, and the runbook says why: `install_dependencies.yml:8-13` runs `apt upgrade: dist` with a reboot handler across all hosts before anything else, and the server playbook also runs the Consul and Vault roles. Either path turns a scoped Nomad upgrade into an unplanned three-service upgrade. F9's runbook set this precedent | deterministic check (no bootstrap/playbook invocation; reason stated) | 100% |
| **A non-redacted snapshot is taken first, and treated as secret** | Read the runbook step order | `nomad operator snapshot save` runs BEFORE the upgrade and does **not** use `-redact`. Under the default AEAD provider the KEK lives in Raft, so a redacted snapshot cannot decrypt Variables or verify workload identities on restore — it would look like a backup and fail when needed. The runbook states the file is secret material and says where it goes | deterministic check (snapshot step precedes upgrade; no `-redact`; handling stated) | 100% |
| **Downgrade is stated as unsupported, plainly** | Read the runbook | It says Nomad does not support downgrading: clients require draining and removing the data directory, servers require re-provisioning. This makes the snapshot the real rollback, which is why the previous row is mandatory rather than advisory | deterministic check (downgrade limitation stated with its consequence) | 100% |
| Server first, then clients one at a time | Read the runbook ordering | Server upgraded before clients, per HashiCorp's guidance that many client features do not work until servers are upgraded. Clients then go **one at a time**, each restart completing within `heartbeat_grace` (10s default) or all allocations on that node may be rescheduled. In-place binary replacement, not host replacement: running allocations continue uninterrupted | deterministic check (order and one-at-a-time constraint stated with the grace bound) | 100% |
| **A baseline is captured before the upgrade and compared after** | Read the runbook; then, at apply time, the captured baseline | Node list, job list with states, and allocation counts are captured BEFORE the upgrade and the post-checks compare against that file, not against an assumed-healthy cluster. This ticket's own plan was written against a cluster that looked broken; assuming health is how a pre-existing fault gets attributed to the upgrade, or an upgrade fault gets dismissed as pre-existing | deterministic check (baseline captured pre-upgrade and diffed post) | 100% |
| Jobs are enumerated from the API | `grep -n "deployments/" <runbook>` for job enumeration | Enumeration comes from `nomad job status`, never the repo tree. `talat-shim` and `talat-consumer` run live with no job file in this repository, so a repo-derived list under-reports by two | deterministic check (API enumeration; talat jobs covered) | 100% |
| **The podman driver is proven compatible before the upgrade, not after** | Read the runbook and the pin | The `nomad-driver-podman` version is pinned and its Nomad 2.x compatibility is stated with evidence. This cluster runs Podman, not Docker, so if the driver will not load, **no workload runs after the upgrade**. Planning found the go-plugin handshake byte-identical between v1.11.3 and v2.0.4 and `driver.proto` changed only additively — re-verify at implementation rather than inheriting it | model + rubric (adversarial review agent) | 5/5 |
| **Post-upgrade: the control plane returns and advertises correctly** *(operator, at apply)* | `nomad server members`; then the advertise line from the journal | Leader elected, and the advertised RPC and Serf addresses are `192.168.2.30`, **not** `10.88.0.1`. The advertise fix landed in the template on 2026-07-31, but a restart is exactly when the old bug bit: `unattended-upgrades` restarted Nomad and it published the podman bridge, taking four of five nodes down. This row is the regression check for that | deterministic check (leader elected; advertise on 192.168.2.30) | 100% |
| **Post-upgrade: nodes and jobs match the baseline** *(operator, at apply)* | `nomad node status`; `nomad job status`; compare to the captured baseline | All five nodes `ready`. Every job in the baseline is running, with allocation counts matching. **Re-check at T+10 minutes**: a Vault template that cannot authenticate blocks and retries silently rather than failing, so an immediate pass can hide a broken workload | deterministic check (nodes and jobs match baseline, re-checked at T+10) | 100% |
| **Post-upgrade: workload identity still works** *(operator, at apply)* | Confirm a `nomad-workloads` job obtains a Vault token through `jwt-nomad` and renders its template | Succeeds. Nomad's `vault` stanza issues every workload its identity; if the upgrade breaks JWT issuance, 16 of 19 jobs lose their secrets and `haproxy` eventually drops the edge as its certificate template fails to renew | deterministic check (token obtained and template rendered) | 100% |
| The runbook is followable cold and its prose passes the gates | Read it end to end; run the doc slop scan | Status line, "Before you start", numbered steps with copy-pasteable commands and expected output, explicit rollback, "Afterwards". Plain language, active voice, prose wrapped at 80, Layer 0 clean (every cited path and command resolves) | model + rubric (adversarial review agent) | 4/5 |
| The repo gate passes | `just worktree_setup <path>`, then `just pre_commit` | All Passed. No gate silenced; pre-existing failures fixed rather than skipped | deterministic check (`just pre_commit` all Passed) | 100% |

signed-off-by: JasperHG90 2026-07-31
