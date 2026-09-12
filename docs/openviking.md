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

It is deliberately not the entity name and not `sub`. `sub` is the entity UUID,
so an account mapped from it would be one account per UUID while every request
still returned 200. The entity name is wrong for a different reason: the
operator's entity is a cluster-admin identity and its OpenViking account is a
data identity, so those two names differ on purpose.

An entity carrying no `ov_account` is NOT refused, and no configuration makes
it so. Vault renders an absent metadata key as an empty string; upstream applies
`fallback` only to a null, and its `regex` narrows a value without ever
rejecting one, because a non-match leaves the value untouched. So such a caller
resolves to an account named `""`. Measured against the deployed version.

`identity.account_id.fallback` is still explicitly `null`, because absent means
`"default"` upstream and `default` is a real account here. What actually keeps
the empty case unreachable is the ACL on the identity-token role: only the
operator and the `openviking-user` group can mint one, and Terraform sets both
metadata keys on every entity it puts in either.

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

### One account, one user each

Everyone shares the `lab` account and is told apart by the user inside it.
`viking://user/jasper` and `viking://user/veerle` cannot read each other,
because OpenViking isolates user scopes absolutely: measured in OV1, an ADMIN
gets 403 on another user's scope and no role grants a cross-user read.
`viking://resources` belongs to the account, so it is common to both.

That shape needs the two claims to be separate. The account is the first
segment of every stored path (`/local/<account_id>/...`) and vectors are
separated by the same value ANDed into every query, so a shared account is what
puts two people in one resource tree; the user is what keeps their own trees
apart. Mapping both from one claim resolves to `lab/user/lab`, which does not
exist.

OV2 briefly gave each person their own account instead. It isolated them from
the shared half as well, and it migrated nothing, so the content stayed in
`lab` while the new accounts sat empty. `lab` is the live account; the
per-person ones are leftovers.

Under `oidc` every caller resolves to role USER. The plugin never consults a
role mapping and never consults `server.root_api_key`, so no admin route has a
reachable credential and nothing can create an account.

Nothing needs to. MEASURED after the switch with
`scripts/ov_identity_probe.py`: a token naming an account that was never
created returns 200 and reads an empty tree. So adding a person is a Vault
entity carrying `ov_account` and `ov_user` and nothing else, and the
provisioner that used to POST to the Admin API is gone rather than replaced.

The cost of that is a typo. A misspelled claim does not fail; it opens a new
empty account or user, and the person sees an empty tree rather than an error.

### The API keys that are left

There are none on the request path. `auth_mode` is `oidc`, so OpenViking
resolves every caller from a Vault-signed JWT and no key is accepted.

Terraform still derives the old per-user keys from a seed and writes them to
`default/openviking-users/*`, because removing that apparatus is a separate
change. Nothing reads them. A client still holding one gets a 401, logged
server-side as `Invalid OIDC token: Invalid token format` -- misleading, and
worth knowing: an old key is `base64url(account).base64url(user).base64url(
secret)`, exactly two dots, and upstream treats any two-dot credential as a JWT
before failing to parse it. Those warnings are stale keys being refused, not a
fault.

Deleting the seed and the KV entries would turn that quiet refusal into a loud
failure at Vault, which is the better shape and is not done yet.

### What this costs

Three things, all accepted.

**No admin path.** Role is always USER, so account and user management have no
credential. The Terraform provisioner that used to create accounts is gone,
because its call could not authenticate and its failure would have failed the
whole apply.

**Web Studio is unmounted.** Its settings page could not collect a credential
anyway: upstream replaces the connection form with an unsupported-mode alert
under `oidc`, and there is nothing for it to collect because the token comes
from Vault. See "No browser surface" below.

**Hermes needs a sidecar**, because its credential cannot live in its
environment. See the authentication section above.

## Using it from the CLI and from an agent

Both authenticate with a Vault identity token, and both use
`openviking-api.lab.orangecluster.nl`, which is an HAProxy route straight to
port 1933. That hostname is not unguarded: OpenViking answers 401 there without
a token, on the REST API and on `/mcp`.

```console
$ vault login -method=userpass username=jasper
$ export OV_URL=https://openviking-api.lab.orangecluster.nl
$ export OV_TOKEN=$(vault read -field=token identity/oidc/token/openviking)

$ curl -H "Authorization: Bearer $OV_TOKEN" "$OV_URL/api/v1/fs/ls?uri=viking://"
```

The Vault login lasts as long as its token renews; the identity token expires
in 30 days and is re-minted by reading that path again, with no browser. Send
it as `Authorization: Bearer`, or in `X-API-Key`, which upstream also accepts
for anything shaped like a JWT.

`ovx` wraps this so nothing lands in `~/.openviking/ovcli.conf`. That matters
because `ov config add` writes whatever it is given to disk in the clear:
`--api-key-env` resolves the variable at write time rather than holding an
indirection, so it stores the literal value exactly as `--api-key-stdin` does.
Measured by writing a config both ways and grepping the result.

For Claude Code, use the memory plugin, not an MCP registration:

```console
$ bash <(curl -fsSL https://raw.githubusercontent.com/volcengine/OpenViking/\
main/examples/memory-plugin-shared/install.sh)
```

It hooks the session lifecycle for auto-recall and auto-capture and reads
`~/.openviking/ovcli.conf`. The installer's legacy path registers a stdio MCP
proxy instead; plugin mode does not, so a separate `claude mcp add` is
redundant with it.

**An agent shares its principal's identity, and that is not laziness.**
OpenViking isolates user scopes absolutely: an ADMIN gets 403 on another user's
scope, and no role grants a cross-user read. An agent given its own user
therefore cannot see the scope of the person it works for, which for an
assistant is the whole job.

So Hermes's identity-token role carries `lab`/`jasper` and its writes land in
`viking://user/jasper`, indistinguishable from jasper's own. It holds no key,
and revoking it is removing one entry from `var.vault_openviking_workloads`
rather than rotating a seed that rotates everyone.

**Hermes reaches OpenViking through a loopback sidecar, not directly.** A
running process cannot have its environment changed, and every read of an
identity-token path mints a NEW token, so rendering one into Hermes's
environment restarted the task on every consul-template poll -- measured, it
flapped every few minutes. The sidecar reads the token from a file per request
instead, Nomad keeps that file fresh with `change_mode = "noop"`, and Hermes
holds a constant endpoint for the life of the process.

## Three forks, and how they were settled

### MinIO uses a static key, not workload identity

Every other keyless service here exchanges a Nomad Workload Identity JWT for
short-lived MinIO credentials. OpenViking cannot:

- `S3Config.validate_config` makes `access_key` and `secret_key` mandatory
  whenever `backend` is `s3`, so a keyless config is rejected before the client
  is built.
- The Rust client behind AGFS builds `Credentials::new(ak, sk, None, ...)`.
  The `None` is the session token, which STS credentials require.
- `session_token` is a forbidden extra key on `S3Config`, and `backend` accepts
  only `local`, `s3` and `memory`, so no config route reaches the SDK's default
  credential chain.

So the job reads the existing `openviking` MinIO user's key from Vault. There
is deliberately **no** `minio_iam_policy` named `openviking`: MinIO's claim mode
resolves a policy by the job id, so one would read as live while granting
nothing to a service that authenticates with a static key.

This is a step back from the direction the rest of the cluster is moving in,
forced rather than chosen. If upstream ever makes those two fields optional and
threads a session token, the route back is one config block.

### Rerank goes through Bifrost, which required upgrading it

OpenViking's OpenAI-compatible rerank clients send `documents` as a list of
bare strings. Bifrost accepted only the object form through 1.6.11 and rejected
strings with a flat `400 Invalid request payload` at its own edge, before the
request reached embark. `U7-upgrade-bifrost-2x` bumped the gateway to 2.0.0,
which normalizes both forms.

Pointing rerank straight at embark would have worked without that upgrade, and
was rejected: it would lose Bifrost's logging, governance and virtual-key
accounting for one call type.

### No browser surface here, and where the hostname went

`openviking.lab.orangecluster.nl` used to reach the same service through
`oauth2-proxy-openviking` on port 4182, and the only thing on it was upstream's
Web Studio. Studio cannot collect a credential under `oidc`, so the proxy gated
a UI nobody could finish logging into. Both are gone: the job, its Vault OIDC
client, its two KV entries, and the HAProxy backend.

Studio is unmounted with `OPENVIKING_WEB_STUDIO_DIR` pointing at a path that
does not exist. There is no config-file switch for it, and the variable takes
`/` down with it, because the root redirect is registered inside the same block
that mounts the bundle. Leaving it mounted with the proxy gone would have
served the UI to anyone reaching the edge: Studio answers without a token.

The name resolved to a 503 for a while, since the HAProxy frontend declares no
`default_backend`. It now reaches ov-dash, the dashboard it was held for:
a Node service on orangepi4a, routed by the `ovdash` backend, deployed by
`nomad_job.ov_dash` from `deployments/applications/services/ov-dash.hcl`. It
sends a person to Vault's own login page, trades the ID token that comes back
for a Vault token on the `jwt-lab` mount, mints their identity token
server-side and never hands the browser one, which is why nothing gates it at
the edge.

## Verifying a deployment

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

It does **not** measure anything about a running service. These checks need a
deployment and nothing in this repo automates them:

```console
# the service is up and its backends opened
$ curl -s "$OV_URL/ready"

# Studio is unmounted, so this one is expected to fail with a 404.
$ curl -s -o /dev/null -w "%{http_code}\n" "$OV_URL/studio/"   # expect 404

# ov-dash answers on the short hostname. /health needs no session.
$ curl -s -o /dev/null -w "%{http_code}\n" \
    https://openviking.lab.orangecluster.nl/health             # expect 200

# the whole identity chain, both directions. Asserts the token is accepted and
# reaches its OWN tree, that no credential and a foreign audience are refused,
# and reports whether an account that was never created is usable
$ python3 scripts/ov_identity_probe.py --account lab --user jasper

# an unauthenticated call is refused. This is the one that justifies opening
# 1933 to the LAN, so it is the one to run first after an apply
$ curl -s -o /dev/null -w "%{http_code}" "$OV_URL/api/v1/fs/ls"   # expect 401

# embeddings reach embark through the gateway
$ python3 scripts/bifrost_smoke.py

# rerank reaches embark, in the bare-string shape OpenViking sends.
# bifrost_smoke.py does NOT cover this: its rerank calls assert a 401 and
# deliberately send the object form, so a green run says nothing about it
$ python3 scripts/embark_rerank.py

# how long an authenticated call takes. Unmeasured. Under oidc the cost per
# request is JWT signature verification rather than an Argon2id hash, and the
# JWKS is fetched over the network at request time, so the number is worth
# having on an SBC. Record what this comes out at
$ OV_TOKEN=$(vault read -field=token identity/oidc/token/openviking)
$ curl -s -o /dev/null -w "%{time_total}\n" \
    -H "Authorization: Bearer $OV_TOKEN" "$OV_URL/api/v1/fs/ls?uri=viking://"
```

The dimension is **384**, measured against `embark/embedding` through Bifrost.
A wrong value corrupts the collection without erroring, which is why the
checker asserts it rather than a comment recording it.

If that latency turns out unacceptable, the thing to change is the guard in
`scripts/check_openviking_config.py`, which now forbids turning the hashing
off. That is deliberate: the trade is worth making in the open.

## The VLM, and why the model list is measured

Image summaries go to `ollama/glm-5.3-flash` through Bifrost, the same route as
embedding and rerank. The virtual key carries `ollama` alongside `embark`.

Being in Bifrost's catalog is not enough. Of the models tried, only
`glm-5.3-flash` accepted an image; plain `glm-5.3`, `glm-5.2`, `glm-5.1` and
both `deepseek-v4` variants are cataloged, answer text, and refuse an image
with `this model does not support image input`. `gemma4:31b`, `kimi-k3`,
`minimax-m3` and `qwen3.5:397b` also work.

Retrieval planning runs on `ollama/gemma4:31b` through the same gateway.
`query_planner` is optional and falls back to the `vlm` block when unset, so
leaving it out is legal and silent -- and means planning runs on the vision
model at vision cost. The checker asserts it is set for that reason.

Picking a blind model is not a loud failure, which is why
`scripts/check_openviking_config.py` pins the list. OpenViking catches the
error and returns a normal-looking summary:

```python
except Exception as e:
    logger.error(...)
    return {"name": file_name, "summary": "Image summary generation failed"}
```

That string is then embedded as the image's content. The ingest reports
success, every image gets the same vector, and they become each other's
nearest neighbors in the collection. Measure a model before adding it to
`VISION_MODELS`, by POSTing an image to Bifrost and reading the answer back.

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

## What is not configured

No agent has its own user yet. The route in works and is documented above, but
every caller today borrows a person's key. Giving an agent its own is one line
in `local.openviking_people`, which would also give it its own account. That is
exactly why Hermes does not have one: an agent in its own account cannot see
its principal's data at all. What may hold one is the open
question.

## The database already existed

The `openviking` database, its role and the `vector` extension were created
before this service was. Its `openviking` schema already held empty
`ov_collections` and `ov_indexes` tables matching ov-postgres v0.2.0's DDL, so
the adapter adopts them rather than migrating.

Five `dbg_fts*` schemas from earlier experimentation are still there. Dropping
them is a hand-run operator step on purpose: a `postgresql_schema` resource
would put a live `DROP` behind every future apply against the vector store's
own database.
