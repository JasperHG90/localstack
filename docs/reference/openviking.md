# OpenViking

A context store for agents, on radxa beside Bifrost. Vectors go to Postgres,
blobs to MinIO, embeddings and rerank through Bifrost to embark, image
summaries through Bifrost to ollama. There is no browser surface: callers
authenticate to the API with a Vault identity token.

## What runs where

| Piece | Where |
|---|---|
| Job | `openviking` on radxa-dragon-q6a, port 1933, open to the LAN |
| CLI and agents | `https://openviking-api.lab.orangecluster.nl` |
| Vectors | Postgres `openviking` database, `openviking` schema, pgvector |
| Blobs | MinIO `openviking` bucket |
| Models | Bifrost, as `embark/embedding` and `embark/reranker` |
| Image summaries | Bifrost, as `ollama/glm-5.3-flash` |
| Query planning | Bifrost, as `ollama/gemma4:31b` |

The image is derived, and building it is an operator step. See
`deployments/applications/services/openviking/README.md`.

## Retrieval: the job does not run `openviking-server`

It runs `python -m ov_retrieval`, a wrapper from our own `openviking_extensions`
repo. OpenViking offers no plugin hook, so the wrapper patches its retriever and
then starts the ordinary server. Two things change for anyone reading results:

- **A keyword leg.** Every search now also runs a lexical query against the
  Postgres full-text index and fuses the two rankings with reciprocal rank
  fusion. An exact identifier or acronym the embedding missed can now surface.
- **A diversity pass.** Maximal marginal relevance drops results that mostly
  repeat the one above them, so five near-identical documents no longer fill
  five of ten slots.

Fusion ranks by *position*, not by score, so a result's place in the answer no
longer tracks its cosine similarity. Do not read the ordering as a distance.

The knobs live in the jobspec's `env` block as `OV_RETRIEVAL_*`, pinned to the
package defaults rather than inherited. `scripts/check_openviking_config.py`
asserts the `command` and `args` that select the wrapper, because dropping
either one starts the stock server, which comes up healthy and answers every
search without both features.

Bodies are stored but not indexed: `store_content` is on, `keyword_fields` names
the five default columns, and the reasoning for that gap is in the service
README beside `ov.conf.json`.

## Authentication: Vault is the identity

One layer, not two. A person logs into Vault, mints a short-lived JWT for
themselves, and OpenViking verifies it. No OpenViking password exists, and no
per-person API key is on the request path.

**Getting a token.** `vault login -method=userpass` returns a Vault token that
renews for as long as its TTL allows. From that session,
`vault read identity/oidc/token/openviking` mints an RS256 JWT that expires in
a month. Re-minting needs no browser, so the expiry costs nothing: a person
logs in when their Vault session lapses, not when the token does.

**What the server checks.** `auth_mode` is `oidc`. OpenViking fetches Vault's
discovery document and JWKS from
`https://vault.lab.orangecluster.nl/v1/identity/oidc` at request time, verifies
the signature, and compares `iss` and `aud` exactly. `aud` must equal the
identity-token role's `client_id`, `openviking`.

**Who the caller is.** The token carries two claims, `ov_account` and
`ov_user`, and OpenViking maps one field from each. They are separate because
they differ: the operator is user `jasper` inside account `lab`, and there is
no `lab/user/lab`. Both come from the Vault
entity's `ov_account` metadata, published by the role's template.

Why the claims come from metadata rather than the entity name or `sub`, and
what happens to an entity without them, is in
[OpenViking identity](../explanation/openviking-identity.md).

| Vault entity | Groups | `ov_account` | `ov_user` | Reaches |
|---|---|---|---|---|
| `operator` | `developer`, `admin`, app tiers | `lab` | `jasper` | the whole cluster |
| `veerle` | `openviking-user` | `lab` | `veerle` | one Vault path, and OpenViking |

Everyone shares the `lab` account and is told apart by the user inside it.
That is what buys isolation without giving up the shared half: OpenViking
isolates user scopes absolutely, so `viking://user/jasper` and
`viking://user/veerle` cannot read each other, while `viking://resources`
belongs to the account and is common to both.

`openviking-user` grants one thing: reading `identity/oidc/token/openviking`.
Vault issues that token for the calling entity only, so the grant cannot be
used to act as anyone else. The operator is not a member, because `developer`
already reaches that path through `identity/*`.

**Hermes mints its own token.** It authenticates to Vault with its Nomad
workload identity and reads a role whose template carries `lab`/`jasper`, so its
writes land in the same tree the operator sees. It holds no key.

The token reaches it through a loopback sidecar rather than its environment. A
running process cannot have its environment changed, and every read of an
identity-token path mints a NEW token, so rendering one into Hermes's env
restarted the task on every consul-template poll. The sidecar reads the token
from disk per request instead, and Hermes holds a constant endpoint.

## Image summaries and query planning

Image summaries go to `ollama/glm-5.3-flash` through Bifrost, the same route as
embedding and rerank. The virtual key carries `ollama` alongside `embark`.

Retrieval planning runs on `ollama/gemma4:31b` through the same gateway.
`query_planner` is optional and falls back to the `vlm` block when unset, so
leaving it out is legal and silent -- and means planning runs on the vision
model at vision cost. The checker asserts it is set for that reason.

Which models accept an image, and why the checker pins that list, is recorded
in `.okf/practices/openviking-vision-models.md`.

## Observability

| Signal | Where it goes | How |
|---|---|---|
| Logs | Loki on `192.168.2.47:3100` | `alloy`, a Nomad system job, tails every alloc's stdout/stderr. No per-service config |
| Metrics | Prometheus on `192.168.2.47:9090` | `server.observability.metrics`, scraped from `192.168.2.50:1933/metrics` |
| Traces | Tempo on `192.168.2.47:4317` | `server.observability.traces`, OTLP gRPC |

Traces read `server.observability.traces`, NOT the `telemetry.tracer` block the
CLI config also declares. Only the first is wired: `telemetry/tracer.py` reads
`server_config.observability.traces` and logs one warning at startup when the
endpoint is empty, then exports nothing for the life of the process. Setting
the other block looks right and does nothing.

`metrics.enabled` alone is not enough either. It builds no exporter without
`exporters.prometheus.enabled`, and `/metrics` keeps returning 404. The checker
asserts both for that reason.

`/metrics` is the one OpenViking route with no auth dependency, so the
Prometheus job carries no credential — and so can anything else on the LAN
while 1933 is open LAN-wide. That is the cost of enabling it, recorded here
because nothing else reports it.

## What the config guard asserts

`scripts/check_openviking_config.py` runs in pre-commit and asserts the config
values that fail silently: the embedding dimension, the vector backend, the
`custom_params` key allow-list, the rerank target, `auth_mode`, the four
`server.oidc` values (issuer, audience, and the two claim mappings with their
fallbacks), the VLM's model and `api_base`, the query planner's model and
`api_base`, `metrics.enabled` and its Prometheus exporter, and `traces.enabled`
with its endpoint.

It reads one value outside that document: `OPENVIKING_WEB_STUDIO_DIR` in
`deployments/applications/services/openviking.hcl`, which must be
`/nonexistent`. Upstream strips the value and falls back to the packaged
bundle when the result is empty, so `""` remounts Studio while reading as
disabled. The guard checks the value for that reason, not just the name.

Two it used to assert are gone. Under `oidc` the plugin never consults
`server.root_api_key`, and nothing on the request path issues or verifies a
per-user key, so `encryption.api_key_hashing` governs nothing reachable. The
`auth_mode` assertion is what keeps both safe: a flip back to `api_key` fails
the guard before either matters again.

The dimension is **384**, measured against `embark/embedding` through Bifrost.
A wrong value corrupts the collection without erroring, which is why the
checker asserts it rather than a comment recording it.

It does **not** measure anything about a running service. The checks that need
a deployment are in
[How to verify an OpenViking deployment](../how-to/verify-an-openviking-deployment.md).
