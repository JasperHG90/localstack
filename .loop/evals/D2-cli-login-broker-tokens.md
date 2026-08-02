eval: D2-cli-login-broker-tokens

**Amended 2026-07-31** after the operator settled the token surface. Three
commands were added (`token`, `config`), `login` now writes
`~/.vault-token`, and the shim in D2 §12 depends on `token` behaving exactly
as row 14 requires. Everything else stands; the rows below were never about
the command list.

**Definition of Done:** `localstack login|logout|whoami|env|token|config`
authenticate a developer against Vault's `userpass` backend, eagerly
broker `nomad/creds/deploy` and `consul/creds/deploy` from that session, cache
all three in one `0600` file with absolute expiries, write `~/.vault-token`,
say out loud when the environment's `VAULT_TOKEN` overrides it, and expose the
tokens as shell exports and to the PATH shims. Purely a
client: it authors no Terraform and no Vault policy.

**Corrected 2026-07-31: F2 is applied.** This marker previously said F2 was
committed on a branch, unmerged and unapplied, and that `auth/userpass` did not
exist. It was merged and applied the same day. `vault auth list` now returns
`jwt-nomad/`, `token/` and `userpass/`, and the `operator` entity is live at
`351f302a-…`. **The rows marked *(live)* are runnable now**, and the plan's §8
was rewritten to run them rather than record them as blocked.

**Corrected 2026-07-31: writing `~/.vault-token` does NOT hand the stock
`vault` CLI the session.** Measured: `VAULT_TOKEN` in the environment outranks
the file, and `.devcontainer/devcontainer.json:38-39` injects
`.devcontainer/.env`, whose `:8` sets `VAULT_TOKEN` to the bootstrap root
token, into every shell in the container. So the file is inert until F8
removes that variable, and F8 is `blocked`. Row 16 was rewritten to score what
is actually true, and **row 17 was added to catch the failure this creates**: a
developer who ran `localstack login`, believes they are `operator`, and is
still root. That row is the highest-value addition to this marker since the
Consul naming row.

**What has NOT changed is the 403.** F2's operator user ships
`token_policies = []`, so a successful login yields a `default`-policy token
and **every broker call 403s** until `F11` grants the creds reads. `F11`
was applied on 2026-08-01, so on the live cluster these rows now pass rather
than documenting a 403; run them against a fresh `userpass` user with no group
membership to exercise the failure path. Verified
against the operator's own token on 2026-07-31: `secret/data/*`,
`sys/policy`, `identity/entity/id` and `auth/userpass/users` all returned
`["deny"]`. **That measurement is now historical.** `F11` applied on
2026-08-01 and grants every one of those paths to the `developer` group the
operator entity belongs to, so the live answers are no longer `deny`.

**The 403 row still matters, but it must be driven differently.** Exercise it
against a scratch `userpass` user with an entity in no group, **deleted together with its entity and alias when the row completes** — not against
`operator`, which now succeeds. The ticket's value is unchanged: it names the
missing grant precisely instead of failing obscurely inside a later
`terraform apply`.

**The trap.** This ticket handles credentials, so the tempting rows ("a token
came back", "login succeeded") are exactly the ones that pass while something
leaks or expires wrong. Rows 5, 6, 7, 9 and 17 are the ones that can actually
fail. Row 17 is the sharpest of them, because the behavior it forbids looks
like success from the developer's chair.

| Behavior | Input | Expected | Scorer | Threshold |
| --- | --- | --- | --- | --- |
| **Refuses to send a password in the clear** | `localstack login --vault-addr http://192.168.2.30:8200` with no `--insecure` | Exits NON-ZERO before prompting, and the message names the HTTPS edge `https://vault.lab.orangecluster.nl`. Grounded in `tls_disable: true` on the Vault listener and today's `VAULT_ADDR=http://192.168.2.30:8200`. Loopback `http://` is allowed; a non-loopback `http://` is not | deterministic check (non-zero exit, no prompt, edge named) | 100% |
| `--insecure` is the only way past, and is loud | Same address with `--insecure` | Proceeds, and a warning goes to STDERR (not stdout). If it proceeded silently the guard would be decorative | deterministic check (proceeds; warning on stderr) | 100% |
| An unsupported method is rejected, not ignored | `localstack login --method oidc` | Exits non-zero with "unsupported method". The flag exists so a later OIDC login reuses this interface; silently falling back to userpass would hide that it is unimplemented | deterministic check (non-zero exit, message names the method) | 100% |
| **A 403 on a creds path names the cause** | With a session whose Vault token lacks the creds grants (the state for a user in NO identity group — `F11` applied on 2026-08-01, so `operator` itself now brokers successfully and cannot drive this row), run `localstack login` | Login itself succeeds; brokering fails with a message naming (a) which creds path was denied, (b) the login token's actual policies as read from `auth/token/lookup-self`, and (c) that the grant is `F11`'s ticket. **Report `identity_policies`, not `policies`** — F11 binds through a group, so the granted policy lands in the former while `policies` holds only `default`; a message reading `policies` tells the developer they have no grants when they do. Exit non-zero. **This is the state for a group-less scratch user; create one to exercise it**, so it is the message a developer will actually see | model + rubric (adversarial review agent) | 5/5 |
| **The cache file cannot be read by anyone else** | After a login, `stat -c '%a'` the session file and its directory | File `600`, directory `700`. The path is `${XDG_CONFIG_HOME:-$HOME/.config}/localstack/session.json` and is NOT inside the repo tree. Verify it was created via temp-file-plus-rename with the mode set at creation, so it is never briefly world-readable: a chmod after write leaves a window | deterministic check (0600 file, 0700 dir, no world-readable window) | 100% |
| **`logout` REVOKES before it deletes** | With a live session: capture the Vault token accessor, run `localstack logout`, then check the accessor server-side | `auth/token/revoke-self` is called BEFORE the file is deleted, and the accessor is gone afterwards. Revoking the parent kills the child Nomad and Consul leases with it. Deleting the file alone would leave live tokens on the cluster for up to an hour, which is the failure this row exists to catch. If revocation fails, the file is still deleted AND the un-revoked accessors print to stderr with a non-zero exit | deterministic check (revoke precedes delete; accessor invalid after) | 100% |
| **`env` emits BOTH Consul variable names** | `localstack env` | Emits `VAULT_TOKEN`, `NOMAD_TOKEN`, and **both** `CONSUL_HTTP_TOKEN` and `CONSUL_TOKEN` set to the same brokered value. The repo reads both names: `deployments/infrastructure/justfile:8,12,16` and `docs/monitoring.md:153` use `CONSUL_HTTP_TOKEN`, the developer shell exports `CONSUL_TOKEN`. Emitting one breaks half the tooling silently | deterministic check (all four exports present, both Consul names equal) | 100% |
| `env` output stays evaluable | `eval "$(localstack env)"` with a stale entry forcing a refresh | Succeeds. Every diagnostic went to stderr; stdout contains only `export` lines. A single log line on stdout makes `eval` execute garbage | deterministic check (`eval` succeeds; stdout is exports only) | 100% |
| **No token value reaches stdout except through `env` and `token`** | Run `login`, `whoami`, `logout`, `config` and every error path; capture stdout and stderr; grep for the token values and for `hvs.`/`hvo_` prefixes | No match anywhere. The only two commands allowed to print a token are the two whose whole job is to emit one: `env` and `token`. `whoami` reports username, `entity_id`, policies, TTLs, accessors and lease ids, and NEVER a token value. Also assert the password never appears in the cache file, any log line, or any error message | deterministic check (token/password absent from all output but those two commands) | 100% |
| **A real login yields an entity-bearing token** *(live)* | `localstack login`, then `whoami` | Succeeds and reports a NON-EMPTY `entity_id`. This is the property F2's userpass backend exists to provide; the bootstrap root token has an empty one, so a row that only checks "a token came back" would pass against a token that cannot be gated on identity | deterministic check (non-empty entity_id) | 100% |
| Expiries are absolute and per credential *(live)* | Read the cache after a login | Three separate entries, each with an absolute ISO8601 `expires_at` computed from that response's `lease_duration` at receipt, plus `renewable` read from the response rather than assumed. They differ: Consul caps at `max_ttl 3600` (`consul_deploy_role.tf:24`), Nomad at `1h` (`nomad/config/lease`), the Vault token at its own TTL. A single shared expiry would be wrong for at least two of the three | deterministic check (three entries, distinct absolute expiries, renewable from response) | 100% |
| Stale brokered credentials are RE-BROKERED, not renewed *(live)* | Force a brokered entry within the 5-minute skew, then run a command needing it | The brokered entry is re-brokered from Vault; the Vault token itself is renewed via `auth/token/renew-self` when it is within skew and renewable. Brokered leases cap at `max_ttl`, so renewing them buys at most one window and then fails anyway. Superseded leases are left to expire, because per-lease revocation needs `sys/leases/revoke`, which the `default` policy does not grant | model + rubric (adversarial review agent) | 4/5 |
| **Guardrail: this ticket authors no policy and no Terraform** | `git diff --stat` over the branch | No changes under `deployments/`, no `.tf` file, no Vault policy document. The `developer` policy is `F11`'s, and this ticket's whole design is to be the client that tells F11 what it needs. A diff that "helpfully" adds the grant has taken F11's decision | deterministic check (no `deployments/**` or `.tf` changes) | 100% |
| **`token <svc>` emits the token and NOTHING else on stdout** | `localstack token nomad`, `localstack token consul`, `localstack token vault`; capture stdout byte for byte | Stdout is the token value and a single trailing newline. No banner, no timing line, no colour codes, no warning. Every diagnostic goes to stderr. This is the contract the PATH shim depends on: the shim does `T="$(localstack token nomad)"` and puts the result straight into `NOMAD_TOKEN`, so one stray character on stdout produces an invalid token and a 403 that looks like a permissions bug | deterministic check (stdout is exactly the token plus newline; diagnostics on stderr) | 100% |
| **`token <svc>` fails closed, with empty stdout** | Run with no session, and again with a session whose Vault token lacks the creds grant | Exits NON-ZERO and stdout is **empty** in both cases. The shim falls through to the bare binary on a non-zero exit; if the command exited zero, or printed an error message to stdout, the shim would export that message as the token. Failing closed with nothing on stdout is what makes the fall-through safe | deterministic check (non-zero exit; stdout empty; message on stderr) | 100% |
| **`login` writes `~/.vault-token` and `logout` removes it** | `localstack login`, then `stat -c '%a' ~/.vault-token` and read it; then `env -u VAULT_TOKEN vault token lookup`; then `localstack logout` | The file exists at mode `600` and holds the Vault token. Verify it works with `env -u VAULT_TOKEN`, **not with a bare `vault` command**: a bare `vault` reads the environment's token and would pass this row against the injected root token, proving nothing. After `logout` the file is **gone**, not left holding a revoked token, because the next `vault` command should fail with an honest "not logged in" rather than a confusing 403. Operator decision of 2026-07-31 (D2 Q4, as re-decided) | deterministic check (0600 file present, valid under `env -u VAULT_TOKEN`; absent after logout) | 100% |
| **A developer who logged in is TOLD they are still root** | In the devcontainer, with the injected `VAULT_TOKEN` present: run `localstack login`, then `whoami`, then `logout`; capture stderr each time. Then run `vault token lookup` and `eval "$(localstack env)"; vault token lookup` | Each of the three commands prints a warning to STDERR naming the mismatch: the environment's `VAULT_TOKEN` is set, differs from the session token, and a bare `vault` therefore runs as it and not as the session. The warning names the environment token's policies (`["root"]` today) when `lookup-self` on it succeeds, and names both ways out: `eval "$(localstack env)"` or the `vault` shim. `vault token lookup` before the `eval` reports `policies ["root"]`; after it, the `operator` entity. **Stdout is unpolluted by the warning.** With `VAULT_TOKEN` unset, or equal to the session token, NO such warning appears — one that fires on every healthy session trains the operator to ignore it. This row exists because `~/.vault-token` is inert while the devcontainer injects a root `VAULT_TOKEN` (`.devcontainer/devcontainer.json:38-39`, `.devcontainer/.env:8`) and F8, which would remove it, is `blocked`. Without the warning the CLI fails in the one direction that is never noticed: the developer believes they are `operator` and is root | model + rubric (adversarial review agent) | 5/5 |
| **`config` never prints a secret** | `localstack config` and `localstack config --json` with a live session | Shows addresses and the edge domain only. No token, no password, no `hvs.`/`hvo_` value, no contents of the session file beyond non-secret fields. `config` is the command a developer will paste into an issue when asking for help, which is precisely why it must be safe to paste | deterministic check (no secret material in either output form) | 100% |
| **Guardrail: nothing sets `CONSUL_HTTP_TOKEN_FILE` or writes the file it names** | `grep -r CONSUL_HTTP_TOKEN_FILE` over the branch diff | No match. Measured 2026-07-31: the file OUTRANKS `CONSUL_HTTP_TOKEN`, so a stale one silently beats every fresh token this CLI emits, and a MISSING one makes `consul` fail outright (`Error loading token file ...: no such file or directory`) rather than fall back. Both failures point the same way as row 17's: more trust in a credential than is warranted, with no error to notice. `consul` gets a PATH shim like `nomad` instead (D2 R12), and D6 must drop its planned static export | deterministic check (no occurrence in the diff) | 100% |
| The repo gate passes | `just worktree_setup <path>`, then `just pre_commit` | All Passed, including the ruff, mypy and pytest hooks D1 added. The default `uv run pytest` stays offline: any test touching the live cluster carries the `cluster` marker and is excluded via `addopts` | deterministic check (`just pre_commit` all Passed; default suite offline) | 100% |

signed-off-by: JasperHG90 2026-07-31

**Signature history, 2026-07-31.** First signed against a four-command scope.
Cleared when the operator added `token` and `config` and reversed the
`~/.vault-token` decision, then re-signed against those three new rows.
Cleared again and re-signed after the measurements that produced rows 16, 17,
18 and 20: `VAULT_TOKEN` outranks `~/.vault-token`, `CONSUL_HTTP_TOKEN_FILE`
outranks `CONSUL_HTTP_TOKEN` and is fatal when missing, and `config`
gained a requirement in the plan proper rather than living as design prose.
