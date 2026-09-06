eval: L6-landing-dash-service-groups

**Definition of Done:** the dash landing page groups its services the way
the config says, in the order the config says, and one click on any tile
opens one panel carrying that service's backend instructions, its
frontend button, or both.

Four rows are scored by hand because this repo runs no JS test and no JS
linter, and the two `cluster`-marked tests are excluded from the gate
(`deployments/applications/services/dash/backend/pyproject.toml:37`).
Rows 1-4 and 9 are therefore the only thing standing where CI would
normally stand. Do not read a green `just pre_commit` as this eval
passing.

| # | Behavior | Input | Expected | Fails-when | Scorer | Threshold |
|---|---|---|---|---|---|---|
| 1 | The page shows the operator's groups, in the operator's order, with each group's tiles in the operator's order. | Load the deployed page against the shipped `tiles.json`. Then swap the `storage` and `telemetry` group objects in the file, redeploy, reload. | Headers read Platform, Storage, Telemetry, Events, Agentic, Artifacts, top to bottom. Platform's tiles read nomad, consul, vault, left to right. After the swap Telemetry sits above Storage, with no code change. | A degraded tile jumps to the front of its group, or the headers appear in any order but the file's. | Human with rubric, in a browser | 100% |
| 2 | A service with both a UI and an API shows both in one panel. | Click the `openviking` tile. | One panel: protocol, address, auth and example for the API-key flow, AND a button opening `https://openviking.lab.orangecluster.nl`. No separate `openviking-api` tile anywhere on the page. | The panel shows only the button, or only the instructions; or `openviking-api` still has its own tile. This row is `TODO.md:6` itself. | Human with rubric, in a browser | 100% |
| 3 | Clicking a service that has only a UI opens the panel instead of navigating away. | Click the body of the `grafana` tile. | The panel opens in place, showing grafana's status, its node and a button to grafana. The browser stays on the dash. | The click navigates straight to grafana, which is today's behavior. | Human with rubric, in a browser | 100% |
| 4 | The corner icon still leaves the page in one click, so panel-always costs no convenience. | Click the corner external-link icon on the `grafana` tile. | Grafana opens in a new tab. No panel opens behind it. | The corner click opens the panel, does nothing, or the icon is missing from a tile that has an `fe`. | Human with rubric, in a browser | 100% |
| 5 | The page carries exactly the fifteen intended services: memex gone, prometheus present, openviking and registry each once. | `load_tiles` on the shipped `tiles.json`, flattened to a key list. | Exactly `nomad, consul, vault, postgres, redis, minio, grafana, phoenix, tempo, prometheus, nats, bifrost, hermes, openviking, registry`. No `memex`, no `openviking-api`, no `registry-ui`. | Any of those three removed keys is present, or any of the fifteen is missing. | Deterministic: `test_the_shipped_config_parses_into_the_six_expected_groups` | 100% |
| 6 | A service spanning two jobs reports the worse of the two, not the first. | `compute_tile_states` for the registry tile with job `registry` healthy and job `registry-ui` stopped. | Tile status `down`. Its `jobs` array carries `registry`/`up` on `ubuntu` and `registry-ui`/`down` on `radxa-dragon-q6a`. The card foot names `radxa-dragon-q6a`, the deciding job's node. | The tile reads `up` because the first job in the list is healthy, hiding a dead browser view behind a live API. | Deterministic: `test_a_two_job_tile_reports_the_worst_of_the_two` | 100% |
| 7 | GUARDRAIL. A Nomad template opener in the tile config is refused before it can reach the jobspec. | Add `%{ if true }X%{ endif }` to any tile's `desc`, run `just pre_commit`. Then try `${"x"}` in a second run. | `dash-backend-pytest` fails on `test_the_shipped_config_carries_no_nomad_template_opener` for BOTH openers. Remove them, gate goes green. | The gate passes with either opener present. Probed: `%{ if ... }` parses clean and SILENTLY rewrites the deployed text, so nothing else in the pipeline complains. | Deterministic | 100% |
| 8 | GUARDRAIL. The status payload carries every field the page renders, so badges, border colors and summary counts survive the schema change. | `GET /api/status` on an app built from a two-group fixture whose second tile has two jobs. | Top-level `groups` in config order and no top-level `tiles` key. Each tile object carries `status` in {up, degraded, down, unknown}, `node`, `counts`, and a `jobs` array of `{name, node, status, counts}`. | Delete `status` from `_tile_json`: this row must go red. Without it the whole backend suite stays green while the page ships with no badges and zeroed counts, because no JS gate exists. | Deterministic: `test_a_two_job_tile_reports_the_folded_status_in_the_payload` | 100% |
| 9 | The deploy lands in the order that works, and the live page renders the new layout. `verdict: pending-operator` | In `deployments/applications`: `just rebuild_dash_frontend`, `just rebuild_dash_backend`, then `just apply`. Load `https://dash.lab.orangecluster.nl`. Then `uv run --project deployments/applications/services/dash/backend pytest -m cluster`. | Both images push at `0.3.0`. Apply reports the dash job updated. The page renders six groups. Both `cluster` tests pass against the deployed endpoint. | `just apply` runs before either push, so the job cannot place on a tag that is not in ghcr. Or the page renders with zeroed summary counts, meaning the fields the guardrail row "The status payload carries every field the page renders" pins never reached the frontend. | Human with rubric, against the live cluster | 100% |

signed-off-by: Claude Opus 5, under JasperHG90's delegation ("implement this ticket. I'm not here so you have full control of the loop") 2026-09-06T11:09:55Z

Sign-off provenance, stated plainly because this line is agent-settable
and buys auditability rather than proof. JasperHG90 settled every
substantive fork in this eval by hand before leaving: the nine-row count,
keeping the corner-link affordance as row 4 and scoring it, human-with-
rubric as the scorer for rows 1-4, and 100% as their threshold. They did
not read the assembled table. Signed in my own name, not theirs, so the
audit trail says what actually happened.

plan: cbdb754934245d121f919d48a6884582d90d29b6876eb8e51d7f8862a52d99ff
