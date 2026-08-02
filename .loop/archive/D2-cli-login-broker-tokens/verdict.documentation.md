---
verdict: pass
tree: 1e32a12139e2e4c07ae0c9e63cb5f53f6aad789f
---

# D2 documentation review (re-bind)

Both required fixes from the previous pass are closed, all three
lower-severity notes are closed, and none of the eleven defect fixes
landed since then falsifies a sentence in the docs. A reader following
`docs/cli-login.md`, `docs/vault-human-auth.md`, `docs/cluster-roles.md`
or `README.md` today gets the current behavior.

Two user-visible behaviors this diff added are not written down anywhere.
Neither contradicts a doc, both announce themselves on stderr at the
moment they happen, and both sit inside a conditional the docs already
scope correctly. They are recommendations, not required fixes.

Scope check: `git diff --name-only 1e32a12... -- . ':!.loop'` is empty, so
every file quoted below is byte-identical to the tree this verdict binds
to.

## Required fixes from the previous verdict: both closed

### 1. `docs/cli-login.md` quickstart now runs

`docs/cli-login.md:8` opens with

```sh
localstack login --vault-addr https://vault.lab.orangecluster.nl
```

and `:16-30` explains why the flag is not optional: the devcontainer's
`VAULT_ADDR` is plaintext and non-loopback, Vault's listener sets
`tls_disable`, `login` refuses before it prompts, `--insecure` is the
override, loopback is exempt, and N4 retires the flag.

Every load-bearing claim in that section checks out:

- The refusal text quoted at `:22-24` is byte-exact against the live
  output. Run from this worktree:
  `uv run --project cli localstack login < /dev/null` prints those three
  lines and exits 1. Source is `cli/src/localstack_cli/auth/vault.py:60-64`.
- `VAULT_ADDR=http://192.168.2.30:8200` in the running container, so the
  address named at `:17-18` is the real one.
- `tls_disable = true` at
  `bootstrap/roles/vault_server/templates/vault.hcl.j2:20`.
- The loopback exemption and the `--insecure` stderr warning are
  `vault.py:30-48` and `:57-65`, called from
  `cli/src/localstack_cli/commands/login.py:82-87`.
- `.devcontainer/.env` exists (gitignored, per `.gitignore:2`) and
  `.devcontainer/devcontainer.json:38-39` passes it as `--env-file`, so
  both anchors at `:28` and `:75` resolve.

### 2. `README.md:26` describes the post-D2 world

> | CLI | `cli/` | Python — the `localstack` cockpit. `login`, `logout`,
> `whoami`, `env`, `token` and `config` today; the read commands are D3 |

Matches `localstack --help`, which lists exactly those six in that order,
registered at `cli/src/localstack_cli/main.py:42-51`.

## Recommendations from the previous verdict: all three closed

- The overclaim is gone. `docs/vault-human-auth.md:200-201` now says
  `docs/cli-login.md` "has the fast path: `localstack logout`, the
  accessor revoke, and what each one cascades to", which is what that
  page actually carries at `docs/cli-login.md:122-172`. The three items
  it does not carry are named on the vault page itself and pointed at
  from `docs/cli-login.md:184-187`.
- `localstack config` is documented at `docs/cli-login.md:68-70`. The
  claim that neither format leaks a token, accessor or password holds:
  `cli/src/localstack_cli/commands/config.py:35-59` builds one report
  dict from addresses, the session path, and `version`, `method`,
  `username`, `vault_addr` and `expires_at`. Both output branches read
  that dict and nothing else.
- The hardcoded count is gone. `docs/vault-human-auth.md:186-187` reads
  "every workload token on the cluster", and the accessor count is
  replaced by `vault list auth/token/accessors` at `:225-229`.

## The eleven fixes against the docs: no drift found

**`login` revokes the session it replaces** (`login.py:126-138`), and the
comment there records the ordering argument. No doc claims otherwise.
`docs/cli-login.md` never described repeat logins, so nothing was
falsified. See recommendation 1 below.

**`login` revokes its own token when brokering fails, and a failed login
leaves the existing session untouched** (`login.py:95-102` and
`:116-124`). `docs/cli-login.md:195-198` describes the 403 message only,
and that description still holds: the message names the denied path and
reads `identity_policies`, matching `broker.py:41-48,62-70`.

**`logout` refuses to delete an orphan `~/.vault-token`**
(`logout.py:44-52`). This is the one place I looked hardest for drift and
did not find it. `docs/cli-login.md:114-115` says logout "Calls
`auth/token/revoke-self` first, then deletes the session file and
`~/.vault-token`", which is exactly what the code does on the path the
sentence describes, the one where a session exists. Both pages already
gate that path on having the session:

- `docs/cli-login.md:127-128` reads "**1. `localstack logout`**, if you
  still have the session", and options 2 and 3 cover the other case.
- `docs/vault-human-auth.md:135-137` names logout, then immediately
  gives the manual path for "If you have the lost session's token but not
  its session file", which is the same remedy the new branch prints.

So no reader is told logout cleans up unconditionally.

**`whoami` reports the policy union.** `docs/cli-login.md:63-66` states
it, and the code agrees: `broker.py:104` stores
`vault.identity_policies(auth)` rather than `token_policies`,
`vault.py:165-179` merges `identity_policies` with `policies`, and
`whoami.py:36,61` prints what was stored.

**Both writers use `tempfile.mkstemp`** (`session.py:144-156`,
`vault_token_file.py:48-59`). The doc's only claim here is the `0600`
file at `docs/cli-login.md:48-49`, which mkstemp guarantees at creation.
Still true, and the mechanism was never documented, correctly.

**`cli/tests/auth/test_live_login.py` is new.** `CLAUDE.md` / `AGENTS.md`
says cluster tests carry the `cluster` marker and are excluded by
default. Still true: `test_live_login.py:22` sets
`pytestmark = pytest.mark.cluster` and `cli/pyproject.toml:34` sets
`addopts = "-m 'not cluster'"`.

**`CLAUDE.md` / `AGENTS.md` still needs no change.** Its CLI section
covers invocation mechanics and never enumerates commands, so six
commands do not falsify a word of it.

## Recommendations (not blocking)

### 1. LOW: login-replaces-login is undocumented

`login.py:138` calls `_revoke_previous`, which prints "revoked the
previous session for `<user>`." or, on failure, names the accessor
(`login.py:41-51`). A developer who logs in twice sees a line about
revocation that no doc mentions. The comment at `login.py:135-137` says
ten orphan tokens were found on the cluster during D2, so this is a real
behavior worth one sentence, probably next to the logout section at
`docs/cli-login.md:108-120`: logging in again ends the session it
replaces, and the new one is on disk before the old one dies.

Not required: nothing in the docs says the opposite, and the stderr line
is self-explanatory.

### 2. LOW: `logout` with no session file

The branch at `logout.py:44-52` prints the exact hand-revoke command and
exits 1 without touching `~/.vault-token`. It is the safe behavior and
the message is complete on its own. One line under
`docs/cli-login.md:119-120` would close the loop, saying that with no
session there is no token left to revoke the file with, so logout reports
it instead of deleting it. Both pages already scope logout to the
have-a-session case, so this is completeness rather than a correction.

### 3. LOW: one Consul claim is server-side only

`docs/cli-login.md:174-179` says Consul runs `ACLDownPolicy:
extend-cache`. Verified against the live server agent `firebat`
(`/v1/agent/self` reports `ACLTokenTTL: 30s`, `ACLDownPolicy:
extend-cache`), and Nomad's `TokenTTL` is 30s there too, so both numbers
in that paragraph are real. But
`bootstrap/roles/consul_client/templates/consul.hcl.j2:22` sets
`down_policy = "deny"` on client agents. The doc says "read off the live
agents", which holds for the servers and not for the clients. It errs
toward assuming the token survives longer, which is the right direction
for an incident runbook, so leave it unless someone wants the
server-versus-client split spelled out.

## Slop scan

**Layer 0 clean on both files.** No identity leaks, no `TODO`/`FIXME`/
`XXX`/`HACK`, no hallucinated anchors. Every backticked path and command
in `docs/cli-login.md` resolves: `.devcontainer/devcontainer.json`,
`.devcontainer/.env`, `docs/cluster-roles.md`,
`docs/vault-human-auth.md`, `roles.tf` (`external_member_entity_ids =
true` at `deployments/infrastructure/roles.tf:131`), the two creds paths
against `broker.py:25-26`, and the lifetimes at `docs/cli-login.md:54-55`
against `deployments/infrastructure/consul_deploy_role.tf:23-24` (1800 /
3600) and `bootstrap/roles/nomad_server/tasks/main.yml:309`
(`ttl=30m max_ttl=1h`).

**Layer 1: 6/6 for `docs/cli-login.md`.** Thesis in the first two lines,
no throat-clearing, 1281 words for the command a developer runs before
every deploy plus the runbook for losing it.

**Layer 2 for `docs/cli-login.md`: clean.** Em-dash density is now 3 per
1281 words, 2.3 per 1000, inside the target and down from 4.0 last pass.
Every line wraps at 80 or under. No double-dash substitution, no
semicolon splices, no tier-1 slop, no self-narration, no smart quotes, no
British spellings.

**Layer 2 for `docs/vault-human-auth.md`: three residues, all inside
added lines, all low confidence.**

- A semicolon splice at `:203`: "Prefer it; the hand-built policy above
  is the fallback for anyone who cannot join." Two independent clauses.
  A period or "and" reads the same.
- Two em-dashes added, at `:212` and `:218`. The page as a whole runs 18
  in 2901 words, about 6 per 1000, but most of those predate this diff
  and sit outside its hunks. Net change is plus one.
- The four lines over 80 columns (`:41-43`, `:152`) are all pre-existing.

**Layer 3: no unbacked quality claims** in either file.
