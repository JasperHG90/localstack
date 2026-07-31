eval: D4-cli-cluster-tui

**Definition of Done:** a `localstack monitor` Textual TUI showing exactly four
things — Vault seal state, Nomad node status, per-job allocation health, and
Consul critical checks — refreshing without ever blocking on a dead source,
with every degraded state named, rendered and snapshot-tested. Auth comes
entirely from D2.

**The scope constraint is the operator's own framing:** "not a Grafana
replacement but a panel for developers". Grafana, Prometheus and Loki already
run here. The Grafana-boundary guardrail below makes that checkable rather
than aspirational, because the natural drift of a status panel is toward a
dashboard.

**Amended 2026-07-31** after the seven open forks were resolved. Two rows are
new: the refresh contract from Q4, and the single-fetch-layer guardrail from
Q3. The 403 row was re-pointed, because Q2 moved the read-capable Nomad role
into F7's replan, so a denied `/v1/jobs` stops being the everyday state and
becomes a guardrail.

**The trap.** A TUI is judged by how it looks when things are fine, and used
when they are not. The degraded-state rows cover what a developer actually
opens it during, and the periodic/system row covers the one that quietly
reports healthy jobs as broken.

| Behavior | Input | Expected | Scorer | Threshold |
| --- | --- | --- | --- | --- |
| The panel shows exactly four widgets | Launch `localstack monitor` against mocked sources; inspect the widget tree | Vault seal state, Nomad node status, per-job allocation health, Consul critical checks. **No fifth widget.** Specifically no "recent failed allocations" panel: Nomad garbage-collects dead allocs (24 live, all running, verified), so it is empty most days while `JobSummary.Failed`/`Lost` on the job row already answers it | deterministic check (exactly four widgets, none extra) | 100% |
| Jobs come from the API, never the repo | `grep -rn "deployments/" cli/localstack/`; run against a mocked cluster including `talat-shim` and `talat-consumer` | No enumeration from `deployments/`. Both talat jobs appear in the job widget. They run live and have **no job file in this repository**, so anything driven from the repo tree silently under-reports by two | deterministic check (talat jobs present; no deployments/ enumeration) | 100% |
| **Periodic and system jobs are not reported as broken** | Fixtures: a `batch/periodic` parent with `Running: 0` between runs (this is `acme`'s normal state), a `system` job on 5 eligible nodes, and a `service` job at 2/3 desired | The periodic job renders healthy, judged on the parent's `Status` and last child outcome — NOT on `Running == 0`. The system job is judged running-count vs eligible-node-count. Only the service job shows degraded. Verified live: 3 of 19 jobs would falsely red under a naive `Running > 0` rule, and a panel that cries wolf on a third of the cluster gets ignored | deterministic check (periodic and system healthy; service degraded) | 100% |
| **A dead source degrades its own panel and nothing else** | Launch with Vault unreachable (connection refused) while Nomad and Consul respond normally | The Vault widget renders an error state; the other three render real data within the normal refresh. The UI never blocks. Each source fetches independently with its own timeout. A TUI that hangs on a dead Vault is worse than no TUI, and this is the most likely real failure | deterministic check (three panels live, one errored, no hang) | 100% |
| **Sealed Vault is a named state, not an error blob** | Launch with `/v1/sys/seal-status` returning `sealed: true` | The Vault widget says the seal state plainly. This is the single most common real outage here — the root `justfile` carries an `unseal_vault` recipe for it — so it must read as a diagnosis, not a stack trace | deterministic check (sealed state rendered as a named state) | 100% |
| **An expired token is distinguishable from an outage** | Launch with a session whose token is expired; separately, with Nomad refusing connections | Expired token renders a state telling the developer to run `localstack login`. Unreachable Nomad renders a different state naming the endpoint. Conflating them sends someone to re-login when the cluster is down, or to debug the cluster when their token lapsed | deterministic check (two distinct rendered states) | 100% |
| A 403 is its own state | Launch with a token that authenticates but lacks `list-jobs` | The node and job widgets render a permission-denied state naming what was denied, not an empty table. Verified live 2026-07-31: a brokered `nomad/creds/deploy` token gets 403 on `/v1/jobs` (`nomad_deploy_role.tf:4-5` withholds `list-jobs`). **Q2's resolution puts a read-capable role in F7, so this stops being the everyday state and becomes a guardrail** against the day a policy is narrowed. Score it from a fixture, not from whichever token happens to be live at implementation time | deterministic check (403 rendered as permission-denied, not empty, from a fixture) | 100% |
| **The refresh contract: a slow source goes stale, never blank** | Fixture where Nomad answers in 5 seconds against a 2-second per-source timeout, across two refresh cycles | The Nomad widget keeps its **last known value, visibly marked stale**, and does not blank, spin or reset to an empty table. The other widgets refresh on schedule throughout. Q4 fixed this at a 5-second poll with a 2-second per-source timeout and `r` to force. A panel that blanks a widget on a slow response tells the developer the data is gone when it is merely late, which is the opposite of what they need mid-outage | deterministic check (last value retained and marked stale; other widgets unaffected; no blanking) | 100% |
| **Guardrail: one fetch layer, imported not rebuilt** | `ls cli/localstack/` and `grep -rnE "^\s*(import\|from)" cli/localstack/tui*` for its data source | The TUI imports D3's `cli/localstack/api/` and there is **no second fetching module** (no `cluster_api.py`, no private HTTP client under the TUI). Q3 resolved that D3 owns the fetch layer and D3's own marker scores it as importable by requiring `api/` to pull in neither typer nor rich. Two fetch layers means two places where a 403 is classified, and they will disagree | deterministic check (imports D3's api/; no second fetch module) | 100% |
| Consul shows failing checks only | Fixture with 41 checks, 2 critical | The widget shows the critical count and only the failing checks. Never all 41. A Nomad alloc can be `running` while its Consul check is critical, which is the gap this widget exists to close; a wall of passing checks buries it | deterministic check (count plus failing only) | 100% |
| **Snapshot tests are deterministic and offline** | `cd cli && uv run pytest` with all three cluster addresses pointed at unroutable hosts | Green, no outbound request. Widgets take their data through an injected callable, fetchers live in a separate module, and snapshots run off scrubbed fixture payloads via `pytest-textual-snapshot`. Live-cluster tests carry the `cluster` marker and are excluded via `addopts`. Baselines are refreshed only after reviewing a diff, never to clear a red test | deterministic check (suite green and offline; snapshots from fixtures) | 100% |
| **Guardrail: the Grafana boundary holds** | Review the diff and the rendered panel | No metrics, no charts, no historical series, no log viewing, no alerting, no dashboard framework, and no write actions of any kind. The operator's constraint is that this is a glance-at panel, not an observability platform; a diff crossing that line is a review failure regardless of how good the feature is | model + rubric (adversarial review agent) | 5/5 |
| **Guardrail: no second auth path** | `grep -rniE "userpass|auth/token|session\.json|VAULT_TOKEN" cli/localstack/tui*` and the widget modules | Auth comes entirely from D2's surface. No token acquisition, no Vault login, no credential-file reading, no env-var token fallback authored here. If D2's surface does not fit, that is an `out-of-scope-fix-needed` block, not a second login path quietly grown in the TUI | deterministic check (no auth logic outside D2's client) | 100% |
| No token value ever renders | Grep the source, the rendered output and every snapshot fixture for token values and the `hvs.`/`hvo_` prefixes | No match. Snapshot fixtures are scrubbed. `detect-private-key` stays green, though note that hook matches PEM headers only and would not catch a Vault token, which is why this row greps explicitly rather than relying on it | deterministic check (no token in source, output or fixtures) | 100% |
| The repo gate passes | `just worktree_setup <path>`, then `just pre_commit` | All Passed. New deps (`textual`, `pytest-textual-snapshot`, `respx`) added via `uv add`, landing in `cli/pyproject.toml` and `cli/uv.lock`. `httpx` reused rather than adding `requests` | deterministic check (`just pre_commit` all Passed; deps in pyproject) | 100% |

signed-off-by: PENDING

**Signature cleared 2026-07-31.** The TUI was renamed from `localstack status`
to `localstack monitor`, freeing `status` for D3's one-shot, scriptable
renderer of the same data. This is a lighter case than D3's: no row's rigor
changed, only the command each row launches. Cleared anyway, because a
signature that describes a command name no longer in the ticket is a
signature nobody can check. Re-sign alongside D3 in one pass.
