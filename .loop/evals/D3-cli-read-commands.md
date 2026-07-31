eval: D3-cli-read-commands

**Definition of Done:** eight read-only commands in three typer groups, split
into a `cli/localstack/api/` layer that imports neither typer nor rich and a
`cli/localstack/commands/` layer that renders it. Calls go over the HTTP APIs
with `httpx`, never `subprocess`. Table by default, `--json` everywhere, and a
failure path that distinguishes "not logged in" from "not allowed".

**Two verified facts drive most of these rows.** With a brokered
`nomad/creds/deploy` token, `GET /v1/jobs` returns **403** — the role
withholds `list-jobs` deliberately (`nomad_deploy_role.tf:4-5`). And with a
brokered `consul/creds/deploy` token, `GET /v1/catalog/services` returns
**2 of 25 services**, while the same call with **no token returns all 25**.
Consul ACL-filters silently and fires no error, so passing the token makes the
answer worse and nothing says so.

**The trap.** A table that renders is not a table that is true. Rows 5 and 6
exist because the natural implementation of `consul services` and
`vault grants` both produce confident, well-formatted, wrong output.

| Behavior | Input | Expected | Scorer | Threshold |
| --- | --- | --- | --- | --- |
| All eight commands exist and reach the right endpoint | `--help` on each group; then run each of the eight against a respx-mocked server | Exactly these eight: `nomad jobs`, `nomad job <id>`, `vault mounts`, `vault policies`, `vault policy <name>`, `vault grants <job>`, `vault kv [path]`, `consul services`. Each issues the API call the plan's table names, and no others | deterministic check (eight commands; endpoints match the table) | 100% |
| **The reuse contract D4 depends on holds** | `grep -rnE "^\s*(import\|from)\s+(typer\|rich)" cli/localstack/api/` | No match. The `api/` layer returns dataclasses and imports neither typer nor rich, so D4's TUI can import it without dragging in a CLI framework. This is the concrete interface D4 was planned against; if it breaks, D4 builds a second fetching layer | deterministic check (no typer/rich import under api/) | 100% |
| **No subprocess anywhere** | `grep -rnE "subprocess\|os\.system\|shutil\.which" cli/localstack/` | No match. The local binaries are a major version ahead of the servers (Nomad CLI 2.0.3 vs server 1.11.3, Vault 2.0.3 vs 1.21.4, Consul 2.0.1 vs 1.22.6) and an `rtk` shim rewrites shelled commands in this devcontainer, so shelling out makes behavior a function of the developer's machine | deterministic check (no subprocess/shell-out) | 100% |
| `--json` on every command, and it cannot drift | For each of the eight: run with `--json` and pipe to `jq -e .` | Valid JSON from all eight, emitting the command's own dataclass rather than a hand-built dict. A hand-built dict is how the JSON and the table diverge | deterministic check (all eight emit parseable JSON from the dataclass) | 100% |
| **`consul services` says the list is ACL-filtered** | `localstack consul services` with a brokered Consul token | The output carries a footer naming the token whose ACLs filtered the result. Verified live: the brokered token yields 2 services, no token yields 25, and no error fires either way. A bare table of 2 presented as "the services" is false, and the failure is invisible without this footer | deterministic check (footer present and names the filtering token) | 100% |
| **`vault grants` resolves the template and never hardcodes the accessor** | `localstack vault grants memex`; then `grep -rn "auth_jwt_649fd6cc" cli/` | Two columns: the raw template line and the resolved path, plus capabilities. The mount accessor is discovered by regex over the fetched policy text, and the literal `auth_jwt_649fd6cc` appears NOWHERE in the source — it is derived at bootstrap (`nomad_server/tasks/main.yml:253-255`) and differs per rebuild. The policy text is fetched at runtime, never embedded | deterministic check (both columns present; accessor absent from source) | 100% |
| **`vault grants` survives both policy shapes** | Fixture tests against the six-block live policy AND F9's three-block template | Both render without error and resolve the job-scoped paths. F9 is merged but unapplied, so the repo template has three `path` blocks while live Vault still serves six. Code that assumes either count breaks on the other, and the switchover happens the moment the operator applies F9 | deterministic check (both fixtures render correctly) | 100% |
| **An unfillable template variable stays visible** | Feed `vault grants` a policy fixture containing a variable the command cannot substitute | The row renders with the `{{...}}` intact and is marked as unresolved. Silently dropping or blanking an unknown variable produces a resolved-looking path that is wrong, which is worse than an obviously incomplete one | deterministic check (unknown variable visible and flagged) | 100% |
| `vault grants` does not claim to be an authorization decision | Read the command's output | A one-line footer states the view is rendered from policy text, not an authorization decision. Vault resolves templates per request against the calling entity; this command resolves them from arguments | deterministic check (footer present) | 100% |
| **"Not allowed" is distinguished from "not logged in", per service** | Three cases: (a) no session at all; (b) valid Vault token, then `nomad jobs` under a brokered `deploy` token; (c) valid token, `vault mounts` without the grant | (a) every command exits non-zero saying run `localstack login`. (b) 403 on `/v1/jobs` while `/v1/job/<known>` succeeds is reported as "the token lacks `list-jobs`", naming the policy, and does **not** tell the user to log in, because logging in again changes nothing. (c) `auth/token/lookup-self` returns 200 so the session is live; the message names the denied path. Telling a developer to re-login when the real problem is a missing grant sends them in a circle | model + rubric (adversarial review agent) | 5/5 |
| The default test suite is offline | `cd cli && uv run pytest` with `VAULT_ADDR`/`NOMAD_ADDR`/`CONSUL_HTTP_ADDR` pointed at unroutable addresses | Green, and no outbound request. HTTP is mocked with respx at the fetcher layer; any test touching the real cluster carries the `cluster` marker and is excluded via `addopts` | deterministic check (suite green and offline with junk addresses) | 100% |
| **Guardrail: read-only** | `grep -rnE "\.(post\|put\|delete\|patch)\(" cli/localstack/api/`; review the diff | No mutating HTTP verb anywhere in the API layer, no Terraform change, no Vault policy authored. This ticket reads; the read-role gap it found is relayed to D2, not fixed here | deterministic check (no mutating verbs; no `deployments/**` changes) | 100% |
| The repo gate passes | `just worktree_setup <path>`, then `just pre_commit` | All Passed, including ruff, mypy and pytest | deterministic check (`just pre_commit` all Passed) | 100% |

signed-off-by: JasperHG90 2026-07-31
