# OpenViking deployment files

What each file here is, and the one thing this repo cannot do for you.

| File | Role |
|---|---|
| `Dockerfile.openviking` | The derived image: upstream OpenViking plus `ov-postgres`, `ov-retrieval` and `psycopg[binary,pool]`. |
| `justfile` | Builds and pushes that image. |
| `ov.conf.json` | The service config, substituted by Terraform and rendered by Nomad. |

## You build and push the image

**The image this job runs is not built by CI. Building and pushing it is an
operator step.**

`storage.vectordb.backend` in the jobspec names
`ov_postgres.adapter.PgVectorCollectionAdapter`, a dotted import path.
OpenViking resolves it with `importlib` at startup. The upstream image carries
neither `ov-postgres` nor `psycopg`, so against the upstream image that backend
does not exist and the server fails to start.

```console
$ just show      # which tags this would act on
$ just build     # upstream image + the Postgres backend + the retrieval wrapper
$ just verify    # does the adapter import, and does the entry point start
$ just push      # to ghcr.io
$ just release   # build and push
```

Both tags come from `deployments/applications/services.tf`, so what gets built
and what Terraform deploys cannot drift. Change the version there, not here.

Unlike embark's justfile, which derives its base by stripping `-jetson` from
its own tag, this one READS the base from its own `openviking_base_image` line.
The two images live in different registries, so no string relates them, and the
pin is what binds the premises to the artifact. `just build` refuses a
`:latest` base for that reason.

Nodes already authenticate to `ghcr.io` via
`bootstrap/playbooks/configure_podman.yml`, so no per-job pull credential is
needed.

## The job does not run `openviking-server`

It runs `python -m ov_retrieval`, named by `command` and `args` in
`services/openviking.hcl`. That wrapper patches OpenViking's retriever to add a
keyword leg and a diversity pass, then starts the ordinary server. OpenViking
has no plugin hook, so a wrapper process is the only way in that does not fork
it.

Dropping those two lines is silent: the image entrypoint takes over, the stock
server starts, `/ready` passes, and every search quietly loses both. That is
why `scripts/check_openviking_config.py` asserts them.

## The config

`ov.conf.json` is the document OpenViking reads. Terraform substitutes the two
addresses it discovers at plan time and hands the result to the jobspec, which
wraps it in the Vault lookups that fill in the credentials. Nothing here holds
a secret.

`scripts/check_openviking_config.py` asserts the settings in it that fail
silently, and runs in pre-commit against this file. Its allowlist of
`custom_params` keys is read off `PgVectorParams` at the ov-postgres tag the
Dockerfile pins, so moving that pin means re-deriving the list.

### `store_content` does not backfill

`store_content` fills the `content` column for writes from the moment it is
on. It cannot reach back: rows written before it hold `''`, and ov-postgres's
`backfill_defaults` only fills NULLs, so it skips them. Existing rows gain
their bodies only by being re-indexed through OpenViking.

`keyword_fields` is spelled out even though it names the five defaults, and
that is deliberate. From ov-postgres 0.3.0 `resolved_keyword_fields` appends
`content` whenever `store_content` is on and the list is left unset, so the
default became a six-column index. Writing the five out opts back out, which
is what that docstring provides for.

Indexing bodies is worth doing, but not yet, and not as a side effect of
wiring up retrieval. It changes the index expression, so the live collection
needs a manual `ensure_indexes` re-key, because `create_index` never re-runs
on a collection that already exists, and until that runs keyword search scans
the whole table. Every existing row also still holds an empty `content`, per the
paragraph above, so today the change would rebuild a large index over almost
nothing.

Revisit once bodies have accumulated. Flipping it is one deleted line and the
re-key, in that order.
