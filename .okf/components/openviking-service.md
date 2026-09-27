---
type: component
title: The OpenViking service
description: "How the openviking job is assembled: a hand-built derived image started as python -m ov_ext, ov.conf.json round-tripped through Terraform and filled by Nomad, a liveness and a readiness check sized off a measured 44-minute boot, and the pre-commit guard that asserts the settings which fail silently."
tags: [openviking, ov-ext, ov-postgres, nomad, config-guard, pre-commit]
status: stable
generated:
  by: claude-opus/5.5
  at: 2026-09-27
sources:
  - id: openviking-jobspec
    resource: git:3ec5d1e:deployments/applications/services/openviking.hcl
    note: "The working tree differs from 3ec5d1e (uncommitted operator edits), and this concept describes the working tree."
  - id: ov-conf
    resource: git:3ec5d1e:deployments/applications/services/openviking/ov.conf.json
    note: "The working tree differs from 3ec5d1e (uncommitted operator edits), and this concept describes the working tree."
  - id: openviking-dockerfile
    resource: git:3ec5d1e:deployments/applications/services/openviking/Dockerfile.openviking
  - id: openviking-justfile
    resource: git:3ec5d1e:deployments/applications/services/openviking/justfile
  - id: openviking-readme
    resource: git:3ec5d1e:deployments/applications/services/openviking/README.md
  - id: config-guard
    resource: git:3ec5d1e:scripts/check_openviking_config.py
    note: "The working tree differs from 3ec5d1e (uncommitted operator edits), and this concept describes the working tree."
  - id: app-services
    resource: git:3ec5d1e:deployments/applications/services.tf
  - id: app-secrets
    resource: git:3ec5d1e:deployments/applications/secrets.tf
  - id: alert-rules
    resource: git:3ec5d1e:deployments/infrastructure/services/grafana/alert-rules.yaml
    note: "The working tree differs from 3ec5d1e (uncommitted operator edits), and this concept describes the working tree."
  - id: OV1-openviking-service
    resource: loop:OV1-openviking-service
  - id: OV2-openviking-user-scoped-resources
    resource: loop:OV2-openviking-user-scoped-resources
  - id: OV3-openviking-vault-identity
    resource: loop:OV3-openviking-vault-identity
---

# The OpenViking service

OpenViking is the context store Hermes and people write memories and resources
into. It runs as job `openviking` on `radxa-dragon-q6a` (192.168.2.50), port
1933. The user-facing surface is `docs/reference/openviking.md`, how identity
works is `docs/explanation/openviking-identity.md`, and the database it adopted
is [the OpenViking database](/components/openviking-database.md). This page is
about how the job is built and what checks it.

The operator has uncommitted edits to `openviking.hcl`, `ov.conf.json`,
`scripts/check_openviking_config.py`, `.pre-commit-config.yaml`,
`grafana/alert-rules.yaml` and a comment in `Dockerfile.openviking`. This page
describes the working tree, and says so where it differs from `3ec5d1e`.

## The pieces and where they come from

| Piece | Where | Root |
|---|---|---|
| Jobspec | `deployments/applications/services/openviking.hcl` | applications |
| Config document | `deployments/applications/services/openviking/ov.conf.json` | applications |
| Image build | `Dockerfile.openviking`, `justfile`, `README.md` beside it | none, an operator step |
| `nomad_job.openviking`, `local.openviking_ov_conf` | `deployments/applications/services.tf` | applications |
| Secrets it reads: `default/openviking/{db,minio,bifrost,root}` | `deployments/applications/secrets.tf` | applications |
| Bifrost virtual key | `bifrost_virtual_key.openviking`, see [Bifrost](/components/bifrost.md) | applications |
| `openviking_data` host volume | `deployments/infrastructure/services.tf` | infrastructure |
| Identity-token roles, the `openviking-user` group | `deployments/infrastructure/oidc.tf`, `identity.tf`, `machine_roles.tf` | infrastructure |
| Edge route `openviking-api.lab` | backend `ovapi` in `deployments/infrastructure/services/haproxy.hcl` | infrastructure |
| Alerts and dashboard | `alert-rules.yaml`, `grafana/openviking.json` | infrastructure |
| Config guard | `scripts/check_openviking_config.py`, hook `openviking-config` | repo |

Apply infrastructure first. The job needs the host volume and the identity
roles, and within the applications root it `depends_on` the Postgres database
and the Bifrost key. `nomad_job.openviking` sets `detach = false`, so the apply
waits for the deployment rather than returning at registration.

## The image

The upstream image cannot run this config. `storage.vectordb.backend` names
`ov_postgres.adapter.PgVectorCollectionAdapter`, which OpenViking imports by
dotted path at startup, and upstream ships neither that package nor psycopg.
`Dockerfile.openviking` installs, with `--no-deps` into the venv's
site-packages, `ov-postgres` at `ov-postgres-v0.6.0` and `ov-ext` at
`ov-ext-v0.7.1` from `JasperHG90/openviking_extensions`, plus
`psycopg[binary,pool]==3.2.3`. `--no-deps` stops pip reinstalling OpenViking
and about 160 packages over the base image's locked venv.

Both tags are pinned in `services.tf` (`openviking_base_image`,
`openviking_image`), and the `justfile` reads both lines, so the image built and
the image deployed cannot drift. The base is read rather than derived because it
is a different repository (`volcengine` against `jasperhg90`), and `just build`
refuses a `:latest` base. Nothing in CI builds it.

## The command bypasses the entrypoint

The jobspec sets `command = "/app/.venv/bin/python"` and
`args = ["-m", "ov_ext", ...]`. `ov_ext` patches OpenViking's retriever (the
keyword leg, the diversity pass) and runs reflection, then starts the ordinary
server. OpenViking has no plugin hook, so a wrapper process is the only way in
short of a fork. If either line goes, the image entrypoint starts the stock
server, which comes up healthy and quietly loses both features.

Naming the command also drops three things the entrypoint did. It wrote the
config, which the template already does. It polled `/health` for 120s and
failed the task if the server never bound, which nothing replaces except the
`OpenVikingDown` alert. And it honored `OPENVIKING_SERVER_*` variables, which
are now dead. The venv python is named rather than a console script because a
`--target` install puts scripts off `PATH` and stamps them with the wrong
interpreter.

## How the config reaches the task

`ov.conf.json` holds two kinds of placeholder. `${...}` tokens are filled by
Terraform's `templatefile` with the two addresses it discovers from Consul
(MinIO and Postgres). `templatefile` errors on an unknown token, so a typo
cannot reach the service. `{{ $minio... }}` style tokens pass through untouched
and are filled by Nomad's template engine. `local.openviking_ov_conf` wraps the
result in `jsonencode(jsondecode(...))`, so a syntax error fails the plan.
Static addresses stay literal in the JSON so the guard can assert them.

In the jobspec, the template binds each of the four secrets to its own
variable. Nested `with secret` blocks would rebind the dot, and every
`.Data.data.*` would silently read the innermost secret. The template body is
live consul-template, so a comment inside it must not contain a doubled brace.
Reflection's Postgres DSN goes to its own file, `secrets/reflect-deltas.env`,
not the env block, because env is stored in the jobspec and printed by
`nomad job inspect`.

`server.root_api_key` is still rendered from `default/openviking/root`. Under
`auth_mode: "oidc"` the auth plugin never reads it. OV1's reflection records
that key as a credential added on a false premise, so it reads as live while
granting nothing.

## Health checks, sized off a measured boot

These are the working tree's checks. At `3ec5d1e` there was one check, on
`/ready`, with `check_restart` and a 60s grace.

- **`openviking alive`** probes `/health`, which answers from the process and
  reaches no backend. It is the only check that may restart the task, with
  `check_restart { limit = 4, grace = "60m" }`. A clean boot bound the port in
  115s. The boot after an unclean stop took 44m46s, because ov-ext's reflect
  sweep runs its LLM pass before the server binds. The old 60s grace killed at
  about 180s and turned one restart into a permanent loop.
- **`openviking ready`** probes `/ready` every 60s with a 15s timeout and has
  no `check_restart`. `/ready` dials MinIO, Postgres, and Bifrost on to embark.
  A restart hanging off it killed healthy servers, and measurement put the
  stall inside OpenViking's own event loop, not the CPU quota (zero throttled
  periods) or the backends. Cycling the task repairs none of that.
- `restart` (3 attempts in 4h, `mode = "fail"`) is written out because a
  failing boot cycles in about 62 minutes, so the 30m default interval never
  counts three restarts and `mode = "fail"` never hands off to rescheduling.
- `update` (`healthy_deadline = "60m"`, `progress_deadline = "75m"`) is written
  out because the default 5m deadline marks a 44m46s boot as a failed
  deployment while the task is still coming up correctly.

Nothing routes on `/ready`: HAProxy's `ovapi` backend has its own check. The
alerts `OpenVikingNotReady` (a reachable service with a sick backend) and
`OpenVikingDown` (`up == 0` for 50m) replace the restart. The known gap, a
restart loop with fast boots, is recorded above those rules in
`alert-rules.yaml`.

`resources` has `memory = 1536` and no `memory_max`: oversubscription is off,
so the old `memory_max = 2560` was headroom the kernel never granted.

## Retrieval and reflection knobs

The `OV_RETRIEVAL_*` env vars restate ov-ext's defaults on purpose, so an
upstream default change cannot move retrieval without a commit here.
`OV_RETRIEVAL_MMR_LAMBDA` matters most: the diversity pass runs only below
1.0. The rerank pooling caps (4 calls, 20 documents) came with `cb2854d` to
cut the fan-out to embark. A single search was measured fanning out to 30-37
embedding calls, and the jobspec says where that multiplier is not, so read
ov-ext at the pinned tag before tuning it. `OV_REFLECT_*` turn on hourly
reflection for account `lab`, user `jasper`, with the model
`ollama/deepseek-v4.1-flash` (`b832604`). A Postgres lock DSN template is
commented out.

`OPENVIKING_WEB_STUDIO_DIR = "/nonexistent"` unmounts Web Studio, which answers
without a token. See
[ADR 0009](/decisions/0009-openviking-has-no-browser-surface.md).

## The config guard

`scripts/check_openviking_config.py` asserts the settings that fail while the
service looks healthy. It reads `ov.conf.json` as JSON, so it can tell the
vector store's `backend` from the blob store's, which is declared first. It
reads two things from the jobspec: the Studio variable's value, and the
`command` and `args` that select `ov_ext`. `--self-test` checks the checker.
The list of assertions is in `docs/reference/openviking.md`.

Several constants tie it to other files and must move together:

- `EXPECTED_AUDIENCE` equals `local.openviking_audience` in
  `deployments/infrastructure/oidc.tf`, and `EXPECTED_ISSUER` equals what Vault
  advertises. Two roots, one literal each.
- `ALLOWED_CUSTOM_PARAMS` is read off `PgVectorParams` at the ov-postgres tag
  the Dockerfile pins. Moving the pin means re-deriving it.
- `VISION_MODELS` lists models measured to accept an image through Bifrost.
  See [Measure a vision model before OpenViking uses
  it](/practices/openviking-vision-models.md).
- `EXPECTED_KEYWORD_FIELDS` names five columns. From ov-postgres 0.3.0, leaving
  the key unset while `store_content` is on adds `content` and changes the index
  expression, and nothing re-keys an existing collection. `3ec5d1e` carried a
  sixth field. The working tree drops it back to five. The live index has not
  been read back to confirm which one it carries.

The pre-commit hook `openviking-config` is new in the working tree. Before it,
nothing ran the script, and two settings drifted while it sat red: the module
name (`ov_retrieval`, renamed to `ov_ext`) and `keyword_fields`. The hook sets
`pass_filenames: false` and matches the jobspec, the JSON and the script, so a
commit touching any one checks the pair.

The guard is static. `scripts/ov_identity_probe.py` and
`docs/how-to/verify-an-openviking-deployment.md` are the runtime half.

## History

OV1 stood the service up and was not deployed inside the ticket. OV2 gave each
person an account and migrated nothing, so older content stays in `lab`. OV3's
Vault identity design was dropped from the loop and shipped outside it as
`5ab5e30` on 2026-09-07, with identity carried in two claims rather than the
entity rename the plan proposed. `d25daa7` removed the oauth2-proxy and Web
Studio. The account provisioner is gone because no admin route is reachable
under `oidc`, as the block after `nomad_job.driftwatch` in `services.tf`
explains.
[ADR 0007](/decisions/0007-openviking-static-key-has-no-claim-policy.md) covers
the static MinIO key, and
[ADR 0008](/decisions/0008-openviking-rerank-goes-through-bifrost.md) the rerank
route.

## Related

- [ov-dash](/components/ov-dash.md)
- [Hermes](/components/hermes.md)
- [Vault human identity](/components/vault-identity.md)
- [The HAProxy edge](/components/edge-proxy.md)
