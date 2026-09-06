# OpenViking

A context store for agents, on radxa beside Bifrost. Vectors go to Postgres,
blobs to MinIO, embeddings and rerank through Bifrost to embark, image
summaries through Bifrost to ollama, and browser logins through Vault.

## What runs where

| Piece | Where |
|---|---|
| Job | `openviking` on radxa-dragon-q6a, port 1933, open to the LAN |
| Browsers | `https://openviking.lab.orangecluster.nl` |
| CLI and agents | `https://openviking-api.lab.orangecluster.nl` |
| Login gate | `oauth2-proxy-openviking` on port 4182, browsers only |
| Vectors | Postgres `openviking` database, `openviking` schema, pgvector |
| Blobs | MinIO `openviking` bucket |
| Models | Bifrost, as `embark/embedding` and `embark/reranker` |
| Image summaries | Bifrost, as `ollama/glm-5.3-flash` |
| Query planning | Bifrost, as `ollama/gemma4:31b` |

The image is derived, and building it is an operator step. See
`deployments/applications/services/openviking/README.md`.

## Authentication: OpenViking's own users, behind a Vault gate

Two layers, and they answer different questions.

**Who may reach the hostname** is oauth2-proxy's job. It gates
`openviking.lab.orangecluster.nl` behind a Vault login, so nothing on the LAN
reaches the service without an account in Vault.

It does inject four headers, since `PASS_USER_HEADERS` defaults to true in v7:
`X-Forwarded-Groups`, `-User`, `-Email` and `-Preferred-Username`. OpenViking
reads none of them, so they are inert. It forwards no Vault ID token, injects
no `Authorization` header, and leaves an incoming one alone, so a caller
through the edge may send its key either way. Studio uses `X-API-Key`.

**Who you are once inside** is OpenViking's own multi-tenant model. An account
holds users, each user has a key, and data ownership resolves from that key.
The server enforces the role attached to each key, and a caller cannot assert
a different one: there is no header or claim that changes who OpenViking
thinks you are.

| Key | Held by | Role | Purpose |
|---|---|---|---|
| Root | the job, from Vault | ROOT | account and user management |
| `jasper` | a person | ADMIN | own data, plus user management in `lab` |
| `veerle` | a person | USER | own data |

### Why not Vault as the identity itself

Both modes that would do it are unusable here. Web Studio refuses to run
against `oidc` and `ldap` outright:

```js
const isUnsupportedAuthMode = serverMode === 'oidc' || serverMode === 'ldap'
```

Under `oidc` the API works and the entire browser half of the service does not.

`trusted` mode would let the proxy assert identity in headers, and it fails at
both settings of its one switch. Without a root key, `TrustedAuthPlugin`
refuses to start at all on a non-loopback bind, and this job binds `0.0.0.0`.
With one configured, every call carries that same root credential, so the two
people stop being distinguishable, which is the whole thing this deployment
wants.

`api_key` is the mode upstream recommends, and it is the only one with per-user
isolation and a working Studio. The cost is that a person holds an OpenViking
key as well as a Vault login: Vault gates the hostname and OpenViking decides
who you are.

### Where a key comes from

A user key is `base64url(account).base64url(user).base64url(secret)` where
`secret = sha256(user_id + NUL + seed)`. Terraform computes that locally from
one seed in Vault, so the key exists in state and in Vault before the server
ever sees it, and `terraform apply` is idempotent instead of minting a new key
per run. The Admin API call only *registers* the user with the same seed.

Three details in that derivation each produce a key that looks correct and is
rejected, so `secrets.tf` spells them out: the separator is a NUL, padding is
stripped entirely rather than one character, and the alphabet is URL-safe.

The seed lives at `default/openviking-seed/seed`, deliberately away from the
root key. `default/openviking/*` is the prefix the job's own Vault role grants
it, and anyone holding the seed derives every human's key offline, so the
service must not be able to read it.

Getting your key:

```console
$ vault kv get -mount=secret default/openviking-users/jasper
```

Rotating everyone's key at once is a change to one seed. Adding a person is one
line in `local.openviking_users`.

**Taking a person away is not.** Deleting their line destroys their Vault entry
and visits them in no Admin API call, so `terraform apply` reports success
while their key still works and their data is still in the account. Terraform
has just deleted the record that would have shown you this. Offboard by hand
first, then remove the line:

```console
$ ROOT_KEY=$(vault kv get -field=root_api_key -mount=secret \
    default/openviking/root)
$ curl -X DELETE -H "X-API-Key: $ROOT_KEY" \
    "$OV_URL/api/v1/admin/accounts/lab/users/veerle"
```

That call also starts durable cleanup of everything they own, which is why no
apply runs it for you. If the key may have leaked, rotate the seed too: their
key is derived, so anyone who held the seed can recompute it.

A role change reconciles in one direction only. `set_user_role` upstream
refuses anything but a promotion, so admin to user updates Vault and leaves the
server alone. That one is a hand step as well.

### What this costs against OIDC

Worth stating plainly, because the previous deployment did better on this axis.
Under `oidc` OpenViking verified each caller cryptographically against Vault's
JWKS, no long-lived secret existed anywhere, and a token expired in an hour.
An API key does not expire, exists in Terraform state and in Vault, and is
revoked only by regenerating it.

`encryption.api_key_hashing` is enabled so the server stores Argon2id hashes
rather than the keys themselves, which keeps the key store from being a list of
working credentials. The rest of the trade is real and is accepted because the
alternative is a service whose UI nobody can open.

## Using it from the CLI and from an agent

Both hold the same key a browser user holds, and both use
`openviking-api.lab.orangecluster.nl`, which is its own HAProxy route straight
to port 1933. The `openviking.` hostname is for browsers only: oauth2-proxy
gates it with a Vault session cookie, and no CLI or MCP client can hold one.

Two hostnames rather than an exemption on the proxy. `bifrost.` already works
this way for the same reason, and `scripts/check_oauth2_proxy_guard.py` forbids
a skip-auth route on an oauth2-proxy. The API hostname is not unguarded:
OpenViking answers 401 there without a key, on the REST API and on `/mcp`.

```console
$ export OV_URL=https://openviking-api.lab.orangecluster.nl
$ export OV_KEY=$(vault kv get -field=api_key -mount=secret \
    default/openviking-users/jasper)

$ printf '%s' "$OV_KEY" | ov config add custom --name lab \
    --url "$OV_URL" --api-key-stdin --activate
$ ov config validate
```

**Every flag writes the key to disk in the clear.** `--api-key-env` does not
hold an indirection: it resolves the variable when the config is written, so
`~/.openviking/ovcli.conf` ends up carrying the literal key exactly as
`--api-key-stdin` does. Measured by writing a config both ways and grepping the
result. `ov` also refuses to run from environment alone -- with no config file
it answers `No ovcli.conf detected` whatever is exported.

`OPENVIKING_CLI_CONFIG_FILE` is the way out. It moves where `ov` READS its
config, so the file can live somewhere that is not the disk. Write it yourself;
`ov config add` ignores the variable and still writes under `~/.openviking`.

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
OpenViking isolates user scopes absolutely: jasper with role ADMIN gets 403 on
`viking://user/hermes`, and hermes gets 403 on `viking://user/jasper`. ADMIN
manages users, it does not read their data, and no role grants a cross-user
read. An agent given its own user therefore cannot see the scope of the person
it works for, which for an assistant is the whole job.

So Hermes holds jasper's key and writes into `viking://user/jasper`. Its
writes are indistinguishable from jasper's own, and revoking it means rotating
the seed, which rotates jasper too. `viking://resources` is account-shared and
readable by every identity, so anything meant for all of them belongs there.

## Two forks, and how they were settled

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

## Verifying a deployment

`scripts/check_openviking_config.py` runs in pre-commit and asserts the nine
config values that fail silently: the embedding dimension, the vector backend,
the `custom_params` key allow-list, the rerank target, `auth_mode`,
`root_api_key`, `api_key_hashing`, and the VLM's model and `api_base`. Without
a root key under `api_key` mode the server calls `sys.exit(1)` at startup, on
loopback and off it.

It does **not** measure anything about a running service. These checks need a
deployment and nothing in this repo automates them:

```console
# the service is up and its backends opened. It MUST be the api hostname:
# openviking.lab.orangecluster.nl/ready answers 200 with the body "OK", which
# is oauth2-proxy's OWN health endpoint and says nothing about OpenViking.
# That check passes with the service dead
$ curl -s "$OV_URL/ready"

# a browser login lands authenticated, and Studio loads and accepts a user
# key rather than refusing the auth mode
$ open https://openviking.lab.orangecluster.nl/

# each person is a separate identity with their own key
$ vault kv get -field=api_key -mount=secret default/openviking-users/jasper
$ vault kv get -field=api_key -mount=secret default/openviking-users/veerle

# an unauthenticated call is refused. This is the one that justifies opening
# 1933 to the LAN, so it is the one to run first after an apply
$ curl -s -o /dev/null -w "%{http_code}" "$OV_URL/api/v1/fs/ls"   # expect 401

# embeddings reach embark through the gateway
$ python3 scripts/bifrost_smoke.py

# rerank reaches embark, in the bare-string shape OpenViking sends.
# bifrost_smoke.py does NOT cover this: its rerank calls assert a 401 and
# deliberately send the object form, so a green run says nothing about it
$ python3 scripts/embark_rerank.py

# how long an authenticated call takes. Unmeasured, and the one number here
# nobody has: api_key_hashing verifies an Argon2id hash per request
# (time_cost 3, memory_cost 64 MiB) on the event loop, with no cache, on an
# SBC. Studio fires many calls per view. Record what this comes out at
$ curl -s -o /dev/null -w "%{time_total}\n" \
    -H "X-API-Key: $OV_KEY" "$OV_URL/api/v1/fs/ls?uri=viking://"
```

The dimension is **768**, measured against `embark/embedding` through Bifrost.
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
every caller today borrows a person's key. Giving an agent its own is two lines
in `local.openviking_users`; what may hold one is the open question.

## The database already existed

The `openviking` database, its role and the `vector` extension were created
before this service was. Its `openviking` schema already held empty
`ov_collections` and `ov_indexes` tables matching ov-postgres v0.2.0's DDL, so
the adapter adopts them rather than migrating.

Five `dbg_fts*` schemas from earlier experimentation are still there. Dropping
them is a hand-run operator step on purpose: a `postgresql_schema` resource
would put a live `DROP` behind every future apply against the vector store's
own database.
