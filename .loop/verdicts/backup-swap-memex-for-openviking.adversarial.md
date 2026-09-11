---
verdict: pass
tree: 36df19e0e29216fb52dfa4f29bb552303eae330b
---

# Adversarial review — cycle 3

**PASS.** The three-line delta since cycle 2 is correct, introduces no new
contradiction, and the gates are green. Cycle-1 and cycle-2 conclusions stand.

## Scope binding: deliberately omitted

My briefing carried the tree fingerprint but no `bound_paths:` set and no
64-hex `scope:` digest. I may only write a digest I was given, so I omit the
three scope-binding lines and let this verdict fall back to whole-tree
binding. That is stricter than a path-scoped binding, so the omission is safe.

For the record, the full path set I reviewed is
`deployments/infrastructure/services/backup-minio.hcl`,
`docs/gcs-backups.md`, `cli/tests/test_backup_coverage.py`, and
`.loop/ledger.json` (harness bookkeeping only: one ticket record plus one
`plan_rebinds` entry, no code).

## Deterministic floor

`loopctl verify-eval-substance backup-swap-memex-for-openviking` returns
`valid`, exit 0, with no `warn:` lines. No hard-fail, no advisory. No
plan-drift advisory to hand to the operator.

`loopctl verify --expect-tree 36df19e0e29216fb52dfa4f29bb552303eae330b`
returns `ok`, exit 0. I am standing in the briefed checkout.

## The three new lines

I verified all three against the jobspec and the Terraform, not against the
hand-off summary. I also re-reviewed the whole diff rather than only the
delta, so this verdict does not depend on the claim that only three lines
moved.

**`docs/gcs-backups.md:55` — correct, and a real improvement.**

    docs/gcs-backups.md:55 = "  - Constrained to `radxa-dragon-q6a`, so it reads postgres over the network at `192.168.2.30`"

DOC-6 was a true defect, not a style nit. The pgdump task reads from postgres
and writes locally:

    deployments/infrastructure/services/backup-postgres.hcl:28 = "        args         = [\"pg_dumpall -h ${postgres_host} | gzip > /alloc/data/pgdumpall-$(date +%Y-%m-%d).sql.gz\"]"

`-h ${postgres_host}` is the source; `/alloc/data/` is the destination. The
cycle-2 wording ("dumps over the network to postgres on `192.168.2.30`") had
the arrow backwards. Every clause of the replacement checks out:

- constraint: `deployments/infrastructure/services/backup-postgres.hcl:15 = "      value     = \"radxa-dragon-q6a\""`
- host: `deployments/infrastructure/services.tf:707 = "      postgres_host   = \"192.168.2.30\""`, inside the `backup_postgres` templatefile
- "over the network": radxa is `192.168.2.50` (`bootstrap/inventory/cluster.ini:15`, corroborated by `deployments/infrastructure/services/grafana/alert-rules.yaml:469`), firebat is `192.168.2.30` (`cluster.ini:2`), and postgres is pinned to firebat (`postgres.hcl:9 = "      value     = \"firebat\""`). Different nodes, so the read crosses the network.

**`docs/gcs-backups.md:57` and `:62` — correct.**

    docs/gcs-backups.md:57 = "  - Resources: 500 MHz CPU, 512 MB memory"
    deployments/infrastructure/services/backup-postgres.hcl:45 = "        cpu    = 500"
    deployments/infrastructure/services/backup-postgres.hcl:46 = "        memory = 512"

    docs/gcs-backups.md:62 = "  - Resources: 200 MHz CPU, 256 MB memory"
    deployments/infrastructure/services/backup-postgres.hcl:69 = "        cpu    = 200"
    deployments/infrastructure/services/backup-postgres.hcl:70 = "        memory = 256"

Both now match. A6 is resolved.

## You asked me to judge widening the diff. The call was right.

I stand by declining to make A6 a *required* fix, and I also think you were
right to apply it. Those are not in tension. My cycle-2 objection was about
what I would block a commit on, not a ban on fixing it. Ratcheting is a
reviewer failure mode: inventing new blocking demands at cycle 2 for defects
that were equally visible at cycle 1. It is not a rule that the implementer
must leave a known-wrong line in a file they are already editing.

Three things make this the cheap branch:

1. Plan section 5 already names `pre-existing-issues.md` as the thing that
   pierces its own doc fence. It grants exactly that exception for `:72`.
   Applying the same rule to `:57` and `:62` follows the plan's stated
   reasoning rather than defying it. A frozen decision that carves out a rule
   by name cannot then be read as fencing that rule out.
2. Blast radius is two digits in a markdown file, in a section the diff was
   already rewriting for `:55`. No code, no Terraform, no state.
3. Both numbers verified correct above. A follow-up ticket would cost a plan,
   an eval, and two review passes to change `1000` to `500` and `500` to
   `200`.

The discipline that makes this fine is "bounded and verified", not "a rule
permits it". A rule citation alone would justify an unbounded cleanup sweep,
and that is the version I would have pushed back on. This was three lines in
one file, each checked against its source. Ship it.

## No new contradiction in the document

I grepped the whole runbook for `memex`, `co-located`, `network transfer`,
`constraint`, `Constrained`, `MHz`, and every host name, then checked each
survivor:

- `docs/gcs-backups.md:5` — "the MinIO openviking bucket lives on `orangepi4a`". `services.tf:718 = "      minio_host   = \"192.168.2.29\""` and `cluster.ini:6 = "orange_pi_4a ansible_host=192.168.2.29"`. Consistent, and its "PostgreSQL data lives on ... `firebat`" half agrees with `:55`.
- `docs/gcs-backups.md:27` — still names memex, correctly. `deployments/applications/secrets.tf:28 = "  name  = \"default/memex/postgres\""`. A8 holds; swapping it would have made the doc wrong.
- `docs/gcs-backups.md:72` — "Pinned to `radxa-dragon-q6a` by a node constraint, like `backup-postgres.hcl`". Matches `backup-minio.hcl:14-15`. The `:55`/`:72` self-contradiction from cycle 1 is gone and the two lines now agree.
- `docs/gcs-backups.md:75` — "1000 MHz CPU, 512 MB memory" against `backup-minio.hcl:57 = "        cpu    = 1000"` and `:58 = "        memory = 512"`. Correct. The A6 fix did not leave a sibling wrong number behind in the minio half.

The old "co-located with postgres, avoids network transfer" rationale is
gone entirely, not half-edited. No line in the document still asserts
co-location.

## Gates, re-run by me

`just pre_commit`, exit 0, 3.8s wall. All 13 hooks pass, including `Nomad
Format (fmt -recursive)`, `Terraform Validate (per root)`, and `Mypy (strict,
cli/)`. Fast and non-destructive, so no trust stamp is warranted; I re-ran it
rather than trusting a stamp.

`uv run --project cli pytest cli/tests/test_backup_coverage.py -q` — 2 passed.

## Test quality

`test_minio_backup_syncs_the_openviking_bucket` reddens against the old code.
I extracted `git show HEAD:deployments/infrastructure/services/backup-minio.hcl`
into the session scratchpad and ran the test's own regexes over it: source
parses as `memex`, destination prefix as `memex`, so the `== "openviking"`
assertion fails. It is a real change-detector.

`test_minio_backup_syncs_a_declared_bucket` does NOT redden against the old
code, because `memex` is also a declared bucket. That is correct and matches
the plan: R2 is a standing typo guard, not a change-detector. I proved it is
not vacuous by feeding `minio:openvikng` through the module's real
`_declared_buckets()`, which returns all 8 keys (`datalake`, `loki`, `memex`,
`mlflow-artifacts`, `models`, `openviking`, `registry`, `tempo`) and fails the
membership assertion. `openviking` is declared at
`deployments/applications/storage.tf:63 = "    openviking = {"`.

**Unasserted literal, checked by reproducer.** `cli/tests/test_backup_coverage.py:29`
is a `pytest.fail` message no gate exercises and the first of its kind at this
anchor, so a green stamp says nothing about it. I checked it by importing the
module in the session scratchpad and calling `_require(None, ...)` — no write
into the repo tree, so neither the read-only rule nor the tree fingerprint was
disturbed. It raises `Failed: parser found no rclone sync source in
backup-minio.hcl — the jobspec cannot be checked`. The interpolation is right
and it names the file a reader would open. Verified, not assumed.

## Settled findings: re-attached

- **A1** (stale `firebat` at `:55`) — touched by this delta, re-attacked, **still resolved**. The line changed again but every clause re-verified above.
- **A6** (wrong CPU figures) — touched by this delta, **resolved this cycle**. Evidence above.
- **A7** (`:55` edits a plan-fenced line) — touched by this delta, **still accepted**. Same cycle-2 grounds, and the line is now more correct rather than merely different.
- **A2** (`:106` outside the plan's line list) — no change in scope, still holds, `:106` is the continuation of the path tree at `:105` and reads "      <mirror of openviking bucket>".
- **A3** (`_declared_buckets` counts braces in comments) — no change in scope, still holds, and I re-ran the parser this cycle: exactly 8 bucket keys, no non-bucket keys. Every miscount still lands on the safe side.
- **A4** (openviking DB already covered by `pg_dumpall`) — no change in scope, still holds, the static chain is untouched by this delta.
- **A5** (15 add / 15 destroy are unrelated firewall churn) — no change in scope, still holds, and I re-verified the anchors: `services.tf:458 = "  for_each = local.firewall_rules"`, `:466 = "    always_run = timestamp()"` inside `triggers` at `:464`, and `local.firewall_rules` parses to exactly 15 keys. **Operator note for eval row 5:** that row's "adds or destroys nothing" will not literally hold. Expect `1 to change` for `nomad_job.backup_minio` plus a 15/15 replace of `null_resource.firewall[*]`, which appears on every plan in this root regardless of this ticket. Account for it and move on.
- **A8** (`:27` memex reference left alone) — no change in scope, still holds, anchor re-verified above.

## Findings this cycle

None blocking. None advisory. Nothing unverified.

The ledger at
`.loop/scratch/backup-swap-memex-for-openviking.adversarial/findings.json`
now carries 11 entries: A6 and A7 updated, A9 (delta introduces no
contradiction), A10 (the two tests do different jobs, deliberately), and A11
(the `pytest.fail` literal, checked by reproducer) appended.
