eval: R4-rollout-phoenix-oauth2-proxy

Definition of Done: browsing the Phoenix console requires a completed Vault
OIDC login through Phoenix's own generic OIDC client, with no oauth2-proxy in
front of it, while OTLP trace ingest keeps working because `memex` now presents
a bearer key, ingest without a key is refused, and the old shared HAProxy basic
auth on the Phoenix backend is gone with no double auth.

Rewritten 2026-07-26 alongside the plan. The previous marker's Definition of
Done encoded the oauth2-proxy design and its port-6006 split, which the plan
rewrite removes. **Note the reversal in the ingest rows:** ingest passing used
to mean `/v1/traces` answering *without* auth. It now means answering *with* a
bearer key and refusing one *without*.

Preconditions (plan §4, §8): depends on **F2** (Vault OIDC issuer and the
Phoenix client) and **T3** (the TLS edge and the
`phoenix.lab.orangecluster.nl` hostname) being applied first. Run each row
after `terraform apply` and the Nomad deploy have landed. Substitute the real
hostname if T3's naming changed.

The ingest rows are the load-bearing guardrails: a pass requires the UI to be
gated **and** ingest to keep working. Breaking either side is a fail. Enabling
Phoenix auth stops trace collection silently, so an unexercised ingest row is
not evidence of anything.

| Behavior | Input | Expected | Scorer | Threshold |
|----------|-------|----------|--------|-----------|
| Phoenix is running and healthy after apply, with no proxy job added | `nomad job status phoenix`; `nomad job status` | the `phoenix` task reports `running`/`healthy` and deployment `Status = successful`; no `phoenix-oauth2-proxy` (or equivalent) job exists, since this design adds no proxy | deterministic check (`nomad job status phoenix`) | 100% |
| An unauthenticated browser hitting the Phoenix console is sent to a login rather than served the app | `curl -sI https://phoenix.lab.orangecluster.nl/` | a `302`/`307` to Phoenix's own login or the Vault OIDC authorize endpoint, or a `401`; NOT `200` with the Phoenix HTML console | deterministic check (`curl -sI`) | 100% |
| The login path actually reaches Vault, proving the OIDC client is wired and not just that some login exists | follow the redirect chain from the Phoenix sign-in, or `curl -s https://phoenix.lab.orangecluster.nl/ -L -o /dev/null -w '%{url_effective}\n'` | the chain reaches the Vault OIDC authorize endpoint on the Vault issuer host with the Phoenix `client_id`; a chain that stops at Phoenix's local login form only means OIDC is not wired | deterministic check (redirect chain inspection) | 100% |
| OTLP ingest WITH the bearer key is accepted, so `memex` traces keep arriving (load-bearing guardrail) | `curl -s -o /dev/null -w '%{http_code}\n' -X POST https://phoenix.lab.orangecluster.nl/v1/traces -H 'content-type: application/json' -H "authorization: Bearer $PHOENIX_KEY" -d '{"resourceSpans":[]}'` | a non-auth status from Phoenix's collector itself (`200`, `415`, or a `400` parse error), proving the request was authenticated and reached the collector; NOT `401`/`403` | deterministic check (`curl -X POST` with the key) | 100% |
| OTLP ingest WITHOUT a key is refused, proving ingest is genuinely gated and not merely still open | same POST as the row above, with the `authorization` header omitted | `401` or `403`; a `200` means auth is not actually enforced on the collector and the ticket has not achieved its second goal | deterministic check (`curl -X POST` with no key) | 100% |
| A real trace from `memex` lands in Phoenix end to end, not just a synthetic POST | exercise a `memex` operation that emits spans, then query Phoenix for recent traces for `service.name = memex` (UI or API) | at least one new `memex` span appears, timestamped after the apply; an empty result means ingest is dark even if the synthetic POST passed | deterministic check (trace query after a known operation) | 100% |
| The old shared basic auth no longer fronts Phoenix, and is not stacked on top of Phoenix's own login | `curl -sI https://phoenix.lab.orangecluster.nl/`; and inspect the live `backend phoenix` block in the running HAProxy config | no `WWW-Authenticate: Basic` on the Phoenix route and no `http-request auth ... http_auth(openfang_users)` in the `phoenix` backend; MLflow and Bifrost basic-auth lines left intact | deterministic check (`curl -sI` + config inspection) | 100% |
| Behind a completed Vault login the console renders, and the auth-versus-ingest split holds under review | complete the OIDC flow in a browser and load the console; hand the reviewer the ingest evidence from the rows above per `.claude/rules/adversarial-reviews.md` | the console renders authenticated with no broken assets or redirect loop, AND the reviewer confirms ingest works with a key and is refused without one | model + rubric (adversarial review agent) | 4/5 |
