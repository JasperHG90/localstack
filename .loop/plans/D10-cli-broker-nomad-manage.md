---
epic = "cli"
priority = 30
summary = """
`localstack status`/`service`/`monitor` 403 on Nomad list-jobs/node:read
because broker.py only brokers `nomad/creds/deploy`. D4 already decided
(2026-07-31) the CLI should also broker `nomad/creds/manage`; this ticket
implements that decided-but-unshipped follow-up to D2.
"""
---

# Ticket: D10-cli-broker-nomad-manage

## 1. Title

Broker `nomad/creds/manage` alongside `nomad/creds/deploy` so `localstack
status`/`service`/`monitor` can read Nomad job/node state without 403ing.

## 2. Size / Effort

M. Touches one small credential-shape change (`Session` gains a field,
`SCHEMA_VERSION` bumps) that ripples through every command and test that
constructs or serializes a `Session` — the individual edits are each small,
but the count of touched call sites (7 product files, 6+ test files) is what
pushes this past S.

## 3. Triggered by

Bug report: `localstack status` prints `nodes | ERROR | nomad: denied. The
token lacks node:read.` Root cause confirmed by reading
`cli/src/localstack_cli/auth/broker.py:25` and
`deployments/infrastructure/nomad_deploy_role.tf:1-5,21-49`: the CLI only
ever brokers the `deploy` Nomad ACL policy, which explicitly excludes
`list-jobs`, `node:read`, and all node/agent/operator access.

## 4. Context

- `cli/src/localstack_cli/auth/broker.py:25` — `NOMAD_CREDS_PATH =
  "nomad/creds/deploy"` is the only Nomad creds path the broker reads.
  `_FIELDS` (`broker.py:31-34`) maps exactly two services, `nomad` (deploy)
  and `consul` (deploy).
- `deployments/infrastructure/nomad_deploy_role.tf:1-5,21-49` — the `deploy`
  Nomad ACL policy grants `submit-job`, `read-job`,
  `host-volume-{create,register,read,write,delete}` and
  `host_volume "*" { mount-readwrite }`, and its own comment says so
  explicitly: "no alloc-node-exec, no list-jobs / dispatch-job / read-logs /
  read-fs, and no node / agent / operator access." Scoped for Terraform's
  job submission, not cluster reads.
- `deployments/infrastructure/nomad_oidc.tf:74-79` —
  `resource "vault_nomad_secret_role" "manage"` (`role = "manage"`, `type =
  "management"`) mints a Nomad management-type token: full Nomad ACL bypass,
  not scoped to any policy.
- `deployments/infrastructure/developer_group.tf:120-146` — the `developer`
  Vault policy already grants `read` on both `nomad/creds/deploy` (:123-125)
  and `nomad/creds/manage` (:140-142, "since G2, manage"). No Vault policy
  or Terraform change is needed; the grant is live today.
- **This was already decided, not a fresh design question.**
  `.loop/archive/D4-cli-cluster-tui/plan.md:601-613,752-771` (Q2, resolved
  2026-07-31): the operator explicitly rejected a narrow
  `nomad_read_role.tf` (option b) and decided **D2 should broker
  `nomad/creds/manage`**, accepting "a management token is full Nomad
  access, not read-only. Brokering it to a read-only [CLI path] is a
  privilege widening the operator accepted." That decision was "relayed to
  D2 ... a small but real follow-up to its `broker.py` (a new creds path)."
  D2 (`D2-cli-login-broker-tokens`) is `done`
  (`.loop/ledger.json:1005-1038`, commit `26cbbb9`) but never picked this
  up — `broker.py` still only reads `deploy`.
- The shipped code already assumes the follow-up landed:
  `cli/src/localstack_cli/commands/_session.py:28-29` — `GRANTED_BY` maps
  `nomad.LIST_JOBS` and `nomad.NODE_READ` to `"brokering \`nomad/creds/manage\`
  (D2)"`. `.loop/archive/D3-cli-read-commands/eval.md:72` still cites the
  superseded `nomad_read_role.tf` language from before the D4 decision; the
  live decision is the `manage` role, not a new ACL policy.
- **Same bug, one more command, found by this investigation.**
  `cli/src/localstack_cli/commands/monitor.py:44` (`localstack monitor`, the
  D4 TUI) also reads `session.credential("nomad")` and feeds it to
  `nomad.list_nodes`/`nomad.job_statuses`
  (`cli/src/localstack_cli/tui/monitor.py:55,57`) — the identical 403 the
  bug report names for `status`, just not yet reported. In scope here: same
  root cause, same one-line fix shape.
- `cli/src/localstack_cli/commands/secret.py:39-54` reads Nomad only via
  `nomad.job_templates` → `get_job` (`READ_JOB`), which `deploy` already
  grants (`nomad_deploy_role.tf:29`). Not affected by this bug and out of
  scope.
- `cli/src/localstack_cli/commands/env.py:32-46` exports `NOMAD_TOKEN` (the
  session's `nomad`/deploy credential) into the shell for
  `eval "$(localstack env)"`. `deployments/infrastructure/providers.tf:26`
  (`provider "nomad" {}`, the default provider every `nomad_job`/
  `nomad_dynamic_host_volume` resource uses) reads `NOMAD_TOKEN` from the
  environment, per the standard Nomad Terraform provider auth contract. This
  is the "write/deploy-adjacent path" the ticket brief asked to check for:
  `deploy` is still needed, unchanged, for `terraform apply`.

## 5. Non-goals / out of scope

- No `deployments/**` or `bootstrap/**` change. The `manage` Vault role and
  the `developer` policy grant already exist live (`nomad_oidc.tf:74-79`,
  `developer_group.tf:140-142`).
- No narrow `nomad_read_role.tf` ACL policy. D4 already rejected this option
  (`.loop/archive/D4-cli-cluster-tui/plan.md:609`); do not re-litigate it.
- Do not export the `manage` credential through `localstack env` or widen
  `localstack token`'s `SERVICES` tuple (`cli/src/localstack_cli/commands/
  token.py:26`) to include it. Containing the management token to the CLI's
  own internal HTTP calls — never the developer's shell, never an external
  tool like `terraform apply` — is the entire reason two Nomad credentials
  exist instead of a single swap; widening the shell export is a materially
  bigger blast-radius decision (every command run in that shell would get
  full Nomad admin, not just the CLI's own reads) that was never decided by
  D4 and is not part of this fix.
- Do not surface the new credential in `whoami`
  (`cli/src/localstack_cli/commands/whoami.py:38,62`) or `config`
  (`cli/src/localstack_cli/commands/config.py:56,76`). Those are purely informational
  displays; leaving them as-is keeps the diff surgical and their existing
  tests (`test_auth_commands.py:323`) pass unchanged. See Open Questions for
  the one exception (`logout`'s revocation-safety-net) this ticket does
  make.
- `secret.py` and `vault.py` (`localstack vault grants`) are untouched: they
  need no Nomad list/node capability today.

## 6. Requirements & restrictions

- Brokering must add `nomad/creds/manage` as a new named credential without
  removing or repointing `nomad/creds/deploy`, because `env.py` still needs
  `deploy` for shell export (§4, `env.py:32-46` + `providers.tf:26`). This is
  the "two Nomad credentials, one per grant" shape, not a path swap.
- The internal CLI reads that need `list-jobs`/`node:read` — `status`
  (`cli/src/localstack_cli/commands/status.py:34,40`), `service`
  (`cli/src/localstack_cli/commands/service.py:41`), and `monitor`
  (`cli/src/localstack_cli/commands/monitor.py:44`) — must use the `manage`
  credential. Per `cli/src/localstack_cli/commands/_session.py:28-29`'s own
  `GRANTED_BY` map, this is the
  already-decided fix.
- `secret.py` must keep using the `deploy` credential (§4): no reason to
  widen it, and `_session.py:28-29`'s map does not list `NOMAD.READ_JOB` as
  needing `manage`.
- A session cached before this change carries no `manage` credential.
  `cli/src/localstack_cli/auth/session.py:20,180-185` already has a `SCHEMA_VERSION` gate exactly
  for this: `load()` refuses a mismatched version with "Run `localstack
  logout` and log in again." Bump `SCHEMA_VERSION` so an old session file is
  refused cleanly rather than silently missing the new credential.
- `broker.py`'s `_denied_message` (`broker.py:41-48`) says "the two creds
  paths" — accurate today (2 Nomad+Consul paths read), false once a third
  is added. Update the wording so a 403 message stays true.
- `ensure_fresh` (`broker.py:115-167`) must refresh the new credential on
  the same skew-based cadence as `nomad`/`consul` (`broker.py:150-157`), not
  on a separate policy — nothing in the decision record asks for one.
- `logout`'s revocation fallback (`cli/src/localstack_cli/commands/logout.py:56-66`) must report
  the new credential's accessor when the Vault-token revoke itself fails,
  matching the existing per-credential accessor list. `login.py:135-137`'s
  own comment ("Ten such orphans were found on this cluster while
  implementing D2") is this repo's stated priority for exactly this failure
  class, now on a full-admin token instead of a scoped one.
- Every `Session(...)` construction in `cli/src/localstack_cli` and
  `cli/tests` uses keyword arguments (verified: `grep -rn "Session(" cli/src
  cli/tests`), so adding a field is additive and does not require touching
  every call site — only the ones a test or code path asserts on.

## 7. Code surface

Product code:

- `cli/src/localstack_cli/auth/broker.py:25-34` — add
  `NOMAD_MANAGE_CREDS_PATH = "nomad/creds/manage"`; add a `"nomad_manage"`
  row to `_FIELDS` (same `secret_id`/`accessor_id` field names as `nomad`,
  since both roles live on the same `nomad` secrets engine backend — see P1).
- `cli/src/localstack_cli/auth/broker.py:41-48` — update `_denied_message`'s
  "the two creds paths" wording (now three Nomad+Consul paths).
- `cli/src/localstack_cli/auth/broker.py:150-166` — `ensure_fresh`'s
  `for service in ("nomad", "consul")` loop and the `replace(...)` call add
  `"nomad_manage"`.
- `cli/src/localstack_cli/auth/session.py:20` — `SCHEMA_VERSION = 1` → `2`.
- `cli/src/localstack_cli/auth/session.py:60-74` — `Session` dataclass:
  add `nomad_manage: Credential | None = None`; `credential()` dict adds
  `"nomad_manage": self.nomad_manage`.
- `cli/src/localstack_cli/auth/session.py:131-142` — `save()`'s JSON body
  adds `"nomad_manage": _encode(session.nomad_manage)`.
- `cli/src/localstack_cli/auth/session.py:191-199` — `load()`'s returned
  `Session` adds `nomad_manage=_decode(data.get("nomad_manage"),
  "nomad_manage")`.
- `cli/src/localstack_cli/commands/login.py:108-115` — `Session(...)` adds
  `nomad_manage=broker("nomad_manage", addr, vault_credential.token)`.
- `cli/src/localstack_cli/commands/status.py:34` — `session.credential
  ("nomad")` → `session.credential("nomad_manage")`.
- `cli/src/localstack_cli/commands/service.py:41` — same swap.
- `cli/src/localstack_cli/commands/monitor.py:44` — same swap.
- `cli/src/localstack_cli/commands/logout.py:63` — `for name in ("vault",
  "nomad", "consul")` → `("vault", "nomad", "nomad_manage", "consul")`.

Test code:

- `cli/tests/fixtures/cluster.py:53-86` — add a `NOMAD_MANAGE_CREDS` dict
  (distinct token/accessor values, e.g. `nomad-manage-secret-id` /
  `nomad-manage-accessor-id`) and a `"/v1/nomad/creds/manage"` route in
  `HEALTHY_ROUTES`. Required: every test that invokes `login` against
  `cluster_addr`/`FakeCluster` brokers all Nomad+Consul creds eagerly
  (`login.py:113-115`), so a missing route here breaks the entire
  login/logout/env/whoami/config/token test suite, not just new assertions.
- `cli/tests/auth/test_broker.py:20-43` — `session_at()` helper adds a
  `nomad_manage` `Credential`; extend with a `nomad_manage_minutes` param
  mirroring `nomad_minutes`/`consul_minutes`.
- `cli/tests/auth/test_session.py:36-51` — `a_session()` adds a
  `nomad_manage=credential(...)` entry.
- `cli/tests/commands/test_auth_commands.py:27-46` — `logged_in` fixture's
  `Session(...)` adds `nomad_manage=Credential("nomad-manage-tok",
  "nomad-manage-acc", now + timedelta(minutes=25), True)`.
- `cli/tests/commands/test_monitor_command.py:88-90` — `_FakeSession
  .credential` stub's `service == "nomad"` check → `service ==
  "nomad_manage"`, matching `monitor.py`'s swap.
- `cli/tests/commands/test_read_commands.py:38-56` — add the three new
  tests listed in §8 (`test_status_uses_the_manage_credential_for_nodes_and_jobs`,
  `test_service_uses_the_manage_credential_for_job_statuses`,
  `test_secret_still_uses_the_deploy_credential`); no stub change needed,
  the existing generic `_Session.credential` stub already returns a
  per-service token by name.

## 8. Tests & validation gates

Definition of Done: `.loop/evals/D10-cli-broker-nomad-manage.md`.

Gates (from `.loop/config.json` `gates`, `justfile:18-19`,
`.pre-commit-config.yaml:33-72`): `just pre_commit` — runs `ruff check`,
`ruff format --check`, `mypy --strict` (`cli/pyproject.toml`), and `pytest
cli/tests`, all scoped to `^cli/`. Per `.claude/rules/python-testing.md`,
also run `uv run --project cli pytest cli/tests` directly during
development. No CI; these are local-only gates.

Reproducing test first (the bug): a test asserting that `status`/`service`
under a `nomad_manage`-mapped 403 on `/v1/jobs/statuses` or `/v1/nodes`
fails with "lacks list-jobs"/"lacks node:read" today would pass BEFORE this
fix reaches the manage credential — the true regression test is that these
calls now receive the `manage` token and succeed. Add to
`cli/tests/commands/test_read_commands.py` (which already exercises
`status`/`service` over `respx`, `test_read_commands.py:38-56`'s generic
`_Session.credential` stub returns a per-service token by name, so no stub
change needed there):

- `test_status_uses_the_manage_credential_for_nodes_and_jobs` — assert the
  `/v1/nodes` and `/v1/jobs/statuses` respx routes see
  `"a-nomad_manage-token"` (the stub's naming convention), not
  `"a-nomad-token"`.
- `test_service_uses_the_manage_credential_for_job_statuses` — same
  assertion against `service`'s `job_statuses` call.
- `test_secret_still_uses_the_deploy_credential` — assert `secret`'s
  `get_job` call sees `"a-nomad-token"`, unchanged (regression guard against
  over-widening).

Add to `cli/tests/auth/test_broker.py` (mirrors the existing `deploy`
coverage, per §7's `session_at()` extension):

- `test_manage_creds_broker_from_the_manage_path` — mirrors
  `test_the_two_engines_use_different_field_names`: `broker("nomad_manage",
  ...)` reads `/v1/nomad/creds/manage` and maps `secret_id`/`accessor_id`.
- `test_a_403_on_manage_names_the_manage_path` — mirrors
  `test_a_403_names_the_path_the_policies_and_the_ticket` for
  `nomad/creds/manage`.
- `test_ensure_fresh_rebrokers_manage_independently` — mirrors
  `test_ensure_fresh_rebrokers_only_the_stale_one`, staleness on
  `nomad_manage` alone.

Add to `cli/tests/auth/test_session.py`:

- Extend `test_round_trip_preserves_every_field` (uses the updated
  `a_session()`, no new test needed, just verify it still passes with the
  new field).
- Extend `test_credential_lookup_by_service_name`
  (`test_session.py:160-165`) with `assert session.credential
  ("nomad_manage") is session.nomad_manage`.

Add to `cli/tests/commands/test_auth_commands.py`:

- Extend `test_login_writes_the_session_and_the_token_file`
  (`:243-252`) with `assert session.nomad_manage is not None and
  session.nomad_manage.token == "nomad-manage-secret-id"`.
- Extend `test_login_brokers_eagerly` (`:255-260`) with `assert
  len(cluster.requests_for("/v1/nomad/creds/manage")) == 1`.
- Extend `test_logout_prints_the_accessors_when_revocation_fails`
  (`:210-216`) with `and "nomad-manage-acc" in stderr`.

## 9. Risk assessment

- **Blast radius:** CLI-local. No Terraform, no Vault policy, no Nomad ACL
  change — the grant already exists live. Worst case on a bad rollout: an
  installed CLI 403s on `status`/`service`/`monitor` exactly as it does
  today (no regression below current behavior) or, if the field mapping is
  wrong (P1, unverified), a `BrokerError` naming the response-shape mismatch
  (`broker.py:79-82`) — a legible failure, not a silent one.
- **Reversibility:** Fully reversible; a single-file revert of `broker.py`
  and `session.py` returns to today's (broken) behavior. `SCHEMA_VERSION`'s
  bump means a rollback after users have re-logged-in forces one more
  `localstack logout && localstack login` cycle — a known, already-designed
  recovery path (`session.py:180-185`'s own message).
- **Widened privilege:** brokering a Nomad **management**-type token (full
  ACL bypass, not scoped) to the developer's session is a real widening,
  already accepted by the operator for this exact purpose in D4's decision
  record (§4). This ticket does not re-open that trade-off; it ships it.
  The one thing that would make the widening worse — exporting it to the
  shell/`terraform apply` — is explicitly excluded (§5).
- **Likeliest failure mode:** the `nomad/creds/manage` response shape
  differs from `nomad/creds/deploy`'s (P1, unverified against the live
  cluster from this environment). `broker.py`'s existing shape-mismatch
  error (`broker.py:79-82`) already turns that into a clear message, not a
  crash, so the failure is caught at `localstack login` time.
- **Test-suite breadth:** the `Session` schema change touches the shared
  `FakeCluster` fixture every auth/command test depends on (§7); the
  highest-leverage single edit is `cli/tests/fixtures/cluster.py`'s
  `HEALTHY_ROUTES` — missing it fails most of `test_auth_commands.py` and
  `test_token_command.py`, not just this ticket's new assertions.

## 10. Subtickets

Single-PR change; no split needed. Suggested internal sequence for the
implementer (not separate plan files):

1. `cli/src/localstack_cli/auth/session.py` — schema field + version bump + encode/decode.
2. `cli/src/localstack_cli/auth/broker.py` — `_FIELDS` row, `_denied_message` wording,
   `ensure_fresh` loop.
3. `cli/tests/fixtures/cluster.py` — `HEALTHY_ROUTES` route (unblocks every
   other test file).
4. `cli/src/localstack_cli/commands/login.py` — broker the new credential at login.
5. `cli/src/localstack_cli/commands/status.py`, `service.py`, `monitor.py` — swap to
   `nomad_manage`.
6. `cli/src/localstack_cli/commands/logout.py` — accessor fallback.
7. Test updates and new tests per §8.

## 11. Open questions

- **Q1 — does `logout`'s accessor fallback list need `nomad_manage`, or is
  that expanding scope beyond the reported bug?** *Recommendation:*
  include it (as scoped in §6/§7). It is a one-line, directly-caused
  consequence of adding a new credential (not a pre-existing issue), and
  the repo has already treated exactly this failure class — an orphaned
  brokered token with no accessor surfaced to revoke manually — as a real
  problem worth a standing code comment (`login.py:135-137`). The
  alternative (leave `logout` silent about `nomad_manage`) means a failed
  Vault-token revoke leaves a full Nomad **management** token's accessor
  unreported to the developer, which is a materially worse instance of a
  bug this repo already fixed once for scoped tokens.
- **Q2 — should `whoami`/`config` also learn about `nomad_manage`?**
  *Recommendation:* no (as scoped in §5). They are purely informational;
  omitting the internal-only credential from them keeps their existing
  fixed-tuple tests (`test_auth_commands.py:323`) unchanged and matches
  treating `nomad_manage` as an implementation detail of `status`/`service`/
  `monitor`, never a user-facing credential (consistent with never exporting
  it via `env`/`token`, §5). If the operator wants full session-introspection
  parity instead, that is a small follow-up, not a blocker to this fix.

## Premises / assumptions

- **P1. UNCERTAIN** — `nomad/creds/manage`'s Vault response carries the same
  `data.secret_id`/`data.accessor_id` field names as `nomad/creds/deploy`'s.
  Both are `vault_nomad_secret_role` resources on the same `nomad` secrets
  engine backend (`nomad_oidc.tf:74-79`, `nomad_deploy_role.tf:56-61`), and
  the Nomad secrets engine's `creds/<role>` response shape is documented to
  be uniform across role types — but this specific path was never probed
  live (the only measured shape in this repo,
  `broker.py:1-11`/`cli/tests/fixtures/cluster.py:50-58`, is `deploy`'s, dated
  2026-08-02). Not independently probed here: no live-cluster access from
  this planning environment. Mitigations already in place if wrong: (a)
  `broker.py:79-82` raises a named `BrokerError` on a shape mismatch rather
  than silently returning an empty token; (b) `cli/tests/auth/
  test_live_login.py` is this repo's own established live-cluster
  verification path (`pytest -m cluster`, excluded from the default run,
  `cli/pyproject.toml`'s `addopts`) — extend it with a `nomad_manage`
  assertion mirroring `test_the_brokered_tokens_are_real` (checks `nomad
  acl token self` returns `management`, not `client`) as part of this
  ticket's implementation, before relying on the mocked-fixture tests alone.
- **P2.** `deploy`'s role grants `submit-job`, `read-job`, `host-volume-*`
  and no `list-jobs`/`node:read`. `anchor:`
  `deployments/infrastructure/nomad_deploy_role.tf:21-49` (read directly).
- **P3.** `manage`'s role mints a Nomad management-type token (full ACL
  bypass). `anchor:` `deployments/infrastructure/nomad_oidc.tf:74-79`,
  `type = "management"` (read directly).
- **P4.** The `developer` Vault policy already grants read on both
  `nomad/creds/deploy` and `nomad/creds/manage`; no Terraform/Vault change
  needed. `anchor:` `deployments/infrastructure/developer_group.tf:120-146`
  (read directly).
- **P5.** D2 (`D2-cli-login-broker-tokens`) and D3 (`D3-cli-read-commands`)
  are both `stage: done` in the ledger, and D3's shipped code
  (`cli/src/localstack_cli/commands/_session.py:28-29`) already documents the `manage` grant as the
  intended fix for `LIST_JOBS`/`NODE_READ` denials. `anchor:`
  `.loop/ledger.json:1005-1070` (read directly).
- **P6.** Every `Session(...)` construction site in `cli/src` and
  `cli/tests` uses keyword arguments. `probe:` `grep -rn "Session(" cli/src
  cli/tests` — 15 matches; 2 are `_FakeSession()`/`_Session()` test doubles
  (`cli/tests/commands/test_monitor_command.py:65`,
  `cli/tests/commands/test_read_commands.py:52`), not the real class. The
  remaining 13 real `Session(...)` construction sites were each read
  directly and all use keyword arguments, none positional (see §6). Adding a
  field with a `None` default is additive, not breaking, at every site not
  explicitly listed in §7.
- **P7.** Repo gates are `just pre_commit` (`.loop/config.json` `gates`),
  running ruff/ruff-format/mypy-strict/pytest scoped to `^cli/`. `anchor:`
  `justfile:16-19`, `.pre-commit-config.yaml:33-72` (read directly). No CI;
  gates are local-only.
- **P8.** `env.py` exports the `deploy`-scoped `nomad` credential as
  `NOMAD_TOKEN`, and Terraform's default `nomad` provider
  (`deployments/infrastructure/providers.tf:26`) reads `NOMAD_TOKEN` from
  the environment absent an explicit `secret_id`. `anchor:`
  `cli/src/localstack_cli/commands/env.py:32-46`,
  `deployments/infrastructure/providers.tf:26` (both read directly); the
  provider's env-var fallback is the standard Terraform Nomad provider
  auth contract, not independently probed against a live `terraform plan`
  in this planning pass.
