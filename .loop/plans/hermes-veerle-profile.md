---
epic = "hermes"
priority = 20
summary = """
Add Veerle as a second profile inside the ONE running Hermes instance, not a
second instance: her own Telegram bot, cron, SOUL, and OpenViking identity,
served by the existing gateway under `gateway.multiplex_profiles`. Three forks
go back to the operator first: the dashboard is gateway-wide with no
per-profile authorization, the bundled OpenViking memory provider reads
credentials from raw `os.environ` and so ignores per-profile scoping, and
`var.vault_openviking_workloads` cannot express two identity roles for one
Nomad job.
"""
---
# Ticket: hermes-veerle-profile

## 1. Add Veerle as a second Hermes profile in the existing instance

One Nomad job, one container, one `hermes_data` volume. Veerle becomes a
second profile served by the default profile's gateway under
`gateway.multiplex_profiles`, with her own Telegram bot, cron jobs, SOUL,
and OpenViking identity.

## 2. Size / Effort

**L.** Drivers:

- Two Terraform roots, and a `var.vault_openviking_workloads` restructure that
  moves existing resource addresses (`moved` blocks required).
- A new prestart-rendered profile tree under `/opt/data/profiles/veerle/`.
- Flipping multiplexing on changes how the EXISTING jasper profile resolves
  credentials (P7), so this is not a pure addition.
- Three unresolved forks (Q1, Q2, Q3) gate the design.

## 3. Triggered by

Operator request: "add Veerle as a hermes user ... her own, isolated profile,
Telegram channel, cron jobs, and memory store (already configured)". Explicitly
NOT a second instance: "No: not SECOND instance. Same fucking instance mate.
Should be possible with profiles."

## 4. Context

### Today: one profile, one home

`HERMES_HOME=/opt/data` (`deployments/applications/services/hermes.hcl:526`).
There is exactly one profile, the default. `/opt/data/profiles/` does not
exist. Live probe confirms no secondary profile is served:

```
$ curl -s -o /dev/null -w '%{http_code}' http://192.168.2.50:8642/p/veerle/v1/models
404
$ curl -s http://192.168.2.50:8642/health
{"status": "ok", "platform": "hermes-agent", "version": "0.21.0"}
```

### How the one profile is built

The prestart `config` task (`deployments/applications/services/hermes.hcl:30`) renders three files and copies
them onto the persistent volume: `deployments/applications/services/hermes.hcl:81` writes `/opt/data/.env`,
`/opt/data/config.yaml` and `/opt/data/SOUL.md`. It creates the profile
directories at `deployments/applications/services/hermes.hcl:73` and takes two ownership passes
(`deployments/applications/services/hermes.hcl:79`, `deployments/applications/services/hermes.hcl:125`). Skills arrive as a base64 TSV bundle
rebuilt every deploy and wired in through `skills.external_dirs`
(`deployments/applications/services/hermes.hcl:247`).

Terraform feeds it at `deployments/applications/services.tf:270`, with the
Vault paths at `deployments/applications/services.tf:304` and `deployments/applications/services.tf:307`, the SOUL at
`deployments/applications/services.tf:312` and the skills fileset at `deployments/applications/services.tf:313`.

### Two credential channels, and they do not agree

The gateway task reads credentials from TWO places:

- `/opt/data/.env`, rendered at `deployments/applications/services/hermes.hcl:215` from the template at
  `deployments/applications/services/hermes.hcl:184`.
- the process environment, from `secrets/file.env` with `env = true`
  (`deployments/applications/services/hermes.hcl:494`) plus the `env {}` block at `deployments/applications/services/hermes.hcl:525`.

They are not the same set. `API_SERVER_KEY` (`deployments/applications/services/hermes.hcl:487`) and `GH_TOKEN`
exist ONLY in the process environment, never in `/opt/data/.env`. Today that
is invisible, because a single-profile gateway reads `os.environ`. Under
multiplexing it stops being invisible (P7).

### OpenViking identity

The job mints a Vault identity token for itself and a loopback sidecar
substitutes it per request (`deployments/applications/services/hermes.hcl:382`), reading
`identity/oidc/token/openviking-hermes` (`deployments/applications/services/hermes.hcl:424`) with
`change_mode = "noop"`. The sidecar listens on the port from
`deployments/applications/services/hermes.hcl:409` and Hermes points at it via `deployments/applications/services/hermes.hcl:528`. The
header comment at `deployments/applications/services/hermes.hcl:373` records why: every read of the identity
path mints a new JWT, so rendering it into the process environment restarted
the task on every consul-template poll. Measured, not predicted.

The account mapping lives in the infrastructure root.
`deployments/infrastructure/variables.tf:112` declares
`vault_openviking_workloads`, whose map key is overloaded four ways: the
identity-role name suffix (`deployments/infrastructure/oidc.tf:152`), the
policy name suffix and the single path it grants
(`deployments/infrastructure/machine_roles.tf:382`), and the JWT role name
(`deployments/infrastructure/machine_roles.tf:405`) AND the `nomad_job_id` bound
claim (`deployments/infrastructure/machine_roles.tf:411`). That shape cannot express
a second identity role read by the SAME Nomad job: a key `hermes-veerle` would
mint a JWT role bound to a Nomad job id that does not exist (Q3).

`deployments/infrastructure/machine_roles.tf:379` records the property to preserve: the read is scoped to
that job's own role path and never `identity/oidc/token/*`.

### Veerle already exists as a person, not as a workload

`deployments/infrastructure/variables.tf:91` already defines her as an
OpenViking consumer with `account = "lab"`, `user = "veerle"`.
`deployments/applications/secrets.tf:302` already derives her human key. That
is the "already configured" in the request. It is a HUMAN key, not a workload
identity token, and it is not what Hermes would use.

`deployments/applications/services.tf:711` records that she has an OpenViking
account from before the OIDC flip, and `deployments/applications/services.tf:713` names
`scripts/ov_identity_probe.py` as what answers whether an uninitialized tree
reads and writes.

### The dashboard is gateway-wide

`deployments/applications/services/hermes.hcl:544` turns on the dashboard on port 9119, served to
`hermes-gateway.lab.orangecluster.nl` by
`deployments/infrastructure/services/haproxy.hcl:217`. Its OIDC client is
assigned to `operators` (`deployments/infrastructure/oidc.tf:779`), which is
the developer plus admin groups (`deployments/infrastructure/oidc.tf:561`). Veerle is in neither. That is
the fork in Q1.

### Uncommitted work in the tree

`deployments/applications/services.tf`,
`deployments/applications/services/hermes.hcl`,
`deployments/applications/services/openviking.hcl`,
`deployments/infrastructure/oidc.tf`,
`deployments/infrastructure/services/haproxy.hcl` and
`docs/haproxy_reverse_proxy.md` are MODIFIED and uncommitted on entry. They
are the in-flight hermes-dashboard change. Every anchor in this ticket is
against the WORKING TREE, not `HEAD`. Re-resolve anchors if that work lands or
is reverted first.

## 5. Non-goals / out of scope

- No second Hermes instance, Nomad job, container, port, or host volume.
- No per-profile s6 gateway slots. The image's `02-reconcile-profiles`
  cont-init can register one slot per profile, but a multiplexing default
  gateway already owns every profile's inbound platforms, so per-profile slots
  would create a second owner.
- No `gateway.profile_routes`. That routes ONE shared bot token by
  guild/chat/thread. Veerle gets her own bot, so it buys nothing here.
- No email platform for Veerle.
- No new `.tf` file named after her or after this feature.
- No edge change. HAProxy already serves 9119 (`deployments/infrastructure/services/haproxy.hcl:217`) and nothing
  new is exposed there.
- No firewall change. `deployments/applications/services.tf:86` already admits
  192.168.2.30 to 9119, which is the HAProxy edge and the only path to the
  dashboard. Her laptop reaches the edge, not the node.
- No change to `deployments/applications/services/hermes/register-cron.sh`. It
  is referenced by nothing and is pre-existing dead code.
- No migration of jasper's sessions. Upstream keeps the default profile on the
  historical `agent:main:` namespace byte for byte (P5).
- Whatever Q4 settles as out of scope lands here.

## 6. Requirements & restrictions

### Must achieve

- **R1.** `/opt/data/profiles/veerle/` carries `config.yaml`, `.env` and
  `SOUL.md`, written declaratively by the prestart `config` task in the same
  style as `deployments/applications/services/hermes.hcl:81`. No hand-run `hermes profile create`. Terraform can
  do this because upstream's served-profile scan is a directory scan plus a
  name check with no config read (P2).
- **R2.** Veerle's `config.yaml` MUST pin `platforms.api_server.enabled: false`
  explicitly. Omitting the key is NOT equivalent: upstream force-enables the
  listener from the inherited process-level `API_SERVER_KEY` unless the
  profile pins it false, and a secondary profile that binds a port is SKIPPED
  ENTIRELY (P3).
- **R3.** Veerle's Telegram bot token is her own, stored in Vault under
  `default/hermes-veerle/telegram` and rendered only into HER `.env`. Two
  profiles sharing one `(platform, token)` fails gateway startup naming both
  (P4).
- **R4.** The default profile's behavior is unchanged after the multiplexing
  flip. Specifically `API_SERVER_KEY` must be added to `/opt/data/.env`
  (`deployments/applications/services/hermes.hcl:184` template), because it currently lives only in the process
  environment and upstream deliberately excludes it from the globals that keep
  reading `os.environ` (P7). Producer: the live probe in §8.
- **R5.** Veerle's OpenViking writes land in `lab`/`veerle`, not `lab`/`jasper`.
  Producer: `scripts/ov_identity_probe.py --role openviking-veerle
  --account lab --user veerle` (`scripts/ov_identity_probe.py:220`), an
  existing repo capability. Q2 decides whether this is reachable at all.
- **R6.** Her cron jobs fire. Under multiplexing the in-process ticker walks
  every served profile's own home (P6). Producer: the `/cron list` check in §8.

### Restrictions the repo imposes

- **R7.** One file per SUBSYSTEM, never per feature
  (`.claude/rules/terraform-file-layout.md`). Her Vault KV writes go in
  `secrets.tf`, her Nomad job changes in `services.tf`, her identity-token role
  in `oidc.tf`, her policy and JWT role in `machine_roles.tf`. There must be no
  `veerle.tf` and no `profiles.tf`.
- **R8.** Editing `services/hermes.hcl` is NOT free.
  `templatefile("services/hermes.hcl", ...)` folds the whole file, comments
  included, into `nomad_job.jobspec`, so any edit re-registers the job
  (`.claude/rules/terraform-file-layout.md`, "Moving a block is free. Editing
  one is not."). This ticket necessarily edits it; the requirement is to edit
  it ONCE, not to churn it.
- **R9.** Comments record only what the code cannot say
  (`.claude/rules/minimal-comments.md`). The existing hermes files carry heavy
  comments recording MEASURED traps (`deployments/applications/services/hermes.hcl:373` is the model). Match that
  register. The traps in P3, P7 and Q2 are exactly the kind that earn a
  comment; nothing else here does.
- **R10.** Plain language in every comment and commit message
  (`.claude/rules/plain-language.md`).
- **R11.** Fix any pre-existing failure the gates surface rather than working
  around it (`.claude/rules/pre-existing-issues.md`). Never silence a check
  (`.claude/rules/prek-code-quality.md`).
- **R12.** New Python ships with a test
  (`.claude/rules/python-testing.md`). See §8 for the form this repo uses for
  `scripts/`.

## 7. Code surface

### `deployments/infrastructure/` (apply FIRST)

| Path | Change |
|---|---|
| `deployments/infrastructure/variables.tf:112` | Restructure `vault_openviking_workloads` so one Nomad job can carry more than one identity role. Shape decided by Q3. |
| `deployments/infrastructure/oidc.tf:152` | `vault_identity_oidc_role.openviking_workload` gains a flattened `for_each`. The EXISTING role name must stay `openviking-hermes` byte for byte: `deployments/applications/services/hermes.hcl:424` reads that literal path. Add `moved` blocks for the key change. |
| `deployments/infrastructure/machine_roles.tf:382` | `vault_policy.openviking_workload` grants one `path` block per identity role the job owns. Preserve the never-`identity/oidc/token/*` property recorded at `deployments/infrastructure/machine_roles.tf:379`. |
| `deployments/infrastructure/machine_roles.tf:401` | `vault_jwt_auth_backend_role.openviking_workload` stays keyed by Nomad job id. `role_name` (`deployments/infrastructure/machine_roles.tf:405`) and the `nomad_job_id` bound claim (`deployments/infrastructure/machine_roles.tf:411`) must remain `hermes`. |

### `deployments/applications/`

| Path | Change |
|---|---|
| `deployments/applications/secrets.tf:205` | Add `random_id.veerle_api_server_key` and `vault_kv_secret_v2.veerle_api_server` at `default/hermes-veerle/api_server`, mirroring the existing pair. Only if Q1 lands on an api-server route for her. |
| `deployments/applications/secrets.tf:220` | Decide Veerle's Bifrost key: share `bifrost_hermes_key` or mint her own. Sharing is the recommendation (one virtual key per JOB, and there is one job); note it means her spend is not separable. |
| `deployments/applications/services.tf:270` | Add `templatefile` vars for her profile: `veerle_telegram_secret`, `veerle_soul_md`, `veerle_openviking_user`, `veerle_openviking_proxy_port`, and (per Q1) `veerle_api_server_secret`. |
| `deployments/applications/services.tf:302` | The existing `ov_auth_proxy_script` var is REUSED by the second sidecar. `deployments/applications/services/hermes/ov_auth_proxy.py` is NOT modified: it already takes its upstream, token file and port from `OV_*` env (`deployments/applications/services/hermes/ov_auth_proxy.py:32`), so a second instance needs no code change. |
| `deployments/applications/services.tf:321` | Extend `depends_on` if Veerle gets her own Bifrost key. |
| `deployments/applications/services/hermes.hcl:73` | `mkdir -p` her profile dirs. Upstream bootstraps `memories sessions skills skins logs plans workspace cron home` in every profile. The two `chown -R ... /opt/data` passes at `deployments/applications/services/hermes.hcl:79` and `deployments/applications/services/hermes.hcl:125` already cover a new subdirectory; confirm rather than assume. |
| `deployments/applications/services/hermes.hcl:81` | Copy her three rendered files into `/opt/data/profiles/veerle/`. |
| `deployments/applications/services/hermes.hcl:184` | Add `API_SERVER_KEY` to the DEFAULT profile's `/opt/data/.env` (R4). |
| `deployments/applications/services/hermes.hcl:215` | New sibling templates: `local/veerle/hermes.env`, `local/veerle/config.yaml`, `local/veerle/SOUL.md`. |
| `deployments/applications/services/hermes.hcl:247` | Veerle's own `config.yaml` points `skills.external_dirs` at the same absolute `/opt/data/skills-library`. Read-only sharing is safe (P1). |
| `deployments/applications/services/hermes.hcl:338` | Add `gateway.multiplex_profiles: true` to the DEFAULT profile's `config.yaml`. It owns the multiplexer. |
| `deployments/applications/services/hermes.hcl:382` | Add a SECOND sidecar task `ov-auth-proxy-veerle` on a second port, reading `identity/oidc/token/openviking-veerle`. A second task rather than a per-profile selector inside the proxy: Hermes sends no profile identifier on an OpenViking call, so the proxy has nothing to select on. |
| `deployments/applications/services/hermes.hcl:409` | The second sidecar's `OV_LISTEN_PORT`. |
| `deployments/applications/services/hermes.hcl:424` | Template the role name off the new variable rather than the `openviking-hermes` literal, so the two sidecars differ only by input. |
| `deployments/applications/services/hermes/SOUL.md` | Unchanged. Add a sibling `deployments/applications/services/hermes/veerle/SOUL.md`. |
| `deployments/applications/services/hermes/veerle/SOUL.md` | NEW. Her persona. Content is the operator's to write; the ticket ships a placeholder naming what it is. |

### Gate and test surface

| Path | Change |
|---|---|
| `scripts/check_hermes_profiles.py` | NEW. Offline assertions over `services/hermes.hcl` (§8). Carries `--self-test`, the convention at `scripts/tf_block_diff.py:204`. |
| `.pre-commit-config.yaml:30` | Register the new checker as a local hook beside `terraform-validate`. |

## 8. Tests & validation gates

### The repo's real gates

`just pre_commit` (`justfile`, recipe `pre_commit`) runs
`pre-commit run --all-files`, which is the loop's configured gate. From
`.pre-commit-config.yaml` the ones this change trips:

- `nomad-fmt` (`nomad fmt -recursive`) on `services/hermes.hcl`.
- `terraform-fmt` (`terraform fmt -check -recursive`).
- `terraform-validate` (`scripts/tf_validate.sh`), which validates both roots
  offline.
- `check-ast`, `debug-statements`, `end-of-file-fixer` on the new script.
- `ruff`, `ruff-format`, `mypy --strict` on `scripts/`, so
  `scripts/check_hermes_profiles.py` must be typed and clean.

There is NO CI. There is no Python test suite for `deployments/`: `tests/`
holds only `tests/wi-vault-probe.nomad.hcl`, and `cli/tests/` covers the CLI
only. Nothing in this repo runs a deployed service. Say so rather than
inventing a gate.

### Tests to add

`scripts/check_hermes_profiles.py --self-test` (file listed in §7), following
`scripts/tf_block_diff.py:156`. It asserts, offline, against
`deployments/applications/services/hermes.hcl`:

1. Every secondary profile's rendered `config.yaml` pins
   `platforms.api_server.enabled: false` (R2). This is the failure that
   silently skips her whole profile, so it is the first assertion.
2. No two profiles are rendered from the same Telegram Vault path (R3).
3. The default profile's `.env` template carries `API_SERVER_KEY` (R4).
4. Each sidecar's `OV_LISTEN_PORT` is distinct, and each profile's
   `OPENVIKING_ENDPOINT` points at its OWN sidecar port.

The self-test covers the cases that would let a violation escape: a profile
with no `api_server` key at all, a profile with `enabled: true`, and two
profiles sharing a token path.

### Post-apply manual verification

No gate runs these. Record the output on the ticket.

- `scripts/ov_identity_probe.py --role openviking-veerle --account lab
  --user veerle` (R5). Asserts the grant AND the denials.
- `curl -s http://192.168.2.50:9119/api/status` before and after, comparing
  `gateway_platforms`. Today it reports `telegram`, `email`, `api_server` all
  `connected`; `api_server` dropping out is the R4 regression.
- Send `/cron list` to Veerle's bot and to jasper's bot. Each must return only
  its own jobs (R6).
- Write a memory as Veerle, then read it as jasper. It must NOT be visible.
  This is what Q2 puts at risk, and it is the assertion that catches it.

## 9. Risk assessment

**Blast radius: the running Hermes instance, which is live and in daily use.**
The live probe shows `active_sessions: 2` and three connected platforms. This
is not a greenfield addition.

- **Flipping multiplexing changes the EXISTING profile.** Upstream loads the
  default profile's config under the default profile's secret scope once
  multiplexing is on (P7), so credentials that live only in the process
  environment stop resolving. `API_SERVER_KEY` is the known case. `GH_TOKEN`
  is the suspected second one and is not covered by R4; check it.
- **Memory cross-contamination (Q2).** The bundled OpenViking provider reads
  `os.environ` directly, so Veerle's memory can land in jasper's tree. This
  fails silently: both profiles get 200s, and the damage is only visible by
  reading jasper's tree. Highest-severity failure mode in this ticket.
- **Dashboard exposure (Q1).** Adding Veerle to `operators` is not scoped to
  Hermes. `deployments/infrastructure/oidc.tf:561` shows `operators` is the developer plus admin groups,
  so it also grants everything else those groups carry.
- **A config error skips her profile, not the gateway.** Upstream degrades a
  port-binding conflict to a skipped secondary profile with a warning. Her
  profile would simply not appear. Failure is quiet, which is why it is the
  first self-test assertion.
- **Terraform state.** The Q3 restructure moves `for_each` keys on
  `vault_identity_oidc_role.openviking_workload`. Without `moved` blocks
  Terraform destroys and recreates the role that `deployments/applications/services/hermes.hcl:424` reads,
  breaking jasper's OpenViking access until the next apply settles.
- **Volume headroom.** `deployments/infrastructure/services.tf:62` caps
  `hermes_data` at 5 GiB. See Q4.

**Reversibility: good, with one exception.** Multiplexing is a config flag and
reverts on the next deploy. Deleting her profile directory removes her state.
The exception is Q2: memory written into the wrong OpenViking tree is not
undone by reverting the flag.

## 10. Subtickets

Ordered. Each is one loop iteration. If these become separate plan files,
encode the order in `depends_on`, not just here.

1. **`hermes-veerle-ov-workload-roles`** (infrastructure root). Restructure
   `vault_openviking_workloads` per Q3, add `moved` blocks, add the
   `openviking-veerle` identity role and extend the policy. Gate:
   `terraform plan` reports zero destroys and zero changes to the existing
   `openviking-hermes` role.
2. **`hermes-veerle-default-profile-parity`** (applications root). Add
   `API_SERVER_KEY` to `/opt/data/.env` and flip
   `gateway.multiplex_profiles: true`, with NO second profile on disk yet.
   This isolates the R4 regression from everything else: multiplexing with one
   profile must be a no-op. Gate: `/api/status` still reports `api_server`
   connected.
3. **`hermes-veerle-profile-tree`**. Render her three files, mkdir her dirs,
   add the second sidecar. Depends on 1 and 2.
4. **`hermes-veerle-profile-checker`**. Ship
   `scripts/check_hermes_profiles.py` and its pre-commit hook.

Subticket 2 before 3 is the load-bearing ordering: it separates "does
multiplexing break the live profile" from "does the new profile work".

## 11. Open questions

Every one needs an operator decision before the loop runs. Q1 and Q2 are
blocking; the design cannot be written without them.

### Q1. Hermes Desktop reaches a gateway-wide dashboard with no per-profile authorization. `security-fork`

The operator asked for Veerle to have Hermes Desktop. Desktop connects to a
`hermes serve` / dashboard backend on 9119, not to the API server on 8642
(P8). The dashboard is machine-level: one sign-in, every profile. Probed at
the pinned tag, no per-principal scoping exists (P9). So an authenticated
Veerle could read and write jasper's `config.yaml`, his API Keys page, his
Chat, and `DELETE /api/profiles/{name}`.

Options:

- **(a) Telegram and cron only, no dashboard.** Smallest and safest. Still
  meets "own profile, Telegram channel, cron jobs, memory store". She loses
  the Desktop GUI.
- **(b) Add her to `operators`.** She gets the default profile as well as her
  own: `HERMES_YOLO_MODE=true` (`deployments/applications/services/hermes.hcl:527`), `NOMAD_TOKEN`,
  `GITHUB_PERSONAL_ACCESS_TOKEN`, plus everything else the developer and admin
  groups carry (`deployments/infrastructure/oidc.tf:561`). Defensible only if she is trusted with cluster
  admin.
- **(c) A second, isolated dashboard for her profile.** `hermes dashboard
  --isolated` exists at the pinned tag (P10) and would need its own port, OIDC
  client, edge hostname and firewall rule. Two costs: the image ships exactly
  ONE dashboard s6 slot hardcoded to `/opt/data` (P10), so this needs a new
  Nomad task in the same group, not a config flag. And upstream warns that a
  dashboard and a gateway sharing one HERMES_HOME race on the same per-profile
  lock files (P10).
- **(d) Per-profile scoping.** Does not exist at the pinned tag (P9). Listed so
  it is rejected knowingly.

**Recommendation: (a) now, (c) as a follow-up ticket.** (a) delivers the whole
ask minus the GUI and adds no new attack surface. (b) hands cluster-admin
access to someone the repo currently models as a consumer with exactly one
Vault path (`deployments/infrastructure/variables.tf:91`). The operator asked for Desktop before knowing
the dashboard is gateway-wide, so this goes back to them.

### Q2. The OpenViking memory provider ignores per-profile credential scoping. `correctness-fork`

Upstream isolates per-profile credentials through a fail-closed secret scope
that deliberately does NOT union into `os.environ` (P11). The bundled
OpenViking memory provider does not use it: it reads `OPENVIKING_ENDPOINT`,
`_API_KEY`, `_ACCOUNT`, `_USER` from raw `os.environ` (P12), and env WINS over
the per-profile `config.yaml` fallback. The gateway task puts those values in
the process environment today (`deployments/applications/services/hermes.hcl:483`, `deployments/applications/services/hermes.hcl:528`). So
Veerle's memory would be written through JASPER's sidecar into JASPER's tree,
whatever her `.env` says.

Subprocess `env_passthrough` IS scoped correctly (P13), so her terminal tool
would see her values while her memory provider sees his. Split-brain, and it
fails silently.

Options:

- **(a) Strip `OPENVIKING_*` from the process environment and carry them per
  profile in each `config.yaml` under `memory.openviking.*`.** Correct, and it
  touches the default profile too. One thing to verify first: upstream sources
  `api_key` from the environment and never from `config.yaml` (P12), so both
  profiles would resolve an empty key. The repo already sends a placeholder
  the sidecar strips (`deployments/applications/services.tf:302` region), so an empty key MAY be fine.
  Unverified.
- **(b) Per-profile ovcli config file** via `memory.openviking.ovcli_config_path`,
  a per-profile `config.yaml` key. Still requires stripping the process env,
  since env outranks ovcli.
- **(c) Ship Veerle with no OpenViking memory** (local memory or none), and
  split her memory isolation into its own ticket. Unblocks Telegram and cron
  immediately, and defers the risky part.
- **(d) Accept shared memory.** Rejects the operator's "isolated ... memory
  store" outright. Listed so it is rejected knowingly, not chosen by default.

**Recommendation: (c) for this ticket, (a) as its own ticket with a probe
first.** (a) changes how the LIVE profile resolves its memory credentials,
which is a bigger blast radius than adding a person and does not belong in the
same iteration.

### Q3. `vault_openviking_workloads` cannot express two identity roles for one Nomad job. `design-fork`

Its key is the identity role suffix, the policy suffix, the JWT role name and the
`nomad_job_id` bound claim at once (`deployments/infrastructure/variables.tf:112`, `deployments/infrastructure/oidc.tf:152`,
`deployments/infrastructure/machine_roles.tf:382`, `deployments/infrastructure/machine_roles.tf:401`). A `hermes-veerle` key would
bind a JWT role to a nonexistent Nomad job id.

Options:

- **(a) Key by job id, value carries a map of roles.**
  `map(object({ roles = map(object({ account, user })) }))`. One JWT role and
  one policy per job, keyed as today so those addresses do not move. The
  policy emits one `path` block per role, preserving `deployments/infrastructure/machine_roles.tf:379`.
  Only `vault_identity_oidc_role.openviking_workload` changes keys, so one
  `moved` block per existing entry.
- **(b) Add a `job` field to the value, keep the key as the role suffix.**
  Breaks: two entries with `job = "hermes"` would declare the same
  `vault_jwt_auth_backend_role` twice.
- **(c) A second variable for extra roles.** Two variables describing one
  thing; the next reader has to check both.

**Recommendation: (a).** It is the only option that keeps one JWT role per job
while letting a job hold several identity roles, and it moves the fewest
addresses. Note the identity role NAME must stay `openviking-hermes`: it is a
literal in `deployments/applications/services/hermes.hcl:424`.

### Q4. `hermes_data` headroom is unmeasured. `unmeasurable-requirement`

"A second profile's sessions, memory and state DB fit within the volume" names
a QUANTITY (bytes used against the 5 GiB cap at
`deployments/infrastructure/services.tf:62`). Nothing in §7 produces it, and I
could not measure it: `du` on the volume needs root on the node.

```
$ ssh radxa@192.168.2.50 'du -sh /opt/nomad/data/host_volumes/*hermes*'
du: cannot access '/opt/nomad/data/host_volumes/*hermes*': Permission denied
$ ssh radxa@192.168.2.50 'df -h /opt/nomad/data'
/dev/nvme0n1p1  234G   89G  134G  40% /
```

The node has 134 GiB free, so the 5 GiB cap is a Nomad-declared ceiling rather
than a physical one. Options:

- **(a) `widen-surface`.** Add a usage producer to §7 and revise §2. Overkill
  for one number.
- **(b) `split-ticket`.** Move volume sizing to its own ticket with
  `depends_on = ["hermes-veerle-profile"]`, where a second profile's real
  growth can be measured rather than guessed.
- **(c) `drop-requirement`.** Cut it from §6 and record in §5 that volume
  headroom is out of scope.
- **(d) `declared-proxy`.** Score it on the `df` figure above, LABELLED: `df`
  measures the whole root filesystem and does NOT measure the `hermes_data`
  volume's own usage against its 5 GiB cap.

**Recommendation: (c), with (b) opened if growth surprises.** The cap is a
Terraform number with headroom behind it, and raising `capacity_max` is a
one-line change.

### Q5. Does Veerle's `lab`/`veerle` tree read and write before anything initializes it?

`deployments/applications/services.tf:711` records that she has an account
from before the OIDC flip, and `deployments/applications/services.tf:695` records that the OIDC plugin
creates nothing. Whether an uninitialized tree serves a read and a write is
explicitly open in that comment.

**Recommendation: run `scripts/ov_identity_probe.py` (its
`report_unknown_account` case, `ov_identity_probe.py:195`) BEFORE subticket 3,
and record the answer in `services.tf`'s comment.** Cheap, and it decides
whether adding a person needs a provisioning step.

### Q6. Operator prerequisites Terraform cannot do

Not forks, but the apply fails or misbehaves without them:

1. Create Veerle's bot with BotFather and write the token to Vault at
   `default/hermes-veerle/telegram` (key `bot_token`, matching the shape
   `deployments/applications/services/hermes.hcl:185` reads).
2. Capture her NUMERIC Telegram user id for `TELEGRAM_ALLOWED_USERS` and
   `TELEGRAM_HOME_CHANNEL`. A username will not work.
3. Write her SOUL content into `deployments/applications/services/hermes/veerle/SOUL.md`.

No firewall rule and no laptop IP are needed. Her path is
laptop to HAProxy edge to 9119, and
`deployments/applications/services.tf:86` already admits the edge.

## Premises / assumptions

- **P1. A secondary profile can share the absolute `/opt/data/skills-library`
  read-only.** VERIFIED from source. `get_external_skills_dirs()` reads
  `skills.external_dirs` from the calling profile's own `config.yaml` and
  resolves only RELATIVE entries against `HERMES_HOME`
  (`agent/skill_utils.py`, upstream at `v2026.8.31`); an absolute
  path resolves absolutely. Entries resolving to the profile's own
  `skills/` dir are skipped, and `/opt/data/skills-library` is not that path.
  Source: https://github.com/NousResearch/hermes-agent/blob/v2026.8.31/agent/skill_utils.py (`get_external_skills_dirs`).
- **P2. Terraform can create a profile by writing a directory; no
  `hermes profile create` is needed.** VERIFIED from source.
  `profiles_to_serve(multiplex=True)` is documented as "a directory scan and
  name validation only: no per-profile config reads"
  (`hermes_cli/profiles.py`). It accepts any dir under
  `<home>/profiles/` matching `^[a-z0-9][a-z0-9_-]{0,63}$`
  (`hermes_cli/profiles.py`) that is not tombstoned. `veerle` matches and is
  not reserved.
  Source: https://github.com/NousResearch/hermes-agent/blob/v2026.8.31/hermes_cli/profiles.py (`profiles_to_serve`, `_PROFILE_ID_RE`).
- **P3. A secondary profile must pin `api_server.enabled: false` explicitly.**
  VERIFIED from source. `gateway/config.py` at the api_server branch states:
  "In multiplex mode a secondary profile's config.yaml pins
  `platforms.api_server.enabled: false` ... That profile still inherits the
  process-level env (including `API_SERVER_KEY`); without this guard the
  env-var presence would force-enable the listener and trip the
  MultiplexConfigError check." `api_server` is in
  `PORT_BINDING_PLATFORM_VALUES` (`gateway/config.py`), and upstream
  degrades that conflict to a SKIPPED secondary profile
  (`website/docs/user-guide/multi-profile-gateways.md`, "Skipping secondary
  profile ... due to port-binding config error").
  Source: https://github.com/NousResearch/hermes-agent/blob/v2026.8.31/gateway/config.py (`PORT_BINDING_PLATFORM_VALUES`, the
  api_server branch of `_apply_env_overrides`).
- **P4. Two profiles cannot poll one Telegram token.** VERIFIED from the
  upstream doc at the pinned tag: "each profile that enables one must supply
  its own bot token ... If two profiles configure the same
  `(platform, token)`, startup fails fast naming both profiles".
  Source: https://github.com/NousResearch/hermes-agent/blob/v2026.8.31/website/docs/user-guide/multi-profile-gateways.md
  (section "Per-credential platforms still need their own token per profile").
  This makes Veerle's own BotFather bot forced, not merely preferred.
- **P5. The default profile's sessions are untouched.** VERIFIED from the
  upstream doc: sessions are namespaced `agent:<profile>:`, and "The default
  profile keeps the historical `agent:main:` namespace byte-for-byte ... no
  migration, no orphaned history".
  Source: https://github.com/NousResearch/hermes-agent/blob/v2026.8.31/website/docs/user-guide/multi-profile-gateways.md
  (section "Session keys are namespaced by profile").
- **P6. The in-process cron scheduler ticks secondary profiles, each in its
  own home.** VERIFIED from source, which is stronger than the doc line the
  brief relied on. `cron/scheduler_provider.py` `_start_multiplex` iterates
  `profile_homes` and wraps each tick in `set_hermes_home_override(str(home))`
  plus `use_cron_store(home)` on both the startup pass and each tick. The
  served set is `profiles_to_serve(multiplex=True)`.
  Source: https://github.com/NousResearch/hermes-agent/blob/v2026.8.31/cron/scheduler_provider.py
  (`InProcessCronScheduler._start_multiplex`).
- **P7. Turning multiplexing on changes how the DEFAULT profile resolves
  credentials.** VERIFIED from source, and NOT in the original brief.
  `gateway/run.py` at `GatewayRunner.__init__`: "When multiplex_profiles is on,
  load under the default profile secret scope so bot tokens in that profile's
  .env resolve the same way secondary profiles do". `gateway/config.py`
  `_getenv` reads ONLY the scope when one is installed
  (`gateway/config.py`), the scope is built from `<home>/.env` alone
  (`agent/secret_scope.py`), and `API_SERVER_KEY` is deliberately excluded
  from the globals that keep reading `os.environ` (`agent/secret_scope.py`
  list, whose comment says "API_SERVER_KEY is deliberately NOT here"). This is
  what R4 exists for.
  Source: https://github.com/NousResearch/hermes-agent/blob/v2026.8.31/gateway/run.py (`GatewayRunner.__init__`), plus
  https://github.com/NousResearch/hermes-agent/blob/v2026.8.31/gateway/config.py (`_getenv`) and
  https://github.com/NousResearch/hermes-agent/blob/v2026.8.31/agent/secret_scope.py (`build_profile_secret_scope`,
  `_GLOBAL_ENV_EXACT`).
- **P8. Hermes Desktop connects to the dashboard on 9119, not the API server
  on 8642.** VERIFIED two ways. Upstream: "'Remote backend' means a
  `hermes serve` server running on the remote machine ... that is the process
  the desktop app connects to", with "Remote URL: `http://<backend-host>:9119`"
  (`website/docs/user-guide/desktop.md`). Repo: "hermes-gateway: the Hermes
  dashboard, which is what Hermes Desktop connects to. Not the
  OpenAI-compatible API server on 8642; Desktop does not speak it"
  (`deployments/infrastructure/services/haproxy.hcl:209`).
- **P9. No per-profile authorization exists on the dashboard at the pinned
  tag.** VERIFIED from source. `hermes_cli/web_routers/profiles.py` at
  `v2026.8.31` declares `@router.get("/api/profiles")`,
  `@router.delete("/api/profiles/{name}")`, `.../soul`, `.../model` and
  siblings with NO principal or identity parameter on any handler. The
  self-hosted OIDC plugin maps `sub`, `email` and `groups` onto a display
  Session and performs no authorization
  (`plugins/dashboard_auth/self_hosted/__init__.py`); its only allowlist is
  for redirect URIs, in `_validate_redirect_uri`. Live: `/api/status` returns 200 unauthenticated
  with `"auth_required":true,"auth_providers":["self-hosted"]`, while
  `/api/profiles` returns 401. Probed both directions, so authentication is
  binary and there is no third state.
  Source: https://github.com/NousResearch/hermes-agent/blob/v2026.8.31/hermes_cli/web_routers/profiles.py, plus
  https://github.com/NousResearch/hermes-agent/blob/v2026.8.31/plugins/dashboard_auth/self_hosted/__init__.py.
- **P10. A second isolated dashboard is possible but not supported by the
  image as it stands.** VERIFIED. `--isolated` exists at the pinned tag
  (`hermes_cli/subcommands/dashboard.py`). The image ships exactly one
  dashboard s6 slot (`docker/s6-rc.d/dashboard/run`), which hardcodes
  `cd /opt/data` and passes no profile. Upstream records the hazard of two
  processes on one HERMES_HOME: they "both race to `flock()` the same
  `logs/gateways/<profile>/lock` files, producing 'Resource busy' failures and
  an s6-log restart storm" (`hermes_cli/container_boot.py`).
  Source: https://github.com/NousResearch/hermes-agent/blob/v2026.8.31/hermes_cli/subcommands/dashboard.py, plus
  https://github.com/NousResearch/hermes-agent/blob/v2026.8.31/docker/s6-rc.d/dashboard/run and
  https://github.com/NousResearch/hermes-agent/blob/v2026.8.31/hermes_cli/container_boot.py (`_is_dashboard_container`).
- **P11. Per-profile credential isolation is fail-closed and never unions into
  `os.environ`.** VERIFIED from source. `agent/secret_scope.py` states the
  module "cannot union them into the process-global `os.environ`", and
  `get_secret` RAISES `UnscopedSecretError` on an unscoped read while
  multiplexing is active (`agent/secret_scope.py`).
  Source: https://github.com/NousResearch/hermes-agent/blob/v2026.8.31/agent/secret_scope.py (module docstring,
  `UnscopedSecretError`, `get_secret`).
- **P12. The bundled OpenViking memory provider bypasses that scope.**
  VERIFIED from source, and this falsifies the naive isolation assumption.
  `plugins/memory/openviking/__init__.py` defines
  `_env_value(name) -> os.environ[name] ...` and resolves endpoint, api_key,
  account and user through it in `_resolve_connection_settings`. It imports
  nothing from
  `agent.secret_scope`. Its own comment records that `api_key` "is sourced
  from the environment (synced from .env), never from config.yaml", and env
  outranks the config.yaml fallback in `_first_nonempty`.
  Source: https://github.com/NousResearch/hermes-agent/blob/v2026.8.31/plugins/memory/openviking/__init__.py
  (`_env_value`, `_resolve_connection_settings`). This is Q2.
- **P13. Subprocess env passthrough IS correctly scoped.** VERIFIED from
  source: `tools/env_passthrough.py` resolves forwarded values through
  `agent.secret_scope.get_secret` with the multiplex fail-closed path
  (`tools/env_passthrough.py`, the forwarded-value resolver). Cited because it is the contrast
  that makes P12 a split-brain rather than a uniform gap.
- **P14. `GATEWAY_MULTIPLEX_PROFILES` is an env-level alternative to the
  config key.** VERIFIED from source: `gateway/config.py` implements the
  three-tier chain "env > config.yaml > default False", and its comment says
  hosted deployments "stamp it on the container". NOT recommended here: the
  repo's own convention puts profile-shaped settings in the rendered
  `config.yaml`, and a blank value silently falls through to config.
- **P15. `scripts/check_openviking_config.py` needs no change for a second
  identity role.** VERIFIED: it asserts `server.oidc.audience` against the
  literal `openviking` and enumerates no roles. The new role reuses
  `local.openviking_audience` (`deployments/infrastructure/oidc.tf:167`), so
  both sides still match.
- **P16. The cluster is reachable from the dev container for read-only
  probes, but the Nomad API is not.** MIXED, measured:

  ```
  $ curl -s http://192.168.2.50:8642/health
  {"status": "ok", "platform": "hermes-agent", "version": "0.21.0"}

  $ curl -s -o /dev/null -w '%{http_code}' http://192.168.2.50:9119/api/status
  200

  $ NOMAD_ADDR=http://192.168.2.30:4646 nomad job status hermes
  Error querying job: Unexpected response code: 403 (Permission denied)
  ```

  So no probe in this ticket may depend on the Nomad API.
- **P17. `veerle` as a profile name does not collide with anything on disk.**
  UNCERTAIN. `/opt/data/profiles/` was not read directly (no shell on the
  container, and `du` on the host volume was permission-denied, see Q4). The
  404 on `/p/veerle/v1/models` is consistent with "no such profile" but does
  not prove the directory is absent, since multiplexing is off today and that
  route would 404 either way. Confirm on the node before subticket 3.
