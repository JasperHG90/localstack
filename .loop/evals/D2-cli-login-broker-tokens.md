eval: D2-cli-login-broker-tokens

**Definition of Done:** `localstack login|logout|whoami|env` authenticate a
developer against Vault's `userpass` backend, eagerly broker
`nomad/creds/deploy` and `consul/creds/deploy` from that session, cache all
three in one `0600` file with absolute expiries, and expose them as shell
exports. Purely a client: it authors no Terraform and no Vault policy.

**Two states of the world, and the marker must score both.** F2 is committed
on a branch, unmerged and unapplied, so `auth/userpass` does not exist on the
live cluster yet. And F2's operator user ships `token_policies = []`, so even
once applied, a successful login yields a `default`-policy token and **every
broker call 403s** until F7 grants the creds reads. Rows 1-9 are offline and
runnable today. Rows 10-12 need F2 applied. **Row 4 is the one that matters
most right now**: the 403 is the expected result, and the ticket's value is
that it says so precisely instead of failing obscurely inside a later
`terraform apply`.

**The trap.** This ticket handles credentials, so the tempting rows ("a token
came back", "login succeeded") are exactly the ones that pass while something
leaks or expires wrong. Rows 5, 6, 7 and 9 are the ones that can actually
fail.

| Behavior | Input | Expected | Scorer | Threshold |
| --- | --- | --- | --- | --- |
| **Refuses to send a password in the clear** | `localstack login --vault-addr http://192.168.2.30:8200` with no `--insecure` | Exits NON-ZERO before prompting, and the message names the HTTPS edge `https://vault.lab.orangecluster.nl`. Grounded in `tls_disable: true` on the Vault listener and today's `VAULT_ADDR=http://192.168.2.30:8200`. Loopback `http://` is allowed; a non-loopback `http://` is not | deterministic check (non-zero exit, no prompt, edge named) | 100% |
| `--insecure` is the only way past, and is loud | Same address with `--insecure` | Proceeds, and a warning goes to STDERR (not stdout). If it proceeded silently the guard would be decorative | deterministic check (proceeds; warning on stderr) | 100% |
| An unsupported method is rejected, not ignored | `localstack login --method oidc` | Exits non-zero with "unsupported method". The flag exists so a later OIDC login reuses this interface; silently falling back to userpass would hide that it is unimplemented | deterministic check (non-zero exit, message names the method) | 100% |
| **A 403 on a creds path names the cause** | With a session whose Vault token lacks the creds grants (today's expected state), run `localstack login` | Login itself succeeds; brokering fails with a message naming (a) which creds path was denied, (b) the login token's actual policies as read from `auth/token/lookup-self`, and (c) that the grant is F7's ticket. Exit non-zero. **This is the state of the world at implementation time**, so it is the message a developer will actually see | model + rubric (adversarial review agent) | 5/5 |
| **The cache file cannot be read by anyone else** | After a login, `stat -c '%a'` the session file and its directory | File `600`, directory `700`. The path is `${XDG_CONFIG_HOME:-$HOME/.config}/localstack/session.json` and is NOT inside the repo tree. Verify it was created via temp-file-plus-rename with the mode set at creation, so it is never briefly world-readable: a chmod after write leaves a window | deterministic check (0600 file, 0700 dir, no world-readable window) | 100% |
| **`logout` REVOKES before it deletes** | With a live session: capture the Vault token accessor, run `localstack logout`, then check the accessor server-side | `auth/token/revoke-self` is called BEFORE the file is deleted, and the accessor is gone afterwards. Revoking the parent kills the child Nomad and Consul leases with it. Deleting the file alone would leave live tokens on the cluster for up to an hour, which is the failure this row exists to catch. If revocation fails, the file is still deleted AND the un-revoked accessors print to stderr with a non-zero exit | deterministic check (revoke precedes delete; accessor invalid after) | 100% |
| **`env` emits BOTH Consul variable names** | `localstack env` | Emits `VAULT_TOKEN`, `NOMAD_TOKEN`, and **both** `CONSUL_HTTP_TOKEN` and `CONSUL_TOKEN` set to the same brokered value. The repo reads both names: `deployments/infrastructure/justfile:8,12,16` and `docs/monitoring.md:153` use `CONSUL_HTTP_TOKEN`, the developer shell exports `CONSUL_TOKEN`. Emitting one breaks half the tooling silently | deterministic check (all four exports present, both Consul names equal) | 100% |
| `env` output stays evaluable | `eval "$(localstack env)"` with a stale entry forcing a refresh | Succeeds. Every diagnostic went to stderr; stdout contains only `export` lines. A single log line on stdout makes `eval` execute garbage | deterministic check (`eval` succeeds; stdout is exports only) | 100% |
| **No token value ever reaches stdout except through `env`** | Run `login`, `whoami`, `logout` and every error path; capture stdout and stderr; grep for the token values and for `hvs.`/`hvo_` prefixes | No match anywhere except `env`'s own output. `whoami` reports username, `entity_id`, policies, TTLs, accessors and lease ids, and NEVER a token value. Also assert the password never appears in the cache file, any log line, or any error message | deterministic check (token/password absent from all output but `env`) | 100% |
| **A real login yields an entity-bearing token** *(needs F2 applied)* | `localstack login`, then `whoami` | Succeeds and reports a NON-EMPTY `entity_id`. This is the property F2's userpass backend exists to provide; the bootstrap root token has an empty one, so a row that only checks "a token came back" would pass against a token that cannot be gated on identity | deterministic check (non-empty entity_id) | 100% |
| Expiries are absolute and per credential *(needs F2 applied)* | Read the cache after a login | Three separate entries, each with an absolute ISO8601 `expires_at` computed from that response's `lease_duration` at receipt, plus `renewable` read from the response rather than assumed. They differ: Consul caps at `max_ttl 3600` (`consul_deploy_role.tf:24`), Nomad at `1h` (`nomad/config/lease`), the Vault token at its own TTL. A single shared expiry would be wrong for at least two of the three | deterministic check (three entries, distinct absolute expiries, renewable from response) | 100% |
| Stale brokered credentials are RE-BROKERED, not renewed *(needs F2 applied)* | Force a brokered entry within the 5-minute skew, then run a command needing it | The brokered entry is re-brokered from Vault; the Vault token itself is renewed via `auth/token/renew-self` when it is within skew and renewable. Brokered leases cap at `max_ttl`, so renewing them buys at most one window and then fails anyway. Superseded leases are left to expire, because per-lease revocation needs `sys/leases/revoke`, which the `default` policy does not grant | model + rubric (adversarial review agent) | 4/5 |
| **Guardrail: this ticket authors no policy and no Terraform** | `git diff --stat` over the branch | No changes under `deployments/`, no `.tf` file, no Vault policy document. The deployer policy is F7's, and this ticket's whole design is to be the client that tells F7 what it needs. A diff that "helpfully" adds the grant has taken F7's decision | deterministic check (no `deployments/**` or `.tf` changes) | 100% |
| The repo gate passes | `just worktree_setup <path>`, then `just pre_commit` | All Passed, including the ruff, mypy and pytest hooks D1 added. The default `uv run pytest` stays offline: any test touching the live cluster carries the `cluster` marker and is excluded via `addopts` | deterministic check (`just pre_commit` all Passed; default suite offline) | 100% |

signed-off-by: PENDING
