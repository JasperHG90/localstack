---
verdict: pass
tree: 36df19e0e29216fb52dfa4f29bb552303eae330b
---

# Documentation freshness: backup-swap-memex-for-openviking, cycle 3 (final)

## Why the scope binding is absent

No `bound_paths:`, `scope:`, or `citations:` lines. The briefing carried a
tree fingerprint but no 64-hex scope digest, and the rule is to write only
the digest I was given, never one I computed for a set of my own choosing.
The harness this pass runs under offers none to compute:
`loop-harness/1.9.0/scripts/loopctl.py --help` lists no scope subcommand.
The verdict therefore falls back to the whole-tree binding, which is
stricter than a path-scoped one and safe by construction. This matches what
the two most recent documentation verdicts in this repo did under the same
condition (`.loop/verdicts/R9-rollout-tempo-keyless-minio.documentation.md`,
`.loop/verdicts/OV2-openviking-user-scoped-resources.documentation.md`).

For the record, the change set I reviewed was: `docs/gcs-backups.md`,
`deployments/infrastructure/services/backup-minio.hcl`,
`cli/tests/test_backup_coverage.py` (new), and `.loop/ledger.json`. Nothing
was deleted.

## Verdict

**Pass.** DOC-5 and DOC-6 are both resolved against source. Every documented
surface this diff touches was updated in step, and the three lines that moved
since cycle 2 are true, correctly directed, and clean under
`plain-language.md` and `slop-scan-for-docs.md`.

## Your question first: was widening the diff wrong?

No. It was the right call, and I would have made it.

You asked me to say so plainly if it was wrong, so here is the reasoning in
full rather than a bare agreement.

I declined to escalate DOC-5 at cycle 2 on anti-goalpost-moving grounds. That
was a decision about what I may *demand*, not a finding that the drift was
acceptable. A reviewer who invents a new blocker on the last cycle of a ticket
whose only remaining change was the fix he himself asked for is just extending
the ticket. That restraint binds the reviewer. It does not bind the
implementer, and it is not a licence to leave a false number in a runbook.

Three things make the fix clearly in bounds here:

1. `docs/gcs-backups.md` was already on the plan's code surface (plan section
   7, row 3). The file was open. This is not a drive-by edit to an untouched
   file, which is what CLAUDE.md section 3 guards against.
2. The plan had already invoked the same rule for the same file. Plan section
   5: "The one exception is the stale `No node constraint` claim at
   `docs/gcs-backups.md:72`, which `.claude/rules/pre-existing-issues.md`
   requires the agent that noticed it to fix." The precedent for widening
   inside this file was set and counter-signed before I ever filed DOC-5.
3. Cost and blast radius are near zero. Two integers in a markdown bullet.
   No behavior changes, no other file changes, no Terraform plan moves.

One honest caveat, logged as DOC-7 and deliberately not escalated: plan
section 5 names exactly one pre-existing-issues exception (`:72`), and the
`:57`/`:62` edits are not in its prose. That is a plan-conformance question,
not a documentation-freshness one. It belongs to the plan-validator and the
adversarial pass, not to me, and I raise it only so neither is surprised by a
diff slightly wider than section 5 reads. From my seat the edits make the doc
more true, which is the only axis I judge.

## Re-attack on the settled findings

I re-opened every anchor rather than trusting the report. Where a line moved,
I re-derived the claim from the jobspec, not from the implementer's summary.

### DOC-5 — RESOLVED (was: observation, cycle 2)

The doc's resource figures now match the jobspec exactly.

```
docs/gcs-backups.md:57 =   - Resources: 500 MHz CPU, 512 MB memory
backup-postgres.hcl:45 =         cpu    = 500
backup-postgres.hcl:46 =         memory = 512

docs/gcs-backups.md:62 =   - Resources: 200 MHz CPU, 256 MB memory
backup-postgres.hcl:69 =         cpu    = 200
backup-postgres.hcl:70 =         memory = 256
```

Task attribution is the right way round, which a naive number-swap could
easily have got backwards: `:57` sits under the **pgdump** bullet at `:53`
and takes the pgdump task's resources block (`backup-postgres.hcl:44-47`);
`:62` sits under the **upload** bullet at `:58` and takes the upload task's
(`backup-postgres.hcl:68-71`).

I then widened the sweep to the one resource line in this doc I had never
checked, since fixing two of three and leaving the third wrong is the classic
partial fix:

```
docs/gcs-backups.md:75 = - Resources: 1000 MHz CPU, 512 MB memory
backup-minio.hcl:56    =         cpu    = 1000
backup-minio.hcl:57    =         memory = 512
```

Correct. Every resource figure in this document is now true.

### DOC-6 — RESOLVED (was: observation, cycle 2)

`docs/gcs-backups.md:55` now reads:

```
  - Constrained to `radxa-dragon-q6a`, so it reads postgres over the network at `192.168.2.30`
```

Direction is now right. "reads postgres ... at `192.168.2.30`" names that
host as the source, which is what the jobspec does:

```
backup-postgres.hcl:29 =         args         = ["pg_dumpall -h ${postgres_host} | gzip > /alloc/data/pgdumpall-$(date +%Y-%m-%d).sql.gz"]
services.tf:707        =       postgres_host   = "192.168.2.30"
```

`pg_dumpall -h` takes the host it reads **from**. The old wording ("dumps
over the network to postgres") put the arrow the other way.

Agreement with `:53` holds, and is now cleaner than it was. `:53` names the
write destination, `:55` names only the read:

```
docs/gcs-backups.md:53 = - **Prestart task** (`pgdump`): uses `docker.io/library/postgres:18` image, runs `pg_dumpall | gzip` to `/alloc/data/pgdumpall-YYYY-MM-DD.sql.gz`
```

One bullet carries one direction each. No reader has to reconcile them.

The causal "so" is earned rather than decorative, which I checked rather than
assumed. The node pin is what *forces* the network read: MinIO and postgres
are elsewhere. `backup-postgres.hcl:12-16` pins the group to
`radxa-dragon-q6a`; postgres is on `firebat` at `192.168.2.30`
(`docs/gcs-backups.md:5`, corroborated by
`deployments/infrastructure/services/grafana/alert-rules.yaml:204`, which
names "postgres-exporter on firebat:9187" and "the listen binding on
192.168.2.30:9187"). Different node, so the hop is real.

### DOC-1 — still RESOLVED, re-derived not carried

`:55` was rewritten *again* this cycle, so I re-verified both halves from
source rather than inheriting cycle 2's confirmation.

```
backup-postgres.hcl:15 =       value     = "radxa-dragon-q6a"
```

That sits inside the **group**-level constraint at `backup-postgres.hcl:12-16`,
so it binds the pgdump task the bullet describes. The bullet's placement under
a task while the constraint lives on the group is pre-existing structure and
remains true as written.

Consistency with `:72` re-checked, since `:72` points a reader at the sibling
jobspec as a likeness:

```
docs/gcs-backups.md:72 = - Pinned to `radxa-dragon-q6a` by a node constraint, like `backup-postgres.hcl`
backup-minio.hcl:15    =       value     = "radxa-dragon-q6a"
```

Same value in both jobspecs, so "like `backup-postgres.hcl`" is true. No
self-contradiction remains anywhere in the file.

### DOC-4 — re-swept, still confirmed-clean

Re-run rather than carried forward, because the cheapest way to miss a stale
doc is to trust last cycle's sweep.

- `README.md:15` = `- **Backups:** nightly GCS off-site jobs for PostgreSQL and MinIO`.
  Bucket-agnostic, still true.
- `docs/workload-identity.md:271` = "`backup-minio` job runs on the root credential, and `storage.tf` still mints".
  That passage (`:265-275`) is about static credentials, not backup buckets.
  This diff changed no credential, so it cannot have staled it.
- `docs/gcs-backups.md:27`'s surviving `memex` mention is about the per-job
  Vault credential-path pattern ("memex gets its own copy of postgres creds"),
  and `deployments/applications/services/memex.hcl` still exists. Still true.

No doc in the repo now implies that `openviking` is unbacked or that `memex`
objects are still synced.

### DOC-2 — no change in scope, still holds

The Context frame at `docs/gcs-backups.md:5` still reads as a pre-change
snapshot ("No off-site backups exist ... This change adds two Nomad periodic
batch jobs") while the rest of the file is a live runbook. The only token the
ticket changed on that line is `memex` to `openviking`. Plan section 5 ("its
structure stay as they are") accepted the frame as out of scope. Not blocking,
not re-raised.

While there I did verify the changed half of `:5` against source, since the
ticket owns that token: `deployments/infrastructure/services/minio.hcl:6-9`
pins MinIO to `orangepi4a`, and `openviking` is a declared bucket at
`deployments/applications/storage.tf:63`. "the MinIO openviking bucket lives
on `orangepi4a`" is true.

### DOC-3 — no change in scope, still holds

Re-read `:99-107` this cycle; byte-identical to cycle 2. The GCS path tree
still shows only `minio/openviking/` while `gs://<bucket>/minio/memex/` keeps
its objects until the 180-day rule at
`deployments/infrastructure/storage.tf:13` expires them. Plan section 5
records the operator's choice to let the rule do that. Not blocking, not
re-raised.

## Surfaces this diff touched, and the docs that describe them

- **The rclone sync command** (`backup-minio.hcl:25`, `minio:memex` to
  `minio:openviking`). Documented at `docs/gcs-backups.md:68`, updated in
  step, and matches byte for byte.
- **The GCS destination prefix.** Documented in the path tree at `:104-106`
  and in the verify command at `:137` (`gsutil ls
  gs://<bucket>/minio/openviking/`). Both updated in step.
- **The Context summary** at `:5`. Updated in step.
- **The node-constraint claim** at `:72`. Updated in step and verified above.
- **`cli/tests/test_backup_coverage.py`** (new). No documented surface. No
  README, runbook or docs page in this repo enumerates `cli/tests`, and the
  only references to this filename are `.loop/` planning artifacts. I do not
  demand documentation the repo never had.

No CLI flag, config key, default, public function, or error contract moved.

## Slop and plain-language scan on the three moved lines

Run over `docs/gcs-backups.md` and read against `:55`, `:57`, `:62`.

| Check | Result |
|---|---|
| Identity leaks, `TODO`/`FIXME`/`XXX`/`HACK` | none in file |
| Hallucinated identifiers and paths | none; every backticked name resolves (verified above) |
| Em dashes | 0 in file |
| ` -- ` in prose | 10 in file, all pre-existing (`:7`, `:36-39`, `:63`, `:70`, `:71`, `:82`, `:83`, `:110`), **none on a moved line** |
| Semicolon splice | none |
| Tier-1 slop | none |
| British spellings | none |
| Smart quotes | none |
| Participial tail | none on moved lines |
| Spatial copula / animated inanimates | none on moved lines |
| Voice | active throughout; `:55` has a real actor ("it reads postgres") |

Line length: `:55` is 94 chars. This file does not wrap at 80 (22 of its 138
lines exceed it), its sibling bullets at `:53`, `:54`, `:56`, `:58`, `:60`,
`:61` run 100 to 145 chars, and this repo has no
`.claude/rules/markdown-formatting.md` for the slop rule's wrap check to point
at. The line matches the file's own style and is shorter than four of its
neighbors. Not a finding.

One pre-existing note, raised for completeness and not as a defect: `:5` uses
"lives on", a spatial-copula pattern the slop rule flags. That phrasing
predates this ticket and the implementer changed only the bucket name on that
line. CLAUDE.md section 3 says leave it. I agree; do not fix it now.

## Findings

| ID | Severity | Status |
|---|---|---|
| DOC-1 | — | resolved, re-derived from source this cycle |
| DOC-2 | info | observation, no change in scope, still holds |
| DOC-3 | info | observation, no change in scope, still holds |
| DOC-4 | — | re-swept, confirmed clean |
| DOC-5 | — | **resolved this cycle**, verified against jobspec |
| DOC-6 | — | **resolved this cycle**, direction correct |
| DOC-7 | info | out of remit: `:57`/`:62` exceed plan section 5's written exception. For the plan-validator and adversarial passes, not a doc defect |

No blocking findings. No required fixes.

Ledger updated at
`.loop/scratch/backup-swap-memex-for-openviking.documentation/findings.json`.
No trust stamp written: every check this pass ran was a file read or a grep,
none took over a minute, and none deleted files, hit the network, or mutated
state outside the worktree. Nothing qualified.
