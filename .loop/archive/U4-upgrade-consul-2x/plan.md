---
epic = "upgrade"
depends_on = ["U1-upgrade-pin-hashistack-versions", "U2-upgrade-vault-2x"]
priority = 46
summary = "Move Consul from 1.22.6 to 2.0.2 on the single server and all four clients. Consul holds Vault's storage and both Terraform states, so the deliverable is a pinned version plus a snapshot-first operator runbook with a rehearsed restore, not an apply the loop can run."
tags = ["consul", "upgrade", "bootstrap", "storage", "terraform"]
---

# U4 — Upgrade Consul 1.22.6 to 2.0.2

## Title
Move the cluster's Consul from 1.22.6 to 2.0.2 on the one server and the four
clients, behind a snapshot whose restore has been proven first. Consul stores
Vault's entire barrier and both Terraform states, so the upgrade's real
product is the runbook and the rollback, not the version bump.

## Size / Effort
**Large.** The code diff is small (a pinned version, a snapshot script, a
runbook). The size is in proving the restore path before touching anything,
establishing what Vault does while its storage restarts, and running a
staged, verified change against live infrastructure the loop cannot apply.

## Triggered by
Operator upgrade sweep, 2026-07-30. Consul 1.22.x reaches planned end of
support 2026-10-31 (Consul 2.0.x release notes, "Version number update"
table), and the CE 1.22 line has shipped no OSS patch since 1.22.7
(2026-04-25) while 2.0.0, 2.0.1 and 2.0.2 shipped; only `+ent` builds of
1.22.8 to 1.22.10 exist. Staying put means an unpatched Consul.

## Context (today's state)

**Verified live on 2026-07-30/31 from this devcontainer** (`GET
http://192.168.2.30:8500/v1/agent/self` and SSH to each node with
`.ssh/id_rsa`). Re-verify before implementing; live numbers drift.

- **Version and topology.** `Config.Version` is `1.22.6`, revision
  `97566680`. `GET /v1/agent/members` returns 5 alive members, all
  `1.22.6:97566680`: `firebat` (role `consul`), plus `orange_pi_4a`,
  `jetson_nano`, `raspberry_pi_4b`, `radxa` (role `node`).
  `GET /v1/status/peers` returns exactly `["192.168.2.30:8300"]`.
- **One server, so there is no rolling upgrade.**
  `bootstrap/roles/consul_server/templates/consul.hcl.j2:16-17` sets
  `server = true` and `bootstrap_expect = 1`. The server restart is a hard
  Consul outage for its duration, not a leader handover.
  `bootstrap/inventory/cluster.ini:1-16` defines `[manager]` firebat
  192.168.2.30 and four `[worker]` hosts.
- **Vault's storage is this Consul.**
  `bootstrap/roles/vault_server/templates/vault.hcl.j2:11-15` is
  `storage "consul"` at `127.0.0.1:8500`, path `vault/`. Live
  `vault status` on firebat: Vault **1.21.4**, `Storage Type consul`,
  `Seal Type shamir`, `Total Shares 5`, `Threshold 3`, `HA Enabled true`,
  `HA Mode active`, `Sealed false`. `consul kv get -recurse -keys vault/`
  returns **272 keys**.
- **Vault restarts into a sealed state.** `systemctl cat vault` on firebat:
  `Restart=on-failure`, `RestartSec=5`, and no `After=consul.service`. If
  the Vault process exits while Consul is down, systemd brings it back
  sealed and it needs `just unseal_vault` (`justfile:22-23`,
  `scripts/unseal_vault.sh:6-13`), which needs three unseal keys from the
  operator's environment.
- **Both Terraform states live in Consul KV.**
  `deployments/infrastructure/backend.tf:1-3` and
  `deployments/applications/backend.tf:1-3` are `backend "consul" {}`,
  configured by `deployments/infrastructure/vars/backend-config.hcl:1-3`
  (`path = "terraform/infrastructure"`) and
  `deployments/applications/vars/backend-config.hcl:1-3`
  (`path = "terraform/applications"`). Live
  `consul kv get -recurse -keys terraform/` returns exactly those two keys.
  `just init` in either root passes `CONSUL_HTTP_TOKEN`
  (`deployments/infrastructure/justfile:7-9`,
  `deployments/applications/justfile:9-11`).
- **25 services, 39 registrations, spread across all five nodes.**
  `GET /v1/catalog/services` returns 25 names. Per-node counts from
  `GET /v1/catalog/node/<n>`: firebat 12, radxa 9, orange_pi_4a 7,
  raspberry_pi_4b 7, jetson_nano 4. All but `consul` and
  `vault:192.168.2.30:8200` are `_nomad-*` registrations made by the local
  Nomad agent.
- **Nomad clients register against a local Consul agent.**
  `bootstrap/roles/nomad_client/templates/nomad.hcl.j2:17-20` points at
  `127.0.0.1:8500`; the server at
  `bootstrap/roles/nomad_server/templates/nomad.hcl.j2:32-35` points at
  `192.168.2.30:8500`. Nomad's own state is its own raft
  (`nomad.hcl.j2:7` `data_dir = /opt/nomad/data`), not Consul.
- **Terraform reads the catalog at plan time.**
  `deployments/applications/services.tf:1-9` declares
  `data "consul_service" "minio"` and `"postgres"`; consumed at
  `deployments/applications/providers.tf:45,51` to configure the minio and
  postgresql providers, and at `services.tf:110,166,167,202,290,291`.
  Provider address is hardcoded at `providers.tf:38-42`.
- **Consul is routed at the edge and scraped.**
  `deployments/infrastructure/services/haproxy.hcl:102,113,139-140`
  (`consul.lab.orangecluster.nl` to `192.168.2.30:8500`);
  `deployments/infrastructure/services/prometheus.hcl:87-92` scrapes
  `/v1/agent/metrics` at `192.168.2.30:8500`, wired from
  `deployments/infrastructure/services.tf:338`.
- **Install is unpinned apt from the HashiCorp repo.**
  `bootstrap/playbooks/install_dependencies.yml:94-104` installs `consul`,
  `vault`, `nomad`, `nomad-driver-podman` with `state: present`, no version.
  Repo line at `:88-92`. U1 introduces the pin; this ticket moves it.
- **The install playbook is not a safe way to move one package.**
  `install_dependencies.yml:8-13` runs `apt upgrade dist` on **all** hosts
  and notifies the `Reboot_server` handler at `:34-38`. Running it to pick
  up a Consul pin dist-upgrades and possibly reboots every node.
- **The deb postinst does not restart Consul.** Verified on firebat:
  `/var/lib/dpkg/info/consul.postinst` only does `mkdir -p /opt/consul`,
  `chown -R consul:consul /opt/consul /etc/consul.d`, and
  `systemctl daemon-reload`. So `apt install consul=<v>` swaps the binary
  and leaves 1.22.6 running until an explicit `systemctl restart consul`.
  Install and restart are separate, operator-controlled steps.
- **apt candidate availability differs per node** (verified over SSH):
  firebat noble/amd64 candidate `2.0.2-1`; raspberry_pi_4b noble/arm64
  `2.0.2-1`; jetson_nano jammy/arm64 `2.0.2-1`; radxa noble/arm64 and
  orange_pi_4a jammy/arm64 still show candidate `1.22.6-1` from a stale
  local apt cache (their `sources.list.d/hashicorp.list` is correct). An
  `apt update` on those two is a prerequisite, not a repo gap.
- **Snapshot state today: none.** Repo-wide grep for `consul snapshot` /
  `snapshot save` / `snapshot agent` returns nothing. `backup-minio.hcl` and
  `backup-postgres.hcl` exist under `deployments/infrastructure/services/`;
  there is no Consul equivalent. Vault's barrier and both Terraform states
  currently have **no backup at all**.
- **Sizing for the snapshot.** firebat `/var/lib/consul` is 66M; `/` has 75G
  free.
- **The ACL default-token finding, reproduced.**
  `consul.hcl.j2:27` is `default_policy = "deny"`, but `:29-32` sets
  `tokens.default` to the agent token, and
  `bootstrap/roles/consul_server/files/agent_policy.hcl:1-12` grants
  `service_prefix ""` and `node_prefix ""` write. So a tokenless
  `GET /v1/catalog/services` returns all 25 services (re-verified). A
  Vault-brokered `consul/creds/deploy` token returns 2, because
  `bootstrap/playbooks/enable_consul_secrets.yml:39-58` grants read on
  exactly `minio` and `postgres-db`. ACL filtering is silent, with no error.
  The same policy has no `operator` rule, which is why
  `consul operator raft list-peers` returns 403 with the default token;
  operator and snapshot commands need `/opt/consul/bootstrap_token`
  (created at `bootstrap/roles/consul_server/tasks/main.yml:61-99`, and now
  owned `consul:consul` mode 0600 because the postinst chowns `/opt/consul`).
- **No config drift on the manager.** Rendering
  `consul.hcl.j2` with the live values diffs clean against
  `/etc/consul.d/consul.hcl`.

**Upstream facts, verified 2026-07-31, re-verify before implementing:**

- Latest CE release is **2.0.2** (2026-07-08), preceded by 2.0.1
  (2026-06-19) and 2.0.0 (2026-05-24), from
  `https://api.releases.hashicorp.com/v1/releases/consul?license_class=oss`.
- **2.0.0 is a versioning-model change, not a rearchitecture.** The
  release notes for v2.0.x open with "Version number update": semantic
  versioning becomes IBM's Version-Modification-Fix model. Support table:
  2.0.x planned end of support 2028-04-30, **1.22.x 2026-10-31**.
- **No 2.0-specific upgrade notes exist.**
  `https://developer.hashicorp.com/consul/docs/upgrade/version-specific`
  rendered for v2.0.x has no 2.0 section; its newest entry is 1.21.x.
- **No BREAKING CHANGES section** in the 2.0.0, 2.0.1 or 2.0.2 changelogs
  (`raw.githubusercontent.com/hashicorp/consul/v2.0.x/CHANGELOG.md`); the
  sections present are SECURITY, FEATURES, IMPROVEMENTS, BUG FIXES. Nothing
  under ACL, KV, catalog, snapshot or raft semantics. Notable non-Enterprise
  items: Go 1.26, Envoy 1.37.2+, and HTTP server timeouts raised
  (`read_timeout`/`write_timeout` 30s to 15m).
- **The jump is allowed directly.**
  `https://developer.hashicorp.com/consul/docs/upgrade/instructions` says an
  upgrade should "jump at most 2 major versions"; 1.22 to 2.0 is one release
  line. No dedicated-instructions row applies (they stop at 1.10.x).
- **Gossip protocol is unchanged.** Live `consul -v` on firebat: "Protocol 2
  spoken by default, understands 2 to 3". The compatibility promise page
  keeps every release >= 0.7 at protocols 2 and 3, so mixed-version agents
  during the rollout are supported and clients may lag the server.
- **Raft protocol is 3** (`DebugConfig.RaftProtocol` live). Nothing in the
  2.0.x changelogs changes it.
- **Snapshots restore only into their own version.**
  `https://developer.hashicorp.com/consul/commands/snapshot/restore`: "It
  restores your configuration into a fresh cluster of Consul servers as long
  as your new cluster runs the same Consul version as the cluster that
  originally took the snapshot." Both `save` and `restore` require a
  **management** ACL token.
- **Snapshot-first is the documented procedure.**
  `https://developer.hashicorp.com/consul/docs/upgrade/instructions/general`,
  "Prepare for the Upgrade": `consul snapshot save backup.snap`, then
  `consul snapshot inspect backup.snap`, store it somewhere safe, and raise
  `log_level` to `debug` for the change window.
- **Vault still supports Consul storage.**
  `https://developer.hashicorp.com/vault/docs/configuration/storage/consul`
  (latest) still lists it as "HashiCorp Supported" with HA support. No
  deprecation notice. **U2's plan does not exist yet** (`.loop/plans/` has no
  `U1-*` or `U2-*` file as of writing), so whether Vault ends up on Consul
  storage or Integrated Storage is unsettled. See Q1 and Q2.

## Non-goals / out of scope
- **Not fixing the ACL default-token finding.** `tokens.default` stays as it
  is. This ticket only proves the behavior is unchanged after the upgrade.
- **Not migrating Vault off Consul storage.** That is U2's call (Q1).
- **Not upgrading Vault, Nomad, or nomad-driver-podman.** The pin this
  ticket moves is Consul's alone, even though
  `install_dependencies.yml:94-101` installs all four in one task.
- **Not adding a scheduled Consul snapshot job.** The runbook takes one-shot
  snapshots. A recurring backup alongside `backup-minio.hcl` and
  `backup-postgres.hcl` is a follow-up ticket (Q6).
- **Not changing any Consul config** beyond a temporary `log_level` bump for
  the change window: no TLS, no gossip encryption, no ACL policy edits, no
  `bootstrap_expect` change, no second server.
- **Not touching the RISC-V node.** `docs/riscv-integration.md:1-20`
  describes a planned Orange Pi RV2 needing a cross-compiled Consul; it is
  not in `bootstrap/inventory/cluster.ini` and not in the live member list.
- **Not running `just bootstrap`** (`bootstrap/justfile:40-49`) or
  `install_dependencies.yml` end to end against the cluster.
- **The loop does not apply this.** No loop iteration may SSH to a cluster
  node, restart a service, or run `apt`. The loop's deliverable is the pinned
  playbook, the snapshot script, and the runbook.

## Requirements & restrictions

1. **Snapshot before, restore proven before, snapshot after.** A snapshot
   whose restore has never been exercised is not a rollback. Required by the
   upstream procedure (upgrade/instructions/general, "Prepare for the
   Upgrade") and by the fact that nothing backs Consul up today.
2. **The pre-upgrade snapshot is a 1.22.6 artifact.** Per the `snapshot
   restore` docs, it restores only into a 1.22.6 cluster. Take a second
   snapshot on 2.0.2 immediately after the upgrade verifies, or the cluster
   spends the following weeks with a rollback-only backup.
3. **Server first, then clients, one at a time.** Upstream standard-upgrade
   ordering (`consul/docs/upgrade`, "Standard Upgrades"). With one server
   there is no follower/leader ordering to respect, but the client rollout
   must still be sequential and verified between hosts.
4. **Install and restart stay separate steps.** The postinst does not
   restart (verified above). The runbook must place `apt install` and
   `systemctl restart consul` as distinct, individually verified actions.
5. **Never run the whole install playbook to move one pin.**
   `install_dependencies.yml:8-13` plus the reboot handler at `:34-38` makes
   that a fleet dist-upgrade. Same class of constraint as
   `tmp/F9-MIGRATION.md:51-56` ("Do NOT use Ansible for this").
6. **Operator commands use the management token.**
   `/opt/consul/bootstrap_token`; the default agent token lacks
   `operator:read` (403 reproduced) and snapshot needs management.
7. **The runbook must state what Vault does during the restart**, as an
   observed fact from the rehearsal, never as an assumption (Q1).
8. **Plain language in the runbook.** `.claude/rules/plain-language.md`, and
   the doc must pass `.claude/rules/slop-scan-for-docs.md`: prose wrapped at
   80 chars, zero em dashes, no British spellings, every cited path real.
9. **Match `tmp/F9-MIGRATION.md` as the house bar** for runbooks: a "Before
   you start" section naming the two things that separate a clean apply from
   an outage, copy-pasteable blocks with expected output, verification that
   discriminates (negative controls, not just green checks), and an explicit
   Rollback section.
10. **Fix, do not skip, anything the gates surface.**
    `.claude/rules/pre-existing-issues.md`. `just pre_commit` is green today
    (verified: all hooks Passed), so any failure is this change's.
11. **Adversarial review before done.** `.claude/rules/adversarial-reviews.md`.

## Code surface

Repo changes (what the loop writes):

- `bootstrap/playbooks/install_dependencies.yml:94-104` — move the Consul pin
  to `2.0.2-1` in whatever shape U1 landed (a `consul_version` var, an
  explicit `name: consul={{ ... }}`, or an apt pin file). Change the Consul
  value only; leave vault, nomad and nomad-driver-podman untouched. If U1's
  shape puts versions in a vars block or `group_vars`, edit there and cite
  the anchor in the commit.
- `scripts/consul_snapshot.sh` (new) — take, inspect and off-node copy a
  snapshot. Reads the management token from `/opt/consul/bootstrap_token`,
  refuses to continue on an empty or zero-byte snapshot (the `test -s` guard
  pattern from `tmp/F9-MIGRATION.md:72-73`), and prints the
  `consul snapshot inspect` index. Sibling of `scripts/unseal_vault.sh`.
- `justfile` — add a `consul_snapshot` recipe next to `unseal_vault`
  (`justfile:22-23`) and an alias in the block at `justfile:3-7`, following
  the existing one-line `bash scripts/<x>.sh` form.
- `docs/upgrades/consul-1.22-to-2.0.md` (new, directory new) — the operator
  runbook. Sections: what changes, before you start, pre-flight, snapshot
  and restore rehearsal, server upgrade, client rollout, verification,
  rollback, afterwards. Location is Q5.
- `docs/notes/audit/plan-premise-sweep-2026-07.md` — append the live-cluster
  date once applied, matching `tmp/F9-MIGRATION.md:163-167`. Append only.

Read-only anchors the runbook and its verification cite (no edits):
`bootstrap/roles/consul_server/templates/consul.hcl.j2:16-17,24-33`,
`bootstrap/roles/consul_client/templates/consul.hcl.j2:4,15-23`,
`bootstrap/roles/consul_server/tasks/main.yml:24-31,54-59,61-99`,
`bootstrap/roles/consul_client/tasks/main.yml:40-53`,
`bootstrap/roles/consul_server/handlers/main.yml:2-5`,
`bootstrap/roles/vault_server/templates/vault.hcl.j2:11-15`,
`bootstrap/roles/nomad_server/templates/nomad.hcl.j2:32-35`,
`bootstrap/roles/nomad_client/templates/nomad.hcl.j2:17-20`,
`bootstrap/playbooks/enable_consul_secrets.yml:39-58`,
`bootstrap/playbooks/configure_network.yml:12-16,36-40`,
`bootstrap/inventory/cluster.ini:1-16`,
`deployments/infrastructure/backend.tf:1-3`,
`deployments/applications/backend.tf:1-3`,
`deployments/applications/services.tf:1-9`,
`deployments/applications/providers.tf:38-42,45,51`,
`deployments/infrastructure/services/haproxy.hcl:102,113,139-140`,
`deployments/infrastructure/services/prometheus.hcl:87-92`,
`scripts/unseal_vault.sh:6-13`.

## Tests & validation gates

No test harness exists for Ansible or HCL in this repo, and no CI gate runs
on push: `.github/workflows/` holds only `claude-ollama.yaml` and
`hermes-interactive.yaml`, both agent bots, neither running tests or lint.
Gates are the repo hook set, offline checks the loop can run, and live evals
the operator runs.

### Repo gate (loop runs)
- `just worktree_setup <path>` (`justfile:30-32`) before the first gate run
  in a worktree.
- `just pre_commit` (`justfile:18-19`, `.pre-commit-config.yaml:1-33`) — all
  Passed. The hooks that bite here: `check-yaml` (the playbook),
  `end-of-file-fixer` (the new markdown and shell files), `detect-private-key`.
  `nomad-fmt` sees no `.hcl` change; `terraform-fmt` and `terraform-validate`
  (`scripts/tf_validate.sh:8-19`) only fire on `.tf` files, and this ticket
  changes none. Baseline verified green on 2026-07-31.

### Offline checks (loop runs, no cluster access)
- `ansible-playbook --syntax-check playbooks/install_dependencies.yml` from
  `bootstrap/` (uses `bootstrap/ansible.cfg`) — exit 0. Verified working.
- `bash -n scripts/consul_snapshot.sh` — parses.
- `scripts/consul_snapshot.sh` guard test: run it with a stubbed `consul`
  on `PATH` that writes a zero-byte snapshot and assert a non-zero exit with
  a loud message. Run the negative control too (a stub that writes a
  non-empty file) so the check is known to discriminate. Both live in the
  script's own test block or a `tests/` sibling; if a new file is needed it
  must be added to §7 first.
- Runbook doc scan per `.claude/rules/slop-scan-for-docs.md`: em-dash count
  0, no ` -- ` in prose, 80-char wrap, every backticked path resolves.

### Live evals (operator runs, from the runbook)
Rehearsal, before any upgrade:
- `consul snapshot save` on firebat with the management token, then
  `consul snapshot inspect` shows a non-zero Index and Size.
- Restore that snapshot into a throwaway 1.22.6 agent (see Q4 for where) and
  assert: `consul kv get -recurse -keys vault/ | wc -l` returns 272 (or the
  count re-measured that day), `terraform/infrastructure` and
  `terraform/applications` both present, `/v1/catalog/services` returns 25.
  Negative control: the same assertions against the empty agent before the
  restore must fail.
- Controlled Consul stop on firebat for 30 seconds with `journalctl -fu
  vault` running, to record what Vault actually does (Q1). Assert afterwards:
  `vault status` shows `Sealed false`, or the runbook records the unseal it
  needed.

After the server upgrade, before touching clients:
- `consul members` shows firebat at the new build; clients still 1.22.6 and
  `alive` (the protocol promise says this is fine).
- `consul operator raft list-peers` with the management token shows one
  leader.
- `consul info` `commit_index` equals `last_log_index`.
- `vault status`: `Sealed false`, `HA Mode active`, and
  `vault kv list secret/` returns.
- `GET /v1/catalog/services` returns 25.

After the client rollout:
- All 5 members at 2.0.2, `alive`.
- Per-node registration counts match the pre-upgrade census (firebat 12,
  radxa 9, orange_pi_4a 7, raspberry_pi_4b 7, jetson_nano 4).
- `nomad job status` on a job per node shows running allocs, no task stuck on
  templates. Wait ten minutes and re-check, per `tmp/F9-MIGRATION.md:118-123`:
  a Vault template that loses access blocks and retries rather than failing.
- `terraform plan` in **both** roots with `CONSUL_HTTP_TOKEN` set produces no
  diff. This proves the state read, the state lock, and the
  `data "consul_service"` lookups at `applications/services.tf:1-9` all still
  work.
- ACL behavior unchanged: tokenless `GET /v1/catalog/services` returns 25, a
  fresh `vault read consul/creds/deploy` token returns 2.
- Edge intact: `curl -sI https://consul.lab.orangecluster.nl` and
  `curl -sI https://vault.lab.orangecluster.nl`.
- Prometheus `consul` scrape target is up.
- Post-upgrade snapshot taken and inspected (requirement 2).

### Evals
The authoritative eval set, if authored, is
`.loop/evals/U4-upgrade-consul-2x.md`. Do not author it in this ticket.

## Risk assessment

**Blast radius: the whole cluster, and the two things that cannot be rebuilt
from this repo.**

- **Vault.** 272 KV keys under `vault/` are Vault's barrier: every secret,
  policy, auth mount, JWT trust and identity on the cluster. Losing or
  corrupting them loses all of it. Nothing else holds a copy.
- **Terraform state.** `terraform/infrastructure` and
  `terraform/applications` are the only mapping between the repo and live
  infrastructure. Losing them means importing every resource by hand or
  destroying and rebuilding.
- **Both live in the same raft log**, so one bad restore takes out secrets and
  state together.
- **Every routed service.** 25 services, 39 registrations. HAProxy resolves
  `consul.lab.orangecluster.nl` at `haproxy.hcl:139-140`, and Nomad
  registrations feed the catalog Terraform reads.

**Reversibility: poor, and this is the ticket's defining constraint.**
- Consul publishes no downgrade procedure. The only documented recovery is
  restoring a snapshot into a fresh cluster **running the same version that
  took it** (`commands/snapshot/restore`). So rollback means: stop Consul,
  reinstall `consul=1.22.6-1`, clear `/var/lib/consul`, start, restore the
  pre-upgrade snapshot with the management token, then bring Vault back.
- That rollback is itself the dangerous operation the restore docs warn about
  ("a potentially dangerous low-level Raft operation"). It must be rehearsed
  before the upgrade, not discovered during one.

**Likeliest failure modes, in rough order:**
1. **The snapshot is bad and nobody notices.** No backup exists today, so the
   first snapshot ever taken here is also the one being trusted. A silent
   failure (wrong token, redirect into an empty file) reproduces exactly the
   trap `tmp/F9-MIGRATION.md:78-81` describes. Mitigation: the `test -s`
   guard, `snapshot inspect`, and the restore rehearsal.
2. **Vault does something unexpected while its storage restarts.** It may
   error requests, step down from the HA lock, or exit. If it exits, systemd
   restarts it (`Restart=on-failure`) and it comes back **sealed**, needing
   three unseal keys. Every Vault-templating Nomad job stalls until then.
   This is Q1 and must be observed, not assumed.
3. **A worker's apt cache is stale and installs nothing.** radxa and
   orange_pi_4a currently show candidate `1.22.6-1`. Without `apt update`
   the install is a silent no-op and the operator believes the node upgraded.
   Assert the installed version per node after each install.
4. **Client restart drops registrations.** A client agent restart removes its
   node's services from the catalog until it rejoins. jetson_nano carries
   memex, orange_pi_4a carries minio and phoenix, radxa carries nats,
   bifrost, hermes and mlflow. Sequential rollout with a per-node census
   between steps contains this.
5. **Someone runs the whole install playbook.** Fleet dist-upgrade plus
   reboots, during a Consul change window. Requirement 5.
6. **A Terraform apply lands mid-window** and cannot reach its state lock, or
   worse, half-writes. The runbook must declare the window and say no
   `just apply` in either root until verification passes.

## Subtickets (ordered)

1. **Snapshot capability.** `scripts/consul_snapshot.sh`, the `justfile`
   recipe, and the offline guard tests. Lands alone and is useful on its own:
   it gives the cluster its first Consul backup regardless of the upgrade.
2. **Rehearse the restore.** Operator runs the snapshot, then restores it
   into a throwaway 1.22.6 agent and asserts the three counts. No cluster
   change. Blocks everything after it: if the restore does not work, the
   upgrade does not happen.
3. **Establish Vault's behavior.** Operator stops Consul on firebat for 30
   seconds in a declared window and records what Vault does, with logs.
   Feeds the runbook's "what to expect" and its unseal step. Answers Q1.
4. **Write the runbook** to `docs/upgrades/consul-1.22-to-2.0.md`, with the
   observed Vault behavior from step 3 written in as fact.
5. **Move the pin** in `install_dependencies.yml` to `2.0.2-1` in U1's shape,
   and re-run the repo gate. Repo-only; changes nothing live until Ansible
   runs.
6. **Upgrade the server** (operator, per runbook): pre-flight, snapshot,
   `log_level` debug, `apt install`, `systemctl restart consul`, verify
   Consul, then verify Vault, then `terraform plan` in both roots.
7. **Roll the four clients** one at a time with a per-node census between
   each.
8. **Post-verification and post-upgrade snapshot**, including the ten-minute
   re-check and the ACL-unchanged assertions.
9. **Record it**: append the applied date to
   `docs/notes/audit/plan-premise-sweep-2026-07.md`, and file the follow-up
   ticket for a recurring snapshot job if Q6 lands that way.
10. **Adversarial review** per `.claude/rules/adversarial-reviews.md`.

## Open questions

- **Q1 — What does Vault do while Consul restarts?** Unknown and
  load-bearing. Vault 1.21.4 is `HA Enabled`, active, and holds a Consul
  session lock; its docs do not state the failure behavior for a storage
  outage, and `Restart=on-failure` means a crash returns it sealed.
  *Recommendation: do not answer it from documentation. Answer it with
  subticket 3*, a 30-second controlled Consul stop in a declared window with
  `journalctl -fu vault` capturing the result, and write the observed
  behavior into the runbook. Have the unseal keys in the operator's
  environment before the real upgrade either way.
- **Q2 — Is "Consul last" the right order?** It is right only if U2 changed
  something. If U2 migrates Vault to Integrated Storage, Consul stops being
  the secrets store and this ticket's risk profile collapses to "restart a
  service discovery agent", so it should be re-planned, not just re-ordered.
  If U2 only bumps Vault's version on Consul storage, the ordering buys one
  thing: a Vault the operator has just restarted and unsealed, so the
  recovery path is fresh. *Recommendation: keep `depends_on` as written, and
  re-read U2's plan before starting. If U2 moved Vault off Consul, re-plan
  this ticket rather than executing it as written.*
- **Q3 — Target 2.0.2, or wait?** 2.0.2 is the newest CE release, six weeks
  old at writing. 1.22.x loses support 2026-10-31 and its CE line has had no
  patch since 1.22.7. *Recommendation: 2.0.2.* Re-check for a newer 2.0.x on
  the day and take it; the pin is a single value. Note the devcontainer's own
  CLI is already `consul 2.0.1`, so local tooling is not the constraint.
- **Q4 — Where does the restore rehearsal run?** Options: a throwaway
  `consul agent -dev` on firebat with a separate data dir and non-default
  HTTP/serf ports; a spare worker; the devcontainer. The snapshot contains
  Vault's barrier (ciphertext, but still the whole secret store) and both
  Terraform states. *Recommendation: on firebat, in a `-dev` agent bound to
  127.0.0.1 with `-data-dir` under `/tmp`, non-default ports and no
  `retry_join`, using the 1.22.6 binary already installed there before the
  upgrade.* Do not copy the snapshot into the devcontainer or anywhere near
  the repo, and confirm the rehearsal agent cannot join the real cluster
  before restoring into it.
- **Q5 — Where does the runbook live?** `tmp/` is gitignored
  (`.gitignore:1`), so `tmp/F9-MIGRATION.md` is untracked scratch and would
  not survive. `docs/` is flat today (`credential-rotation.md`,
  `gcs-backups.md`, `tls-certificates.md`). *Recommendation: create
  `docs/upgrades/` and write `consul-1.22-to-2.0.md` there*, since U1, U2 and
  U3 each want one and a flat `docs/` will not hold four upgrade runbooks
  well. Settle this once for the epic, not per ticket.
- **Q6 — Should the snapshot become a scheduled job?** The cluster has no
  Consul backup at all, which is a standing risk this ticket only fixes for
  one afternoon. `backup-minio.hcl` and `backup-postgres.hcl` show the
  pattern, and `docs/gcs-backups.md` the destination. *Recommendation: out of
  scope here, file it as a follow-up ticket* once subticket 1 has produced a
  working snapshot script, so the job wraps something already proven.
- **Q7 — Do the clients have to move in the same window?** The protocol
  promise keeps 1.22.6 clients talking to a 2.0.2 server, so they could lag
  by days. *Recommendation: same window, sequentially.* A split-version
  cluster is an undocumented state nobody will remember in a month, and each
  client restart is low risk on its own. Take the operator's call if the
  window is tight.
- **Q8 — What if U1 has not landed the pin in a shape this ticket can move?**
  `depends_on` gates pickup on U1 being done, so it should exist. If U1's pin
  turns out to be a shared `hashistack_version` covering all four packages,
  bumping Consul alone is impossible without changing U1's structure.
  *Recommendation: if that is the shape, stop and surface it as
  `out-of-scope-fix-needed` rather than restructuring U1's work inside this
  ticket.*

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

Consul 1.22.6-1 to 2.0.2-1 on all five nodes, server first.

**The largest open question is answered, and the answer is good.** Vault
does not seal when Consul restarts under it. During the server restart, with
`journalctl -fu vault` running, Vault logged zero errors and zero seal
events, and stayed unsealed throughout. The leader came back in about 10
seconds. The plan refused to guess this, and it was right to: Vault has
`Restart=on-failure` and no `After=consul.service`, so a crash would have
returned it sealed.

The first Consul snapshot that has ever existed was taken before any of
this, then a second one after the Nomad and Vault upgrades, then a third on
2.0.2 after verification. The last one matters because `snapshot restore`
only restores into the version that took the snapshot.

Install and restart were kept separate. The deb postinst does not restart
the service, so the pause point is real and was used.

Every client refreshed its apt cache and verified the candidate was 2.0.2-1
before installing, and aborts otherwise. Without that check a stale cache
makes the install a silent no-op and the operator believes a node upgraded
when nothing changed.

Verified after: all five members alive, all 25 services present, the
`vault/` and `terraform/` prefixes intact with 274 keys under `vault/`, and
Vault unsealed on Consul storage.

The check that actually proves the Terraform states survived is a clean
plan, not the presence of the keys. Both roots return exit code 0, no
changes. An earlier run of mine crashed and reported nothing; that was a bad
invocation on my side, missing `-backend-config` and using the wrong var
file, not a real finding.

Deviation: no restore rehearsal into a scratch 1.22.6 instance. The
snapshots are verified by `consul snapshot inspect`, which is weaker than
restoring one. This is the main gap in this apply.
