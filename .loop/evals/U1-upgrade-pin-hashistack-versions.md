eval: U1-upgrade-pin-hashistack-versions

**Definition of Done:** the four HashiStack package versions (`vault`,
`nomad`, `consul`, `nomad-driver-podman`) are declared once in the repo and
enforced on every node, pinned to **what is installed today**. It upgrades
nothing. A correct implementation changes zero bytes on any node and restarts
no service for a version reason.

**Why this ticket exists.** The install task at
`bootstrap/playbooks/install_dependencies.yml:94-104` installs all four with
`state: present` and no version pin, which means
install-if-absent and never upgrade. Every host froze at whatever was current
when it was first provisioned. Verified live: all reachable nodes sit at
`consul 1.22.6-1`, `vault 1.21.4-1`, `nomad 1.11.3-1`,
`nomad-driver-podman 0.6.4-1`, while apt's candidates on firebat are `2.0.3-1`,
`2.0.4-1`, `2.0.2-1` and `0.6.5-1`. No apt holds exist and there is no
HashiCorp entry in `/etc/apt/preferences.d/`.

**The finding that makes this urgent and shapes row 3.** The same playbook
runs `upgrade: dist` at `:8-13` with a reboot handler, on all hosts, **before**
it ever reaches the install task. With the HashiCorp repo present, the next
`just bootstrap` would major-upgrade all three services and reboot. A pin
written only into the install task does not survive that.

**The trap.** Success here looks like "nothing happened", so a weak marker
passes by doing nothing at all. Rows 3, 4 and 5 are the ones that can fail.

| Behavior | Input | Expected | Scorer | Threshold |
| --- | --- | --- | --- | --- |
| The versions are declared once | `grep -rn` each of the four version strings across `bootstrap/` | Each appears in exactly ONE place, referenced from there. No version string appears twice. Two copies is how a pin and its consumer drift apart | deterministic check (each version string appears once) | 100% |
| **The pins equal what is actually installed, read on the day** | On every node in `bootstrap/inventory/cluster.ini`: `dpkg-query -W -f='${Version}' vault nomad consul nomad-driver-podman`; compare to the declared values | Exact match, node by node. The values must be re-read at implementation time, not copied from the plan: if a node has drifted since, pinning to the plan's table silently schedules an upgrade or a downgrade | deterministic check (declared == installed, per node) | 100% |
| **The pin survives `upgrade: dist`** | On a node, after applying the change: `sudo apt-get -s dist-upgrade` | None of `vault`, `nomad`, `consul`, `nomad-driver-podman` appears in the simulated upgrade list. This is requirement 3 and the whole point: a pin that only guards the install task at `:94-104` is defeated by the `upgrade: dist` at `:8-13`, which runs first. **Prove it with the simulation; do not assert it from the config** | deterministic check (none of the four listed by `apt-get -s dist-upgrade`) | 100% |
| **A full bootstrap run changes nothing** | Capture `dpkg-query` versions and `systemctl show <unit> -p ExecMainStartTimestamp` for all three units on every node. Run `just bootstrap`. Re-capture | Versions identical. No unit restarted for a version reason. This is the ticket's real success condition and the one a weak eval skips because it is expensive. Note the run may legitimately restart a unit for a config-template reason; the assertion is specifically that no version changed | deterministic check (versions unchanged; no version-driven restart) | 100% |
| **A drifted node is reported, never silently downgraded** | Simulate a node whose installed version is AHEAD of the pin (a scratch container or a `--check` run against a doctored fact) | The run REPORTS the mismatch and does not quietly roll the package back. Silently downgrading Vault across a version boundary on a node that was upgraded for a reason is the worst thing this ticket could do | deterministic check (mismatch reported; no automatic downgrade) | 100% |
| The pins resolve on every suite and architecture in use | For each declared version, confirm it exists in the apt index for `noble` amd64, `noble` arm64 and `jammy` arm64 | All four resolve on all three. The suite is `{{ ansible_distribution_release }}` (`:88-92`), which is `noble` on three nodes and `jammy` on `jetson_nano`, spanning amd64 and arm64. A version present on one and missing on another fails only on the node you did not test | deterministic check (all four resolve on all three index combinations) | 100% |
| `nomad-driver-podman` is pinned and recorded | Read the declaration | Pinned alongside Nomad, with its current version (`0.6.4-1` at plan time, re-verified at implementation) written down. It constrains U3: if the driver does not support Nomad 2.x, no workload runs after that upgrade | deterministic check (driver pinned; current version recorded) | 100% |
| Moving a pin later is one edit, and the procedure is written | Read the docs the ticket adds | A named procedure states which single value to change to move a version, so U2/U3/U4 become one-variable moves rather than archaeology | model + rubric (adversarial review agent) | 4/5 |
| **Guardrail: this ticket upgrades nothing** | `git diff` over the branch | No pin is set to a version other than the one currently installed. No `state: latest`. The diff introduces pinning machinery and nothing else. If any declared version differs from live, this ticket has become an unplanned upgrade | deterministic check (every declared version == currently installed) | 100% |
| Convention is followed, not invented | Read the change against `bootstrap/playbooks/configure_hashistack_server.yml:5-9,31-35,41-44` | Variables passed inline on the role invocation, matching the existing style. **No `defaults/` directory is introduced** — no role in this repo has one. No new Ansible collection: modules stay within the pinned set in `requirements.yml:3-8` or `ansible.builtin` | deterministic check (inline vars; no defaults/ dir; no new collection) | 100% |
| The unreadable node is resolved or recorded | Check `orange_pi_4a` (192.168.2.29) | Its installed versions are read and pinned like the rest, OR the ticket records explicitly that its SSH host key changed and the node is unverified, so nobody assumes coverage it does not have. It refused SSH during planning | deterministic check (node read, or its exclusion explicitly recorded) | 100% |
| The repo gate passes | `just worktree_setup <path>`, then `just pre_commit` | All Passed. This change is YAML, so `check-yaml` and `end-of-file-fixer` are what bite | deterministic check (`just pre_commit` all Passed) | 100% |

signed-off-by: PENDING
