---
epic = "cli"
depends_on = ["D1-cli-package-skeleton", "F2-foundation-vault-oidc-provider", "F11-foundation-human-read-role", "F14-foundation-role-taxonomy"]
priority = 46
tags = ["cli", "vault", "nomad", "consul", "auth"]
summary = "Add `localstack login|logout|whoami|env|token|config`: authenticate a developer to Vault with userpass, broker short-lived Nomad and Consul tokens from that session, cache them at 0600, and hand them to terraform and the hashi CLIs via `eval \"$(localstack env)\"` until D6's shims land. The devcontainer still injects root today; retiring that is F8's job, not this ticket's."
---

# D2 — `localstack login`: Vault session, brokered Nomad and Consul tokens

## 1. Title

Add the auth half of the `localstack` CLI: `login` (Vault `userpass`),
`logout`, `whoami`, `env`, `token` and `config`. **One command brokers all
three credentials**: `localstack login` authenticates to Vault and, in the
same run, brokers the Nomad and Consul tokens (R1, eager by design). No
per-service login and no static god-mode token to deploy. Re-brokering after
a lease expires is automatic (R4); that is a refresh, not a second sign-in.

**Getting them into the shell is a separate step until D6 lands.** `login`
brokers; `eval "$(localstack env)"` delivers. Until D6's shims exist, and
with the devcontainer injecting root (R5, R11, §12), a bare `vault` after
`login` alone still runs as root and `nomad` as the bootstrap token. D6 makes
the delivery step disappear; this ticket must not claim it already has.

## 2. Size / Effort

**L.** Six commands (`login`, `logout`, `whoami`, `env`, `token`,
`config`), but the weight is elsewhere: a credential cache
with per-credential expiry, three different lease models in one session
(Vault token, Nomad lease, Consul lease), a revoke-on-logout path that
must not leave live tokens behind, and an offline test suite that never
touches the cluster by default. The command surface must also admit a
future `--method oidc` without changing shape.

`token` is small to write and easy to get wrong: it is the backend
`D6-cli-deps-and-shims` builds its PATH shims on, so its stdout contract
(the token, nothing else, empty on failure) is load-bearing for another
ticket. `config` is thin, and it lives here because
they read the session file and the resolved addresses this ticket already
owns.

## 3. Triggered by

Operator request: a developer should authenticate once and deploy, the
way `gcloud auth login` works, instead of copying a Vault root token and
two static god-mode tokens into `.devcontainer/.env`
(`.devcontainer/.env.example:2,6,10`). This is the client half of
`F11-foundation-human-read-role`. D2 builds the client; F11 owns the policy.
**F7 is retired** — it was dropped on 2026-08-01 after failing plan review
twice, and this plan named it throughout. F11 replaces it, and as of
2026-08-01 it is **`done` and applied to the live cluster** — the `developer`
policy and identity group exist and the operator entity is a member.

## 4. Context

### What a developer holds today

Static, long-lived, god-mode:

- `VAULT_TOKEN` is the bootstrap root token. Verified live:
  `vault token lookup` reports `policies: ["root"]`, `ttl: 0`,
  `entity_id: ""`, `path: auth/token/root`. Source is
  `/opt/vault/init.json`, read at
  `bootstrap/roles/nomad_server/tasks/main.yml:189-196` and reused as
  `VAULT_TOKEN` at `:202,211,224`.
- `NOMAD_TOKEN` and `CONSUL_TOKEN` are the bootstrap management tokens,
  exported from `.devcontainer/.env` (gitignored, `.gitignore:2`).
- **All three reach every shell and every child process, because the
  devcontainer injects the whole file into the container:**
  `.devcontainer/devcontainer.json:38-39` passes
  `--env-file .devcontainer/.env`, and `.devcontainer/.env:8` sets
  `VAULT_TOKEN` to the root token. Nothing a CLI does can remove a
  variable from a shell that already has it. This fact governs §6 R11 and
  R12 and is the reason the shim in §12 exists.
- Addresses, **current as of 2026-07-31, not fixtures**:
  `VAULT_ADDR=http://192.168.2.30:8200`,
  `NOMAD_ADDR=http://192.168.2.30:4646`,
  `CONSUL_HTTP_ADDR=http://192.168.2.30:8500`.
  `N4-netsec-edge-only-service-access` (`planning`, priority 50 against
  D2's 46) moves `.devcontainer/.env` and `.env.example` to the edge
  hostnames (`.loop/plans/N4-netsec-edge-only-service-access.md:377-378`, the `.env`
  edge cutover).
  That cutover is absorbed: every address D2 uses comes from the
  environment or a flag. Two consequences to expect rather than
  re-litigate. Today R2 forces `--insecure` on every login, because the
  default `VAULT_ADDR` is non-loopback plaintext. After N4 lands that flag
  becomes unnecessary, and the addresses above go stale.

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

**F2 is merged and applied.** The ledger has
`F2-foundation-vault-oidc-provider: done`. Verified live 2026-07-31:
`vault auth list` returns `jwt-nomad/`, `token/` **and** `userpass/`
(accessor `auth_userpass_ca653bd3`, description "Human logins. Entities
created here are what OIDC assignments gate on."). `vault list
auth/userpass/users` returns `operator`. The operator entity is live at
`351f302a-ada1-0e79-15d3-e22a4be2e3e4`, and
`secret/default/vault/operator` holds `username` and `password`. So a real
`userpass` login runs today, and the live acceptance rows in §8 are
runnable at pickup rather than blocked.

`deployments/infrastructure/auth_userpass.tf`, now on `main`, creates:

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
   policy binds the operator entity to the creds paths. **That policy is
   `F11`, which is **`done` and applied** and grants exactly `nomad/creds/deploy` and
   `consul/creds/deploy` as read** — the two paths this client brokers, so
   the coupling is satisfied once F11 lands. The CLI must still fail with a message naming
   the missing grant rather than a bare traceback — that path is reachable
   from a scratch user in no group, or from any other role name.
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

The `consul` binary reads `CONSUL_HTTP_TOKEN`, never `CONSUL_TOKEN`.
`CONSUL_TOKEN` matters only because the repo's own recipes bridge it into
`CONSUL_HTTP_TOKEN`, so a stale `CONSUL_TOKEN` in the shell silently
overwrites a fresh one inside every `just` recipe. That is why R5 emits
both names and why emitting only the one the binary reads is not enough.

### How each CLI picks up a credential, measured

Measured against the installed binaries on 2026-07-31. These three results
decide §6 R10 to R12 and the §12 shim table, so they are stated here rather
than inside a design section.

1. **`vault`: the environment beats the file.** With `HOME` pointed at a
   directory whose `~/.vault-token` held garbage, `vault token lookup`
   still succeeded, because it used `VAULT_TOKEN` from the environment.
   Combined with the devcontainer injection above, **writing
   `~/.vault-token` changes nothing in this container**: `vault` keeps
   running as root. There is already an 8-byte, invalid `~/.vault-token`
   in this container that no `vault login` created, and
   `env -u VAULT_TOKEN vault token lookup` against it returns 403.
2. **`consul`: the file beats the environment, and a missing file is
   fatal.** With a valid token in `CONSUL_HTTP_TOKEN` and a garbage token
   in the file `CONSUL_HTTP_TOKEN_FILE` names, `consul acl token read
   -self` returned `403 (token does not exist: ACL not found)`. The file
   won. And with `CONSUL_HTTP_TOKEN_FILE` pointing at a path that does not
   exist, `consul members` returned `Error connecting to Consul agent:
   Error loading token file ...: no such file or directory`, even with a
   valid `CONSUL_HTTP_TOKEN` set. Exporting that variable before something
   writes the file breaks the `consul` CLI for everyone. It is not inert.
3. **`nomad`: there is no file.** `strings /usr/bin/nomad | grep -c
   NOMAD_TOKEN_FILE` returns `0`, against `2` for `CONSUL_HTTP_TOKEN_FILE`
   in `/usr/bin/consul`. The `NOMAD_*` string table carries `NOMAD_TOKEN`
   and no file variant, and `nomad login -h` (v2.0.3) lists no sink flag.
   `nomad` reads `NOMAD_TOKEN` or `-token` and nothing else.

Result 1 is the dangerous one, because it fails silently in the direction
of more privilege: a developer who ran `localstack login` and sees
`vault kv get` working is still root. Result 2 is dangerous in the same
direction one layer down. §6 R10 and R11 are the response.

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

- **Not the `developer` Vault policy.** `F11` owns it. D2 must not author,
  widen, or work around it, and a diff touching `deployments/` is out of scope
  here. Note that `F11` deliberately grants the **exact** paths
  `nomad/creds/deploy` and `consul/creds/deploy`, not `nomad/creds/*` — so a
  client that brokers any other role name will 403 by design, not by
  oversight.
- **Not OIDC login.** Operator decision, already made: authenticate
  against the `userpass` backend F2 ships. Reserve `--method` in the
  interface so OIDC can be added later without an interface change. Do
  not build a callback listener, a Google OAuth client, or a Vault OIDC
  auth mount.
- **Not the read commands (D3) or the TUI (D4).** They consume these
  tokens. D2 does not anticipate their needs.
- **Not the provider cutover (F8).** D2 does not edit `providers.tf`, any
  `justfile`, `.devcontainer/.env`, `.devcontainer/.env.example`, or
  `.devcontainer/devcontainer.json`. Removing the static `VAULT_TOKEN`,
  `NOMAD_TOKEN` and `CONSUL_TOKEN` from the injected env file is F8's
  story, and F8 is `blocked` (`loopctl ledger`). **D2 therefore ships into
  a container where the root token is in every shell**, and R11 is how it
  behaves honestly there instead of pretending otherwise.
- **Not `localstack exec`.** See Q3; `env` is the chosen surface.
- **Not installing the shims or the pinned binaries.** `D6-cli-deps-and-shims`
  owns `~/.localstack/bin`, the PATH entry, and the devcontainer change
  that adds it. D2 owns only `localstack token`, the contract D6's shims
  call. See R10.
- **Not multi-cluster profiles.** One cluster, one session. See Q5.
- **Not any `ui` command.** `ui consul` was cut on 2026-08-01; see §12. The
  operator's locked surface for D2 is `login|logout|whoami|env|token|config`
  (`ROADMAP.md`, the locked command-surface block — cite **by name**, the
  file has uncommitted edits so line numbers do not survive into a worktree),
  and `ui consul` was folded into D3's `service consul --open`. An earlier
  draft shipped it here on the reasoning
  that pasting a token into the Consul UI is unavoidable on CE. **That
  reasoning is refuted in §12**: the UI needs no token at all, and pasting the
  brokered one cuts the visible catalog from 25 services to 2. Nomad UI SSO is
  a separate story (G2).
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
  "vault":  {"token": "", "accessor": "", "entity_id": "", "policies": [],
             "expires_at": "ISO8601", "renewable": true},
  # The vault accessor is REQUIRED, not symmetry: it is the input to the
  # one-action revoke in §9, and the login response already returns it. The
  # schema recorded every accessor except the one the headline remedy needs.
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

Emitting `VAULT_TOKEN` is what makes `eval "$(localstack env)"` the one
move that actually demotes the shell from root to `operator`, since the
variable it overwrites is the injected root token (§4). That is a real
benefit and it is also the reason R11's warning must not fire after an
`eval`: the values match, so there is nothing to warn about.

**R5 does not use `CONSUL_HTTP_TOKEN_FILE`, and neither does anything
else in this ticket.** Measured, §4: the file outranks
`CONSUL_HTTP_TOKEN`, so a stale file would silently beat every fresh
token R5 emits and every token a shim exports, and a missing file makes
the `consul` CLI fail outright rather than fall back. Setting it would
turn R5 into decoration. See R12 for the ownership call and what D6 must
change.

**R6 — `localstack whoami` and `localstack logout`.**

- `whoami` reports: username, `entity_id`, **the Vault token's own
  accessor**, Vault token policies, Vault TTL remaining, and per brokered
  credential the accessor, lease id, and TTL remaining. Never the token
  values. Exit non-zero when no session exists. `--format json`.

  **The Vault accessor is not symmetry, it is the input to §9's primary
  remedy.** Revoking a stolen session means revoking every accessor at
  `auth/userpass/login/operator` **except your own**, and this is the only
  command that tells a responder which one is theirs. R3 writes it to a `0600`
  file and R13 rightly forbids `config` from printing it, so without this line
  it is recorded and unreadable.
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
lookup-self>`, and that the grant is `F11`'s ticket. **Read
`identity_policies`, not `policies`** — F11 binds through an identity group,
so the granted policy lands in the former while `policies` holds only
`default`. An error message reporting `policies` will tell the developer they
have no grants when they do. If F11 has not landed, the 403 is the expected
result and this is the message a developer will actually see, so it gets the
most care. A 404 on `auth/userpass/login/*` prints that
the `userpass` backend is not enabled at that path; it is no longer the
expected state of the world, since F2 is applied, so treat it as a
misconfigured `--vault-addr` or a wrong username rather than a known
blocker.

**R9 — Tokens never reach stdout by accident.** No token value in any
log line, exception message, or `--format json` output other than
`env`'s and `token`'s, which exist to emit them.

**R10 — `localstack token <svc>`.** Prints the current token for `nomad`,
`consul` or `vault`, refreshing it first if stale (R4). This is the
backend `D6-cli-deps-and-shims` builds its PATH shims on, so the contract
is strict and mechanical, not stylistic:

- **Stdout is the token value and a single trailing newline. Nothing
  else.** No banner, no timing line, no colour, no warning. Every
  diagnostic goes to stderr. The shim does `T="$(localstack token nomad)"`
  and puts `$T` straight into `NOMAD_TOKEN`, so one stray character
  becomes an invalid token and a 403 that reads like a permissions bug.
- **Fail closed: non-zero exit with empty stdout**, whenever there is no
  session, the session is expired, or brokering is denied. The shim's
  fall-through to the unmodified binary is only safe because a failure
  produces nothing to export. Exiting zero with an error message on
  stdout would export the error message as the token.
- An unknown service name exits non-zero with empty stdout too.

**R11 — `login` writes `~/.vault-token`, and says out loud when the
environment overrides it.** Two halves, and the second is the one that
matters in this container.

- Write the Vault token to `~/.vault-token` at mode `0600`, via the same
  temp-file-plus-rename as R3, and delete it in `logout`. This is what
  `vault login` itself writes, so the value is not a novel invention, and
  a revoked token left on disk is worse than no file: the next `vault`
  command fails with a confusing 403 instead of an honest "not logged
  in". Q4 covers the decision.
- **The file is inert while `VAULT_TOKEN` is set, and it is set for
  everyone** (§4 result 1: the environment outranks the file;
  `.devcontainer/devcontainer.json:38-39` plus `.devcontainer/.env:8`).
  So `login` and `whoami` must compare the session token against
  `$VAULT_TOKEN` and, when the variable is set and differs, print a
  warning **to stderr** naming the mismatch, saying plainly that a bare
  `vault` command runs as the environment's token and not as the session,
  and naming the two ways out: `eval "$(localstack env)"` in this shell,
  or the `vault` shim on PATH (R10, installed by D6). The warning names
  the policies of the environment's token when `lookup-self` on it
  succeeds, because "you are still root" is the fact worth printing.
  `logout` warns the same way: it deletes the file and revokes the
  session, and `vault` keeps working as the environment's token, so a
  silent `logout` would look like it did nothing.
- The warning must not fire when `VAULT_TOKEN` equals the session token,
  which is the state after `eval "$(localstack env)"`. A warning on every
  healthy session trains the operator to ignore it.
- `whoami` reports which token a bare `vault` would use, not only which
  token the session holds. That is the question the developer has.

**R12 — Consul gets a shim, not a token file, and D2 owns that call.**
Nothing in this repo writes a Consul token file today, and nothing should
start. The write was unowned: D2 never mentioned it, and
`D6-cli-deps-and-shims` disclaims all session and token logic
(`.loop/plans/D6-cli-deps-and-shims.md:188`, "No session or token
logic"). Per §4 result 2, an unowned `CONSUL_HTTP_TOKEN_FILE` export
breaks `consul` for everyone the moment it lands.

- D2's answer, and D2 owns it: `consul` takes a shim with the same shape
  as `nomad`'s, calling `localstack token consul` and exporting
  `CONSUL_HTTP_TOKEN` for that one invocation. One mechanism, one
  precedence order, no file.
- D2 writes no Consul token file and sets no `CONSUL_HTTP_TOKEN_FILE`.
  The eval's guardrail row greps the branch diff for the name.
- **D6 has taken all of it, verified 2026-07-31 after both plans were
  corrected in parallel.** Its shim table
  (`.loop/plans/D6-cli-deps-and-shims.md:84-88`) now reads **yes** for all
  three tools: `vault` ("yes, `~/.vault-token`, but `VAULT_TOKEN` outranks
  it"), `consul` ("yes, via `CONSUL_HTTP_TOKEN_FILE`, which is the
  problem") and `nomad`. D6 exports `CONSUL_HTTP_TOKEN` and never the file
  variant, and bans the file variant as a non-goal.
- **The two plans converged independently on three shims.** D2 reached it
  from Q4 (the `~/.vault-token` write is inert while the devcontainer
  injects `VAULT_TOKEN`); D6 reached it by measuring the same precedence at
  the wire. Nothing is left to relay. An earlier version of this section
  said D6 "has NOT yet taken the `vault` row" and named two stale anchors
  in it; both statements were true when written and are false now.
- Interaction with the justfile bridge: `terraform` is not shimmed, so
  recipes keep reading `CONSUL_HTTP_TOKEN=${CONSUL_TOKEN}`
  (`deployments/infrastructure/justfile:8,12,16`). `eval "$(localstack
  env)"` sets both names (R5), so the bridge substitutes the fresh token.
  This is the second reason R5 emits both.

**R13 — `localstack config`.** Prints the resolved cluster addresses and
the edge domain, in text and with `--format json`. **No secret material
in either form**: no token, no password, no `hvs.` or `hvo_` value, and
no session-file field beyond the non-secret ones (`vault_addr`, `method`,
`version`, expiries). `config` is what a developer pastes into an issue
when asking for help, which is exactly why it must be safe to paste. It
lands here rather than in D1 because it reads the resolved `vault_addr`
and the session file, both of which this ticket owns.

**R14 — REMOVED. `localstack ui consul` is not part of this ticket.**

Cut on 2026-08-01 for two independent reasons.

**It is not in the operator's locked surface.** `ROADMAP.md`'s locked
command-surface block (by name, not line — the file has uncommitted edits)
fixes D2's surface at
`login | logout | whoami | env | token <svc> | config`, and records that
`ui consul` was folded into `service consul --open`, which is D3's. This plan
predates that lock and never caught up.

**Its premise was false anyway.** It existed to hand you a token to paste into
the Consul UI. Measured 2026-08-01: the UI needs no token — `tokens.default`
is the agent token, so unauthenticated requests return the full catalog and
`/ui/` answers 200. Both directly and through the edge over TLS. Pasting the
brokered `deploy` token would have made it *worse*, replacing the agent
default and cutting the visible catalog from 25 services to 2.

Nothing replaces it here: `config` (R13) already prints the Consul address.

### Restrictions the repo states

- **Tests ship with the code** (`.claude/rules/python-testing.md:6`) and
  mirror the source tree (`:43-48` "Where tests live").
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
- `cli/src/localstack_cli/auth/vault_token_file.py` — R11's first half:
  write `~/.vault-token` at `0600` through temp-file-plus-rename, remove
  it, and `env_token_differs(session_token)` reporting whether
  `$VAULT_TOKEN` is set and differs. Separate from `session.py` because
  it writes a file this CLI does not own, and the next reader should see
  that boundary in the layout.
- `cli/src/localstack_cli/commands/auth.py` — `login`, `logout`,
  `whoami`, `env` wired into D1's CLI entry point, plus R11's stderr
  warning on `login`, `whoami` and `logout`.
- `cli/src/localstack_cli/commands/token.py` — R10. `localstack token
  <svc>`. Kept in its own module precisely because its stdout contract is
  stricter than every other command's: no shared output helper that might
  one day print a banner, and nothing else in the file to tempt one.
- `cli/src/localstack_cli/commands/config.py` — R13. Addresses and edge
  domain, text and JSON, no secrets.
- `cli/tests/auth/test_vault.py` — login, lookup, renew, revoke, and the
  R2 plaintext refusal, all against `respx`.
- `cli/tests/auth/test_vault_token_file.py` — R11. Write at `0600`,
  removal, and the `$VAULT_TOKEN` comparison including the equal case
  that must not warn.
- `cli/tests/auth/test_session.py` — write/read round trip, file mode
  `0600` and directory mode `0700`, atomicity (no world-readable window),
  staleness at the skew boundary, corrupt-file handling.
- `cli/tests/auth/test_broker.py` — creds parsing for both engines,
  `ensure_fresh` re-brokers a stale entry and leaves a fresh one alone,
  a 403 raises the R8 message.
- `cli/tests/commands/test_auth_commands.py` — `env` emits all four
  variable names including both Consul spellings; `whoami` prints no
  token value; `logout` calls `revoke-self` before deleting and still
  deletes when revocation fails; R11's warning fires when `$VAULT_TOKEN`
  differs and stays quiet when it matches.
- `cli/tests/commands/test_token_command.py` — R10. Byte-for-byte stdout
  purity across all three services, and failing closed with empty stdout
  on every failure path.
- `cli/tests/commands/test_config_command.py` — R13. No secret material
  in text or JSON output, asserted against a session file whose token
  values are known.
- `cli/tests/auth/test_live_login.py` — live-cluster tests carrying D1's
  `cluster` marker (`.loop/plans/D1-cli-package-skeleton.md:137-140,172`),
  excluded by default via `addopts`.
- `cli/tests/conftest.py` — autouse fixtures redirecting
  `XDG_CONFIG_HOME` **and `HOME`** into `tmp_path`, so no test can write
  the developer's real `~/.vault-token`, and a fixture that clears
  `VAULT_TOKEN` from the environment by default so R11's warning is
  opt-in per test; a fixture building a session file.
- `docs/cli-login.md` — one page: how to get the password the first time,
  `localstack login`, `eval "$(localstack env)"`, what `logout` revokes, the
  F2/F11 preconditions, and **the revocation shape from §9** — three
  credentials; `logout` and an accessor revoke each end all three by cascade,
  and the accessor revoke needs no root; if neither is available it is
  cut-then-delete in that order, and revocation does not un-disclose what was
  read. The revocation section of `docs/vault-human-auth.md` says the same
  thing — cite it **by name**: at the time of writing it is an uncommitted
  working-tree edit, so a line anchor would not resolve in a worktree, which
  branches from committed state. Runs the slop
  scan.

Modified:

- `cli/pyproject.toml` (D1's file) — add `httpx` and dev `respx` via
  `uv add`; register the `cluster` marker and the `addopts` exclusion if
  D1 did not.
- D1's CLI entry module — register the subcommands: `login`, `logout`,
  `whoami`, `env`, `token` and `config`. One line each. **No `ui` group** —
  see R14 and §12.

Read-only anchors the implementer will open, and must not edit:
`deployments/infrastructure/nomad_deploy_role.tf:36-41`,
`deployments/infrastructure/consul_deploy_role.tf:19-25`,
`deployments/infrastructure/justfile:8,12,16`,
`deployments/infrastructure/auth_userpass.tf:13-53`,
`.devcontainer/.env.example:2,6,10-11`,
`.devcontainer/devcontainer.json:38-39`,
`bootstrap/roles/nomad_server/tasks/main.yml:309`,
`docs/vault-human-auth.md`.
All of these are on `main` now that F2 is applied, **except
`docs/vault-human-auth.md`**, whose revocation section is an uncommitted
working-tree edit — expect it to be absent in a fresh worktree. Worse than
absent: the version on `main` still carries a bullet this section's
measurements falsify, so a worktree shows the **wrong** claim rather than no
claim. Commit the doc alongside this ticket. Nothing here
needs a branch checkout.

## 8. Tests & validation gates

### Repo gates, discovered

- **Loop gate:** `just pre_commit` (`.loop/config.json:2-3`) runs
  `pre-commit run --all-files` (`justfile:18-19`). The config excludes
  `^\.(claude|loop)/` (`:1`).

  **This description is written against `main`; D1 changes it.** D1 adds four
  hooks to the root `.pre-commit-config.yaml`: `ruff` (lint), `ruff-format`,
  `mypy` and `pytest`. Two consequences for D2:

  - **mypy runs `strict = true`** against `cli/src` and `cli/tests`, so every
    symbol D2 adds needs annotations. This is not optional and it is not
    caught late — the hook is in the loop gate.
  - **`just pre_commit` DOES run the suite.** The old claim that it would not
    is inverted by D1.

  Still do not add hooks here (`.claude/rules/prek-code-quality.md`) — D1 owns
  that config, and D2 inherits it.
- **Inner loop:** `cli/justfile` provides `just check` (lint, typecheck, test)
  plus `test`, `test_cluster`, `lint` and `typecheck` individually. Use those
  while working; `just pre_commit` from the repo root is what gates.
- **Marked live run:** `uv run pytest -m cluster` (`:12-13`). Off by default
  via `addopts` (`:26-32`). The marker name is D1's
  (`.loop/plans/D1-cli-package-skeleton.md:137-140,172`); use it rather than
  inventing a second one.
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
   per `.claude/rules/python-testing.md:101-103`).
9. `test_broker.py::test_403_on_creds_names_the_missing_grant` — R8.
   Asserts the message names the path and points at F11.
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
16. `test_token_command.py::test_token_stdout_is_exactly_the_token` —
    R10. Parametrized over `nomad`, `consul` and `vault`. Compares stdout
    byte for byte against `f"{token}\n"`, not with `in` or `strip()`. A
    loose assertion passes against the banner this test exists to catch.
17. `test_token_command.py::test_token_fails_closed_with_empty_stdout` —
    R10. Parametrized over no session, expired session, 403 on the creds
    path, and an unknown service name. Each: non-zero exit, stdout
    exactly empty, message on stderr. This is the row D6's shim safety
    rests on.
18. `test_vault_token_file.py::test_login_writes_0600_vault_token_file` —
    R11. Written under the `HOME` redirected into `tmp_path`, mode
    asserted, no world-readable window.
19. `test_vault_token_file.py::test_logout_removes_vault_token_file` —
    R11. Gone afterwards, and gone even when `revoke-self` failed.
20. `test_auth_commands.py::test_warns_when_env_vault_token_differs` —
    R11, and **the row that catches the dangerous failure**. With
    `VAULT_TOKEN` set to a different value, `login`, `whoami` and
    `logout` each print a warning to stderr saying a bare `vault` runs as
    the environment's token, not the session. Assert on stderr, assert
    stdout is unpolluted, and assert `whoami` reports which token a bare
    `vault` would use.
21. `test_auth_commands.py::test_no_warning_when_env_matches_session` —
    R11. With `VAULT_TOKEN` equal to the session token, and with it
    unset, stderr carries no such warning. A warning on every healthy
    session is worse than none.
22. `test_config_command.py::test_config_prints_no_secret` — R13. Text
    and JSON forms, asserted against a session file whose token and
    accessor values are known strings, plus a check for the `hvs.` and
    `hvo_` prefixes.
23. `test_auth_commands.py::test_whoami_prints_the_vault_accessor` —
    R6. Asserts the session token's **accessor** appears in `whoami`'s
    output and in `--format json`. This is the one R6 output clause with
    no test, it is the input to §9's headline remedy (revoke every
    accessor at the path except your own), and it has failed to land
    twice. Test 12 does not cover it — that row asserts token *values*
    are absent, and an accessor is not a token value.

### Live-cluster acceptance, runnable now

In `test_live_login.py`, all carrying the `cluster` marker. **F2 is
applied, so rows 24, 25 and 27 run at pickup**: `vault auth list` returns
`userpass/`, `auth/userpass/users/operator` exists, and the password is at
`secret/default/vault/operator` (§4). Retrieve it out of band once, per
R7 and Q7. Run these; do not record them as blocked.

24. `login` against the real Vault yields a token with a non-empty
    `entity_id` (the whole point of F2's entity, §4).
25. `whoami` reports the entity and a TTL.
26. Brokering both creds paths **fails with R8's message naming the
    missing policy**. **`F11` applied on 2026-08-01, so `operator` now
    brokers successfully and this row can no longer be driven from it.**
    Create a scratch `userpass` user whose entity is in no identity group,
    log in as that, and assert the 403 message against it. **Tear it down in
    this order: revoke the login token by accessor FIRST, then delete the
    user, its entity and its alias** — it is created on the live cluster and
    nothing else removes it. The order is not cosmetic. Deleting the user and
    entity does not revoke what they minted: an earlier run of this row left a
    `userpass-rowsix` token valid for 30.6 more days with its user gone and its
    entity id no longer resolving. It had decayed to `default` because the
    entity was deleted, so it was litter rather than a live grant — but the
    same teardown on a token still carrying `developer` would not have been. The row still
    matters — it is the one that is not a success assertion — but its subject
    changed.
27. `logout` revokes: after it, `vault token lookup` on the cached token
    fails. Assert against the Vault token, not against the brokered
    accessors, since under row 26 there are none to check.
28. **R11 against the live container.** With the devcontainer's injected
    `VAULT_TOKEN` still in the environment, after `localstack login`:
    `vault token lookup` still reports `policies ["root"]`, the warning
    fired on stderr, and after `eval "$(localstack env)"` the same lookup
    reports the operator entity. This row exists because the whole point
    of R11 is a fact about this machine, and an offline mock cannot prove
    it. Skip it outside the devcontainer rather than faking it.

## 9. Risk assessment

**What lands on disk.** `session.json` holds a Vault token whose TTL is
Vault's 32-day default (F2 sets no `token_ttl`; `default_lease_ttl: 0`,
verified), plus a Nomad and a Consul token each living at most an hour,
plus lease ids, accessors, and `entity_id`. It does **not** hold the
password. Mode `0600` in a `0700` directory is the whole protection; a
wrong mode, a non-atomic write, or a path inside the repo tree is the
worst realistic outcome of this ticket. Tests 3 and 4 exist for that.
R11 adds a second file, `~/.vault-token`, holding the same Vault token at
the same mode; tests 18 and 19 cover it.

**What a stolen `session.json` buys, stated plainly. `F11` is applied, so
this is the present tense.** The file is a bearer credential for the
`developer` identity, and `developer_group.tf` says in its own header that it
is **not a containment boundary**: the holder can grant themselves anything
short of `root` in about three commands. It carries `identity/*`,
`sys/policies/acl/*` and `auth/userpass/users/*` write, `secret/data/default/*`,
`auth/token/create`, and both Terraform roots.

So a stolen `session.json` is not "a token that brokers deploy credentials".
It is the cluster, for up to 32 days — Vault's built-in `768h` default, since `auth_userpass.tf`
sets no `token_ttl` and `sys/config/state/sanitized` reports
`default_lease_ttl: 0`. There is no client-side bound and no rotation. Q6
records the operator's decision that this is the design, modelled on
`gcloud`'s refresh token, and D2 does not overturn it. The consequence is
recorded here because the `gcloud` analogy understates it: a Google
refresh token is scoped and centrally revocable, this one is a key to the
cluster's deploy path.

**`session.json` holds three credentials — a Vault token and two brokered ACL
tokens. Two single actions end all three; everything else is partial.** Both
cascade from the parent token: the holder's own `localstack logout`, and a
revoke by accessor. **Neither needs root.** In order of preference:

1. `localstack logout`, if you still have the file. Below under **"Cascades,
   no root, but only the holder can run it"**.
2. A revoke by accessor, which needs `auth/token/revoke-accessor`. Reachable
   without root two ways: **join `admin`** (three commands, and membership
   survives a mid-incident `terraform apply`), or write the policy yourself if
   you cannot join it. Below under **"Closes everything in one action, and does
   NOT need root"**.
3. The composite, if you hold Nomad and Consul management tokens. Below under
   **"A composite closer, when you hold both management tokens"**.

**The blocks below are not in that order.** Each one's bold lead states what
that action does — closes everything, partial, or not a remedy — so read the
leads rather than inferring anything from position. The three above are the
ranking; the headings named there are where each one lives.

**Cascades, no root, but only the holder can run it:** `localstack logout`.
`auth/token/revoke-self` is granted by `default`, and revoking the parent kills
the child Nomad and Consul leases. Useless once the thief has the file and the
holder does not.

**Partial — the Vault token only.** Remove the operator entity from the
`developer` group. The token demotes to `default` on its next call, because the
policy arrives through the group at request time (`auth_userpass.tf:34` sets
`token_policies = []`; `developer_group.tf:141-147`). The floor is real: the
entity's other group, `oidc-smoke`, carries `policies: []`. But `default`
grants `sys/leases/renew`, so the demoted holder keeps renewing the two
brokered leases to their `max_ttl` of 3600.

**Partial — stops use, revokes nothing.** Disable the entity.
`vault path-help identity/entity/id/<id>` says it verbatim: *"If set true,
tokens tied to this identity will not be able to be used (**but will not be
revoked**)."* The brokered tokens are real ACL tokens in Nomad's and Consul's
own state and live out their lease — up to 30 minutes, or the balance of the
hour if the thief renewed first.

**Partial — the brokered tokens only, and they can be re-minted.** Delete them
where they live:

```
nomad  acl token delete <accessor_id>
CONSUL_HTTP_TOKEN="$CONSUL_TOKEN" consul acl token delete -accessor-id <accessor>
```

Both take the accessor `R3` already records and both need a management token.
**The Consul bridge is not optional**: `.devcontainer/.env` sets `CONSUL_TOKEN`
and the `consul` binary reads only `CONSUL_HTTP_TOKEN` (§4), so without it the
call runs as the agent token and fails with a permission error that reads like
a wrong accessor. And on its own this closes nothing: the stolen Vault token
still resolves `developer`, which grants read on `nomad/creds/deploy` and
`consul/creds/deploy` (`developer_group.tf:123-129`), so one `vault read`
re-mints the pair.

**A composite closer, when you hold both management tokens, and the order
matters.** Cut the mint path first — group removal or entity disable — **then**
delete the two ACL tokens. Either half alone leaves a live route. This is not
*the* non-root closer; the accessor revoke is also non-root and needs no
management tokens at all.

**Closes everything in one action, and does NOT need root:** revoke by
accessor. Revoking the parent cascades to both child leases — measured against
real Consul and Nomad agents, both brokered tokens gone from those services'
own state.

**An earlier draft called this root-only. It is not.** Two ways to reach it,
neither needing root.

**Preferred, since F14 landed: join `admin`.** `vault_policy.admin`
(`roles.tf`) is `path "*"` with `sudo`, and the live `default` policy names
none of the three accessor paths, so nothing shadows the glob there — measured
2026-08-02, a `default`-only token is denied `vault list auth/token/accessors`
and an `admin` token is allowed. Membership is a `vault write` that **survives
`terraform apply`**, which the hand-built grant below does not (see the first
residual). Three commands:

```sh
# read the current membership first: the write REPLACES the list
vault write identity/group/name/admin member_entity_ids="<current>,<you>"

vault list auth/token/accessors
vault token revoke -accessor <the stolen session's accessor>

vault write identity/group/name/admin member_entity_ids="<current-without-you>"
```

**Leaving afterwards is a habit, not a gate.** Joining `admin` is invisible to
every `terraform plan`, so nothing will remind you. `docs/cluster-roles.md`
carries that warning and the commands to read the membership.

**Fallback, for a responder who cannot join `admin`:** write the policy
yourself. `developer` grants `sys/policies/acl/*` and `identity/*`, so this
works end to end, non-root — measured. It is the longer path and its teardown
order matters, so prefer `admin` when you have it.

```hcl
# `sudo` on the list path is REQUIRED. Without it the first command 403s,
# and the prose form of this policy did exactly that for nine passes.
path "auth/token/accessors"       { capabilities = ["list", "sudo"] }
path "auth/token/lookup-accessor" { capabilities = ["update"] }
path "auth/token/revoke-accessor" { capabilities = ["update"] }
```

**Attach that policy to a THROWAWAY ENTITY, never to the `developer` group.**
This bounds the blast radius; it does not lower the thief's ceiling. A
`developer` can already create its own userpass user, entity and alias
carrying the same policy in three writes — measured — because `developer`
holds the same two grants the responder uses. What the throwaway genuinely
buys is that no *present or future* `developer` picks the grant up
automatically on their next call, and that a Terraform-managed group is not
permanently widened.
An earlier draft said the group. That is dangerous: group policies resolve at
request time — the same mechanism this section relies on for demotion — and
**the thief is a `developer`**. Attaching it to the group arms them with
`auth/token/accessors` (list, with `sudo`) and `revoke-accessor` over every
token in the cluster. That is **20 accessors, measured 2026-08-02**: 14 `jwt-nomad` workload tokens
(postgres ×2, minio, mlflow, grafana, loki, prometheus, haproxy, hermes,
phoenix, memex, bifrost, talat-consumer, talat-shim), the root token, and 5
`userpass` sessions. It was 21 until the `rowsix` orphan below was revoked. It turns a credential theft into a cluster-wide outage. The
responder already holds `identity/*` and `auth/userpass/users/*`, so a
throwaway entity costs two extra commands and contains the grant.

**Four more things the responder must know.**

- **`terraform apply` will strip your grant mid-incident.**
  `developer_group.tf:144` manages `policies` as a single-element list, so any
  apply during the incident silently removes it — and afterwards leaves an
  orphan near-root policy that Terraform does not know about. Delete the
  policy by hand when you are done.
- **Revoke every accessor at that path except the one you are using.** Five
  live accessors share `path auth/userpass/login/operator`, `display_name
  userpass-operator`, `entity_id 351f302a…` and `policies ['default']`. They
  carry distinct `creation_time` values, so they *separate* — but two of them
  were minted **10 seconds apart**, there is no audit device recording when
  the lost session was created, and "confirm before revoking" names nothing to
  confirm against. So `creation_time` does not *identify* the target. And all
  five resolve `identity_policies: ['developer']` with 30 to 32 renewable days
  left, so revoking one leaves four near-root credentials live for a month.
  Revoke them all except your own, then log in again.
- **None of this is logged.** `vault audit list` returns "No audit devices are
  enabled", and the escalation writes into `identity/entity` and
  `auth/userpass/users` — the exact two places this section's first residual
  tells you to audit afterwards.
- **Deleting the throwaway does not revoke what it minted.** Proven on this
  cluster on 2026-08-02: a `userpass-rowsix` token from an earlier run of live
  row 26 was still valid with **30.6 days left**, its user deleted and its
  entity id no longer resolving. It had decayed to `default` because the
  entity was gone, so it was litter rather than a live grant — but a throwaway
  torn down the same way while its token still carried `developer` would not
  have. **Revoke the throwaway's token by accessor before deleting the user,
  the entity and the policy.** It has been revoked.

**Why the accessor revoke outranks the composite.** The composite needs a
Nomad management token **and** a Consul management token. The accessor revoke
needs only the Vault password, which R7 says the operator already holds. For
the exact victim this section addresses — laptop gone, password known — the
composite is the remedy they cannot run. **So after `logout`, this is the
first thing to reach for.**

**Not a remedy: `vault lease revoke`.** `sys/leases/revoke` is in neither
`default` nor `developer` — and it is reachable by the same self-elevation as
the accessor revoke, so calling it "root-only" was wrong for the same reason.
It is simply dominated by the
accessor revoke above.

**Does not work: rotating the password.** `secret/default/vault/operator` is
the KV *record*; the credential lives at `auth/userpass/users/operator`
(`auth_userpass.tf:29`), so rewriting the KV entry authenticates nothing. The
thief also holds `secret/data/default/*` and `auth/userpass/users/*` and can
rotate it back.

**Three residuals survive every remedy above.** A fourth — a child token minted
via `auth/token/create` — is **closed**, measured on a dev server: the child
policy subset check reads the parent's `policies`, which is `['default']`, not
its `identity_policies`, so `auth/token/create policies=developer` returns
`400 child policies must be subset of parent`. An inherited child is
non-orphan and carries `entity_id`, so group removal demotes it in the same
call, disable 403s it, and both cascading revokes reach it. Orphan creation
needs root or sudo. The identity-group delivery R8 is built around is what
closes this.

- **A credential minted before you act.** Re-granting afterwards is not
  possible — a demoted token holds only `default`, which grants no
  `identity/*`, and a disabled one cannot be used at all — but anything
  created while the thief still held `developer` stands on its own. Only an
  audit of `identity/entity` and `auth/userpass/users` finds it, and no audit
  device is enabled, so there is no log to search.
- **Every secret they read.** `developer` grants `secret/data/default/*`, and
  nothing here rotates what was read. Revocation ends access; it does not
  un-disclose.
- **A cached grant, for up to 30 seconds — and on Consul, indefinitely.**
  Measured live: Consul runs `ACLTokenTTL: 30s` with
  `ACLDownPolicy: extend-cache`, Nomad `ACL.TokenTTL: 30s`; neither template
  sets these, so they are defaults. After the deletes an agent keeps honoring
  the token until its cache expires, and Consul keeps honoring it for as long
  as the ACL servers are unreachable. The deletes are not instantaneous and
  the runbook should not imply they are.

`docs/cli-login.md` must carry the shape, not a list: three credentials;
**your own `localstack logout` ends all three on the spot** and is the first
thing to do if you still have the file; a revoke by accessor does the
same; without either it is cut-then-delete in that order; rotating the
password saves nothing; the deletes take up to 30 seconds to bite, and on Consul are ignored entirely while its ACL servers are unreachable; and
revocation does not un-disclose what was read.

**The `~/.vault-token` write is inert today, by measurement, not by
design.** `VAULT_TOKEN` is injected into every shell (§4), and the
environment wins, so R11's file changes nothing until F8 removes the
static token and F8 is `blocked`. R11's warning is the honest response:
the failure it prevents is a developer believing they run as `operator`
while every `vault` command runs as root. That is a wrong-direction
failure — more privilege than expected, and no error to notice — which is
why tests 20, 21 and 28 exist and why the warning is a requirement rather
than a nicety.

**Blast radius.** Additive. No `deployments/`, `bootstrap/`, or
`justfile` change, so a wrong CLI cannot break an existing deploy path.
The static tokens keep working the whole time (F8 removes them, not D2),
which also means a broken `localstack login` costs a developer nothing
but the new command.

**Reversibility.** High. Delete the package directory and the cache file.
Nothing on the cluster changes except leases that expire within an hour
anyway.

**Likeliest failure modes.**
1. **Believing the `~/.vault-token` write did something.** It does not, in
   this container (§4 result 1). An implementer who writes the file, runs
   `vault kv get`, sees it work and calls R11 proven has measured the
   injected root token. Test 28 is the check; `env -u VAULT_TOKEN vault
   token lookup` is the one-liner that tells the truth.
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
6. **Tests writing to the real `~/.config/localstack/` or the real
   `~/.vault-token`** and clobbering the developer's live session. Both
   `XDG_CONFIG_HOME` and `HOME` are redirected in `conftest.py` (§7).
   There is already a stale `~/.vault-token` in this container that a
   careless test would overwrite.
7. **Scope creep into the policy.** The 403 in test 9 will tempt an
   implementer to "just add the grant". That is F11's ticket and the
   subject of a `fail` verdict. Blocking with `out-of-scope-fix-needed`
   is the correct move.
8. **A banner on `token`'s stdout.** A progress spinner, a deprecation
   notice, or a shared output helper that prints one line of context
   turns every shimmed `nomad` call into a 403 that looks like a
   permissions bug, not a CLI bug. Test 16 compares bytes for this
   reason, and `commands/token.py` is its own module for this reason.
9. **Setting `CONSUL_HTTP_TOKEN_FILE` anyway**, because it looks tidier
   than a shim. A missing file makes `consul` fail outright, and a stale
   one silently outranks every fresh token (§4 result 2). R12 forbids it
   here and tells D6 to drop it.


## 10. Subtickets (ordered, dependency-aware)

1. **Lock the D1 contract.** Settle Q1 and Q2: package root, CLI
   framework, HTTP client. Nothing below can be written against a guess.
2. **`session.py`.** Cache schema, atomic `0600` write, staleness. Pure,
   file-backed, no network. Tests 3 to 6.
3. **`vault.py`.** The five Vault calls plus the R2 plaintext refusal.
   Tests 1 and 2.
4. **`broker.py`.** Both creds paths, the two response shapes,
   `ensure_fresh`, the R8 messages. Tests 7 to 9. Depends on 2 and 3.
5. **`vault_token_file.py`.** R11's first half: the `0600` write, the
   removal, and the `$VAULT_TOKEN` comparison. Pure and file-backed, no
   network. Tests 18 and 19. Depends on nothing above it, so it can run
   alongside 3 and 4.
6. **`login` and `logout`.** Prompt, eager broker, revoke-then-delete,
   the `~/.vault-token` write and removal, and R11's stderr warning.
   Tests 13 to 15, 20 and 21. Depends on 2, 3, 4 and 5.
7. **`whoami` and `env`.** Both output formats, both Consul names,
   stderr discipline, and `whoami` reporting which token a bare `vault`
   would use and its own accessor. Tests 10 to 12 and 23, and the `whoami`
   halves of 20 and 21.
8. **`token`.** R10, and the first thing `D6-cli-deps-and-shims` needs to
   exist. Its own module, byte-exact stdout, fail-closed on every path.
   Tests 16 and 17. Depends on 4, so it can land right after `broker.py`
   if D6 is waiting; nothing in 5 to 7 blocks it.
9. **`config`.** R13: addresses with no secrets. Test 22. Depends on 4
   and 8.
10. **Confirm D6 still writes three shims.** Nothing to relay: D6 took
    the `vault` row independently on 2026-07-31 and its table
    (`.loop/plans/D6-cli-deps-and-shims.md:84-88`) reads **yes** for
    `vault`, `consul` and `nomad`. At pickup, re-read that table and stop
    if it has drifted back to two, because Q4 and R11 both assume three
    while the devcontainer injects a root `VAULT_TOKEN`. Do not edit D6
    from inside this ticket.
11. **Live tests and docs.** `test_live_login.py` (tests 24 to 28,
    `cluster`-marked, and rows 24, 25, 27 and 28 are runnable now),
    `docs/cli-login.md` covering the one-time password retrieval, the
    `VAULT_TOKEN` shadowing and how to get out of it, and **what it takes to
    revoke a stolen session** — not "who can", which is the wrong question:
    §9 establishes that `logout` and an accessor revoke each end all three by
    cascade, that **neither needs root** — a `developer` can write itself the
    accessor policy in §9 and run it — and that without either it takes the
    two-step composite. Slop scan, `just pre_commit`, `uv run pytest`,
    adversarial review.

## 11. Open questions

**Q1 → ANSWERED by D1, 2026-07-31.** This question said D1 had no plan file.
It has one now, and it settles the fork: package under `cli/`, src layout,
its own `cli/pyproject.toml`, `typer` at runtime. §7's anchors hold. Still
verify at pickup. **D1's code is not on `main`.** As of 2026-08-01
`git ls-files` matches nothing under `cli/`, and `loopctl ledger` reads
`D1-cli-package-skeleton: ready`, not `done` — the tree is staged and
uncommitted in `.loop/worktrees/D1-cli-package-skeleton` behind its review
gate. D1 is a hard dependency, so the loop will not hand D2 to an implementer
until it lands: `cli/` will exist by pickup and does not exist now. Confirm
these four against the merged tree rather than against this paragraph — the
package root `cli/src/localstack_cli/`, the console script
`localstack = "localstack_cli.main:main"`, the `cluster` marker with its
`addopts` exclusion, and the Python hooks D1 adds to the root
`.pre-commit-config.yaml`.

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

The word "only" is slightly strong: an exported bash function
(`export -f nomad`) would cover interactive shells and `bash` children.
It does not cover non-bash processes, `just`, or `exec`-style callers, so
the shim is still the more general answer. Also note the measurement is
against CLI 2.0.3 and `D6-cli-deps-and-shims` installs the cluster's
pinned 2.0.4 (`.loop/plans/D6-cli-deps-and-shims.md:45-46,61`). A shim works
either way, so this does not need re-measuring before pickup.

**All three CLIs take a shim**, not just `nomad`. The original answer here
exempted `vault` and `consul`; the measurements in §4 removed both
exemptions. `vault` because the injected `VAULT_TOKEN` outranks
`~/.vault-token`, and a shim's `exec env VAULT_TOKEN=...` is the only
thing that beats an inherited variable. `consul` because
`CONSUL_HTTP_TOKEN_FILE` is worse than useless here (R12). One mechanism
for all three, and `localstack token <svc>` (R10) is the single backend.

**Q4 → RE-DECIDED (2026-07-31, after measurement): write
`~/.vault-token` at 0600, AND keep `vault` on the shim list, AND warn when
`VAULT_TOKEN` disagrees.** The earlier answer to this question was "yes,
write the file, and that is why `vault` needs no shim." The first half
survives. **The second half was wrong**, and wrong in the direction that
produces confident, silent, over-privileged behavior.

What the earlier answer missed: `VAULT_TOKEN` in the environment outranks
`~/.vault-token`, measured (§4 result 1). And `VAULT_TOKEN` is not
hypothetical here. `.devcontainer/devcontainer.json:38-39` injects
`.devcontainer/.env` into the container, and `.devcontainer/.env:8` sets
`VAULT_TOKEN` to the bootstrap root token, so every shell and every child
process has it. On the machine this ticket targets, writing
`~/.vault-token` changes nothing: `vault kv get` keeps running as root,
`localstack logout` deletes the file and `vault` keeps working as root, so
logout looks like it did nothing. The developer believes they are
`operator`. They are root.

Three responses were available. Each is recorded with why it was or was
not taken:

1. **Defer the whole thing until F8 removes `VAULT_TOKEN` from the env
   file.** Rejected as the sole answer. F8 is `blocked` on a broken
   premise (`loopctl ledger`), so "later" has no date, and D2 would ship a
   `vault` story that is quietly false in the meantime.
2. **Have `login` unset the variable.** Impossible, and worth writing down
   so nobody tries: a child process cannot change its parent shell's
   environment. It is the same constraint that forces the `nomad` shim.
3. **Stop the devcontainer injecting it.** Correct, and explicitly not
   D2's (§5: no `.devcontainer/` edits; F8 owns removing the static
   tokens).

So the decision is the honest combination. Write the file, because it
costs nothing, it is exactly what `vault login` writes, and it becomes
load-bearing the day F8 lands. Put `vault` on the shim list next to
`nomad`, because a shim's `exec env VAULT_TOKEN=...` is the one mechanism
that beats an inherited variable today. And warn to stderr whenever
`$VAULT_TOKEN` is set and differs from the session token, because scripts,
`just` recipes and anything calling `/usr/bin/vault` directly bypass the
shim, and silence there is what makes the failure dangerous. R11 carries
all three, tests 20, 21 and 28 check them, and `docs/cli-login.md` says
plainly that until F8 lands a bare `vault` runs as root unless you ran
`eval "$(localstack env)"` or use the shim.

The residual cost of writing a file the CLI does not own still stands and
is still thin: one cluster, one operator, and `localstack login` is itself
a Vault login, so the value written is the value `vault login` would have
written. Remove it on `logout` rather than leaving a revoked token on
disk.

**D6 already agrees.** It copied the pre-correction table verbatim, then
corrected both rows on its own: `.loop/plans/D6-cli-deps-and-shims.md:84-88`
now reads **yes** for `vault`, `consul` and `nomad`, reached by measuring
`VAULT_TOKEN` precedence at the wire rather than by inheriting this
finding. Two plans, two methods, same answer.

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

### Q-relay — should §9's escalation use `admin` rather than a throwaway?

**RESOLVED by the operator, 2026-08-02: use `admin`.** The recommendation
below was taken, and `F14-foundation-role-taxonomy` was added to this ticket's
`depends_on` in the same change. §9 leads with the `admin` procedure; the
throwaway is not the primary path.

**Relayed from `F14-foundation-role-taxonomy`, 2026-08-02. Fork: both answers
were defensible and they changed what this ticket ships.**

§9 currently tells a responder whose session was stolen to build the escalation
by hand: write a policy granting `auth/token/{accessors, lookup-accessor,
revoke-accessor}` with `sudo`, create a throwaway entity, attach it, use it,
then tear all three down in an order that matters (revoke by accessor before
deleting the user and entity, or a live orphan survives — measured at 30.6
days).

F14 shipped `vault_policy.admin` and `vault_identity_group.admin`, which cover
that escalation outright. Measured on 2026-08-02:

- The live `default` policy names **none** of the three accessor paths, so
  nothing shadows `admin`'s `path "*"` on them. Vault matches most-specific
  first, so an exact path in `default` would otherwise cap the holder there.
- A `default`-only token is denied `vault list auth/token/accessors`; an
  `admin` token is allowed. That endpoint is `sudo`-protected, so this also
  confirms the `sudo` reaches.
- `vault_identity_group.admin` sets `external_member_entity_ids = true`, so
  membership is a `vault write` that **survives `terraform apply`** — proven
  against an apply that really writes the group, not a no-op.

That last point is the sharp one. §9 already warns that a `terraform apply`
mid-incident silently strips the hand-built grant, because
`developer_group.tf` manages `policies` as a fixed list. `admin` membership has
no such failure mode.

**The trade, stated honestly.** `admin` is `path "*"` plus `sudo` — the
responder gets root-equivalent for the duration. The throwaway grants exactly
three capabilities. Anyone who wants the narrow grant during an incident has a
real argument, and it is not mine to settle.

*Recommendation:* **use `admin`.** It removes six commands, a teardown order
whose mistakes leave live credentials behind, and a documented hazard where an
unrelated apply disarms the responder mid-incident. It does not lower anyone's
ceiling: `developer` can already self-elevate, which is the only reason the
throwaway procedure works at all. Keep the throwaway in the doc as the fallback
for anyone not in `admin`, and add the one property `admin` does not have:
joining it is invisible to every plan, so leaving afterwards is a habit rather
than a gate (`docs/cluster-roles.md` says so).

**The dependency edge is now real.** `F14-foundation-role-taxonomy` was added
to `depends_on` when this question resolved, so §9's `admin` procedure cannot
be implemented before the role it depends on exists.

## What this ticket settled for F11

F7 was retired on 2026-08-01 and its artifacts moved to `.loop/archive/`;
`F11-foundation-human-read-role` replaces it and is `done` with a signed eval
marker. Three things this plan established fed into it, each verified here
rather than assumed:

1. **The login method is `userpass`, not OIDC.** Operator decision, shipped by
   F2 on 2026-07-31.
2. **`nomad/creds/deploy` and `consul/creds/deploy` read are the minimum for
   `localstack login` to work.** F11 grants exactly those two paths, as exact
   names rather than `nomad/creds/*` — so a client brokering any other role
   will 403 by design.
3. **The 32-day token TTL is the design, not a defect.** Measured here:
   `ttl = 2764799`. It is the refresh token; the 30-minute brokered creds are
   the access tokens. The `token_ttl` task once handed to F7 was withdrawn on
   that basis and F11 does not carry it.

## Eval marker

`.loop/config.json` sets `require_eval: true`, so the loop refuses pickup
until `.loop/evals/D2-cli-login-broker-tokens.md` exists with a
`signed-off-by` line. Co-author it with the `create-eval` skill and get
operator sign-off. This ticket does not author it.

Four guardrails belong in that eval, because prose alone leaves them
wobbly: `env` must emit both Consul variable names, `logout` must revoke
before it deletes, `token` must fail closed with empty stdout, and
`login` must warn when `$VAULT_TOKEN` shadows the session.

## 12. Design locked, 2026-07-31

The operator settled Q1, Q3, Q4 and Q6 in one sitting. This section is the
shape those answers add up to, so an implementer does not have to reassemble
it from four question blocks.

### The model

`gcloud`, mapped onto Vault. One long-lived credential the human holds, and
short-lived service credentials refreshed from it without the human noticing.

```
Vault token       32 days, renewable    -> ~/.vault-token (0600)
  |                                        + session.json
  +- nomad/creds/deploy     30 min       -> refreshed by the shim
  +- consul/creds/deploy    30 min       -> refreshed by the shim
```

### How each CLI gets its token

**Corrected 2026-07-31, after measurement.** The table this section first
carried exempted `vault` and `consul` from needing a shim. Both exemptions
were wrong, both in the direction of silent failure, and
`D6-cli-deps-and-shims` copied the wrong table verbatim and has since
corrected it (`.loop/plans/D6-cli-deps-and-shims.md:84-88`). The full
measurements are in
§4, "How each CLI picks up a credential". This is the corrected table:

| CLI | Credential file? | Precedence | Needs a shim? |
| --- | --- | --- | --- |
| `vault` | `~/.vault-token` | **env `VAULT_TOKEN` wins**, and the devcontainer injects a root token into every shell | **yes** |
| `consul` | `CONSUL_HTTP_TOKEN_FILE` | **file wins** over `CONSUL_HTTP_TOKEN`, and a missing file is a hard error | **yes**, and set no file |
| `nomad` | none. `NOMAD_TOKEN_FILE` does not exist | env `NOMAD_TOKEN` only | **yes** |

`CONSUL_HTTP_TOKEN_FILE` is not the harmless piece of configuration this
section first called it. It is a credential path whose *contents* outrank the
environment, so a stale file silently beats every fresh token, and whose
*absence* makes `consul` refuse to run at all rather than fall back. D2 does
not set it and does not write the file it names; see R12, which also carries
what D6 must change.

`~/.vault-token` still gets written (Q4, R11) because it is what `vault
login` writes and it becomes load-bearing when F8 removes the injected
`VAULT_TOKEN`. It is inert until then, and R11's stderr warning is what
keeps that fact visible instead of silent.

### The shim contract

```bash
# ~/.localstack/bin/nomad
#!/usr/bin/env bash
T="$(localstack token nomad 2>/dev/null)" || exec /usr/bin/nomad "$@"
exec env NOMAD_TOKEN="$T" /usr/bin/nomad "$@"
```

The same shape serves all three, changing only the service name, the
variable and the real binary: `VAULT_TOKEN` with `/usr/bin/vault`,
`CONSUL_HTTP_TOKEN` with `/usr/bin/consul`. `exec env VAR=...` is what makes
the `vault` shim work where the credential file does not: it overrides the
inherited variable for that one call.

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

### Why there is no `ui consul`

An earlier draft shipped one. It is cut, and this records why so nobody
re-adds it.

**It is outside the operator's locked surface.** `ROADMAP.md`'s locked
command-surface block (by name, not line — the file has uncommitted edits)
fixes D2's surface at
`login | logout | whoami | env | token <svc> | config`, and folds `ui consul`
into `service consul --open`, which belongs to D3.

**Its stated premise was false.** The command existed to broker a Consul token
and hand it to you for the UI, on the reasoning that Consul's OIDC auth method
is Enterprise-only so "pasting a token is the only route". The first half is
true; the conclusion does not follow. Measured 2026-08-01:

```
services with NO token:            25
services with the brokered token:   2
UI reachable with no token:        200
```

`bootstrap/roles/consul_server/templates/consul.hcl.j2:29-32` sets
`tokens { default = <agent token> }`, so unauthenticated requests run as the
agent and see everything. An explicit token **replaces** that default rather
than merging, and the `deploy` policy grants service read on `minio` and
`postgres-db` only — so the command would have cut the catalog from 25
services to 2. It degraded the thing it claimed to enable.

**The real finding is not about the command.** Consul authenticates nobody
here, and this holds through the edge as well as directly:
`https://consul.lab.orangecluster.nl/v1/catalog/services` returns the full
catalog over TLS with no credential. So closing port 8500 is not "its only
control" — there are two paths, and the edge is one of them. Out of scope for
this ticket, recorded in the roadmap's known gaps, and it needs an owner.
### What this does NOT settle

`localstack env` still has a place for `just` recipes and CI, where a shim on
PATH may not be present. Q3 chose the shim as the developer surface, not as
the only surface. Do not make the recipes depend on a shim being installed.

`env` is **not** optional, and R5 is not a hedge. Two things depend on it that
the shim cannot do. `terraform` is never shimmed, so the justfile bridge
`CONSUL_HTTP_TOKEN=${CONSUL_TOKEN}` needs both Consul names refreshed in the
shell. And `eval "$(localstack env)"` is the only move that overwrites the
devcontainer's injected root `VAULT_TOKEN` for a whole shell, which is what
R11's warning points the developer at.

### Command surface, settled 2026-07-31

The operator fixed the CLI's whole command surface on the same day as §12's
decisions. Two commands land in this ticket that were not in its original
`login|logout|whoami|env` scope. Each now has a requirement, a file, tests
and a place in the build order; this list is the index:

- **`localstack token <svc>`** — R10, `commands/token.py`, tests 16 and 17,
  subticket 8. The shim's backend, so the strict stdout contract and the
  fail-closed behavior are requirements, not style.
- **`localstack config`** — R13, `commands/config.py`, test 22, subticket 9.
  Addresses and edge domain, never a secret. It lands here rather than in D1
  because this ticket already resolves `vault_addr` and already owns the
  session file.

`login` also writes `~/.vault-token`, per Q4 as re-decided, and `logout`
removes it. R11 carries that, plus the stderr warning that keeps the write
from being a silent lie while the devcontainer injects a root `VAULT_TOKEN`.

§1, §2, §5, §7, §8 and §10 were rewritten to carry these three commands.
The frontmatter `summary` was updated. Before that pass this section was the
only place they existed, and the plan could not be built to its own eval.

Machine setup, meaning installing the pinned CLI binaries and the shims
themselves, is **not** this ticket. See `D6-cli-deps-and-shims`. What D2 owes
D6 is `localstack token`, the corrected shim table above, and R12's
instruction to drop the `CONSUL_HTTP_TOKEN_FILE` export.

The eval marker's signature was cleared and re-signed: it was first signed
against the four-command scope before these decisions.

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
