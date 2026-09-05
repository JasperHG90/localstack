# OpenViking

A context store for agents, on radxa beside Bifrost. Vectors go to Postgres,
blobs to MinIO, embeddings and rerank through Bifrost to embark, and browser
logins through Vault.

## What runs where

| Piece | Where |
|---|---|
| Job | `openviking` on radxa-dragon-q6a, port 1933 |
| Edge | `https://openviking.lab.orangecluster.nl` |
| Login gate | `oauth2-proxy-openviking` on port 4182 |
| Vectors | Postgres `openviking` database, `openviking` schema, pgvector |
| Blobs | MinIO `openviking` bucket |
| Models | Bifrost, as `embark/embedding` and `embark/reranker` |

The image is derived, and building it is an operator step. See
`deployments/applications/services/openviking/README.md`.

## Authentication uses Vault, in two hops

A browser reaching the edge is redirected to Vault's `lab` OIDC provider by
oauth2-proxy. The proxy then forwards the Vault ID token upstream
(`OAUTH2_PROXY_PASS_AUTHORIZATION_HEADER`), and OpenViking, running
`auth_mode: "oidc"`, validates that same token against Vault's JWKS.

Both hops therefore resolve to one Vault identity. The setting that makes the
second hop work is easy to drop, and dropping it leaves a browser flow that
still looks correct while OpenViking sees an unauthenticated request.

`OAUTH2_PROXY_SET_AUTHORIZATION_HEADER` is a different setting and must stay
unset: it writes the Authorization header on the RESPONSE, handing the raw
Vault ID token back to the browser instead of forwarding it upstream.

OpenViking's own OAuth 2.1 implementation is **off**. It is an authorization
server whose identity always originates from an OpenViking API key, so it
cannot use Vault. The cost of that choice: an external MCP client that speaks
only OAuth 2.1 cannot connect.

`audience` and `client_id` are the same value, and it is Vault-generated. The
client is created in the infrastructure root, and the applications root reads
it back through `data "vault_identity_oidc_client_creds" "openviking"`. Nothing
writes it down twice.

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

`scripts/check_openviking_config.py` runs in pre-commit and asserts the config
values that fail silently: the embedding dimension, the vector backend, the
`custom_params` key allow-list, the rerank target, `auth_mode`, and that
`audience` equals `client_id`.

It does **not** measure anything about a running service. These checks need a
deployment and nothing in this repo automates them:

```console
# the service is up and its backends opened. Checked ON the node: the edge
# hostname routes to the proxy, which carries no auth exemption by design, so
# /ready through it answers with a sign-in page rather than readiness JSON
$ ssh radxa@192.168.2.50 curl -s http://127.0.0.1:1933/ready

# a browser login lands authenticated rather than looping
$ open https://openviking.lab.orangecluster.nl/

# a token minted for another client is refused. Also on the node, and for the
# same reason: a curl carrying a bearer token but no proxy session cookie is
# redirected to Vault by the proxy and never reaches OpenViking
# The remote command is ONE quoted string: ssh joins its argv with spaces and
# hands the result to a shell, so unquoted here the remote curl would see
# `-H Authorization:`, which is how curl REMOVES a header, and would report
# the plain unauthenticated 401 while sending no token at all
$ ssh radxa@192.168.2.50 'curl -s -o /dev/null -w "%{http_code}" \
    -H "Authorization: Bearer <token minted for another client>" \
    http://127.0.0.1:1933/api/v1/collections'   # expect 401

# embeddings reach embark through the gateway
$ python3 scripts/bifrost_smoke.py

# rerank reaches embark, in the bare-string shape OpenViking sends.
# bifrost_smoke.py does NOT cover this: its rerank calls assert a 401 and
# deliberately send the object form, so a green run says nothing about it
$ python3 scripts/embark_rerank.py
```

The dimension is **768**, measured against `embark/embedding` through Bifrost.
A wrong value corrupts the collection without erroring, which is why the
checker asserts it rather than a comment recording it.

## What is not configured

No `vlm` section. Bifrost's `ollama` provider is Ollama Cloud, and a model must
exist in Bifrost's catalog for that provider or the call returns 403 regardless
of the virtual key's allowlist. No vision model has been chosen, and naming an
uncatalogued one yields a config that validates and then fails on first use.

No agent access. `auth_mode` selects exactly one plugin and Vault's `lab`
provider offers only the authorization-code grant, so nothing headless can mint
a token for it. `auth_mode: "trusted"`, which takes identity from
`X-OpenViking-Account` / `X-OpenViking-User` headers behind a root key, is the
candidate for that follow-up, and its precondition is that every route to port
1933 passes through the proxy.

## The database already existed

The `openviking` database, its role and the `vector` extension were created
before this service was. Its `openviking` schema already held empty
`ov_collections` and `ov_indexes` tables matching ov-postgres v0.2.0's DDL, so
the adapter adopts them rather than migrating.

Five `dbg_fts*` schemas from earlier experimentation are still there. Dropping
them is a hand-run operator step on purpose: a `postgresql_schema` resource
would put a live `DROP` behind every future apply against the vector store's
own database.
