eval: D3-cli-read-commands

**Rewritten 2026-07-31** against the operator's command-surface decision. The
previous version scored eight commands, six of which were `vault` and `nomad`
subcommands mirroring native CLI calls (`vault mounts`, `vault policies`,
`vault policy <name>`, `vault kv`, `nomad jobs`, `nomad job <id>`,
`consul services`). Those are cut. The cockpit does not restate what
`vault kv list` and `nomad job status` already do; it does what no native CLI
can, which is synthesize across Vault, Nomad, Consul and the edge.

Most rows below are unchanged, because they were never about which commands
exist: the `api/` purity contract, the no-subprocess rule, the `vault grants`
correctness rows, the offline suite and the read-only guardrail all still bite.

**Definition of Done:** four read-only synthesis commands, split into a
`cli/localstack/api/` layer that imports neither typer nor rich and a
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
| **Exactly four commands exist, and no mirror of a native CLI** | `localstack --help` and each command's `--help`; then run each against a respx-mocked server | Exactly these four: `status`, `service [<name>]`, `secret <service>`, `vault grants <job>`. Each issues the API calls the plan's table names and no others. **No `nomad jobs`, `nomad job`, `vault mounts`, `vault policies`, `vault policy`, `vault kv`, or `consul services`** — each of those is a native command renamed, and the operator cut them on 2026-07-31. A command that only restates `nomad job status` fails this row even if it works | deterministic check (exactly the four; none of the seven cut names present) | 100% |
| **`status` reads all three systems, and one being down does not blank the rest** | `localstack status` against a respx-mocked server where Vault returns 200, Nomad returns 200, and Consul times out | Vault and Nomad sections render their real data; the Consul section renders an explicit error state naming Consul. The command exits non-zero. A status view that renders three green panels because it silently swallowed a timeout is the failure this catches, and it is the reason the command exists rather than three separate ones | deterministic check (healthy sections render; failed source named; non-zero exit) | 100% |
| **`service` joins Nomad, Consul and the edge, and says when a source is missing** | `localstack service` against fixtures where a job runs in Nomad but has no Consul health check, and a hostname is routed in `haproxy.hcl` with no backing job | Each row shows job state, health check state, and URL, with **missing sources shown as missing rather than as healthy or absent**. A job with no health check must not render as healthy, and a routed hostname with no job must appear rather than being dropped. This join is the whole reason the command exists; a table that silently inner-joins hides exactly the broken cases you are looking for | deterministic check (both fixture cases render with the missing source marked) | 100% |
| **`service <name> --open` prints the URL even when it cannot open a browser** | Run in an environment with no browser and no `DISPLAY` | The URL is printed to stdout and the command exits zero. Inside a devcontainer, launching a browser is the part most likely to fail, and a command that opens nothing and prints nothing leaves the developer with no way to reach the service. For `consul`, the brokered token is printed too, since Consul's UI has no SSO on Community Edition | deterministic check (URL on stdout; exit 0; token printed for consul) | 100% |
| **`secret <service>` reports a referenced path that does not exist** | Fixture: a jobspec whose `template` block references a KV2 path that is absent from Vault | The row renders the path and marks it **missing**. Reporting only the paths that resolve turns "this job cannot render its template" into an empty, healthy-looking table, which is the exact question the command was built to answer | deterministic check (absent path listed and flagged missing) | 100% |
| **The reuse contract D4 depends on holds** | `grep -rnE "^\s*(import\|from)\s+(typer\|rich)" cli/localstack/api/` | No match. The `api/` layer returns dataclasses and imports neither typer nor rich, so D4's TUI can import it without dragging in a CLI framework. This is the concrete interface D4 was planned against; if it breaks, D4 builds a second fetching layer | deterministic check (no typer/rich import under api/) | 100% |
| **No subprocess anywhere** | `grep -rnE "subprocess\|os\.system\|shutil\.which" cli/localstack/` | No match. The local binaries are a major version ahead of the servers (Nomad CLI 2.0.3 vs server 1.11.3, Vault 2.0.3 vs 1.21.4, Consul 2.0.1 vs 1.22.6) and an `rtk` shim rewrites shelled commands in this devcontainer, so shelling out makes behavior a function of the developer's machine | deterministic check (no subprocess/shell-out) | 100% |
| `--json` on every command, and it cannot drift | For each of the four: run with `--json` and pipe to `jq -e .` | Valid JSON from all four, emitting the command's own dataclass rather than a hand-built dict. A hand-built dict is how the JSON and the table diverge | deterministic check (all four emit parseable JSON from the dataclass) | 100% |
| **Consul-sourced output says when it is ACL-filtered** | `localstack service` and `localstack status`, both with a brokered Consul token | Wherever Consul's catalog or health data appears, the output carries a footer naming the token whose ACLs filtered it. Verified live 2026-07-31: the brokered `deploy` token yields **2 of 25** services, no token yields all 25, and **no error fires either way**. Consul filters silently, so a confident table built on 2 rows is false and nothing reveals it. This row moved off the cut `consul services` command; the defect it guards belongs to the data, not the command that displayed it | deterministic check (footer present and names the filtering token, on every view carrying Consul data) | 100% |
| **`vault grants` resolves the template and never hardcodes the accessor** | `localstack vault grants memex`; then `grep -rn "auth_jwt_649fd6cc" cli/` | Two columns: the raw template line and the resolved path, plus capabilities. The mount accessor is discovered by regex over the fetched policy text, and the literal `auth_jwt_649fd6cc` appears NOWHERE in the source — it is derived at bootstrap (`nomad_server/tasks/main.yml:253-255`) and differs per rebuild. The policy text is fetched at runtime, never embedded | deterministic check (both columns present; accessor absent from source) | 100% |
| **`vault grants` survives both policy shapes** | Fixture tests against the six-block live policy AND F9's three-block template | Both render without error and resolve the job-scoped paths. F9 is merged but unapplied, so the repo template has three `path` blocks while live Vault still serves six. Code that assumes either count breaks on the other, and the switchover happens the moment the operator applies F9 | deterministic check (both fixtures render correctly) | 100% |
| **An unfillable template variable stays visible** | Feed `vault grants` a policy fixture containing a variable the command cannot substitute | The row renders with the `{{...}}` intact and is marked as unresolved. Silently dropping or blanking an unknown variable produces a resolved-looking path that is wrong, which is worse than an obviously incomplete one | deterministic check (unknown variable visible and flagged) | 100% |
| `vault grants` does not claim to be an authorization decision | Read the command's output | A one-line footer states the view is rendered from policy text, not an authorization decision. Vault resolves templates per request against the calling entity; this command resolves them from arguments | deterministic check (footer present) | 100% |
| **"Not allowed" is distinguished from "not logged in", per service** | Three cases: (a) no session at all; (b) valid Vault token, then `localstack service` where `GET /v1/jobs` returns 403 under a brokered `deploy` token; (c) valid token, `localstack vault grants <job>` without the policy-read grant | (a) every command exits non-zero saying run `localstack login`. (b) 403 on `/v1/jobs` while `/v1/job/<known>` succeeds is reported as "the token lacks `list-jobs`", naming the policy, and does **not** tell the user to log in, because logging in again changes nothing. (c) `auth/token/lookup-self` returns 200 so the session is live; the message names the denied path. Telling a developer to re-login when the real problem is a missing grant sends them in a circle | model + rubric (adversarial review agent) | 5/5 |
| The default test suite is offline | `cd cli && uv run pytest` with `VAULT_ADDR`/`NOMAD_ADDR`/`CONSUL_HTTP_ADDR` pointed at unroutable addresses | Green, and no outbound request. HTTP is mocked with respx at the fetcher layer; any test touching the real cluster carries the `cluster` marker and is excluded via `addopts` | deterministic check (suite green and offline with junk addresses) | 100% |
| **Guardrail: read-only** | `grep -rnE "\.(post\|put\|delete\|patch)\(" cli/localstack/api/`; review the diff | No mutating HTTP verb anywhere in the API layer, no Terraform change, no Vault policy authored. This ticket reads; the read-role gap it found is relayed to D2, not fixed here. `service --open` launching a browser and printing a URL is not a mutation and does not trip this row; brokering a token for that is D2's `localstack token`, called, not reimplemented | deterministic check (no mutating verbs; no `deployments/**` changes) | 100% |
| **Guardrail: no secret value is ever printed** | `localstack secret <service>` and its `--json` output, against a fixture whose KV2 paths hold real-looking values | Paths, key names and a present/missing marker only. **No secret value appears in stdout, in `--json`, or in any error message.** The command answers "which paths does this job read and are they there", and reading the value is neither needed nor safe to render into a terminal that scrolls into a log | deterministic check (no KV2 data values in any output path) | 100% |
| The repo gate passes | `just worktree_setup <path>`, then `just pre_commit` | All Passed, including ruff, mypy and pytest | deterministic check (`just pre_commit` all Passed) | 100% |

signed-off-by: PENDING

**Signature cleared 2026-07-31.** This marker was signed
`JasperHG90 2026-07-31` against the eight-command scope. The operator cut six
of those commands the same day, so the attestation no longer describes what is
being scored and cannot be carried over. Re-sign before implementing.
