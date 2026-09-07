# Building our own OpenViking dashboard

**Worth doing, roughly four loop tickets, and the reason is authentication.**
A dashboard we own can hold each person's OpenViking key server-side and
resolve who they are from the Vault OIDC session the edge already
establishes. The browser then never holds a key, and the two identity systems
this deployment runs in parallel collapse into one. Search is the biggest
surprise: dense vector search is live, hybrid sparse search is blocked by a
choice we do not control, and a Postgres full-text index that no API can query
already exists in the store.

Nothing here was measured against the running service. Every claim is read
from source at the versions named under "Provenance". The four claims that
need a live check are listed under "Unmeasured", each with the command that
would settle it.

## Why build one: one identity instead of two

Today two systems answer two different questions, and `docs/openviking.md`
records why. `oauth2-proxy-openviking` gates the hostname behind a Vault
login. OpenViking itself runs `auth_mode: "api_key"` and resolves each caller
from a long-lived key. The key exists because Web Studio refuses to run
against `oidc` or `ldap`, so making OpenViking speak OIDC costs us the browser
half of the service.

A dashboard we own removes that trade instead of paying it:

1. The app sits behind oauth2-proxy, which already injects
   `X-Forwarded-User`, `-Email` and `-Preferred-Username`. That is not a
   change we request. `PASS_USER_HEADERS` defaults true in v7 and
   `deployments/infrastructure/services/oauth2-proxy-openviking.hcl` documents
   the four headers as inert because OpenViking ignores them.
2. The backend reads that header, fetches that person's key from Vault under
   `secret/default/openviking-users/<user>`, and calls OpenViking as them.
3. The browser holds a session cookie that expires with the Vault token in an
   hour. No API key reaches it, and none is written to anyone's disk.

Two costs, both real and both worth a decision rather than an assumption.

**Header trust.** Nothing in this repo consumes those headers today. A grep
over `.py`, `.tf`, `.hcl`, `.html` and `.md` returns no hits, so this would be
the first consumer. The headers are only trustworthy if the app cannot be
reached except through the proxy. That means a loopback upstream plus the
single-caller firewall rule dash already uses at
`deployments/applications/services.tf:144`. Get it wrong and identity becomes
a spoofable header on the LAN.

**A Vault grant wider than the usual one.** A Nomad job's role grants read on
`secret/data/default/<job_id>/*`. Reading every person's key is outside that
prefix, so this needs its own role and its own justification. It also makes
the dashboard a target worth more than the sum of its views.

## What it would cost

This repo already builds this exact shape twice. `dash` and `registry-ui` are
each an nginx container serving one hand-written `index.html` plus a Python
container talking to an upstream API, both behind their own oauth2-proxy. The
dashboard is that again with a different upstream.

Measured from `deployments/applications/services/dash`:

| Part | Lines |
|---|---|
| Backend source (10 modules) | 1,224 |
| Backend tests (7 files) | 1,093 |
| Frontend `index.html`, no build step | 661 |
| `tiles.json` | 327 |

Estimated split for the OpenViking dashboard:

| Piece | Size | Note |
|---|---|---|
| Broker backend | M | Identity from headers, key from Vault, proxy to OpenViking. Carries the whole security story, so it earns its own ticket and review. |
| Explorer view | M to L | Rebuild against `fs/ls`, `fs/tree`, `fs/stat`, `fs/attrs`, `content/read`, `content/abstract`, `content/download`. Bulk of the frontend. |
| Search view | M | Dense through the API, keyword through Postgres, fused. Larger than first estimated. See below. |
| Deploy | S | Jobspec, two images, firewall rule, HAProxy route at `deployments/infrastructure/services/haproxy.hcl:110`, oauth2-proxy upstream. Copy `dash.hcl`. |

Do not iframe Web Studio for the explorer. It is a 15 MB single-page app whose
main bundle alone is 900 KB, and it expects an API key in the browser, which
is the thing this design removes.

## Search: three engines, one reachable

### Dense vector, live today

`/api/v1/search/find` and `/api/v1/search/search` run pgvector cosine
similarity and then rerank through `embark/reranker` on Bifrost.
`/api/v1/search/search` with `mode: "context"` returns a token-budgeted,
deduplicated context block. `/grep` and `/glob` scan a URI subtree literally
and use no index.

Filters available on both: `tags`, `since`, `until`, `time_field`,
`context_type`, `level`, `score_threshold`, plus a raw `filter` object.

### Hybrid sparse, built and blocked

The plumbing is complete and switched off. The ov-postgres adapter fuses a
dense and a sparse term whenever `sparse_weight > 0` and the schema declares a
sparse field (`collection.py:1672` and `collection.py:1729`). OpenViking
declares `sparse_vector` in the context collection unconditionally
(`storage/collection_schemas.py:96`), and the adapter maps that type to a
`jsonb` column (`ddl.py:349`).

The blocker is the embedder, not the store. Our `embedding` block configures
only `dense` with `provider: "openai"` pointed at Bifrost, and
`OpenAISparseEmbedder` exists solely to raise "OpenAI does not support sparse
embeddings" (`models/embedder/openai_embedders.py:369`). Only
`VolcengineSparseEmbedder` and `VikingDBSparseEmbedder` produce sparse
vectors, and both call Volcengine cloud APIs that embark does not serve.

Two smaller walls behind that one, worth knowing before anyone tries:

- `sparse_weight` is read from the parent vectordb config, not from
  `custom_params`. `PgVectorParams` is `extra="forbid"` and declares no such
  field, and `scripts/check_openviking_config.py` pins the allowed
  `custom_params` keys.
- Changing the active embedding config changes the collection's embedding
  signature. That is a reindex of everything, not a config flip.

Conclusion: treat sparse-vector hybrid as unavailable until the embedding
route changes. It is not a small switch.

### Full-text, indexed and unreachable

This is the useful finding. The adapter builds a GIN index over
`to_tsvector` of `name`, `description`, `abstract`, `tags` and `search_tags`
at collection creation (`ddl.py:601`, called from `collection.py:525`), and
`search_by_keywords` ranks matches with `ts_rank` (`collection.py:1240`).

No OpenViking HTTP route calls it. The index is maintained on every write and
nothing can query it.

So we can have real hybrid search without sparse vectors: run
`/api/v1/search/find` for the dense side, query that Postgres table for the
keyword side, and fuse the two rankings. Reciprocal rank fusion over two
result lists is about eighty lines.

**This replaces the DuckDB idea.** The index we were going to build already
exists, OpenViking maintains it on write, and it needs no sync job. Note that
`deployments/applications/database.tf:11` and
`deployments/applications/storage.tf:5` already provision a `ducklake`
database and MinIO users that no job consumes, so a second store would also
have been a second unused one.

### The cost of going around the API

Reading the collection table directly leaves the API's protection behind.
OpenViking enforces per-user isolation in its service layer, so in SQL we
enforce it ourselves. The table carries `account_id` and `owner_user_id`
columns alongside `uri`, so the filter is writable, but a mistake leaks one
person's rows to another with no 403 to announce it.

If we do this, the scope filter needs its own tests and its own review pass,
and it should be the narrowest possible query rather than a general SQL
surface.

## Unmeasured

Four things this document asserts from source and nobody has checked against
the running deployment. `scripts/check_openviking_config.py` measures nothing
about a live service, and no gate in this repo does either.

**1. Does the deployed table actually have the sparse column?** The code path
creates it: the field is declared unconditionally and maps to `jsonb`. But
`create_collection` returns early when the collection already exists, and the
adapter has no `ALTER TABLE ... ADD COLUMN` path anywhere. `ensure_indexes`
reconciles indexes only. `backfill_defaults` fills values, and it skips
`sparse_vector` deliberately (`schema.py:420`). So a table created by an
earlier schema would never gain the column, and nothing would report that.

`docs/openviking.md` records that the `openviking` schema already held empty
`ov_collections` and `ov_indexes` tables when the service was deployed, which
is exactly the situation where an adopted table could differ from what the
current code would create.

```console
$ PGHOST=$(consul catalog nodes -service=postgres -detailed)   # node_address
$ vault kv get -mount=secret default/openviking/db             # username, password
$ psql -h "$PGHOST" -U openviking -d openviking -c \
    "SELECT name, table_name FROM openviking.ov_collections"
$ psql -h "$PGHOST" -U openviking -d openviking -c \
    "\d openviking.<table_name from above>"
```

Look for a `sparse_vector jsonb` column and an index whose name ends
`fts_idx`. The second one decides whether the hybrid plan above is real.

**2. How slow is an authenticated call?** `encryption.api_key_hashing` is on,
so the server verifies an Argon2id hash (time cost 3, 64 MiB) per request, on
the event loop, with no cache, on an SBC. `docs/openviking.md` flags this and
says nobody has the number. A dashboard issues far more calls per view than
the CLI does, so this can sink the design on its own.

```console
$ curl -s -o /dev/null -w "%{time_total}\n" \
    -H "X-API-Key: $OV_KEY" "$OV_URL/api/v1/fs/ls?uri=viking://"
```

Run this before writing any code. If it is slow, the fix is a decision about
hashing, and the guard in `scripts/check_openviking_config.py` currently
forbids turning it off on purpose.

**3. Do the oauth2-proxy headers actually arrive?** Read from v7 source and
from the jobspec comment, never observed. One request through the edge to any
echo endpoint settles it.

**4. Is the usage and audit projection running?** `UsageAuditConfig.enabled`
defaults true (`server/config.py:232`) and our `observability` block sets
`metrics` and `traces` but not `usage_audit`, so it should be live on the
sqlite backend. If it is, the console endpoints below already return data.

## What to put in it

Consumer-facing only. Admin endpoints under `/api/v1/admin` are out of scope
for this dashboard, and the observer endpoints are operator signals rather
than user ones.

Strong:

- **Chat over your own memory.** `/bot/v1/chat` and `/bot/v1/chat/stream`,
  with `/bot/v1/feedback`. A streaming question-and-answer endpoint against
  the caller's own store. Studio does nothing with it. Probably the single
  best feature in the API.
- **Version history.** `/api/v1/snapshot/log`, `/show`, `/diff`, `/restore`,
  `/commit`, `/ignore`. Git-style time travel over your own files.
- **Ingest progress.** `/api/v1/tasks`, `/api/v1/tasks/{id}` and
  `/api/v1/tasks/{id}/cancel`. Uploads are asynchronous and today give no
  progress and no way to stop them. Cheap and immediately felt.
- **Session browser.** `/api/v1/sessions/{id}/context`, `/tool-results`, and
  search within those results. What an agent actually saw and did.

Good, and cheap once the broker exists:

- **Usage.** `/api/v1/console/dashboard/summary`, `/tokens`,
  `/context-commits`, `/audit`. The role gate admits `USER`. Retention is 14
  days for usage and 7 for audit.
- **Memory health.** `/api/v1/stats/memories`, `/api/v1/stats/sessions/{id}`.
- **Watches.** `/api/v1/watches`, with per-watch trigger. Tell me when this
  changes.
- **Skills.** `/api/v1/skills` list, get, put, delete, validate, find.
- **Privacy rules.** `/api/v1/privacy-configs`, versioned, with activate.
- **Export.** `/api/v1/pack/export`, a download-my-data button.

One with a bonus:

- **Upload destinations.** `/api/v1/user-settings/add-locations`, GET, PATCH
  and DELETE. This is the per-user override of where an upload lands, and it
  is a user setting rather than an admin one. The plan-validator verdict on
  `OV2-openviking-user-scoped-resources` showed Web Studio defeats this by
  always posting an explicit `parent`. In a client we write, we control what
  is posted, so honoring it works. That is a second and softer route at the
  user-scoped-resources problem, and it needs no account split.

Skip for now:

- **WebDAV.** `/webdav/resources` names the account-shared tree as a literal
  in server Python (`server/routers/webdav.py:73`) and its router is
  registered unconditionally, so it ignores user scoping entirely.

## Dependency on OV2

`.loop/plans/OV2-openviking-user-scoped-resources.md` reshapes identity to one
account per person, and its plan-validator verdict currently reads `fail`. The
broker's Vault lookup depends on that shape. Either settle OV2 first, or build
the broker against a mapping local rather than a hardcoded account name.

The `add-locations` route above may also change what OV2 needs to do, since a
client we control can respect a per-user target that Studio overrides.

## Suggested ticket split

1. **Broker backend.** Identity from headers, key from Vault, proxy to
   OpenViking, refuse everything unauthenticated. Carries the Vault role
   change and the firewall shape. The security ticket.
2. **Explorer and preview.** Tree, listing, content read, download.
3. **Hybrid search.** Dense through the API, keyword through Postgres, fused,
   with the scope filter as the reviewed centerpiece. Blocked on Unmeasured
   item 1.
4. **Deploy.** Jobspec, images, firewall, HAProxy route, proxy upstream.

Items 1 and 3 hold the design forks. Items 2 and 4 are copies of work this
repo has done twice.

## Provenance

Read from the installed copies, not from upstream documentation:

| Thing | Version | Where |
|---|---|---|
| OpenViking | 0.4.17.1 | the tag `deployments/applications/services.tf` pins as `openviking_base_image` |
| ov-postgres | 0.2.0 | pinned by git tag in `deployments/applications/services/openviking/Dockerfile.openviking`, from our own `openviking_extensions` repo |

That second row matters for the search plan. We own ov-postgres, so exposing
`search_by_keywords` through a supported interface is a change we can make
rather than one we must work around.
