# OpenViking deployment files

What each file here is, and the one thing this repo cannot do for you.

| File | Role |
|---|---|
| `Dockerfile.openviking` | The derived image: upstream OpenViking plus `ov-postgres` and `psycopg[binary,pool]`. |
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
$ just build     # upstream image + the Postgres backend
$ just verify    # does the adapter import
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

## The config

`ov.conf.json` is the document OpenViking reads. Terraform substitutes the two
addresses it discovers at plan time and hands the result to the jobspec, which
wraps it in the Vault lookups that fill in the credentials. Nothing here holds
a secret.

`scripts/check_openviking_config.py` asserts the settings in it that fail
silently, and runs in pre-commit against this file.
