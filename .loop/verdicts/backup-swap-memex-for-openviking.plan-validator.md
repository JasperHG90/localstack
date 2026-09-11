---
verdict: pass-with-required-fixes
plan: f3e3b068a83ec110375fdd8c737f0bab55d07fb2eb8e7a2c57748b2b77c5ab6d
bound_paths: front-matter, 5, 6, 7, 8, 9, 10, premises
scope: ad85298e4b84443e1c98347d97e061e3445e02c2130fa490a49cf34c131deaf2
fix_sections: 5, 6, 7
citations:
deployments/infrastructure/services/backup-minio.hcl:25 =         args         = ["rclone sync minio:memex gcs:${gcs_bucket}/minio/memex/ --config /secrets/rclone.conf"]
deployments/infrastructure/services/backup-postgres.hcl:29 =         args         = ["pg_dumpall -h ${postgres_host} | gzip > /alloc/data/pgdumpall-$(date +%Y-%m-%d).sql.gz"]
deployments/infrastructure/services.tf:707 =       postgres_host   = "192.168.2.30"
deployments/infrastructure/services.tf:713 = resource "nomad_job" "backup_minio" {
deployments/infrastructure/services.tf:719 =       minio_host   = "192.168.2.29"
deployments/infrastructure/secrets.tf:303 =   name  = "default/backup-postgres/postgres"
deployments/infrastructure/secrets.tf:305 =     username = "localstack"
deployments/infrastructure/secrets.tf:334 =   name  = "default/backup-minio/minio"
deployments/infrastructure/secrets.tf:336 =     access_key = "minio"
deployments/infrastructure/storage.tf:6 = resource "google_storage_bucket" "backups" {
deployments/infrastructure/storage.tf:13 =       age = 180
deployments/infrastructure/storage.tf:16 =       type = "Delete"
deployments/applications/database.tf:34 =     openviking = {
deployments/applications/storage.tf:2 =   buckets = {
deployments/applications/storage.tf:63 =     openviking = {
deployments/applications/services/openviking/ov.conf.json:7 =         "bucket": "openviking",
deployments/applications/services/openviking.hcl:33 =     ### in Postgres and the blobs in MinIO, so this is working state rather
.claude/rules/terraform-file-layout.md:73 =   re-registers the job.
.pre-commit-config.yaml:14 =   - repo: local
.pre-commit-config.yaml:18 =         entry: nomad fmt -recursive
.pre-commit-config.yaml:56 =         # the cwd only, and Q1 leaves no root manifest -- so without this it logs
.pre-commit-config.yaml:58 =         entry: uv run --project cli mypy --config-file cli/pyproject.toml cli/src cli/tests scripts
.loop/config.json:3 =     "just pre_commit"
cli/pyproject.toml:37 = testpaths = ["tests"]
cli/tests/commands/test_breakglass_runbook_facts.py:1 = """Drift tests: every fact in the runbook is pinned to the repo file that
cli/tests/test_health_rules.py:131 = @pytest.mark.parametrize("name", ["acme", "backup-minio", "backup-postgres"])
docs/gcs-backups.md:68 = - **Single task** (`sync`): uses `docker.io/rclone/rclone:latest`, runs `rclone sync minio:memex gcs:<bucket>/minio/memex/`
docs/gcs-backups.md:72 = - No node constraint (any node with network access to MinIO)
docs/gcs-backups.md:137 = gsutil ls gs://<bucket>/minio/memex/
docs/workload-identity.md:271 = `backup-minio` job runs on the root credential, and `storage.tf` still mints
---

rebound-by: JasperHG90 2026-09-11T12:28:29+02:00 (reason: Applied the plan-validator's required fixes verbatim: added docs/gcs-backups.md to the code surface as R6 (it states the memex sync at :68, the GCS path tree at :105, the verify command at :137), recorded in section 5 what in that doc stays untouched, and corrected R5's pre-commit anchors from :14/:56 to :18/:58. Edits confined to sections 5, 6, 7, matching fix_sections.)

## Deterministic floor

`loopctl verify-plan backup-swap-memex-for-openviking` returns `valid`. No
mechanical defect, so the semantic pass below ran in full.

## Premise verdict

**PARTIALLY SOUND.** Every premise the author stated survives attack, and the
two the briefing singled out (P2/P3 on `pg_dumpall` coverage, P4 on MinIO
credentials) are demonstrated against the live cluster rather than inferred.
One premise the author left implicit breaks: the section 7 code surface is not
complete, because `docs/gcs-backups.md` states the memex-specific fact this
change falsifies and appears in neither section 7 nor section 5.

## Per-assumption findings

- **P1 — HOLDS.** `deployments/infrastructure/services/backup-minio.hcl:25`
  > `        args         = ["rclone sync minio:memex gcs:${gcs_bucket}/minio/memex/ --config /secrets/rclone.conf"]`

  One `rclone sync`, one source bucket, and the destination prefix on the same
  line. The plan's claim that this is a single-line edit is exact: source and
  destination both live at line 25 and nowhere else. The whole 61-line jobspec
  names `memex` only here.

- **P2 — HOLDS.** Demonstrated, not inferred.
  `deployments/infrastructure/services/backup-postgres.hcl:29`
  > `        args       = ["pg_dumpall -h ${postgres_host} | gzip > /alloc/data/pgdumpall-$(date +%Y-%m-%d).sql.gz"]`

  and `deployments/infrastructure/services.tf:707`
  > `      postgres_host   = "192.168.2.30"`

  This is code-form, so it was probed. A scratch script ran `pg_dumpall` from
  the job's OWN image (`postgres:18`), against the job's own host, with the
  job's own credentials read from `secret/default/backup-postgres/postgres`.
  Captured output:

      PostgreSQL 18.3 (Debian 18.3-1.pgdg13+1) on x86_64-pc-linux-gnu|localstack|t

      bifrost|t|t
      ducklake|t|t
      localstack|t|t
      memex|t|t
      openviking|t|t
      phoenix|t|t
      postgres|t|t

  (columns: `datname | datallowconn | has_database_privilege(CONNECT)`.)
  `openviking` is on the same instance, allows connections, and the backup role
  may connect. Consul agrees the instance is the same one the applications root
  provisions the database on: `consul catalog nodes -service=postgres-db`
  returned `firebat | 41b4da7e | 192.168.2.30 | localstack`, and
  `deployments/applications/services.tf:7` names that same service
  (`name       = "postgres-db"`) as the postgresql provider's host. There is
  one postgres, not two, so the hardcoded `192.168.2.30` in the backup job and
  the Consul-discovered host in `deployments/applications/database.tf:34`
  > `    openviking = {`

  are the same server.

- **P3 — HOLDS.** Demonstrated at the strongest available level: not a
  privilege check standing in for the dump, but the dump itself.
  `deployments/infrastructure/secrets.tf:305`
  > `    username = "localstack"`

  Captured probe output, `pg_dumpall --schema-only` run as that role:

      110:CREATE DATABASE bifrost WITH TEMPLATE = template0 ...
      6695:CREATE DATABASE openviking WITH TEMPLATE = template0 ENCODING = 'UTF8' LOCALE_PROVIDER = libc LC_COLLATE = 'C' LC_CTYPE = 'en_US.utf8';
      6701:\connect openviking
      6765:CREATE SCHEMA openviking;
      --- stderr ---
      (empty)

  And a full (data-bearing) `pg_dumpall`, with only the two largest databases
  excluded to fit the wall-clock ceiling, emits the rows too:

      23631: COPY openviking.ov_collections (name, table_name, meta, created_at) FROM stdin;
      23640: COPY openviking.ov_context (id, uri, type, context_type, vector, sparse_vector, created_at, updated_at, active_count, level, name, description, tags, search_tags, abstract, content, account_id, owner_user_id, extra) FROM stdin;
      24760: COPY openviking.ov_indexes (collection, index_name, meta, created_at) FROM stdin;

  About 1,120 data lines sit between the `ov_context` COPY and the next one,
  so this is the live vector store, not an empty schema. `rolsuper` is `t` for
  `localstack` (first probe above), so nothing is silently skipped. The
  operator's second ask really is already satisfied, and the plan is right to
  treat it as a non-goal.

- **P4 — HOLDS, and this was the one worth the hardest look.**
  `deployments/infrastructure/secrets.tf:336`
  > `    access_key = "minio"`

  and `deployments/infrastructure/services.tf:719`
  > `      minio_host   = "192.168.2.29"`

  Code-form, so probed with `mc` configured from the job's own Vault secret,
  against the job's own endpoint. Consul confirms that endpoint is the only
  MinIO: `consul catalog nodes -service=minio` returned
  `orange_pi_4a | da560d72 | 192.168.2.29 | localstack`. Captured output:

      === ls buckets ===
      [2026-03-22 08:39:45 CET]     0B datalake/
      [2026-04-26 08:48:00 CEST]     0B loki/
      [2026-03-22 08:39:45 CET]     0B memex/
      [2026-04-27 13:35:33 CEST]     0B mlflow-artifacts/
      [2026-09-01 22:29:29 CEST]     0B models/
      [2026-08-30 09:49:06 CEST]     0B openviking/
      [2026-09-01 22:29:29 CEST]     0B registry/
      [2026-09-01 21:00:30 CEST]     0B tempo/

      === recursive count/size openviking ===
      Total Size: 150 MiB
      Total Objects: 7613

  Listing alone would NOT settle this, because `rclone sync` needs GetObject as
  well as ListBucket, and a list-only key would produce exactly the silent
  empty backup the briefing worried about. So the probe also read an object:

      === stat one object ===
      OBJ=.ovgit/lab/index/main.json
      Size      : 10 KiB
      ETag      : 06c00aa169d854790bf871496128ef08
      === GET first 64 bytes ===
      0000000   {   "   v   e   r   s   i   o   n   "   :   1   ,   "   p   a

  The bytes came back, unencrypted, with no SSE-C header in the way. The key is
  the MinIO root credential (`access_key = "minio"`, secret copied from
  `random_password.minio_secret_key`), so bucket-scoped IAM never enters the
  path. Nothing in the runtime context changes either: the task keeps
  `network_mode = "host"` on the same pinned node and dials the same
  `192.168.2.29:9000` it already reaches for `memex`, and swapping the bucket
  name does not move the network path. No new `minio_iam_policy` and no new
  access key. The plan's section 5 non-goal is correct.

  Two supporting reads confirm the `openviking` bucket is in fact where OV's
  artifacts live, so the bucket named is the right one.
  `deployments/applications/services/openviking/ov.conf.json:7`
  > `        "bucket": "openviking",`

  and `deployments/applications/services/openviking.hcl:33`
  > `    ### in Postgres and the blobs in MinIO, so this is working state rather`

  The host volume `openviking_data` is declared working state, not the store,
  so leaving it out of the backup is consistent rather than an omission.

- **P5 — UNCERTAIN, and correctly so.** `deployments/infrastructure/services.tf:713`
  > `resource "nomad_job" "backup_minio" {`

  and `.claude/rules/terraform-file-layout.md:73`
  > `  re-registers the job.`

  This is a pure-intent premise as far as the rule goes, and the rule says what
  the plan says it says: a `templatefile` jobspec edit folds into
  `nomad_job.jobspec` and re-registers the job. The plan marks the "1 to
  change, nothing else" half UNCERTAIN until `just plan` runs, and section 8
  makes that a gate. I did not force a probe there: `terraform plan` takes a
  state lock against live infrastructure, which is outside a read-only pass,
  and the author already disclaimed the measurement. Left UNCERTAIN.

  One observation on how that gate is worded. Section 9 failure mode 2 reads a
  plan showing more than `nomad_job.backup_minio` as proof "the edit touched
  something outside the intended line." It could equally be pre-existing drift
  in a root that mints service-account keys and random passwords. Not a
  required fix, but the implementer should be told to attribute each extra
  resource rather than assume their own edit caused it.

- **P6 — HOLDS.** `deployments/infrastructure/storage.tf:13`
  > `      age = 180`

  paired with `deployments/infrastructure/storage.tf:16`
  > `      type = "Delete"`

  inside `google_storage_bucket.backups` at
  `deployments/infrastructure/storage.tf:6`
  > `resource "google_storage_bucket" "backups" {`

  The lifecycle rule is on the bucket, so it reaches the orphaned
  `minio/memex/` prefix without any further action. Read from the managing
  resource, not probed against GCS, exactly as the author disclaimed.

- **P7 (implicit, added) — BREAKS. The section 7 code surface is not
  complete.** `docs/gcs-backups.md:68`
  > `- **Single task** (`sync`): uses `docker.io/rclone/rclone:latest`, runs `rclone sync minio:memex gcs:<bucket>/minio/memex/``

  and `docs/gcs-backups.md:137`
  > `gsutil ls gs://<bucket>/minio/memex/`

  Section 7 ends with "Nothing else." Both of those lines state the fact this
  ticket falsifies, and neither the code surface nor the non-goals in section 5
  mentions the file. That leaves the implementer two bad moves: edit an
  unlisted file, which is the `out-of-scope-fix-needed` blocker the contract
  names, or leave the doc stating a command the cluster no longer runs, which
  the `documentation` review pass in `.loop/config.json` is dispatched to
  catch. Either way the ticket stalls on something the plan could have decided.

  This is not the same class of defect as a broken premise about the cluster,
  and it is confined to two named sections, so it is a required fix rather than
  a `fail`. Note that `docs/gcs-backups.md:72`
  > `- No node constraint (any node with network access to MinIO)`

  is ALREADY wrong against `backup-minio.hcl:13-16`, which constrains the group
  to `radxa-dragon-q6a`. That is pre-existing and not this ticket's to fix, but
  it is evidence the file drifts unattended, which argues for listing it rather
  than waving it off.

  `docs/workload-identity.md:271` needs nothing.
  > `` `backup-minio` job runs on the root credential, and `storage.tf` still mints ``

  That sentence stays true after the swap, since P4 shows the root credential
  is what reads the new bucket too.

- **P8 (implicit, added) — HOLDS. No existing test pins `memex` in this
  jobspec, so the two-file surface is otherwise complete.**
  `cli/tests/test_health_rules.py:131`
  > `@pytest.mark.parametrize("name", ["acme", "backup-minio", "backup-postgres"])`

  That is the only test in the tree naming `backup-minio`, and it reads the
  captured fixture `cli/tests/fixtures/capture/jobs_statuses.json`, not the
  jobspec, so the bucket swap cannot turn it red. A grep across `*.py`,
  `*.md`, `*.toml`, `*.yaml` and `*.json` found no other non-doc consumer of
  `minio:memex` or `minio/memex`.

- **P9 (implicit, added) — HOLDS. The unchanged task resources still fit.**
  Captured from the same MinIO probe:

      === memex size ===
      Total Size: 705 MiB
      Total Objects: 1635

  against `openviking` at 150 MiB / 7613 objects. More objects, a fifth of the
  bytes. `rclone sync` walks directory by directory rather than holding a whole
  bucket listing, so the 512 MB task memory the plan leaves alone is not at
  risk. Worth stating because the plan changes one line and implicitly asserts
  everything around it still holds.

## Most dangerous assumption

**P4.** If the backup job's credential could list but not read the
`openviking` bucket, `rclone sync` would create the destination prefix, copy
nothing, and exit 0. The job would look healthy for 180 days while the backup
was empty, and no gate in this plan would notice. It is demonstrated to hold:
the key is MinIO root, and the probe read real object bytes, not just a
listing.

Runner-up is P2/P3, which would cost half the operator's ask. Also
demonstrated, and at the level that matters: `pg_dumpall` emits
`COPY openviking.ov_context ... FROM stdin;` with rows behind it.

## Contract hygiene

Clean except where noted:

- **Code surface anchors.** All resolve and support their claims, except the
  incompleteness in P7.
- **Gates discovered, not assumed.** `.loop/config.json:3`
  > `    "just pre_commit"`

  is the configured gate, and it reaches both changed files. `nomad fmt` takes
  the `.hcl` (`.pre-commit-config.yaml:18` with `files: '\.hcl$'`), and mypy
  strict takes the new test (`.pre-commit-config.yaml:58`, whose argument list
  includes `cli/tests`). The second gate command in section 8 was checked for
  invocation shape: `uv run --project cli pytest cli/tests/test_health_rules.py -q`
  returned `25 passed in 0.14s` from the repo root, so pytest walks up to
  `cli/pyproject.toml:37` and the plan's command form works as written.
- **Non-goals explicit.** Five of them, including the two settled forks.
- **Tests homed.** Both named tests declare `cli/tests/test_backup_coverage.py`,
  which section 7 lists. The cited pattern is real:
  `cli/tests/commands/test_breakglass_runbook_facts.py:1`
  > `"""Drift tests: every fact in the runbook is pinned to the repo file that`

  and that file locates repo content through `REPO_ROOT = Path(__file__).resolve().parents[3]`,
  a pattern the new test at one level shallower must adapt (`parents[2]`)
  rather than copy.
- **Forks surfaced.** Section 11 declares none outstanding and points at the
  two recorded in section 5. Consistent.
- **Requirements reachable by a measurement.** R1 through R5 each name a
  producer that section 7 lists or section 8 runs. No `unmeasurable-requirement`
  fork is owed.
- **Reverse direction (advisory).** Every file in section 7 is reached by a
  requirement. Nothing orphaned.

## Required fixes

1. **Section 7, or section 5 — account for `docs/gcs-backups.md`.** Add a row
   to the code surface updating `docs/gcs-backups.md:68` and `:137` to the new
   bucket, or add an explicit non-goal saying the doc is deliberately left for
   a follow-up. Do not leave it unmentioned: unmentioned is the one state that
   forces the implementer to guess. Recommend adding the row, since it is two
   lines and the documentation pass will otherwise ask for it anyway.

2. **Section 6, R5 — tighten two anchors.** `.pre-commit-config.yaml:14` is
   > `  - repo: local`

   while the command R5 names is at line 18. `.pre-commit-config.yaml:56` is
   > `        # the cwd only, and Q1 leaves no root manifest -- so without this it logs`

   while the mypy invocation is at line 58. Both land inside the right hook
   block, so the claims are supported, but cite 18 and 58 so a reader lands on
   the entry rather than on its preamble.

## Scratch

scratch created at `.loop/scratch/backup-swap-memex-for-openviking.plan-validator/`
scratch removed at end of pass (the `mc` config dir and the postgres probe
script). The findings ledger at
`.loop/scratch/backup-swap-memex-for-openviking.plan-validator/findings.json`
is kept on purpose for the next cycle.
