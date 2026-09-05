---
epic = "openviking"
depends_on = ["U7-upgrade-bifrost-2x"]
priority = 25
summary = """Stand up OpenViking on the cluster: a derived image layering ov-postgres onto ghcr.io/volcengine/openviking pinned at v0.4.17.1, pgvector in the existing `openviking` Postgres database, the existing `openviking` MinIO bucket for AGFS blobs, embedding and rerank through Bifrost as embark/embedding at dimension 768 and embark/reranker, VLM through Bifrost's ollama provider, and browser auth via a dedicated Vault OIDC client whose ID token oauth2-proxy forwards to an OpenViking running auth_mode=oidc. Rerank through Bifrost requires the gateway at 2.0.0 or newer, which is why this ticket depends on U7-upgrade-bifrost-2x: the deployed 1.6.7 rejects the plain-string documents every OpenAI-compatible OpenViking rerank client sends. One of the operator's stated requirements does not survive contact with the code and is raised as a fork rather than settled: MinIO workload identity is unreachable, because OpenViking's S3 config validator demands a static access_key/secret_key pair and the Rust client hard-codes session_token=None."""
tags = ["openviking", "postgres", "pgvector", "minio", "bifrost", "embark", "rerank", "oidc", "oauth2-proxy", "vault", "nomad", "terraform", "haproxy", "docker"]
premise = { Q1 = "MinIO workload identity is unreachable at OpenViking v0.4.17.1, so blob storage uses the existing openviking MinIO user's static key from secret/data/default/openviking/minio and NO minio_iam_policy named openviking is created; the premise this rests on is that access_key and secret_key are mandatory for backend s3, session_token is a forbidden extra key, backend is restricted to local|s3|memory, and the Rust client passes session_token=None, so no config route reaches the SDK default chain. A deliberate step back from the cluster's keyless direction, forced rather than chosen", Q2 = "OpenViking's openai and cohere rerank clients each build their own flat body and both send documents as a list of plain strings, which Bifrost 1.6.7 rejects with a flat 400 before the request reaches embark; the litellm client hands the same list to a third-party library whose wire output was not measured, and the vikingdb client does wrap each document as an object but signs for Volcengine's own host and cannot be aimed at Bifrost. Bifrost 2.0.0 accepts a bare string in RerankDocument.UnmarshalJSON, which removes the incompatibility, so the operator resolved this fork by upgrading the gateway rather than bypassing it", Q3 = "OpenViking's auth_mode selects exactly one plugin with no API-key fallback, and Vault's lab provider offers only the authorization_code grant, so nothing headless can authenticate; this ticket therefore ships browser access through oauth2-proxy alone and defers agent access to its own ticket, for which auth_mode trusted is the named starting point", Q4 = "the openviking schema is adopted as it stands because ov_collections and ov_indexes are empty and already carry ov-postgres v0.2.0's column shapes with its three helper functions installed, so first run finds what it would have created; the five dbg_fts* schemas are dropped by hand in an operator-run step and never from Terraform, so no apply carries a live DROP against the vector store's database", Q5 = "vlm is left unset in the first deployment because no catalogued vision model has been chosen and Bifrost 403s an uncatalogued model for a provider whatever the virtual key allows; OpenViking's VLM config validates only when one of its fields is set, so an absent block is legal", Q7 = "R15's static half becomes measurable in this ticket via scripts/check_openviking_config.py and its pre-commit hooks, which sections 7 and 8 already name conditionally so no bound section changes; its runtime half is scored by an explicitly LABELLED proxy whose eval row must state that it does not measure whether a live Vault token is accepted, whether a foreign audience is refused, or whether any call reaches embark or Bifrost" }
measured_against = { Q1 = { kind = "agent-decision", version = "2026-09-05", ref = "resolution (a) of section 11 Q1; decided by the coordinating agent under an explicit grant of full loop control from JasperHG90, operator offline", note = "falsified if upstream makes access_key/secret_key optional and threads an STS session token, or if any config route to the Rust default credential chain is found; either would make the keyless form reachable and this decision wrong" }, Q2 = { kind = "probe", version = "OpenViking v0.4.17.1 source, live Bifrost 1.6.7 on radxa, Bifrost transports/v2.0.0 source", ref = "openviking/models/rerank/openai_rerank.py lines 75-102, cohere_rerank.py lines 64-70, volcengine_rerank.py lines 107 and 122; POST /v1/rerank against 192.168.2.50 port 8080; core/schemas/rerank.go lines 26-41 at tag transports/v2.0.0 against the same file at transports/v1.6.7", note = "object documents 200, string documents 400 Invalid request payload with empty routing_info on 1.6.7; transports/v2.0.0 adds RerankDocument.UnmarshalJSON accepting a bare string, which transports/v1.6.7 has not" }, Q3 = { kind = "agent-decision", version = "2026-09-05", ref = "resolution (a) of section 11 Q3; decided by the coordinating agent under an explicit grant of full loop control from JasperHG90, operator offline", note = "falsified if OpenViking gains a second concurrent auth path or Vault's lab provider gains a non-interactive grant, either of which would let agents in without a follow-up ticket" }, Q4 = { kind = "agent-decision", version = "2026-09-05", ref = "resolution of section 11 Q4; decided by the coordinating agent under an explicit grant of full loop control from JasperHG90, operator offline", note = "falsified if the registry tables gain rows before deployment or if ov-postgres changes its DDL so the existing columns no longer match, either of which turns adoption from a no-op into a migration" }, Q5 = { kind = "agent-decision", version = "2026-09-05", ref = "resolution of section 11 Q5; decided by the coordinating agent under an explicit grant of full loop control from JasperHG90, operator offline", note = "falsified if a vision model is added to Bifrost's ollama catalog and chosen, which turns this from a deferral into an omission" }, Q7 = { kind = "agent-decision", version = "2026-09-05", ref = "resolution widen-surface plus declared-proxy of section 11 Q7; decided by the coordinating agent under an explicit grant of full loop control from JasperHG90, operator offline", note = "falsified if the repo gains a harness that exercises a deployed service, which would make the runtime half directly measurable and the declared proxy an unnecessary downgrade; also violated, not falsified, if the eval row ships without the label" } }
---

# Ticket: OV1-openviking-service

## 1. Title

Deploy OpenViking on the cluster: pgvector-backed vector store in the
existing `openviking` Postgres database, AGFS blobs in the existing
`openviking` MinIO bucket, embedding and rerank through Bifrost against
embark's served models, VLM through Bifrost, and browser authentication
through a dedicated Vault OIDC client fronted by its own oauth2-proxy.
Gated on `U7-upgrade-bifrost-2x`, without which the rerank path cannot
work.

## 2. Size / Effort

**L.** Two Terraform roots, two new jobspecs, a derived container image,
a new Vault OIDC client, a new edge route, and a docs page. The size is
driven by breadth, not depth: no single piece is hard, but the change
spans image, storage, secrets, identity, job, edge and docs. Two things
add to it: one of the operator's stated requirements (MinIO through
workload identity) is contradicted by upstream code and must be settled
before any of it lands, and the whole ticket is gated behind
`U7-upgrade-bifrost-2x`, without which the rerank path cannot work.

## 3. Triggered by

Operator request: add OpenViking to the stack, with Postgres as the
vector store (via the operator's own `ov-postgres` extension), MinIO as
blob storage through workload identity, embark for embedding and rerank
through Bifrost, ollama for VLM through Bifrost, a Bifrost API key
provisioned by Terraform, and OAuth authentication backed by Vault.
Placement chosen by the operator: radxa (192.168.2.50), because every
embed / rerank / VLM call then becomes a loopback hop to Bifrost.

## 4. Context

**Already provisioned, unused.** The Postgres database, role and `vector`
extension exist in Terraform (`deployments/applications/database.tf:8`
and `:34-38`) and on the live server. The MinIO bucket and its writer
user exist (`deployments/applications/storage.tf:63-68`). Nothing
consumes either: there is no `nomad_job` for OpenViking, no Vault KV
entry holding its database or MinIO credentials, and no MinIO policy
named `openviking`.

**Live state, measured 2026-09-05.** Bucket `openviking` exists (created
2026-08-30) and is empty. `mc admin policy list` returns
`openviking_read_write` and `openviking_read_only` (emitted by
`module.buckets`, `deployments/applications/storage.tf:178-189`) but no
policy named exactly `openviking`, which is the name MinIO claim mode
would need. The database carries schemas `openviking`, `public` and
`dbg_fts` through `dbg_fts5`, and tables `openviking.ov_collections` and
`openviking.ov_indexes`, on PostgreSQL 18.3 with pgvector 0.8.2.

**Bifrost already serves embark.**
`deployments/applications/services/bifrost.hcl:154-176` declares embark
as a custom OpenAI-compatible provider reachable as `embark/embedding`
and `embark/reranker`; served names come from
`deployments/applications/services/embark/models.json:2-3`. That file's
own comment (`deployments/applications/services/bifrost.hcl:107-112`)
records the measured rerank wire-format gotcha this ticket runs into.

**Patterns this change copies.** Derived image:
`deployments/applications/services/embark/Dockerfile.embark:40-42` layers
a pip install onto a published base, with a sibling justfile deriving
both tags from the one image line in `services.tf`
(`deployments/applications/services/embark/justfile:15-17`,
`deployments/applications/services.tf:345`). MinIO workload identity:
`deployments/applications/storage.tf:104-165` plus the `credential_process`
helper at `deployments/applications/services/loki.hcl:107-140`, documented
at `docs/workload-identity.md:405-459`. Bifrost virtual key in Terraform:
`deployments/applications/services.tf:621-646`, keyed into Vault under the
consumer's own prefix (`deployments/applications/secrets.tf:201-220`).
OIDC client: `deployments/infrastructure/oidc.tf:424-444`, with the
provider allow-list at `:92-107`. Second oauth2-proxy:
`deployments/infrastructure/services/oauth2-proxy-registry-ui.hcl:1-24`,
wired at `deployments/infrastructure/services.tf:548-564`. Edge route:
`deployments/infrastructure/services/haproxy.hcl:98-122` and `:180-184`.

**What is wrong or missing.** Three things the operator asked for do not
hold against the code as deployed today. One is fatal and becomes a fork
(1); one is fixed by a dependency (2); one narrows the scope (3):

1. *MinIO through workload identity is unreachable.* OpenViking's
   `S3Config.validate_config` requires `bucket`, `endpoint`, `region`,
   `access_key` and `secret_key`, and `AGFSConfig`'s model validator
   calls it whenever `backend == "s3"`. The Rust client's
   default-credential-chain branch is therefore never reached, and even
   if it were, it builds `Credentials::new(ak, sk, None, ...)` with no
   session token, which MinIO STS credentials require. See P1.
2. *Rerank cannot go through Bifrost 1.6.7.* The three OpenAI-compatible
   OpenViking rerank clients send `documents` as plain strings, and the
   deployed gateway's rerank schema requires objects. Bifrost 2.0.0
   accepts both, which is why this ticket depends on
   `U7-upgrade-bifrost-2x` rather than bypassing the gateway. See P2 and
   P20.
3. *`auth_mode` selects exactly one plugin.* There is no API-key fallback
   under `oidc`, and Vault's lab provider issues ID tokens only through
   an interactive `authorization_code` flow, so headless LAN agents have
   no way in. See P3 and P8.

**Gate gap.** `scripts/check_oauth2_proxy_guard.py:22-25` hard-codes the
two existing proxy jobspecs, and the hook that runs it is scoped to those
same two filenames (`.pre-commit-config.yaml:75-83`). A third proxy added
by this ticket would be unguarded by default.

**Placement is unverified.** radxa already runs bifrost, hermes, dash,
registry-ui, nats, redis, prometheus, two oauth2-proxies and two backup
jobs. Nomad's API refused an unauthenticated read from this session
(HTTP 403), so headroom was not measured. See P10.

## 5. Non-goals / out of scope

- No change to embark, to the models embark serves, or to Bifrost's own
  jobspec. Bifrost's version bump lives in `U7-upgrade-bifrost-2x`, which
  this ticket depends on rather than performs; the only Bifrost-side
  change here is the new virtual key.
- No rerank bypass. Rerank stays on the gateway (R5). Q2's option (a),
  pointing OpenViking straight at embark, is recorded as a fallback and
  is out of scope unless U7 is abandoned.
- No headless / machine authentication to OpenViking. Agent access is
  deferred (Q3).
- No `openviking.tf` in either Terraform root, and no new `.tf` file at
  all: this feature spans existing subsystems and is written across
  their files (`.claude/rules/terraform-file-layout.md`).
- No migration of the existing `openviking.ov_*` tables or the `dbg_fts*`
  schemas, and no drop of either, until Q4 is settled.
- No Vault dynamic database credentials. OpenViking gets the same static
  role password Bifrost has
  (`deployments/applications/secrets.tf:224-231`); the dynamic-credential
  cutover is R7's ticket, not this one.
- No OpenViking native OAuth 2.1 (`oauth.enabled`). It is layered on
  `AuthMode.API_KEY` and its identities always originate from an
  OpenViking API key, so it cannot be backed by Vault. See P9.
- No ingestion of content, no collections seeded, no evaluation of
  retrieval quality.
- No rotation of the three live credentials the operator pasted in
  plaintext; that is named in Q9 as an operator action, and no value from
  that message appears anywhere in this plan or its implementation.

## 6. Requirements & restrictions

- **R1.** Placement precondition, not an assumption: confirm CPU and
  memory headroom on `radxa-dragon-q6a` before writing the constraint.
  If it does not fit, fall back to hostname `ubuntu` (192.168.2.47, the
  rpi4b), the node loki, tempo and registry already use
  (`deployments/applications/services/loki.hcl:7-10`). Moving the job
  moves its oauth2-proxy with it (the upstream is loopback), moves the
  host volume's constraint, and changes which node the infra firewall
  rule opens 4182 on. It needs NO application-side firewall change: under
  R5 OpenViking dials only Bifrost, whose rule already admits the whole
  `192.168.0.0/16` to port 8080
  (`deployments/applications/services.tf:126-133`). Adding an entry to the
  embark rule would open a port to a node with no reason to reach it, and
  section 9 records that these provisioners are ONE-WAY, so that entry
  would outlive any `terraform destroy` and need a manual `ufw delete`.
- **R2.** The image is DERIVED, not the upstream one, and its base is
  PINNED. `ov-postgres` and `psycopg[binary,pool]` are absent from the
  upstream image and must be layered on, using the system pip with
  `--target` into the uv venv, exactly as
  `deployments/applications/services/embark/Dockerfile.embark:40-42` does.
  Two lines are written once, both in
  `deployments/applications/services.tf` beside embark's `embark_image`
  (`:345`): `openviking_base_image` holding
  `ghcr.io/volcengine/openviking:v0.4.17.1`, and `openviking_image`
  holding the derived tag. The justfile derives BOTH from those lines, the
  way embark's derives its base from its one tag
  (`deployments/applications/services/embark/justfile:15-31`), so the tree
  the premises were read at and the tree the build consumes cannot drift.
  `:latest` is NOT a pin: it and `:v0.4.17.1` resolve to one index digest
  today and need not tomorrow. See P21.
- **R3.** `storage.vectordb.backend` is
  `ov_postgres.adapter.PgVectorCollectionAdapter`, and `custom_params`
  carries only keys `ov-postgres` declares: `dsn`, `schema`,
  `table_prefix`, `index_method`, `index_options`, `create_extension`,
  `iterative_scan`, `distance`, `keyword_fields`, `text_search_config`,
  `tz_policy`, `min_pool_size`, `max_pool_size`, `connect_timeout`,
  `application_name`. Both that model and `VectorDBBackendConfig` forbid
  extra keys, so an invented key is a hard startup failure. See P4.
- **R4.** `embedding.dense.dimension` is **768**, measured against
  embark's `embeddinggemma-q8` through Bifrost. Producer: the literal in
  the ov.conf template in `deployments/applications/services/openviking.hcl`
  (section 7), asserted statically by
  `scripts/check_openviking_config.py` if Q7 resolves to widen-surface.
  A wrong dimension corrupts the collection. See P5.
- **R5.** Rerank goes THROUGH Bifrost, as the operator asked:
  `provider: "openai"`, `api_base` set to Bifrost's full rerank URL on
  192.168.2.50 port 8080, `model` `"embark/reranker"` (the served name at
  `deployments/applications/services/embark/models.json:3` behind the
  provider prefix `deployments/applications/services/bifrost.hcl:102-105`
  documents), and `api_key` read from OpenViking's own copy of the Bifrost
  virtual key. This requires Bifrost 2.0.0 or newer and is why this ticket
  declares `depends_on = ["U7-upgrade-bifrost-2x"]`: the deployed 1.6.7
  rejects the plain-string `documents` OpenViking sends. Implementing OV1
  against 1.6.7 yields a service whose rerank path 400s on every call. See
  P2, P20 and Q2. Because rerank stays on the gateway, this ticket needs
  no direct radxa-to-embark path, and the rule and intent comment at
  `deployments/applications/services.tf:102-114` stay untouched.
- **R6.** Every secret the job reads lives under
  `secret/data/default/openviking/*`.
  The `nomad-workloads` Vault role grants a job read only under its own
  `<namespace>/<job_id>/` prefix
  (`bootstrap/roles/nomad_server/templates/vault_nomad_workloads.hcl.j2:1-7`),
  so the Bifrost virtual key, the Postgres password and the MinIO
  credential are all COPIES under OpenViking's prefix, following
  `deployments/applications/secrets.tf:116-128`. Because R5 keeps rerank
  on the gateway, OpenViking needs no copy of embark's own API key: the
  Bifrost virtual key is the only model credential it holds.
- **R7.** The Bifrost virtual key is a `bifrost_virtual_key` resource in
  `deployments/applications/services.tf`, depending on
  `null_resource.bifrost_ready` (`:578-607`), with `provider_configs` in
  ALPHABETICAL order by `provider` (`:615-620`), and its value written to
  Vault under OpenViking's prefix as
  `deployments/applications/secrets.tf:201-208` does for hermes.
- **R8.** Browser authentication uses a DEDICATED confidential Vault OIDC
  client named `openviking`, not the shared `oauth2_proxy` client at
  `deployments/infrastructure/oidc.tf:424-437`. Reason: OpenViking
  validates `aud` and nothing else about the caller, so reusing the
  shared client would make every live dash or registry-ui session token a
  valid OpenViking credential. The client's `client_id` is both
  oauth2-proxy's `OAUTH2_PROXY_CLIENT_ID` and OpenViking's `audience`.
  Its id must be appended to `local.oidc_provider_client_ids`
  (`deployments/infrastructure/oidc.tf:99-107`) and registered against
  the `lab` key with a `vault_identity_oidc_key_allowed_client_id`
  (`:441-444`). Who is allowed in is `assignments = ["allow_all"]`, branch
  3 of the repo's own procedure (`docs/vault-human-auth.md:288-292`),
  matching the sibling client at
  `deployments/infrastructure/oidc.tf:433`. A client carrying no
  assignment authorizes nobody, and it fails AFTER the redirect.
- **R8a.** The `audience` value has a named producer. Vault generates the
  client_id in the INFRASTRUCTURE root while OpenViking's config lives in
  the APPLICATIONS root, and R6 forbids the job from reading the proxy's
  KV prefix, so neither root supplies it by itself. The applications root
  reads it back over the same cross-root channel memex already uses,
  `data "vault_identity_oidc_client_creds"`
  (`deployments/applications/services.tf:33-39`), and carries it into
  ov.conf as a `templatefile` variable. `oidc.issuer` comes from
  `local.vault_oidc_issuer` (`deployments/applications/services.tf:24-31`),
  byte-identical to the `issuer` the live discovery document advertises
  (P3); `oidc.jwks_uri` may be set explicitly from the same local rather
  than left to discovery, which is the escape hatch P22 describes.
- **R9.** The new proxy sets `OAUTH2_PROXY_PASS_AUTHORIZATION_HEADER="true"`
  and `OAUTH2_PROXY_COOKIE_EXPIRE` equal to the client's `id_token_ttl`
  (3600s). Vault advertises no `refresh_token` grant, so
  `--cookie-refresh` cannot work and a longer cookie life would leave the
  session valid while the forwarded ID token is expired, which OpenViking
  answers with a 401 and no re-login. See P3 and P6.
- **R10.** The OIDC `identity` block is omitted. OpenViking's defaults map
  `account_id` to the fixed string `default` and `user_id` to the `sub`
  claim, and the OIDC plugin never calls `map_role` at all: role is
  always `USER`. Omitting the block therefore avoids the Vault `groups`
  array entirely, and the proxy requests scope `openid` only, matching
  `deployments/infrastructure/services/oauth2-proxy-registry-ui.hcl:70-71`.
  See P7.
- **R11.** No `.tf` file is added to either root, and no block is named
  after this feature: the MinIO policy goes in `storage.tf`, the Vault KV
  writes in `secrets.tf`, the jobs and firewall rules in `services.tf`,
  the OIDC client in `oidc.tf` (`.claude/rules/terraform-file-layout.md`).
- **R12.** Firewall entries follow the single-caller shape already used
  for dash (`deployments/applications/services.tf:140-144`): OpenViking's
  1933 admits only the node its proxy runs on, and the infra
  `oauth2_proxy` rule (`deployments/infrastructure/services.tf:384-396`)
  gains 4182 for HAProxy's node alone. Both are ONE-WAY: removing an
  entry later leaves the rule live on the host
  (`deployments/applications/services.tf:148-158`).
- **R13.** The third oauth2-proxy is added to the auth-exemption guard:
  `JOBSPECS` in `scripts/check_oauth2_proxy_guard.py:22-25` and the
  hook's `files:` pattern at `.pre-commit-config.yaml:75-83`. Without
  both edits the new proxy can gain a skip-auth key with every gate green.
- **R14.** Comments record only what the code cannot
  (`.claude/rules/minimal-comments.md`), and every prose surface follows
  `.claude/rules/plain-language.md`; the new docs page is scanned per
  `.claude/rules/slop-scan-for-docs.md`. This requirement has no
  mechanical producer and needs none: it demands no quantity, and the
  `documentation` review pass `.loop/config.json` enables is what judges
  it.
- **R15.** *Runtime acceptance:* the deployed service authenticates a
  Vault-issued ID token, refuses one carrying another audience, embeds
  through Bifrost, reranks against its configured provider, and persists
  a collection into the `openviking` schema. **No producer for this
  exists in the declared code surface** — see Q7, tagged
  `unmeasurable-requirement`. Do not silently rescore it against
  `terraform validate`.

## 7. Code surface

New files carry no line anchors because they do not exist yet. No new
`.tf` file appears anywhere below, which is R11.

**deployments/applications (Terraform root)**

- `deployments/applications/services.tf:43-145` — add an `openviking`
  entry to `local.firewall_rules` (single-caller on port 1933, R12).
- `deployments/applications/services.tf:333-368` — add
  `resource "nomad_job" "openviking"` beside embark's, rendering
  `services/openviking.hcl`; pin BOTH `openviking_base_image`
  (`ghcr.io/volcengine/openviking:v0.4.17.1`) and `openviking_image` here,
  as embark pins `embark_image` at `:345` (R2); pass the OIDC client_id
  and `local.vault_oidc_issuer` in as templatefile variables (R8a);
  `depends_on` the Postgres database, the Bifrost key secret, and (only if
  Q1 resolves to keep it) the MinIO policy.
- `deployments/applications/services.tf:33-39` — add
  `data "vault_identity_oidc_client_creds" "openviking"` beside the memex
  one. It is the only producer of the client_id OpenViking validates as
  `audience` (R8a), since the client itself is created in the other root.
  A confidential client returns a real `client_secret` here; OpenViking
  needs the id alone, so the secret is not rendered anywhere.
- `deployments/applications/services.tf:621-646` — add
  `resource "bifrost_virtual_key" "openviking"`, provider_configs
  alphabetical, `depends_on = [null_resource.bifrost_ready]` (R7).
- `deployments/applications/secrets.tf:201-231` — add, per R6,
  `vault_kv_secret_v2` resources under `default/openviking/`: `db`
  (username/password from `postgresql_role.role["openviking"]` and
  `random_password.password["openviking"]`,
  `deployments/applications/database.tf:56-67`),
  `bifrost` (the virtual key value, copied the way
  `deployments/applications/secrets.tf:201-208` copies hermes's), and
  `minio` (only under Q1's option (a)). No `embark` entry: R5 keeps rerank
  on the gateway, so the Bifrost key is the only model credential.
- `deployments/applications/storage.tf:149-165` — add
  `resource "minio_iam_policy" "openviking_wi"` with `name = "openviking"`
  ONLY if Q1 keeps the workload-identity path alive; otherwise this file
  is untouched and the reason is recorded in the job's header comment.
- `deployments/applications/database.tf` — untouched. The role, database
  and `vector` extension already exist at `:8` and `:34-38`.

**deployments/applications/services (jobspecs and image)**

- `deployments/applications/services/openviking.hcl` — NEW. Single task,
  podman, `network_mode = "host"`, static port 1933, `vault {}`, host
  volume mounted at `/app/.openviking`, Consul check on `/ready`
  (unauthenticated), `secrets/file.env` template for credentials and a
  `local/ov.conf` template for the config, following
  `deployments/applications/services/registry-ui.hcl:87-102` for the
  Vault template shape and
  `deployments/applications/services/loki.hcl:107-140` if Q1 keeps a
  credential helper. Carries R10's `server.oidc` block with no `identity`
  key, its `issuer` from `local.vault_oidc_issuer`, its `audience` from
  the `vault_identity_oidc_client_creds` data source, and optionally an
  explicit `jwks_uri` so a first request does not depend on live
  discovery (P22).
- `deployments/applications/services/openviking/Dockerfile.openviking` —
  NEW, and the whole of R2. `ARG BASE_IMAGE`, then two `--target` pip
  installs, copying
  `deployments/applications/services/embark/Dockerfile.embark:40-51`.
  Uses `/usr/local/bin/python3.13 -m pip`, not the venv's python: the venv
  ships no pip (P11).
- `deployments/applications/services/openviking/justfile` — NEW. `build`,
  `push`, `release`, `show`, `verify`, reading the derived tag from the
  `openviking_image` line and `--build-arg BASE_IMAGE` from the
  `openviking_base_image` line in `../../services.tf`, copying
  `deployments/applications/services/embark/justfile:15-31` and `:73-79`.
  Unlike embark's, the base is READ rather than computed from the derived
  tag, because R2's pin is the artifact binding.
- `deployments/applications/services/openviking/README.md` — NEW. What
  each file is and the fact that building and pushing the image is an
  operator step, copying
  `deployments/applications/services/embark/README.md:1-13`.

**deployments/infrastructure (Terraform root)**

- `deployments/infrastructure/oidc.tf:99-107` — append the new client to
  `local.oidc_provider_client_ids`.
- `deployments/infrastructure/oidc.tf:407-444` — add an `openviking`
  section: a `local.openviking_redirect_url`, a confidential
  `vault_identity_oidc_client` carrying `assignments = ["allow_all"]`
  (R8, `docs/vault-human-auth.md:288-292`), and its
  `vault_identity_oidc_key_allowed_client_id` against
  `vault_identity_oidc_key.lab`.
- `deployments/infrastructure/secrets.tf:251-290` — add the proxy's own
  `oidc` and `cookie` KV entries under
  `default/oauth2-proxy-openviking/`, reusing
  `random_password.oauth2_proxy_cookie_secret` (`:231-234`).
- `deployments/infrastructure/services.tf:173-215` — add
  `resource "nomad_dynamic_host_volume" "openviking_data"`, constrained to
  the node R1 settles on.
- `deployments/infrastructure/services.tf:384-396` — add port 4182 to the
  `oauth2_proxy` firewall rule (R12).
- `deployments/infrastructure/services.tf:548-564` — add
  `resource "nomad_job" "oauth2_proxy_openviking"`.
- `deployments/infrastructure/services/oauth2-proxy-openviking.hcl` —
  NEW. A copy of
  `deployments/infrastructure/services/oauth2-proxy-registry-ui.hcl:25-107`
  on port 4182, one catch-all upstream to 127.0.0.1 port 1933, R10's
  `OAUTH2_PROXY_SCOPE="openid"`, plus the two settings R9 adds.
- `deployments/infrastructure/services/haproxy.hcl:98-122` — add
  `acl is_openviking` and its `use_backend`.
- `deployments/infrastructure/services/haproxy.hcl:180-184` — add
  `backend openviking` pointing at the proxy's port. No certificate work:
  the ACME job issues a wildcard
  (`deployments/infrastructure/services/acme.hcl:102`) and public DNS
  resolves any label (`docs/dns.md:91-93`).

**Gates and docs**

- `scripts/check_oauth2_proxy_guard.py:22-25` — add the new jobspec to
  `JOBSPECS`; its `_self_test` at `:41-56` stays as is.
- `.pre-commit-config.yaml:75-83` — widen the `oauth2-proxy-guard` hook's
  `files:` pattern to the new filename.
- `scripts/check_openviking_config.py` — NEW, only under Q7's
  widen-surface option. Parses the rendered ov.conf template and asserts
  R4's dimension, R3's key allow-list, R5's rerank target and R8's
  audience wiring; carries `--self-test` like
  `scripts/check_oauth2_proxy_guard.py:41-56`.
- `.pre-commit-config.yaml:66-73` — add the two hooks for that script,
  under the same reasoning the `tf-block-diff-self-test` comment records.
- `docs/openviking.md` — NEW. The deployment, the two forks and how they
  were settled, and the operator verification block R15 depends on.

## 8. Tests & validation gates

**The repo's gate is one command:** `just pre_commit` (`justfile:18-19`),
which runs `pre-commit run --all-files` over `.pre-commit-config.yaml`.
`.loop/config.json` declares it as the sole gate, with `require_review`,
`require_eval` and the `plan-validator` planning pass all on. There is no
CI workflow that runs these.

What actually fires for this change:

| Hook | Anchor | Covers |
|---|---|---|
| `check-json`, `check-yaml`, `end-of-file-fixer`, `detect-private-key` | `.pre-commit-config.yaml:6-13` | any JSON or YAML this ticket adds |
| `nomad-fmt` | `.pre-commit-config.yaml:16-21` | `openviking.hcl`, `oauth2-proxy-openviking.hcl`, `haproxy.hcl` |
| `terraform-fmt` | `.pre-commit-config.yaml:22-27` | both roots |
| `terraform-validate` | `.pre-commit-config.yaml:28-33` | `scripts/tf_validate.sh:8-12` validates both roots offline |
| `oauth2-proxy-guard` | `.pre-commit-config.yaml:75-83` | must be widened by R13 or it skips the new proxy |
| `oauth2-proxy-guard-self-test` | `.pre-commit-config.yaml:85-90` | fires when `scripts/check_oauth2_proxy_guard.py` changes |
| `ruff`, `ruff-format`, `mypy` | `.pre-commit-config.yaml:37-64` | scoped `^(cli|scripts)/`, so both scripts in section 7 are linted and type-checked strictly |
| `pytest` (cli) | `.pre-commit-config.yaml:91-97` | runs `cli/tests`; touches nothing this ticket adds |
| `dash-backend-pytest` | `.pre-commit-config.yaml:123-130` | runs the dash backend suite; touches nothing this ticket adds |
| `registry-ui-backend-pytest` | `.pre-commit-config.yaml:152-157` | runs the registry-ui backend suite; touches nothing this ticket adds |

The repo therefore does run tests in its gate, and the three suites are
real. None of them reaches `deployments/` or `scripts/`: each is pinned to
`cli/tests` or one service backend directory by its own `--project` and
path argument. That is why R15 still has no producer and Q7 stands.

**Tests to add.**

- `scripts/check_oauth2_proxy_guard.py` — extend `JOBSPECS` (`:22-25`) to
  the third proxy. Its existing `--self-test` (`:41-56`) is the test that
  guards the guard; it must stay green under `mypy --strict`.
- `scripts/check_openviking_config.py` — NEW, under Q7's widen-surface
  option only. Its own `--self-test` is its test: `scripts/` holds no
  pytest project, which is exactly the reasoning
  `.pre-commit-config.yaml:66-73` already records for `tf_block_diff.py`.

**Terraform-specific proof.** This change adds blocks rather than moving
them, so `scripts/tf_block_diff.py` is not required. If the implementer
does relocate an existing block, run it per
`.claude/rules/terraform-file-layout.md` and read every reported diff.

**Not automatable here.** No suite in this repo exercises a running
service, and none of the three pytest hooks above covers the paths this
ticket touches. R15's checks are runbook steps in `docs/openviking.md`,
not gates — see Q7.

**Review.** `.claude/rules/adversarial-reviews.md` requires an
adversarial sub-agent review before the work is reported done;
`.loop/config.json` runs `adversarial` and `documentation` passes with
`max_review_cycles` 3.

## 9. Risk assessment

**Blast radius.** Mostly additive, but three edits reach live shared
state:

- `local.oidc_provider_client_ids` (`deployments/infrastructure/oidc.tf:99-107`)
  is read by `vault_identity_oidc_provider.lab` (`:117-126`). A
  malformed entry breaks the authorization endpoint for dash,
  registry-ui, grafana, nomad and memex at once.
- `haproxy.hcl`'s config is a template rendered into the job, so any edit
  re-registers HAProxy and briefly interrupts every edge hostname.
- The firewall provisioners are ONE-WAY
  (`deployments/applications/services.tf:148-158`): a wrong rule cannot
  be removed by `terraform` and needs a manual `ufw delete` on the host.

**Reversibility.** The Nomad jobs, the Vault KV entries, the OIDC client
and the Bifrost virtual key all destroy cleanly. The firewall rules do
not. The pushed container image is immutable and harmless if unused.
Nothing here drops data: the pre-existing schemas and tables are left
alone until Q4 is answered.

**Likeliest failure modes.**

1. *Q1 settled wrong.* Shipping the workload-identity shape produces a
   service that fails at startup with `S3 backend requires the following
   fields: access_key, secret_key`, not at request time.
2. *Deployed against Bifrost 1.6.7.* If OV1 lands before U7, every rerank
   call fails with a flat `400 Invalid request payload` naming no field
   and an empty `routing_info`, which reads like a Bifrost or embark fault
   rather than a payload-shape mismatch (P2, P20). The `depends_on` gate
   is what prevents it; do not bypass it.
3. *Wrong embedding dimension.* Silent at startup, corrupt at write time,
   and only fixable by dropping the collection (R4).
4. *Audience mismatch.* Every request 401s after a successful browser
   login, which looks like a proxy bug (R8).
5. *Session outliving the token.* Works for an hour, then 401s with the
   cookie still valid and no re-login prompt (R9).
6. *`extra: "forbid"` everywhere.* `PgVectorParams`, `OIDCConfig`,
   `S3Config`, `RerankConfig` and `VectorDBBackendConfig` all forbid
   unknown keys, so one invented or misspelled key is a hard startup
   failure rather than a warning (P4).
7. *Image build.* `ov-postgres` is installed from a git URL and versioned
   by `hatch-vcs` from git tags. A ref that does not carry a `v*` tag, or
   a build environment without git, yields a wheel versioned `0.0.0` or
   fails outright (P12).
8. *No admin path.* Under `auth_mode: "oidc"` every identity resolves to
   role `USER` and `root_api_key` is not consulted, so OpenViking's admin
   endpoints are unreachable over HTTP (P7). Q3's option (d),
   `auth_mode: "trusted"`, is the only mode that offers one behind a
   proxy; it is not recommended without the operator settling Q3.
9. *Placement.* If radxa has no headroom the job either fails to place or
   evicts something (R1, P10).
10. *The container cannot reach the Vault issuer.* The OIDC plugin
    resolves its discovery document and JWKS over HTTP at request time, so
    a DNS or egress failure to `vault.lab.orangecluster.nl` surfaces as a
    401 that looks like a token problem. Setting `jwks_uri` explicitly
    removes the discovery hop but not the JWKS fetch (P22).
11. *The base image floats.* Building against `:latest` rather than R2's
    pin can pick up a tree none of these premises were read at, and the
    failure arrives as a pydantic error at container start rather than at
    build (P21).

## 10. Subtickets

Ordered. Each is one loop iteration. If these become separate plan files,
encode this chain in each file's `depends_on` front-matter, and see Q8.

1. **S0 — settle the forks.** Operator answers Q1, Q3, Q4, Q5 and Q7 (Q2
   is already settled by operator decision, see section 11), and confirms
   R1's placement. No code. Everything below assumes those answers, and
   nothing below may start before `U7-upgrade-bifrost-2x` reaches `done`:
   the `depends_on` front-matter enforces it.
2. **S1 — the derived image.** `Dockerfile.openviking`, its `justfile`,
   its `README.md`, and the `openviking_image` line in
   `deployments/applications/services.tf`. Ends with a pushed image and a
   `verify` recipe proving `ov_postgres` imports inside it.
3. **S2 — storage and database wiring.** The `openviking` MinIO policy in
   `storage.tf` if Q1 keeps it, plus the Vault KV entries for the
   database credential and, under Q1 option (a), the MinIO credential.
   Depends on S0.
4. **S3 — Bifrost key.** `bifrost_virtual_key.openviking` in
   `services.tf` and its Vault KV copy under `default/openviking/bifrost`.
   It is the only model credential the job holds, because R5 keeps both
   embedding and rerank on the gateway. Depends on S0 and on U7 being
   done; independent of S1 and S2.
5. **S4 — Vault OIDC client.** The client with its
   `assignments = ["allow_all"]`, its key registration, the redirect-URL
   local, the append to `local.oidc_provider_client_ids`, the proxy's two
   KV entries, and the applications-root
   `data "vault_identity_oidc_client_creds" "openviking"` that carries the
   client_id across roots (R8a). Depends on S0.
6. **S5 — the job.** `openviking.hcl`, the host volume, the
   `nomad_job.openviking` resource and its firewall rule. Depends on S1,
   S2, S3 and S4: every template reference it renders comes from those.
7. **S6 — edge and proxy.** `oauth2-proxy-openviking.hcl`, its Terraform
   resource, the 4182 firewall entry, the HAProxy acl/backend, and the
   R13 guard widening. Depends on S4 and S5.
8. **S7 — docs and verification.** `docs/openviking.md`, including the
   R15 runbook and the R14 slop scan over it, and, under Q7's
   widen-surface option, `scripts/check_openviking_config.py` with its
   hooks. Depends on S6.

## 11. Open questions

**Q1 — MinIO workload identity is not reachable. How should blob storage
authenticate? RESOLVED: (a), static key from Vault.** The operator asked
for MinIO through WI. P1 shows the
config layer forbids it: `access_key` and `secret_key` are mandatory for
`backend: "s3"`, and the Rust client passes `session_token = None`, so
MinIO STS credentials cannot be represented even if the validator were
bypassed.

- (a) **Static key from Vault.** Use the existing `openviking` MinIO user
  and its `openviking_read_write` policy, copied into
  `secret/data/default/openviking/minio`, and record the WI gap in the
  jobspec header. Do NOT create a `minio_iam_policy` named `openviking`:
  it would be dead config that looks live.
- (b) Patch OpenViking upstream so `access_key`/`secret_key` are optional
  and a session token is threaded through. Correct, and far outside this
  ticket.
- (c) Use `backend: "local"` on the host volume and drop MinIO. Loses
  durability across a node loss.
- (d) Defer OpenViking entirely until (b) lands.

**Settled as (a).** Decided by the coordinating agent under an explicit
grant of full loop control from JasperHG90, 2026-09-05, operator offline.
It ships, it is honest about what it is, and it is a one-line change to
(b) later. It is also the shape the operator's own extension repo
assumes: `openviking_extensions` ships a MinIO policy document naming the
`openviking` bucket for a static read-write user.

Three things this resolution binds. The job reads the existing
`openviking` MinIO user's key, copied under
`secret/data/default/openviking/minio`, and the jobspec header records
the workload-identity gap and why it exists, so a later reader does not
re-derive P1. NO `minio_iam_policy` named `openviking` is created: claim
mode would resolve it from `nomad_job_id`, and creating one while nothing
performs an STS exchange leaves config that reads as live and grants
nothing — the failure this ticket exists to avoid, not a harmless
placeholder. And this is a deliberate step BACK from the cluster's
keyless direction (`docs/workload-identity.md:263-355`), forced by
OpenViking's config layer rather than chosen; if upstream ever makes
`access_key`/`secret_key` optional and threads a session token, the
change back is one block in `storage.tf` plus the helper shape loki
already carries.

**Q2 — rerank through Bifrost. RESOLVED by operator decision: upgrade the
gateway.** This fork was raised because the deployed Bifrost 1.6.7 rejects
the plain-string `documents` OpenViking's three OpenAI-compatible rerank
clients send, measured on both sides (P2). The evidence is kept here
because it is what the dependency rests on, not because the question is
still open.

- (a) Point rerank straight at embark, bypassing the gateway. Was the
  recommendation; now the documented FALLBACK if `U7-upgrade-bifrost-2x`
  stalls. Its cost is what made it second-best: rerank would lose
  Bifrost's logging, governance and virtual-key accounting, and radxa
  would dial embark directly, against the stated intent of the rule it
  relies on (`deployments/applications/services.tf:102-106`).
- (b) **Upgrade Bifrost to 2.0.0**, whose `RerankDocument.UnmarshalJSON`
  accepts a bare string and normalizes it, removing the incompatibility
  entirely. **CHOSEN.** Tracked as `U7-upgrade-bifrost-2x`, which this
  ticket's `depends_on` names, so the loop refuses to pick OV1 up until
  U7 is `done` (P20).
- (c) Run a translating shim. An extra deployment unit for one call type,
  obsolete the moment (b) lands.
- (d) Drop rerank. It is optional: `rerank_batch` returns `None` when
  rerank fails and the caller falls back.

**Settled as (b).** R5 and P20 carry the consequence; nothing in this
ticket may be implemented against 1.6.7. If U7 is abandoned, reopen this
question and fall back to (a) rather than shipping a rerank path that
400s.

**Q3 — how do headless LAN agents authenticate? RESOLVED: (a), browser
access only in this ticket.** `auth_mode` selects
exactly ONE plugin, `oidc` has no API-key fallback, and Vault's lab
provider supports only `authorization_code` (P3, P8). So under the
operator's stated design nothing headless can call OpenViking.

- (a) **Scope this ticket to browser access** through the proxy, and give
  agent access its own ticket once the mechanism is chosen.
- (b) Run `auth_mode: "api_key"` and gate humans at the proxy only. Drops
  the OAuth requirement the operator asked for.
- (c) Two OpenViking jobs against one database, one per mode. Two
  services to keep in step, and the second is unauthenticated to anything
  that reaches its port.
- (d) `auth_mode: "trusted"`, which trusts `X-OpenViking-Account` and
  `X-OpenViking-User` headers and can be gated on a root API key, and
  which also accepts an `X-OpenViking-Role: admin` assertion — the only
  mode in this set that leaves an admin path open (section 9, failure
  mode 8). Honest assessment: it moves the entire authorization decision
  into whatever sets those headers, so it is safe ONLY if every route to
  port 1933 passes through the proxy and the proxy sets them itself. The
  firewall shape R12 requires makes that reachable, but nothing in this
  plan asserts it, and a single future rule widening 1933 would turn it
  into header-spoofable access with no error anywhere. It also drops
  OIDC, which is what the operator asked for.

**Settled as (a).** Decided by the coordinating agent under an explicit
grant of full loop control from JasperHG90, 2026-09-05, operator offline.
This ticket ships browser access through the proxy and nothing else;
agent access gets its own ticket once its mechanism is chosen. Section 5
already records headless authentication as a non-goal, so no scope
changes here.

For whoever writes that follow-up: option (d), `auth_mode: "trusted"`, is
the strongest candidate and should be the starting point rather than a
rediscovery. It is the only mode in this set that also reopens the admin
path section 9's failure mode 8 closes. Its precondition is the one named
above — every route to port 1933 must pass through the proxy, and the
proxy must set the identity headers itself — so that ticket's first job
is to make the firewall shape an asserted invariant rather than an
incidental one.

**Q4 — what happens to the pre-existing schemas and tables? RESOLVED:
adopt the `openviking` schema, drop `dbg_fts*` by hand.** Narrower
than it looks. `openviking.ov_collections` and `openviking.ov_indexes`
hold ZERO rows, their columns already match ov-postgres v0.2.0's DDL
exactly, and its three helper functions `ov_array_to_text`,
`ov_path_matches` and `ov_sparse_dot` are already installed (P13). So the
registry is bootstrapped, not stale, and adoption costs nothing. Five
`dbg_fts*` schemas from operator experimentation also sit in the database.
**Settled: leave the `openviking` schema in place and let ov-postgres
adopt it.** Decided by the coordinating agent under an explicit grant of
full loop control from JasperHG90, 2026-09-05, operator offline.
Adoption is a no-op, not a migration: both registry tables are empty and
already carry the v0.2.0 column shapes, so the first run finds what it
would have created. The five `dbg_fts*` schemas are dropped by hand in a
separate, operator-run step and NEVER from Terraform: a `postgresql_schema`
resource would put a live `DROP` behind every future `apply`, and this
database holds the vector store. This ticket touches neither, which is
what section 5 already records.

**Q5 — which VLM model, and is VLM enabled at all? RESOLVED: leave `vlm`
unset.** Bifrost's `ollama`
provider is Ollama Cloud, and a model must exist in Bifrost's catalog for
that provider or the call 403s regardless of the virtual key's allowlist
(`deployments/applications/services.tf:609-614`). The operator has named
no model. **Settled: leave `vlm` unset in the first deployment.** Decided by
the coordinating agent under an explicit grant of full loop control from
JasperHG90, 2026-09-05, operator offline.
Naming a model nobody has chosen would produce a config that validates
and then 403s on first use, since Bifrost refuses an uncatalogued model
for a provider whatever the virtual key allows. OpenViking's VLM config
validates only when one of its fields is set, so the empty block is
legal and costs nothing. A follow-up adds it once a catalogued vision
model is picked; that is a `vlm` block and a `provider_configs` entry,
not a redesign.

**Q6 — image name and registry. RESOLVED: `ghcr.io/jasperhg90/openviking`.**
embark's derived image goes to
`ghcr.io/jasperhg90/embark-jetson`
(`deployments/applications/services.tf:345`), while model weights go to
the cluster registry.
**Settled: `ghcr.io/jasperhg90/openviking:<upstream>-<rev>`**, matching
embark, because nodes already authenticate to ghcr.io
(`bootstrap/playbooks/configure_podman.yml`) and the cluster registry is
reachable only through the edge. Decided by the coordinating agent under an
explicit grant of full loop control from JasperHG90, 2026-09-05, operator
offline.
R2's pin fixes `<upstream>` at `v0.4.17.1`, so the first tag is
`v0.4.17.1-1`, reading the way embark's `-1` build revision does.

**Q7 — `unmeasurable-requirement`: R15 (runtime acceptance) has no
producer in the declared code surface. RESOLVED: `widen-surface` for the
static half, `declared-proxy` for the runtime half.** This repo's only
gates are
pre-commit hooks over file content (P14). Nothing runs a deployed
service, so "authenticates a Vault ID token", "refuses a foreign
audience", "embeds through Bifrost", "reranks" and "persists a
collection" are unproducible here. The four options, in order:

- **`widen-surface`:** add `scripts/check_openviking_config.py` (section
  7) with a pre-commit hook, so the STATIC half of R15 becomes part of
  this ticket: dimension 768, the `custom_params` key allow-list, the
  rerank target, `auth_mode`, and that OpenViking's `audience` is the
  same client_id the proxy uses. Revises section 2 upward by roughly one
  subticket. It cannot reach the runtime half.
- **`split-ticket`:** move R15 to its own plan file that runs after
  deployment, with `depends_on = ["OV1-openviking-service"]`.
- **`drop-requirement`:** cut R15 from section 6 and record in section 5
  that runtime acceptance is out of scope.
- **`declared-proxy`:** keep R15 and score it with an explicitly LABELLED
  proxy — the static config check plus the presence of a runbook in
  `docs/openviking.md` — where the eval row's Expected cell states that
  the proxy does NOT measure whether a live token is accepted, whether a
  foreign audience is refused, or whether any call reaches embark or
  Bifrost.

**Settled: `widen-surface` for the static half plus `declared-proxy` for
the runtime half.** Decided by the coordinating agent under an explicit
grant of full loop control from JasperHG90, 2026-09-05, operator offline.

`widen-surface` costs no change to any bound section. Sections 7 and 8
already name `scripts/check_openviking_config.py` and its two
`.pre-commit-config.yaml` hooks, each marked as landing only under this
option, so the resolution satisfies that condition rather than adding a
file. Section 2's magnitude stands at L: the script is one file with its
own `--self-test`, the shape `scripts/check_oauth2_proxy_guard.py`
already carries, not a new subticket.

`declared-proxy` governs the rest, and the LABEL is the whole point. The
eval row scoring R15 must state, in its Expected cell, that the proxy
does NOT measure whether a live Vault-issued token is accepted, whether a
token carrying a foreign audience is refused, or whether any call
actually reaches embark or Bifrost. What it does measure is that the
rendered config carries the right literals and that
`docs/openviking.md` carries the runbook that checks the rest by hand.
Scoring R15 against `terraform validate` without that label is the silent
downgrade this fork exists to prevent, and an eval row missing the label
should be treated as a defect in the eval, not in the plan.

**Q8 — one ticket or eight?** Section 10 decomposes into S0..S7. As one
ticket the diff spans two Terraform roots, two jobspecs, an image and a
docs page, which is a large surface for one adversarial review.
**Recommendation: keep it as one ticket** — the pieces are mutually
useless (a job with no secrets, a proxy with no job) and every subticket
but S1 is a handful of Terraform blocks. Split only if the review cap is
hit.

**Q9 — credential rotation.** The operator's request pasted a live MinIO
secret key, a live Postgres password and a live Bifrost API key in
plaintext. None appears in this plan or may appear in the
implementation. **Recommendation: rotate all three** before this ships;
`docs/credential-rotation.md` carries the procedure. Tracked here so it
is not lost, not because this ticket performs it.

## Premises / assumptions

- **P1.** OpenViking cannot use MinIO workload identity, at the version
  this ticket deploys. `S3Config.validate_config` lists `access_key` and
  `secret_key` among the fields an `s3` backend requires, and
  `AGFSConfig`'s after-validator calls it whenever the backend is `s3`;
  the Rust client then builds
  `Credentials::new(ak, sk, None, None, "ragfs-s3fs")`, so no session
  token is ever sent. Three escape routes are closed: `session_token` is a
  forbidden extra key on `S3Config`, `backend` is restricted to
  `local`/`s3`/`memory`, and the Rust crate names no session token
  anywhere. The field's own description claims the opposite of what the
  validator enforces, which is why reading it alone misleads.
  Source: https://github.com/volcengine/OpenViking/blob/v0.4.17.1/openviking_cli/utils/config/agfs_config.py#L89-L108
  (validator), #L561-L571 (the dispatch that calls it), #L36 (the
  misleading description), and
  https://github.com/volcengine/OpenViking/blob/v0.4.17.1/crates/ragfs/src/plugins/s3fs/client.rs#L472-L476
  probe: git clone --depth 1 --branch v0.4.17.1 https://github.com/volcengine/OpenViking.git, then read those ranges and grep -rn "session_token" crates/ragfs/src/plugins/s3fs/ (empty). These line numbers are the DEPLOYED tag's; on main at 0c5147c the dispatch sits at 475-477 instead.
- **P2.** The rerank shape OpenViking sends is the one Bifrost 1.6.7
  rejects, and no provider setting dodges it. The `openai` client types
  `documents` as `List[str]` and passes it through unwrapped in both the
  nested and the flat body; the `cohere` client is a separate
  `RerankBase` subclass that builds its own flat body inline and posts to
  its own `/v2/rerank`, never calling the `openai` client's builder, but
  it passes `documents` through as the same plain `List[str]`. Two
  independent code paths, one wire shape. Switching between those two
  changes nothing. The
  `litellm` client hands the same `List[str]` to `litellm.rerank(...)`
  and never reaches OpenViking's own body builder, so what its
  transformer emits on the wire is UNCERTAIN and was not measured; it
  does not matter here, because R5 configures `provider: "openai"`. The
  `vikingdb` client is the one exception that DOES wrap each document as
  `{"text": doc}`, but it signs a Volcengine request against its own host
  and cannot be aimed at Bifrost, so it is no escape either. Bifrost
  1.6.7 answers object-shaped documents with 200 and string-shaped
  documents with a flat `400 Invalid request payload` whose
  `routing_info` is empty, meaning the request never reached embark.
  Source: https://github.com/volcengine/OpenViking/blob/v0.4.17.1/openviking/models/rerank/openai_rerank.py#L75-L102,
  https://github.com/volcengine/OpenViking/blob/v0.4.17.1/openviking/models/rerank/cohere_rerank.py#L64-L70,
  https://github.com/volcengine/OpenViking/blob/v0.4.17.1/openviking/models/rerank/litellm_rerank.py#L67-L73 (the client that
  does NOT share the builder),
  https://github.com/volcengine/OpenViking/blob/v0.4.17.1/openviking/models/rerank/volcengine_rerank.py#L107 (the object
  wrapping), #L122 (the Volcengine host) and #L220 (the dispatch to the
  OpenAI client)
  probe: curl -s POST /v1/rerank against Bifrost on 192.168.2.50 port 8080 with a virtual key, once with objects and once with strings; the same behavior is recorded at `deployments/applications/services/bifrost.hcl:107-112`.
  P20 is what makes this survivable. Whether embark itself accepts string
  documents is UNCERTAIN and no longer load-bearing, since R5 keeps rerank
  on the gateway: embark's own API documentation (docs/api.md, line 254)
  is in a PRIVATE repository this session cannot open, GitHub returning
  404 unauthenticated. It matters only if Q2's fallback (a) is taken, and
  then it must be confirmed by one curl from radxa first.
- **P3.** Vault's `lab` provider offers no refresh tokens and no
  non-interactive grant. Its discovery document reports
  `grant_types_supported` of exactly `["authorization_code"]`,
  `response_types_supported` of `["code"]`, and scopes
  `["email","groups","openid"]`.
  probe: curl -sS https://vault.lab.orangecluster.nl/v1/identity/oidc/provider/lab/.well-known/openid-configuration (fetched 2026-09-05).
- **P4.** A misspelled config key is a startup failure, not a warning.
  `PgVectorParams` sets `extra="forbid"` and declares exactly the fifteen
  keys R3 lists; `VectorDBBackendConfig`, `OIDCConfig`, `S3Config` and
  `RerankConfig` each set `extra="forbid"` too.
  Source: https://github.com/JasperHG90/openviking_extensions/blob/ov-postgres-v0.2.0/src/ov_postgres/config.py#L116-L177
  and https://github.com/volcengine/OpenViking/blob/v0.4.17.1/openviking_cli/utils/config/vectordb_config.py#L263-L268
  probe: git clone --depth 1 --branch ov-postgres-v0.2.0 https://github.com/JasperHG90/openviking_extensions.git, then read src/ov_postgres/config.py.
- **P5.** embark's `embedding` model returns 768-dimensional vectors
  through Bifrost. A `POST /v1/embeddings` for model `embark/embedding`
  returned `{"model":"embedding","dim":768,"usage":{"prompt_tokens":4,
  "total_tokens":4}}`.
  probe: curl -s POST /v1/embeddings against Bifrost on 192.168.2.50 port 8080 piped through jq counting the vector (coordinator-measured this session). The operator's draft ov.conf said 512, which belongs to a different model.
- **P6.** `OAUTH2_PROXY_PASS_AUTHORIZATION_HEADER` forwards the OIDC ID
  token upstream as `Authorization: Bearer`. oauth2-proxy v7.13.0's own
  configuration reference documents the flag as "pass OIDC IDToken to
  upstream via Authorization Bearer header", and lists `--cookie-refresh`
  as supported only for providers implementing the full OIDC refresh
  spec, which P3 shows Vault does not.
  Source: https://raw.githubusercontent.com/oauth2-proxy/oauth2-proxy/v7.13.0/docs/docs/configuration/overview.md
  (lines 128, 134 and 146 of that file). That the receiving end reads it
  as OpenViking expects is UNCERTAIN and is an S6 verification step.
- **P7.** Under `auth_mode: "oidc"` the role is always `USER` and the
  `groups` array is never consulted. The OIDC plugin calls
  `map_account_id` and `map_user_id` and then returns
  `ResolvedIdentity(role=Role.USER, ...)` unconditionally; it never calls
  `map_role`. Defaults map `account_id` to the fixed string `default` and
  `user_id` to the `sub` claim. A claim that IS consulted is stringified
  with `str(v)`, so an array claim would arrive as its Python repr.
  Source: https://github.com/volcengine/OpenViking/blob/v0.4.17.1/openviking/server/auth/plugins/oidc.py#L121-L144
  and https://github.com/volcengine/OpenViking/blob/v0.4.17.1/openviking/server/auth/identity_mapping.py#L56-L93
  and #L145-L159.
- **P8.** Exactly one auth plugin serves the server. `app.py` resolves
  one plugin class from the registry by the effective auth mode and
  installs it; there is no chain and no fallback, so `root_api_key` is
  not consulted under `oidc`.
  Source: https://github.com/volcengine/OpenViking/blob/v0.4.17.1/openviking/server/app.py#L102-L131
- **P9.** OpenViking's native OAuth 2.1 cannot be backed by Vault. Its
  config docstring states it is layered on `AuthMode.API_KEY` and
  resolves its own opaque `ovat_` tokens to the same identity an API key
  would produce; the guide adds that an OAuth token grants the same
  permissions "as the API key that produced it".
  Source: https://github.com/volcengine/OpenViking/blob/v0.4.17.1/openviking_cli/utils/config/oauth_config.py#L16-L29
  and https://github.com/volcengine/OpenViking/blob/v0.4.17.1/docs/en/guides/11-oauth.md#L299
- **P10.** Headroom on radxa is UNCERTAIN. Nomad's API refused an
  unauthenticated node read from this session, so no capacity number was
  obtained. Ten jobs already constrain themselves to
  `radxa-dragon-q6a`, whose declared reservations total roughly 3.0 CPU
  shares and 2.4 GiB across bifrost, hermes, dash, registry-ui, nats,
  redis, prometheus, two oauth2-proxies and two backup jobs
  (`deployments/infrastructure/services/prometheus.hcl:182-183`,
  `deployments/infrastructure/services/nats.hcl:97-98`,
  `deployments/applications/services/registry-ui.hcl:104-107`).
  probe: curl -sS -o /dev/null -w "%{http_code}" http://192.168.2.30:4646/v1/nodes returned 403. Re-run with a token as R1's precondition.
- **P11.** The upstream image can be layered but not pip-installed into
  directly. It carries `jose` and `httpx` (so OIDC works out of the box)
  but not `psycopg` (so ov-postgres must be added), runs as root, ships
  git 2.47.3 and curl but NOT wget, has no pip inside `/app/.venv` and no
  `uv`, and has pip 26.2.1 at `/usr/local/bin` for python 3.13.15. Its
  site-packages directory is `/app/.venv/lib/python3.13/site-packages`.
  The absence of wget matters: `deployments/applications/services/loki.hcl:112`
  builds its credential helper on wget, so any helper here must use curl.
  probe: docker run --platform linux/arm64 --entrypoint sh ghcr.io/volcengine/openviking:v0.4.17.1 -c "..." inspecting importlib specs, /usr/local/bin/python3.13 -m pip --version, git --version, command -v wget, and id (run this session against the arm64 manifest).
- **P12.** `ov-postgres` installs only from a git URL and versions itself
  from git tags. It is not on PyPI; its pyproject declares
  `hatch-vcs` with `git describe --match "v*"`, and the tag carrying the
  release is `v0.2.0` (the repository also carries `ov-postgres-v0.2.0`
  and `latest`). At that tag the package lives at `src/ov_postgres`, NOT
  under `packages/ov-postgres`, so a `#subdirectory=` fragment pinned to
  that tag would fail. The repository was renamed: its README still
  points installs at the old `openviking_postgres` name, which redirects.
  Source: https://github.com/JasperHG90/openviking_extensions/blob/ov-postgres-v0.2.0/pyproject.toml#L36-L48
  probe: git clone --depth 1 --branch ov-postgres-v0.2.0 of that repository, then `find` its tree and read pyproject.toml (run this session).
- **P13.** The target database is already partly populated. It reports
  PostgreSQL 18.3 with `vector` 0.8.2, schemas `dbg_fts`, `dbg_fts2`
  through `dbg_fts5`, `openviking` and `public`, and tables
  `openviking.ov_collections` and `openviking.ov_indexes`.
  Both registry tables hold ZERO rows, their columns are
  `ov_collections(name, table_name, meta, created_at)` and
  `ov_indexes(collection, index_name, meta, created_at)`, which match
  ov-postgres v0.2.0's DDL exactly, and its three helper functions
  `ov_array_to_text`, `ov_path_matches` and `ov_sparse_dot` are already
  installed in that schema. So adoption is a no-op rather than a
  migration.
  Source: https://github.com/JasperHG90/openviking_extensions/blob/ov-postgres-v0.2.0/src/ov_postgres/ddl.py#L38-L39
  probe: read the admin password with `vault kv get -mount=secret -field=password default/postgres/localstack`, then run psql -tAc "select ..." from a throwaway postgres:17-alpine container against 192.168.2.30, querying pg_namespace, information_schema.columns, pg_proc and the two row counts (run this session; read-only selects only).
- **P14.** This repo's gate runs tests, but none that reach this ticket.
  `.loop/config.json` declares `gates` of exactly `["just pre_commit"]`
  and `justfile:18-19` runs `pre-commit run --all-files`. Most hooks in
  `.pre-commit-config.yaml:6-157` read files, but THREE run pytest:
  `.pre-commit-config.yaml:91-97` over `cli/tests`,
  `.pre-commit-config.yaml:123-130` over the dash backend, and
  `.pre-commit-config.yaml:152-157` over the registry-ui backend. Each is
  pinned by its own `--project` and path argument to `cli/` or one service
  backend directory, so none covers `deployments/` or `scripts/` — which
  `.pre-commit-config.yaml:66-73` states in its own words when it explains
  why `tf_block_diff.py` carries its own cases. The conclusion is
  unchanged: R15 has no producer.
- **P15.** The MinIO side is ready except for the workload-identity
  policy. Bucket `openviking` exists and is empty; the policy list holds
  `openviking_read_write` and `openviking_read_only` but no policy named
  exactly `openviking`, which is the name claim mode resolves from
  `nomad_job_id` (`deployments/applications/storage.tf:86-98`).
  probe: mc ls m1lab and mc admin policy list m1lab (run this session, read-only).
- **P16.** The pluggable vectordb backend is real. The adapter factory
  falls back to `importlib.import_module` when the configured backend
  contains a dot and the resolved class subclasses `CollectionAdapter`,
  so `ov_postgres.adapter.PgVectorCollectionAdapter` resolves only if the
  package is importable in the interpreter running the server.
  Source: https://github.com/volcengine/OpenViking/blob/v0.4.17.1/openviking/storage/vectordb_adapters/factory.py#L24-L45
- **P17.** The server's config file expands environment variables at load
  time (`os.path.expandvars` over the raw JSON text before parsing), so
  the ov.conf template can hold placeholders and the secrets can arrive
  through the task's env instead of being written into the rendered
  config. A literal placeholder inside a Terraform `templatefile` must be
  escaped as `$${VAR}`, the convention already used for
  `$${attr.unique.hostname}` at
  `deployments/applications/services/registry-ui.hcl:7`.
  Source: https://github.com/volcengine/OpenViking/blob/v0.4.17.1/openviking_cli/utils/config/config_loader.py#L86-L92
- **P18.** `/health` and `/ready` need no authentication, so a Consul
  check works under any auth mode; the server listens on 1933 and keeps
  its state under `/app/.openviking`, which is the one path to mount.
  Source: https://github.com/volcengine/OpenViking/blob/v0.4.17.1/openviking/server/routers/system.py#L70-L116
  and https://github.com/volcengine/OpenViking/blob/v0.4.17.1/Dockerfile#L119-L137
- **P19.** The `openviking` MinIO bucket, its writer user, and the
  Postgres database, role and `vector` extension are already declared in
  Terraform and need no new declaration:
  `deployments/applications/storage.tf:63-68` and
  `deployments/applications/database.tf:8` with `:34-38`.
- **P20.** Rerank through Bifrost needs the gateway at 2.0.0 or newer, and
  the deployed one is 1.6.7. Three links, each measured:

  1. *The Docker tag tracks the `transports` module.* `transports/version`
     reads `2.0.0` at tag `transports/v2.0.0` and `1.6.7` at
     `transports/v1.6.7`, the image is built from `transports/Dockerfile`
     whose Go stage opens `COPY transports/go.mod transports/go.sum ./`,
     and this repo pins `bifrost_version = "1.6.7"`
     (`deployments/applications/services.tf:537`) into
     `docker.io/maximhq/bifrost:v${bifrost_version}`
     (`deployments/applications/services/bifrost.hcl:40`).
  2. *The fix arrives through the `core` module, not the in-tree file.*
     `transports/v2.0.0` builds against `github.com/maximhq/bifrost/core
     v1.8.3` (`transports/go.mod` line 18), with no `replace` directive
     and no `go.work` in the tree, so the binary links the published
     `core v1.8.3` rather than the sibling directory. That module's
     `core/schemas/rerank.go` carries
     `func (d *RerankDocument) UnmarshalJSON` at line 28, decoding a bare
     string into `RerankDocument{Text: text}` before falling back to the
     object branch, and it is byte-identical (md5
     `6d6fafb30462aad8847793176ed53041`) to the in-tree copy at
     `transports/v2.0.0`. The same file at `transports/v1.6.7` declares
     the struct and no unmarshaler at all.
  3. *Therefore* OV1 must NOT be implemented before
     `U7-upgrade-bifrost-2x` reaches `done`, which the front-matter
     `depends_on` enforces at pickup.

  Source: https://github.com/maximhq/bifrost/blob/core/v1.8.3/core/schemas/rerank.go#L26-L41
  (the linked module) and
  https://github.com/maximhq/bifrost/blob/transports/v2.0.0/transports/go.mod#L18
  (the pin to it), against
  https://github.com/maximhq/bifrost/blob/transports/v1.6.7/core/schemas/rerank.go
  probe: curl -sS each raw URL and compare with md5sum. Note what is NOT true: there is no `core/v2.0.0` tag (a raw fetch 404s), so the `2.0.0` version number belongs to the transports module alone. The BARE tag `v2.0.0` does resolve and its rerank schema carries no unmarshaler, which is why naming the tag series matters.
- **P21.** `:latest` is not a pin, and the version the premises were read
  at is the version the image ships. `ghcr.io/volcengine/openviking:latest`
  and `:v0.4.17.1` both return index digest
  `sha256:14553ec16f2bda9bd08a188cffb659fcfff4fde5891cbb881ed1bd8488b23294`
  today, and the pulled arm64 image reports
  `openviking.__version__ == "v0.4.17.1"`. That equality is a fact about
  today, not a guarantee, which is why R2 writes the tag rather than
  `:latest`.
  probe: fetch a pull token from ghcr.io and read the Docker-Content-Digest header of the manifest for each tag with an OCI-index Accept header; separately, docker run the pulled image with --entrypoint /app/.venv/bin/python printing importlib.metadata.version (run this session, read-only).
- **P22.** The OIDC plugin resolves discovery and JWKS over the network at
  request time, so the container must reach the Vault issuer. It builds
  `discovery_url` from the configured `issuer` and fetches the
  `jwks_uri` the document names, unless `jwks_uri` is configured
  explicitly, which short-circuits discovery but not the JWKS fetch.
  Whether the OpenViking container on its chosen node can resolve and
  reach `vault.lab.orangecluster.nl` is UNCERTAIN: it depends on the
  node's DNS and egress, which this session could not test from inside a
  Nomad alloc. Supporting, not decisive: `oauth2-proxy-registry-ui` is
  host-networked on that same node and performs its own OIDC discovery
  against the same issuer at startup, and Consul reports it passing, so a
  job on radxa demonstrably reaches the issuer today. That is a different
  runtime and a different image, so it lowers the risk rather than
  settling it. Verify from the OpenViking alloc before S5 is called done.
  probe: curl -sS http://192.168.2.30:8500/v1/health/service/oauth2-proxy-registry-ui returned node radxa 192.168.2.50 with checks Serf Health Status passing and oauth2-proxy ping passing (read this session).
  Source: https://github.com/volcengine/OpenViking/blob/v0.4.17.1/openviking/server/auth/plugins/oidc.py#L224-L270
