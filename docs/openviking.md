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

### One account per person, and why it is the account rather than a setting

Each person gets their own OpenViking ACCOUNT, not a user inside a shared one.
The account is the first segment of every stored path
(`/local/<account_id>/...`), so two accounts never address the same bytes.
Vectors are separated by a different mechanism for the same effect: both
accounts would share one Postgres collection, so the server ANDs an
`account_id` equality into every query and stamps it on every write.

The alternative was a per-user default upload target
(`server.user_config_defaults.add_targets.resource_uri`), and it does not work
here. It is consulted only when a caller supplies neither `to` nor `parent`,
and the two surfaces a person actually uploads through both supply one: Web
Studio's add-resource form ships prefilled with `viking://resources/`, and
WebDAV builds that same URI as a literal in server Python. Configuration
reaches neither. The account does.

Inside an account `viking://resources` is still shared by every user in it.
At one person per account that is a tree of one, and it stops being one the
moment a second person joins.

Under `oidc` every caller resolves to role USER. The plugin never consults a
role mapping and never consults `server.root_api_key`, so no admin route has a
reachable credential and nothing can create an account.

Nothing needs to. MEASURED after the switch with
`scripts/ov_identity_probe.py`: a token naming an account that was never
created returns 200 and reads an empty tree. So adding a person is a Vault
entity carrying `ov_account` and nothing else, and the provisioner that used
to POST to the Admin API is gone rather than replaced.

The cost of that is a typo. A misspelled `ov_account` does not fail; it opens
a new empty account, and the person sees an empty tree rather than an error.

### Where a key comes from

A user key is `base64url(account).base64url(user).base64url(secret)`, and here
the first two segments carry the same string, because the account id IS the
person's user id. The secret is derived from the user id and the seed and NOT
the account, which is why giving everyone their own account re-homed every key
without rotating any secret. The derivation is
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
line in `local.openviking_people`, which gives them their own account as well
as their own key.

**Taking a person away is not.** Deleting their line destroys their Vault entry
and visits them in no Admin API call, so `terraform apply` reports success
while their key still works and their data is still in their account. Terraform
has just deleted the record that would have shown you this. Offboard by hand
first, then remove the line.

The call is against the ACCOUNT, not the user, and that is not a style choice.
Under one account per person the per-user delete can never succeed: the server
refuses to remove an account's last active admin, and every account here has
exactly one. The fence tests the target's role, not the caller's, so the root
key does not get past it either.

```console
$ ROOT_KEY=$(vault kv get -field=root_api_key -mount=secret \
    default/openviking/root)
$ curl -X DELETE -H "X-API-Key: $ROOT_KEY" \
    "$OV_URL/api/v1/admin/accounts/veerle"
```

That removes `/local/veerle` entirely, taking their resources, memories and
skills with it, which is why no apply runs it for you. If the key may have
leaked, rotate the seed too: their key is derived, so anyone who held the seed
can recompute it.

There are no roles left to reconcile. Everyone is ADMIN of their own account
from the moment `POST /accounts` creates it, and `set_user_role` upstream
refuses anything but a promotion, so there is nothing for an apply to change.

### Closing the old `lab` account

Before this deployment gave each person their own account, both shared one
called `lab`. That account still exists, still holds everything uploaded before
the change, and is still shared. Nothing in the move revoked its keys.
`ov config add` writes a key to disk in the clear, so a working `lab` key is
probably still sitting in `~/.openviking/ovcli.conf` on more than one laptop.

Re-minting both keys from a seed you keep nowhere kills those copies without
destroying the content:

```console
$ ROOT_KEY=$(vault kv get -field=root_api_key -mount=secret \
    default/openviking/root)
$ umask 077 && printf '{"seed":"%s"}' "$(openssl rand -hex 24)" > /tmp/ov-remint.json
$ for u in jasper veerle; do \
    curl -sS -o /dev/null -w "$u %{http_code}\n" -X POST \
      -H "X-API-Key: $ROOT_KEY" -H 'Content-Type: application/json' \
      --data-binary @/tmp/ov-remint.json \
      "$OV_URL/api/v1/admin/accounts/lab/users/$u/key"; \
  done
$ rm -f /tmp/ov-remint.json
```

Two details in that block are the point of it, not decoration. `-o /dev/null`
is there because the endpoint returns the NEW key in its response body: print
it and you have replaced two leaked keys with two fresh ones in your
scrollback. And the seed goes in a 0600 file rather than an argument, because
an argv secret is readable from `ps` for the life of the call. The provisioner
beside this does both for the same reasons.

The old keys stop working immediately: the server stores an Argon2id hash of
the key, and a re-mint replaces it. The content stays where it is, reachable
again by re-minting once more with a seed you DO keep. That reversibility is
the reason to prefer this over `DELETE /accounts/lab`, which closes the same
hole by deleting everything in it.

Keep the throwaway seed nowhere: not in the file above, not in your shell
history, not in a password manager. The key is derived from it, so retaining
the seed retains the key.

### What this costs

Three things, all accepted.

**No admin path.** Role is always USER, so account and user management have no
credential. The Terraform provisioner that used to create accounts is gone,
because its call could not authenticate and its failure would have failed the
whole apply.

**Web Studio's settings page cannot collect a credential.** Upstream replaces
the connection form with an unsupported-mode alert under `oidc`. Studio itself
still renders; only that panel is dead, and there is nothing for it to collect
because the token comes from Vault.

**Hermes needs a sidecar**, because its credential cannot live in its
environment. See the authentication section above.

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

$ printf '%s' "$OV_KEY" | ov config add custom --name orangecluster \
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

So Hermes holds jasper's key and writes into `viking://user/jasper`, now inside
jasper's own account. Its writes are indistinguishable from jasper's own, and
revoking it means rotating the seed, which rotates jasper too.
`viking://resources` is still shared by every identity in an account, but an
account now holds one person, so no tree is readable by both. Sharing something
between them means copying it.

**Re-homing Hermes empties its memory.** OpenViking is its memory provider, so
its history lives under the old `lab` account and the new one starts blank.
That is a consequence of the move, not a fault to debug.

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

`scripts/check_openviking_config.py` runs in pre-commit and asserts the fifteen
config values that fail silently: the embedding dimension, the vector backend,
the `custom_params` key allow-list, the rerank target, `auth_mode`,
`root_api_key`, `api_key_hashing`, the VLM's model and `api_base`, the query
planner's model and `api_base`, `metrics.enabled` and its Prometheus exporter,
and `traces.enabled` with its endpoint. Without a root key under `api_key` mode
the server calls `sys.exit(1)` at startup, on loopback and off it.

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
