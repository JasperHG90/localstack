eval: D8-cli-service-tag-rung

**Definition of Done:** `localstack service` resolves a route to a Consul
service that carries a tag of the same name, when exactly one service carries
it. `s3` renders `consul-tag` with job `minio` instead of `not found`.

**Why the tag is trustworthy.** MinIO's job declares the service `minio` with
tags `["s3", "http"]` on the port label the `s3` route points at
(`192.168.2.29:9000`, the S3 API; `:9001` is the console and is the `minio`
route). Reading the tag is reading what the job said about itself, not
guessing from an address or a hardcoded alias.

**Why this is safe.** Measured live 2026-08-04 across the ten routes, asking
which catalog services carry a tag equal to the route name: only
`s3 -> ["minio"]` and `memex -> ["memex"]`, both unique. `memex` already
resolves at rung (a), so exactly one row changes. The shared tags D7 worried
about (`http` on 16 services, `monitoring` on 9) are not route names.

**The trap.** Two ways to get this wrong quietly. Written as "at least one
carrier" it silently picks whichever sorts first the day a tag is shared,
and no live case would catch it. Placed above the existing rungs it beats a
real name match. Rows 2 and 3 are those.

**One existing test goes vacuous and must be repaired.**
`test_the_table_says_where_an_unresolved_row_points` uses `s3` as its
unresolved row, and `s3` is the only unresolved row in the fixtures. After
this change it passes while covering nothing. Row 6 scores the repair.

| Behavior | Input | Expected | Scorer | Threshold |
| --- | --- | --- | --- | --- |
| **A route named after a unique Consul tag resolves to that service** | `join()` with a route named `s3`, no Nomad job `s3`, no catalog key `s3`, and a catalog where exactly one service (`minio`) carries the tag `s3` | The row renders `job_source == consul-tag`, `job == minio`, and health taken from `minio`'s own checks rather than from the route name. This is the reported defect: `s3` is MinIO's S3 API port under its own hostname, and the job declares the tag, so rendering `not found` is wrong | deterministic check (`consul-tag`; job is the matched service; health from that service) | 100% |
| **Guardrail: an ambiguous tag resolves nothing** | `join()` with a route named `shared` and a catalog where two services both carry the tag `shared` | The row stays `unresolved` with its backend populated. Written as "at least one carrier" this picks whichever sorts first, and no live input would catch it because every route-name tag on this cluster has exactly one carrier today. The conservative branch is the whole reason a tag rung is acceptable at all | deterministic check (two carriers leaves the row `unresolved`) | 100% |
| **Guardrail: the tag rung never pre-empts a name match** | `join()` with a route named `memex` that matches a Nomad job `memex` AND is carried as a tag by some other service; separately, a route matching a catalog service name that is also a tag elsewhere | The first resolves `job-id`, the second `consul-name`. The tag is the weakest signal and must be consulted last. Placed above either existing rung it would rewrite rows that are already correct | deterministic check (`job-id` and `consul-name` both win over `consul-tag`) | 100% |
| **A route matching nothing at all still renders** | `join()` with a route whose name matches no job, no catalog key and no tag | `unresolved`, with `job` and `health` both not found and `backend` populated. Adding a rung must not remove the honest fallback | deterministic check (still `unresolved`; backend populated) | 100% |
| **`s3` resolves through the command** | `localstack service --json` against the fixtures | The `s3` row carries `job_source == consul-tag` and `job == minio`. The `minio` row is unaffected and still resolves `job-id`, and the `minio` job is not suppressed or duplicated: a tag match reports the matched service and does not mark the job routed | deterministic check (`s3` resolves; `minio` row unchanged; no duplicate or missing row) | 100% |
| **The repaired test still tests something** | Read `test_the_table_says_where_an_unresolved_row_points` after the change, and the fixtures it runs against | It exercises a route that is genuinely unresolved after this change, not `s3`. A test whose only subject started resolving is a test that passes for free, and this one guards D7's backend column. Note the cheap path: append the extra backend to that test's own inline edge mock rather than to the shared `LIVE_SHAPE`, which `test_haproxy.py` pins at exactly ten routes by name | deterministic check (the test's subject row is `unresolved`; `test_haproxy.py` still green) | 100% |
| **The ladder documentation matches the ladder** | Read `api/services.py`'s module docstring and `docs/cli-read-commands.md`'s `job_source` table | Both describe four rungs including `consul-tag`, and neither still names `s3` as the live `unresolved` example, because after this change no live route is unresolved. A docstring describing three rungs is a reader's first and wrongest source | deterministic check (four rungs documented in both; no stale `s3` example) | 100% |
| **Guardrail: the live premise still holds** | `cluster`-marked test: fetch the catalog and the running edge config, and resolve every route | `s3` resolves to `minio`, and no live route name is carried as a tag by more than one service. The second half is what keeps the ambiguity rule theoretical: if a future service starts carrying a route-name tag, this goes red and says so instead of a row silently reverting to `unresolved`. Extends the assertion D7 already added rather than duplicating it | deterministic check (`s3` resolves to `minio`; every route-name tag has at most one carrier) | 100% |

signed-off-by: JasperHG90 2026-08-04
