eval: OV3-openviking-vault-identity

**Definition of Done:** jasper and veerle each authenticate to OpenViking with a
Vault identity token carrying their entity name, no API key is involved in that
path, and a token that does not name a real person is refused rather than landed
somewhere shared.

**Sign-off is delegated, and that is visible on purpose.** The operator wrote
"Goal set: implement this. I'm not here so you are in control of the loop"
(2026-09-07) and was absent for the whole authoring session. No human read these
rows. The sign-off line records the grant rather than a name, so nobody later
mistakes this marker for a reviewed one. Same form as OV1's settled forks.

**Most rows need a deployed service.** `scripts/check_openviking_config.py:25`
says in its own docstring that nothing here exercises one, so a green
`just pre_commit` says nothing about rows 1-7 or row 9. Rows 8 and 10 are the
only ones a gate covers, and row 7 is the only live-ish row that runs BEFORE the
flip, against a local container rather than the cluster.

**Row 2 is the one that silently breaks everything.** OpenViking compares `iss`
exactly. A near-miss string authenticates nobody and looks like a network fault.

**Hermes is deliberately NOT scored.** It authenticates with jasper's derived key
and breaks the moment `auth_mode` flips; repairing it is a follow-up ticket. A
row asserting Hermes still works would fail by design, and one asserting it is
broken would score the damage rather than the feature.

| Behavior | Input | Expected | Fails-when | Scorer | Threshold |
|----------|-------|----------|------------|--------|-----------|
| A person logs into Vault and mints a token for themselves | `vault login -method=userpass username=veerle`, then `vault read identity/oidc/token/<role>` | A JWT comes back. Decoded, it is RS256 and carries a non-empty `sub`, `iss`, `aud` and the entity-name claim | The same read run by a token with no grant on `identity/oidc/token/<role>`, which must 403 rather than mint | Human, against the live cluster | 100%, both people |
| The issuer string OpenViking trusts equals the one Vault stamps | Decode `iss` from a freshly minted token; read `server.oidc.issuer` from the deployed `ov.conf.json` | The two are byte-for-byte identical, and both read `https://vault.lab.orangecluster.nl/v1/identity/oidc` | Either string carries a trailing slash, a path Vault rejects, or the raw `192.168.2.30:8200` form | Human, against the live cluster | 100% |
| The audience matches the role's client id | Decode `aud` from the token; read `server.oidc.audience` from `ov.conf.json` | Identical, and both equal the literal `client_id` set explicitly on the role rather than one Vault generated | `client_id` left unset on the role, so Vault generates one and the config's literal goes stale silently | Human, against the live cluster | 100% |
| A person's identity reaches OpenViking as their own account | `GET /api/v1/fs/ls?uri=viking://` with veerle's token | HTTP 200, and the listing is veerle's tree, not jasper's and not `default`'s | The mapping reads `sub`, which is the entity UUID, so the account id becomes a UUID while still returning 200 | Human, against the live cluster | 100%, both people |
| **Guardrail:** a token with no entity-name claim is refused, not shared | A token minted from a role whose template omits the claim | HTTP 401/403. The caller must NOT land in the pre-existing `default` account, which exists live with `user_count` 0 | `identity.account_id.fallback` left at upstream's `"default"`, which turns this refusal into a silent shared-account login | Human, against the live cluster | 100% |
| **Guardrail:** a token naming no real person is refused | A token for a scratch entity whose name matches no OpenViking account, minted then deleted in the same run | Refused on a data route. Whatever the status, it is the same for a read and a write | The unknown name is accepted and a tree is created for it, which would make every typo a new account | `scripts/ov_identity_probe.py` (R9), operator-run | 100% |
| **Guardrail:** a foreign audience is refused | A token minted from a second role carrying a different `client_id` | HTTP 401. Audience verification is never skipped | `audience` absent from `ov.conf.json`, which upstream refuses to start without — so a passing row here with no audience configured means the probe is not reaching the server | `scripts/ov_identity_probe.py` (R9), operator-run | 100% |
| An account whose directory tree was never initialized is settled either way | Local run of the pinned `v0.4.17.1` image in `trusted` mode with a root key, asserting `X-OpenViking-Account: neverseen`; then one read and one write | A recorded answer, not a guess: either both succeed (no provisioning needed) or the failure names what is missing. Plan P15 stops being UNCERTAIN | Run against the deployed server instead, where the api-key path always verifies existence and root is refused on data routes, so the result says nothing | Human, local container, BEFORE the flip | 100% (the question is answered, not that it answers yes) |
| `terraform apply` completes on the flip | A full apply of `deployments/applications` with `ov.conf.json` moved to `auth_mode: "oidc"` | Apply succeeds. The `openviking_users` provisioner, whose `jobspec` trigger re-runs it on any `ov_conf` change, does not exit 1 against a server now in `oidc` mode | The provisioner left as-is: its account-creation curl 401s (it sends no bearer token), the guard exits 1, and the apply fails outright | Human, against the live cluster | 100% |
| **Guardrail:** the config checker fails a broken oidc block | `ov.conf.json` mutated three ways: `auth_mode` back to `"api_key"`; the issuer given a trailing slash; `identity.account_id.fallback` set to `"default"` | `scripts/check_openviking_config.py` exits non-zero on each, naming the offending key | Only the presence of `server.oidc` is asserted, so every mutant above still passes | Deterministic (`just pre_commit`, plus the script's `--self-test`) | 100%, all three mutants |
| The rename does not break the CLI suite | `uv run pytest` in `cli/`, default markers, after `operator` becomes `jasper` | Green. `cli/tests/commands/test_auth_commands.py:252` and `:279` and `cli/tests/fixtures/cluster.py:85` assert the new name | The rename lands in Terraform only, leaving the three default-run assertions on the old name | Deterministic (`uv run pytest`) | 100% |

signed-off-by: coordinating agent under an explicit grant of loop control from JasperHG90, operator offline, no human reviewed these rows 2026-09-07
plan: 1eba564dd42e31ecee81c2763300ef8e505fb0c527064daf88721147b8c56959
