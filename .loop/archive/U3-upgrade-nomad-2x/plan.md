---
epic = "upgrade"
depends_on = ["U1-upgrade-pin-hashistack-versions", "U2-upgrade-vault-2x"]
priority = 47
tags = ["nomad", "upgrade", "bootstrap", "podman"]
summary = """
Move the cluster from Nomad CE 1.11.3 to 2.0.4 on the single server and the
four workers. 2.0.x is the CE continuation of the 1.11 line under IBM's V.M.F
naming, not a semver-major break: Enterprise 1.11.4 and CE 2.0.0 ship the same
changelog. CE 1.11.3 is the last CE build of that line and carries two
unpatched CVEs fixed in 2.0.1. The repo change is a version pin plus a
committed runbook. An operator applies it, because it restarts the only server,
which is also the client hosting the edge proxy.
"""
---

# U3 - Upgrade Nomad 1.11.3 to 2.0.4

## Title
Move Nomad from CE 1.11.3 to CE 2.0.4 on the manager and the four workers, and
pin it, so the cluster leaves an unpatched, end-of-life CE build.

## Size / Effort
**L.** The repo diff is small (one pinned version, one config block, one
runbook). The size is operational: single server, no quorum to hold the control
plane, that server also runs the edge proxy, downgrade is unsupported, and a
live pre-existing advertise-address fault means the restart this upgrade
requires already broke four of five clients once today.

## Triggered by
The `upgrade` epic sweep. Nomad on this cluster is CE 1.11.3, the last CE build
of the 1.11 line (released 2026-03-11). Everything after it in that line is
Enterprise-only, so CE 1.11.3 receives no further security patches, and Nomad
1.11.x support ends 2026-10-31.

## Context

Every fact below was re-verified against the live cluster and upstream on
2026-07-31. Re-verify before implementing, because releases move.

### Versions, as installed
`dpkg-query` on `firebat` (192.168.2.30):

| Package | Installed |
| --- | --- |
| `nomad` | `1.11.3-1` |
| `nomad-driver-podman` | `0.6.4-1` |
| `consul` | `1.22.6-1` |
| `vault` | `1.21.4-1` |

Available in `apt.releases.hashicorp.com` `noble`: `nomad` up to `2.0.4-1`,
`nomad-driver-podman` up to `0.6.5-1` (only `0.6.0-1` through `0.6.5-1` exist).

### 2.0 is not a semver-major break
The GitHub release list for `hashicorp/nomad` shows CE tags stopping at
`v1.11.3` and resuming at `v2.0.0` (2026-04-21). The Enterprise-only
`ent-changelog-1.11.4` body and the `v2.0.4` CHANGELOG entry for 2.0.0 are the
same list of changes. HashiCorp's 2.0.x release notes say versioning moved from
semver to IBM's Version-Modification-Fix model as of 2.0.0. The 2.0.0 CHANGELOG
has no BREAKING CHANGES section.

Upgrade notes for 2.0.0, from
developer.hashicorp.com/nomad/docs/upgrade/upgrade-specific:
`server.raft_boltdb` deprecated in favor of `raft_logstore`, and licensing log
and error text changed (Enterprise). Neither applies: `nomad.hcl.j2` sets
neither.

One BREAKING CHANGE in the 1.11.3 to 2.0.4 window, from 2.0.1:
"logging: The allocation logs directory is bind-mounted read-only for task
drivers that support filesystem isolation" (CVE-2026-6959). The podman driver
has filesystem isolation, so any task writing into `/alloc/logs` breaks.

### Why now: two unpatched CVEs
Both fixed in 2.0.1 (Enterprise 1.11.5), so unavailable to CE 1.11.3:
- CVE-2026-7474, dynamic host volumes, code execution outside the plugin
  directory. This cluster runs nine dynamic host volumes (`nomad volume status
  -type host`: `memex_data`, `hermes_data`, `loki_data`, `postgres`,
  `grafana_data`, `nats_data`, `acme_lego_state`, `prometheus_data`,
  `minio_data`).
- CVE-2026-6959, logging FIFO symlink swap.

2.0.x base support runs to 2028-04-30. 1.11.x ends 2026-10-31.

### The podman driver: compatible, and this is checkable
`nomad-driver-podman` is installed from the same apt repo
(`bootstrap/playbooks/install_dependencies.yml:94-104`) and this cluster uses
Podman, not Docker. `plugin_dir = "/usr/bin"`
(`bootstrap/roles/nomad_server/templates/nomad.hcl.j2:8`) and the binary is at
`/usr/bin/nomad-driver-podman`. If the driver does not load, nothing runs.

Evidence it loads under 2.0.4:
- `go.mod` at driver `v0.6.5` and at `main` both pin
  `github.com/hashicorp/nomad v1.11.3`. No driver release is built against 2.x.
- The go-plugin handshake is byte-identical between Nomad `v1.11.3` and
  `v2.0.4` `plugins/base/plugin.go`: `ProtocolVersion: 2`, same
  `MagicCookieValue`. The handshake is the categorical gate, and it passes.
- `plugins/drivers/proto/driver.proto` changed only additively between the two
  tags: RPCs `Init` and `Shutdown` and their four messages were added, none
  removed, no message removed.
- Nomad 2.0.4 tolerates drivers that do not implement them.
  `plugins/drivers/client.go:46-49` returns nil on `codes.Unimplemented` for
  `Init`; `:544-548` does the same for `Shutdown`.

This is strong, but it is inference from source, not a run. The runbook must
still check the driver fingerprint after the restart.

### Consul and Vault: no ordering constraint from Nomad
- developer.hashicorp.com/nomad/docs/networking/consul compatibility table:
  Nomad 2.0.0+ against Consul 1.22.0+ is supported. Live Consul is 1.22.6 on
  all four alive members. U4 is irrelevant to this ticket.
- developer.hashicorp.com/nomad/docs/secure/vault compatibility table: Nomad
  2.0.0+ against Vault 1.18.0+, 1.19.0+, 1.20.0+. Live Vault is 1.21.4. The
  table has no Vault 2.0 column at all. See OQ-2.

### Single server, and it is also the client running the edge
`nomad.hcl.j2:11-14` is `server { enabled = true, bootstrap_expect = 1 }` and
`:20-21` is `client { enabled = true }`. `nomad server members` reports one
member, `firebat.global`, alive, leader, build 1.11.3. `haproxy` is pinned to
that node by hostname constraint
(`deployments/infrastructure/services/haproxy.hcl:5-9`). Restarting the agent
therefore takes down the control plane and touches the agent supervising the
edge in the same action.

### The live cluster is already degraded, by exactly this restart
This is the load-bearing finding. Do not plan around the healthy-cluster
assumption.

`systemctl show nomad` on firebat: `ActiveEnterTimestamp=Fri 2026-07-31
06:44:28 UTC`. The nomad service restarted today. Host uptime is 112 days, so
only the service restarted. Since then:

- `nomad node status`: 1 of 5 nodes ready (`firebat`). `orangepi4a`,
  `radxa-dragon-q6a`, `ubuntu`, `jetson-orin-nano` are `down`. `orangepi4a`'s
  node events show `Node heartbeat missed` at `2026-07-31T06:44:54Z`, 26
  seconds after the restart, with no re-registration since.
- `nomad job status`: 19 jobs, 7 running, 12 `pending`.
- The worker agents are alive. On `orangepi4a`, `systemctl is-active nomad` is
  `active` with `ActiveEnterTimestamp=Sun 2026-04-26`, its allocations still
  render Vault templates, and its journal repeats:

```
[ERROR] client.rpc: error performing RPC to server: error="rpc error: failed
to get conn: dial tcp 10.88.0.1:4647: connect: connection refused"
rpc=Node.UpdateStatus server=10.88.0.1:4647
[INFO]  client.consul: discovered following servers: servers=[10.88.0.1:4647]
```

Cause. `nomad.hcl.j2:9` is `bind_addr = "0.0.0.0"` with no `advertise` block,
so Nomad picks its advertise address from the host's interfaces. firebat has
four: `lo 127.0.0.1/8`, `enp1s0 192.168.2.30/24`, `podman0 10.88.0.1/16`,
`tailscale0 100.117.172.3/32`. On the 06:44 restart it picked `podman0`.
`nomad agent-info` now reports `leader_addr = 10.88.0.1:4647` and
`known_servers = 10.88.0.1:4647`, while `nomad operator raft list-peers` still
holds the bootstrap-time address `192.168.2.30:4647` and cannot map it to a
live node (`Node (unknown)`, `State follower`, while `agent-info` says
`state = Leader`). Nomad registers the advertised RPC address in Consul, the
workers read it from Consul, and `10.88.0.1` on a worker is that worker's own
podman bridge, which refuses the connection.

Consequences for this ticket:
- The upgrade restarts the server. On the current config that restart re-rolls
  the same dice.
- "All 19 jobs healthy" is not a reachable post-check today. The 12 pending
  jobs are pending because their nodes are unreachable, not because the
  workloads are dead. The post-check has to be a comparison against a baseline
  captured before the upgrade, plus the client-recovery check.

### Install path
`install_dependencies.yml:94-104` installs `consul`, `vault`, `nomad`,
`nomad-driver-podman` with `state: present`, unpinned. U1 introduces the pin;
this ticket moves it.

Separately, `install_dependencies.yml:8-13` runs `apt upgrade: dist` against
`hosts: all` before any of that, and notifies a reboot handler. Any full
bootstrap run today therefore upgrades Nomad, Consul and Vault to whatever apt
offers, unplanned, and reboots the node. That is the accident this epic exists
to close, and it is why the upgrade must not be applied by running the
bootstrap pipeline.

### Config and role surface
- `bootstrap/roles/nomad_server/tasks/main.yml:121-128` templates
  `nomad.hcl.j2` to `/etc/nomad.d/nomad.hcl`, `notify: Restart nomad`;
  `:130-134` ensures the service started. The handler
  (`roles/nomad_server/handlers/main.yml:1-5`) is a plain service restart.
- `bootstrap/roles/nomad_client/tasks/main.yml:58-65` and `:67-71` do the same
  for workers.
- The role has no `tags:`, and its Vault and Consul tasks depend on facts set
  earlier in the same file (`roles/nomad_server/tasks/main.yml:16-23`,
  `:157-164`, `:189-196`), so neither `--tags` nor `--start-at-task` can
  isolate a subset. Same constraint F9 hit.
- Workers dial the server by `retry_join` at
  `roles/nomad_client/templates/nomad.hcl.j2:9-11`
  (`{{ nomad_client_server_address }}:4647`, set to `192.168.2.30` in
  `playbooks/configure_hashistack_clients.yml:11-18`) and run `server
  { enabled = false }` at `:45-47`. No worker config change is needed.
- Workload identity to Vault: `nomad.hcl.j2:37-46` enables the `vault` stanza
  with `default_identity { aud = ["vault.io"], ttl = "1h" }`. The trust is the
  `jwt-nomad` mount configured at
  `roles/nomad_server/tasks/main.yml:216-226` with
  `jwks_url="http://127.0.0.1:4646/.well-known/jwks.json"`. Live: the mount
  exists (`vault auth list` shows `jwt-nomad/`) and the JWKS endpoint serves
  one RS256 key.
- Terraform reaches Nomad through provider `hashicorp/nomad` `~>2.5.0`, locked
  at `2.5.2` (`deployments/infrastructure/providers.tf:3-6`,
  `deployments/applications/providers.tf:3-6`).

### Two jobs are not in this repository
`talat-shim` and `talat-consumer` run but have no job file under
`deployments/`. Enumerate the job list from the API, never from the repo.

## Non-goals / out of scope
- Upgrading Consul (U4) or Vault (U2). No Consul or Vault version moves here.
- Introducing the pinning mechanism. U1 owns that. This ticket only changes the
  value it holds.
- Adding a second Nomad server or otherwise fixing `bootstrap_expect = 1`.
- Fixing the four down clients as a goal in its own right. The advertise fix is
  in scope only because the upgrade cannot be verified without it (OQ-1).
- Reworking `install_dependencies.yml:8-13` (`upgrade: dist`). Flagged here,
  owned elsewhere.
- `server { oidc_issuer }`. That is F10.
- Moving `raft_boltdb` to `raft_logstore` or running
  `nomad operator raft migrate-backend`. Neither is set today and the WAL
  migration is one-way.
- Any change under `deployments/`.
- Running the upgrade. The loop produces the repo change and the runbook, and an
  operator applies it.

## Requirements & restrictions

1. The repo change must be pin-only plus config plus docs. No new Ansible task
   performs the upgrade, because `just pre_commit` cannot verify a cluster and
   the loop cannot reach one.
2. The runbook must not instruct anyone to run `just bootstrap`
   (`bootstrap/justfile:40-49`) or `configure_hashistack_server.yml`. Both drag
   in `apt upgrade: dist` (`install_dependencies.yml:8-13`) or the Consul and
   Vault roles (`playbooks/configure_hashistack_server.yml:1-44`). F9's runbook
   set this precedent and gave the reason: the role has no tags and its tasks
   are fact-coupled.
3. Server before clients. developer.hashicorp.com/nomad/docs/upgrade: "While it
   is possible to upgrade Nomad client nodes before servers, this guide
   recommends upgrading servers first as many new client features will not work
   until servers are upgraded."
4. One client at a time, and each client's restart must complete inside
   `heartbeat_grace`. Same page: "When upgrading a Nomad Client, if it takes
   longer than the heartbeat_grace (10s by default) period to restart, all
   allocations on that node may be rescheduled."
5. In-place binary replacement, not rolling replacement. Same page: "In Place:
   The Nomad binary can be updated on existing hosts. Running allocations will
   continue running uninterrupted."
6. A pre-upgrade `nomad operator snapshot save` is mandatory and must not use
   `-redact`. Under the default AEAD provider the KEK lives in Raft
   (developer.hashicorp.com/nomad/docs/manage/key-management), so a redacted
   snapshot cannot decrypt Variables or verify workload identities on restore.
   Treat the file as secret material.
7. The runbook states plainly that downgrade is unsupported. Same upgrade page:
   "Nomad does not support downgrading at this time. Downgrading clients
   requires draining allocations and removing the data directory. Downgrading
   servers safely requires re-provisioning the cluster."
8. Post-upgrade checks compare against a baseline captured before the upgrade,
   not against an assumed-healthy cluster. See the degraded state above.
9. Job enumeration comes from `nomad job status`, not from `deployments/`
   (`talat-shim`, `talat-consumer`).
10. Plain language in the runbook and every comment
    (`.claude/rules/plain-language.md`), and the doc slop scan
    (`.claude/rules/slop-scan-for-docs.md`) applies to the new markdown file.
11. Pre-existing failures found while running the gates get fixed, not skipped
    (`.claude/rules/pre-existing-issues.md`).

## Code surface

- `bootstrap/playbooks/install_dependencies.yml:94-104` - change the `nomad`
  version U1 pinned to `2.0.4-1`. Leave `consul`, `vault` untouched. Decide
  `nomad-driver-podman` per OQ-3 (recommendation: leave at `0.6.4-1`).
- `bootstrap/roles/nomad_server/templates/nomad.hcl.j2:9` - add an `advertise`
  block below `bind_addr` pinning `http`, `rpc` and `serf` to
  `{{ nomad_server_ip_address }}`, which the template already uses at `:33` and
  `:39`. Conditional on OQ-1.
- `bootstrap/roles/nomad_client/templates/nomad.hcl.j2` - no change. Listed so
  a diff touching it is a scope violation.
- `docs/nomad-2x-upgrade.md` - new. The operator runbook. `docs/` is where this
  repo keeps operator procedures (`docs/delete_nomad_dynamic_host_volume.md`,
  `docs/credential-rotation.md`). `tmp/` is gitignored (`.gitignore:1`), so the
  F9 precedent file is a house-style reference, not a location precedent.
  Style bar: `/home/vscode/workspace/tmp/F9-MIGRATION.md`. Read it, because
  `tmp/` is untracked and the file may have moved.

Nothing else. Needing another file is `out-of-scope-fix-needed`.

## Tests & validation gates

### Repo gates the loop runs
This repo has no test suite, no CI, and no ansible-lint hook. `.ansible-lint`
exists but nothing in `.pre-commit-config.yaml` invokes it. The only gate is:

```
just worktree_setup <worktree-path>   # justfile:30-32, required first
just pre_commit                       # justfile:18-19
```

`worktree_setup` is not optional in a loop worktree: `terraform-validate`
(`.pre-commit-config.yaml:28-33`) and `terraform-fmt` (`:22-27`) are
`pass_filenames: false`, so `--all-files` runs them regardless of what changed,
and they need the gitignored `.ssh` key and `prod.tfvars`.

Hooks this change can trip:
- `check-yaml --unsafe` (`.pre-commit-config.yaml:9-10`) on the
  `install_dependencies.yml` edit.
- `end-of-file-fixer` (`:13`) on the new `docs/nomad-2x-upgrade.md`.
- `nomad-fmt` (`:16-21`) will NOT run on `nomad.hcl.j2`. Its `files: '\.hcl$'`
  requires the name to end in `.hcl` and `types: [hcl]` does not match a `.j2`
  file. The template is not format-checked by any hook, so match the file's
  existing two-space indentation by hand.

### There is no automated test for this change
Say so in the ticket rather than inventing one. An Ansible pin and a markdown
runbook have no unit under test. Verification is the operator checklist below,
which the runbook must contain in full.

### Baseline, captured before any change (runbook step 0)
Write each to a file on the operator's machine:

```
nomad server members
nomad operator raft list-peers
nomad agent-info
nomad node status
nomad job status                       # the authoritative 19-job list
nomad volume status -type host
nomad node status -verbose <firebat-id> | grep -E '^driver\.|nomad\.version'
curl -s $NOMAD_ADDR/.well-known/jwks.json
curl -sI https://vault.lab.orangecluster.nl
```

Plus `nomad operator snapshot save` per requirement 6.

### After the advertise change (runbook step 1), before any version move
- `nomad agent-info`: `leader_addr` and `known_servers` both
  `192.168.2.30:4647`.
- `nomad operator raft list-peers`: `Address 192.168.2.30:4647` and a resolved
  node name, not `(unknown)`, and `State leader`.
- `nomad node status`: all five nodes `ready`. This is the check that proves
  the advertise diagnosis. If the four workers do not come back, stop and
  re-diagnose before touching versions.
- `nomad job status`: pending count drops toward the baseline's running set.

### After the server upgrade
- `nomad version` on firebat reports 2.0.4.
- `nomad server members`: `firebat.global`, alive, leader, build `2.0.4`.
- `nomad agent-info`: `state = Leader`, `applied_index` advancing.
- `nomad node status -verbose <firebat-id>`: `driver.podman` detected and
  healthy, "All Podman sockets are responding". This is the driver-compat
  check. Without it the source-level evidence above is untested.
- `nomad node status`: the other four still `ready` (a 1.11.3 client against a
  2.0.4 server is inside the two-point backward-compatibility window the
  upgrade page states).
- Each job from the step-0 list: `nomad job status <job>` matches or improves
  on the baseline, no task stuck on templates.
- Edge: `curl -sI https://vault.lab.orangecluster.nl` returns the baseline
  status.
- Workload identity end to end: mint a WI JWT for a running job and exchange it
  at the `jwt-nomad` mount, confirming `token_policies` includes
  `nomad-workloads`. `curl $NOMAD_ADDR/.well-known/jwks.json` still serves a
  key. This is the check that F1, M1, R2 and R3 all depend on.
- Allocation logs still work under the 2.0.1 read-only `/alloc/logs` bind
  mount: `nomad alloc logs <alloc>` for the haproxy and promtail allocations.
- Terraform still plans: in `deployments/infrastructure`, `just init` then
  `terraform plan` with the prod tfvars shows no unexpected diff. Provider
  `hashicorp/nomad` 2.5.2 against a 2.0.4 API is untested here.
- Wait 30 minutes and re-run the job sweep. A Vault template that loses access
  blocks and retries rather than failing fast, so an immediate pass proves
  little. Same trap F9 documented.

### After each client upgrade
Per node, before moving to the next: `nomad node status` shows it `ready` with
`nomad.version = 2.0.4`, its `driver.podman` healthy, and its allocations
running.

### Rollback
- Server: reinstall `nomad=1.11.3-1`, stop the agent, move
  `/opt/nomad/data/server` aside, `nomad operator snapshot restore` the step-0
  snapshot, start. This is a re-provision rather than a downgrade, which is
  what the upgrade docs mean by "downgrading servers safely requires
  re-provisioning the cluster".
- Client: reinstall `nomad=1.11.3-1` after draining allocations and removing
  the client data directory, per the same page.
- Repo: revert the pin. If a rollback happens, revert the pin too, or the next
  bootstrap run silently re-applies the upgrade.

## Risk assessment

**Blast radius: the whole cluster.** One server, no quorum. It is also the
client running `haproxy`, so a failed restart takes every routed service off
the network, and the operator loses the web UI they would use to diagnose it.

**Reversibility: poor.** Downgrade is unsupported upstream. Rollback means
reinstall plus snapshot restore, and the snapshot is only as good as step 0.
Missing or redacting the snapshot loses the keyring, which loses Variables and
workload-identity verification.

Likeliest failure modes, roughly in order:

1. **Advertise address re-rolls on restart.** Already happened today. Without
   the fix it happens again and the four workers stay unreachable. Mitigated by
   subticket 1 and its explicit gate.
2. **Podman driver does not fingerprint.** Every podman task becomes
   unplaceable, which is every service on this cluster. The source evidence
   says it will load, and the fingerprint check is the proof. Recovery: pin the
   driver back and restart, or roll the server back.
3. **`/alloc/logs` read-only (2.0.1 breaking change).** A task writing there
   crash-loops. Affects the podman driver specifically. Check haproxy and
   promtail logs first.
4. **`apt` upgrades more than Nomad.** The install play's `upgrade: dist`
   (`install_dependencies.yml:8-13`) and its reboot handler are one careless
   `just bootstrap` away. The runbook must use a targeted
   `apt install nomad=2.0.4-1` and say why.
5. **The driver binary and the agent move in the same apt transaction.** Both
   land in `/usr/bin` and the deb postinst restarts nomad. Ordering is apt's,
   not the operator's. Argument for holding the driver pin (OQ-3).
6. **Restart exceeds `heartbeat_grace`** on a client and its allocations get
   rescheduled onto a cluster with nowhere to put them. The 06:44 restart took
   8 seconds on firebat, and the ARM workers may be slower.
7. **Terraform provider 2.5.2 breaks against the 2.0.4 API.** Lower severity:
   it blocks deploys, not running workloads. Caught by the `terraform plan`
   check.
8. **F10's version-specific verification goes stale.** Checked: it does not.
   See OQ-7.

## Subtickets

Ordered. Items 1 to 3 are repo changes the loop can make. Items 4 to 6 are
operator actions the runbook describes and the loop must not attempt. If
these become separate plan files, encode the order in each file's
`depends_on`.

1. **Pin the advertise address.** Add the `advertise` block to
   `nomad.hcl.j2:9`. Repo change only. Gate: `just pre_commit`. Conditional on
   OQ-1. If OQ-1 resolves to "separate ticket", this becomes that ticket and
   this one depends on it.
2. **Move the version pin.** `install_dependencies.yml:94-104`, `nomad` to
   `2.0.4-1`. Gate: `just pre_commit`.
3. **Write `docs/nomad-2x-upgrade.md`.** Baseline capture, snapshot, the
   advertise apply and its gate, the server upgrade, the per-client loop, every
   check above, and the rollback. Style bar: `tmp/F9-MIGRATION.md`. Gate:
   `just pre_commit` plus the doc slop scan.
4. **Operator: apply the advertise change and confirm all five clients ready.**
   Hard gate. Do not proceed while any client is down.
5. **Operator: upgrade the server, verify, wait 30 minutes, verify again.**
6. **Operator: upgrade the four clients one at a time, verifying each.**

Follow-ups, not this ticket: move `nomad-driver-podman` to `0.6.5-1` (OQ-3);
refresh F10's source citations (OQ-7).

## Open questions

**OQ-1. Does the advertise-address fix belong in this ticket?**
The upgrade's own acceptance criterion ("every client node ready") is
unreachable while the server advertises `10.88.0.1`, and the upgrade's required
restart is the very event that triggers the fault.
*Recommendation: fold it in as subticket 1, applied and verified in the same
maintenance window but before the version moves, so a failure is attributable
to one change.* Alternative: a separate ticket this one lists in `depends_on`,
which is cleaner on paper and costs a second control-plane restart.

**OQ-2. Should U3 really depend on U2?**
The stated reason is that Nomad consumes Vault, so the provider upgrades first.
The evidence points the other way. Nomad's own compatibility table lists Vault
1.18.0+ through 1.20.0+ and has no Vault 2.0 column, so no Nomad version is
documented against Vault 2.x. Nomad 2.0.4 with the live Vault 1.21.4 sits
inside the documented range. Nomad 1.11.3 with a 2.x Vault does not, and 1.11.3
is the build with no remaining CE patches.
*Recommendation: flip the order. Do U3 first, then U2, and drop
`U2-upgrade-vault-2x` from this ticket's `depends_on`.* Keep the U1 dependency;
the pin has to exist before it can move. Editing the front-matter re-syncs the
ledger on the next session, so this is a plan edit, not a ledger edit. Operator
call, because it re-plans a sibling ticket.

**OQ-3. Move the `nomad-driver-podman` pin in the same step?**
Installed is `0.6.4-1`; latest is `0.6.5-1`. Both build against Nomad 1.11.3,
so neither is "the 2.x-compatible one" and 0.6.5 buys no compatibility.
*Recommendation: hold the driver at `0.6.4-1` through this upgrade. One
variable at a time, and it keeps the driver binary out of the same apt
transaction as the agent (risk 5). Bump to `0.6.5-1` in a separate follow-up
once 2.0.4 is proven.*

**OQ-4. Where does the runbook live?**
*Recommendation: `docs/nomad-2x-upgrade.md`, tracked.* `docs/` already holds
operator procedures and U4 will copy the pattern. F9's runbook sat in `tmp/`,
which `.gitignore:1` excludes, so it was never committed. Alternative: keep it
untracked in `tmp/` per that precedent, at the cost of losing it.

**OQ-5. What shape did U1's pin take?**
U1 does not exist yet, so this ticket cannot cite the variable it edits. It
assumes U1 turns `install_dependencies.yml:94-104` into per-package version
pins.
*Recommendation: the implementer reads U1's landed diff first and edits
whatever it introduced. If U1 pinned some other way (an apt preferences file, a
role default, a `hashistack_versions` map), that is not a blocker, but the code
surface anchor above needs updating to match.*

**OQ-6. Upgrade the four down clients, or restore them first?**
They are `down` from the control plane's view but their agents are alive and
their allocations are running.
*Recommendation: restore them first (subticket 4), then upgrade. Upgrading a
disconnected client means restarting an agent whose allocations the server has
already written off, which risks losing running work with no scheduler able to
replace it.*

**OQ-7. How do U3 and F10 sequence?**
F10's plan verified Nomad's `oidc_issuer` behavior against `hashicorp/nomad`
v1.11.3 source. Checked against v2.0.4 today: `nomad/structs/keyring.go:621` is
still `jwksURL, err := url.JoinPath(issuer, JWKSPath)` at the same line, and
`claims.Issuer = e.issuer` moved from `nomad/encrypter.go:339` to `:338`. The
behavior is unchanged and only one citation shifts by a line.
*Recommendation: let F10 run after U3 and relay a one-line citation refresh to
it. No re-plan is needed.* If F10 lands first, both tickets edit
`nomad.hcl.j2`'s `server` block and the second one rebases. Harmless, but
worth knowing.

**OQ-8. How does the operator install a single pinned package?**
The Ansible role cannot be run in isolation (no tags, fact-coupled tasks) and
the playbook that would run it also runs `upgrade: dist`.
*Recommendation: the runbook does `apt install nomad=2.0.4-1` on the host
directly, as F9's runbook did the equivalent for Vault policy, and states that
the repo pin is the durable source of truth so the next bootstrap run is a
no-op.* Alternative: add a tagged, Nomad-only playbook, which is real new
surface and a separate ticket.

**OQ-9. `depends_on` names two slugs that are not in the ledger.**
Neither `U1-upgrade-pin-hashistack-versions` nor `U2-upgrade-vault-2x` exists
in `.loop/ledger.json` yet. `depends_on` is a hard pickup gate, so this ticket
cannot be advanced to `implementing` until both exist and reach `done`.
*Recommendation: fine if the U-series is authored in one batch, but confirm
the two slugs match exactly before registering, since a typo reads as an
unsatisfiable dependency.* See also OQ-2 on dropping U2.

## Update, 2026-07-31 (post-incident)

Three facts changed after this plan was written. They are recorded here rather
than edited into the text above, so the original reasoning stays readable.

1. **The cluster was degraded when the upgrade epic was planned, and is not
   now.** At 06:44:17 UTC `unattended-upgrades` patched openssl and restarted
   nomad one second later. On that restart Nomad re-resolved
   `bind_addr = "0.0.0.0"` and advertised the podman bridge for RPC and Serf
   (`10.88.0.1`), so four of five clients could not reach the server. HTTP
   resolved correctly, which is why the API kept answering and nothing looked
   wrong. Twelve of nineteen jobs sat `pending`; running allocations survived.

2. **That is fixed.** Commit `c744b92` adds an explicit `advertise` block to
   both `nomad_server` and `nomad_client` templates, and the live manager was
   patched and restarted the same way. All five nodes returned `ready` and all
   19 jobs `running`. **The clients still run the old config**: they recovered
   because the server now advertises correctly, but each can still publish a
   bad address on its own restart until the template reaches it.

3. **`unattended-upgrades` can restart these services at any time.** It has
   run 44 times per `/var/log/apt/history.log`. Combined with `upgrade: dist`
   at `install_dependencies.yml:8-13`, both the version and the restart timing
   of the HashiStack are currently outside the repo's control. That is the
   standing condition this epic exists to end.

**Consequence for any post-upgrade verification in this ticket:** a healthy
cluster is now the baseline, and "all nodes ready, all jobs running" is a
meaningful assertion again. Capture the baseline immediately before the
upgrade regardless, because the gap between planning and applying is exactly
where this ticket's own premises went stale once already.

## Applied, 2026-07-31

Nomad 1.11.3-1 to 2.0.4-1 on all five nodes. Server first, then the four
clients one at a time, each verified before moving to the next.

A non-redacted snapshot was taken first and kept at mode 600. A second
snapshot was taken after the upgrade, because a 1.11.3 snapshot cannot be
restored into 2.x, which would otherwise leave the cluster holding a backup
that only works after a downgrade Nomad does not support.

Each client received the `advertise` block before its restart. That mattered
more than it looks: a restart is exactly when the old bug bit. With
`bind_addr = "0.0.0.0"` and no advertise block, Nomad published the podman
bridge `10.88.0.1` for RPC and Serf, which is what took four of five nodes
down when unattended-upgrades restarted it. Upgrading without fixing that
first would have reproduced the outage and blamed the upgrade for it.

Verified after: all five agents report `2.0.4 ready`, 19 jobs running, the
advertised addresses are 192.168.2.30 and not 10.88.0.1, and workload
identity still works (see U2, the grafana restart).

The podman driver stayed at 0.6.4-1 and loads fine under Nomad 2.0.4, which
was the risk worth watching: this cluster runs Podman, so a driver that
refused to load would mean no workload runs at all.
