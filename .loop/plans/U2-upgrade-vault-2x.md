---
epic = "upgrade"
depends_on = ["U1-upgrade-pin-hashistack-versions"]
priority = 48
summary = "Vault runs 1.21.4 Community, the terminal patch on that line (1.21.5-1.21.8 are Enterprise only). Move the pin to 2.0.3 and ship the runbook the operator applies by hand. Verified: Vault 2.x still supports the Consul storage backend, so this is a version bump, not a storage migration."
tags = ["vault", "upgrade", "bootstrap", "storage"]
---

# U2 - Upgrade Vault from 1.21.4 to 2.0.3

## Title
Vault runs 1.21.4 Community, which is the last Community release on the 1.21
line. Move the apt pin to 2.0.3 and ship a runbook for the hand-applied,
sealed-window upgrade on the manager.

## Size / Effort
**Large.** The repo diff is one pinned version string. The size comes from
everything around it: a proven restore rehearsal on an isolated instance, a
pre-flight audit against five 2.x breaking changes (one of which, if it
bites, revokes every workload's secret read at once), a hand-run upgrade with
a sealed outage window, and the runbook that carries all of it. The loop
cannot apply this change. It produces the pin and the runbook, nothing more.

## Triggered by
The `upgrade` epic. Vault is pinned by U1 and this ticket moves the pin.
Confirmed on 2026-07-31 that CE 1.21.4 receives no further patches.

## Context (today's state)

### Verified live, 2026-07-31
`GET http://192.168.2.30:8200/v1/sys/seal-status` and `/v1/sys/health` and
`/v1/sys/leader`, all unauthenticated:

- `"version":"1.21.4"`, `"build_date":"2026-03-04T17:40:05Z"`
- `"enterprise":false` - **Community edition**
- `"storage_type":"consul"` - the server's own report
- `"type":"shamir"`, `"t":3`, `"n":5` - 3-of-5 unseal threshold
- `"sealed":false`, `"initialized":true`
- `"ha_enabled":true`, `"is_self":true`, active since `2026-04-10T07:50:45Z`
- Single manager node, `firebat` at `192.168.2.30`
  (`bootstrap/inventory/cluster.ini:1-3`). No second Vault to roll through,
  so the restart is a full outage.
- Consul on the same node reports `1.22.6`, datacenter `localstack`
  (`GET /v1/agent/self`).

### The storage question, settled
**Vault 2.x still supports the Consul storage backend.** This ticket is a
version bump. No `vault operator migrate`, no Raft migration, no split.
Four independent sources, all checked on 2026-07-31:

1. `https://developer.hashicorp.com/vault/docs/configuration/storage/consul`
   resolves under the `v2.x (latest)` doc version and states, verbatim:
   *"**HashiCorp Supported** - the Consul storage backend is officially
   supported by HashiCorp."* Consul is also still listed in the v2.x storage
   sidebar alongside Integrated Storage (Raft).
2. `https://developer.hashicorp.com/vault/docs/updates/deprecation` (v2.x)
   lists three deprecations, four pending removal, and six removed. **No
   storage backend appears in any of the three tables.**
3. `hashicorp/vault` `CHANGELOG.md`, section `## 2.0.0`, carries a live fix
   against that code path: *"replication (enterprise): fix rare panic due to
   race when enabling a secondary with Consul storage."* The backend is
   maintained in 2.x, not vestigial.
4. The running server reports `"storage_type":"consul"` and
   `"ha_enabled":true`, so the backend is doing HA locking today.

The repo side is `bootstrap/roles/vault_server/templates/vault.hcl.j2:11-15`,
`storage "consul" { address = "127.0.0.1:8500", path = "vault/" }`, with the
Consul ACL grant in
`bootstrap/roles/vault_server/files/consul_vault_policy.hcl:1`
(`key_prefix "vault/" { policy = "write" }`).

### The upgrade path
Community releases, from the paginated
`https://api.releases.hashicorp.com/v1/releases/vault` (`license_class` is
`oss`):

| Version | Released |
| --- | --- |
| 1.21.4 | 2026-03-05 |
| 2.0.0 | 2026-04-14 |
| 2.0.1 | 2026-05-19 |
| 2.0.2 | 2026-06-04 |
| 2.0.3 | 2026-06-17 |

**1.21.5 through 1.21.8 are Enterprise only.** The CHANGELOG headers read
`## 1.21.8 Enterprise`, `## 1.21.7 Enterprise`, `## 1.21.6 Enterprise`,
`## 1.21.5  Enterprise`, and then plain `## 1.21.4`;
`https://releases.hashicorp.com/vault/1.21.5/` through `.../1.21.8/` all
return 404. The cluster is Community, so **1.21.4 is terminal and gets no
further security patches**. That is the reason to move.

**There is no intermediate Community version to step through.** The CE line
goes 1.21.4 straight to 2.0.0. Vault's upgrade doc
(`https://developer.hashicorp.com/vault/docs/upgrade`) asks you to *review*
important changes for each major between source and target, not to install
them, and it prescribes a single in-place stop, install, start, unseal.
One major boundary, one hop.

apt has the target. `https://apt.releases.hashicorp.com` carries
`vault 2.0.3-1` for `noble`, `jammy`, and `bookworm` on both `amd64` and
`arm64`. It also still carries `1.21.4-1` and `1.21.3-1` today, and nothing
older: the repo prunes, which is why the rollback binary has to be cached
before the upgrade, not fetched after it.

### What 2.x breaks that touches this cluster
From `https://developer.hashicorp.com/vault/docs/updates/important-changes`
(page states "Last updated: 2026-05-21") plus the 2.0.0 / 2.0.1 / 2.0.2
CHANGELOG sections. Only the items with a surface here:

1. **Wildcards rejected in rendered identity templates** (2.0.1+, all
   editions; CHANGELOG lists it under SECURITY as *"core/identity: reject
   wildcards in rendered identity templates"*). **This is the one that can
   take the cluster down.**
   `bootstrap/roles/nomad_server/templates/vault_nomad_workloads.hcl.j2:1-11`
   is entirely identity-templated
   (`secret/data/{{identity.entity.aliases.<accessor>.metadata.nomad_namespace}}/...`)
   and ends two of its three rules with a literal `/*`. It is the policy
   `jwt-nomad`'s `default_role` attaches, so sixteen of nineteen live jobs
   hold it (`tmp/F9-MIGRATION.md:6-9`), including `haproxy`, which renders
   the edge TLS PEM from Vault
   (`deployments/infrastructure/services/haproxy.hcl:39`,
   `acme.tf:41-49`). If this change rejects the policy, every one of those
   jobs loses its secret read at the same moment and the edge follows.
   The published example only demonstrates a *rendered metadata value*
   containing `+` (`region="amer/+/us-west"`), which Nomad namespace and job
   IDs never do. That reading says the literal trailing `/*` is safe. It is
   a reading, not a guarantee. See Open Question 2.
2. **`sys/rekey` and `sys/generate-root` now require a token** (2.0.0+, all
   editions). Old behavior returns via the new top-level config key
   `enable_unauthenticated_access` (string array; supported values `"rekey"`,
   `"generate-root"`, `"generate-operation-token"`; SIGHUP-updatable). Does
   not affect `sys/unseal`, so `scripts/unseal_vault.sh` is unaffected. It
   does mean the "lost root token" recovery path now needs a token. See Open
   Question 4.
3. **Non-canonical paths rejected** (2.0.0+, all editions): `//`, `/./`,
   `/../`, and URL-encoded equivalents. Repo grep finds no literal double
   slash in a Vault path, but every job template path is interpolated
   (`with secret "${...}"` across `deployments/*/services/*.hcl`), so the
   rendered values need a live check, not a grep.
4. **RSA modulus capped at 8192 bits** (2.0.2+, CVE-2026-39829).
   `deployments/infrastructure/services/acme.hcl` sets no lego key type, so
   the edge cert uses lego's default (EC), not a 16k RSA key. Cheap one-line
   confirmation, expected pass.
5. **Duplicate HCL attributes** (deprecated JUN 2025, end of support OCT
   2025): affected policies fail outright once support ends. Applies to
   `vault.hcl` and to every stored policy.

Two more that read as scary and are not: `max_token_header_size` (8 KB
default) bounds the `X-Vault-Token` and `Authorization: Bearer` headers only,
and Nomad's workload JWT travels in the login *body*; and the container
`IPC_LOCK` churn does not apply because Vault is an apt package on the host,
with `disable_mlock = true` already set at `vault.hcl.j2:9`.

### Backup, and the trap in it
There is no Vault or Consul backup in this repo. `docs/gcs-backups.md` covers
PostgreSQL and MinIO only.

Vault's data is Consul KV under `vault/`. `vault operator raft snapshot` does
not apply, it is Integrated Storage only. The two backup artifacts are
`consul snapshot save` (whole Consul state) and `consul kv export vault/`
(scoped).

**The trap:** both Terraform roots use `backend "consul" {}`
(`deployments/infrastructure/backend.tf:1-3`,
`deployments/applications/backend.tf:1-3`). A full `consul snapshot restore`
therefore rolls Terraform state back too, silently. The scoped
`consul kv import` of the `vault/` prefix is the surgical restore; the full
snapshot is the last resort, and its side effect has to be stated where the
operator will read it.

Vault's own upgrade doc insists any restore rehearsal happen on a **fully
isolated** instance, because a non-isolated restored Vault revokes live
third-party credentials and can strand the production cluster with
irrevocable leases.

### Unseal, and who holds the keys
Two paths exist and the brief understates the first:

- `bootstrap/roles/vault_server/tasks/main.yml:135-161` reads
  `/opt/vault/init.json` on the manager (mode `0600`, owner `vault`, written
  at `:116-123`) and unseals with `vault_init.unseal_keys_b64[:3]`. The keys
  are **on the box**, not only in an operator's env.
- `scripts/unseal_vault.sh:6-13` requires `VAULT_UNSEAL_KEY_1/2/3`,
  `VAULT_ADDR` and `VAULT_TOKEN` in the environment and exits 1 otherwise.
  Wired as `just unseal_vault` (`justfile:21-22`).

So the operator does not need shards in hand, but `/opt/vault/init.json` is a
single point of total failure, and it must be read and parsed successfully
**before** the service is stopped. That file also holds `root_token`, which
`seed_vault.yml:11-18` and `nomad_server/tasks/main.yml:189-196` both read.

### What breaks while Vault is sealed
- Nomad's `vault` stanza (`nomad_server/templates/nomad.hcl.j2:37-46`) mints
  every workload's identity token. Sealed Vault means no new tokens.
- Vault templates **do not fail fast**: they block and retry, so an
  allocation sits `pending` and the job merely looks slow
  (`tmp/F9-MIGRATION.md:120-123`). An immediate green check after unseal
  proves little, so re-check ten minutes later.
- `haproxy` keeps serving its already-rendered PEM while its allocation
  lives. A restart inside the sealed window leaves it unable to render, and
  every routed service goes down together (`haproxy.hcl:46-49`).
- Terraform state is in Consul, and Consul is untouched, so it survives.

### The F9 coupling
`bootstrap/roles/nomad_server/tasks/main.yml:257-271` re-renders
`vault_nomad_workloads.hcl.j2` and runs `vault policy write nomad-workloads`
on **every** run of `configure_hashistack_server.yml`. F9 is merged to `main`
(commit `51b9852`) but **not applied**: the repo template has three `path`
blocks, live Vault still serves six (`tmp/F9-MIGRATION.md:3-4,11-18`).

So the Ansible route to this upgrade would also apply F9 in the same run,
conflating two changes that share one failure mode: every workload losing its
secret read at once. `tmp/F9-MIGRATION.md:51-56` already records why Ansible
cannot isolate those tasks (the role has no `tags:` and the policy tasks
depend on facts set earlier in the same role).

`install_dependencies.yml` is worse as a live tool: `:8-13` runs
`apt upgrade: dist` and notifies a reboot handler (`:34-38`) across **all**
hosts before it ever reaches the Vault package at `:94-101`. Running it to
move a pin dist-upgrades and may reboot the fleet.

### F2 status
`loop/F2-foundation-vault-oidc-provider` is at `dc9046b` and is **not merged
into `main`**: `git branch --merged main` lists only `main`,
`feat/bifrost-grafana-metrics`,
`loop/F5-foundation-vault-nomad-secrets-engine` and
`plan/auth-epic-fork-resolutions`. Re-check at implementation time; see Open
Question 5 for both branches of the answer.

## Non-goals / out of scope
- **No storage migration.** Consul storage stays. Do not run
  `vault operator migrate` and do not introduce a Raft stanza.
- **No Consul or Nomad upgrade.** Consul 1.22.6 and the Nomad version stay
  put. Separate tickets in this epic.
- **Do not apply F9 as a side effect.** The `nomad-workloads` policy is out
  of scope for this ticket. If the chosen procedure would rewrite it, the
  procedure is wrong.
- **No Terraform provider bump.** `hashicorp/vault` stays pinned `~>5.3.0`,
  locked at `5.3.0` in both `.terraform.lock.hcl` files. Verify only; open a
  follow-up if 2.0.3 breaks it.
- **No TLS change.** `tls_disable = true` at `vault.hcl.j2:17-20` stays;
  haproxy still terminates.
- **No change to the seal type, unseal threshold, or key custody.** Shamir
  3-of-5 and `/opt/vault/init.json` stay as they are.
- **No new backup automation.** This ticket takes backups as a step in a
  runbook. A recurring Vault or Consul backup job is its own ticket.
- **The loop does not apply this to the cluster.** It produces a repo diff
  and a runbook, nothing more.

## Requirements & restrictions
- **R1.** The pinned Vault version in the repo becomes `2.0.3-1` (apt
  version string, confirmed present for both architectures), edited into
  whatever pin mechanism U1 introduced at
  `bootstrap/playbooks/install_dependencies.yml:94-101`. Re-read that block
  before editing, because U1's shape is not yet known.
- **R2.** Ship a runbook. `tmp/F9-MIGRATION.md` is the bar for structure and
  tone: status line up front, a "Before you start" section whose points are
  the difference between a clean apply and an outage, numbered apply steps
  with copy-pasteable commands and expected outputs, explicit rollback, and
  an "Afterwards" section. Note the file lives under gitignored `tmp/`
  (`.gitignore:1`), so it may not be present; the copy quoted above is from
  2026-07-31.
- **R3.** The runbook proves restore **before** the upgrade, on an isolated
  instance, per Vault's upgrade doc. Backup taken and restore rehearsed are
  two separate steps and only the second one counts.
- **R4.** The runbook caches `vault_1.21.4-1_<arch>.deb` locally before
  touching anything. Vault does not support automatic rollback
  (`https://developer.hashicorp.com/vault/docs/upgrade/rollback`), the apt
  repo prunes old versions, and the documented rollback needs both the old
  binary and the pre-upgrade data.
- **R5.** The chosen live procedure must not rewrite the `nomad-workloads`
  policy. Follow `tmp/F9-MIGRATION.md:51-56`'s reasoning: name the exact
  commands, do not reach for the playbook.
- **R6.** Plain language throughout the runbook, per
  `.claude/rules/plain-language.md`. Active voice, short words, no
  motivational framing. Prose wraps at 80 characters.
- **R7.** Do not silence a gate to make it pass
  (`.claude/rules/prek-code-quality.md`). Fix any pre-existing failure the
  run surfaces (`.claude/rules/pre-existing-issues.md`).
- **R8.** Secrets stay in Vault and never land in the repo (`AGENTS.md`,
  "Secrets"). The runbook may reference `/opt/vault/init.json` by path; it
  must never print or paste a key or token value.
- **R9.** Every version claim in the runbook carries its source. The 2.x
  facts above were checked on 2026-07-31 and must be re-verified at
  implementation time, because 2.0.4 may exist by then.

## Code surface

| Path | Anchor | Change |
| --- | --- | --- |
| `bootstrap/playbooks/install_dependencies.yml` | `:94-101` (`Install Hashistack products`) | Move the Vault pin U1 introduced to `2.0.3-1`. Touch the Vault entry only; `consul`, `nomad`, `nomad-driver-podman` keep their U1 pins. |
| `docs/vault-upgrade.md` | new file | The runbook: pre-flight audit, backup, isolated restore rehearsal, apply, verify, rollback. Path is Open Question 3. |
| `bootstrap/roles/vault_server/templates/vault.hcl.j2` | `:1-21` | **Read only unless Open Question 4 resolves to yes.** If it does, add top-level `enable_unauthenticated_access = ["generate-root"]`; the file is a Jinja template rendered to `/etc/vault.d/vault.hcl` by `roles/vault_server/tasks/main.yml:89-96`, and a change there notifies the `Restart vault` handler (`handlers/main.yml:2-5`). |

Read but not edited, cited so the implementer does not have to find them:

- `bootstrap/roles/vault_server/tasks/main.yml:104-161` - init check, unseal
  from `/opt/vault/init.json`, seal-status guard.
- `bootstrap/roles/nomad_server/tasks/main.yml:257-271` - the policy write
  that must not run.
- `bootstrap/roles/nomad_server/templates/vault_nomad_workloads.hcl.j2:1-11`
  - the identity-templated policy under test for breaking change 1.
- `scripts/unseal_vault.sh:6-13` and `justfile:21-22` - the manual unseal
  path and its env requirements.
- `deployments/infrastructure/backend.tf:1-3`,
  `deployments/applications/backend.tf:1-3` - why a full Consul snapshot
  restore also rolls back Terraform state.
- `deployments/infrastructure/acme.tf:41-90` - the `acme-tls-write` policy
  and the `acme` JWT role, both in the post-upgrade verification set.
- `deployments/infrastructure/services/haproxy.hcl:34-60` - the edge PEM
  render, the sharpest end of a failed upgrade.

## Tests & validation gates

### Repo gates
- `just pre_commit` (`justfile:18-19`, `pre-commit run --all-files`). The
  hooks that bite a YAML-plus-markdown change are `check-yaml --unsafe`,
  `end-of-file-fixer`, and `check-merge-conflict`
  (`.pre-commit-config.yaml:6-13`). `nomad-fmt`, `terraform-fmt` and
  `terraform-validate` (`:14-33`) are no-ops unless Open Question 3 or 4
  pulls in an `.hcl` or `.tf` file.
- Run `just worktree_setup <path>` (`justfile:30-32`) in a fresh worktree
  before the first gate run. `terraform-validate` fails on the missing SSH
  key and tfvars otherwise, and that failure is unrelated to this change.
- **No Ansible lint gate and no CI.** `bootstrap/.ansible-lint` exists but no
  pre-commit hook references it (`grep -c ansible .pre-commit-config.yaml`
  returns 0), and `.github/workflows/` holds only `claude-ollama.yaml` and
  `hermes-interactive.yaml`. Nothing in this repo validates a playbook edit
  automatically. The pin change is checked by reading it and by the live run.

### Pre-flight assertions (runbook, isolated instance, before prod)
These are the real tests. They live in `docs/vault-upgrade.md` and each one
must state its expected output.

1. **Identity-template policy still resolves.** On 2.0.3, restored from the
   `vault/` export, mint a Nomad workload token against `jwt-nomad`'s
   `nomad-workloads` role and read `secret/data/default/haproxy/tls`. Expect
   a successful read, not `permission denied`. This is the assertion that
   decides whether the upgrade is safe at all. A root token cannot produce
   it: root bypasses policy (`tmp/F9-MIGRATION.md:124-126`).
2. **Rendered paths are canonical.** `nomad job inspect` across the live
   jobs; assert no rendered Vault path contains `//`, `/./` or `/../`.
3. **No duplicate HCL attributes.** Start 2.0.3 against the restored data and
   grep the server log for `policy contains duplicate attributes`. Expect
   zero.
4. **Cert key type.** Confirm the live edge certificate is not an RSA key
   over 8192 bits. Expect EC (lego default; no key type is set in
   `acme.hcl`).
5. **Restore is proven, not assumed.** The isolated instance unseals with the
   same three shards and serves a known secret read. If it does not, stop:
   the backup is not a rollback.

### Post-upgrade verification (runbook, prod)
1. `vault status` reports `Version 2.0.3`, `Sealed false`,
   `Storage Type consul`, `HA Enabled true`.
2. `vault auth list` shows `jwt-nomad/` with the same accessor as before.
   A changed accessor invalidates the templated policy and is a stop event.
3. `vault read auth/jwt-nomad/role/nomad-workloads` and
   `.../role/acme` both return, `acme` with
   `token_policies: nomad-workloads, acme-tls-write` (`acme.tf:87`).
4. `vault policy read nomad-workloads` returns **six** `path` blocks, not
   three. Six is correct until F9 is applied. Three means the upgrade
   procedure rewrote the policy, which R5 forbids.
5. `vault policy read acme-tls-write` returns the single write rule
   (`acme.tf:44-48`).
6. A workload actually renews. Pick a job with a bare `vault {}`, force a new
   allocation, and confirm its template renders rather than sitting
   `pending`.
7. The edge still serves TLS:
   `curl -sI https://vault.lab.orangecluster.nl` returns 200.
8. **Re-run 6 and 7 ten minutes later.** Vault templates block and retry
   rather than failing, so an immediate pass is not evidence
   (`tmp/F9-MIGRATION.md:118-123`).
9. `terraform plan` in `deployments/infrastructure/` is clean, proving
   provider `5.3.0` still talks to 2.0.3.

## Risk assessment

**Blast radius: total.** Vault holds every credential on this cluster. A
failed upgrade takes out workload identity for sixteen of nineteen jobs, and
the edge TLS certificate with them.

**Reversibility: only through the backup.** Vault publishes no automatic
rollback and makes no backward-compatibility guarantee for the data store
across an upgrade. Downgrade means stop, install `1.21.4-1`, restore the
pre-upgrade `vault/` data, restore the pre-upgrade config, start, unseal. If
the backup is bad or the old `.deb` is gone, there is no way back.

Failure modes, likeliest first:

1. **The identity-template change rejects `nomad-workloads`.** Sixteen jobs
   lose their secret reads at once and `haproxy` cannot re-render the edge
   PEM. Symptom is quiet: allocations sit `pending`, nothing errors loudly.
   Caught by pre-flight assertion 1 and post-upgrade check 6. Mitigated by
   never proceeding on the doc reading alone.
2. **The procedure rewrites `nomad-workloads` as a side effect.** Any Ansible
   route runs `nomad_server/tasks/main.yml:257-271` and silently applies F9's
   three-rule policy inside the upgrade window, which makes an outage
   impossible to attribute. Caught by post-upgrade check 4.
3. **`/opt/vault/init.json` is missing or unreadable after the stop.** The
   cluster is sealed with no way to unseal. Mitigated by reading and parsing
   it *before* stopping the service, and by rehearsing on the isolated
   instance.
4. **Full `consul snapshot restore` used for rollback.** Rolls Terraform
   state back to snapshot time along with Vault's data. Mitigated by
   preferring the scoped `consul kv import` of `vault/` and by stating the
   side effect in the rollback section.
5. **`haproxy` restarts inside the sealed window.** Its template cannot
   render, and every routed service goes down together rather than coasting
   on the rendered PEM. Mitigated by keeping the window short and not
   touching Nomad during it.
6. **Rollback binary unavailable.** The apt repo currently keeps only
   `1.21.4-1` and `1.21.3-1`; the next prune could remove the target.
   Mitigated by R4.
7. **Restore rehearsal not isolated.** A restored Vault reachable from the
   network revokes live third-party credentials and can strand production
   with irrevocable leases. Mitigated by following the isolation checklist in
   Vault's upgrade doc.
8. **`install_dependencies.yml` run to move the pin.** Its first play
   dist-upgrades every host and can reboot the fleet (`:8-13`, `:34-38`)
   before it reaches the Vault package.

## Subtickets
Ordered. If these become separate plan files, encode the order in each file's
`depends_on`. Only stage 3 is loop-implementable; the rest are operator-run
and the loop's job is to write them down precisely.

1. **U2a - back up and prove restore.** Take `consul snapshot save` and
   `consul kv export vault/`. Cache `vault_1.21.4-1_<arch>.deb`. Stand up an
   isolated instance, restore the `vault/` export, unseal with the same three
   shards, read a known secret. `depends_on = ["U1-..."]`.
2. **U2b - pre-flight audit on 2.0.3.** On that isolated instance, run
   pre-flight assertions 1 through 4. Assertion 1 is the gate: if the
   templated policy stops resolving, this ticket stops and becomes a policy
   rewrite. `depends_on = ["U2a"]`.
3. **U2c - repo change (the loop's share).** Move the pin to `2.0.3-1` and
   write `docs/vault-upgrade.md` carrying the findings of U2a and U2b, the
   apply steps, the verification set, and the rollback.
   `depends_on = ["U2b"]`.
4. **U2d - apply and verify on the manager.** Operator runs the runbook: stop
   `vault`, `apt install vault=2.0.3-1`, start, unseal, then the full
   post-upgrade verification set including the ten-minute re-check. Record
   the live-apply date the way `tmp/F9-MIGRATION.md:163-167` does.
   `depends_on = ["U2c"]`.

## Open questions

1. **Target 2.0.3, or hold at 2.0.2?**
   *Recommendation: 2.0.3.* It is the current Community release, six weeks
   old at time of writing, and it carries fixes 2.0.2 lacks. Holding one
   patch back buys nothing and 2.0.2 has the same major boundary to cross.
   Re-check for 2.0.4 at implementation time (R9).

2. **Does the 2.0.1 wildcard rejection break a literal trailing `/*` after a
   rendered template, or only a wildcard inside the rendered value?**
   The doc's only example is a metadata value containing `+`. The CHANGELOG
   entry is one line. Both readings survive the published text, and
   `vault_nomad_workloads.hcl.j2:1,9` uses a literal trailing `/*` after a
   rendered template.
   *Recommendation: treat it as unknown and settle it empirically.* Pre-flight
   assertion 1 answers it in an hour on an isolated instance and costs
   nothing. Do not proceed on the doc reading. If the strict reading turns
   out to be right, this ticket blocks on a policy rewrite and that is a
   separate ticket.

3. **Where does the runbook live: `docs/vault-upgrade.md` or `tmp/`?**
   `tmp/` is gitignored (`.gitignore:1`), which is why `tmp/F9-MIGRATION.md`
   is untracked. `docs/` holds the tracked operational pages
   (`credential-rotation.md`, `tls-certificates.md`, `gcs-backups.md`).
   *Recommendation: `docs/vault-upgrade.md`.* A gitignored runbook means the
   loop's commit carries nothing reviewable, and U3 and U4 in this epic will
   reuse the same procedure.

4. **Add `enable_unauthenticated_access = ["generate-root"]` to
   `vault.hcl.j2` to keep the old break-glass path?**
   *Recommendation: no.* The root token already sits in
   `/opt/vault/init.json` on the manager, so generate-root is not the live
   recovery path. Re-opening an unauthenticated key-update endpoint on a
   listener with `tls_disable = true` (`vault.hcl.j2:17-20`) trades real
   attack surface for a path that is already covered. Revisit under
   `D5-cli-breakglass`, which owns break-glass design. If the operator
   overrules this, the config key belongs in `vault.hcl.j2` and the change
   notifies the `Restart vault` handler, so it must be sequenced into the
   same outage window rather than applied separately.

5. **Sequence against F2.**
   *Recommendation: upgrade first.* F2 is unmerged and unapplied, so
   upgrading now keeps the change under test to a single variable. If F2
   lands first, add its `userpass` mount and its OIDC provider stack to the
   post-upgrade verification set, and re-run pre-flight assertion 1 against
   any templated policy it introduces, since breaking change 1 applies to
   those identically.

6. **Does U1's pin mechanism land as an apt version string on the package
   list, or as a variable?**
   U1 is not authored yet; `.loop/plans/` has no `U1-*` file and the ledger
   has no `upgrade` epic.
   *Recommendation: write the ticket against
   `install_dependencies.yml:94-101` and re-read that block before editing.*
   If U1's shape differs from an inline `vault=<version>` pin, follow U1's
   convention rather than introducing a second one.

7. **Bump the Terraform Vault provider in the same window?**
   Pinned `~>5.3.0`, locked `5.3.0` in both roots; latest is `5.10.1`
   (2026-06-26), which post-dates Vault 2.0.
   *Recommendation: no.* Verify with post-upgrade check 9 and open a
   follow-up only if `terraform plan` breaks. Bundling a provider bump into
   an outage window makes attribution harder for no gain.

8. **Should this ticket also leave a recurring Vault backup behind?**
   The cluster has none, and the runbook will produce a one-shot backup
   procedure that a periodic job could reuse.
   *Recommendation: no, but file the follow-up.* It is real scope, the
   ticket is already Large, and `docs/gcs-backups.md` shows the pattern a
   later ticket would copy.

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
