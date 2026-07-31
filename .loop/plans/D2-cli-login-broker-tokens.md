---
epic = "cli"
depends_on = ["D1-cli-package-skeleton", "F2-foundation-vault-oidc-provider"]
priority = 46
tags = ["cli", "vault", "nomad", "consul", "auth"]
summary = "Add `localstack login|logout|whoami|env`: authenticate a developer to Vault with userpass, broker short-lived Nomad and Consul tokens from that session, cache them at 0600, and expose them to terraform and the hashi CLIs without any static god-mode token."
---

# D2 — `localstack login`: Vault session, brokered Nomad and Consul tokens

## 1. Title

Add the auth half of the `localstack` CLI: `login` (Vault `userpass`),
`logout`, `whoami`, and `env`, so a developer holds a short-lived Vault
session that brokers short-lived Nomad and Consul tokens on demand, and
no static god-mode token is needed to deploy.

## 2. Size / Effort

**L.** Four commands, but the weight is elsewhere: a credential cache
with per-credential expiry, three different lease models in one session
(Vault token, Nomad lease, Consul lease), a revoke-on-logout path that
must not leave live tokens behind, and an offline test suite that never
touches the cluster by default. The command surface must also admit a
future `--method oidc` without changing shape.

## 3. Triggered by

Operator request: a developer should authenticate once and deploy, the
way `gcloud auth login` works, instead of copying a Vault root token and
two static god-mode tokens into `.devcontainer/.env`
(`.devcontainer/.env.example:2,6,10`). This is the client half of
`F7-foundation-deployer-vault-oidc-login`, which is `blocked` on a broken
premise. D2 builds the client. F7 keeps the policy.

## 4. Context

### What a developer holds today

Static, long-lived, god-mode:

- `VAULT_TOKEN` is the bootstrap root token. Verified live:
  `vault token lookup` reports `policies: ["root"]`, `ttl: 0`,
  `entity_id: ""`, `path: auth/token/root`. Source is
  `/opt/vault/init.json`, read at
  `bootstrap/roles/nomad_server/tasks/main.yml:189-196` and reused as
  `VAULT_TOKEN` at `:202,211,224,241`.
- `NOMAD_TOKEN` and `CONSUL_TOKEN` are the bootstrap management tokens,
  exported from `.devcontainer/.env` (gitignored, `.gitignore:2`).
- Addresses, verified in this shell: `VAULT_ADDR=http://192.168.2.30:8200`,
  `NOMAD_ADDR=http://192.168.2.30:4646`,
  `CONSUL_HTTP_ADDR=http://192.168.2.30:8500`.

### What already exists to broker from

F5 and F6 are `done` (`.loop/ledger.json`) and their roles are live.
Verified today:

- `vault list nomad/role` returns `deploy`; `vault read nomad/role/deploy`
  returns `type: client`, `policies: ["deploy"]`
  (`deployments/infrastructure/nomad_deploy_role.tf:36-41`).
  **A `client`-type Nomad token cannot perform ACL management.** That
  limit is what broke F8's premise
  (`.loop/verdicts/F8-foundation-deployer-provider-cutover.plan-validator.md`).
  The CLI must not promise otherwise.
- `vault list consul/roles` returns `deploy`; `vault read
  consul/roles/deploy` returns `ttl: 1800`, `max_ttl: 3600`,
  `token_type: client`, `consul_policies: ["deploy"]`
  (`deployments/infrastructure/consul_deploy_role.tf:19-25`).
- Nomad mount lease: `vault read nomad/config/lease` returns
  `ttl: 1800`, `max_ttl: 3600`, set at
  `bootstrap/roles/nomad_server/tasks/main.yml:309`.

So both brokered credentials die within 30 minutes and cannot be renewed
past 60. **Handling expiry is the substance of this ticket**, not a
detail at the end of it.

### What F2 ships, and what it does not

F2 is committed on branch `loop/F2-foundation-vault-oidc-provider`. It is
**not merged and not applied**. Verified live: `vault auth list` returns
only `jwt-nomad/` and `token/`. On that branch,
`deployments/infrastructure/auth_userpass.tf` creates:

- `vault_auth_backend "userpass"` at path `userpass` (`:13-17`).
- The user, written through the generic endpoint at
  `auth/userpass/users/${var.vault_operator_username}` (`:28-36`, default
  `operator` at `variables.tf:58`).
- `vault_identity_entity` and `vault_identity_entity_alias` (`:38-53`),
  so a login through this backend carries a non-empty `entity_id`. The
  root token's is empty, so nothing gated on identity can use it.
- The generated password lands in KV2 at `secret/default/vault/operator`
  (`secrets.tf:121-123` on that branch).

**The load-bearing gap: `token_policies = []`**
(`auth_userpass.tf:34`, deliberate, per the comment at `:24-27`). A
successful `userpass` login therefore yields a token carrying only the
`default` policy. Read live, `vault policy read default` grants
`auth/token/lookup-self`, `auth/token/renew-self`,
`auth/token/revoke-self`, `sys/leases/renew`, `sys/leases/lookup`,
`sys/capabilities-self`, and the entity self-read. It grants **no**
`nomad/creds/*`, **no** `consul/creds/*`, **no** KV2 read, and **no**
`sys/leases/revoke`.

Consequences the implementer must design around:

1. `login` will authenticate but every broker call returns 403 until a
   policy binds the operator entity to the creds paths. That policy is
   F7's deliverable, not D2's. The CLI must fail with a message naming
   the missing grant, not a bare traceback.
2. `logout` can still revoke cleanly: `auth/token/revoke-self` is in the
   `default` policy, and revoking a Vault token revokes the leases that
   token created. Per-lease revocation via `sys/leases/revoke` is not
   granted, so do not build logout on it.
3. The login token's TTL is server-side. F2 sets no `token_ttl`, and
   `vault read sys/config/state/sanitized` reports `default_lease_ttl: 0`
   (unset), so Vault's built-in 32-day default applies. D2 cannot lower
   it from the client. See Q6.

### The password bootstrap problem

The operator password lives at `secret/default/vault/operator`, and
reading KV2 needs a Vault token, which is what login produces. The CLI
cannot read the password it needs to log in. The operator retrieves it
once out of band with the root token, per the F2 branch doc
`docs/vault-human-auth.md` ("Logging in"). D2 prompts and never stores
it. See §6 R7.

### The `CONSUL_TOKEN` naming split

The Consul provider and every terraform recipe read
`CONSUL_HTTP_TOKEN`, while the developer shell exports `CONSUL_TOKEN`.
Every recipe bridges the two by hand:
`deployments/infrastructure/justfile:8,12,16`,
`deployments/applications/justfile:10,18,22,27,31`,
`docs/monitoring.md:153,175`. The checked-in template says
`CONSUL_HTTP_TOKEN` (`.devcontainer/.env.example:6`) while the real
gitignored file says `CONSUL_TOKEN` (`.devcontainer/.env:5`). Any CLI
that emits only one name breaks half the repo.

### Addresses at the edge

haproxy routes `vault.`, `nomad.`, and `consul.lab.orangecluster.nl` over
TLS (`deployments/infrastructure/services/haproxy.hcl:96,100-102,111-113,133,136,139`).
Probed today: both `https://vault.lab.orangecluster.nl/v1/sys/health` and
`https://nomad.lab.orangecluster.nl/v1/agent/health` return 200. The
Vault listener itself is plaintext:
`vault read sys/config/state/sanitized` reports
`listeners[0].config.tls_disable: true` on `0.0.0.0:8200`. **A password
sent to the current `VAULT_ADDR` crosses the wire in the clear.** See §6
R2.

### Python state of the repo

There is no `pyproject.toml` anywhere in the tracked tree, no packaged
Python, and no Python lint or type hook. `.pre-commit-config.yaml` runs
`check-ast` (`:7`) and `debug-statements` (`:11`) over Python, plus
generic and terraform hooks. `requirements.txt` lists `httpx` (`:3`) and
`hvac` (`:5`), but nothing installs it. `D1-cli-package-skeleton` owns
the package root, the CLI framework, and any ruff/mypy/pytest wiring. D2
consumes what D1 established. See Q1 and §8.

## 5. Non-goals / out of scope

- **Not the `deployer` Vault policy.** F7 owns it. Its verdict
  (`.loop/verdicts/F7-foundation-deployer-vault-oidc-login.plan-validator.md:36-73`)
  found the policy forbids the `sys/*` and `auth/*` writes its own
  `terraform apply` performs. D2 must not author, widen, or work around
  that policy. A diff touching `deployments/` is out of scope here.
- **Not OIDC login.** Operator decision, already made: authenticate
  against the `userpass` backend F2 ships. Reserve `--method` in the
  interface so OIDC can be added later without an interface change. Do
  not build a callback listener, a Google OAuth client, or a Vault OIDC
  auth mount.
- **Not the read commands (D3) or the TUI (D4).** They consume these
  tokens. D2 does not anticipate their needs.
- **Not the provider cutover (F8).** D2 does not edit `providers.tf`, any
  `justfile`, or `.devcontainer/.env.example`. Removing the static tokens
  is F8's story.
- **Not `localstack exec`.** See Q3; `env` is the chosen surface.
- **Not applying or merging F2.** D2 cannot be verified end to end until
  someone applies F2. State that plainly rather than faking a green run.
- **Not multi-cluster profiles.** One cluster, one session. See Q5.
- **Not ACL management through the brokered Nomad token.** It is
  `type: client` (`nomad_deploy_role.tf:39`).

## 6. Requirements & restrictions

### Must achieve

**R1 — `localstack login`.** Prompts for the password, authenticates
against `POST /v1/auth/userpass/login/<username>`, then eagerly brokers
both child credentials (`GET /v1/nomad/creds/deploy`,
`GET /v1/consul/creds/deploy`) and writes one cache file. Eager brokering
is deliberate: it makes the missing-policy failure (§4, F2
`token_policies = []`) show up at login with a clear message instead of
inside a later `terraform apply`. Flags: `--username` (default
`operator`, or `$LOCALSTACK_VAULT_USERNAME`), `--method` (default
`userpass`; any other value exits non-zero with "unsupported method"),
`--vault-addr` (default `$VAULT_ADDR`).

**R2 — Refuse to send a password in the clear.** If the resolved Vault
address is `http://` and not loopback, exit non-zero and name the HTTPS
edge (`https://vault.lab.orangecluster.nl`, live per §4). `--insecure`
overrides, prints a warning to stderr, and is the only way past. Grounded
in `tls_disable: true` on the Vault listener and the current
`VAULT_ADDR=http://192.168.2.30:8200`.

**R3 — Cache shape.** One file,
`${XDG_CONFIG_HOME:-$HOME/.config}/localstack/session.json`, directory
mode `0700`, file mode `0600`, written to a temp file in the same
directory with mode set at creation and then renamed, so the token is
never briefly world-readable. Never inside the repo tree (loop worktrees
live under `.loop/worktrees/` and a stray path would not be gitignored).
Schema, one object per credential because their TTLs differ:

```json
{
  "version": 1,
  "method": "userpass",
  "vault_addr": "https://vault.lab.orangecluster.nl",
  "vault":  {"token": "", "entity_id": "", "policies": [],
             "expires_at": "ISO8601", "renewable": true},
  "nomad":  {"token": "", "accessor": "", "lease_id": "",
             "expires_at": "ISO8601", "renewable": true},
  "consul": {"token": "", "accessor": "", "lease_id": "",
             "expires_at": "ISO8601", "renewable": true}
}
```

One file, three entries: one atomic write, one thing to delete on logout,
no partial-state cleanup. `expires_at` is absolute, computed from the
response's `lease_duration` at receipt, so a clock read decides freshness
rather than a countdown the process does not own. `method` and `version`
exist so a later OIDC login writes the same file.

**R4 — Expiry policy: re-broker on demand, renew only the Vault token.**
Brokered leases cap at `max_ttl: 3600` (`consul_deploy_role.tf:24`,
`nomad/config/lease`), so renewal buys at most one extra window and then
fails anyway. Rules:

- Any command needing a Nomad or Consul token treats an entry as stale
  when `expires_at` is within a 5-minute skew, and re-brokers it.
- Renew the Vault token through `auth/token/renew-self` when it is within
  the skew and `renewable` is true (the `default` policy grants this).
  If renewal fails, exit non-zero with "session expired, run `localstack
  login`". Do not silently re-prompt for a password.
- Read `renewable` from each response rather than assuming it. Do not
  renew brokered leases. Re-broker them.
- Superseded leases are left to expire. Per-lease revocation needs
  `sys/leases/revoke`, which the `default` policy does not grant (§4).
  Say so in a code comment so the next reader does not "fix" it.

**R5 — `localstack env`.** Prints shell `export` lines to stdout for
`eval "$(localstack env)"`. Refreshes stale entries first (R4). Emits
`VAULT_TOKEN`, `NOMAD_TOKEN`, **and both** `CONSUL_HTTP_TOKEN` and
`CONSUL_TOKEN` set to the same brokered value, because the repo reads
both names (§4). Tokens only, no addresses: the addresses are already
exported and are not this command's to own. Every diagnostic goes to
stderr so stdout stays evaluable. `--format json` for machine callers.

**R6 — `localstack whoami` and `localstack logout`.**

- `whoami` reports: username, `entity_id`, Vault token policies, Vault
  TTL remaining, and per brokered credential the accessor, lease id, and
  TTL remaining. Never the token values. Exit non-zero when no session
  exists. `--format json`.
- `logout` calls `auth/token/revoke-self` first, then deletes the cache
  file. Revoking the Vault token revokes the leases it created, so the
  brokered Nomad and Consul tokens die with it. This is a real security
  property: deleting the file alone leaves live tokens on the cluster for
  up to an hour. If revocation fails, still delete the file, and print
  the un-revoked accessors to stderr with a non-zero exit so the operator
  can revoke them by hand.

**R7 — Password handling.** Prompt with `getpass` (no echo). Never write
it to the cache, a log line, an env var, or an error message. Do not add
a KV2 read path for it: reading `secret/default/vault/operator` needs a
token, which is what login produces (§4). Document the one-time
out-of-band retrieval instead.

**R8 — Errors name the cause.** A 403 on a creds path prints which path
was denied, that the login token's policies are `<policies from
lookup-self>`, and that the grant is F7's ticket. A 404 on
`auth/userpass/login/*` prints that the `userpass` backend is not enabled
and that F2 is unapplied. These two failures are the expected state of
the world at implementation time, so they are the messages that get used
most.

**R9 — Tokens never reach stdout by accident.** No token value in any
log line, exception message, or `--format json` output other than
`env`'s, which exists to emit them.

### Restrictions the repo states

- **Tests ship with the code** (`.claude/rules/python-testing.md:6`) and
  mirror the source tree (`:99-103` "Where tests live").
- **Live-cluster tests carry a marker and are excluded by default**
  through `addopts` in `pyproject.toml`
  (`.claude/rules/python-testing.md:26-32`). Every test that talks to
  Vault, Nomad, or Consul is marked. The default `uv run pytest` is
  offline.
- **Mock only at true external boundaries**
  (`.claude/rules/python-testing.md:77-89`); for `httpx`, use `respx`
  (`:89`). The cache is a real file under `tmp_path`, not a mock.
- **Redirect global state in tests** (`:63-75`): an autouse fixture sets
  `XDG_CONFIG_HOME` into `tmp_path`. No test may read or write the real
  `~/.config/localstack/`.
- **Dependencies land in `pyproject.toml` via `uv add`**
  (`.claude/rules/uv-installer.md`), never `uv pip`.
- **The user's pre-commit config is leading**
  (`.claude/rules/prek-code-quality.md`): do not invent lint or type
  hooks here. If D1 added them they run inside `just pre_commit`; if it
  did not, that is D1's gap to close, not D2's.
- **Pre-existing failures get fixed, not skipped**
  (`.claude/rules/pre-existing-issues.md`).
- **Plain language in code comments and docs**
  (`.claude/rules/plain-language.md`). Any markdown this ticket adds runs
  the slop scan (`.claude/rules/slop-scan-for-docs.md`).
- **Adversarial review before done**
  (`.claude/rules/adversarial-reviews.md`;
  `.loop/config.json` `require_review: true`).
- **Surgical changes** (`AGENTS.md` §3): nothing under `deployments/`,
  `bootstrap/`, or any `justfile` changes in this ticket.

## 7. Code surface

**Layout assumption.** `D1-cli-package-skeleton` owns the package root
and is not authored yet, so the paths below assume `cli/` with
`src/localstack_cli/` and `cli/tests/`. If D1 shipped a different root,
substitute it throughout. That substitution is part of this ticket, not
an out-of-scope change. Confirm before pickup (Q1).

New files:

- `cli/src/localstack_cli/auth/vault.py` — Vault HTTP calls:
  `login_userpass`, `lookup_self`, `renew_self`, `revoke_self`,
  `read_creds(path)`. One thin client, no framework. Reads `VAULT_ADDR`,
  applies R2's plaintext refusal.
- `cli/src/localstack_cli/auth/session.py` — the cache: schema `version`,
  atomic `0600` write, load, delete, `is_stale(entry, skew)`. Pure
  functions over a path so tests point it at `tmp_path`.
- `cli/src/localstack_cli/auth/broker.py` — `broker_nomad(session)` and
  `broker_consul(session)` over `nomad/creds/deploy` and
  `consul/creds/deploy`, plus `ensure_fresh(session)` implementing R4.
  **Response field names differ between the two engines** (the Nomad
  engine returns a secret id and accessor id, and the Consul engine returns
  a
  token and accessor). Verify both against one live read during
  implementation rather than assuming. The mapping into the cache schema
  lives here and nowhere else.
- `cli/src/localstack_cli/commands/auth.py` — `login`, `logout`,
  `whoami`, `env` wired into D1's CLI entry point.
- `cli/tests/auth/test_vault.py` — login, lookup, renew, revoke, and the
  R2 plaintext refusal, all against `respx`.
- `cli/tests/auth/test_session.py` — write/read round trip, file mode
  `0600` and directory mode `0700`, atomicity (no world-readable window),
  staleness at the skew boundary, corrupt-file handling.
- `cli/tests/auth/test_broker.py` — creds parsing for both engines,
  `ensure_fresh` re-brokers a stale entry and leaves a fresh one alone,
  a 403 raises the R8 message.
- `cli/tests/commands/test_auth_commands.py` — `env` emits all four
  variable names including both Consul spellings; `whoami` prints no
  token value; `logout` calls `revoke-self` before deleting and still
  deletes when revocation fails.
- `cli/tests/auth/test_live_login.py` — marked live-cluster tests
  (`@pytest.mark.integration` or D1's marker), excluded by default.
- `cli/tests/conftest.py` — autouse fixture redirecting `XDG_CONFIG_HOME`
  into `tmp_path`; a fixture building a session file.
- `docs/cli-login.md` — one page: how to get the password the first time,
  `localstack login`, `eval "$(localstack env)"`, what `logout` revokes,
  and the F2/F7 preconditions. Runs the slop scan.

Modified:

- `cli/pyproject.toml` (D1's file) — add `httpx` and dev `respx` via
  `uv add`; register the integration marker and the `addopts` exclusion
  if D1 did not.
- D1's CLI entry module — register the four subcommands. One line each.

Read-only anchors the implementer will open, and must not edit:
`deployments/infrastructure/nomad_deploy_role.tf:36-41`,
`deployments/infrastructure/consul_deploy_role.tf:19-25`,
`deployments/infrastructure/justfile:8,12,16`,
`.devcontainer/.env.example:2,6,10-11`,
`bootstrap/roles/nomad_server/tasks/main.yml:309`,
and, on branch `loop/F2-foundation-vault-oidc-provider`,
`deployments/infrastructure/auth_userpass.tf:13-53` and
`docs/vault-human-auth.md`.

## 8. Tests & validation gates

### Repo gates, discovered

- **Loop gate:** `just pre_commit` (`.loop/config.json:2-3`) runs
  `pre-commit run --all-files` (`justfile:18-19`). Hooks that touch
  Python: `check-ast` (`.pre-commit-config.yaml:7`) and
  `debug-statements` (`:11`). The config excludes `^\.(claude|loop)/`
  (`:1`). **There is no ruff, mypy, or pytest hook today.** Do not add
  one here (`.claude/rules/prek-code-quality.md`); it is D1's scope.
- **Test gate, run explicitly:** `uv run pytest` from the CLI root
  (`.claude/rules/python-testing.md:21`). Because no pytest hook exists,
  `just pre_commit` will not run it. The implementer runs it by hand and
  it must be green before done.
- **Marked live run:** `uv run pytest -m integration` (`:24`). Off by
  default via `addopts` (`:26-32`).
- **Review:** `.loop/config.json` `require_review: true`, plus
  `.claude/rules/adversarial-reviews.md`.
- **Docs:** `docs/cli-login.md` runs the slop scan
  (`.claude/rules/slop-scan-for-docs.md`).
- No CI workflow covers Python in this repo; `.github/` holds no Python
  job. The gates above are the whole set.

### Offline tests to add, and their homes

Each file below is listed in §7.

1. `test_vault.py::test_login_userpass_returns_token_and_entity` —
   respx-stubbed `auth/userpass/login/operator`, asserts token, policies,
   `entity_id`, and `lease_duration` mapped to an absolute `expires_at`.
2. `test_vault.py::test_plaintext_vault_addr_is_refused` — R2. An
   `http://` non-loopback address exits non-zero and names the HTTPS
   edge; `--insecure` proceeds.
3. `test_session.py::test_cache_file_is_0600_in_0700_dir` — R3. Asserts
   `stat().st_mode & 0o777`.
4. `test_session.py::test_write_is_atomic_and_never_world_readable` —
   R3. No intermediate path with looser mode survives the write.
5. `test_session.py::test_is_stale_at_skew_boundary` — parametrized
   around the 5-minute skew, including an already-expired entry.
6. `test_session.py::test_corrupt_cache_reports_and_does_not_crash`.
7. `test_broker.py::test_parses_nomad_and_consul_creds_responses` —
   parametrized over the two engines' differing field names.
8. `test_broker.py::test_ensure_fresh_rebrokers_only_stale_entries` — R4.
   Asserts the fresh entry's request was never made
   (`respx` route `.call_count == 0`, not a loose not-called assertion,
   per `.claude/rules/python-testing.md:44-48`).
9. `test_broker.py::test_403_on_creds_names_the_missing_grant` — R8.
   Asserts the message names the path and points at F7.
10. `test_auth_commands.py::test_env_emits_both_consul_variable_names` —
    R5. The single highest-value regression test in this ticket: the
    naming split at `deployments/infrastructure/justfile:8` is the trap.
11. `test_auth_commands.py::test_env_writes_diagnostics_to_stderr` — R5,
    stdout stays evaluable.
12. `test_auth_commands.py::test_whoami_prints_no_token_value` — R9.
    Asserts each cached token string is absent from stdout.
13. `test_auth_commands.py::test_logout_revokes_then_deletes` — R6.
    Asserts the call order, because both happening in either order is
    not enough.
14. `test_auth_commands.py::test_logout_deletes_cache_when_revoke_fails`
    — R6. Non-zero exit, accessors printed to stderr, file gone.
15. `test_auth_commands.py::test_unsupported_method_exits_nonzero` —
    `--method oidc` today.

### Live-cluster acceptance, marked and deferred

In `test_live_login.py`, all marked. **None of these can pass until F2 is
merged and applied**: `vault auth list` returns only `jwt-nomad/` and
`token/` today, so `auth/userpass/login/operator` 404s. Do not fake a
green run. Record the blocked state.

16. `login` against the real Vault yields a token with a non-empty
    `entity_id` (the whole point of F2's entity, §4).
17. `whoami` reports the entity and a TTL.
18. Brokering both creds paths succeeds, **or** fails with R8's message
    naming the missing policy. Under F2 as written
    (`token_policies = []`), the R8 branch is the expected result until
    F7 lands. Assert the message, not success.
19. `logout` revokes: after it, `vault token lookup` on the cached token
    fails, and the brokered Nomad and Consul accessors are gone.

## 9. Risk assessment

**What lands on disk.** `session.json` holds a Vault token whose TTL is
Vault's 32-day default (F2 sets no `token_ttl`; `default_lease_ttl: 0`,
verified), plus a Nomad and a Consul token each living at most an hour,
plus lease ids, accessors, and `entity_id`. It does **not** hold the
password. Mode `0600` in a `0700` directory is the whole protection; a
wrong mode, a non-atomic write, or a path inside the repo tree is the
worst realistic outcome of this ticket. Tests 3, 4, and 10 exist for
that.

**Blast radius.** Additive. No `deployments/`, `bootstrap/`, or
`justfile` change, so a wrong CLI cannot break an existing deploy path.
The static tokens keep working the whole time (F8 removes them, not D2),
which also means a broken `localstack login` costs a developer nothing
but the new command.

**Reversibility.** High. Delete the package directory and the cache file.
Nothing on the cluster changes except leases that expire within an hour
anyway.

**Likeliest failure modes.**

1. **Verifying nothing.** F2 is unapplied, so the implementer cannot run
   a real login. The temptation is to assert what the offline mocks say
   and call it proven. The honest close-out is: offline suite green, live
   tests written and skipped, F2 named as the blocker.
2. **Emitting one Consul variable name.** Half the repo reads
   `CONSUL_HTTP_TOKEN` and the shell exports `CONSUL_TOKEN` (§4). The
   failure is silent: `terraform` picks up a stale token from the shell
   and appears to work.
3. **Guessing the creds response field shape.** The two engines do not
   agree. Verify with one live read.
4. **Building logout on `sys/leases/revoke`.** Not in the `default`
   policy (verified). It would 403 for exactly the token that needs it.
   `auth/token/revoke-self` cascades and is granted.
5. **`env` writing a diagnostic to stdout**, which lands inside
   `eval "$(...)"` and breaks the shell.
6. **Tests writing to the real `~/.config/localstack/`** and clobbering
   the developer's live session.
7. **Scope creep into the policy.** The 403 in test 9 will tempt an
   implementer to "just add the grant". That is F7's ticket and the
   subject of a `fail` verdict. Blocking with `out-of-scope-fix-needed`
   is the correct move.

## 10. Subtickets (ordered, dependency-aware)

1. **Lock the D1 contract.** Settle Q1 and Q2: package root, CLI
   framework, HTTP client. Nothing below can be written against a guess.
2. **`session.py`.** Cache schema, atomic `0600` write, staleness. Pure,
   file-backed, no network. Tests 3 to 6.
3. **`vault.py`.** The five Vault calls plus the R2 plaintext refusal.
   Tests 1 and 2.
4. **`broker.py`.** Both creds paths, the two response shapes,
   `ensure_fresh`, the R8 messages. Tests 7 to 9. Depends on 2 and 3.
5. **`login` and `logout`.** Prompt, eager broker, revoke-then-delete.
   Tests 13 to 15.
6. **`whoami` and `env`.** Both output formats, both Consul names,
   stderr discipline. Tests 10 to 12.
7. **Live tests and docs.** `test_live_login.py` (tests 16 to 19,
   marked), `docs/cli-login.md`, slop scan, `just pre_commit`,
   `uv run pytest`, adversarial review.

## 11. Open questions

**Q1 → ANSWERED by D1, 2026-07-31.** This question said D1 had no plan file.
It has one now, and it settles the fork: package under `cli/`, src layout,
its own `cli/pyproject.toml`, `typer` at runtime. §7's anchors hold. Still
verify at pickup, since D1 is `planning` and nothing is built — no `cli/`
directory exists in the tree yet.

**Q2 — HTTP client and its mocking tool.** `requirements.txt` lists both
`httpx` (`:3`) and `hvac` (`:5`), and nothing installs either.
*Recommendation:* `httpx` plus `respx`. `.claude/rules/python-testing.md:89`
names `respx` as this repo's tool for `httpx` and names nothing for
`hvac`'s `requests` layer. The five Vault endpoints D2 needs are small
enough that `hvac` buys little and costs a mocking story the rules do not
cover. Defer to D1 if D1 already picked.

**Q3 → RESOLVED (operator, 2026-07-31): a PATH shim. Neither `env` nor
`exec`.** A third option this question did not list, and it dissolves the
cost the recommendation admitted. `~/.localstack/bin` goes on PATH ahead of
`/usr/bin`, holding a shim per CLI that refreshes the brokered token when
stale and then execs the real binary. See §12 for the contract.

Why it beats both listed options: `env` goes stale after 30 minutes with no
way to reach back into the shell, and it only ever fixes the one shell it
ran in — scripts, subshells and `just` recipes each need their own `eval`.
`exec` is always fresh but rewrites every call site and you type the prefix
forever. The shim is fresh per invocation AND works in every shell, script
and subprocess with nothing typed.

The forcing constraint, measured 2026-07-31: **`nomad` has no credential
file.** `NOMAD_TOKEN_FILE` does not exist — zero occurrences in the 2.0.3
binary, against two for `CONSUL_HTTP_TOKEN_FILE` — and `nomad login` has no
sink flag, it only prints. So `nomad` reads `NOMAD_TOKEN` or `-token` and
nothing else, and a child process cannot set its parent shell's environment.
Every option that is not a shim inherits that limitation.

`vault` needs no shim at all once Q4 is applied, and `consul` needs none if
`CONSUL_HTTP_TOKEN_FILE` is set statically in the devcontainer. Nomad is the
only CLI that strictly requires one; ship the other two for uniformity or
skip them, implementer's call.

**Q4 → RESOLVED (operator, 2026-07-31): yes, write `~/.vault-token`,
mode 0600.** The earlier recommendation was no. It is reversed.

That file is the whole reason the stock `vault` CLI needs no shim: `vault`
reads it natively, so writing it is what makes `vault kv get` work after
`localstack login` with no env var and no wrapper. It is also the exact
mechanism this repo is copying — `gcloud` keeps its credential in
`~/.config/gcloud/credentials.db` and every later `gcloud` command reads it.

The objection stands but is thin here: the CLI writes a file it does not
own, and clobbers whatever a developer's own `vault login` put there. One
cluster, one operator, and `localstack login` is itself a Vault login, so
the value it writes is the value `vault login` would have written.

Write it the way `vault login` does: 0600, and on `localstack logout` remove
it rather than leaving a revoked token on disk.

**Q5 — One session or named profiles?** One cluster exists.
*Recommendation:* one session file, no profile flag. The schema already
carries `version` and `vault_addr`, so a profile layer is an additive
change later. Building it now is speculative
(`AGENTS.md` §2).

**Q6 → RESOLVED (operator, 2026-07-31): the 32-day TTL is the design, not a
defect. Keep it.** This question framed a long Vault TTL as a problem to fix.
That framing is wrong once the two credentials are told apart.

The Vault token is the **refresh token**: long-lived, renewable, held on
disk, re-obtained by logging in about monthly. The brokered Nomad and Consul
creds are the **access tokens**: 30 minutes, refreshed invisibly by the Q3
shim. Short access tokens are a feature precisely because refresh is
automatic; lengthening them would be the wrong fix for the staleness `env`
suffered from. This is `gcloud`'s architecture, which is what the CLI is
modelled on.

Two consequences, both reversals of the earlier recommendation:

- **Drop the `whoami` warning** above 24 hours. It would fire on every
  healthy session and train the operator to ignore it.
- **Drop the `token_ttl`/`token_max_ttl` task handed to F7.** Recorded in
  F7's `## Measured evidence, 2026-07-31` section so its replan does not act
  on the earlier advice.

`whoami` should still *show* the remaining TTL, and warn when it is nearly
expired, which is the useful direction. Leave `auth_userpass.tf` alone, as
before.

**Q7 — Where the one-time password retrieval is documented.** The
operator needs the KV2 password once, using the root token, and the CLI
cannot fetch it (§4).
*Recommendation:* document it in `docs/cli-login.md` and point at the F2
branch's `docs/vault-human-auth.md`, which already carries the
`vault kv get secret/default/vault/operator` recipe. Do not add a KV2
read path to the CLI.

## How this ticket informs F7's replan

D2 does not fix F7, and does not touch its policy. It does settle three
things F7's replan needs, each verified here rather than assumed:

1. **The login method is `userpass`, not OIDC.** Operator decision. F7's
   own Q1 recommended Google OIDC, and its verdict flagged the
   `depends_on = F2` edge as contradicting that recommendation
   (`.loop/verdicts/F7-foundation-deployer-vault-oidc-login.plan-validator.md:118-138`).
   With `userpass` chosen, the F2 edge is correct and F7's login half
   collapses to binding a policy to the existing operator entity.
2. **What the policy must grant on top of `default`.** D2's client calls
   `nomad/creds/deploy` (read), `consul/creds/deploy` (read),
   `auth/token/lookup-self`, `auth/token/renew-self`,
   `auth/token/revoke-self`. The last three are already in `default`. The
   first two are the minimum F7 must add for `localstack login` to
   function at all. This is separate from, and smaller than, the
   terraform-apply grant the verdict says F7 got wrong
   (`:250-260`).
3. **The operator login needs a `token_ttl`.** See Q6.

## Eval marker

`.loop/config.json` sets `require_eval: true`, so the loop refuses pickup
until `.loop/evals/D2-cli-login-broker-tokens.md` exists with a
`signed-off-by` line. Co-author it with the `create-eval` skill and get
operator sign-off. This ticket does not author it.

Two guardrails belong in that eval, because prose alone leaves them
wobbly: `env` must emit both Consul variable names, and `logout` must
revoke before it deletes.

## 12. Design locked, 2026-07-31

The operator settled Q1, Q3, Q4 and Q6 in one sitting. This section is the
shape those answers add up to, so an implementer does not have to reassemble
it from four question blocks.

### The model

`gcloud`, mapped onto Vault. One long-lived credential the human holds, and
short-lived service credentials refreshed from it without the human noticing.

```
Vault token       32 days, renewable    -> ~/.vault-token (0600)
  |                                        + ~/.localstack/session.json
  +- nomad/creds/deploy     30 min       -> refreshed by the shim
  +- consul/creds/deploy    30 min       -> refreshed by the shim
```

### How each CLI gets its token

Measured against the installed binaries on 2026-07-31, not assumed:

| CLI | Reads a credential file? | Needs a shim? |
| --- | --- | --- |
| `vault` | yes, `~/.vault-token`, no config needed | **no**, once Q4 writes it |
| `consul` | yes, via `CONSUL_HTTP_TOKEN_FILE` | **no**, if that var is set statically |
| `nomad` | **no. `NOMAD_TOKEN_FILE` does not exist** | **yes** |

`CONSUL_HTTP_TOKEN_FILE` is configuration, not a credential: it names a path,
never changes, and holds no secret, so the devcontainer can export it once
and `localstack login` just writes the file it points at.

### The shim contract

```bash
# ~/.localstack/bin/nomad
#!/usr/bin/env bash
T="$(localstack token nomad 2>/dev/null)" || exec /usr/bin/nomad "$@"
exec env NOMAD_TOKEN="$T" /usr/bin/nomad "$@"
```

Three requirements the implementer must not drop:

1. **Fall through on failure.** If `localstack token` cannot produce one, exec
   the real binary unchanged. A broken CLI must degrade to today's behavior,
   never to a dead `nomad`.
2. **Cache, do not mint per invocation.** Reuse the brokered token until it is
   near expiry. Minting on every `nomad` call piles up Vault leases fast. This
   is what `gcloud`'s `access_tokens.db` is for.
3. **Resolve the real binary robustly.** `/usr/bin/nomad` is the current path;
   do not re-resolve through `PATH` or the shim calls itself.

The devcontainer puts `~/.localstack/bin` on PATH ahead of `/usr/bin`, so on
a configured machine the setup cost is zero. `which nomad` showing the shim is
the accepted cost.

### `localstack ui consul`

Consul's OIDC auth method is Enterprise-only and this cluster is CE, verified
2026-07-31: `consul version` carries no `+ent` and the agent reports
`Edition: n/a`. The CE `jwt` method is programmatic, with no browser redirect,
so the Consul UI cannot drive it either. Pasting a token is the only route,
and no amount of design removes that.

So make it one command: broker a Consul token, copy it to the clipboard, print
it as a fallback, and open `https://consul.lab.orangecluster.nl`. The operator
pastes once per session.

- Print the token even when the clipboard write succeeds. Inside a container
  the clipboard is the part most likely to fail, and a silent failure leaves
  the operator with a browser and no token.
- Clipboard needs a helper (`xclip`, `pbcopy`, or an OSC 52 escape). OSC 52
  travels over SSH and through the devcontainer, so prefer it.
- The same command shape can serve `localstack ui nomad` later, but do not
  build that here. Once Nomad UI SSO lands, Nomad needs no token paste at all.

### What this does NOT settle

`localstack env` still has a place for `just` recipes and CI, where a shim on
PATH may not be present. Q3 chose the shim as the developer surface, not as
the only surface. Keep `env` if it is cheap; do not make the recipes depend on
a shim being installed.

### Command surface, settled 2026-07-31

The operator fixed the CLI's whole command surface on the same day as §12's
decisions. Two commands land in this ticket that were not in its original
`login|logout|whoami|env` scope:

- **`localstack token <svc>`** — prints the brokered token for `nomad`,
  `consul` or `vault`, refreshing it first if stale. This is the shim's
  backend, so its output contract is strict: **the token and nothing else on
  stdout**, every diagnostic on stderr, and a non-zero exit with empty stdout
  when it cannot produce one. The shim puts the result straight into
  `NOMAD_TOKEN`, so a stray banner becomes an invalid token and a 403 that
  reads like a permissions bug. Failing closed with empty stdout is what makes
  the shim's fall-through to the bare binary safe.
- **`localstack config`** — show the cluster addresses and edge domain. It
  lands here rather than in D1 because this ticket already needs `vault_addr`
  to log in and already owns the session file. Keep it small, and keep it free
  of secrets: `config` is what a developer pastes into an issue when asking
  for help.

`login` also writes `~/.vault-token` now, per Q4, and `logout` must remove it.
A revoked token left on disk is worse than no file, because the next `vault`
command fails with a confusing 403 instead of an honest "not logged in".

Machine setup, meaning installing the pinned CLI binaries and the shims
themselves, is **not** this ticket. See `D6-cli-deps-and-shims`.

The eval marker's signature was cleared: it was signed against the
four-command scope before these decisions.

### Remaining forks resolved, 2026-07-31

Q1, Q3, Q4 and Q6 were settled earlier the same day and are marked inline.
The other three are resolved on their recorded recommendations:

- **Q2 → `httpx` plus `respx`.** `.claude/rules/python-testing.md` names
  `respx` as this repo's tool for `httpx` and names nothing for `hvac`'s
  `requests` layer. The handful of Vault endpoints here does not earn a client
  library plus a mocking story the rules do not cover. Confirm against D1's
  shipped `cli/pyproject.toml` at pickup; if D1 already added `hvac`, raise it
  rather than adding a second HTTP stack.
- **Q5 → one session file, no profiles.** One cluster exists. The schema
  already carries `version` and `vault_addr`, so a profile layer stays an
  additive change. Building it now is speculative.
- **Q7 → `docs/cli-login.md`, pointing at `docs/vault-human-auth.md`.** That
  doc already carries the `vault kv get secret/default/vault/operator` recipe
  and is now merged on `main`. Do not add a KV2 read path to the CLI to fetch
  the password it needs in order to log in.
