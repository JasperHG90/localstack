---
epic = "landing"
depends_on = ["L4-landing-dash-fe-be-split"]
priority = 10
summary = "Add a registry view to dash: a new /api/registry route on the backend that walks the cluster OCI registry with bounded eight-way concurrency, keeps a digest-keyed cache refreshed by a cheap HEAD sweep so newly pushed models and images appear within about a minute, deduplicates repo-tag pairs down to one card per distinct manifest digest, splits KitOps ModelKits from container images on the manifest's artifactType and renders a row for every image repo it finds, reading a plain image's config blob for the architecture and build date the mockup's images table shows while a manifest index gets a multi-arch marker instead, and returns a card assembled from the Kitfile config blob plus the docs layer's README.md rendered to HTML server-side with markdown-it-py; a SQLite store on a new dash_data host volume so the digest-keyed cards survive a restart and cold start is paid once ever rather than once per restart, with every database call pushed off the event loop through asyncio.to_thread and each of those workers opening and closing its own connection, because one connection shared across them breaks under the walk's concurrent writes; conditional manifest HEADs carrying If-None-Match so the sweep spends less time, though not fewer requests; a models/images tab strip in the frontend ported verbatim from the approved mockup, polling while visible and carrying a manual refresh; dash's own Vault KV copy of the registry credential; and the Terraform wiring plus a third oauth2-proxy upstream so the browser can reach the route, which stays behind the same session gate the homepage already has because no skip-auth exemption exists and this ticket adds none."
tags = ["dash", "registry", "kitops", "oci", "vault", "oauth2-proxy", "frontend", "markdown", "cache", "concurrency", "sqlite", "persistence", "async", "authz"]
premise = { Q1 = "a manifest HEAD returns Docker-Content-Digest with a zero-byte body, so a 13-request sweep detects every push without touching a blob, and a manifest digest is content-addressed so a rendered card for a digest is valid forever", Q2 = "the catalog holds zero image repos today, but the operator requires a pushed image to appear; repository, tag, digest and summed layer size are readable from the manifest the sweep already fetches, and arch and pushed come from one config blob per plain image digest, which is the same shape the Kitfile fetch already takes and not the index resolution Q2 refused", Q3 = "dash's page already carries its own header and refresh loop, and a registry poll needs its own slower timer scoped to the tab's visibility rather than a seat on the 15 s health loop", Q4 = "this repo has no JS or browser test harness, no package.json, and zero frontend tests, so no assertion about what the browser draws or how it responds to a click has a producer in the declared code surface, while the HTML string and the JSON payload are produced in Python and are fully assertable", Q5 = "the registry answers blob GETs with a 307 to a presigned MinIO URL, and that redirect is what keeps embark's multi-hundred-MB ModelKit pulls off the registry node", Q6 = "markdown-it-py 4.2.0 under preset js-default renders GFM tables and fenced code and escapes raw HTML by default, and it ships py.typed so mypy --strict needs no stub package", Q7 = "every repo carries 0.1.0 and latest resolving to one manifest digest, so a repo-tag walk draws each kit twice and pays two extra blob fetches for the duplicate", Q8 = "oauth2-proxy matches an upstream path exactly, so /api/registry/<repo> is unroutable and /api/registry/ falls through to the frontend, while /api/registry?card=<repo> still matches", Q9 = "the mockup's layers table had been lost in an incomplete edit, not omitted by design, which its orphaned .layers CSS evidenced; it has been restored so the modal order is card, layers, commands, matching the operator's stated order", Q10 = "the registry walk must be concurrent to be affordable, Starlette is already async, and starlette.testclient.TestClient drives an async route from a sync test with no new dev dependency", Q11 = "stdlib sqlite3 is present in the runtime image and has no async API, so a query called straight from an async handler blocks the event loop, and one connection shared across asyncio.to_thread workers is unsafe under concurrent writes whatever check_same_thread is set to, so each worker opens and closes its own", Q12 = "a manifest ETag IS its Docker-Content-Digest and the registry honors If-None-Match with a 304 and a zero-byte body, which buys time on the sweep and not a single request, while GET /v2/_catalog carries no ETag, Last-Modified or Link so the catalog must be walked every sweep", Q13 = "oauth2-proxy guards every upstream by default and this repo's jobspec sets no skip-auth key of any kind, so the registry view and its route inherit the homepage's session gate as long as no exemption is introduced", Q14 = "rendering one live-sized README with markdown-it-py costs about 4 ms of event-loop time, which is affordable only because a digest is rendered once ever and then persisted" }
measured_against = { Q1 = { kind = "probe", version = "3 runs against registry.lab.orangecluster.nl, catalog of 2026-09-05T06:35Z", ref = "sweep 13 requests, 0.81 s at eight-way concurrency", note = "HEAD /v2/<repo>/manifests/<tag> returns 200, Docker-Content-Digest, 0 body bytes" }, Q2 = { kind = "probe", version = "catalog of 2026-09-05T06:35Z; Docker Hub image config blob re-probed 2026-09-05", ref = "zero image repos; all four manifests carry the ModelKit artifactType; the arm64 child of docker.io/library/registry:3.1.1 has a 3611-byte config blob carrying architecture=arm64, os=linux and created=2026-06-22T19:54:07Z" }, Q4 = { kind = "repo-scan", version = "working tree at plan time", ref = "no package.json, no browser harness, dash frontend has zero tests" }, Q5 = { kind = "probe", version = "distribution 3.1.1", ref = "307 then 200, 2033 bytes, history [307]" }, Q6 = { kind = "probe", version = "markdown-it-py 4.2.0", ref = "opts.html False, table True, escaped True, py.typed present True" }, Q7 = { kind = "probe", version = "Docker-Content-Digest on both tags of each repo", ref = "0.1.0 and latest resolve to one digest for all four repos" }, Q8 = { kind = "probe", version = "oauth2-proxy v7.13.0 container, three upstreams", ref = "/api/registry to REGISTRY, /api/registry/nested and /api/registry/ to FRONTEND, /api/registry?tab=models to REGISTRY" }, Q9 = { kind = "repo-scan", version = "assets/registry-mockup.html, 974 lines, every anchor re-resolved 2026-09-05", ref = "layers table at :889-917; .layers CSS at :312-324 selects again; openCard :867-934; card.innerHTML :882; close handlers :936-937; tab handlers :939-956; theme toggle :958-968" }, Q10 = { kind = "probe", version = "concurrency sweep, best of two runs each", ref = "1-way 2.44 s / 188 ms per request, 4-way 0.86 s, 8-way 0.81 s / 62 ms, 16-way 0.77 s" }, Q11 = { kind = "probe", version = "python:3.12-slim, sqlite lib 3.46.1, threadsafety 3, one subprocess and a fresh database per trial", ref = "8 concurrent WRITES on one shared connection: 6 of 20 clean with 12 SIGSEGV in the operator's run and 0 of 60 clean here, three of those losing rows silently; connection-per-call clean in every trial of both runs; 8 concurrent READS on a shared connection clean; 26.2 us per call through to_thread against 2.6 us inline" }, Q12 = { kind = "probe", version = "distribution 3.1.1, six runs each, operator-run against the live registry", ref = "ETag equals Docker-Content-Digest; conditional HEAD and conditional GET both 304 with a zero-byte body; median 147 ms conditional against 181 ms unconditional; no ETag, Last-Modified or Link on GET /v2/_catalog" }, Q13 = { kind = "repo-scan", version = "deployments/infrastructure/services/oauth2-proxy.hcl at plan time", ref = "no OAUTH2_PROXY_SKIP_AUTH_ROUTES, SKIP_AUTH_REGEX or any skip-auth key in the env heredoc at :59-73; repo-wide grep for skip-auth returns nothing" }, Q14 = { kind = "probe", version = "markdown-it-py 4.2.0, js-default, 4914-byte README, 200 iterations", ref = "4.12 ms per render, 16.5 ms for today's four kits" } }
---

# Ticket: L5-landing-registry-tab

## 1. Title

Give `dash` a registry view: a `/api/registry` route that walks the
cluster OCI registry concurrently, persists a digest-keyed card store in
SQLite on a new host volume, re-sweeps for pushes with conditional
`If-None-Match` manifest `HEAD`s, renders each kit's `README.md` to HTML
server-side, and a models/images tab strip in the frontend ported from
the approved mockup. Async end to end: the walk, the route and every
database call, each offloaded to a thread that opens its own SQLite
connection, so `sqlite3` neither blocks the event loop nor corrupts
under the walk's concurrent writes. The view stays behind
oauth2-proxy's existing session gate.

## 2. Size / Effort

**L (large).** Drivers:

- **Two Terraform roots, not one.** The Vault KV copy and the jobspec
  wiring land in `deployments/applications`
  (`secrets.tf`, `services.tf`, `services/dash.hcl`); the oauth2-proxy
  upstream lands in `deployments/infrastructure`
  (`services/oauth2-proxy.hcl`, `services.tf`). Both roots need `plan`
  run and read (§8).
- **A new async, bounded-concurrency I/O surface.** Two new modules
  built on an `httpx.AsyncClient` with an eight-way ceiling, which is
  a 3x win over serial and the difference between a poll that fits its
  interval and one that does not (§4 **P31**). The backend is already
  async (`main.py:56`), so this is not a new execution model, but it is
  a new client.
- **A durable store, which this backend has never had.** Keyed by
  manifest digest, refreshed by a `HEAD` sweep, with eviction and a
  sweep floor (Requirement 9), and persisted in SQLite across restarts
  (Requirement 23). This is the largest single piece of new logic in
  the ticket and it carries thirteen test cases of its own.
- **Persistence reaches a third Terraform place and the jobspec.** The
  `dash_data` host volume lands in `deployments/infrastructure/services.tf`
  beside the other ten `nomad_dynamic_host_volume` resources (`:2`,
  `:22`, `:42`, `:173`, `:193`), while the `volume` and `volume_mount`
  stanzas that consume it land in
  `deployments/applications/services/dash.hcl`. dash has no host volume
  today, so both halves are new (§4 **P34**).
- **Async that goes all the way down, including the database.**
  `sqlite3` is a blocking C library with no async API (§4 **P36**), so
  every query is wrapped in `asyncio.to_thread` and every one of those
  workers opens its own connection. Two failure modes, not one: a call
  left on the loop serializes the 8-way concurrency this ticket just
  bought and stalls `/api/status` with it, and one connection shared
  across those workers breaks under the walk's concurrent writes —
  measured, and not always as an exception (Requirement 25, §4 **P36**,
  §9).
- **A new runtime dependency and a markdown render step.**
  `markdown-it-py` is the first dependency this backend has added since
  L4, it must reach `uv.lock` because the Dockerfile builds with
  `uv sync --frozen` (§4 **P26**), and the render path needs its own
  tests including the raw-HTML escape case.
- **The frontend port is normative, not approximate.** The operator
  requires the shipped UI to look and act exactly as the mockup
  (§3), so the tab strip, panels, kit grid, `.md` card pane, modal
  builder and every interaction handler
  (`assets/registry-mockup.html:436-509`,
  `:513-524`, `:329-371`, `:748-968`) are ported rather than
  reinterpreted, minus the page-level chrome (Requirement 14).
- **The images path ships tested against fixtures alone, and it grew
  by one fetch.** The registry holds no image today (§4 **P1**), and the
  operator requires a pushed image to render (Requirement 10), so five
  `respx`-fixture tests carry a path production cannot verify. §11 Q2's
  amendment widens the surface rather than dropping two columns: a
  plain image manifest costs one config blob, which is what produces
  the mockup's `arch` and `pushed` (§4 **P41**). Index resolution stays
  out (§5).
- **Four new test files' worth of coverage** across a `respx`-mocked
  fetch layer, a pure assembly-and-render layer, the cache, and the
  route itself, plus a `cluster`-marked live check.
- **One small repo-level gate, outside the backend tree.** The
  no-skip-auth assertion (Requirement 27) needs a hook that fires when
  `oauth2-proxy.hcl` changes, and the `dash-backend-pytest` hook is
  scoped to the backend directory (`.pre-commit-config.yaml:107-112`),
  so it would not. One script under `scripts/` plus one hook entry,
  following `tf-block-diff-self-test`'s shape (`:66-74`). §11 Q11
  records the cheaper alternative.
- Two image tags rebuild and bump (frontend and backend both change).

**What the ticket does *not* cost, and did in earlier revisions:**
dropping `embark.json` (§3) removes a blob fetch per digest, the
serving-spec panel, the prefixes block and the kind pill, and the
concurrency decision leaves `_http.py` untouched (§11 Q10). Both are
subtractions. Two more: `If-None-Match` (Requirement 24) is one request
header and no new code path, and the oauth2-proxy guard (Requirement
27) is a prohibition on a setting that does not exist rather than a
mechanism to build (§4 **P38**).

## 3. Triggered by

Operator request, this session: add a registry view to `dash` with two
tabs, models and images. Five named parts:

1. `/api/registry` on dash's backend. Lists the registry's repositories
   and tags, and splits ModelKits from container images on the
   manifest's `artifactType`.
2. **The card itself.** Verbatim: "For each model, ideally it would
   also show some sort of card (i.e. what is in it)... can you just do
   a pull `<CARD>.md` and read only that artifact." This is the part
   the earlier revision of this ticket could not honor, because at
   probe time no kit carried a docs layer. That has changed (§4
   **P16**), so the ask is now satisfiable exactly as stated.
3. A models/images tab strip in
   `deployments/applications/services/dash/frontend/index.html`, with
   per-kit cards and a detail modal.
4. A Vault credential so the backend can authenticate to the registry.
5. Terraform wiring for that credential, and an oauth2-proxy upstream so
   the browser can reach the new route.

Six further constraints the operator added mid-plan, each verbatim
and each hard:

- **"I expect it to look and act exactly as in your mockup."** The
  mockup is normative for the shipped UI, both its appearance and its
  interactions. Requirements 14 and 15 encode it; §11 Q3's resolution
  bounds it, since the mockup is a standalone page and the view ships
  as a section on an existing one.
- **"Also: it must update when new models or images are pushed."** A
  push must reach the page without a redeploy and without a reload.
  Requirement 9 encodes the backend half, Requirement 16 the frontend
  half, and both supersede earlier resolutions of §11 Q1 and Q3.
- **"Images must render if they are pushed."** Said twice, so treated
  as load-bearing rather than as a passing remark. Requirement 10
  encodes it, and it takes the images tab past the empty-state-only
  scope §11 Q2 originally settled on.
- **"Embark.json is application-specific and should not be included in
  the design."** `embark.json` is embark's own serving config, a
  private schema belonging to one consumer of this registry. A registry
  browser that parses it is coupled to that application and silently
  wrong for any kit not built for embark. Nothing is lost: the
  `README.md` already carries the same facts in human form, in the
  cards' own tables. Requirement 4 encodes the result — the card panel
  sources from the Kitfile and the rendered README and from nothing
  else — and §5 records what was cut.

- **"And async calls everywhere of course."** The `httpx.AsyncClient`
  half was already in scope (Requirement 8). The half this constraint
  adds is the database: `sqlite3` is synchronous, so a query issued
  straight from the Starlette handler blocks the event loop for its
  whole duration and serializes the concurrency the walk just bought.
  Requirement 25 encodes the offload, Requirement 26 the end-to-end
  claim, and §11 Decision 8 records why `aiosqlite` is not the answer.
- **"The registry page must be guarded by oauth proxy like the homepage
  is."** The guarantee already holds by construction and the work is to
  keep it: the view is a section of `index.html`, served by the
  frontend upstream, and `/api/registry` is a third upstream on a proxy
  that carries no skip-auth exemption of any kind (§4 **P38**).
  Requirement 27 makes that a prohibition rather than an assumption,
  and §5 records the exemption as a non-goal.

Conditional, and answered by §11 Decision 5: **"If you need an external
cache, use redis."** The condition does not hold, the option is costed
rather than skipped, and an escalation trigger is recorded.

**Superseded:** the in-process dict. An earlier revision held the
digest store in memory and accepted one cold walk per restart. The walk
was then measured: 21 registry-side requests — 29 client round trips,
because every blob answers `307` and the client must follow it — and
1.20 s at eight-way concurrency cold, against 13 requests and 0.81 s
for the change-detection sweep (§4 **P7**, **P27**, **P31**). Cold
start is the harsher bound of the two and it is the one that scales
worst (§9's table: about 80 s for a
first load at fifty repos), so it is the one worth removing. Persisting
the store on a host volume removes it permanently, because a `cards`
row is keyed by a content digest and can never be invalidated
(Requirement 23). §11 Decision 5 keeps Redis declined and records that
its reason changed with this.

**Superseded:** an earlier operator statement accepted a docs-layer gap
("I know about the docs gap, for now that's fine"). The gap closed when
all four kits were repacked at `2026-09-05T06:35Z` with a `docs.v1.tar`
layer each (§4 **P16**). The acceptance described a state that no longer
exists, so it is void rather than carried, and the original ask in item
2 above governs instead.

## 4. Context

- **The registry holds four repositories, all ModelKits, and every one
  carries a `docs` layer.** `GET /v2/_catalog?n=200` returns
  `{"repositories":["embeddinggemma-q8","embeddinggemma-qat","mxbai-rerank-qat","mxbai-rerank-xsmall-v1-q8"]}`.
  All four were repacked at `2026-09-05T06:35Z` with kitops 1.15.0 and
  now carry **six** layers each, the sixth being
  `application/vnd.kitops.modelkit.docs.v1.tar` holding one `README.md`.
  There are zero container image repos: cluster images go to
  `ghcr.io/jasperhg90`
  (`deployments/applications/services.tf:345`, `:389-390`). The images
  tab is empty in production on day one and must stop being empty the
  moment an image lands (Requirement 10). (**P1**, **P16**)
- **Both tags of every repo resolve to one digest.** Each repo carries
  `0.1.0` and `latest`, and `Docker-Content-Digest` is identical across
  the pair for all four. A naive repo-tag walk therefore draws eight
  cards for four kits and pays two extra blob fetches per duplicate.
  Deduplication by digest is a requirement, not an optimization.
  (**P22**)
- **A manifest `HEAD` is the change-detection primitive.**
  `HEAD /v2/embeddinggemma-q8/manifests/latest` answers `200` with
  `Docker-Content-Digest: sha256:a303abc2...` and a **zero-byte body**
  (`Content-Length: 1725` describes the manifest, not the response
  body). A full change-detection sweep is therefore catalog plus one
  tag list per repo plus one `HEAD` per tag, `1 + R + T` = 13 requests,
  measured 0.81 s at eight-way concurrency. Its cost does not scale
  with blob sizes, which is what makes polling affordable. (**P27**)
- **Serial is the wrong shape: the cost is round-trip, not registry
  work.** The same 13-request sweep measured 2.44 s serially (188 ms
  per request), 0.86 s at four-way, 0.81 s at eight-way (62 ms per
  request) and 0.77 s at sixteen-way. Four-way is a 2.8x win and it
  plateaus by eight, so something upstream — HAProxy, or the registry
  itself — serializes past that. Eight is the specified bound:
  past it there is nothing to gain, and the registry is a shared
  service on `ubuntu` whose own jobspec calls its reservation
  deliberately small
  (`deployments/applications/services/registry.hcl:195-204`).
  (**P31**)
- **A manifest digest is content-addressed, so a rendered card never
  goes stale.** The bytes behind `sha256:a303abc2...` cannot change,
  which means a cache keyed on digest is correct with no expiry: the
  only thing that changes is which digests exist. That is exactly what
  the sweep measures, and it is why §11 Q1's resolution moved from a
  time-based TTL to a digest-keyed store. (**P22**, **P27**)
- **`artifactType` is the tab split, and it is present on a ModelKit
  and absent on a container image.** A kit's manifest carries
  `artifactType: application/vnd.kitops.modelkit.manifest.v1+json`; a
  real container image tag (`docker.io/library/registry:3.1.1`)
  resolves to an OCI **index** with keys `manifests`/`mediaType`/
  `schemaVersion`, no `artifactType`, no `config` and **no `layers`**.
  A single-architecture image tag resolves to an image manifest, which
  does carry `config` and `layers`, and its config blob is ~3.6 KB of
  raw JSON carrying `architecture`, `os` and `created` — the three
  fields the mockup's images table needs for `arch` and `pushed`
  (§11 Q2's amendment, **P41**). Both shapes must produce a row rather
  than an exception (Requirement 10). (**P2**, **P30**, **P41**)
- **The card's data comes from two small blobs, not three, and not the
  weights.** The Kitfile config blob is ~2033 bytes of JSON (1976-2098
  across the four) carrying `manifestVersion` and `package`
  (`name`, `version`, `description`, `license`, `authors`), plus
  `model`/`code`/`docs` sections listing every layer's path and digest.
  `README.md` is a 6144-7680 byte `docs` layer whose single member is
  4448-5645 bytes of markdown. Together that is under 10 KB per digest
  against a 95.8 MB-978.0 MB artifact. **`embark.json` is not read.**
  It stays visible in the layer table, because the manifest lists it
  and the layer table is generic, but nothing parses it (§3, §5).
  (**P3**, **P16**)
- **Layer blobs are TAR archives; only the OCI config blob is raw
  JSON.** This is the trap that broke the first probe of this ticket: a
  `json.loads` on a fetched layer blob raises `JSONDecodeError`,
  because the bytes are a tar holding one member. It applies to the
  `README.md` docs layer, which is the one layer this ticket reads.
  Python's stdlib `tarfile` reads it with
  `tarfile.open(fileobj=..., mode="r")` (plain tar, not gzip), so the
  backend needs no `kit` binary. That is what keeps the
  no-`cli`-dependency rule (L4 Decision 2) cheap to hold here.
  (**P4**, **P19**)
- **Blob GETs answer `307`, redirecting to MinIO, and a client that
  does not follow it fails misleadingly.** The registry's S3 storage
  driver hands back a presigned MinIO URL
  (`http://192.168.2.29:9000/registry/...?X-Amz-...`). httpx defaults
  `follow_redirects` to `False` on both its sync and async clients, and
  because `307 < 400` a status guard of the shape
  `_http.py:47-48` uses does not fire: the empty body reaches
  `response.json()` and raises `ValueError`, surfacing as a JSON error
  rather than as anything naming a redirect. The registry client must
  set `follow_redirects=True` explicitly, and its header block must
  record the symptom, because the symptom points at parsing.
  (**P5**, **P8**)
- **The network path works without a firewall change, but only through
  the edge.** The registry's own port is admitted from HAProxy alone
  (`deployments/applications/services.tf:121-125`, `allow from
  192.168.2.30 to any port 5000`), so dash on `192.168.2.50` cannot dial
  `192.168.2.47:5000`. It can reach HAProxy's 443
  (`deployments/infrastructure/services.tf:261-271`, `allow from
  192.168.0.0/16`) and MinIO's 9000 (`:252-259`, same `/16`), which is
  exactly the pair a redirect-following blob fetch needs.
  `registry.lab.orangecluster.nl` resolves from public DNS to
  `192.168.2.30` (`docs/dns.md:3`). embark already reaches the same
  registry the same way (`deployments/applications/services.tf:312`,
  `:347`). (**P6**, **P20**)
- **A cold full walk costs 21 requests at the registry and 29 round
  trips at the client; the steady state costs 13 of each.** The cold
  shape is `1 + R + T + B`: one catalog read, one tag list per repo
  (`R = 4`), one manifest per tag (`T = 8`, which is where two tags
  collapse onto one digest), then the blobs per distinct digest, whose
  count depends on the kind: **a ModelKit digest costs 2** (Kitfile
  config plus the docs layer), **a plain image digest costs 1** (its
  config blob, §11 Q2's amendment), **a manifest index costs 0**.
  Today's catalog is four ModelKit digests, so `B = 8` and
  `1 + 4 + 8 + 8 = 21`. **The 21 counts requests that reach the
  registry. The client issues 29**, because each of the eight blob
  GETs answers `307` to MinIO and Requirement 8 makes
  `follow_redirects=True` mandatory, so every blob is two round trips
  (§4's redirect bullet, **P7**). Both numbers are real and they count
  different things; §8 says which one each test asserts. With every
  digest already cached, the same round is the sweep alone:
  `1 + R + T` = 13 requests and 13 round trips, 0.81 s at eight-way,
  zero blob fetches and zero markdown renders — the sweep touches no
  blob, so nothing redirects. Measured: the cold walk is 1.20 s at
  eight-way and 4.49 s serial. **Cold start is the harsher of the two
  bounds** — it carries the extra blob fetches at two round trips each
  and the markdown renders, and it is the term that grows worst as the
  catalog does (§9). That is what Requirement 23 removes, by persisting
  the store rather than by making the walk faster.
  (**P7**, **P27**, **P21**)
- **Persisting the store turns cold start from a per-restart cost into
  a once-ever one, and the invariant that makes it safe is
  content-addressing.** The schema is three tables: `repos(name PK,
  first_seen, last_seen, last_changed)`, `tags(repo, tag, digest,
  checked_at, PRIMARY KEY (repo, tag))` where `digest` doubles as the
  stored ETag, and `cards(digest PK, kitfile_json, card_html,
  fetched_at)`. **A `cards` row is never invalidated.** A digest names
  its own bytes, so the card rendered from it cannot go stale; the row
  is only ever *evicted*, when no `tags` row references it any more.
  Nothing in the design expires a card on age, and nothing needs to.
  (**P22**, **P35**)
- **dash has no host volume today, and there are ten precedents for
  adding one.** Every `nomad_dynamic_host_volume` in this repo lives in
  `deployments/infrastructure/services.tf` — `postgres` at `:2`,
  `minio_data` at `:22`, `memex_data` at `:42`, `embark_data` at
  `:173`, `nats_data` at `:193` and five more — and they are all the
  same shape: `plugin_id = "mkdir"`, `node_pool = "default"`, a
  capacity pair, a hostname `constraint` and one
  `single-node-writer`/`file-system` `capability`. `nats_data`
  (`:193-211`) is the closest match, because it is already pinned to
  `radxa-dragon-q6a`, the node dash's group constraint pins to
  (`deployments/applications/services/dash.hcl:6-9`). The consuming
  half is a group-level `volume` stanza plus a task-level
  `volume_mount`, as `tempo.hcl:30-35` and `:101-104` do it; `dash.hcl`
  has neither today. (**P34**)
- **The two Terraform roots hold separate state, so the volume and the
  job cannot be linked by `depends_on`.** `memex`, `hermes`, `loki`,
  `tempo` and `embark` all mount a volume declared in
  `deployments/infrastructure/services.tf` from a job declared in
  `deployments/applications/services.tf`, and not one of them carries a
  cross-root `depends_on` — the roots have no link between them, as
  `deployments/infrastructure/services.tf:501-502` states in its own
  comment. Ordering is by root apply order: infrastructure first, then
  applications. **And no ACL change is needed:** the deployer's Nomad
  policy already grants `host_volume "*"` with `mount-readwrite`
  (`deployments/infrastructure/machine_roles.tf:115-117`), unscoped by
  name on purpose (`:108-114`). (**P34**)
- **`sqlite3` is a blocking C library, it is present in the runtime
  image, and one connection cannot be shared across the walk's
  threads.** `python:3.12-slim` ships it (SQLite 3.46.1,
  `threadsafety` 3) with **no async API at all**, so a query called
  straight from an `async def` handler holds the event loop for its
  whole duration. The fix is `asyncio.to_thread`, and the trap is what
  that exposes. A connection opened with the default
  `check_same_thread=True` and reused from `to_thread` **raises**
  `ProgrammingError: SQLite objects created in a thread can only be
  used in that same thread`, at runtime on the first query.
  **`check_same_thread=False` does not fix that; it only silences the
  thread guard.** Eight concurrent `to_thread` *reads* on one shared
  connection are clean, and eight concurrent *writes* — which is the
  shape Requirement 8's per-digest gather actually has, one `cards`
  row per digest — fail in most trials: `InterfaceError: bad parameter
  or other API misuse`, `cannot start a transaction within a
  transaction`, one run that lost rows without raising at all, and, on
  the operator's hardware, 12 SIGSEGVs in 20 trials. **Opening a fresh
  connection inside each worker and closing it in a `finally` is clean
  in every trial of both runs**, which is why Requirement 25 forbids a
  shared connection rather than preferring against one. The thread hop
  itself is cheap and measured: 26.2 µs per call through `to_thread`
  against 2.6 µs inline, so the hop dominates the query and both are
  microseconds. (**P36**)
- **`/api/status` shares the event loop, which is why blocking is a
  gate and not a style preference.** `main.py:56` is `async def
  status_endpoint` and it runs on the same loop the registry route
  will. Note it already calls `fetch_tile_states` synchronously
  (`main.py:58`, through the sync client at `_http.py:42-43`), so the
  loop is a contended resource before this ticket touches it — which
  argues for not adding a second blocking caller, not for shrugging at
  one. The frontend re-runs `/api/status` every 15 s
  (`index.html:588`). (**P37**)
- **A manifest carries an `ETag`, its value IS the digest, and the
  registry honors `If-None-Match`.** Measured against the live
  registry: `ETag:
  "sha256:a303abc2f44d9e907ed5049c9a001616e2d8e5a7abd8334f2b363326490a6fef"`,
  byte-identical to `Docker-Content-Digest`. A conditional `HEAD` and a
  conditional `GET` both answer **304** with a zero-byte body. Median
  **147 ms** against **181 ms** for an unconditional `HEAD`, six runs
  each. **This saves time, not requests:** the sweep still issues
  `1 + R + T` = 13 requests, because it must ask about every tag to
  learn whether it moved. What changes is what each ask costs. Nobody
  should later read Requirement 24 as a request-count optimization.
  (**P39**)
- **`GET /v2/_catalog` gives no cheap change signal, so the catalog is
  walked every sweep.** It carries no `ETag`, no `Last-Modified` and no
  `Link` header, so there is no conditional form of the one request
  that would tell the sweep whether anything changed at all. The
  catalog read is the `1` in `1 + R + T` and it is unavoidable.
  (**P39**)
- **oauth2-proxy guards every upstream today, because nothing exempts
  anything.** Its env template
  (`deployments/infrastructure/services/oauth2-proxy.hcl:58-76`) sets
  thirteen `OAUTH2_PROXY_*` keys and **none** of them is
  `SKIP_AUTH_ROUTES`, `SKIP_AUTH_REGEX` or `SKIP_AUTH_PREFLIGHT`; a
  repo-wide grep for a skip-auth setting returns nothing. That default
  is the homepage's guard, and it is what the registry view inherits.
  One near-miss to not trip over:
  `OAUTH2_PROXY_SKIP_PROVIDER_BUTTON="false"` at `:71` contains the
  substring `SKIP` and has nothing to do with authorization, so
  Requirement 27's check must name the three `SKIP_AUTH_*` keys rather
  than grep for `SKIP`. (**P38**)
- **Rendering a card costs about 4 ms of event-loop time, which is
  affordable only because it happens once per digest ever.**
  `markdown-it-py` is CPU-bound and runs inside the loop: measured
  4.12 ms for a 4,914-byte README under `js-default`, so today's four
  kits cost 16.5 ms on a cold walk and 0 ms on every sweep after,
  because the rendered HTML is persisted (Requirement 23). §11 Decision
  8 names `asyncio.to_thread` as the escape hatch if a future catalog
  makes that untrue — at 4 ms each, the fifty-repo row in §9's table
  (250 digests) would be about a second of blocked loop. Stated rather
  than left unexamined. (**P40**)
- **The backend's existing HTTP helper is sync, `GET`-only, and
  JSON-only, and this ticket leaves it alone.** `_http.py:17`
  (`TIMEOUT_SECONDS = 2.0`), `:42-43` (a sync `httpx.Client` and
  `client.get`), `:47-48` (the `>= 400` guard), `:51` (parsed JSON
  only). None of that suits a concurrent, redirect-following,
  bytes-and-`HEAD` registry walk, and widening it would touch the one
  module every `/api/status` call already depends on. §11 Q10 resolves
  this: the registry client owns its own `httpx.AsyncClient` and
  imports `FetchError` from `_http.py` so the error taxonomy stays
  single. (**P8**, **P32**)
- **Async route tests need no new dev dependency.**
  `starlette.testclient.TestClient` drives the app's event loop from a
  sync test, which is how `deployments/applications/services/dash/backend/tests/test_main.py:107-109` already exercises
  the `async def status_endpoint` at `main.py:56`. Direct unit tests of
  an async helper use `asyncio.run(...)` inside a sync test function,
  stdlib and no dependency. There is no `pytest-asyncio` or `anyio` in
  the dev group and this ticket adds neither. (**P32**)
- **dash runs exactly one instance, so one SQLite file is the whole
  store and there is exactly one writer.**
  `deployments/applications/services/dash.hcl:5` declares
  `group "dash" {` with no `count`, which Nomad defaults to 1, and the
  group is pinned to one node by the constraint at `:6-9` — the same
  node the `dash_data` volume must be constrained to, since a host
  volume does not follow a job (`deployments/infrastructure/services.tf:170-172`
  says so about `embark_data`). The store is therefore server-side
  state shared by every viewer, with no concurrent-writer question to
  answer. This is the fact §11 Decision 5 turns on. (**P28**, **P34**)
- **Redis exists and has an established opt-in pattern, and taking it
  would cost more than it saves here.** A consumer job joins
  `local.redis_cache_consumers`
  (`deployments/infrastructure/database.tf:98-103`, currently holding
  `embark` alone), which drives a per-consumer database role
  (`:125-135`), a per-consumer policy and a per-consumer JWT role
  (`deployments/infrastructure/machine_roles.tf:322-331`, `:344-348`),
  and the job opts in with `vault { role = "redis-cache-<job>" }` and
  reads `redis/creds/cache-<job>`
  (`deployments/infrastructure/services.tf:521-531`). One detail makes
  it worse than the usual per-job cost for dash specifically: naming a
  dedicated role **replaces** `nomad-workloads` rather than adding to
  it (`machine_roles.tf:340-343`), and a Nomad task carries one `vault`
  stanza, so dash could not simply add a second role beside
  `vault { role = "dash" }` (`dash.hcl:89-91`) — the Redis policy would
  have to be folded into the existing `dash` role's `token_policies`
  (`machine_roles.tf:312`). (**P29**)
- **Rendering the card in Python is verified and needs one dependency.**
  `markdown-it-py` 4.2.0 under preset `js-default` renders GFM tables
  and fenced code as `<pre><code class="language-...">`, renders
  blockquotes, and escapes raw HTML by default (`md.options['html']` is
  `False`, so `<script>x</script>` becomes `&lt;script&gt;x&lt;/script&gt;`).
  It ships `py.typed`, so `mypy --strict`
  (`.pre-commit-config.yaml:101-106`) type-checks against it with no
  stub package. The output shape matches the mockup's `card_html`
  fields byte for byte in structure. (**P23**, **P24**)
- **The mockup's payload is ~31 KB and its card panes are ~26 KB of
  it.** The four `card_html` strings measure 5907, 6895, 7221 and 5665
  bytes, 25,688 in total; a `{"models": [...], "images": []}`
  serialization of the mockup's own `KITS` array is 31,612 bytes. Each
  card carries exactly eight fields — `repo`, `tags`, `digest`,
  `created`, `description`, `authors`, `layers`, `card_html` — and no
  serving spec. (**P25**)
- **The Vault 403 trap applies to dash exactly as it applied to
  embark.** `deployments/applications/secrets.tf:81-100` records it in
  full: the `nomad-workloads` role grants a job read only under
  `secret/data/<namespace>/<job_id>/*`
  (`bootstrap/roles/nomad_server/templates/vault_nomad_workloads.hcl.j2:1`),
  so job `embark` reading `default/registry/auth` gets a 403, and
  `vault_kv_secret_v2.embark_registry_credentials` at
  `default/embark/registry` (`:93-100`) exists for that reason. dash
  needs the same copy under `default/dash/registry`, not a widened
  policy. The value is `{username = "push", password =
  random_password.registry_push.result}`, the same two fields embark
  copies, and never the `htpasswd` hash
  (`secrets.tf:143-151` holds all three). (**P9**)
- **dash's Vault role already carries `nomad-workloads`, so the KV read
  needs no `machine_roles.tf` change.**
  `deployments/infrastructure/machine_roles.tf:312`:
  `token_policies = ["nomad-workloads",
  vault_policy.dash_nomad_creds_read.name]`, and its own comment
  (`:284-290`) says the default grant is kept precisely so the job has
  its own KV prefix available. The Nomad ACL policy
  (`:238-255`, `read-job`/`list-jobs`/`node:read`) is unrelated to a KV
  read and does not change either. (**P10**, **P12**)
- **oauth2-proxy matches an upstream's path exactly, so `/api/registry`
  needs its own entry and must carry no trailing slash.** Recorded in
  the repo already
  (`deployments/infrastructure/services/oauth2-proxy.hcl:46-57`,
  `docs/dash-landing-page.md:75-85`) and re-probed against a real
  v7.13.0 container with three upstreams: `/api/registry` routes to the
  third upstream; `/api/registry/nested` **and** `/api/registry/` both
  fall through to the `/` catch-all; `/api/registry?tab=models` still
  matches. The route is therefore exactly `/api/registry`, the frontend
  fetch must not append a slash, and any sub-resource or flag — the
  manual refresh in Requirement 16 included — has to be a query
  parameter. (**P11**)
- **The backend's module shape is fetcher plus pure logic plus glue.**
  `nomad_client.py`/`consul_client.py` fetch (`consul_client.py:31-62`),
  `status.py` computes, `live.py` glues, `main.py` mounts one route
  (`main.py:77-79`) and swallows every fetch failure into an honest
  payload rather than a 500 (`main.py:56-75`). Each copied module
  carries a provenance comment naming its `cli` source
  (`consul_client.py:1-8`, `nomad_client.py:1-7`); the registry modules
  are new code, not copies, so they carry a purpose-and-traps header
  instead, per `.claude/rules/minimal-comments.md`.
- **`Config` requires every variable it names, and exactly one place
  builds it by hand.** `config.py:32-44` (`from_env`) fails on any
  missing name;
  `deployments/applications/services/dash/backend/tests/test_main.py:62-70`
  is the only direct `Config(...)` construction in the tree. New fields
  therefore mean one test-helper edit, not a sweep.
- **One new Python dependency, and it must reach the lockfile.**
  `pyproject.toml:6-10` already lists `httpx`; `tarfile` and `asyncio`
  are stdlib; `respx` is already a dev dependency
  (`pyproject.toml:22-28`) and already the tested convention for this
  backend's HTTP code
  (`deployments/applications/services/dash/backend/tests/test_http.py:17-78`,
  `deployments/applications/services/dash/backend/tests/test_consul_client.py:24-50`).
  `markdown-it-py` is the exception, and the backend image builds with
  `uv sync --frozen` (`Dockerfile:18`), so an unlocked dependency fails
  the image build rather than the gate. (**P13**, **P19**, **P26**)
- **The frontend has one fetch and no data of its own.**
  `index.html:561` (`fetch('/api/status', { cache: 'no-store' })`),
  re-run every 15 s (`:588`). Its page is two `.section` blocks,
  Dashboards and Backend services (`:413-427`), plus one `<dialog>`
  modal (`:433-454`). It already carries a header with a wordmark and a
  theme toggle (`:383-411`) and its own `:root` token blocks
  (`:9-39` light, `:41-67` dark). There is no registry data source in
  the frontend today. (**P14**)
- **The mockup is the normative UI, and it shares dash's token
  vocabulary.** Its CSS is written against the same custom-property
  names dash already defines (`--panel`, `--border-soft`, `--accent`,
  `--text-faint` and the rest), so the port is mostly additive to
  dash's existing `<style>` block rather than a parallel stylesheet.
  The one genuinely new group is the layer-material tokens
  `--lay-model`/`--lay-part`/`--lay-code`/`--lay-docs`
  (`assets/registry-mockup.html:30-35`, dark values
  at `:61-64` and `:86-89`, consumed by `.seg.*` at `:227-230`), which
  dash has no equivalent of.
  `assets/registry-mockup.html:533-746` is the
  literal `var KITS = [...]` the fetch replaces; `:436-443` the tab
  strip; `:445-509` the two panels; `:748-968` every builder and
  interaction handler; `:867-934` the modal builder. Its page-level
  header (`:407-434`) is a second wordmark, summary strip and theme
  toggle that dash already has equivalents of, and is the one part not
  ported (Requirement 14). Two pieces of its copy are hardcoded and must
  become dynamic, for different reasons: the models tab count at `:438`
  reads `4`, which is **right today and hardcoded**, so it goes stale the
  next time a repo is pushed; the images empty state at `:470` says "The
  catalog holds two repositories" and is **already wrong** against a
  catalog of four. (**P15**)
- **The mockup's modal builds three sections in this order: the
  rendered card, the layers table, then the pull commands.** `openCard`
  (`:867-934`) writes the card pane (`:879-887`, with the docs-less
  fallback at `:884-887`), the layers table (`:889-917`) and the
  command rows (`:919-931`), then calls `modal.showModal()` (`:933`).
  The `.layers`, `.layer-wrap` and `.swatch` CSS at `:312-324` is
  selected again — `.layer-wrap` by `:890`, `.swatch` by `:903` — so
  nothing in the file is orphaned and nothing about the port is
  ambiguous. This order is the operator's stated one and Requirement 14
  is written against it. §11 Q9 records how it got here. (**P33**)
- **`tiles.json` already carries a `registry` backend tile** with
  connect details (protocol, `https://registry.lab.orangecluster.nl`,
  the htpasswd auth note, and a `podman login` example). It answers
  "how do I push and pull"; the new tab answers "what is in it". They do
  not overlap. (**P18**)
- **There is no JS or browser test harness anywhere in this repo.** No
  project `package.json`, no playwright/vitest/jest/puppeteer anywhere
  outside vendored plugin and `.graveyard/` paths, and dash's frontend
  has zero tests. Anything asserted about what the **browser draws** or
  how it **responds to a click** has no automated producer here. The
  HTML string and the JSON payload are a different matter: both are
  produced in Python and are fully assertable. This is what §11 Q4
  turns on, and Requirements 14, 15 and 16 are the reason it now
  carries more weight than it did. (**P17**)

## 5. Non-goals / out of scope

- **Reading, parsing or displaying `embark.json`.** Operator
  instruction (§3): it is embark's private schema and a registry
  browser coupled to it is wrong for any kit not built for embark.
  Concretely cut, and not to be reintroduced under another name: the
  serving-spec panel and every field behind it (`kind`, `output_dim`,
  `max_seq_length`, `normalized`, `pooling`, `output_name`,
  `source_repo`, `source_revision`), the asymmetric query/document
  prefixes block, and the `embedding`/`reranker` kind pill on the kit
  card. **Do not substitute a guess** — deriving a kind from the repo
  name is exactly the coupling this removes, and the Kitfile's
  `package` block carries no kind field to replace it. `embark.json`
  still appears as a row in the layer table, because the manifest lists
  it and that table is generic. The `--lay-*` layer material tokens
  stay: they key off OCI media types, not off embark.
- **Porting the mockup's page-level chrome.** Its `registry_` wordmark,
  summary strip and theme toggle
  (`assets/registry-mockup.html:407-434`) are not
  carried over: dash's header already fills those roles
  (`index.html:383-411`) and a second theme toggle would fight the
  existing one. "Exactly as in the mockup" is scoped from the section
  eyebrow downward (Requirement 14).
- **Index resolution, and per-platform detail for multi-arch image
  tags.** A multi-arch tag's manifest is an OCI index with no `config`
  and no `layers` (§4 P30), so reading a platform's architecture, size
  or build date means resolving that platform's own manifest and then
  its config blob — an extra pair of requests per architecture, on a
  path with no production instance to verify against. Such a row shows
  repository, tag, digest and a `multi-arch` marker, with **no arch, no
  size and no pushed date**; per-platform rows are a follow-up. This is
  the half of §11 Q2's option (b) that stays refused. The other half —
  one config blob for a **plain** image manifest — is now in scope
  (Requirement 10), because it is the same one-blob-per-digest shape
  the ModelKit path already pays and it is what gives the mockup's
  `arch` and `pushed` columns a producer.
- **Unbounded concurrency.** The walk is capped at eight in flight
  (Requirement 8). Past eight there is nothing measurable to gain (§4
  P31) and the registry is a shared job with a deliberately small
  reservation
  (`deployments/applications/services/registry.hcl:195-204`).
- **Push notifications from the registry.** `distribution` 3.1.1
  supports `notifications.endpoints`, which would replace polling with
  an inbound webhook, but it needs a change to
  `deployments/applications/services/registry.hcl` (out of scope, §11
  Q5) and a new inbound route on dash. §9 records it as the documented
  answer past roughly fifty repos, alongside the Redis escalation.
- **An external cache.** No Redis, no memcached, no shared store. §11
  Decision 5 costs the Redis option against this repo's own opt-in
  pattern and declines it, and records the one condition that would
  reverse that.
- **A schema-migration framework, an ORM, or any SQL abstraction.**
  The store is three `CREATE TABLE IF NOT EXISTS` statements and a
  handful of parameterized queries against stdlib `sqlite3`
  (Requirement 23). No alembic, no SQLAlchemy, no migration versioning:
  `CLAUDE.md:22-27` forbids the abstraction and the schema is small
  enough that a future change can drop the file and pay one cold walk.
- **`aiosqlite`, or any async database driver.** `asyncio.to_thread`
  over stdlib `sqlite3` is the whole mechanism (Requirement 25, §11
  Decision 8). A third runtime dependency is not warranted for queries
  this small.
- **Tuning SQLite.** No WAL-mode decision, no `PRAGMA` sweep, no
  connection pool. One writer, one instance, a few dozen rows.
- **Backing up `dash_data`, or restoring it.** The store is derived
  state: losing the file costs one cold walk (21 registry-side
  requests, 29 client round trips, 1.20 s) and nothing else, which is
  why it is not in `backup_minio`'s or
  `backup_postgres`'s company
  (`deployments/infrastructure/services.tf:587`, `:599`).
- **Any auth exemption on oauth2-proxy.** Stated as a prohibition, not
  an omission: this ticket must not add `OAUTH2_PROXY_SKIP_AUTH_ROUTES`,
  `OAUTH2_PROXY_SKIP_AUTH_REGEX`, `OAUTH2_PROXY_SKIP_AUTH_PREFLIGHT` or
  any other setting that lets a request past the session gate
  (Requirement 27). The proxy carries none today (§4 **P38**), and the
  registry view inherits the homepage's guard precisely because of
  that.
- **An inbound webhook route on dash.** The `notifications.endpoints`
  escape hatch (§9, §11 Q5) would need one, and an inbound POST from
  the registry cannot carry a browser session — so it would need the
  exemption the line above forbids. Out of scope here, and §9 records
  what taking it later must respect.
- **Changing `_http.py`.** §11 Q10 gives the registry client its own
  async client and leaves the sync helper every `/api/status` call
  depends on untouched.
- **Rendering markdown in the browser.** No client-side markdown
  library, and no CDN script tag: dash must not depend on an external
  host to draw its own dashboard. The backend ships `card_html` and the
  frontend assigns it (§11 Q6).
- **A syntax highlighter for the card's fenced code.**
  `markdown-it-py` emits `<pre><code class="language-console">` and the
  mockup styles it plainly (`.md pre code`,
  `assets/registry-mockup.html:353`). No Pygments,
  no highlight.js.
- **Sanitizing or rewriting the rendered HTML beyond the renderer's own
  default.** `js-default` escapes raw HTML at parse time (§4 **P23**),
  which is the whole mitigation. No bleach, no allowlist pass.
- Changing how the kits are packed, or what their `README.md` says.
  The backend renders whatever the docs layer holds.
- Changing the registry job itself.
  `deployments/applications/services/registry.hcl` is not in this
  ticket's code surface: not its storage config, not its htpasswd auth,
  not its S3 redirect behavior, not its notification endpoints.
- Widening any Vault policy. dash gets its own KV copy under
  `default/dash/registry`, the same shape embark already has
  (`secrets.tf:93-100`); `machine_roles.tf` is untouched (§4 P10).
- Changing dash's Nomad ACL grant. `nomad_acl_policy.dash_read`'s
  `rules_hcl` (`machine_roles.tf:243-254`) stays byte-identical.
- Changing `/api/status`'s JSON contract, its tests, its 15 s refresh
  loop, or `tiles.json`'s schema or content. The registry poll is a
  separate, slower timer (Requirement 16) and the `registry` tile stays
  exactly as it is (Requirement 19).
- Any firewall rule change. The measured path needs none (§4 P6).
- Deleting, garbage-collecting, or pushing anything to the registry.
  `/api/registry` is read-only and answers `GET` alone.
- **A per-repo route.** `/api/registry/<repo>` is unroutable through
  oauth2-proxy (§4 P11). The `?card=<repo>` query form would route and
  is recorded in §11 Q8 as the escape hatch if the payload grows; this
  ticket ships one payload with cards inline.
- Registry catalog pagination beyond `?n=200`. Four repos today; a
  `Link`-header follow is speculative until the catalog outgrows one
  page.
- Fixing the first-SSO-attempt quirk (`docs/dash-landing-page.md:27-32`).
  Still observed, still not root-caused, still out of scope.
- A browser or JS test harness. §11 Q4's `widen-surface` option names
  it as an option and does not take it.

## 6. Requirements & restrictions

Must achieve:

1. **`GET /api/registry` on the backend, at exactly that path, with no
   trailing slash.** No path parameters, no sub-routes: oauth2-proxy
   matches the upstream path exactly, and both `/api/registry/anything`
   **and** `/api/registry/` fall through to the frontend (§4 P11). The
   Starlette route and the frontend's `fetch(...)` must both use the
   bare `/api/registry`. Any flag, the manual refresh included, is a
   query parameter.
2. **The response splits repos on `artifactType`.** A manifest carrying
   `artifactType ==
   "application/vnd.kitops.modelkit.manifest.v1+json"` is a model;
   anything else is an image (§4 P2). One payload carries both lists,
   since one route serves both tabs (Requirement 1).
3. **One card per distinct manifest digest, listing every tag that
   resolves to it.** Both tags of every repo point at one digest (§4
   P22), so the walk reads a digest per tag and then groups on it
   before fetching any blob. Each card carries `tags` as a list, the
   shape the mockup renders
   (`assets/registry-mockup.html:806`, `:873`).
   Producer:
   `deployments/applications/services/dash/backend/tests/test_registry.py`
   asserts two tags on one digest collapse to a single card carrying
   both tags, and
   `deployments/applications/services/dash/backend/tests/test_registry_client.py`
   asserts the two blob routes are called once per digest, not once
   per tag.
4. **Each model card is assembled from the manifest, the Kitfile config
   blob, and the docs layer's `README.md` — and from nothing else.**
   This is what makes the view registry-generic rather than
   embark-specific (§3, §5). The card carries exactly the fields the
   mockup renders
   (`assets/registry-mockup.html:533-746` is the
   shape; `:794-832` and `:867-934` are what consume it): `repo`,
   `tags`, `digest`, `created`, `description`, `authors`, `layers`
   (each with path, kind, size and digest) and `card_html`. Everything
   textual comes from the Kitfile's `package` block
   (`package.name`, `package.description`, `package.authors`) or from
   the rendered README. **No serving spec, no prefixes block, no kind
   pill** (§5). Layer `kind` derives from the layer `mediaType`
   (`...modelkit.model.v1.tar` to `model`, `...modelpart.v1.tar` to
   `modelpart`, `...code.v1.tar` to `code`, `...docs.v1.tar` to
   `docs`) and is the one place a KitOps-specific vocabulary is read,
   which is safe because it is the manifest's own media type rather
   than a payload schema. **"From nothing else" scopes a model card.**
   An images row is a different object with different sources
   (Requirement 10: the manifest, plus one config blob on a plain
   image), and the per-digest blob cost that follows from both is
   Requirement 7's `1 + R + T + B`.
5. **The model card renders server-side into a `card_html` string.**
   The backend fetches the `docs` layer, untars it, and renders the
   `README.md` with `markdown-it-py` under preset `js-default`. Raw
   HTML in a `README.md` must arrive escaped, not executed: the preset
   sets `html=False` and this ticket must not turn it on. Producer:
   `deployments/applications/services/dash/backend/tests/test_registry.py`
   asserts a GFM table renders to `<table>`, a fenced block renders to
   `<pre><code class="language-...">`, and a `<script>` tag in the
   source arrives as `&lt;script&gt;` in `card_html`.
6. **The docs layer blob is untarred; only a config blob is parsed as
   JSON.** A layer blob is a plain tar archive holding one member, and
   parsing it as JSON raises (§4 P4). Config blobs are the walk's only
   raw-JSON fetches: the Kitfile config on a ModelKit digest, and the
   OCI image config on a plain image digest (Requirement 10). Producer:
   `deployments/applications/services/dash/backend/tests/test_registry_client.py`
   builds a real single-member tar with `tarfile`, serves it through
   `respx`, and asserts the extracted member's bytes; and asserts the
   config blob path parses the body directly, with no tar step.
7. **The backend never fetches a weights layer, and never fetches
   `embark.json`.** Per digest it reads at most two small blobs — on a
   ModelKit, the Kitfile config and the `README.md` docs layer, both
   under 8 KB; on a plain image, its ~3.6 KB config blob; on an index,
   nothing (§4, §11 Q2). Sizes come from the manifest's own `size`
   fields, never from a download. The cold shape is therefore
   `1 + R + T + B`, where `B = 2·(ModelKit digests) + 1·(plain image
   digests)`, which is **21 requests at the registry for today's
   four-ModelKit catalog**. Producer:
   `deployments/applications/services/dash/backend/tests/test_registry_client.py`
   asserts, by `respx` route call count, that a cold assembly issues
   exactly that count, and that **no route matching the `model.onnx`,
   `tokenizer.json` or `embark.json` layer digest is ever called**.
   **Which number the fixture counts, stated so it is not guessed:**
   the fixture models the `307` (§4 P5), so `respx` sees **29** calls
   in total for today's catalog while the **registry-path** routes see
   **21**. The assertion is written on the registry-path routes at
   `21`, with a second assertion that the total is `29` — the pair is
   what proves both the walk's shape and that the redirect is followed
   rather than stubbed away.
8. **The walk is concurrent, bounded at eight in flight.** Serial costs
   188 ms per request and eight-way costs 62 ms; four-way is a 2.8x
   win and it plateaus by eight, so eight is the bound (§4 P31). The
   registry client uses an `httpx.AsyncClient` constructed with
   `follow_redirects=True`, HTTP Basic auth, and
   `limits=httpx.Limits(max_connections=8)`, with an
   `asyncio.Semaphore(8)` gating the gathers: the per-repo tag lists,
   then the per-tag manifest `HEAD`s, then the per-digest blobs (two
   on a ModelKit, one on a plain image, none on an index — Requirement
   7), each member of that last gather also writing a `cards` row,
   which is why Requirement 25 forbids a shared database connection.
   **Bounded, not unbounded** — the registry is a shared service whose
   own jobspec calls its reservation deliberately small
   (`deployments/applications/services/registry.hcl:195-204`).
   `follow_redirects` is not optional: without it a blob GET returns
   `307` and, because `307 < 400`, surfaces as a JSON parse error
   rather than as a status (§4 P5), so the module header must record
   the symptom. Producer:
   `deployments/applications/services/dash/backend/tests/test_registry_client.py`
   asserts the client is constructed with a max-connections limit of
   `8`, so an unbounded rewrite fails the suite rather than silently
   hammering the registry.
9. **The view updates when a model or an image is pushed, without a
   redeploy.** The operator's constraint (§3), and the backend half of
   it. The cache is keyed by **manifest digest, not by time**:
   - The backend holds `digest -> {description, authors, created,
     layers, card_html}` in the `cards` table (Requirement 23). Entries
     never expire on age, because a digest is content-addressed and its
     rendered card is valid forever (§4). They survive a restart, so
     the cold walk is paid once ever rather than once per restart.
   - A **sweep** refreshes the digest *set*: catalog, one tag list per
     repo, one manifest `HEAD` per tag, `1 + R + T` = 13 requests,
     0.81 s at eight-way (§4 P27). Sweeps carry a short floor (~30 s)
     so several open tabs share one sweep instead of each triggering
     its own.
   - A digest present in the sweep and absent from the cache costs its
     blob fetches — two and one render for a ModelKit, one and no
     render for a plain image, none for an index (Requirement 10). A
     digest absent from the sweep is **evicted**.
   - Steady state with nothing pushed: 13 requests per sweep, zero blob
     fetches, zero markdown renders — and after a restart, still zero,
     because the `cards` rows are on disk (Requirement 23).

   Producers, all in
   `deployments/applications/services/dash/backend/tests/test_registry_client.py`
   by `respx` route call count: an unchanged digest set triggers **no**
   blob fetch; a newly appearing ModelKit digest triggers **exactly
   two** blob fetches and a newly appearing plain image digest
   **exactly one**; a digest that vanishes from the sweep is evicted
   from the payload; and a second call inside the sweep floor issues no
   second sweep.
10. **Images render if they are pushed.** The operator said this twice,
    so it is a requirement in its own right rather than a clause of
    Requirement 2. Any repository whose manifest is **not** a KitOps
    ModelKit renders as a row in the images tab, and it appears there
    within one sweep interval of being pushed — the same freshness
    guarantee the models tab gets (Requirement 9). **The row carries
    the mockup's six columns** (`assets/registry-mockup.html:482`:
    repository, tag, digest, arch, size, pushed), which Requirement 14
    makes normative, and they come from two places:
    - repository, tag, digest and total size summed from the
      manifest's own `layers` sizes — all of which the sweep's
      manifest read already yields;
    - `arch` and `pushed` from **one config blob per plain image
      digest**, which carries `architecture`, `os` and `created` (§4
      P41). This is the same one-blob-per-digest shape the ModelKit
      path already pays, and it is **not** the index-resolution hop
      §11 Q2 refused. Q2's resolution is amended to say so.

    A **multi-arch** tag resolves to an OCI index with no `config` and
    no `layers` (§4 P30), so its row shows repository, tag, digest and
    a `multi-arch` marker with **no arch, no size and no pushed date**,
    and must not raise; resolving its platforms stays out of scope
    (§5). The empty state renders only when the sweep finds genuinely
    zero image repos, which is today's state. Producers, all `respx`
    fixtures in
    `deployments/applications/services/dash/backend/tests/test_registry.py`
    and
    `deployments/applications/services/dash/backend/tests/test_registry_client.py`:
    an image manifest (plain OCI image `config` mediaType) yields an
    images row rather than being dropped or routed to models; that row
    carries `arch` and `pushed` read from the config blob, and the
    blob is fetched **once** for that digest; a ModelKit manifest never
    appears in `images`; an index manifest yields a `multi-arch` row
    with those three fields absent rather than raising, and fetches
    **no** blob for it; and a repo appearing for the first time in a
    sweep reaches the payload with no process restart. This path ships
    tested against fixtures and **unverified against production**,
    since the registry holds no image today (§4 P1) — §11 Q4's label
    names that.
11. **Graceful degradation, with no error path, when a kit lacks a
    `docs` layer.** Every kit carries one today (§4 P16), so this is
    the degradation case rather than the main case: a kit packed
    without a docs layer renders the mockup's plain `.card-missing`
    note (`assets/registry-mockup.html:884-887`,
    styles at `:368-371`) instead of a card pane, and the response
    stays `200`. Producer:
    `deployments/applications/services/dash/backend/tests/test_registry.py`
    asserts a card assembles from a manifest with no docs layer without
    raising, and with `card_html` absent or empty rather than the
    string `"None"`.
12. **A registry fetch failure never 500s the route.** Same stance
    `main.py:56-75` already takes for `/api/status`: catch, return an
    honest payload with an `error` string, and let the page say so. A
    failed sweep must leave the last good cache in place rather than
    emptying it. Producer:
    `deployments/applications/services/dash/backend/tests/test_main.py`
    asserts a raising fetch yields `200` plus `error`, and that a
    raising sweep after a good one still returns the cached models.
13. **No credential value ever reaches the response or the frontend.**
    The registry username and password stay server-side. Producer:
    `deployments/applications/services/dash/backend/tests/test_main.py`
    asserts the serialized `/api/registry` body contains neither the
    username nor the password held by the `Config` the test built. That
    file is where the assertion belongs, because it is the only one
    that constructs a `Config` (`:62-70`).
14. **Visual fidelity to the mockup, which is normative.** Operator
    constraint, verbatim: "I expect it to look and act exactly as in
    your mockup."
    `assets/registry-mockup.html` governs the
    shipped appearance and is ported rather than reinterpreted:
    - the tab strip on a baseline rule with the active tab underlined
      in `--accent` (`:436-443`, styles at `:170-188`, the underline
      rule at `:182`);
    - the section eyebrow with its label and hint (`:446-449`, styles
      at `:190-197`);
    - the kit card layout — name plus tag aliases, description, the
      to-scale layer-stack bar and its `weights are N% of it` legend,
      and the footer with pushed-date and "read card" (`:794-832`).
      **No kind pill** (§5);
    - the detail modal's **section order**, which is the operator's
      stated one and which the mockup's builder (`:867-934`) already
      implements: rendered model card (`:879-887`, with the docs-less
      fallback at `:884-887`) → layers table (`:889-917`) → pull
      commands (`:919-931`). §11 Q9 records why the table was missing
      and how it came back; the artifact is now the authority and it
      carries all three;
    - the `.md` styling for the rendered card (`:329-366`) and
      `.card-missing` (`:368-371`);
    - the layer-material tokens (`:30-35`, `:61-64`, `:86-89`) and the
      `.seg.*` rules that consume them (`:227-230`), which dash has no
      equivalent of and must gain;
    - the two panel footnotes (`:452-458` models, `:504-508` images),
      ported as **copy that describes the shipped walk**, not blind.
      The models one states `1 + R + T + 2D` and 21 requests, which is
      right for today's all-ModelKit catalog and is the registry-side
      count (§4). The images one says a multi-arch tag "resolves
      through an index first", which this ticket does **not** do
      (§5, §11 Q2): that clause is corrected to say a plain image costs
      one config blob and a multi-arch tag renders without one.

    **Scope bound, so "exactly as" is not read as shipping a second
    header:** everything from the section eyebrow downward is ported;
    the mockup's page-level chrome (`registry_` wordmark, summary
    strip, theme toggle, `:407-434`) is **not**, because §11 Q3 places
    this view as a third `.section` on dash's existing page and dash's
    header already carries those roles (`index.html:383-411`).
    Producer: the manual browser check in §8. There is no automated
    producer for appearance in this repo (§4 P17) — see §11 Q4's
    label.
15. **Behavioral fidelity to the mockup.** The second half of "look and
    act exactly as". Each interaction the mockup implements ships, and
    none is dropped in the port:
    - tab switching, including the ArrowLeft/ArrowRight keyboard
      handler and the `aria-selected` bookkeeping (`:939-956`);
    - a card click opens the modal (`:830`);
    - the modal closes on the close button **and** on a backdrop click
      (`:936-937`);
    - a copy button on each pull command, with the
      `copy` → `copied` → `copy` label cycle and the
      `navigator.clipboard` → `document.execCommand` fallback, both
      wrapped in `try`/`catch` (`:844-865`);
    - the theme toggle's three-state light/dark/system model,
      persisting to `localStorage` under `ls-theme` inside
      `try`/`catch` (`:958-968`) — **as dash's existing toggle**, not a
      second one (Requirement 14's scope bound). dash already carries
      an equivalent; the port must not duplicate it.

    Producer: the manual browser check in §8. As with Requirement 14,
    this repo has no producer for interaction behavior (§4 P17) — see
    §11 Q4.
16. **The frontend polls while the registry tab is visible, and offers
    a manual refresh.** The frontend half of the operator's freshness
    constraint (§3).
    - Poll `/api/registry` roughly every 60 s **while the registry
      section's tab is visible**, and stop when it is not. A newly
      pushed kit or image therefore appears within about a minute with
      no page reload.
    - This is a **separate, slower timer**. It must not join the 15 s
      `/api/status` health loop (`index.html:588`), which exists for
      live health.
    - **The section shell renders immediately and fills on resolve.**
      The section paints its tab strip and an in-flight placeholder on
      first load and the page never blocks on the fetch.
    - A **manual refresh affordance** in the section eyebrow lets the
      operator force a sweep straight after a push instead of waiting
      out the timer. It calls the same endpoint with a cache-bypass
      query flag (Requirement 1: a query parameter, never a path
      segment). **The flag bypasses the sweep floor only, never the
      digest cache**, because a digest's content cannot change.
    - **The tab counts and the images empty-state copy are computed
      from the payload**, not the mockup's literals. The two are wrong
      in different ways and both must go: `:438` renders `4`, which is
      **correct today** and hardcoded, so it lies the next time a repo
      is pushed — which is exactly what this requirement exists to
      handle; `:470` says "two repositories" and is **already wrong**
      against a catalog of four.

    Backend-side producer:
    `deployments/applications/services/dash/backend/tests/test_main.py`
    asserts the bypass flag forces a sweep inside the floor while
    leaving cached digests unfetched. Frontend-side has no producer
    (§4 P17) — see §11 Q4.
17. **dash reads its own KV copy of the registry credential.** A new
    `vault_kv_secret_v2` at `default/dash/registry` carrying `username`
    and `password` only, never the `htpasswd` hash, rendered into the
    backend task by a `template` stanza. Reading `default/registry/auth`
    directly is a 403 (§4 P9) and is not an option.
18. **`/api/registry` gets its own oauth2-proxy upstream.** A third
    value in `OAUTH2_PROXY_UPSTREAMS`, path-scoped to `/api/registry`
    and pointed at the backend task's loopback port, alongside today's
    two (`oauth2-proxy.hcl:68`). Exact-match, verified (§4 P11).
19. **`tiles.json` is untouched.** The `registry` backend tile keeps
    its connect modal; the tab complements it (§4 P18). Decided here,
    not left open: the tile answers "how do I reach it", the tab
    answers "what is in it", and neither is the other's substitute.
    Producer: the adversarial hand-off in §8 carries `git diff --stat`
    on `deployments/applications/services/dash/tiles.json` returning
    empty.
20. **Both image tags bump and both images rebuild.**
    `dash_frontend_version` and `dash_backend_version`
    (`deployments/applications/services.tf:389-390`, both `"0.2.0"`)
    each move, since both trees change. Producer: the adversarial
    hand-off in §8 carries `git diff` on
    `deployments/applications/services.tf:389-390` showing **both**
    values changed — one moved and one left behind is the failure
    mode, and it ships a new frontend against an old backend.
21. **`markdown-it-py` is added with `uv add` and the lockfile is
    committed, and it is the only dependency added.** `uv add
    markdown-it-py` run in
    `deployments/applications/services/dash/backend/`, which writes
    both `pyproject.toml` and `uv.lock`. The Dockerfile builds with
    `uv sync --frozen` (`Dockerfile:18`), so an unlocked dependency
    fails the image build, not the pre-commit gate. No async test
    dependency is added: `TestClient` and `asyncio.run` cover it
    (§4 P32).
22. **`docs/dash-landing-page.md` covers the new route**, its
    credential, the third upstream, the markdown dependency and why the
    render is server-side, the digest-keyed cache and its sweep, the
    eight-way concurrency bound, the scaling ceiling and its two escape
    hatches (`notifications.endpoints` and Redis), the reason
    `embark.json` is deliberately not read, why an image row costs one
    config blob and a multi-arch row costs none, the SQLite store and
    its `dash_data` volume, why a `cards` row is never invalidated, why
    every database call goes through `asyncio.to_thread` **and opens
    its own connection there**, what
    `If-None-Match` does and does not buy, and the rule that no
    skip-auth exemption may be added to oauth2-proxy.
23. **The store is persisted in SQLite on a new `dash_data` host
    volume.** Supersedes the in-process dict (§3). Three tables,
    exactly:
    - `repos(name PK, first_seen, last_seen, last_changed)`
    - `tags(repo, tag, digest, checked_at, PRIMARY KEY (repo, tag))`,
      where `digest` doubles as the stored ETag Requirement 24 sends
    - `cards(digest PK, kitfile_json, card_html, fetched_at)`

    **Invariant, and the reason this is worth the volume: a `cards` row
    is never invalidated.** It is keyed by a manifest digest, a digest
    is content-addressed, so the bytes behind it cannot change. A row
    is only ever *evicted* — when no `tags` row references its digest
    any more. Nothing expires a card on age. That is what turns the
    cold walk — 21 registry-side requests, 29 client round trips,
    1.20 s (§4 P7) — from a per-restart cost into a once-ever one.

    Stdlib `sqlite3` only. **No new dependency beyond
    `markdown-it-py`** (Requirement 21), no ORM, no migration framework
    (§5). The volume is a `nomad_dynamic_host_volume "dash_data"` in
    `deployments/infrastructure/services.tf`, shaped like `nats_data`
    (`:193-211`) and constrained to `radxa-dragon-q6a` to match dash's
    own group constraint (`dash.hcl:6-9`); the consuming half is a
    group `volume` stanza and a backend-task `volume_mount` in
    `dash.hcl`, shaped like `tempo.hcl:30-35` and `:101-104`.
    Producers, in
    `deployments/applications/services/dash/backend/tests/test_registry_store.py`:
    the three tables are created on an empty file and creating them
    twice is a no-op; a `cards` row survives closing and reopening the
    database; a card whose digest no longer appears in `tags` is
    evicted while one that does is kept. And in
    `deployments/applications/services/dash/backend/tests/test_registry_client.py`,
    by `respx` route call count: **a warm database serves the payload
    with zero blob fetches**, and **a fresh client process opened
    against an already-populated database file fetches no blob either**
    — the restart case, which is the whole point of the volume.
24. **The sweep's manifest `HEAD`s are conditional, carrying
    `If-None-Match: <stored digest>`.** A manifest's `ETag` **is** its
    `Docker-Content-Digest`, byte for byte, and the registry honors the
    conditional form: a matching `If-None-Match` answers `304` with a
    zero-byte body (§4 P39). A `304` therefore means "this tag still
    points where the database thinks", which is the sweep's exact
    question asked in one header.

    **This saves TIME, not REQUESTS.** Measured: median **147 ms**
    conditional against **181 ms** unconditional, six runs each. The
    sweep still issues `1 + R + T` = 13 requests, because it must ask
    about every tag to learn whether that tag moved. Anyone reading
    this later as a request-count optimization has misread it. Note
    also that `GET /v2/_catalog` carries no `ETag`, no `Last-Modified`
    and no `Link`, so there is no cheap top-level "did anything change"
    signal and the catalog must be walked every sweep.
    Producer:
    `deployments/applications/services/dash/backend/tests/test_registry_client.py`
    asserts the sweep sends `If-None-Match` with the digest the store
    holds, that a `304` leaves the stored digest and its card untouched
    and triggers no blob fetch, and that a `200` carrying a different
    `Docker-Content-Digest` updates the `tags` row and triggers that
    digest's blob fetches — two for a ModelKit, which is the case the
    test drives.
25. **No database call runs on the event loop, and no connection is
    shared between the threads that run them.** Two rules, because the
    measurement found two failure modes (§4 P36, §11 Q12).

    **Rule one: every database call is wrapped in
    `asyncio.to_thread(...)`.** `sqlite3` is a blocking, synchronous C
    library with no async API. Called straight from an async Starlette
    handler it holds the loop for the duration of every query, which
    serializes exactly the eight-way concurrency Requirement 8 buys and
    stalls every other request the backend serves — `/api/status`
    included, whose 15 s health loop shares the process (§4 P37). The
    hop is cheap: 26 µs against a 2.6 µs query, both microseconds.

    **Rule two: each worker opens its own `sqlite3.connect()` and
    closes it in a `finally`.** **A module-level connection, or any
    connection shared between two `to_thread` workers, is
    FORBIDDEN** — not discouraged. The walk's per-digest gather is
    eight-way and each member writes a `cards` row, so the store's real
    load is eight **concurrent writes**, and on one shared connection
    that fails in most trials and sometimes hard-crashes the
    interpreter (§4 P36). `check_same_thread=False` is **not** the
    lever: it silences Python's thread guard and does nothing about the
    `Connection`'s own transaction state, so it converts a reliable
    `ProgrammingError` into an unreliable `InterfaceError`, a lost row
    or a `SIGSEGV`. Under connection-per-call it is also unnecessary,
    since no connection ever crosses a thread. `isolation_level=None`
    is not the lever either (§4 P36). A connection per call costs one
    `open`/`close` on a local file per query, which this store's few
    dozen rows can afford.

    No new dependency: **`aiosqlite` is rejected** (§11 Decision 8), a
    third runtime dependency on a backend whose design premise is
    minimal dependencies, for queries this small.

    Producers, in
    `deployments/applications/services/dash/backend/tests/test_registry_store.py`:
    - every public store call reaches `sqlite3` through the
      thread-offload helper — spy on the helper, drive the route's
      store calls, and assert no call path touched a cursor without
      going through it;
    - **eight concurrent writes through the real store path all
      land.** Drive eight `asyncio.gather`ed calls to the public
      card-write method against one `tmp_path` database, then assert
      **all eight rows are present and correct**. **A read-only
      concurrency test does NOT satisfy this requirement**, and the
      distinction is written down because a reader will otherwise
      reintroduce one as a simplification: eight concurrent reads on a
      shared connection pass 20 out of 20 (§4 P36), so a read test goes
      green against the exact defect this requirement exists to
      prevent. Asserting "it does not raise" is also not enough on its
      own — three measured runs wrote fewer rows than they were given
      and raised nothing — so the assertion is on the **rows**, counted
      and read back.
26. **The whole path is async, with no sync `httpx.Client` anywhere in
    the new code.** Starlette handler → sweep → `AsyncClient` gather
    bounded at eight → thread-offloaded SQLite → response.
    `_http.py`'s sync client stays where it is, serving `/api/status`
    alone (§11 Q10), and no new module imports it for anything but
    `FetchError`. Producer:
    `deployments/applications/services/dash/backend/tests/test_registry_client.py`
    asserts the client is constructed with
    `httpx.Limits(max_connections=8)`, asserted on the constructed
    client rather than inferred, so an unbounded rewrite fails; and the
    adversarial hand-off in §8 carries a grep for `httpx.Client(` under
    the new modules returning nothing.
27. **The registry view and its route stay behind oauth2-proxy's
    session gate, and this ticket adds no exemption.** Operator
    constraint (§3): "the registry page must be guarded by oauth proxy
    like the homepage is." Two halves, and both already hold by
    construction — the requirement is to keep them deliberately rather
    than to build anything:
    - **The view is guarded because it is part of `index.html`.** §11
      Q3 puts it on dash's existing page as a third `.section`, served
      by the frontend upstream, so it sits behind the same gate as the
      rest of dash (`oauth2-proxy.hcl:1-4`). **Stated so nobody thinks
      it needs its own mechanism** — and so that anyone who later
      revisits Q3 and proposes a separate `registry.html` re-checks
      this. A new static page under the `/` catch-all is still guarded;
      a new *upstream* might not be.
    - **`/api/registry` is guarded because no skip-auth list exists.**
      The third upstream (Requirement 18) inherits the default. This
      ticket **must not** introduce `OAUTH2_PROXY_SKIP_AUTH_ROUTES`,
      `OAUTH2_PROXY_SKIP_AUTH_REGEX`, `OAUTH2_PROXY_SKIP_AUTH_PREFLIGHT`
      or any other auth exemption (§5). Note the check must name those
      keys: `OAUTH2_PROXY_SKIP_PROVIDER_BUTTON` at
      `oauth2-proxy.hcl:71` already contains `SKIP` and is unrelated
      (§4 P38).

    **How this gets loosened later, which is the reason it is written
    down.** The `notifications.endpoints` escape hatch (§9, §11 Q5)
    replaces polling with an inbound POST from the registry, and an
    inbound POST carries no browser session — so taking it would need
    exactly the exemption forbidden above. If it is ever taken, the
    exemption must be scoped to that one webhook path, must carry its
    own shared-secret check, and must never widen to `/api/*` or to the
    registry view.
    Producer: `scripts/check_oauth2_proxy_guard.py`, run by a
    `.pre-commit-config.yaml` hook scoped to `oauth2-proxy.hcl`,
    asserting the env heredoc contains none of the three `SKIP_AUTH_*`
    keys. Templating the jobspec inside a test is not available here —
    the file is consumed by Terraform's `templatefile()` and nothing in
    Python renders it — so the check asserts on the file's text, which
    is the same text `templatefile` reads. The script carries its own
    `--self-test` cases, as `scripts/tf_block_diff.py:199`, `:204`
    already does, since `scripts/` holds no pytest project
    (`.pre-commit-config.yaml:66-74`). §11 Q11 records the cheaper
    alternative and why it is not taken.

28. **The reservations in `dash.hcl` do not move, and the registry
    client caps how many bytes it reads from a blob.** Operator
    constraint, verbatim: "I would like it if we can keep the resource
    consumption of this UI as low as possible, like the dashboard."
    Three parts: a prohibition, the measured facts that already satisfy
    it, and the one gap that does not.

    **The prohibition.** This ticket must not raise either task's
    reservation. The `frontend` task's `resources` block
    (`deployments/applications/services/dash.hcl:40-43`) holds
    `cpu = 50` and `memory = 32`; the `backend` task's (`:132-135`)
    holds `cpu = 200` and `memory = 128`. Both stay at those numbers.
    **If the backend turns out not to fit in 128 MB, that is a blocker
    to raise with the operator** — `loopctl block`, the same route as
    any other fork this ticket does not settle — and not a number to
    bump in passing. A
    raised reservation is the failure this requirement exists to catch,
    which is why it is written as a prohibition rather than as a budget
    to aim at.

    **Why the design already mostly holds it**, stated so the
    prohibition is checkable rather than aspirational. Four measured
    facts, none of them new work:
    - **The store is on disk, not in memory.** The `cards` table lives
      on the `dash_data` volume (Requirement 23), so the ~26 KB of
      rendered card HTML and the ~31 KB payload (§4 P25) are not
      resident between requests. §11 Decision 7 moved persistence out
      of an in-process dict for the cold-start reason; this is its
      second justification, and the dict would have held those bytes
      for the life of the process.
    - **Every blob this design fetches is small.** The Kitfile config
      blob is ~2 KB (§4 P3), a `README.md` docs layer 6144-7680 bytes
      (§4 P16), a plain image's config blob ~3.6 KB (§4 P41). The model
      layers — 309,664,768 bytes for one `model.onnx`, 33,387,008 for
      one `tokenizer.json` (§4 P4) — are never requested
      (Requirement 7).
    - **A card renders once per digest, ever.** 4.12 ms per README,
      16.5 ms for today's four kits, then persisted and never
      re-rendered (§4 P40, §11 Decision 8).
    - **The steady-state sweep reads no blob at all.** 13 requests,
      zero blob fetches, zero renders (§4 P27, Requirement 9).

    **The gap, and the one mechanism this requirement adds.**
    `follow_redirects=True` is mandatory on a blob GET, because a blob
    answers `307` to MinIO (Requirement 8, §4 P5), and nothing else in
    this design bounds how many bytes a blob read may consume. A bug, a
    malformed manifest, or a later edit that fetches a model layer by
    mistake would stream hundreds of megabytes into a task reserving
    128 MB. **The registry client must cap the bytes it reads from any
    single blob response and fail loudly past that cap**, counting as
    it streams rather than buffering a whole body and then measuring
    it. The cap reaches the FINAL, post-`307` body and no further: on a
    redirect httpx calls `response.read()` inside
    `_send_handling_redirects`, so the 3xx response's own body is
    buffered in library code before any client-side counter sees it.
    Measured: a 2,621,440-byte body on the redirect hop was buffered
    whole with the cap never firing. That gap is accepted, not closed —
    closing it would need `follow_redirects=False`, which Requirement 8
    forbids — and it is immaterial here because the live registry's
    `307` carries a zero-byte body (§4 P5) and this requirement's
    threat model is a mistaken model-layer fetch, not a hostile
    registry. Past the cap it raises `FetchError`, the taxonomy the client
    already imports from `_http.py` (§7), which Requirement 12's stance
    turns into an honest `error` payload rather than a 500. A
    `Content-Length` header is not the check: it can be absent, and
    after the redirect it describes whatever MinIO chose to send. The
    count is on bytes actually read.

    **The cap is 1 MiB, 1_048_576 bytes, and the number is argued
    rather than asserted.** It is 136x the largest blob this design
    legitimately reads (the 7680-byte docs layer, §4 P16), so no honest
    fetch comes near it. It is 1/128 of the backend's 128 MB
    reservation, so one oversized read cannot be the thing that
    exhausts the task. And with Requirement 8's eight-way bound the
    worst case is eight concurrent reads at the cap — 8 MiB, about 6%
    of the reservation. Against the failure it guards, it is not close:
    one `model.onnx` layer is 309,664,768 bytes (§4 P4), 295x the cap,
    so a mistaken model-layer fetch trips in its first megabyte instead
    of its last.

    **The eight-way bound is a resource decision too, not only a
    politeness-to-the-registry one.** Requirement 8's
    `httpx.Limits(max_connections=8)` and the matching
    `asyncio.Semaphore(8)` are what keep connection buffers bounded:
    every open connection carries its own read buffer plus whatever of
    its response is in flight, so the count of them is a memory term
    and not merely a courtesy to a shared registry with a small
    reservation. Removing the bound multiplies both terms at once.

    Producers, in
    `deployments/applications/services/dash/backend/tests/test_registry_client.py`:
    a blob response running past the cap raises rather than being
    buffered, and — since the read is streamed — the reader never
    materializes the whole body for it; and the cap constant's value is
    asserted directly, so a silent raise of it fails a gate the way
    Requirement 8's max-connections assertion does. The reservations
    themselves are held by the adversarial hand-off in §8, which
    carries `git diff` on
    `deployments/applications/services/dash.hcl` showing both
    `resources` blocks unchanged.

Restrictions the repo enforces (each cited):

- **Terraform file layout** (`.claude/rules/terraform-file-layout.md`):
  one file per subsystem, never per feature. The Vault KV write goes in
  `deployments/applications/secrets.tf`, the jobspec wiring in
  `deployments/applications/services.tf`, the oauth2-proxy upstream var
  **and the `dash_data` host volume** in
  `deployments/infrastructure/services.tf` — that file already holds
  every `nomad_dynamic_host_volume` in the repo (§4 P34). **There must
  be no `registry_tab.tf` and no `dash_data.tf`.**
- **Do not edit the `nomad_acl_policy.deploy` heredoc**
  (`deployments/infrastructure/machine_roles.tf:95-118`). Its comment
  at `:108-114` lists the jobs that mount a host volume and dash is
  about to become one, but that comment lives **inside** `rules_hcl`,
  so editing it rewrites the ACL policy on the next apply for no
  functional gain — exactly the case
  `.claude/rules/terraform-file-layout.md` covers under "Moving a block
  is free. Editing one is not." The `host_volume "*"` grant at
  `:115-117` already covers `dash_data` by name-agnostic design, which
  the comment itself says is why it is unscoped. Leave the list stale.
- **Stdlib before a dependency.** `sqlite3`, `asyncio` and `tarfile`
  are stdlib and carry the store, the offload and the layer read.
  `markdown-it-py` is the one addition (Requirement 21);
  `aiosqlite` and `redis` are both declined with reasons (§11
  Decisions 5 and 8).
- **No `cli` dependency in the backend** (L4 Decision 2, restated at
  `docs/dash-landing-page.md:11-18`). New registry code lives in the
  backend's own tree, including its async HTTP client. A grep for
  `localstack_cli` under
  `deployments/applications/services/dash/backend/` must stay empty.
- **Simplicity first** (`CLAUDE.md:22-27`, "No abstractions for
  single-use code"). This is the rule §11 Decision 5 applies against
  the Redis option and §11 Decision 8 applies against `aiosqlite`, and
  it applies equally to the store: three tables, a timestamp and an
  eviction pass, not a cache framework.
- **New Python dependencies via `uv add`, never `uv pip`**
  (`.claude/rules/uv-installer.md`). This ticket adds exactly one,
  `markdown-it-py` (Requirement 21).
- **Every change ships a test** (`.claude/rules/python-testing.md`),
  mocking only at true external boundaries. The registry HTTP API is
  one, and this project already standardized on `respx`
  (`pyproject.toml:22-28`,
  `deployments/applications/services/dash/backend/tests/test_http.py:17-78`)
  so no new mocking dependency is warranted. The markdown renderer is
  **not** an external boundary: run it for real. The cache is not one
  either: exercise it through the real route.
- **Cluster-touching tests carry the `cluster` marker** and stay out of
  the default run
  (`deployments/applications/services/dash/backend/pyproject.toml:34-36`
  declares the marker,
  `deployments/applications/services/dash/backend/pyproject.toml:37` is
  `addopts = "-m 'not cluster'"`).
- **Tests stay deterministic** (`.claude/rules/python-testing.md`, "no
  reliance on wall-clock time"). The sweep floor is time-based, so its
  tests must inject or monkeypatch the clock rather than sleeping.
- **Secrets live in Vault KV2, never hardcoded**
  (`deployments/applications/secrets.tf`'s own shape; `README.md`).
- **Comment only what the code cannot say**
  (`.claude/rules/minimal-comments.md`): the new registry modules get
  one short header block each naming purpose and traps (the `307`
  redirect and its misleading symptom is one, the tar-not-JSON layer
  shape is the second, the digest-not-time cache key is the third, and
  the concurrency bound and why it is eight is the fourth), matching
  `consul_client.py:1-8`'s shape without its provenance line, since
  these are not copies.
- **Plain language** in every comment, commit message and doc line
  (`.claude/rules/plain-language.md`).
- **Pre-existing failures get fixed, never skipped**
  (`.claude/rules/pre-existing-issues.md`).
- **Adversarial review before done**
  (`.claude/rules/adversarial-reviews.md`), plus this repo's
  `documentation` pass (`.loop/config.json`).

## 7. Code surface

**Backend** (`deployments/applications/services/dash/backend/`):

- **CREATE** `src/dash_app/registry_client.py` — the async I/O layer,
  shaped like `consul_client.py` but owning its own
  `httpx.AsyncClient` (§11 Q10): `list_repositories`, `list_tags`,
  `head_manifest` (the sweep primitive, returns
  `Docker-Content-Digest` off a zero-byte response, §4 P27),
  `get_manifest` (sends the OCI/Docker `Accept` set and returns the
  body plus its digest), `get_config_json` (the raw-JSON config blob —
  the Kitfile on a ModelKit digest, the OCI image config on a plain
  image digest, Requirement 10),
  `get_layer_file` (blob to `tarfile.open(fileobj=..., mode="r")` to
  one member's bytes, used for the `README.md` docs layer), **the
  capped streaming reader every blob path goes through — module
  constant `MAX_BLOB_BYTES = 1_048_576`, counted chunk by chunk over
  the final post-`307` body, raising `FetchError` past it and never
  materializing an oversized body (Requirement 28)** — the
  eight-way `asyncio.Semaphore` and `httpx.Limits(max_connections=8)`
  (Requirement 8), and the digest-keyed cache with its sweep, floor and
  eviction (Requirement 9). Imports `FetchError` from `_http.py` so the
  error taxonomy stays single. Header block names the traps: blob GETs
  answer `307` to MinIO and fail as a JSON error rather than a status
  code, layer blobs are plain tar rather than JSON or gzip, the cache
  key is a content digest rather than a timestamp so entries are
  evicted by absence and never by age, and the concurrency ceiling is
  eight because the curve plateaus there and the registry is a shared
  job with a small reservation.
- **CREATE** `src/dash_app/registry_store.py` — the SQLite layer
  (Requirement 23). Owns the database **path** rather than a
  connection: every call opens its own `sqlite3.connect()` inside the
  worker thread and closes it in a `finally` (Requirement 25, §4 P36,
  §11 Q12). **No module-level connection and no connection passed
  between threads.** Also owns the three `CREATE TABLE IF NOT EXISTS`
  statements for `repos`, `tags` and `cards`, the parameterized reads
  and writes, the eviction pass that drops a `cards` row once no `tags`
  row references its digest, and the one `asyncio.to_thread` helper
  every public call goes through. Header block names the traps: a
  `cards` row is keyed by a content digest and is therefore never
  invalidated, only evicted; `sqlite3` blocks the event loop, so
  nothing here is called without the thread hop; and one connection
  shared across those threads breaks under concurrent writes —
  measured, sometimes as a raise, sometimes as a lost row, sometimes as
  a `SIGSEGV` — which is why `check_same_thread=False` is absent rather
  than set.
- **CREATE** `src/dash_app/registry.py` — the pure layer, shaped like
  `status.py`: `kit_card(manifest, kitfile, readme) -> dict`,
  `image_row(manifest, config) -> dict`, where `config` is the plain
  image's config blob and is `None` for an index, which is the
  `multi-arch` case (Requirement 10); `layer_kind(media_type) -> str`,
  `render_card(markdown: str) -> str` wrapping
  `MarkdownIt("js-default")`, the digest grouping, and the
  models/images split on `artifactType`. No HTTP here, so its tests
  need no `respx` and no event loop.
- **EDIT** `src/dash_app/config.py` — `Config` (`:25-31`) gains the
  registry address, the path its credential renders to, and the SQLite
  file's path on the mounted volume (Requirement 23); `from_env`
  (`:32-44`) names all three in its `names` tuple; a reader beside
  `read_nomad_token` (`:46-57`) returns the username/password pair or
  `None` on an unrendered template, never raising, for the same reason
  that one does not.
- **EDIT** `src/dash_app/main.py` — a second `Route("/api/registry",
  registry_endpoint)` in `routes` (`:77-79`), an `async def` handler
  that `await`s the registry client (the route is async already, as
  `status_endpoint` at `:56` is) and wraps the fetch in the same broad
  `except Exception` stance `:56-75` already takes (Requirement 12),
  and the cache-bypass query flag (Requirement 16). `_tile_json`
  (`:29-52`) is untouched.
- **EDIT** `pyproject.toml` — `markdown-it-py` joins `dependencies`
  (`:6-10`), written by `uv add`, never by hand (Requirement 21).
- **EDIT** `uv.lock` — regenerated by the same `uv add`. It must be
  committed: `Dockerfile:18` builds with `uv sync --frozen`.
- `src/dash_app/_http.py` — **expected unchanged** (§11 Q10). It stays
  the sync, `GET`-only, JSON-only helper every `/api/status` call
  depends on (`:25-53`); its `FetchError` (`:20-22`) is imported by the
  registry client. Do not widen `TIMEOUT_SECONDS` (`:17`) for the
  registry's sake.
- **CREATE**
  `deployments/applications/services/dash/backend/tests/test_registry_client.py`
  — `respx`-mocked, modeled on
  `deployments/applications/services/dash/backend/tests/test_http.py:17-78`
  and
  `deployments/applications/services/dash/backend/tests/test_consul_client.py:24-50`,
  driving async helpers with `asyncio.run(...)` from sync test
  functions (§4 P32): catalog parse, tags parse, `HEAD` digest read,
  manifest `Accept` header, basic-auth header placement, the
  `307`-to-`200` redirect follow, tar member extraction from a real
  `tarfile`-built fixture (Requirement 6), the max-connections-8
  construction assertion (Requirements 8 and 26), per-digest rather
  than per-tag blob call counts (Requirement 3), the conditional-`HEAD`
  cases from Requirement 24 (`If-None-Match` carries the stored digest;
  a `304` changes nothing and fetches no blob; a `200` with a new
  digest updates `tags` and fetches exactly two), the warm-database and
  restart cases from Requirement 23 (zero blob fetches in both), the
  five cache cases from Requirement 9 with an injected clock, the image
  and multi-arch fixtures from Requirement 10 (one config blob for a
  plain image digest, none for an index), and the request-count and
  no-weights/no-`embark.json` assertions Requirement 7 names — counted
  `21` over the registry-path routes and `29` over all routes, since
  the fixture models the `307`.
- **CREATE**
  `deployments/applications/services/dash/backend/tests/test_registry_store.py`
  — no network, no `respx`: the schema created on a `tmp_path` file and
  created twice as a no-op, a `cards` row surviving a close-and-reopen,
  eviction of a card whose digest no longer appears in `tags` and
  retention of one that does, tag-digest upsert, and the two async
  cases from Requirement 25 driven with `asyncio.run(...)` — every
  public call reaches `sqlite3` through the thread-offload helper (spy
  on the helper), and **eight concurrent writes through the public
  card-write path all land**, asserted on the eight rows read back
  rather than on the absence of an exception. The read-only variant of
  that second test is explicitly not the test (Requirement 25).
- **CREATE**
  `deployments/applications/services/dash/backend/tests/test_registry.py`
  — no network, no event loop: card assembly from captured fixtures,
  `layer_kind` over each of the four media types, the ModelKit/image
  split including "a ModelKit never appears in `images`" (Requirement
  10), `image_row` over a plain image manifest plus its config blob
  (asserting `arch` and `pushed`) and over an index (`multi-arch`, with
  those fields absent), the digest grouping (Requirement 3), the markdown
  render cases including the raw-HTML escape (Requirement 5), and the
  docs-less degradation case from Requirement 11.
- **EDIT**
  `deployments/applications/services/dash/backend/tests/test_main.py` —
  `_config()` (`:62-70`) gains the new `Config` kwargs; new cases for
  `/api/registry` through the existing `TestClient` convention
  (`:107-109`): a happy path, a raising fetch that still returns `200`
  with `error` and a raising sweep that still returns the cached models
  (Requirement 12), the no-credential-in-payload assertion (Requirement
  13), the cache-bypass flag forcing a sweep without refetching cached
  digests (Requirement 16), and an empty `images` list rendering as an
  empty list rather than an error (part of §11 Q4's proxy). The
  `Config` it builds now points its SQLite path at `tmp_path`, so no
  test touches a real database file.
- **EDIT**
  `deployments/applications/services/dash/backend/tests/test_cluster.py`
  — a `cluster`-marked test hitting the deployed `/api/registry` on the
  backend's own port, alongside the existing `/api/status` one
  (`:25-27`, `_dash_addr()`), asserting four models, one card per
  digest, a non-empty `card_html` on each, and that a second call
  inside the sweep floor returns the same payload. Persistence is
  checked by hand rather than here, because restarting the deployed
  alloc is not something a test should do (§8's manual check).

**Frontend** (`deployments/applications/services/dash/frontend/`):

- **EDIT** `index.html` — a third `.section` block after Backend
  services (`:421-427`) holding the mockup's models/images tab strip
  (`assets/registry-mockup.html:436-443`), the
  section eyebrow (`:446-449`) extended with the manual refresh
  affordance (Requirement 16), the kit grid (`:450`), the images table
  and its empty state (`:461-509`); the layer-material CSS variables
  (`assets/registry-mockup.html:30-35`, dark values
  at `:61-64` and `:86-89`) with the `.seg.*` rules that consume them
  (`:227-230`), the tab and eyebrow rules (`:170-197`), the `.md`
  card-pane rules (`:329-366`) and `.card-missing` (`:368-371`), added
  to dash's own `:root` blocks (`index.html:9-39`, `:41-67`) and
  stylesheet — additive, since the mockup's CSS already speaks dash's
  token vocabulary (§4 P15); a second `<dialog>` for the model card
  (`assets/registry-mockup.html:513-524`) beside
  the existing connect modal (`index.html:433-454`); and the mockup's
  builders and interaction handlers
  (`assets/registry-mockup.html:748-968`) with
  `var KITS = [...]` (`:533-746`) replaced by a fetch of
  `/api/registry` with no trailing slash, plus the visibility-scoped
  60 s poll. The mockup's page-level header (`:407-434`) is **not**
  ported (Requirement 14), so its theme-toggle handler (`:958-968`)
  binds dash's existing toggle rather than adding a second.

**Jobspec and Terraform**:

- **EDIT** `deployments/applications/services/dash.hcl` — the `backend`
  task gains a registry address in its `env` block (`:69-75`) and a
  third `template` stanza rendering the registry credential to
  `secrets/`, modeled on
  `deployments/applications/services/embark.hcl:64-72` (which renders
  `.Data.data.username`/`.Data.data.password` from the same KV shape).
  The `backend` task's `env` block also gains the SQLite file's path
  under the mount (Requirement 23). `group "dash"` (`:5`) gains a
  `volume "dash_data"` stanza — `type = "host"`, `source =
  "dash_data"`, `single-node-writer`, `file-system` — shaped like
  `deployments/applications/services/tempo.hcl:30-35`, and the
  `backend` task gains the matching `volume_mount` beside its `config`
  block (`:61-67`), shaped like `tempo.hcl:101-104`. The `frontend`
  task (`:20-44`) gets neither: it serves static files and holds no
  state. The `vault { role = "dash" }` stanza (`:89-91`) is unchanged:
  it already carries the grant (§4 P10). `group "dash"` keeps its
  implicit `count = 1`, which is what makes one SQLite file the whole
  store (§11 Decision 5).
- **EDIT** `deployments/applications/secrets.tf` — a
  `vault_kv_secret_v2 "dash_registry_credentials"` at
  `default/dash/registry` with `username`/`password` only, placed
  beside `embark_registry_credentials` (`:81-100`) and carrying a
  comment that points at the 403 reason rather than repeating it.
  `random_password.registry_push` (`:138-141`) is the source and is
  unchanged.
- **EDIT** `deployments/applications/services.tf` — `nomad_job "dash"`'s
  `templatefile` vars (`:382-400`) gain the registry host and the KV
  path (`vault_kv_secret_v2.dash_registry_credentials.path`), mirroring
  embark's own pair (`:347`, `:351`); `dash_frontend_version` and
  `dash_backend_version` (`:389-390`) both bump.
  `locals.dash_tiles_json` (`:378-380`) is untouched.
- **EDIT** `deployments/infrastructure/services/oauth2-proxy.hcl` —
  `OAUTH2_PROXY_UPSTREAMS` (`:68`) gains a third comma-separated
  value; the comment block above it (`:46-57`) extends to name the
  third upstream and keeps its exact-match finding, adding the
  trailing-slash case.
- **EDIT** `deployments/infrastructure/services.tf` — two unrelated
  additions in one file, which is what the one-file-per-subsystem rule
  asks for:
  1. a `nomad_dynamic_host_volume "dash_data"` beside the other ten
     (`:2`, `:22`, `:42`, `:62`, `:82`, `:102`, `:122`, `:145`, `:173`,
     `:193`, `:220`), copied in shape from `nats_data` (`:193-211`) —
     same `plugin_id = "mkdir"`, same `node_pool`, same capability
     pair, a capacity range sized for a few dozen rows of JSON and
     HTML rather than for weights, and a hostname `constraint` of
     `radxa-dragon-q6a` to match dash's group constraint
     (`dash.hcl:6-9`). It carries a `###` comment saying what the file
     holds and that losing it costs one cold walk and nothing else. No
     `depends_on` links it to `nomad_job.dash`: that job lives in the
     other root and the two roots share no state (§4 P34,
     `:501-502`).
  2. a `dash_registry_upstream` var beside the existing two
     (`:509-510`), `"http://127.0.0.1:8001/api/registry"`, and the
     comment above them (`:498-508`) extended.
- **CREATE** `scripts/check_oauth2_proxy_guard.py` — reads
  `deployments/infrastructure/services/oauth2-proxy.hcl` and fails if
  the env heredoc contains `OAUTH2_PROXY_SKIP_AUTH_ROUTES`,
  `OAUTH2_PROXY_SKIP_AUTH_REGEX` or `OAUTH2_PROXY_SKIP_AUTH_PREFLIGHT`
  (Requirement 27). Names those three keys rather than matching `SKIP`,
  which `OAUTH2_PROXY_SKIP_PROVIDER_BUTTON` (`:71`) would trip. Carries
  its own `--self-test` cases in the file, as
  `scripts/tf_block_diff.py:199`, `:204` does, since `scripts/` holds
  no pytest project (`.pre-commit-config.yaml:66-74`). It is linted by
  the existing `ruff`/`ruff-format` hooks and type-checked by the
  existing `mypy` hook, all three of which already scope to
  `^(cli|scripts)/` (`.pre-commit-config.yaml:37-65`), so it must be
  `mypy --strict` clean with no config change.
- **EDIT** `.pre-commit-config.yaml` — one `local` hook running
  `python3 scripts/check_oauth2_proxy_guard.py`, `pass_filenames:
  false`, scoped by `files:` to
  `^deployments/infrastructure/services/oauth2-proxy\.hcl$` and to the
  script itself, placed beside `tf-block-diff-self-test` (`:66-74`)
  whose shape it copies. This is why the check does not live in the
  backend suite: `dash-backend-pytest` is scoped to
  `^deployments/applications/services/dash/backend/` (`:107-112`), so a
  commit touching only `oauth2-proxy.hcl` would skip it entirely (§11
  Q11).
- **EDIT** `docs/dash-landing-page.md` — the route, the credential, the
  third upstream (extending `:75-85`), the markdown dependency and the
  server-side render, the digest-keyed store with its sweep, the
  `dash_data` volume and why a `cards` row is never invalidated, the
  `asyncio.to_thread` rule, what `If-None-Match` buys and what it does
  not, the concurrency bound, the scaling ceiling and its escape
  hatches, why `embark.json` is not read, and the no-skip-auth rule
  with the webhook caveat (Requirement 27).

**Read-only anchors to consume, not edit:**
`assets/registry-mockup.html` (the normative UI and
the JSON shape, `card_html` included);
`deployments/applications/secrets.tf:81-100` and
`deployments/applications/services/embark.hcl:64-72` (the credential
copy-and-render precedent);
`bootstrap/roles/nomad_server/templates/vault_nomad_workloads.hcl.j2:1`
(the 403's source);
`deployments/infrastructure/machine_roles.tf:284-315` (unchanged, cited
for the "no Terraform change needed here" claim, P10/P12);
`deployments/infrastructure/database.tf:98-103` and `:125-135`,
`deployments/infrastructure/machine_roles.tf:322-331`, `:340-348`, and
`deployments/infrastructure/services.tf:521-531` (the Redis opt-in
pattern §11 Decision 5 costs and declines — **none of these files is
edited by this ticket**);
`deployments/applications/services/registry.hcl:81`
(`docker.io/library/registry:3.1.1`, the version whose
`notifications.endpoints` support §9 names as the scaling escape
hatch), `:143-157` (the S3 config, the reason blob GETs redirect) and
`:195-204` (the deliberately small reservation, the reason the walk is
bounded at eight and the reason §11 Q5 rejects disabling the redirect);
`deployments/applications/services/dash/backend/src/dash_app/consul_client.py:1-62`
(the module shape to match);
`deployments/applications/services/dash/backend/src/dash_app/_http.py:20-22`
(`FetchError`, imported rather than redefined);
`deployments/applications/services/dash/backend/tests/test_main.py:107-109`
(the `TestClient` convention that makes an async route testable with no
new dependency);
`deployments/applications/services/dash/backend/Dockerfile:18`
(`uv sync --frozen`, the reason `uv.lock` must be committed) and
`:23-24` (the runtime stage copies `.venv` and `src` only, so the
database lives on the mounted volume and never in the image);
`deployments/infrastructure/services.tf:193-211` (`nats_data`, the
host-volume shape to copy, already on dash's node) and `:165-172`
(`embark_data`'s comment on why a volume and its job must be pinned
together);
`deployments/applications/services/tempo.hcl:30-35` and `:101-104`
(the group `volume` plus task `volume_mount` pair to copy);
`deployments/infrastructure/machine_roles.tf:95-118` (the deployer's
Nomad policy: `host_volume "*"` at `:115-117` already grants the mount,
and the heredoc must not be edited to say so);
`deployments/infrastructure/services/oauth2-proxy.hcl:1-4` (the guard
model Requirement 27 preserves) and `:58-76` (the env heredoc carrying
no skip-auth key, with the `SKIP_PROVIDER_BUTTON` near-miss at `:71`);
`scripts/tf_block_diff.py:199`, `:204` (the `--self-test` shape a
`scripts/` checker follows);
`CLAUDE.md:22-27` (Simplicity First);
`.pre-commit-config.yaml:83-112` (the four `dash-backend-*` hooks
already match `^deployments/applications/services/dash/backend/`, so new
files under it are gated with no config change).

## 8. Tests & validation gates

- **Repo gate:** `just pre_commit` (`justfile:18-19`, `pre-commit run
  --all-files`, the single gate in `.loop/config.json`). Relevant
  hooks: `nomad-fmt` on `dash.hcl` (`.pre-commit-config.yaml:16-21`);
  `terraform-fmt` and `terraform-validate` via `scripts/tf_validate.sh`
  (`:22-33`), which validates both roots this ticket touches; and the
  four `dash-backend-*` hooks (`:89-112`) running ruff, ruff-format,
  `mypy --strict` and pytest against the backend tree.
  `markdown-it-py` ships `py.typed` (§4 P24), so the mypy hook
  (`:101-106`) needs no stub package and no config change. `sqlite3` is
  stdlib and typed, so it needs none either. **One hook is new:** the
  no-skip-auth check (Requirement 27), scoped to `oauth2-proxy.hcl`,
  beside `tf-block-diff-self-test` (`:66-74`). It is the only gate that
  fires on a commit touching only that file — the four
  `dash-backend-*` hooks are scoped to the backend directory
  (`:89-112`), so none of them would (§11 Q11).
- **Unit tests, default run, no network, no marker:**
  `deployments/applications/services/dash/backend/tests/test_registry_client.py`,
  `deployments/applications/services/dash/backend/tests/test_registry.py`
  and
  `deployments/applications/services/dash/backend/tests/test_registry_store.py`
  as specified in §7, plus the `/api/registry` cases added to
  `deployments/applications/services/dash/backend/tests/test_main.py`.
  Run with
  `uv run --project deployments/applications/services/dash/backend
  pytest deployments/applications/services/dash/backend/tests`.
  Named tests, each homed in a file §7 lists:
  - `test_registry_client.py`, I/O: the `307`-follow, the `HEAD` digest
    read, the tar extraction from a `tarfile`-built fixture, the config
    blob parsed without a tar step, the `1 + R + T + B` cold call count
    (`B` = 2 per ModelKit digest, 1 per plain image digest, 0 per
    index — Requirement 7), **no `model.onnx`, `tokenizer.json` or
    `embark.json` digest requested**, blob routes called once per
    digest rather than per tag. **The fixture models the `307`, so the
    count is asserted twice: `21` over the registry-path routes and
    `29` over all routes for today's four-ModelKit catalog.** A fixture
    that stubs only the MinIO destination would count 21 and pass while
    production fails on the redirect (§9).
  - `test_registry_client.py`, concurrency (Requirement 8): the client
    is constructed with `httpx.Limits(max_connections=8)`, asserted on
    the constructed client rather than inferred, so an unbounded
    rewrite fails.
  - `test_registry_client.py`, cache (Requirement 9), all by `respx`
    route call count with an injected clock: an unchanged digest set
    triggers **zero** blob fetches; a new digest triggers **exactly
    two**; a vanished digest is evicted from the payload; a second call
    inside the sweep floor issues no second sweep; the cache-bypass
    flag forces a sweep but refetches no cached digest.
  - `test_registry_client.py` / `test_registry.py`, images
    (Requirement 10): an image manifest yields an images row; that row
    carries `arch` and `pushed` read from the image's config blob, and
    that blob is fetched exactly once for the digest; a ModelKit
    manifest never appears in `images`; an index manifest yields a
    `multi-arch` row with `arch`, `size` and `pushed` absent rather
    than raising, and fetches no blob; a repo first seen in a sweep
    reaches the payload with no restart.
  - `test_registry_client.py`, conditional requests (Requirement 24):
    the sweep's manifest `HEAD` carries `If-None-Match` set to the
    digest the store holds; a `304` response leaves the `tags` row and
    the `cards` row untouched and fetches no blob; a `200` carrying a
    different `Docker-Content-Digest` updates the `tags` row and
    fetches exactly two blobs. **No test asserts a lower request
    count**, because the conditional form does not lower it (§4 P39) —
    a test that claimed otherwise would be asserting the wrong thing.
  - `test_registry_client.py`, persistence (Requirement 23), by `respx`
    route call count: a warm database serves the whole payload with
    **zero** blob fetches; and a second client built fresh against the
    same already-populated database file — the restart case — fetches
    **zero** blobs too. That second one is the assertion the host
    volume exists for.
  - `test_registry_store.py`, schema and eviction (Requirement 23):
    the three tables are created on an empty `tmp_path` file and
    creating them again is a no-op; a `cards` row survives close and
    reopen; a `cards` row whose digest no longer appears in `tags` is
    evicted and one that still does is kept; a tag repointed to a new
    digest updates in place rather than duplicating.
  - `test_registry_store.py`, the event loop and concurrent writes
    (Requirement 25): every public store call reaches `sqlite3` through
    the thread-offload helper — spy on the helper, drive each public
    call, assert the spy saw them all, so a future direct call fails
    the suite rather than silently blocking the loop; and **eight
    concurrent writes through the public card-write path, gathered at
    the ticket's own bound of eight against one `tmp_path` database,
    all land** — asserted on the eight rows read back, not on the
    absence of an exception, because one measured failure lost rows
    without raising (§4 P36). **A read-only concurrency test does not
    satisfy this**: eight concurrent reads on a shared connection pass
    20 of 20, so that test goes green against the very defect this one
    exists to catch. This is the assertion that fails if anyone
    reintroduces a shared connection.
  - `test_registry_client.py`, the blob byte cap (Requirement 28): a
    `respx` route serves a blob body longer than the cap and the read
    raises instead of buffering it; the same test asserts the streamed
    reader never materialized the whole body for that response; and the
    cap constant is asserted at its value, 1_048_576, so raising it
    silently fails the suite the way an unbounded rewrite fails the
    max-connections assertion above.
  - `test_registry.py`, pure: `layer_kind` over four media types, the
    artifactType split, the digest grouping into one card with two
    tags, the markdown table and fenced-code renders, the `<script>`
    escape, and the docs-less degradation case.
  - `test_main.py`, route: `/api/registry` happy path, raising fetch
    yields `200` with `error`, a raising sweep still returns cached
    models, no credential in the serialized body, the bypass flag's
    behavior, `images: []` serializes as an empty list.
- **`cluster`-marked test:** the `/api/registry` case in
  `deployments/applications/services/dash/backend/tests/test_cluster.py`,
  excluded from the default run by
  `deployments/applications/services/dash/backend/pyproject.toml:37`
  (`addopts = "-m 'not cluster'"`) and run on purpose with `-m cluster`
  against the deployed backend.
- **Image build check:** `docker build` (or the repo's usual build
  path) of the backend image must succeed. `Dockerfile:18` is
  `uv sync --frozen`, so this is the gate that catches an unlocked
  `markdown-it-py` (Requirement 21).
- **`terraform -chdir=deployments/applications plan`** must show the new
  `vault_kv_secret_v2.dash_registry_credentials` created and the `dash`
  job updated, and must destroy nothing. Apply **infrastructure first**:
  the `dash_data` volume lives in the other root and the job will not
  place without it (§4 P34).
- **`terraform -chdir=deployments/infrastructure plan`** must show the
  `oauth2_proxy` job updated in place (new upstream value) and
  `nomad_dynamic_host_volume.dash_data` created; **no diff at all** in
  `machine_roles.tf`'s resources (§5 non-goal, §4 P10, and the
  `rules_hcl` heredoc must not be touched to add `dash` to its comment
  — §6's restriction); and **no diff in `database.tf`** (§11 Decision 5
  declines Redis, so `local.redis_cache_consumers` must not gain
  `dash`). No other volume may appear in the plan.
- **Manual browser check, once deployed.** This is the only producer
  for Requirements 14, 15 and the frontend half of 16 (§11 Q4):
  - Open `https://dash.lab.orangecluster.nl`. The registry section's
    shell paints before the data arrives.
  - **Appearance (Requirement 14):** the tab strip sits on its baseline
    rule with the active tab underlined in `--accent`; the models tab
    lists **four** kits, each with name plus both tag aliases, a
    description, a to-scale six-segment layer bar with its
    `weights are N% of it` legend, and a footer with the pushed date
    and "read card"; **no kind pill anywhere**; the tab count reads `4`
    rather than the mockup's literal. Open one card: the modal shows
    the rendered model card in the `.md` pane with its tables and
    fenced blocks styled, then the layers table, then the pull
    commands — the mockup's own order (§6 Requirement 14) — and **no
    serving-spec grid and no prefixes block**. There is exactly
    **one** header and **one** theme toggle on the page.
  - **Behavior (Requirement 15):** click each tab and confirm the
    switch; press ArrowLeft/ArrowRight on a focused tab and confirm it
    moves; click a card to open the modal; close it with the button and
    again by clicking the backdrop; click a copy button and confirm the
    `copy` → `copied` → `copy` cycle; toggle the theme, reload, and
    confirm it persisted.
  - **Freshness (Requirements 9, 10, 16):** with the tab open, push a
    kit (or retag an existing one) and confirm it appears within about
    a minute with no reload; click the manual refresh and confirm it
    appears sooner. Push a container image to the registry and confirm
    an images row appears rather than the empty state. Then switch away
    from the registry tab and confirm the poll stops.
  - Confirm the images empty state's copy does not claim "two
    repositories". When an image is pushed, confirm its row fills all
    six of the mockup's columns — repository, tag, digest, arch, size,
    pushed — and that a multi-arch tag shows the `multi-arch` marker
    with the last three blank rather than an error (Requirement 10).
  - **Persistence (Requirement 23), the one check nothing automated
    covers on the live cluster.** Load the page once so the store fills,
    then restart the `dash` alloc and load it again. The models tab must
    fill without a cold walk: no blob fetch in the backend's logs, and
    the first paint no slower than a warm one. Then confirm the file is
    on the volume, not in the alloc dir, so the next restart behaves the
    same.
  - **The guard (Requirement 27).** In a private window, with no
    session, request `https://dash.lab.orangecluster.nl/api/registry`
    and confirm oauth2-proxy answers with a login redirect rather than
    the payload. Do the same for the page itself. Neither may return
    registry contents to an unauthenticated caller.
- **Adversarial review** (`.claude/rules/adversarial-reviews.md`, the
  `adversarial` pass in `.loop/config.json`). Hand the reviewer: no diff
  in `machine_roles.tf`, none in `database.tf`, and none in `_http.py`;
  **`git diff --stat` on
  `deployments/applications/services/dash/tiles.json` is empty**
  (Requirement 19); no `registry_tab.tf` or any other new `.tf` file; a
  grep for `localstack_cli` under the backend tree returns nothing;
  **a grep for `embark` under the backend `src/` tree returns nothing**
  outside a comment explaining why `embark.json` is not parsed
  (Requirement 4, §5); no `redis` import or dependency anywhere in the
  backend (§11 Decision 5); `uv.lock` is committed and
  `pyproject.toml` gained exactly one dependency, with no
  `pytest-asyncio` or `anyio` added; the async client is constructed
  with `max_connections=8` and the semaphore bound matches;
  `MarkdownIt` is constructed with `js-default` and `html` is never set
  to `True`; the cache key is a digest and no code path expires an
  entry on age; the bypass flag reaches the sweep floor and not the
  digest cache; no credential value in any `/api/registry` response;
  the route is exactly `/api/registry` with no path parameters and no
  trailing slash, in both the Starlette route and the frontend fetch;
  the frontend has one theme toggle, not two; **no
  `OAUTH2_PROXY_SKIP_AUTH_ROUTES`, `SKIP_AUTH_REGEX` or
  `SKIP_AUTH_PREFLIGHT` anywhere in the diff**
  (Requirement 27) and no new unauthenticated route on dash; **a grep
  for `httpx.Client(` under the backend's new modules returns nothing**
  (Requirement 26) and no `aiosqlite` in `pyproject.toml`; every
  `sqlite3` call site in `registry_store.py` sits behind the
  thread-offload helper and none is awaited directly from
  `main.py`; **no module-level `sqlite3.Connection`, no
  connection passed between threads and no `check_same_thread=False`
  anywhere** — every store call opens its own connection and closes it
  in a `finally` (Requirement 25); **both `dash_frontend_version` and
  `dash_backend_version` moved at
  `deployments/applications/services.tf:389-390`**, not one of them
  (Requirement 20); no code path deletes or rewrites a `cards` row on
  age, only on eviction; exactly one new `.tf` resource block
  (`nomad_dynamic_host_volume.dash_data`) and no new `.tf` file; and
  `machine_roles.tf`'s `rules_hcl` heredoc is byte-identical; **neither
  `cpu` nor `memory` moved in
  `deployments/applications/services/dash.hcl:40-43` or `:132-135`**,
  so both task reservations are byte-identical (Requirement 28); and
  every blob read in the registry client goes through the capped
  reader, with no bare whole-body read on a blob path.
- **Documentation review** (the `documentation` pass in
  `.loop/config.json`) against `docs/dash-landing-page.md`.
- **Eval marker** (`require_eval: true`, `.loop/config.json`): none
  exists yet. Loop pickup stays blocked until
  `.loop/evals/L5-landing-registry-tab.md` exists and `loopctl eval` /
  `loopctl verify-eval-substance` both report `valid`. See the closing
  recommendation.

## 9. Risk assessment

- **Blast radius.** The backend addition is additive: a new route
  beside `/api/status`, whose contract, tests and HTTP helper this
  ticket does not touch (§11 Q10). The two live shared files are
  `deployments/infrastructure/services/oauth2-proxy.hcl:68` and
  `deployments/applications/services/dash.hcl`. A malformed upstream
  value in the former breaks the whole `dash` route, the same failure
  mode L4 already carried on the same line, and still scoped to `dash`
  alone: no other oauth2-proxy'd service reads that variable.
- **Scaling ceiling, and where this design breaks.** At eight-way the
  sweep sustains roughly **16 requests per second** (13 requests in
  0.81 s, §4 P31). Sweep cost is `1 + R + T`:

  | catalog | sweep requests | sweep time |
  |---|---|---|
  | 10 repos, 3 tags each | 41 | ~2.6 s |
  | 25 repos, 4 tags each | 126 | ~8 s |
  | 50 repos, 5 tags each | 301 | ~19 s |
  | 100 repos, 5 tags each | 601 | ~38 s |

  The first row is fine, the second usable but slow, the third
  uncomfortable against a 60 s poll, and the fourth broken: the sweep
  no longer fits its interval. **The dominant growth term is `T`, not
  `R`**, and a model registry accumulates versions rather than
  projects: four repos at twenty tags each is `1 + 4 + 80` = 85 sweep
  requests, worse than twenty repos at two tags (`1 + 20 + 40` = 61).
  Cold start is the harsher bound, because it adds the blob term, and
  **the blob half costs two round trips per blob, not one** (§4 P7):
  fifty repos with five distinct ModelKit digests each is 250 digests,
  so 500 blob GETs at the registry and **1000 client round trips**,
  which is about **62 s**, not the ~31 s an earlier revision of this
  table claimed. On top of the 19 s sweep that is about **80 s for a
  first load** — which the digest cache then makes a one-time cost. **The escape
  hatch, recorded and deliberately not scoped in:** the registry is
  `distribution` 3.1.1
  (`deployments/applications/services/registry.hcl:81`), which supports
  `notifications.endpoints` — it POSTs to a configured URL on every
  push, replacing polling entirely with an inbound webhook. That needs
  a change to `registry.hcl` (out of scope, §5 and §11 Q5) and a new
  inbound route on dash. It is the documented answer past roughly fifty
  repos, sitting alongside the Redis escalation in §11 Decision 5, and
  it is not this ticket's work.
- **The poll multiplies upstream cost by the number of open tabs.**
  Every visible registry tab wants a sweep every 60 s, and a sweep is
  13 requests through HAProxy. Four open tabs would be 52 requests a
  minute without coordination. The sweep floor in Requirement 9 is what
  bounds this: sweeps are shared server-side, so N tabs cost one sweep
  per floor interval rather than N. Getting the floor wrong — or
  bypassing it from the manual refresh in a loop — is the way this
  becomes a self-inflicted load problem.
- **Unbounded concurrency would be a self-inflicted outage.** Removing
  the semaphore turns a cold walk on a large catalog into hundreds of
  simultaneous connections against a job reserving 100 MHz and 256 MB
  (`deployments/applications/services/registry.hcl:195-204`), through
  an HAProxy every other service shares. Requirement 8's
  max-connections assertion exists so this fails a test rather than
  production.
- **The `307`-to-MinIO redirect is the likeliest correctness failure,
  and its symptom lies.** It is invisible in a `curl` that follows
  redirects by default and invisible in any test that mocks the blob
  URL directly. A `respx` test that stubs only the final blob URL
  passes while production returns `307`. Worse, a `>= 400` status guard
  lets `307` through, so the error surfaces as a JSON parse failure and
  points the implementer at parsing rather than at redirects.
  Requirement 8's test must stub the redirect itself, not just the
  destination.
- **The tar-not-JSON layer shape is the second trap, and it has already
  bitten once.** The first probe of this ticket parsed a layer blob as
  JSON and raised `JSONDecodeError`. Requirement 6 exists because a
  comment would not have caught it; a test built on a real `tarfile`
  archive does.
- **A cache keyed on the wrong thing is the third.** Keying on repo and
  tag rather than digest reintroduces staleness that a content-address
  makes impossible, and expiring digest entries on age throws away work
  that can never go stale. Requirement 9's five call-count tests exist
  to pin the behavior rather than the implementation.
- **The images path ships unverified against production.** The registry
  holds no image (§4 P1), so Requirement 10's five tests are fixtures
  written from the OCI spec and from real Docker Hub probes (§4 P2,
  P41). The first real push is the first real test, and the multi-arch
  branch is the likeliest to be wrong. §11 Q2's amendment widens the
  path by one fetch — a config blob per plain image digest — which is
  more fixture-only surface, not less. §11 Q4's label names this
  explicitly.
- **The presigned MinIO URL is cross-origin.** The blob fetch leaves
  `registry.lab.orangecluster.nl` and lands on `192.168.2.29:9000` with
  its own query-string credentials. Measured working end to end, but it
  means the route's health depends on MinIO's reachability from the
  dash node, not only the registry's, and a MinIO outage will surface
  here as a registry error. The digest cache softens it: with every
  digest cached, a sweep touches no blob and no MinIO.
- **Rendered HTML in the payload.** `card_html` is HTML the frontend
  assigns with `innerHTML`
  (`assets/registry-mockup.html:882`), so a
  `README.md` is now an input to the DOM. The mitigation is the
  renderer's own default: `js-default` sets `html=False` and escapes
  raw HTML at parse time (§4 P23). The risk is that someone later
  passes `html=True` for a formatting reason and turns a model card
  into a script vector. Requirement 5's escape test and §8's
  adversarial hand-off both exist to hold that line.
- **Payload growth.** ~31 KB today for four kits (§4 P25), now fetched
  every 60 s per visible tab rather than once per page load. Ten kits
  at the same shape is ~78 KB. §11 Q8 records the `?card=<repo>` split
  as the escape hatch and does not take it.
- **The frontend port is the largest single diff and has no automated
  gate at all** (§4 P17): no lint, no test, no type check touches
  `index.html`. Requirements 14 and 15 make it a fidelity requirement
  as well as a large one, and the only producer for both is the manual
  browser check in §8. A syntax error there ships silently to a `200`
  page with a dead section. Two things reduce the risk rather than
  removing it: the mockup's CSS already uses dash's own token names, so
  the style port is additive rather than a parallel sheet (§4 P15),
  and the only genuinely new tokens are the four `--lay-*` ones.
- **The mockup is complete, and its anchors moved when it was
  completed.** `openCard` (`:867-934`) builds card, layers table and
  commands in that order, and the `.layers`/`.layer-wrap`/`.swatch` CSS
  at `:312-324` selects again (§4 P33, §11 Q9). The residual risk is
  citation drift, not ambiguity: restoring the table pushed every
  handler after it down about thirty lines, so any anchor carried over
  from an older revision of this plan now lands inside the layers
  builder and reads plausibly while pointing at the wrong code. Every
  mockup anchor in this ticket was re-resolved against the 974-line
  file; an implementer who finds one that does not resolve should
  re-resolve rather than trust it.
- **The store assumes one instance, and nothing enforces that.**
  `dash.hcl:5` has no `count`, so Nomad defaults to 1 (§4 P28). If that
  ever changes, the store stops being shared: a host volume is
  `single-node-writer`, so a second instance on another node gets its
  own empty file, sweeps on its own timer, multiplies upstream cost by
  the instance count, and two browser tabs can see different catalogs.
  Two instances *on the same node* would be worse than that — two
  writers against one SQLite file, which is the case nothing here is
  designed for. That is the escalation trigger recorded in §11 Decision
  5, and it is a silent failure, not a loud one.
- **A blocking call reintroduced on the event loop degrades
  `/api/status` too, which is why Requirement 25 is a gate and not a
  style preference.** The two routes share one loop (§4 P37). A
  `sqlite3` call made directly from the registry handler holds it for
  the whole query, so it does not merely serialize the registry sweep's
  eight-way concurrency — it delays the health payload that the page
  polls every 15 s, on a dashboard whose job is to be readable when
  other things are not. The failure is invisible under test unless
  something asserts the call path, which is exactly what
  `test_registry_store.py`'s spy does.
- **A shared SQLite connection under the walk's concurrent writes is
  the one failure this ticket cannot catch and retry.** The per-digest
  gather is eight-way and each member writes a `cards` row. On one
  shared connection that is measured broken (§4 P36, §11 Q12): most
  trials raise `InterfaceError` or a transaction-state error, three
  runs completed and silently wrote fewer rows than they were given,
  and on the operator's hardware 12 trials in 20 ended in
  **`SIGSEGV`**. **A
  segfault is not an exception**: no `try`/`except` sees it, no retry
  wrapper survives it, and it takes the whole uvicorn process with it —
  including `/api/status` (§4 P37), on the one dashboard whose job is
  to be readable when other things are not. This is why Requirement 25
  states connection-per-call as a prohibition rather than a preference,
  and why its producer asserts the write case: the read case passes 20
  of 20 on a shared connection, so a suite built around it goes green
  over the defect.
- **The database file is a new failure surface, and a small one.** It
  can be missing (first boot: create the schema and pay one cold walk),
  unwritable (the `mkdir` plugin creates a host volume `root:root 0700`
  — `deployments/applications/services/embark.hcl:106` records that
  same trap for a non-root task; dash's backend task declares no
  `user`, so it runs as the image's default and this must be confirmed
  on first deploy), locked, or corrupt. **The honest mitigation is that
  the store is derived state**: deleting the file costs one cold walk
  (21 registry-side requests, 29 round trips, 1.20 s) and nothing
  else, so "delete it and restart" is
  a complete recovery procedure. Requirement 12's stance covers the
  read path: a store failure must degrade to a fetch, not to a 500.
  Disk growth is bounded by the catalog — today ~31 KB of cards
  (§4 P25) plus a row per tag.
- **The volume and the job must stay pinned to the same node, and
  nothing checks it.** `dash_data` is constrained to
  `radxa-dragon-q6a` and so is dash's group (`dash.hcl:6-9`). Move one
  without the other and the job stops placing —
  `deployments/infrastructure/services.tf:170-172` records that exact
  failure for `embark_data`, and it is a scheduling failure rather than
  a runtime one, so it shows up as an alloc that never starts.
- **An auth exemption here would publish the cluster's inventory.**
  oauth2-proxy guards the route today only because no skip-auth list
  exists (§4 P38). Adding one would expose repository names, tags,
  digests, sizes and the full model-card prose to anyone who can reach
  the edge. That is not credential material, and it is a complete
  inventory of what the cluster runs and how it was built: the cards
  carry training details, gold-set numbers and licence obligations
  (§4 P25's `card_html`). The likeliest route to it is not
  carelessness but the webhook escape hatch — an inbound POST from the
  registry cannot carry a session, so whoever takes that hatch will
  need an exemption and must scope it to that one path with its own
  shared secret (Requirement 27).
- **An out-of-memory kill in the backend task takes `/api/status` down
  with it, which is why Requirement 28's blob cap is a gate rather than
  a nicety.** The two routes share one process — the same shared-process
  argument the shared-connection bullet above makes about a `SIGSEGV`,
  and with the same consequence: no `try`/`except` sees the end of the
  process, and the dashboard whose job is to be readable when other
  things are not goes dark with it. The route in is narrow and
  specific. A blob GET follows a `307` to MinIO (§4 P5) and an
  unbounded read of a model layer is 309,664,768 bytes (§4 P4) against
  a reservation of 128 MB
  (`deployments/applications/services/dash.hcl:132-135`). The walk
  never asks for such a layer today (Requirement 7); the cap is what
  keeps a bug, a malformed manifest or a later edit from asking. What
  the cap does not remove: it bounds one response, so the real ceiling
  is the cap times the eight-way bound (Requirement 8), 8 MiB, and
  raising either number raises that product.
- **Reversibility: high.** The Vault KV write is additive and
  destroying it affects nothing else. The oauth2-proxy change reverts
  to a two-value string. The frontend and backend revert by tag: both
  previous images stay in `ghcr.io/jasperhg90` and pinning
  `services.tf:389-390` back redeploys them. The new dependency reverts
  with `uv remove`. The store is derived state, so deleting the
  database file costs one cold walk and nothing else. The one addition
  that is not free to revert is the `dash_data` volume: destroying a
  `nomad_dynamic_host_volume` removes the data with it, which is
  acceptable here for exactly the reason above and would not be for a
  volume holding anything original.
- **Node and port collision: none expected.** The route rides the
  backend's existing 8001; no new port is declared anywhere, and the
  new volume is a mount rather than a listener.
- **`If-None-Match` is the lowest-risk item in the ticket and the
  easiest to over-claim.** It is one request header; if the registry
  ever stops honoring it the sweep still works, just 34 ms slower per
  manifest. The real risk is documentary: someone reading Requirement
  24 as a request-count win and then sizing §9's scaling table against
  a saving that does not exist. The requirement says so in bold and no
  test asserts a lower count, which is the whole mitigation.

## 10. Subtickets

Ordered, dependency-aware. **Every fork in §11 is resolved, Q9, Q11
and Q12 included, so no step below waits on a decision.** Historical
note, because earlier revisions of this section said otherwise: Q9
affected step 9 and is settled in the artifact itself (the layers table
is in the mockup at `assets/registry-mockup.html:889-917`); Q11
affects step 15 and resolved to the standalone script; Q12 affects
step 3 and resolved to connection-per-call.

1. **`uv add markdown-it-py`** in the backend directory; confirm
   `pyproject.toml` and `uv.lock` both change, that nothing else was
   added, and that the image still builds under `uv sync --frozen`.
   Depends on: nothing.
2. **`registry.py`** and
   `deployments/applications/services/dash/backend/tests/test_registry.py`:
   card assembly from Kitfile plus README only, `image_row` including
   `multi-arch`, the `layer_kind` mapping, the ModelKit/image split,
   the digest grouping, the markdown render and its escape case, the
   docs-less degradation case. Depends on: 1.
3. **`registry_store.py`** and
   `deployments/applications/services/dash/backend/tests/test_registry_store.py`
   (Requirements 23 and 25): the three tables, the parameterized reads
   and writes, the eviction pass, **a fresh `sqlite3.connect()` opened
   inside each worker and closed in a `finally`** (§11 Q12), and the
   one `asyncio.to_thread` helper every public call goes through — with
   the spy test that keeps it that way and the eight-concurrent-write
   test that proves the store survives the walk's own shape. Depends
   on: nothing.
4. **`registry_client.py`**, I/O half, and the matching half of
   `deployments/applications/services/dash/backend/tests/test_registry_client.py`:
   the async client with `follow_redirects`, basic auth and
   `max_connections=8`, the semaphore, catalog, tags, `HEAD`,
   manifest, the two blob fetches, tar extraction, **the capped
   streaming reader with `MAX_BLOB_BYTES = 1_048_576` and its
   oversized-body, never-materialized and cap-constant tests
   (Requirement 28)**, per-digest call counts, request count, no
   weights and no `embark.json` fetch.
   Depends on: nothing (can run parallel to 1-3).
5. **The digest-keyed sweep on top of the store**: floor, eviction,
   the conditional `If-None-Match` manifest `HEAD`s (Requirement 24),
   the five cache tests with an injected clock (Requirement 9), the
   three conditional-request tests, and the warm-database and restart
   tests (Requirement 23). Depends on: 3, 4.
6. **The images path** (Requirement 10) and its fixture tests,
   including the per-image config blob that produces `arch` and
   `pushed` (§11 Q2's amendment) and the index branch that fetches no
   blob. Depends on: 2, 4.
7. **`config.py`** and the
   `deployments/applications/services/dash/backend/tests/test_main.py:62-70`
   helper edit, including the SQLite path pointed at `tmp_path`.
   Depends on: nothing.
8. **`main.py`**: the `/api/registry` route, the cache-bypass flag, and
   its `test_main.py` cases including the no-credential assertion.
   Depends on: 2, 5, 6, 7.
9. **`index.html`, structure and style**: the third `.section`, the
   tab strip, section eyebrow, kit grid, images table, empty state,
   `.md` pane, `.card-missing`, the `--lay-*` tokens and `.seg.*`
   rules, and the second `<dialog>`, ported per Requirement 14.
   §11 Q9 is settled and the mockup carries the layers table
   (`assets/registry-mockup.html:889-917`), so the modal order to port
   is card → layers → commands. Re-resolve the mockup's line numbers
   before porting: restoring that table moved every handler after it
   (§9). Depends on: 8.
10. **`index.html`, behavior**: the builders, every interaction handler
    from Requirement 15, the non-blocking shell, the visibility-scoped
    60 s poll, the manual refresh, and the dynamic tab counts and
    empty-state copy (Requirement 16). Depends on: 9.
11. **`secrets.tf`**: the `default/dash/registry` KV copy. Depends on:
    nothing.
12. **`deployments/infrastructure/services.tf`**: the
    `nomad_dynamic_host_volume "dash_data"`, shaped from `nats_data`
    (`:193-211`) and constrained to `radxa-dragon-q6a`. Apply this root
    before the applications root, since the job will not place without
    the volume. Depends on: nothing.
13. **`dash.hcl`**: the registry env var, the SQLite path, the
    credential template, the group `volume` stanza and the backend
    task's `volume_mount`; **`applications/services.tf`**: the two new
    templatefile vars and the two version bumps. Depends on: 8, 11, 12.
14. **`oauth2-proxy.hcl` and `infrastructure/services.tf`**: the third
    upstream. Depends on: 13.
15. **`scripts/check_oauth2_proxy_guard.py` and the
    `.pre-commit-config.yaml` hook** (Requirement 27), with its
    `--self-test` cases. §11 Q11 is settled: the standalone script,
    because `dash-backend-pytest` never fires on a commit that touches
    only `oauth2-proxy.hcl`. Depends on: 14.
16. **`deployments/applications/services/dash/backend/tests/test_cluster.py`**:
    the live `/api/registry` check. Depends on: 13, 14.
17. **`docs/dash-landing-page.md`**. Depends on: 1-16.
18. **Rebuild and push both images, apply both roots (infrastructure
    first), run the full manual browser check** (§8), including a real
    push to prove freshness, an alloc restart to prove persistence, and
    an unauthenticated request to prove the guard. Depends on: 1-17.
19. **Adversarial review + documentation review.** Depends on: 1-18.

## 11. Decisions carried forward (operator, do not relitigate) & Open questions

**Decision 1 — the mockup
(`assets/registry-mockup.html`) is the normative
UI.** Operator, verbatim: "I expect it to look and act exactly as in
your mockup." It defines the shipped appearance and the shipped
interactions, and the JSON the backend supplies, `card_html` included.
Requirements 14 and 15 encode it; the one deliberate exclusion is its
page-level chrome, because Q3 places this view on dash's existing page
(Requirement 14's scope bound). Two literals inside it are stale
against the live catalog and must become dynamic rather than being
copied across (Requirement 16): the models tab count at `:438` and the
"two repositories" sentence at `:470`. One part of it is mid-edit and
is raised as Q9 rather than guessed at. Redesigning anything else is
not this ticket's business.

**Decision 2 — the view must update when models or images are pushed.**
Operator, verbatim: "Also: it must update when new models or images are
pushed." Requirement 9 is the backend half (digest-keyed cache,
`HEAD` sweep, eviction), Requirement 16 the frontend half (a
visibility-scoped ~60 s poll plus a manual refresh). This constraint
arrived after Q1 and Q3 were settled and it overrides both; each of
those questions below records the supersession rather than leaving the
contradiction standing.

**Decision 3 — `embark.json` is not read, and nothing derived from it
ships.** Operator, verbatim: "Embark.json is application-specific and
should not be included in the design." It is one consumer's private
serving schema, so a registry browser that parses it is coupled to that
application and silently wrong for any kit not built for embark. The
`README.md` already carries the same facts in human form, so nothing is
lost. Cut: the serving-spec panel and every field behind it, the
asymmetric prefixes block, and the kind pill. Not substituted: there is
no generic source for a model's kind — the Kitfile's `package` block
has none — and guessing one from the repo name would reintroduce
exactly the coupling this removes (§5). Consequences recorded
throughout: the per-digest blob triple becomes a pair, the formula
becomes `1 + R + T + B` where a ModelKit digest costs 2 (21
registry-side requests for today's all-ModelKit catalog, 29 client
round trips), and Q4's proxy loses some of the structure it used to
assert on, which Q4 says plainly.

**Decision 4 — the `registry` tile in `tiles.json` is left alone.**
Decided here rather than left open, per the operator's own instruction
to decide and state. The tile answers "how do I reach it" through its
connect modal; the tab answers "what is in it". Neither substitutes for
the other, and merging them would need a `tiles.json` schema change
(backend tiles carry `connect`, not `url`) for no gain.

**Decision 5 — no external cache; SQLite on a host volume is the
store, and Redis is declined with a recorded trigger.** The operator's
input was conditional: "If you need an external cache, use redis." The
condition does not hold. **The verdict is unchanged and the reason
changed**, which is worth recording rather than quietly restating: an
earlier revision declined Redis on the grounds that an in-process dict
sufficed. That argument is gone — Requirement 23 replaced the dict with
a persisted store, precisely because "a restart costs one cold walk"
turned out to be the cost worth removing. The decision survives on two
different grounds. Costed rather than skipped:

- **Durability is already handled, by SQLite on the `dash_data` host
  volume.** That was the one thing an external store would have bought
  over a dict, and Requirement 23 buys it without a network hop, a
  credential, or a dependency. A restart no longer costs a cold walk at
  all (§4 P35).
- **Sharing is not a problem to solve: there is still exactly one
  instance, holding about 33 KB.**
  `deployments/applications/services/dash.hcl:5` declares
  `group "dash" {` with no `count`, which Nomad defaults to 1, pinned
  to one node by the constraint at `:6-9` (§4 P28). The store is ~31 KB
  of cards (§4 P25) plus a row per repo and per tag. An external store
  would buy cross-instance sharing for a service that has one
  instance.
- **Redis is genuinely available, and its cost here is known rather
  than hypothetical.** The opt-in pattern is established: a job joins
  `local.redis_cache_consumers`
  (`deployments/infrastructure/database.tf:98-103`), which drives a
  per-consumer database role (`:125-135`), policy and JWT role
  (`deployments/infrastructure/machine_roles.tf:322-331`, `:344-348`),
  and the job reads `redis/creds/cache-<job>` for a credential minted
  per render (`deployments/infrastructure/services.tf:521-531`). For
  dash it costs more than the usual per-job entry: naming a dedicated
  Vault role **replaces** `nomad-workloads` rather than adding to it
  (`machine_roles.tf:340-343`) and a Nomad task carries one `vault`
  stanza, so the Redis policy would have to be folded into the existing
  `dash` role's `token_policies` (`:312`) rather than added beside it
  (§4 P29). On top of that: the `redis` client dependency, connection
  and retry handling, and a new failure mode (Redis unreachable) in a
  backend whose whole design premise is minimal dependencies.
- **`CLAUDE.md:22-27` rules against it.** "Minimum code that solves the
  problem. Nothing speculative... No abstractions for single-use code."
  All of the above to hold 31 KB for a single-instance service.

  **ESCALATION TRIGGER, unchanged and the reason this decision is
  reviewable rather than a preference: if `dash` ever runs `count > 1`,
  the store stops being shared. Each instance would sweep
  independently, multiplying upstream cost by the instance count, and
  two browser tabs could see different catalogs. At that point Redis is
  the answer and the operator has pre-approved it.** A host volume is
  `single-node-writer`, so persistence does not soften this: a second
  instance gets its own empty file rather than a shared one. §9 records
  that this failure is silent, and Requirement 22 puts the trigger in
  `docs/dash-landing-page.md` so it is discoverable from outside this
  plan.

**Decision 7 — the digest store is persisted in SQLite on a host
volume, superseding the in-process dict.** Not an operator quote: a
decision the measurement forced, recorded here so it is not
relitigated. The cold walk is 21 registry-side requests — 29 client
round trips, since every blob answers `307` — and 1.20 s at eight-way
against 13 requests and 0.81 s for the sweep (§4 P7, P27, P31), and
cold start is the term that scales worst (§9's table). Persisting the
store removes it permanently rather than making it faster, and it is
safe to persist for one reason worth stating plainly: **a `cards` row
is keyed by a content digest, so it can never be invalidated — only
evicted when nothing references it.** Stdlib `sqlite3`, three tables,
one new host volume, no new dependency (Requirement 23). What this
supersedes: §5's old "cache persistence across restarts is out of
scope" non-goal, and the first leg of Decision 5's earlier argument.
**Requirement 28 gives this decision a second justification it did not
have when it was taken:** with the cards on disk, the ~26 KB of
rendered HTML and the ~31 KB payload (§4 P25) are not resident between
requests in a task reserving 128 MB. The dict held them there for the
life of the process.

**Decision 8 — async everywhere, including the database; `aiosqlite`
declined.** Operator, verbatim: "And async calls everywhere of course."
The HTTP half was already Requirement 8. The database half is the part
that bites: `sqlite3` is a blocking C library with no async API (§4
P36), so a query issued from an async handler holds the event loop for
its whole duration, serializing the eight-way concurrency the walk just
bought and delaying `/api/status` with it (§4 P37, §9). The resolution
is `asyncio.to_thread` around every database call (Requirement 25),
which costs a measured 26 µs per call against a 2.6 µs query — the hop
dominates, and both are microseconds. **Q12 adds the second half of
it:** the threads that run those calls must not share a connection,
because the walk writes concurrently and a shared connection breaks
under that (§4 P36). Two things declined:

- **`aiosqlite`** — a third runtime dependency on a backend whose
  design premise is minimal dependencies, for queries that are a
  handful of rows against a local file. It would buy syntax, not
  throughput: it runs the same blocking driver on a thread.
- **Rendering markdown off the loop, for now.** `markdown-it-py` is
  CPU-bound and runs inside the loop at a measured 4.12 ms per README
  (§4 P40). That is acceptable **only** because a card renders once per
  digest ever and is then persisted, so the cost is 16.5 ms on a cold
  walk and zero on every sweep after. If a future catalog makes cold
  start heavy — 250 digests would be about a second of blocked loop —
  the escape hatch is the same `asyncio.to_thread`. Stated rather than
  left unexamined. Requirement 28 reads the same once-per-digest fact
  as a resource argument rather than only a loop one.

**Decision 9 — the registry view and its route stay behind
oauth2-proxy, and no exemption is added.** Operator, verbatim: "the
registry page must be guarded by oauth proxy like the homepage is."
Both halves already hold by construction, so the work is preservation
rather than construction: the view is a section of `index.html` served
by the frontend upstream (Q3), and `/api/registry` is a third upstream
on a proxy that carries no skip-auth setting of any kind (§4 P38).
Requirement 27 turns that into a prohibition with a producer, §5
records it as a non-goal, and §9 records what an exemption would
expose. The one place this gets loosened later is the
`notifications.endpoints` webhook (Q5), which cannot carry a browser
session; if it is ever taken, the exemption is scoped to that one path
with its own shared secret and never widens.

**Decision 6 (VOID) — the docs-layer gap is accepted and shipped.** An
earlier revision of this ticket carried this from the operator. It
described a registry state that ended at `2026-09-05T06:35Z`, when all
four kits were repacked with a `docs.v1.tar` layer (§4 P16). A decision
whose premise is gone is not a decision to honor, so it is recorded
here as void rather than deleted, and Q6 below settles what replaces
it.

---

**How Q1-Q12 were settled.** The operator handed the loop over
mid-session with "get the registry UI done. I'm not here so I'm not
available for feedback. You have full control of the loop," then
returned briefly with the six constraints in §3. Every question below
was settled by the agent on the recommendation this section argues,
except where an operator constraint overrode it, which is marked. The
premise behind each is recorded in the front-matter `premise` table,
whose `Q<n>` keys are premise slots and do **not** line up with this
section's question numbers: this section's Q12 (the SQLite connection)
is front-matter `premise.Q11`, and front-matter `premise.Q12` is the
`If-None-Match` claim behind Requirement 24.
**Every agent-settled resolution here is reopenable on the operator's
return, and none of them is left open.** Q9 was settled in the
artifact itself — the layers table is in the mockup at
`assets/registry-mockup.html:889-917` and the modal order is card →
layers → commands, which is what Requirement 14 ports. Q11 resolved to
the standalone script, on a scope gap in `dash-backend-pytest` that was
verified rather than assumed. Q12, the newest, was settled by the
operator on a measurement: connection-per-call, with a shared
connection forbidden.

**Q1 — RESOLVED, (c') — a digest-keyed cache with no time expiry,
refreshed by a `HEAD` sweep behind a ~30 s floor. This SUPERSEDES the
earlier resolution of a flat 60 s TTL, and the operator's freshness
constraint (§3, Decision 2) is what forced the change. Originally OPEN:
does the backend cache registry responses, and if so where?** Measured
cost of one cold `/api/registry` call: 21 registry-side requests, 29
client round trips (§4 P7). A sweep alone is 13 of each and 0.81 s at
eight-way (§4 P27). With a 60 s poll now required (Requirement 16),
the cache is no longer an
optimization but the thing that makes the poll affordable. Four
options:

- **(a) No cache.** Every poll pays 21 registry-side requests, 29
  round trips. At one visible tab that is 21 a minute forever, most of
  them re-fetching and re-rendering blobs that provably cannot have
  changed.
- **(b) A flat 60 s TTL, keyed on the route.** What the previous
  revision resolved on, and it was defensible when the view fetched
  once on open. Under a poll it is actively wrong: the TTL expires on
  age, so every minute the cache throws away four rendered cards and
  re-fetches eight blobs to rebuild them identically. It also gives a
  worse freshness guarantee than (c') for strictly more work — a push
  is invisible for up to 60 s either way, but (b) pays 21 requests
  (29 round trips) to discover it and (c') pays 13 of each.
- **(c) Cache per manifest digest, re-reading catalog and tags each
  call.** Correct in principle; the previous revision named it and
  deferred it as "the right answer at a scale this cluster does not
  have."
- **(c') Cache per manifest digest, refreshed by a `HEAD` sweep behind
  a floor.** (c) plus the two things that make it cheap and safe: the
  digest comes from a `HEAD` with a zero-byte body rather than a full
  manifest `GET` (§4 P27), and the sweep is rate-limited so N open tabs
  cost one sweep per floor interval rather than N. Entries are evicted
  by absence from a sweep, never by age. Steady state with nothing
  pushed: 13 requests, zero blob fetches, zero renders.

  **Recommendation: (c').** A manifest digest is content-addressed, so
  a rendered card for a digest is valid forever; a time-based key
  throws away work that cannot go stale, and (b) does exactly that once
  a minute. (c') is also the only option that answers the operator's
  constraint honestly: freshness is bounded by the sweep interval and
  costs 13 requests to maintain, rather than being bought by re-doing
  everything. The extra code over (b) is a store keyed by digest, a set
  difference, and a timestamp floor — small enough to stay inside
  `CLAUDE.md:22-27`'s bar, which Decision 5 applies to the same
  question from the other direction. §9 records where it stops scaling.
  **AMENDED by Decision 7:** this question resolved on a dict in
  process memory. The keying argument is unchanged and is exactly why
  persisting is safe — a content-addressed key cannot go stale on disk
  either — but the store is now three SQLite tables on a host volume
  (Requirement 23), so the cold walk this option still pays is paid
  once ever rather than once per restart.

**Q2 — RESOLVED, (a') — ship the images tab with real rows for whatever
the sweep finds, using only fields the manifest already yields; the
empty state renders when there are none. This AMENDS the earlier
resolution of empty-state-only, and the operator's "images must render
if they are pushed" (§3, said twice) is what forced the amendment.
Originally OPEN: does the images tab ship at all in this ticket?** The
registry holds zero image repos today and cluster images go to
`ghcr.io/jasperhg90` (§4 P1), so the tab is empty in production on day
one — but "empty today" and "empty by construction" are different
promises, and the operator asked for the second to be false. Four
options:

- **(a) The empty state only.** What the previous revision resolved on.
  It is now insufficient: a pushed image would find no code path to
  render it, so the tab would stay empty after a push and quietly
  break the operator's stated requirement.
- **(a') Real rows from the manifest the sweep already reads.**
  Repository, tag, digest, and total size summed from the manifest's
  own `layers`. No index-resolution hop, no per-image config blob, so
  no extra request beyond what change detection already costs. A
  multi-arch tag resolves to an index with no `config` and no `layers`
  (§4 P30), so its row shows repo/tag/digest and a `multi-arch` marker
  with no size. The empty state still renders when the sweep finds
  none, which is today's state.
- **(b) The full path, including index resolution and per-image config
  blobs**, giving architecture and build date. Complete on arrival.
  Cost: an extra request per architecture per tag, on a path with zero
  production instances to verify against, and the mockup's own example
  rows are labelled "not in this registry"
  (`assets/registry-mockup.html:478`).
- **(c) Drop the images tab.** Ruled out by the request (§3) and now
  doubly so.

  **Recommendation: (a').** It satisfies the operator's requirement at
  no extra upstream cost, because every field it renders comes from the
  manifest the sweep fetches anyway. (b) buys two columns for an extra
  request per architecture and a branch nothing can exercise. The
  honest disclosure that goes with (a'): this whole path ships tested
  against `respx` fixtures and unverified against production, and Q4's
  label names that as a third thing the proxy does not measure. One
  correction the mockup's empty state needs regardless: its copy claims
  "two repositories" and the catalog holds four, so Requirement 16
  makes it dynamic.

  **AMENDED — (a''), `widen-surface`: a plain image manifest's config
  blob is fetched after all, and (b) stays refused for the index
  case.** The fork this amendment closes was not visible when (a') was
  taken. Requirement 14 makes the mockup normative, and its images
  table header
  (`assets/registry-mockup.html:482`) is
  `repository | tag | digest | arch | size | pushed`. Two of those six
  columns — `arch` and `pushed` — have no producer under (a') as
  written, because neither is in the manifest; the mockup's own
  footnote says so (`:504-508`). That left Requirement 10 and
  Requirement 14 contradicting each other, both citing the operator.
  Of the four options the contract names, this takes **`widen-surface`**:

  - **`widen-surface` (TAKEN).** For a **plain (non-index) image
    manifest, fetch its config blob**, which carries `architecture`,
    `os` and `created` (§4 P41, measured). That fills `arch` and
    `pushed`. It is the same shape the ModelKit path already runs —
    one config blob per distinct digest — and it is **not** the
    index-resolution hop (a') refused: no per-platform manifest is
    resolved and no second round of manifests is walked. The blob cost
    per digest becomes: ModelKit 2, plain image 1, index 0, and §2, §4,
    Requirement 7 and Requirement 10 are revised to that formula.
  - `split-ticket` — move the two columns to a follow-up with
    `depends_on = ["L5-landing-registry-tab"]`. Rejected: it would
    ship a normative table with two blank columns and no note saying
    why, which is the state that produced this fork.
  - `drop-requirement` — cut `arch` and `pushed` from the images table
    and record in §5 that the mockup's own table is not normative in
    those two columns. Rejected: it makes an exception to "look exactly
    as in the mockup" for a saving of one small blob per image digest.
  - `declared-proxy` — keep the columns and score them against
    something the repo can already measure. Not applicable: the
    problem was a missing producer, not an unmeasurable observable, and
    one config blob supplies it.

  **What stays refused:** index resolution. A multi-arch tag still
  renders repository, tag, digest and a `multi-arch` marker with no
  arch, no size and no pushed date (§5, Requirement 10). The mockup's
  footnote at `:504-508` is right about the config blob and describes
  index resolution as a further step; this ticket takes the first and
  not the second.

**Q3 — RESOLVED, (a') — a third `.section` on the existing page,
polling every ~60 s while its tab is visible, with a manual refresh;
never on the 15 s health loop. This AMENDS the earlier resolution of
"fetch on open and on tab click only", per the operator's freshness
constraint (§3, Decision 2). Originally OPEN: where does the registry
view sit on dash's page, and when does it fetch?** The request names the
file (`services/dash/frontend/index.html`) but not the placement. The
mockup is a standalone page with its own `registry_` wordmark and
summary strip (`assets/registry-mockup.html:407-434`);
dash's page already has an equivalent header of its own
(`index.html:383-411`) and two `.section` blocks (`:413-427`). Three
options for placement, then the cadence:

- **(a) A third `.section` on the existing page**, below Backend
  services. The mockup's page-level chrome is dropped (dash's header
  already carries that role) and its section eyebrow is kept.
- **(b) A separate static page** (say `registry.html`), linked from the
  header or from the `registry` tile. nginx serves any extra file under
  the `/` catch-all and a non-`/api` path falls through to the frontend
  (§4 P11), so this works with no extra upstream. Cost: a second page
  to keep in visual sync, and a navigation affordance dash does not
  have.
- **(c) Join the existing 15 s refresh loop.** Ruled out on cost: 13
  requests every 15 s per tab, four times the load of the 60 s poll,
  for a catalog that changes a few times a day.

  **Recommendation: (a'), meaning (a) plus a visibility-scoped ~60 s
  poll and a manual refresh.** Placement follows the request's own
  wording ("a models/images tab strip in the dash frontend
  (`services/dash/frontend/index.html`)"), keeps one page and one
  header, and bounds Requirement 14's "exactly as in the mockup" so it
  is not read as shipping a second wordmark and a second theme toggle.
  The cadence is where this question changed: fetch-on-open cannot
  satisfy "it must update when new models or images are pushed" for an
  operator who leaves the page open, so the view polls — on its own
  slower timer, stopped when the tab is not visible so a backgrounded
  dashboard costs nothing, and with a manual refresh for the operator
  who just pushed and does not want to wait. Requirement 16's
  non-blocking shell goes with it, so a cold walk never leaves the
  section blank behind a spinner-less page.

**Q4 — RESOLVED, `declared-proxy` — the label is mandatory and the eval
row must state what the proxy does not measure. Originally OPEN, tagged
`unmeasurable-requirement`: several requirements demand observables
this repo cannot produce.** Requirements 14 (the shipped UI looks
exactly like the mockup), 15 (every mockup interaction works), the
frontend half of 16 (the poll runs while visible and stops otherwise,
the shell paints first), and the rendering half of 11 (a docs-less kit
shows the plain note rather than a blank panel) are claims about **what
a browser draws and how it responds to input**. Nothing in §7's code
surface produces that: there is no JS or browser test harness anywhere
in this repo, no project `package.json`, and dash's frontend has zero
tests (§4 P17). The operator's four options:

- **`widen-surface`** — add a browser test harness (playwright or
  equivalent) to §7, plus the CI or pre-commit hook to run it, making
  appearance and interaction assertions a real gate. This makes the
  metric part of this ticket and revises §2 upward: a new dependency, a
  new hook, and a first-of-its-kind test tier for this repo. Note this
  option got stronger when Requirements 14 and 15 arrived — there is
  now more unverifiable frontend surface than there was — and it is
  still not taken, for the reason below.
- **`split-ticket`** — move "the frontend matches the mockup and
  behaves correctly" into its own plan file with `depends_on =
  ["L5-landing-registry-tab"]`, and let that ticket carry the harness
  decision.
- **`drop-requirement`** — cut the appearance and interaction claims
  from §6, keeping only the payload halves, and record in §5 that
  browser behavior is out of scope. Not available in practice: the
  operator stated Requirements 14 and 15 verbatim and they are the
  point of the ticket.
- **`declared-proxy`** — keep every requirement and score them with an
  explicitly labelled proxy. The proxy is the backend assertions in
  `deployments/applications/services/dash/backend/tests/test_registry.py`,
  `deployments/applications/services/dash/backend/tests/test_registry_client.py`
  and
  `deployments/applications/services/dash/backend/tests/test_main.py`,
  scoped to the path production actually takes: **a card assembles from
  a real docs layer and its `card_html` contains the rendered markdown
  (`<table>`, `<pre><code class="language-...">`, and `&lt;script&gt;`
  for escaped raw HTML), the docs-less fallback assembles without
  raising, the digest cache does no blob work when nothing changed and
  exactly two blob fetches when something did, and an image manifest
  produces an images row.** The manual browser check in §8 covers the
  rest. The eval row's Expected cell must state what the proxy does
  **not** measure:
  1. It does not verify that the browser draws anything — not the card
     pane, not the `.md` styling, not the layer bar, not the docs-less
     note, not the empty state, not the tab underline. Every appearance
     claim in Requirement 14 is manual-only.
  2. It does not verify any interaction from Requirement 15 — not tab
     switching or its keyboard handler, not modal open or either close
     path, not the copy-button label cycle or its clipboard fallback,
     not theme persistence — nor the frontend half of Requirement 16:
     that the poll runs while visible, stops when hidden, or that the
     shell paints before the payload.
  3. It does not verify the images path against production at all.
     Requirement 10 ships tested against `respx` fixtures written from
     the OCI spec and Docker Hub probes (§4 P2, P41), and the registry
     holds no image today (§4 P1), so the first real push is the first
     real test. §11 Q2's amendment adds a config-blob read to that
     path — the source of `arch` and `pushed` — so there is now more
     fixture-only surface here, not less.

  **Recommendation: `declared-proxy`, re-scoped to the production path,
  and weaker than it was.** An earlier revision named a proxy that
  asserted only the docs-less case, which production no longer
  produces; the re-scoped proxy above fixes that and extends to the
  cache and the images row. But Decision 3 cut the serving-spec panel,
  and with it most of the machine-checkable *structure* in the card
  payload — there is no longer a spec grid whose eight fields a test
  can assert on. **What remains rests almost entirely on two claims: a
  card assembles and renders from a real docs layer, and the docs-less
  fallback does not raise.** That is a real assertion with teeth (it
  catches a raise where a `200` belongs, and an unescaped `<script>`
  reaching `innerHTML`) and it is thinner than it was; saying so is the
  point of the label. `widen-surface` would add a browser harness, a
  dependency and a gate tier to a repo that has never had one, and §2
  does not have room for it alongside the cache, the concurrency work
  and the images path. Whichever fork the operator picks, the label is
  mandatory: retargeting these requirements to "the JSON payload is
  right" without saying that the drawing, the interactions and the
  images path are unverified is the silent downgrade this question
  exists to prevent. **Requirements 14 and 15 are operator-stated and
  machine-unverified in this repo, and nothing in this ticket should
  read as implying otherwise.**

**Q5 — RESOLVED, (a) — the backend follows the redirect;
`registry.hcl` stays untouched. Originally OPEN: does the backend
follow the registry's blob redirect, or does the registry stop
redirecting?** Blob GETs answer `307` with a presigned MinIO URL (§4
P5), so the bytes arrive from `192.168.2.29:9000`, not from the
registry. Two options:

- **(a) The backend follows the redirect.** `follow_redirects=True` on
  the registry client (Requirement 8), no change to the registry.
  Measured working end to end: `307` then `200`, 2033 bytes,
  `history: [307]`, and Basic auth survives the cross-host hop in both
  the manual-header and `auth=` forms. Cost: dash's registry route now
  depends on MinIO's reachability too (§9), and any test that stubs
  only the destination URL passes while production fails.
- **(b) Disable the registry's storage redirect** (`storage: redirect:
  disable: true` in
  `deployments/applications/services/registry.hcl`'s config template,
  `:143-157`), so the registry proxies blob bytes itself and dash never
  talks to MinIO. Cost: a change to a shared, live job that every
  puller shares. embark's prestart task pulls whole multi-hundred-MB
  ModelKits through it (`deployments/applications/services/embark.hcl:29-31`),
  and routing those bytes through the registry on `ubuntu` instead of
  straight from MinIO moves real traffic onto a node whose own comment
  calls it deliberately small
  (`deployments/applications/services/registry.hcl:195-204`).

  **Recommendation: (a).** The redirect is the registry's designed
  behavior and the reason embark's pulls are fast. Turning it off to
  simplify two ~2 KB metadata reads per new digest would tax every
  multi-hundred-MB model pull in the cluster. The digest cache makes
  the trade better still: in steady state the route touches no blob and
  therefore no MinIO at all. §5 already puts `registry.hcl` out of
  scope on this reasoning; this question records why rather than
  leaving the absence unexplained. Note the same file is where §9's
  `notifications.endpoints` escape hatch would land, which is a second
  reason to keep the reason for its exclusion written down.

**Q6 — RESOLVED, (a) — render the card server-side in Python with
`markdown-it-py`. NEWLY OPENED by the registry repack: the docs layer
now exists, so where does its markdown become HTML?** All four kits
carry a `README.md` in a `docs.v1.tar` layer (§4 P16), which makes the
operator's original ask ("show some sort of card... just do a pull
`<CARD>.md` and read only that artifact", §3) satisfiable for the first
time — and after Decision 3, the rendered README is the *only* prose
source the card has. Three options:

- **(a) Render in the backend with `markdown-it-py`**, ship the result
  as `card_html`, and let the frontend assign it. One new dependency,
  a small wrapper, and the logic lands where `pytest` and `mypy
  --strict` already reach (`.pre-commit-config.yaml:101-112`). Verified
  behavior: preset `js-default` renders GFM tables and fenced code and
  escapes raw HTML by default (§4 P23), and it ships `py.typed` so no
  stub package is needed (§4 P24). It also renders **once per digest**
  and caches (Requirement 9), so the poll costs no repeated render.
  Cost: a runtime dependency and ~26 KB of HTML in the payload (§4
  P25).
- **(b) Render in the browser with a hand-rolled JS markdown
  function.** No dependency, no payload growth. Cost: this repo has no
  JS or browser test harness of any kind (§4 P17), so a hand-rolled
  renderer would be untestable by construction — and a markdown
  renderer is precisely the sort of code that needs tests, since GFM
  tables, fenced blocks and HTML escaping are each a separate failure
  mode. Shipping an untested escaper into an `innerHTML` assignment is
  the worst combination on offer. It would also re-render on every
  60 s poll rather than once per digest.
- **(c) Load a markdown library from a CDN.** Smallest diff. Cost:
  dash would depend on an external host to draw its own dashboard, on
  a page reached through oauth2-proxy inside a private cluster. That is
  a new outbound dependency for a page whose whole purpose is to work
  when other things do not, and it puts a third party's script inside
  the authenticated origin.

  **Recommendation: (a).** (c) is rejected outright: the dashboard must
  not need the public internet to render. (b) is rejected because §4
  P17 already established there is nothing in this repo that could test
  it — the same fact Q4 turns on — and an untested HTML escaper feeding
  `innerHTML` is a security decision made by accident. (a) puts the
  logic where the gates already are, for one small, typed, widely-used
  dependency, and the digest cache makes the render a once-per-artifact
  cost rather than a per-request one. Decision 3 raises the stakes: the
  card pane is now the whole of the modal's content, so its correctness
  matters more than when it sat beside a spec grid. The escape behavior
  is a requirement with a test (Requirement 5), not a comment.

**Q7 — RESOLVED, (a) — deduplicate by manifest digest, one card per
digest, listing every tag. NEWLY OPENED: every repo carries two tags
pointing at one digest.** Confirmed by `Docker-Content-Digest` on both
tags of all four repos (§4 P22). The earlier revision of this ticket
spoke of "repo-tag pairs" as cards, which would draw eight cards for
four kits. Three options:

- **(a) Deduplicate on the manifest digest.** Read a digest per tag
  (the sweep's `HEAD` already yields it), group by digest, fetch the
  two blobs once per group, and carry `tags` as a list on the card.
  This is the shape the mockup renders (`:806` joins the tag list,
  `:873` repeats it in the modal head), and it is the same key the
  cache uses (Requirement 9), so grouping and caching are one mechanism
  rather than two.
- **(b) One card per repo, showing only `latest`.** Simplest. Cost: it
  silently hides any tag that is not `latest`, which is wrong the first
  time two tags diverge, and the registry gives no signal when that
  happens.
- **(c) One card per repo-tag pair.** No grouping code. Cost: eight
  cards for four kits, eight extra blob fetches per cold walk, and a UI
  that presents two views of one artifact as two artifacts.

  **Recommendation: (a).** (c) is what the previous revision implied
  and it is visibly wrong against the live registry. (b) is a
  correctness bet on a convention the registry does not enforce. (a)
  costs one `dict` keyed by digest, makes the cold request formula
  `1 + R + T + B` — two blobs per ModelKit digest rather than three per
  tag — and shares its key with the cache that Requirement 9 needs
  anyway.

**Q8 — RESOLVED, (a) — one endpoint, cards inline. NEWLY OPENED: does
the card come back with the list, or on demand per repo?** The payload
is ~31 KB with four kits, ~26 KB of it `card_html` (§4 P25), and it is
now fetched every 60 s per visible tab rather than once per open.
Three options:

- **(a) One `/api/registry` payload with `card_html` inline.** One
  route, one fetch, one cache, and the modal opens instantly with no
  second round trip. Cost: ~31 KB per poll on a page that would
  otherwise send ~7 KB, and the cold walk pays `2D` blob fetches even
  for cards nobody opens — though only once per digest, since the cache
  holds the render (Requirement 9).
- **(b) A second route, `/api/registry/<repo>`, fetched on modal
  open.** Smaller payload. **Not available:** oauth2-proxy matches
  upstream paths exactly, so `/api/registry/embeddinggemma-q8` falls
  through to the frontend and returns the HTML page (§4 P11). This
  option is not a tradeoff, it is unroutable.
- **(c) A query variant, `/api/registry?card=<repo>`, fetched on modal
  open.** This **would** route: the probe confirms
  `/api/registry?tab=models` still matches the path-scoped upstream
  (§4 P11). Cost: a second code path, a second payload shape, a spinner
  in the modal, and a per-open round trip.

  **Recommendation: (a), with (c) recorded as the escape hatch.** At
  four kits, 31 KB is one response and the modal is instant. The poll
  raises the stakes a little — 31 KB a minute per visible tab, on a
  LAN, inside an authenticated origin — but not enough to buy a second
  code path yet. (b) is ruled out by the proxy, and that fact is worth
  recording so nobody reaches for the obvious REST shape and discovers
  it silently serving HTML. (c) is the right move if the catalog
  reaches a few dozen kits or the cards grow — §9's scaling table is
  where that threshold is written down — and Requirement 1's "any flag
  is a query parameter" is written the way it is to keep that door
  open, as the manual refresh in Requirement 16 already does.

**Q9 — RESOLVED, (a) — the layers table is restored to the mockup and
is ported. Originally OPEN. Does the model card modal carry a layers
table, and is the mockup's omission of it deliberate?** Settled in the
artifact rather than on paper: the table is in the mockup, `openCard`
(`:867-934`) writes card (`:879-887`), layers (`:889-917`) and
commands (`:919-931`) in that order, and the
`.layers`/`.layer-wrap`/`.swatch` CSS at `:312-324` selects again
(§4 P33). That order is the one the operator stated when `embark.json`
was cut: "rendered model card → layers table → pull commands". When
this question was opened the table was absent and its CSS was
orphaned, which is the evidence that decided it. Three options were on
the table:

- **(a) Restore the layers table to the mockup and port it.** The
  order becomes card → layers → commands, matching the operator's
  stated order and re-using the surviving CSS. The data is already on
  the card (`layers`, each with path, kind, size and digest,
  Requirement 4) and the kit-card stack bar already renders the same
  array (`:782-792`), so nothing new is fetched.
- **(b) Ship without it and delete the orphaned CSS.** The modal is
  card plus commands; the layer *bar* on the kit card still conveys the
  stack visually. Cost: the per-layer digests and exact sizes lose
  their only home, and `.swatch`, which exists to key a layer row to
  its material color, loses its purpose entirely.
- **(c) Ship without it and leave the CSS.** Rejected on sight: dead
  CSS in a file this repo treats as normative is how the next reader
  learns to distrust it.

  **RESOLUTION: (a), taken.** The omission was an incomplete edit, not
  a decision: it was lost when the `embark.json` spec grid was cut, and
  the surviving CSS was the evidence. The table is back in the mockup at
  `assets/registry-mockup.html:889-917`, the modal order is now card →
  layers → commands as the operator stated, and the `.layers`,
  `.layer-wrap` and `.swatch` CSS at `:312-324` selects again. Subticket
  9's "confirm the mockup before porting" step stands, but the answer it
  will find is settled. Original reasoning follows.

  The orphaned CSS is stronger evidence of an incomplete edit than of a
  decision — the same signature as the false-callout removal earlier in
  this ticket's history — and it matches what the operator said the
  order should be. It costs no extra request. **The implementer should
  confirm the mockup before porting** (subticket 9) rather than
  inferring the answer from a file that may change again; if the
  mockup still lacks the builder at that point, restore it there first
  so Requirement 14's "port, do not reinterpret" stays literally true.

**Q10 — RESOLVED, (a) — the registry client owns its own
`httpx.AsyncClient`; `_http.py` is untouched. NEWLY OPENED by the
concurrency requirement: where does the async, redirect-following,
bounded HTTP client live?** The walk must be concurrent to be
affordable (§4 P31) and Starlette is already async (`main.py:56`), but
`_http.py` today is a sync, `GET`-only, JSON-only helper that every
`/api/status` call depends on (`:25-53`). Two options:

- **(a) The registry client constructs and owns its own
  `httpx.AsyncClient`**, with `follow_redirects=True`, Basic auth and
  `limits=httpx.Limits(max_connections=8)`, and imports `FetchError`
  from `_http.py` (`:20-22`) so the error taxonomy stays single.
  `_http.py` gets no diff at all. Cost: two HTTP helpers in one
  backend, which a reader has to notice.
- **(b) `_http.py` gains an async twin** alongside `get_json`, plus the
  redirect, auth, bytes and `HEAD` paths. One module, one import site.
  Cost: it touches the module the entire existing status path runs
  through, for four capabilities none of that path's callers use, and
  every one of those additions is dead code from `/api/status`'s point
  of view. It also puts a sync and an async client in one file, which
  is where the next reader picks the wrong one.

  **Recommendation: (a).** The blast radius argument decides it: `dash`
  has one working endpoint in production and this ticket should not
  edit the module that endpoint's every call passes through in order to
  add a second one. Sharing `FetchError` keeps the one thing worth
  sharing — `main.py`'s broad `except Exception` (`:56-75`) does not
  care which module raised — and §7 records `_http.py` as expected
  unchanged so the diff itself is the check. Two consequences worth
  stating: the `307` trap's documentation moves to the registry
  client's header block, since that is now the only client that meets
  it; and the async tests need no new dependency, because
  `TestClient` drives the route (`deployments/applications/services/dash/backend/tests/test_main.py:107-109`) and
  `asyncio.run(...)` drives a helper directly (§4 P32).

**Q11 — RESOLVED, (a) — a standalone `scripts/check_oauth2_proxy_guard.py`
with its own `local` hook scoped to the jobspec. Originally OPEN. Where
does Requirement 27's no-skip-auth check live: a new repo-level hook, or
the backend test suite with a widened scope?**
The requirement is settled (Decision 9); only its producer's home is
not, and the choice trades one small new gate against the coverage of
an existing one. The constraint that decides it:
`dash-backend-pytest` is scoped to
`^deployments/applications/services/dash/backend/`
(`.pre-commit-config.yaml:107-112`), so a commit that touches only
`deployments/infrastructure/services/oauth2-proxy.hcl` — exactly the
commit that would add an exemption — runs none of the backend tests.
Three options:

- **(a) A standalone `scripts/check_oauth2_proxy_guard.py` plus a
  `local` hook scoped to that file.** Fires on the commit that matters.
  Follows a shape this repo already has: `tf-block-diff-self-test`
  (`.pre-commit-config.yaml:66-74`) runs a `scripts/` tool that carries
  its own cases because `scripts/` holds no pytest project (`:68`). The
  script inherits the existing `ruff`, `ruff-format` and `mypy` hooks,
  all scoped to `^(cli|scripts)/` (`:37-65`), so it is linted and
  type-checked with no config change. Cost: one new file and one new
  hook entry, and §2 counts it.
- **(b) The assertion in the backend suite, with
  `dash-backend-pytest`'s `files:` widened to also match
  `oauth2-proxy.hcl`.** No new file. Cost: a Python test in a
  standalone uv project reaching six directories up to the repo root,
  which breaks the moment anyone runs `pytest` from inside the backend
  directory rather than from the root; and a hook whose name and scope
  now lie about what it covers.
- **(c) The assertion in the backend suite with no scope change.**
  Rejected: it would pass review looking like a gate while never
  running on the commit it exists to catch, which is worse than no
  producer at all because it reads as covered.

  **RESOLUTION: (a), taken.** A gate that does not fire on the commit
  it exists to catch is not a gate, and `dash-backend-pytest`'s scope
  means (b) and (c) both fail that test — (c) outright, (b) by making a
  hook's name lie about its coverage while adding a six-level path
  traversal that breaks when pytest runs from the backend directory.
  The script must name `OAUTH2_PROXY_SKIP_AUTH_ROUTES`,
  `SKIP_AUTH_REGEX` and `SKIP_AUTH_PREFLIGHT` explicitly rather than
  grepping for `SKIP`, because `OAUTH2_PROXY_SKIP_PROVIDER_BUTTON` is a
  legitimate near-miss already in the file. Original reasoning follows.

  The point of Requirement 27 is that an exemption fails a gate rather than
  passing unnoticed, and (b) and (c) both weaken exactly that. (a)
  costs one file in a directory that already exists for this kind of
  tool. If the operator would rather not grow the hook list, (b) is
  serviceable and the plan should be amended to say the path traversal
  is deliberate; do not take (c).

**Q12 — RESOLVED by the operator, (b) — a fresh connection per call,
opened inside the worker and closed in a `finally`; a shared connection
is forbidden. NEWLY OPENED by a measurement: `check_same_thread=False`
is necessary and not sufficient.** An earlier revision of this plan
concluded that `threadsafety 3` (SQLite's serialized mode) licensed
sharing one connection across `asyncio.to_thread` workers, and mandated
a test asserting that two workers reading through one connection do not
raise. **That test certifies the wrong property.** The store's real
load is Requirement 8's eight-way per-digest gather, whose members each
**write** a `cards` row. Measured, each shape in its own subprocess
against a fresh database every trial (§4 P36):

| shape | result |
|---|---|
| 8 concurrent **writes**, one shared conn (`check_same_thread=False`) | operator: 6 of 20 clean, 2 `InterfaceError`, **12 `SIGSEGV`**. Here: **0 of 60 clean**, 57 raises and **3 runs that wrote 5 or 6 of 8 rows without raising** |
| 8 concurrent **writes**, shared conn + `isolation_level=None` | operator: 16 of 20 clean, **4 `SIGSEGV`**. Here: 60 of 60 clean |
| 8 concurrent **writes**, connection-per-call | operator: 20 of 20 clean. Here: 20 of 20 clean, all eight rows present |
| 8 concurrent **reads**, one shared conn — the shape the old test asserted | 20 of 20 clean in both runs |

Three options:

- **(a) Keep one shared connection and serialize the writes behind an
  `asyncio.Lock`.** No connection churn. Cost: it hands the store a
  second concurrency mechanism to get right, it serializes the writes
  the gather just parallelized, and it leaves a shared `Connection`
  one careless call site away from the failures above — including the
  ones that do not raise.
- **(b) A fresh `sqlite3.connect()` inside each worker, closed in a
  `finally`.** Nothing crosses a thread, so there is nothing to
  serialize and `check_same_thread` never comes up. Cost: one
  `open`/`close` on a local file per query.
- **(c) `aiosqlite`.** Declined already on dependency grounds
  (Decision 8), and it would not help: it runs the same blocking driver
  on a thread and inherits the same rule about not sharing a
  connection across them.

  **RESOLUTION: (b), taken by the operator.** The crash column decides
  it. A `SIGSEGV` is not an exception: no `try`/`except` sees it, no
  retry survives it, and it takes the uvicorn process down with
  `/api/status` (§4 P37, §9). Even where nothing crashed, three runs
  wrote fewer rows than they were given and returned cleanly, which is
  worse than a raise because nothing reports it. (a) would work if
  every call site respected the lock forever; (b) removes the shared
  object instead, which is the smaller thing to keep true.
  `isolation_level=None` is not a fix — it is the same shared
  connection with a different failure rate, and the rate differs by
  hardware. **The producer moves with the resolution:** Requirement 25
  and §8 now mandate an **eight concurrent write** test asserting all
  eight rows land, and say in as many words that the read-only variant
  does not satisfy it, since the read case passes 20 of 20 on the
  broken shape.

## Premises / assumptions

- **P1.** The registry's catalog holds exactly four repositories today,
  `embeddinggemma-q8`, `embeddinggemma-qat`, `mxbai-rerank-qat` and
  `mxbai-rerank-xsmall-v1-q8`, all ModelKits; there are zero container
  image repos.
  `probe:` `GET https://registry.lab.orangecluster.nl/v2/_catalog?n=200`
  with the `push` basic-auth credential, re-run 2026-09-05 after the
  06:35Z repack, captured:
  `{"repositories":["embeddinggemma-q8","embeddinggemma-qat","mxbai-rerank-qat","mxbai-rerank-xsmall-v1-q8"]}`;
  and a manifest read per repo returning
  `artifactType= application/vnd.kitops.modelkit.manifest.v1+json` for
  all four. Totals: 343.1 MB, 978.0 MB, 107.0 MB, 95.8 MB.
  `Evidence:` cluster images are pushed to `ghcr.io/jasperhg90`
  (`deployments/applications/services.tf:345`, `:389-390`).
- **P2.** `artifactType` separates the two kinds: a ModelKit manifest
  carries `artifactType:
  application/vnd.kitops.modelkit.manifest.v1+json`, and a real
  container image tag resolves to an OCI index carrying no
  `artifactType` and no `config`.
  `probe:` the ModelKit manifest reads in P1; and
  `GET https://registry-1.docker.io/v2/library/registry/manifests/3.1.1`
  with an anonymous pull token and the OCI/Docker `Accept` set, run
  2026-09-05, captured: `mediaType:
  application/vnd.oci.image.index.v1+json`, `artifactType present:
  False`, `config present: False`, `top-level keys: ['manifests',
  'mediaType', 'schemaVersion']`, child entry keys `['annotations',
  'digest', 'mediaType', 'platform', 'size']`, child `config
  mediaType: application/vnd.oci.image.config.v1+json`.
- **P3.** The Kitfile config blob is ~2033 bytes of raw JSON (1976,
  2012, 2033 and 2098 across the four kits) carrying `manifestVersion`,
  `package` (`name`, `version`, `description`, `license`, `authors`),
  and `model`/`code`/`docs` sections listing every layer's path and
  digest. It is the sole source of the card's text alongside the
  rendered README (Requirement 4).
  `probe:` `GET /v2/embeddinggemma-q8/blobs/sha256:<config digest>`
  with `follow_redirects=True`, run 2026-09-05, captured:
  `status=200 bytes=2033 history=[307]`, `config top keys: ['code',
  'docs', 'manifestVersion', 'model', 'package']`, `package:
  {"name": "embeddinggemma-q8", "version": "0.1.0", "description":
  "Embedding model, INT8 post-training quantization. 328 MB, and the
  embedder embark serves by default.", "license":
  "LicenseRef-Gemma-Terms-of-Use", "authors": ["Google", "embark"]}`.
  This blob is the one place a raw `.json()` is correct; every layer
  blob is not (P4). Note it carries no model "kind" field, which is why
  §5 forbids substituting one for the cut kind pill.
- **P4.** Layer blobs are plain tar, not gzip and not raw JSON. The
  `docs` layer this ticket reads holds one member, `README.md`.
  `probe:` the manifest reads in P1 list layer mediaTypes
  `...modelkit.model.v1.tar` (309,664,768 B, `model.onnx`),
  `...modelkit.modelpart.v1.tar` (2,048 B `embark.json`; 67,072 B
  `golden.json`; 33,387,008 B `tokenizer.json`),
  `...modelkit.code.v1.tar` (3,584 B `justfile`) and
  `...modelkit.docs.v1.tar` (6,656 B `README.md`), each with an
  `org.cncf.model.filepath` annotation; and a
  `tarfile.open(fileobj=..., mode="r")` on a fetched layer, run
  2026-09-05, captured `status=200 history=[307]` and a single-entry
  member list. The failure mode is recorded rather than inferred: an
  earlier probe of this ticket called `json.loads` on layer bytes and
  raised `JSONDecodeError`. The `embark.json` layer is listed here
  because the manifest lists it and the layer table renders it; per
  Decision 3 nothing fetches or parses it.
- **P5.** A blob GET answers `307` and redirects to a presigned MinIO
  URL; httpx returns that `307` unless `follow_redirects=True`; and the
  `307` does not surface as a status error under a `>= 400` guard.
  `probe:` the config blob URL from P3 fetched twice with httpx, run
  2026-09-05, captured: `httpx version: 0.28.1`, `httpx.Client
  follow_redirects default: False`, `blob GET without
  follow_redirects -> 307`, `location ->
  http://192.168.2.29:9000/registry/docker/registry/v2/blobs/sha256/8e/...?X-Amz-...`,
  `body len: 0`, `.json() raised ValueError: Expecting value: line 1
  column 1 (char 0)`, and `blob GET with follow_redirects -> 200 2033
  history: [307]`. Basic auth survives the cross-host hop in both
  shapes: `manual Authorization header + follow_redirects: 200 2033
  [307]` and `auth= param + follow_redirects: 200 2033 [307]`.
  `Evidence:`
  `deployments/applications/services/dash/backend/src/dash_app/_http.py:47-48`
  guards only `>= 400`, so a `307` passes it and reaches `:50-53`,
  where `response.json()` on an empty body raises and becomes
  `FetchError("... did not return JSON")` — the shape of misleading
  failure the registry client's header block must record.
- **P6.** dash's node reaches the registry only through the edge, and
  reaches MinIO directly, both without a firewall change.
  `Evidence:` `deployments/applications/services.tf:121-125` (registry
  port 5000 admitted from `192.168.2.30` alone);
  `deployments/infrastructure/services.tf:261-271` (HAProxy 443 from
  `192.168.0.0/16`); `:252-259` (MinIO 9000 from `192.168.0.0/16`);
  `docs/dns.md:3` (public DNS resolves `*.lab.orangecluster.nl` to the
  cluster edge). `probe:` `getent hosts
  registry.lab.orangecluster.nl` returned `192.168.2.30`, and
  `curl https://registry.lab.orangecluster.nl/v2/` returned
  `http=401 ssl_verify=0` (publicly valid certificate, auth required),
  both run 2026-09-05, and every blob probe above went through the same
  pair.
- **P7.** One cold deduped `/api/registry` assembly for the current
  catalog costs **21 requests at the registry and 29 round trips at the
  client**, and the registry-side shape is `1 + R + T + B`.
  **The two numbers count different things and both are load-bearing**,
  which is why they are stated together: an earlier revision of this
  premise called 21 "measured", and what was measured is 29.
  `Evidence:` with `R = 4` repos, `T = 8` tags, and `B = 8` blobs (four
  ModelKit digests at two blobs each; a plain image digest would cost
  one and an index none, §11 Q2), `1 + 4 + 8 + 8 = 21`. That is exact
  arithmetic over P1, P22, Decision 3's two-blob rule and Q2's
  one-blob-per-image rule, not a measurement, and the mockup's own
  footnote states the same formula and count for its all-ModelKit
  catalog (`assets/registry-mockup.html:452-458`).
  `probe:` the deduped eight-way walk replayed through a counting
  transport, two runs, captured
  `R=4 T=8 D=4 formula 1+R+T+2D=21 counted_requests=29 elapsed=1.40s`
  and the same with `elapsed=1.14s`. **The client issues 29 because
  each of the eight blob GETs answers `307` to MinIO (P5) and
  Requirement 8 makes `follow_redirects=True` mandatory, so every blob
  costs two round trips: `21 + 8 = 29`.** The earlier measurement of
  the same walk without a counting transport recorded 1.20 s eight-way
  and 4.49 s serial, matching the ~1.2 s the mockup's footnote records.
  `probe (superseded):` the pre-Decision-3 walk measured 25
  registry-side requests at 4.96 / 5.35 / 5.46 s serially, three runs
  on 2026-09-05. Against the sweep's 13 requests — 13 round trips too,
  since the sweep touches no blob and nothing redirects (P27) — cold
  start is the harsher bound and the one Requirement 23 removes by
  persisting rather than by accelerating. P21's vantage-point caveat
  applies to the seconds, not to either count.
- **P8.** The backend's existing HTTP helper is sync, has a 2.0 s
  default timeout, follows no redirects, issues `GET` only, and returns
  parsed JSON only — none of which suits the registry walk, which is
  why Q10 gives the registry client its own.
  `Evidence:` `_http.py:17` (`TIMEOUT_SECONDS = 2.0`); `:20-22`
  (`FetchError`, the one piece the registry client imports); `:25-30`
  (signature, returning `tuple[Any, httpx.Headers]`); `:42-43` (sync
  client construction and `client.get`); `:47-48` (the `>= 400`
  guard); `:51` (`return response.json(), response.headers`).
- **P9.** The `nomad-workloads` role grants a job read only under
  `secret/data/<namespace>/<job_id>/*`, so any job reading another
  job's KV prefix gets a 403, and the repo's answer is a copy under the
  consumer's own prefix.
  `Evidence:`
  `bootstrap/roles/nomad_server/templates/vault_nomad_workloads.hcl.j2:1`;
  `deployments/applications/secrets.tf:81-100` (the comment states the
  403 and the reason, and `embark_registry_credentials` at
  `default/embark/registry` is the copy); `:143-151`
  (`registry_auth` holds `username`, `password` and `htpasswd`; the
  copy carries the first two only).
- **P10.** dash's Vault JWT role already carries `nomad-workloads`, so
  a KV secret under `default/dash/*` is readable by the job with no
  `machine_roles.tf` change, and its `bound_claims` gate on the job id
  rather than the task.
  `Evidence:` `deployments/infrastructure/machine_roles.tf:312`
  (`token_policies = ["nomad-workloads", ...]`); `:284-290` (the
  comment stating the default grant is kept for the job's own KV
  prefix); `:297-300` (`bound_claims` on `nomad_namespace` and
  `nomad_job_id = "dash"` only).
- **P11.** oauth2-proxy routes multiple upstreams by exact path, so
  `/api/registry` needs its own entry, must carry no path parameters
  and must carry no trailing slash; query strings still match.
  `probe:` `docker run --network host
  quay.io/oauth2-proxy/oauth2-proxy:v7.13.0` with
  `--upstream=http://127.0.0.1:18001`,
  `--upstream=http://127.0.0.1:18002/api/status`,
  `--upstream=http://127.0.0.1:18003/api/registry` against three local
  echo servers, run 2026-09-05. Startup log captured:
  `mapping path "/api/registry" => upstream
  "http://127.0.0.1:18003/api/registry"`, `mapping path "/api/status"
  => ...:18002/api/status`, `mapping path "/" => ...:18001`. Request
  results captured: `/` and `/index.html` to FRONTEND;
  `/api/status` to STATUS; `/api/status/nested` to FRONTEND;
  `/api/registry` to REGISTRY; `/api/registry/nested` to FRONTEND;
  `/api/registry?tab=models` to REGISTRY; **`/api/registry/` to
  FRONTEND**. Containers and servers stopped after the run.
  `Evidence:` the same finding already recorded at
  `deployments/infrastructure/services/oauth2-proxy.hcl:46-57` and
  `docs/dash-landing-page.md:75-85`.
- **P12.** dash's Nomad ACL grant is `read-job`, `list-jobs` and
  `node:read` and has no bearing on a Vault KV read, so this ticket
  needs no change to it.
  `Evidence:` `deployments/infrastructure/machine_roles.tf:243-254`
  (the `rules_hcl` heredoc); `:233-237` (the comment tying each
  capability to the status functions that need it).
- **P13.** This backend's tested convention for HTTP-calling code is
  `respx`-mocked with no real network, covering parse shape, header
  placement and failure collapse.
  `Evidence:`
  `deployments/applications/services/dash/backend/tests/test_http.py:17-78`;
  `deployments/applications/services/dash/backend/tests/test_consul_client.py:24-50`;
  `deployments/applications/services/dash/backend/pyproject.toml:22-28`
  (`respx` already a dev dependency).
- **P14.** The frontend makes one same-origin call, `/api/status`,
  re-run every 15 s, holds no data source of its own, and already
  carries a header and a theme toggle.
  `Evidence:`
  `deployments/applications/services/dash/frontend/index.html:561`
  (the fetch); `:588` (`setInterval(refresh, 15000)`); `:413-427` (the
  two sections it renders into); `:433-454` (the one dialog, whose
  `</dialog>` is `:454`; `:456` is the `<script>` after it);
  `:383-411` (the header); `:9-39` and `:41-67` (its light and dark
  `:root` token blocks).
- **P15.** The mockup hardcodes its kit data, speaks dash's own token
  vocabulary, scopes its tab strip to models versus images rather than
  to the whole page, carries no embark-specific fields, and holds two
  hardcoded copy literals, one of them already wrong.
  `Evidence:` `assets/registry-mockup.html:533-746`
  (`var KITS = [...]`, four kits, six layers each, two tags each, one
  `card_html` each, and exactly the eight fields Requirement 4 names —
  no `spec` key on any kit); `:436-443` (the tab strip); `:445-509`
  (the two panels, including the images empty state at `:467-476`, the
  "not in this registry" label at `:478` and the six-column images
  table header at `:482`); `:748-968` (every builder and interaction
  handler, with the kit-card builder at `:794-832`, the stack bar at
  `:782-792`, the copy button at `:844-865`, the modal builder at
  `:867-934`, the modal close handlers at `:936-937`, the tab handlers
  at `:939-956` and the theme toggle at `:958-968` — **every one of
  these after `:889` moved about thirty lines when the layers table was
  restored (P33), so an anchor carried over from an earlier revision of
  this plan lands inside the layers builder and reads plausibly**);
  `:329-366` and
  `:368-371` (the `.md` and `.card-missing` rules); `:170-197` (the tab
  and section-eyebrow rules); `:30-35`, `:61-64`, `:86-89` and
  `:227-230` (the `--lay-*` tokens and the `.seg.*` rules consuming
  them, the only genuinely new custom properties — every other name its
  CSS uses is one dash already defines at `index.html:9-39`);
  `:407-434` (the page-level header this ticket does not carry over);
  `:438` (the tab count literal `4`, which is **correct against today's
  four-repo catalog** and hardcoded, so it goes stale on the next push)
  and `:470` ("The catalog holds two repositories", **already wrong**
  against four) — the two literals Requirement 16 makes dynamic, for
  those two different reasons.
  `probe:` `grep -c 'serving spec\|asymmetric prefixes\|kit.spec.kind'`
  over the mockup returned `0`, run 2026-09-05, confirming Decision 3
  has already landed in the artifact.
- **P16.** Every live kit carries a `docs` layer holding one
  `README.md`. **This premise inverts an earlier revision's P16**,
  which read "Neither live kit has a `docs` layer" and was true when
  taken and false by review time.
  `probe:` raw `curl` of `/v2/embeddinggemma-q8/manifests/0.1.0` and
  the equivalent for the other three, run 2026-09-05, captured for
  `embeddinggemma-q8`:
  `application/vnd.kitops.modelkit.docs.v1.tar 6656 README.md` and
  `created: 2026-09-05T06:35:01Z`, with six layers rather than five;
  and the config blob's `top keys: ['code', 'docs', 'manifestVersion',
  'model', 'package']`. Across the four kits the docs layer measures
  6656, 7680, 7680 and 6144 bytes and its `README.md` member 4618,
  5636, 5645 and 4448 bytes — `tarinfo.size` and the bytes read, which
  agree; an earlier revision of this premise reported decoded character
  counts (4597, 5611, 5625, 4431) as though they were bytes.
  All four kits were repacked at
  `06:35:01Z`-`06:35:19Z` with kitops 1.15.0. After Decision 3 this is
  the card's only prose source, so a kit without it degrades to
  Requirement 11's note.
- **P17.** This repo has no JS or browser test harness, and dash's
  frontend has no tests at all, so no assertion about what a browser
  draws or how it responds to input has an automated producer. The HTML
  string and the JSON payload are a different matter: rendered in
  Python, both are fully assertable by the existing pytest hook.
  `probe:` a repo-wide search for a project `package.json` and for
  `playwright|vitest|jest|puppeteer`, run 2026-09-05, matched only
  `.claude/plugins/`, `.cache/uv/` and `.graveyard/` paths, none of
  them project code. `Evidence:` `.pre-commit-config.yaml:1-112`
  declares no hook touching `.html`; the four `dash-backend-*` hooks
  (`:89-112`) are scoped to the backend tree alone and the config's own
  comment (`:83-88`) says the frontend needs no hooks because it holds
  no Python.
- **P18.** `tiles.json` already carries a `registry` backend tile whose
  connect block covers the OCI Distribution API, the edge address, the
  htpasswd auth model and a `podman login` example.
  `Evidence:`
  `deployments/applications/services/dash/tiles.json`, the `registry`
  entry; `docs/dash-landing-page.md:46-49` (the `connect` block's
  contract: never a credential value).
- **P19.** `tarfile` and `asyncio` are stdlib and `httpx` is already a
  direct dependency, so the registry I/O path needs no new dependency;
  the markdown render is the one exception (P23).
  `Evidence:`
  `deployments/applications/services/dash/backend/pyproject.toml:6-10`
  (`httpx>=0.28.1`, `starlette`, `uvicorn`); `:22-28` (dev group
  already carrying `respx`, and carrying no `pytest-asyncio` or
  `anyio`). `probe:` `tarfile.open(fileobj=..., mode="r")` read a live
  layer in P4 with no `kit` binary.
- **P20.** embark already reaches this same registry through the edge
  hostname, rendering its own KV credential copy into a Docker-style
  auth file, which is the precedent this ticket's credential wiring
  follows.
  `Evidence:` `deployments/applications/services/embark.hcl:64-72`
  (the `template` rendering `.Data.data.username`/`.Data.data.password`);
  `deployments/applications/services.tf:312` (`embark_registry =
  "registry.lab.orangecluster.nl"`); `:347` (`registry_host`); `:351`
  (`registry_auth_secret =
  vault_kv_secret_v2.embark_registry_credentials.path`).
- **P21 (UNCERTAIN).** One thing about the timings is still
  unconfirmed, and one has been resolved. **Unconfirmed:** every
  measurement in P7, P27, P31 and P39 was taken from the devcontainer,
  not from `radxa-dragon-q6a` where the backend runs; the dash node's
  path to HAProxy and MinIO is a different hop count, so the seconds
  may not transfer and the concurrency plateau may sit elsewhere.
  `probe:` not run from the dash node. **Resolved:** the cold-walk
  wall-clock, which an earlier revision left pending after Decision 3
  cut a blob per digest, has been measured at 1.20 s eight-way and
  4.49 s serial (P7), matching the mockup's ~1.2 s
  (`assets/registry-mockup.html:452-458`). The **registry-side**
  request counts (21 cold, 13 swept) are exact arithmetic and do not
  depend on the vantage point; the **client-side** count of 29 is
  arithmetic too (one extra round trip per blob, P7), but the
  wall-clock cost of those extra hops is a MinIO round trip from the
  dash node and is exactly what this caveat does not cover. Confirm on
  the deployed backend before treating §11 Q1's argument, Requirement
  16's ~60 s interval, or §9's scaling table as final. An earlier
  revision of this premise claimed a request count of 9, which the
  repack invalidated; a count is only exact against the
  catalog and the design it was taken on.
- **P22.** Both tags of every repo resolve to one manifest digest, so a
  repo-tag walk draws each kit twice, and a digest is content-addressed
  so anything derived from it is valid for as long as the digest
  exists.
  `probe:` `Docker-Content-Digest` read from a manifest request on both
  tags of each repo, run 2026-09-05, captured for `embeddinggemma-q8`:
  `0.1.0 -> sha256:a303abc2f44d9e907ed5049c9a001616e2d8e5a7abd8334f2b363326490a6fef`
  and `latest -> sha256:a303abc2f44d9e907ed5049c9a001616e2d8e5a7abd8334f2b363326490a6fef`,
  identical, and the same result for the other three repos.
  `Evidence:` the mockup's own `KITS` array carries `"tags": ["0.1.0",
  "latest"]` against one `digest` per kit
  (`assets/registry-mockup.html:533-746`).
- **P23.** `markdown-it-py` 4.2.0 under preset `js-default` renders GFM
  tables and fenced code and escapes raw HTML by default, so it is a
  sufficient and safe renderer for a model card fed into `innerHTML`.
  `probe:` `uv run --no-project --with 'markdown-it-py==4.2.0' python`,
  run 2026-09-05, captured: `version 4.2.0`, `opts.html False`,
  `table True`, `code True`, `escaped True` for a source containing a
  GFM table, a ```` ```console ```` fence and `<script>x</script>`; and
  the exact output shapes
  `'<pre><code class="language-console">$ x\n</code></pre>\n'` and
  `'<blockquote>\n<p>quote</p>\n</blockquote>\n'`, which match the
  element shapes the mockup's `card_html` strings and its `.md` CSS
  (`assets/registry-mockup.html:329-366`) are
  written against.
- **P24.** `markdown-it-py` ships `py.typed`, so `mypy --strict` needs
  no stub package and `.pre-commit-config.yaml` needs no change.
  `probe:` `os.path.exists(os.path.join(dirname(markdown_it.__file__),
  'py.typed'))` returned `True` under
  `markdown-it-py==4.2.0`, run 2026-09-05. `Evidence:`
  `deployments/applications/services/dash/backend/pyproject.toml:46-48`
  (`[tool.mypy]`, `strict = true`);
  `.pre-commit-config.yaml:101-106` (the mypy hook).
- **P25.** The assembled payload is ~31 KB for four kits, ~26 KB of it
  rendered card HTML, and each card carries eight fields with no
  serving spec.
  `probe:` `json.dumps({"models": KITS, "images": []})` over the
  mockup's own post-Decision-3 `KITS` array, run 2026-09-05, captured
  `payload bytes 31612`, per-kit `keys= ['authors', 'card_html',
  'created', 'description', 'digest', 'layers', 'repo', 'tags']`,
  `layers 6` on every kit, and `card_html` at 5907, 6895, 7221 and 5665
  bytes (25,688 in total; 5886/6870/7201/5648 are the decoded CHARACTER
  counts, which an earlier revision reported as bytes, as P16 did). `Evidence:`
  `assets/registry-mockup.html:882`
  (`card.innerHTML = kit.card_html`, inside the `.md` wrapper built at
  `:881`).
- **P26.** The backend image builds with `uv sync --frozen`, so a new
  dependency that does not reach `uv.lock` fails the image build rather
  than the pre-commit gate.
  `Evidence:`
  `deployments/applications/services/dash/backend/Dockerfile:18`
  (`RUN uv sync --frozen --no-dev`); `:5-10` (the build stage copies
  the whole backend directory, lockfile included).
- **P27.** A manifest `HEAD` returns the digest with a zero-byte body,
  and a full change-detection sweep costs `1 + R + T` = 13 requests and
  0.81 s at eight-way concurrency.
  `probe:` operator-run against the live registry, 2026-09-05:
  `HEAD /v2/embeddinggemma-q8/manifests/latest` returned `200` with
  `Docker-Content-Digest: sha256:a303abc2...`, **0 body bytes** and
  `Content-Length: 1725` (describing the manifest, not the response
  body); and a sweep of catalog plus one tag list per repo plus one
  `HEAD` per tag, run at four concurrency levels (P31), captured
  `13 requests` at `0.81 s` eight-way. The sweep's cost is independent
  of blob sizes, which is what makes a poll affordable.
  Vantage-point caveat as P21.
- **P28.** dash runs exactly one instance, so one SQLite file is the
  whole store, there is exactly one writer, and every viewer shares it.
  `Evidence:` `deployments/applications/services/dash.hcl:5`
  (`group "dash" {`, with no `count` attribute anywhere in the file, so
  Nomad's default of 1 applies); `:6-9` (the `constraint` pinning the
  group to `radxa-dragon-q6a`). `probe:` `grep -n 'count'
  deployments/applications/services/dash.hcl` returned nothing, run
  2026-09-05. This premise is the load-bearing one under §11 Decision
  5, and §9 records that it fails silently if it ever stops holding.
- **P29.** Redis is available with an established per-consumer opt-in
  pattern, and adopting it for dash would cost more than the usual
  per-job entry because a dedicated Vault role replaces
  `nomad-workloads` rather than adding to it.
  `Evidence:` `deployments/infrastructure/database.tf:98-103`
  (`local.redis_cache_consumers = toset([...])`, holding `embark`
  alone today); `:125-135` (the per-consumer
  `vault_database_secret_backend_role`);
  `deployments/infrastructure/machine_roles.tf:322-331` (the
  per-consumer `vault_policy`); `:344-348` (the per-consumer
  `vault_jwt_auth_backend_role`); `:340-343` (the comment recording
  that naming a dedicated role REPLACES `nomad-workloads`, so a caller
  needing its own KV secrets must keep that policy attached too);
  `:312` (dash's existing `token_policies`, which is where a Redis
  policy would have to be folded);
  `deployments/applications/services/dash.hcl:89-91` (dash's single
  `vault { role = "dash" }` stanza);
  `deployments/infrastructure/services.tf:521-531` (the opt-in
  contract, `redis/creds/cache-<job>` minted per render).
- **P30.** An OCI index carries no `layers`, so an images row for a
  multi-arch tag has no size to sum and must not be built as though it
  did.
  `Evidence:` the P2 probe's captured `top-level keys: ['manifests',
  'mediaType', 'schemaVersion']` for
  `docker.io/library/registry:3.1.1` — no `layers` key, no `config`
  key, and the child entries carry `digest`/`platform`/`size` for each
  platform's own manifest rather than for layers. A single-architecture
  image manifest does carry `config` and `layers`, which is the branch
  Requirement 10's size column reads. Both branches ship tested against
  fixtures alone (§9), since the registry holds no image (P1).
- **P31.** The walk's cost is round-trip latency, not registry work, so
  concurrency buys almost 3x and plateaus by eight.
  `probe:` operator-run, the same 13-request sweep at four concurrency
  levels against the live registry, best of two runs each, 2026-09-05:

  | concurrency | requests | seconds | ms per request |
  |---|---|---|---|
  | 1 | 13 | 2.44 | 188 |
  | 4 | 13 | 0.86 | 66 |
  | 8 | 13 | 0.81 | 62 |
  | 16 | 13 | 0.77 | 59 |

  Four-way is a 2.8x win over serial; the curve is flat from eight
  onward, so something upstream — HAProxy, or the registry itself —
  serializes past that. Eight is the bound Requirement 8 specifies:
  past it there is nothing measurable to gain, and the registry is a
  shared job whose own jobspec comment calls its reservation
  deliberately small
  (`deployments/applications/services/registry.hcl:195-204`). At
  eight-way the sweep sustains roughly 16 requests per second, which is
  the rate §9's scaling table extrapolates from. Vantage-point caveat
  as P21.
- **P32.** The backend is already async and its tests already drive an
  async route from a sync test, so concurrency needs no new execution
  model and no new dev dependency.
  `Evidence:`
  `deployments/applications/services/dash/backend/src/dash_app/main.py:56`
  (`async def status_endpoint`), mounted at `:77-79`;
  `deployments/applications/services/dash/backend/tests/test_main.py:6`
  (`from starlette.testclient import TestClient`) and `:107-109`
  (`client = TestClient(app)` then `client.get("/api/status")`), which
  runs the event loop internally;
  `deployments/applications/services/dash/backend/pyproject.toml:22-28`
  (the dev group: `mypy`, `pytest`, `respx`, `ruff` — no
  `pytest-asyncio`, no `anyio`). A direct unit test of an async helper
  uses `asyncio.run(...)`, stdlib. `probe:` `grep -rn 'async def\|await
  '` over the backend `src/` and `tests/` matched only `main.py:56`,
  run 2026-09-05, so this is the first async I/O in the tree.
- **P33.** The mockup's modal builds three sections — the rendered
  card, the layers table, then the pull commands — and the CSS that
  table needs is selected again, so nothing in the file is orphaned and
  the section order matches the one the operator stated. **This premise
  inverts an earlier revision's P33**, which read "no layers table,
  while the CSS that table needs survives unused" and was true when
  taken and false by review time; §11 Q9 records the restoration that
  made it false.
  `Evidence:` `assets/registry-mockup.html:867-934`
  (`openCard`: `mBody.textContent = ''` at `:877`, the card pane at
  `:879-887` with its docs-less fallback at `:884-887`, the layers
  table at `:889-917`, the command rows at `:919-931`, and
  `modal.showModal()` at `:933`); `:891` (`var t = el('table',
  'layers')`); `:312-324` (the `.layers`, `.layers th`, `.layers td`,
  `.layers .path`, `.layers .dg`, `.layers .sz`, `.swatch` and
  `.layer-wrap` rules). `probe:` `grep -n 'layer-wrap\|swatch'` over
  the 974-line `assets/registry-mockup.html`, re-run 2026-09-05,
  captured four lines — `323` and `324` in the CSS, **`890`
  (`el('div', 'layer-wrap')`) and `903` (`el('span', 'swatch')`) in the
  builder** — so the CSS is live rather than dead. Two consequences the
  rest of this plan depends on: the modal order Requirement 14 ports is
  card → layers → commands, and **every JS anchor after `:889` sits
  about thirty lines lower than it did before the restoration**, which
  is why P15, P25, Requirements 14 and 15 and §9 were all re-pointed
  and why an implementer should re-resolve rather than trust an anchor
  that looks plausible.
- **P34.** dash has no host volume today; every
  `nomad_dynamic_host_volume` in this repo lives in one file and shares
  one shape; the closest precedent is already pinned to dash's node;
  the deployer's Nomad policy already grants the mount; and a
  cross-root volume/job pair carries no `depends_on`.
  `probe:` `grep -rn 'nomad_dynamic_host_volume' deployments/`, run
  2026-09-05, matched eleven resource declarations, all in
  `deployments/infrastructure/services.tf` — `postgres` `:2`,
  `minio_data` `:22`, `memex_data` `:42`, `hermes_data` `:62`,
  `prometheus_data` `:82`, `grafana_data` `:102`, `loki_data` `:122`,
  `tempo_data` `:145`, `embark_data` `:173`, `nats_data` `:193`,
  `acme_lego_state` `:220` — and none in
  `deployments/applications/`. `grep -n 'volume'
  deployments/applications/services/dash.hcl` matched only the podman
  bind mount at `:64-66`, so the job has neither a `volume` stanza nor
  a `volume_mount`. `Evidence:`
  `deployments/infrastructure/services.tf:193-211` (`nats_data`: same
  `plugin_id = "mkdir"`, `node_pool = "default"`, capacity pair,
  hostname `constraint` and single `single-node-writer`/`file-system`
  `capability`, and constrained to `radxa-dragon-q6a`, which is the
  node `deployments/applications/services/dash.hcl:6-9` pins dash to);
  `deployments/applications/services/tempo.hcl:30-35` and `:101-104`
  (the group `volume` plus task `volume_mount` pair to copy);
  `deployments/infrastructure/machine_roles.tf:115-117`
  (`host_volume "*" { capabilities = ["mount-readwrite"] }`) with
  `:108-114` recording that it is deliberately unscoped by name, so
  `dash_data` needs no ACL change — and that the comment saying so
  lives inside `rules_hcl`'s heredoc, which §6 forbids editing;
  `deployments/applications/services.tf:333` (`nomad_job "embark"`)
  against `deployments/infrastructure/services.tf:173`
  (`embark_data`) with no `depends_on` between them, the same shape
  `memex`, `hermes`, `loki` and `tempo` use, and
  `deployments/infrastructure/services.tf:501-502` stating that the two
  roots hold separate state with no link;
  `deployments/infrastructure/services.tf:170-172` (a host volume does
  not follow its job, so the two constraints must agree).
- **P35.** A `cards` row is keyed by a manifest digest and a digest is
  content-addressed, so the row can never be invalidated — only evicted
  when nothing references it. This is what makes persistence correct
  with no expiry and turns cold start into a once-ever cost.
  `Evidence:` P22 (both tags of every repo resolve to one digest, and
  the digest names its own bytes); §4's digest-keyed cache bullet,
  which already carries this reasoning for the in-memory case —
  persistence changes where the row lives, not whether it can go stale.
  The schema follows from it: `repos(name PK, first_seen, last_seen,
  last_changed)`, `tags(repo, tag, digest, checked_at, PRIMARY KEY
  (repo, tag))`, `cards(digest PK, kitfile_json, card_html,
  fetched_at)`. `tags.digest` doubles as the stored ETag P39 sends.
- **P36.** stdlib `sqlite3` is present in the runtime image, has no
  async API, and **one connection cannot be shared across the workers
  this ticket's walk uses: eight concurrent writes on a shared
  connection fail in most trials, sometimes by crashing the
  interpreter, while a connection opened per call is clean in every
  trial.** `threadsafety 3` licenses concurrent *reads*, not this.
  **The resolution stated by an earlier revision of this premise —
  that `check_same_thread=False` is what makes sharing safe — is
  false**, and §11 Q12 records the fork it opened and how the operator
  settled it.
  `probe:` `docker run python:3.12-slim` in a throwaway container,
  discarded after the run, 2026-09-05, captured: `python 3.12.14`,
  `sqlite3 module OK, lib 3.46.1`, `threadsafety 3`,
  `has async api none`; `shared conn, check_same_thread default ->
  RAISES ProgrammingError: SQLite objects created in a thread can only
  be used in that same thread`; and `to_thread + 1-row SELECT: 26.2
  us/call   inline SELECT: 2.6 us/call` over 2000 iterations each, with
  the default executor at 15 workers, which is more than the eight-way
  gather needs.
  `probe:` the four concurrency shapes, each in its own subprocess
  against a fresh database every trial, `python:3.12`. Operator's run,
  20 trials each: 8 concurrent **writes** on one shared connection
  (`check_same_thread=False`) — **6 OK, 2 `InterfaceError: bad
  parameter or other API misuse`, 12 hard crashes (exit 139,
  `SIGSEGV`)**; the same plus `isolation_level=None` — 16 OK, **4
  crashes**; **connection-per-call — 20 OK**; 8 concurrent **reads** on
  one shared connection — 20 OK. Re-run here on `aarch64` (`python
  3.12.14`, `sqlite lib 3.46.1`, `threadsafety 3`), 20 trials of every
  shape and 40 more of the two shared-write shapes: shared connection —
  **0 of 60 OK**, 43 `InterfaceError: bad parameter or other API
  misuse`, 11 transaction-state errors, 3 `SystemError: error return
  without exception set`, and **3 runs that raised nothing and wrote 5,
  6 and 6 of the 8 rows**; shared connection plus
  `isolation_level=None` — 60 of 60 OK; **connection-per-call — 20 of
  20 OK with all eight rows present**; 8 concurrent reads on a shared
  connection — 20 of 20 without an exception. No crash reproduced on
  this hardware. **The crash mode is hardware-dependent; the failure is
  not**, and neither is the silent partial write, which this run hit
  three times and no `try`/`except` would have caught. `Evidence:`
  `deployments/applications/services/dash/backend/Dockerfile:5`
  (`FROM python:3.12-slim`) and `:20` (the same base for the runtime
  stage), so the probe image is the deployed one;
  `deployments/applications/services/dash/backend/src/dash_app/main.py:56`
  (`async def status_endpoint`), which shares the process a `SIGSEGV`
  would end (P37).
- **P37.** `/api/status` and `/api/registry` share one event loop, and
  the status path already blocks it, so a second blocking caller makes
  a contended resource worse rather than introducing a new problem.
  `Evidence:`
  `deployments/applications/services/dash/backend/src/dash_app/main.py:56`
  (`async def status_endpoint`) calling `fetch_tile_states(config,
  tiles)` synchronously at `:58`, which reaches the sync
  `httpx.Client` at
  `deployments/applications/services/dash/backend/src/dash_app/_http.py:42-43`;
  both routes are mounted on one `Starlette(routes=routes)`
  (`main.py:77-80`) served by one uvicorn process (`:90`);
  `deployments/applications/services/dash/frontend/index.html:588`
  (`setInterval(refresh, 15000)`), the loop that pays for it.
- **P38.** oauth2-proxy guards every upstream because this repo's
  jobspec sets no skip-auth key of any kind, and the one setting whose
  name contains `SKIP` is unrelated to authorization.
  `probe:` `grep -rn 'SKIP_AUTH\|skip_auth\|skip-auth' deployments/
  docs/`, run 2026-09-05, returned nothing.
  `awk 'NR>=59 && NR<=73' | grep -c '^\s*OAUTH2_PROXY_'` over
  `deployments/infrastructure/services/oauth2-proxy.hcl` returned `13`,
  and the thirteen keys are `PROVIDER`, `OIDC_ISSUER_URL`, `CLIENT_ID`,
  `CLIENT_SECRET`, `COOKIE_SECRET`, `COOKIE_SECURE`, `REDIRECT_URL`,
  `EMAIL_DOMAINS`, `UPSTREAMS`, `OIDC_EMAIL_CLAIM`, `SCOPE`,
  `SKIP_PROVIDER_BUTTON` and `HTTP_ADDRESS` — no `SKIP_AUTH_ROUTES`, no
  `SKIP_AUTH_REGEX`, no `SKIP_AUTH_PREFLIGHT`. `Evidence:`
  `deployments/infrastructure/services/oauth2-proxy.hcl:1-4` (the job's
  own description: an OIDC forward-gate for dash, any authenticated
  user let through); `:68` (`OAUTH2_PROXY_UPSTREAMS`, the two-value
  string Requirement 18 extends); `:71`
  (`OAUTH2_PROXY_SKIP_PROVIDER_BUTTON="false"`, the near-miss a
  substring check would trip on, pinned `false` for the reason at
  `:18`).
- **P39.** A manifest carries an `ETag` equal to its
  `Docker-Content-Digest`, the registry honors `If-None-Match` with a
  `304` and a zero-byte body, the saving is time rather than requests,
  and the catalog offers no conditional form at all.
  `probe:` operator-run against the live registry, 2026-09-05: a
  manifest read returned `ETag:
  "sha256:a303abc2f44d9e907ed5049c9a001616e2d8e5a7abd8334f2b363326490a6fef"`,
  identical to its `Docker-Content-Digest`; a conditional `HEAD` and a
  conditional `GET` carrying that value both returned **304** with a
  zero-byte body; medians over six runs each were **147 ms**
  conditional against **181 ms** for an unconditional `HEAD`; and
  `GET /v2/_catalog` returned no `ETag`, no `Last-Modified` and no
  `Link` header. `Evidence:` the sweep's shape is `1 + R + T` (P27) and
  a conditional request is still a request, so the count is unchanged
  at 13 — the conditional form changes what each of the twelve manifest
  asks costs, not how many there are. Vantage-point caveat as P21.
- **P40.** Rendering one live-sized `README.md` with `markdown-it-py`
  costs about 4 ms of event-loop time, which is affordable only because
  a digest is rendered once ever and then persisted.
  `probe:` `docker run python:3.12-slim` in a throwaway container with
  `markdown-it-py==4.2.0`, 2026-09-05, over a 4,914-byte source
  (inside P16's measured 4448-5645 byte range) carrying GFM tables, a
  `console` fence, a blockquote and a list, 200 iterations, captured:
  `html bytes: 8802`, `html opt: False`, `render: 4.12 ms per README`,
  `four READMEs: 16.46 ms`. `Evidence:` P23 (the same preset and the
  same escape behavior); Requirement 23 (the render is persisted, so
  the cost is paid once per digest); §9's scaling table (250 digests
  would be about a second of blocked loop, which is where §11 Decision
  8's `asyncio.to_thread` escape hatch applies).
- **P41.** A plain (non-index) OCI image manifest's config blob is a
  few KB of raw JSON carrying `architecture`, `os` and `created`, which
  is what produces the `arch` and `pushed` columns of the mockup's
  images table; an index carries no such blob, which is why a
  multi-arch row has neither field.
  `probe:` `docker.io/library/registry:3.1.1` with an anonymous pull
  token and the OCI/Docker `Accept` set, run 2026-09-05: the tag
  resolves to `application/vnd.oci.image.index.v1+json` (P2, P30); its
  `arm64` child manifest
  (`sha256:bc68ba48dae0e0423bb885c8d07d20c3210febbe996d38d54d32c574fda690ae`)
  carries `config mediaType application/vnd.oci.image.config.v1+json`
  at **3611 bytes** and five `layers` summing 18,823,580 bytes; and
  that config blob, fetched, parsed with `json.loads` and captured:
  `config top keys: ['architecture', 'config', 'created', 'history',
  'os', 'rootfs', 'variant']`, `architecture = 'arm64'`, `os =
  'linux'`, `created = '2026-06-22T19:54:07.889802725Z'`, `variant =
  'v8'`. `Evidence:` `assets/registry-mockup.html:482` (the six-column
  header this fills) and `:504-508` (the mockup's own footnote, which
  says an image row costs one config blob more than a ModelKit row
  does); P5 (the blob GET redirects, so this fetch follows the
  redirect like every other); §11 Q2's amendment (the fetch is in
  scope; index resolution is not).
