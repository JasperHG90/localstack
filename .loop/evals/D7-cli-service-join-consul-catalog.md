eval: D7-cli-service-join-consul-catalog

**Definition of Done:** `localstack service` resolves its Consul rung from
`GET /v1/catalog/services` instead of from health checks, so `consul` renders
`consul-name` rather than `unresolved`, and the table renders the `backend`
column the row already carries and requirement 5 already mandates.

**The measurement this ticket rests on**, taken live 2026-08-04 and pinned by
row 8. Consul's catalog lists 25 services including `consul`. Across the 41
health checks, `ServiceName` is `nomad` 3 times, `vault` once, `consul`
**zero** times, and empty 5 times (node-level `serfHealth`). So `vault` and
`nomad` resolve today only because they happen to own service-scoped checks.
The rung was never about checks.

**The trap.** Both defects shipped through a full adversarial review of D3.
Row 1 is the regression and must be seen RED against the pre-fix code before
the fix lands; test 6 in the ticket is the form that can go red, because a
direct `join()` call with the new argument only raises `TypeError`. Rows 6
and 7 are the guardrails: without them the fix can be written in a shape that
either keeps the old behavior as a fallback or lets a caller pass the wrong
dict positionally and type-check clean.

**`s3` is deliberately still `unresolved`.** No row asserts otherwise. Its
resolution needs a tag rung, which the ticket defers with the evidence
recorded (Q2), and row 5 is what makes the row legible in the meantime.

| Behavior | Input | Expected | Scorer | Threshold |
| --- | --- | --- | --- | --- |
| **A service Consul knows about but does not health-check still resolves** | `join()` with a route named `consul`, a catalog containing `consul`, and checks containing no element whose `ServiceName` is `consul` | The row renders `job_source == consul-name`, not `unresolved`. This is the reported defect: Consul registers itself in the catalog but its only check is a node-level `serfHealth` with an empty `ServiceName`, so a rung keyed on checks misses it. `vault` and `nomad` must keep resolving too, which they will, since the catalog is a strict superset of the check-derived set (`checks - catalog` is empty, measured) | deterministic check (`consul` resolves `consul-name`; `vault` and `nomad` unchanged) | 100% |
| A route matching neither a job nor a catalog service stays unresolved | `join()` with a route named `s3`, a catalog with no `s3` key, and no Nomad job `s3` | `job_source == unresolved`, `job` and `health` both read not found, and `backend` is populated. Widening the rung must not start resolving things by accident; `s3` is the live case and it is correct output | deterministic check (still `unresolved`; backend populated) | 100% |
| The catalog fetcher returns names with their tags, and sends no token | `list_services()` against a mocked `GET /v1/catalog/services` returning the captured live payload | Returns `dict[str, list[str]]` mapping each service name to its tags, and the request carries no `X-Consul-Token` header. Tokenless for the same reason the health read is: the agent's `tokens.default` is its own token. The tags are returned rather than discarded so the deferred tag rung (ticket Q2) is not foreclosed by a return type; `minio` must come back carrying `s3` | deterministic check (dict of name to tags; no token header; `minio` carries `s3`) | 100% |
| A tightened Consul ACL degrades rather than crashes | `list_services()` against a mocked 403 | Raises `MissingCapability` naming the Consul read, the same typed error the health read raises, so the command reports a denial instead of a traceback. If `tokens.default` is ever removed this read is denied along with the health read, and the panel must say so | deterministic check (typed `MissingCapability`, not an unhandled exception) | 100% |
| **An unresolved row says where it points** | `localstack service` rendered against the fixtures, reading the `s3` row | The table carries a `backend` column and the `s3` row shows `192.168.2.29:9000`. Requirement 5 of D3 already mandates rendering "the hostname and the raw `ip:port` backend" for an unresolved row; the dataclass carries it and `--json` emits it, but the table dropped it, so the two rows with the least resolved information showed the least on screen. The column is blank on the 13 `no-route` rows, which is correct: a job the edge does not serve has no backend | deterministic check (backend column present; `s3` row shows its `ip:port`) | 100% |
| **Guardrail: no fallback to check-derived names** | Read the shipped `api/services.py`, then call `join()` omitting the catalog | The catalog is a REQUIRED parameter and no code path derives rung-(b) names from `check.service`. Omitting it is an error, not a silent empty set and not a silent revert to the old behavior. A default of `None` would have to mean one of those two, and both are this ticket's defect preserved: the first resolves nothing at rung (b), the second is the bug itself kept as a fallback | deterministic check (call without the catalog fails; no `check.service` name-set anywhere in the join) | 100% |
| **Guardrail: the catalog parameter is keyword-only** | `uv run mypy --config-file cli/pyproject.toml cli/src cli/tests` after rewriting one call site to pass the catalog positionally | mypy strict reports `Too many positional arguments for "join"`. Merely making it required is not enough: `catalog: dict[str, list[str]]` and the existing `service_names: dict[str, list[str]] | None` are positionally interchangeable, so a positional `catalog` lets a caller bind its names dict to it and type-check clean, which ships the defect green AND degrades every `job-id` row's health to `no check`. Ten call sites bind this argument (one in `commands/service.py`, nine in `tests/api/test_services.py`), and the mypy hook covers `cli/tests` as well as `cli/src`, which is what makes the check reach all ten | deterministic check (positional form rejected by mypy strict; keyword form clean) | 100% |
| **Guardrail: the live premise still holds** | `cluster`-marked test against the real cluster: fetch `GET /v1/catalog/services` and `GET /v1/health/state/any` | The catalog contains `consul`; no health check carries `ServiceName == "consul"`. Excluded from the default offline run via `addopts`. This is the one fact the whole ticket rests on, and it is a fact about Consul's own registration behavior rather than about this repo. If a future Consul starts registering a self-check, this row goes red and says the fix has become pointless, instead of the fix quietly doing nothing | deterministic check (catalog contains `consul`; zero checks with that `ServiceName`) | 100% |

signed-off-by: JasperHG90 2026-08-04
