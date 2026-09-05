---
verdict: fail
tree: 2ae69df79a7a420cf021b7296471fc4e86c50a42
---

# Adversarial review — OV1-openviking-service

No scope-binding block. My briefing carried the tree fingerprint but no
`scope:` digest and no `verdict_binding_inputs`, and the rules forbid writing a
digest I computed myself. The three lines are omitted, so this verdict falls
back to the whole-tree binding, which is stricter.

## Deterministic floor

`loopctl verify-eval-substance OV1-openviking-service` → `valid`, exit 0, no
advisories. `loopctl verify --expect-tree 2ae69df7…` → `ok`, exit 0. Proceeded
to the semantic pass.

## Gate

I re-ran `just pre_commit` myself: exit 0, 1m16s. Trust stamp at
`.loop/scratch/OV1-openviking-service.adversarial/trust-stamp.json`.

One thing the green stamp hides. Two of the new hooks printed
`(no files to check) Skipped`, because `deployments/applications/services/openviking.hcl`
and `scripts/check_openviking_config.py` are untracked in this worktree and
`pre-commit run --all-files` walks `git ls-files`. The harness gate runs
`git add --intent-to-add -A .` first, so they will fire at commit time; a bare
`just pre_commit` in this worktree does not exercise them. I forced every
affected hook with explicit `--files`: `openviking-config-guard`,
`openviking-config-guard-self-test`, `ruff`, `ruff-format`, `mypy` (strict),
`nomad-fmt`, `end-of-file-fixer`, `detect-private-key` all pass, and
`terraform-fmt` / `terraform-validate` pass over both roots. So the gate result
is real; it just was not reached by my invocation unaided.

Nothing below is a gate failure. The gate cannot see any of it.

---

## Blocking

### B1. The derived image cannot be built. The plan predicted this exact line.

`deployments/applications/services/openviking/Dockerfile.openviking:29`

```
    "ov-postgres @ git+https://github.com/JasperHG90/openviking_extensions@ov-postgres-v0.2.0#subdirectory=packages/ov-postgres"
```

There is no `packages/` directory at that tag. The GitHub trees API for
`ov-postgres-v0.2.0` returns exactly `.claude`, `.github`, `.gitignore`,
`.pre-commit-config.yaml`, `LICENSE`, `README.md`, `aim.lock.toml`, `aim.toml`,
`minio-openviking-rw.json`, `pyproject.toml`, `src`, `tests`, `uv.lock`.
`raw.githubusercontent.com/.../packages/ov-postgres/pyproject.toml` returns 404;
`.../src/ov_postgres/adapter.py` returns 200.

Reproduced, not inferred:

```
$ uv pip install --dry-run --no-deps "ov-postgres @ git+https://github.com/JasperHG90/openviking_extensions@ov-postgres-v0.2.0#subdirectory=packages/ov-postgres"
  × Failed to download and build `ov-postgres @ git+...#subdirectory=packages/ov-postgres`
  ╰─▶ The source distribution ... has no subdirectory `packages/ov-postgres`
EXIT=1
```

The same requirement without the fragment exits 0 and resolves
`ov-postgres @ git+...@9466e7ee`.

The plan says this in advance. P12: *"At that tag the package lives at
`src/ov_postgres`, NOT under `packages/ov-postgres`, so a `#subdirectory=`
fragment pinned to that tag would fail."* The implementation wrote the
fragment anyway.

Consequence: `just build` fails on the first `RUN`. No image exists, so the
eval row *"R2 the image actually carries the extension"* cannot pass, and
`storage.vectordb.backend` names a dotted path that resolves only if this
install succeeds. R2 is, in the plan's own words, "the whole of R2".

Fix: delete `#subdirectory=packages/ov-postgres`.

### B2. The root API key is defended by a false claim and consumed by nothing.

`deployments/applications/secrets.tf:273-275`

```
### The root API key. server.auth_mode is "oidc", so this is not the identity
### source for ordinary callers; OpenViking refuses to start bound to a
### non-loopback host without one.
```

The second clause is false at the pinned tag. `openviking/server/config.py`:
`get_effective_auth_mode()` returns the explicit `auth_mode` when one is set, so
with `"auth_mode": "oidc"` the mode never falls through to `dev`;
`validate_server_config` then runs `plugin_cls().validate_config(config)` for
that mode alone. `OIDCAuthPlugin.validate_config`
(`openviking/server/auth/plugins/oidc.py`) checks three things and only three:
the `oidc` section is present, `issuer` is non-empty, and one of `audience` /
`client_id` is set. `root_api_key` does not appear in that file at all, nor in
`app.py`, `bootstrap.py`, `identity.py` or `registry.py`. The non-loopback
refusal is `DevAuthPlugin.validate_config`
(`openviking/server/auth/plugins/dev.py:46-64`), which under `oidc` never runs.
P8 already said as much: *"there is no chain and no fallback, so `root_api_key`
is not consulted under `oidc`."*

Two things follow. First, `random_password.openviking_root_key` and
`vault_kv_secret_v2.openviking_root_key` (`secrets.tf:276-287`) are outside the
declared code surface: §7 names `db`, `bifrost` and `minio` and nothing else.
Second, and worse, they mint a live 48-character root credential, write it to
Vault, and render it into the config on disk — for a service that never reads
it. That is the shape Q1's resolution names as the failure this ticket exists
to avoid: *"config that reads as live and grants nothing."* A false comment is
what is holding it up.

Fix: drop both resources, the `openviking_root_key_secret` templatefile
variable (`services.tf:415`) and the `root_api_key` block
(`openviking.hcl:156-158`). If some other code path does read it, replace the
comment with a citation to that path — I looked in the five files above and
found none.

---

## High

### H1. R9 is half-implemented: no `OAUTH2_PROXY_COOKIE_EXPIRE`.

`deployments/infrastructure/services/oauth2-proxy-openviking.hcl:54-68` sets
thirteen variables. `OAUTH2_PROXY_COOKIE_EXPIRE` is not among them.

R9 is two clauses: *"The new proxy sets `OAUTH2_PROXY_PASS_AUTHORIZATION_HEADER="true"`
**and** `OAUTH2_PROXY_COOKIE_EXPIRE` equal to the client's `id_token_ttl`
(3600s)."* Only the first landed.

oauth2-proxy v7.13.0's own configuration reference, line 124: `--cookie-expire`
defaults to `168h0m0s`. `vault_identity_oidc_client.openviking` sets
`id_token_ttl = 3600`. Vault advertises no refresh grant (P3), so nothing
renews the forwarded token. The session therefore stays valid for seven days
while the ID token OpenViking validates dies after one hour. That is section
9's failure mode 5 word for word: *"Works for an hour, then 401s with the
cookie still valid and no re-login prompt."* It is the entire reason R9 names
the setting.

The eval's R9 row checks only `PASS_AUTHORIZATION_HEADER`, so this scores green
against the eval and red against the requirement. I score the requirement.

Fix: `OAUTH2_PROXY_COOKIE_EXPIRE="3600s"`.

### H2. `SET_AUTHORIZATION_HEADER` is the wrong flag, and two comments say otherwise.

`deployments/infrastructure/services/oauth2-proxy-openviking.hcl:68`

```
        OAUTH2_PROXY_SET_AUTHORIZATION_HEADER="true"
```

The briefing asked whether both flags are what v7.13.0 needs. They are not.
From that release's configuration reference:

- line 146 — `--pass-authorization-header`: *"pass OIDC IDToken to upstream via
  Authorization Bearer header"*
- line 142 — `--set-authorization-header`: *"set Authorization Bearer **response**
  header (useful in Nginx auth_request mode)"*

Confirmed in the source. `pkg/apis/options/legacy_options.go`:

```go
if l.PassAuthorization {
    requestHeaders = append(requestHeaders, getAuthorizationHeader())
```

sits in `getRequestHeaders`, while

```go
if l.SetAuthorization {
    responseHeaders = append(responseHeaders, getAuthorizationHeader())
}
```

sits in `getResponseHeaders`. Both call `getAuthorizationHeader()`, which is
`Authorization: Bearer <id_token>`.

So line 67 does the job and line 67 alone. Line 68 contributes nothing to the
upstream hop and instead attaches the raw Vault ID token to every response the
proxy hands the browser. It is redundant in the direction that matters and
leaky in the direction that does not.

Both comments assert the opposite. `oauth2-proxy-openviking.hcl:12-14`: *"Drop
the two settings below and the browser flow still looks correct while
OpenViking sees an unauthenticated request."* `docs/openviking.md:28-30` repeats
it: *"The two settings that make the second hop work…"* Dropping line 68 changes
nothing about what OpenViking sees.

Fix: delete line 68; make both comments name `PASS_AUTHORIZATION_HEADER` alone.

---

## Medium

### M1. Four credentials land in `local/ov.conf`, not `secrets/`.

`deployments/applications/services/openviking.hcl:169`

```
        destination = "local/ov.conf"
```

The Postgres password (inside the DSN, `:125`), the MinIO secret key (`:112`),
the Bifrost virtual key (`:139`, `:148`) and the root key (`:157`) all render
into that file.

§7 asked for the split: *"`secrets/file.env` template for credentials and a
`local/ov.conf` template for the config, following `registry-ui.hcl:87-102` for
the Vault template shape."* P17 exists to make that split possible — it records
that OpenViking runs `os.path.expandvars` over the raw config text before
parsing, and that a placeholder escapes as `$${VAR}` through `templatefile`.
None of that mechanism is used.

The named precedent goes the other way too: `registry-ui.hcl:104` writes its
credential-bearing JSON to `secrets/registry.json`. Across the repo, 25 of 27
templates that interpolate a Vault secret target `secrets/`; the exceptions are
`hermes.hcl` (`local/hermes.env`) and `prometheus.hcl` (`local/prometheus.yml`),
so the convention is not absolute — which is why this is medium and not
blocking. But Nomad's `secrets/` is a per-task tmpfs whose contents are never
written to disk, and `local/` is a plain directory in the allocation dir. Four
live credentials now persist to disk on radxa.

Fix is two lines: `destination = "secrets/ov.conf"` and
`OPENVIKING_CONFIG_FILE = "/secrets/ov.conf"` (`:79`).

### M2. A third pip install that R2 does not declare, pulling 165 packages.

`deployments/applications/services/openviking/Dockerfile.openviking:37-42`

```
# server.auth_mode = "oidc" needs the auth extra. The image carries jose and
# httpx already, so this resolves to little, but naming it keeps the image
# correct if upstream moves a dependency behind the extra.
RUN /usr/local/bin/python3.13 -m pip install --upgrade \
    --target /app/.venv/lib/python3.13/site-packages \
    "openviking[auth]==0.4.17.1"
```

R2 says "two `--target` pip installs". This is a third, and "resolves to little"
is measurably wrong:

```
$ uv pip install --dry-run --target ... "openviking[auth]==0.4.17.1"
Resolved 165 packages in 56ms
Would install 165 packages
```

Among them OpenViking itself, `volcengine-python-sdk`, twelve `tree-sitter-*`
grammars, `twisted`, `tokenizers`. The `--target` is the image's own venv
site-packages and `--upgrade` explicitly tells pip to replace what is already
there, so this reinstalls upstream's locked dependency set with a freshly
resolved one on top of the very interpreter that runs the server. P11 already
established that the image carries `jose` and `httpx`, which is the whole of the
`auth` extra's benefit here.

Fix: delete the third `RUN`.

### M3. The `custom_params` allow-list is missing five keys R3 declares, and its failure message is false for them.

`scripts/check_openviking_config.py:35-48` holds ten keys. R3 enumerates
fifteen. Missing: `tz_policy`, `min_pool_size`, `max_pool_size`,
`connect_timeout`, `application_name`.

All five are real declared fields on `PgVectorParams` at `ov-postgres-v0.2.0`
(`src/ov_postgres/config.py` — declared attrs `dsn`, `db_schema`,
`table_prefix`, `index_method`, `index_options`, `create_extension`,
`iterative_scan`, `distance`, `keyword_fields`, `text_search_config`,
`tz_policy`, `min_pool_size`, `max_pool_size`, `connect_timeout`,
`application_name`, with `schema` as the alias of `db_schema`).

Demonstrated against the real jobspec: adding `"max_pool_size": 8` makes the
gate print

```
custom_params carries ['max_pool_size'], which ov-postgres forbids
(its config model is extra=forbid, so this fails at startup)
```

which is not true. The gate fails closed, so no bad config escapes; the cost is
that a future implementer making a legal change is told by a gate that upstream
forbids it.

Fix: add the five keys.

---

## Low

- **L1.** `deployments/applications/storage.tf:35` — `# creation (datalake, openviking, mlflow-artifacts have none).`
  This change gives `openviking` a Vault KV entry (`secrets.tf:254-261`), so the
  parenthetical is now false. `.claude/rules/minimal-comments.md` says existing
  comments stand "unless your change makes them wrong". This change makes it
  wrong.
- **L2.** `deployments/applications/secrets.tf:235` — `### All three under the job's own prefix.`
  Four resources follow. Folds into B2 if the root key goes.
- **L3.** `deployments/applications/services.tf:405` — `openviking_base_image = "ghcr.io/volcengine/openviking:v0.4.17.1"`
  is passed to `templatefile` but never referenced in `openviking.hcl` (grep
  count 0). R2 is satisfied — the line is in `services.tf` and `just show`
  correctly prints `base image : ghcr.io/volcengine/openviking:v0.4.17.1` — but
  a `locals` block would not read as a value the jobspec consumes.
- **L4.** `scripts/check_openviking_config.py:98-106` — the rerank assertion
  greps for `8080` anywhere in the block. The host in `api_base` is
  `${bifrost_host}`, a `templatefile` variable the checker cannot resolve, so
  the eval's R5 claim ("points at Bifrost, NOT at `192.168.2.46:8000`") is
  measured by the port alone; changing `bifrost_host` at `services.tf:410`
  keeps the gate green. The `\n\s{10}\}` and `\n\s{12}\}` block anchors also
  hard-code indentation depth. Both fail closed. Recorded so the check is not
  mistaken for a stronger measure than it is.
- **L5.** R1's placement precondition is unretired. R1 calls headroom on
  `radxa-dragon-q6a` "a precondition, not an assumption"; P10 records it
  UNCERTAIN (Nomad returned 403). The constraint is written
  (`openviking.hcl:21-24`) and the job asks for `cpu = 1000`, `memory = 1536`,
  `memory_max = 2560` (`:173-177`) on the busiest node. Nothing in the diff or
  `docs/openviking.md` records a measurement. Deploy-time obligation, not
  commit-blocking; the eval's R1 row is a runtime row this cycle does not score.

---

## What I confirmed clean (do not re-derive next cycle)

- **Every key in the rendered `ov.conf` is legal at v0.4.17.1.** Section 9's
  failure mode 6 is the one I expected to catch something and it did not. All
  of these are `extra="forbid"` and all of them accept what the template sends:
  `StorageConfig{workspace, agfs, vectordb}`, `AGFSConfig{backend, s3}`,
  `S3Config{bucket, region, access_key, secret_key, endpoint, use_ssl,
  use_path_style}`, `VectorDBBackendConfig{backend, name, index_name,
  distance_metric, custom_params}` whose `validate_config` explicitly exempts a
  dotted backend from the standard-backend list,
  `EmbeddingModelConfig{provider, model, dimension, api_base, api_key}`,
  `RerankConfig{provider, model, api_base, api_key, timeout}`,
  `ServerConfig{host, port, auth_mode, root_api_key, public_base_url, oidc}`,
  `OIDCConfig{issuer, client_id, audience, jwks_uri}` with no `identity` key,
  which is R10. `index_method: "flat"` is a documented `PgVectorParams` value.
- **The OIDC chain closes end to end, on one Vault client (R8, R8a).** The
  client is created in infrastructure, registered against key `lab`, appended to
  `local.oidc_provider_client_ids` (`oidc.tf:106`), and its `client_id` /
  `client_secret` written to `default/oauth2-proxy-openviking/oidc`, which the
  proxy reads as `OAUTH2_PROXY_CLIENT_ID`. The applications root reads the same
  client back by name through `data.vault_identity_oidc_client_creds.openviking`
  and feeds one value into both `client_id` and `audience`. The issuer strings
  match byte for byte: `local.vault_oidc_issuer` is
  `https://vault.lab.orangecluster.nl/v1/identity/oidc/provider/lab`, and the
  infra side builds the same from `var.vault_issuer_host` (default
  `vault.lab.orangecluster.nl`) and provider name `lab`. `jwks_uri` is issuer +
  `/.well-known/keys`, which is Vault's real JWKS path. The only break in the
  chain is H2's wrong flag, and it is additive rather than missing.
- **R13 holds, re-verified independently.** I mirrored the guard and the three
  jobspecs into scratch: clean run exit 0; after planting
  `OAUTH2_PROXY_SKIP_AUTH_ROUTES` in `oauth2-proxy-openviking.hcl`, exit 1
  naming that file. The `files:` regex at `.pre-commit-config.yaml:83` matches
  all three proxy filenames and rejects a hypothetical fourth.
- **The `_vectordb_backend` scoping fix has a real positive control.** Reverting
  it to `_value(text, "backend")` makes `--self-test` fail with
  `self-test: clean config was flagged: storage.vectordb.backend is 's3'`. The
  widened `CLEAN` fixture is doing the work the author claimed. Mutating the
  real jobspec's backend, dimension, a `custom_params` key, the rerank port,
  `auth_mode` and `audience` each yields exactly one matching failure; the
  unmutated file yields none. The other unscoped `_value` lookups (`auth_mode`,
  `client_id`, `audience`) have exactly one occurrence each in the file, so no
  current config shape misreads.
- **R11 and Q1's guardrail hold.** No new `.tf` in either root; the data source,
  firewall rule, job and virtual key in `services.tf`, the KV writes and the
  `random_password` in `secrets.tf`, the OIDC client in `oidc.tf`, the host
  volume and job in infra `services.tf` — every block in its subsystem file per
  `.claude/rules/terraform-file-layout.md`. Both `storage.tf` files are byte
  identical to HEAD, there is no `minio_iam_policy` named `openviking`, and the
  reason is recorded in the jobspec header at `openviking.hcl:3-10`.
- **R6, R7, R12.** All four secret paths sit under
  `secret/data/default/openviking/`, which is what
  `bootstrap/roles/nomad_server/templates/vault_nomad_workloads.hcl.j2:1-7`
  grants job `openviking` in namespace `default`.
  `bifrost_virtual_key.openviking` carries
  `depends_on = [null_resource.bifrost_ready]` with a single `provider_configs`
  entry, so alphabetical order is trivially met. The `openviking` firewall rule
  admits only 192.168.2.50 to 1933, the `oauth2_proxy` rule gains 4182 from
  192.168.2.30 alone, and the `embark` rule is untouched.
- Terraform map keys all resolve: `minio_accesskey.users["openviking"]`,
  `postgresql_role.role["openviking"]`, `random_password.password["openviking"]`
  are each declared in `storage.tf` / `database.tf`.
- `docs/openviking.md:101` cites `scripts/bifrost_smoke.py`, which exists. The
  "through 1.6.11" boundary at `:70` is supported by U7's measured premises, not
  invented here.

## Verdict

**fail.** Two blocking findings. B1 means the artifact this ticket is built
around cannot be produced, and the plan warned about the exact line in P12. B2
ships a live unused root credential behind a false claim about upstream, which
is the failure mode Q1's resolution was written to prevent. H1 and H2 are both
one-line fixes in the same file and should ride along, since between them the
proxy currently leaks the ID token to the browser and holds a session seven
days past the token's life.

The rest of the change is in good shape. The OIDC wiring is correct, the
config validates against every `extra="forbid"` model upstream declares, the
layout rule is honored, and R13's guard genuinely covers the new proxy.
