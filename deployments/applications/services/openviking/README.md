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

Both costs above are about the old `openviking` schema. Schema `openviking_v2`
starts empty with `store_content` on, so its rows carry bodies from the first
write, and its index is built from whatever `keyword_fields` says at first
boot. Adding `content` before the cutover would cost no re-key. The five
fields stay because that is a separate choice from starting over.

## Cutover to the v2 store

OpenViking started over on bucket `openviking-v2`, schema `openviking_v2` and
host volume `openviking_data_v2`. The old bucket `openviking`, schema
`openviking` and volume `openviking_data` stay as they are, as a read-only
backup. The `openviking` storage key loses all access to the old bucket, and
only the backup and restore keys still reach it. Why is in
`.okf/decisions/0021-openviking-starts-over-on-a-v2-store.md`.

Run these in one sitting. The nightly `backup-s3` fails between the two
applies, because it syncs a bucket that does not exist yet.

1. Stop the job, so the hourly reflection sweep, Hermes and leo-consumer stop
   writing to the old store:

   ```console
   $ nomad job stop openviking
   ```

2. Record a baseline of the old store, so you can show afterwards that nothing
   touched it. Use the backup key, `default/backup-s3/seaweedfs`, which keeps
   read access to `openviking`, with an rclone remote `seaweedfs` pointed at
   `http://192.168.2.29:8333`:

   ```console
   $ rclone lsf -R --format pst seaweedfs:openviking > openviking.lsf
   $ rclone md5sum seaweedfs:openviking > openviking.md5
   ```

   For the schema, as the `openviking` role (`default/openviking/db`) on
   `192.168.2.30`, save the per-table row counts, the tuple counters, and a
   hash of the dump:

   ```console
   $ psql -h 192.168.2.30 -U openviking -d openviking -c \
       "SELECT relname, n_live_tup, n_tup_ins + n_tup_upd + n_tup_del AS writes
          FROM pg_stat_user_tables WHERE schemaname = 'openviking' ORDER BY relname" \
       > openviking.stats
   $ pg_dump -h 192.168.2.30 -U openviking -d openviking --schema=openviking \
       | grep -v -E '^\\(un)?restrict ' | sha256sum > openviking.dump.sha256
   ```

   pg_dump 17.6 and later writes a random `\restrict` key on every run. The
   `grep` drops it, so unchanged data hashes the same twice.

   `n_live_tup` is an estimate, so also run `SELECT count(*)` on each table if
   you need exact counts. The devcontainer has no `psql`; run it from
   `docker run --rm -it postgres:18.0`, and use that same tag for the
   comparison afterwards. pg_dump writes its version into the dump, so a
   newer client changes the hash with no change to the data.

3. Apply `deployments/infrastructure`. It creates the `openviking_data_v2`
   volume, adds the `openviking-v2` sync line to `backup-s3` and the restore
   allowlist entry, and removes the `veerle` consumer.

4. Create the schema as the `openviking` role, before OpenViking first boots
   on it. ov-ext opens its delta store before the adapter creates the schema,
   so without this step change capture stays off until a restart:

   ```console
   $ psql -h 192.168.2.30 -U openviking -d openviking -c \
       "CREATE SCHEMA IF NOT EXISTS openviking_v2"
   ```

   This is a manual step, not a Terraform provisioner. A provisioner keyed on
   the jobspec re-runs on every config change, and the `NO ACCOUNT PROVISIONER
   HERE` comment in `deployments/applications/services.tf` records how the
   last one failed an apply.

5. Apply `deployments/applications`. It creates the `openviking-v2` bucket,
   moves the `openviking` key's policy onto it, and starts the job on the v2
   config. The job waits for `/ready`.

6. Restart Hermes, so it opens a new session instead of committing to one the
   new instance has never seen:

   ```console
   $ nomad job restart hermes
   ```

7. Check the new instance before anything writes to it. `/ready` answers 200,
   the bucket holds only `backend_meta.json` and the preset `default/` tree,
   both tokens resolve to `lab`/`jasper`, a search finds nothing, and Hermes's
   own search tool answers:

   ```console
   $ curl -s -o /dev/null -w '%{http_code}\n' https://openviking-api.lab.orangecluster.nl/ready
   $ rclone lsf -R seaweedfs:openviking-v2
   $ python3 scripts/ov_identity_probe.py --account lab --user jasper
   ```

   Run the probe as in `docs/how-to/verify-an-openviking-deployment.md`,
   once with your CLI token and once with Hermes's token, then ask Hermes on
   Telegram to search OpenViking for anything: it should answer with zero
   results.

8. Compare the old store with the baseline: repeat step 2's commands and
   `diff` against the saved files. Any difference means something wrote to
   the old store.

9. Force a backup and check that both buckets have their own GCS folder,
   `openviking-v2/` and `openviking/`, with the listing step in
   `docs/how-to/run-a-backup-job-on-demand.md`:

   ```console
   $ nomad job periodic force backup-s3
   ```
