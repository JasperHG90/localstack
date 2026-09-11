---
verdict: pass-with-required-fixes
plan: ae9bba06d855fc94e97c158244a790614f267e05035d13da0fc7339098d8742f
bound_paths: front-matter, 5, 6, 7, 8, 9, 10, premises
scope: 3dab9b6e786b4088c1cc159b6f7ee6260fa8fc4d48433f7890c9e1091c18c3b2
fix_sections: 6, 8, 9, premises
citations:
docs/gcs-backups.md:1 = # Nightly GCS Backup Jobs
docs/gcs-backups.md:51 = Periodic batch job running at 2:00 AM Europe/Amsterdam:
docs/gcs-backups.md:57 =   - Resources: 500 MHz CPU, 512 MB memory
docs/gcs-backups.md:58 = - **Main task** (`upload`): uses `docker.io/rclone/rclone:latest`, runs `rclone copy` to upload today's dump
docs/gcs-backups.md:62 =   - Resources: 200 MHz CPU, 256 MB memory
docs/gcs-backups.md:67 = Periodic batch job running at 3:00 AM Europe/Amsterdam (staggered):
docs/gcs-backups.md:75 = - Resources: 1000 MHz CPU, 512 MB memory
docs/gcs-backups.md:94 = Google provider added (`hashicorp/google ~>6.0.0`), authenticated via ADC.
docs/gcs-backups.md:118 = # Deploy (re-init needed first time to fetch google provider)
deployments/infrastructure/providers.tf:17 =       version = "~>7.27.0"
deployments/infrastructure/secrets.tf:3 =   path        = var.secret_mount
deployments/infrastructure/variables.tf:1 = variable "secret_mount" {
deployments/infrastructure/services/backup-postgres.hcl:7 =     crons            = ["0 2 * * *"]
deployments/infrastructure/services/backup-postgres.hcl:45 =         cpu    = 500
deployments/infrastructure/services/backup-postgres.hcl:54 =         image      = "docker.io/rclone/rclone:latest"
deployments/infrastructure/services/backup-postgres.hcl:69 =         cpu    = 200
deployments/infrastructure/services/backup-minio.hcl:7 =     crons            = ["0 3 * * *"]
deployments/infrastructure/services/backup-minio.hcl:15 =       value     = "radxa-dragon-q6a"
deployments/infrastructure/services/backup-minio.hcl:56 =         cpu    = 1000
deployments/infrastructure/storage.tf:13 =       age = 180
deployments/infrastructure/services.tf:707 =       postgres_host   = "192.168.2.30"
bootstrap/roles/nomad_server/templates/vault_nomad_workloads.hcl.j2:1 = path "secret/data/{{ '{{' }}identity.entity.aliases.{{ auth_method_accessor }}.metadata.nomad_namespace{{ '}}' }}/{{ '{{' }}identity.entity.aliases.{{ auth_method_accessor }}.metadata.nomad_job_id{{ '}}' }}/*" {
.pre-commit-config.yaml:58 =         entry: uv run --project cli mypy --config-file cli/pyproject.toml cli/src cli/tests scripts
.loop/plans/gcs-backups-doc-to-runbook.md:89 = - R3. Every doc claim that is mechanically parseable from both the document
.loop/plans/gcs-backups-doc-to-runbook.md:111 = - R8. The document states, in its own text, two absences: no restore
.loop/plans/gcs-backups-doc-to-runbook.md:153 = - `test_backup_doc_matches_jobspec_schedules_and_images` (R3) — parse both
.loop/plans/gcs-backups-doc-to-runbook.md:168 = - The scenario set in `.loop/evals/gcs-backups-doc-to-runbook.md` is the
.loop/plans/gcs-backups-doc-to-runbook.md:189 = 4. The doc drifts again. R3 pins ten facts across four tests. It does not
.loop/plans/gcs-backups-doc-to-runbook.md:266 = - **P6.** No code reads this document, so the rewrite cannot break a gate
---

rebound-by: JasperHG90 2026-09-11T20:41:09+02:00 (reason: Applied all five cycle-2 required fixes: corrected R3's fact counts to twelve (six CPU/memory figures across three tasks, three images) and required the rewrite to state both cron expressions literally so the schedule test is writable at all; bound each figure to its task; reworded R8 off the unverifiable 'none has been performed'; extended R9 to cover the H1; repointed P3's secret_mount anchor to the j2 policy template that hardcodes the prefix; corrected P4 to four drifts; rewrote P6, which fix 3 had falsified. Authored the missing eval marker that R7 and R9 cite. Edits confined to sections 6, 8, 9 and premises, matching fix_sections.)

# Plan review — cycle 2, gcs-backups-doc-to-runbook

Deterministic floor first: `loopctl verify-plan gcs-backups-doc-to-runbook`
returns `valid`, so every anchor resolves and no contract section is missing.
`loopctl plan-snapshot` returns the same plan hash and scope digest I was
briefed with, so this verdict binds the plan on disk.

## Premise verdict

**PARTIALLY SOUND.** The plan's core premise survives cycle 2 intact: the
document is stale, the jobs are live and periodic, the one false claim is the
provider version, and nobody can show a run succeeded. P1 through P5 all hold
on fresh evidence. What breaks is the delivery mechanism the cycle-1 fixes
built. R3's widened set miscounts the facts it promises to pin, one of its four
tests has no doc-side parser to write, the eval rows R7 and R9 point at do not
exist, P6's consequence clause is falsified by this plan's own section 8, and
R8 now obliges the document to assert the one unverifiable negative R9 exists
to forbid. All five are text edits confined to sections 6, 8, 9 and Premises,
and each fails loudly rather than silently if missed, which is why this is
`pass-with-required-fixes` and not a second `fail`.

## Per-assumption findings

### Stated premises

- **P1 — HOLDS.** Cluster probe, re-run this cycle on `main` at `ff911d5`:

      ID                   = backup-minio
      Submit Date          = 2026-07-07T10:02:54+02:00
      Status               = running
      Periodic             = true
      Next Periodic Launch = 2026-09-12T03:00:00+02:00 (6h33m48s from now)

  Registered and periodic, so the present tense is right for the
  configuration. The `Next Periodic Launch` at 03:00 independently confirms
  `deployments/infrastructure/services/backup-minio.hcl:7`
  > `    crons            = ["0 3 * * *"]`

- **P2 — HOLDS. Fix 1 applied correctly.** `docs/gcs-backups.md:94`
  > Google provider added (`hashicorp/google ~>6.0.0`), authenticated via ADC.

  `deployments/infrastructure/providers.tf:17`
  > `      version = "~>7.27.0"`

  The declaration is on the cited line itself, inside the `google` block that
  opens at `:15`. Plan line 41 (section 4) and plan line 140 (section 8) carry
  the same corrected anchor. Cycle-1 finding PV-01 is resolved.

- **P3 — HOLDS, with one overstated anchor. Fix 2 applied, substitution only
  half-carries.** I re-opened all eighteen anchors in the extended list. Every
  one resolves and supports its claim: the four `google_*` resources, the four
  `vault_kv_secret_v2` backup secrets, the lifecycle rule
  (`deployments/infrastructure/storage.tf:13`
  > `      age = 180`
  ), both `nomad_job` resources, both host-volume constraints (`firebat`,
  `orangepi4a`), the postgres host
  (`deployments/infrastructure/services.tf:707`
  > `      postgres_host   = "192.168.2.30"`
  , which matches `bootstrap/inventory/cluster.ini:2`), both crons, the images,
  the two variables, the bucket set and the justfile recipes.

  The substitution you flagged does NOT fully carry its claim as worded. P3
  says `deployments/infrastructure/secrets.tf:2` is "the KV v2 mount that makes
  the doc's `secret/data/default/...` paths resolve". The anchor and the line
  under it:
  > `resource "vault_mount" "kvv2" {`
  > `  path        = var.secret_mount`

  The path is a variable, and `deployments/infrastructure/variables.tf:1`
  > `variable "secret_mount" {`

  declares it with a description and a type and no default (lines 1-4). So the
  literal `secret` is not derivable from that anchor. What does carry it is an
  anchor P3 already lists,
  `bootstrap/roles/nomad_server/templates/vault_nomad_workloads.hcl.j2:1`
  > `path "secret/data/{{ '{{' }}identity.entity.aliases.{{ auth_method_accessor }}.metadata.nomad_namespace{{ '}}' }}/{{ '{{' }}identity.entity.aliases.{{ auth_method_accessor }}.metadata.nomad_job_id{{ '}}' }}/*" {`

  which hardcodes the mount name, plus the live cluster: `vault secrets list`
  returns `secret/    kv    kv_ee1db009    KV Version 2 secret engine mount`,
  whose description matches `secrets.tf:6` and so identifies that mount as
  `vault_mount.kvv2`. P3's conclusion stands. Its wording for this one anchor
  claims more than the anchor shows (fix 6 below, minor).

- **P4 — HOLDS, and undercounts in the plan's favor.** `git show be88f27`
  (`backup-swap-memex-for-openviking`) changed four structural facts in this
  file, not the three P4 names:

      -  - Constrained to `firebat` (co-located with postgres, ...)
      +  - Constrained to `radxa-dragon-q6a`, so it reads postgres ...
      -  - Resources: 1000 MHz CPU, 512 MB memory
      +  - Resources: 500 MHz CPU, 512 MB memory
      -  - Resources: 500 MHz CPU, 256 MB memory
      +  - Resources: 200 MHz CPU, 256 MB memory
      -- No node constraint (any node with network access to MinIO)
      +- Pinned to `radxa-dragon-q6a` by a node constraint, ...

  The pgdump node constraint is a fourth drift P4 omits. All four sit inside
  the family R3 now pins, so the argument gets stronger, not weaker. Note the
  pgdump CPU drift read `1000`, which is the sync task's real figure: see the
  T3 note under Required fix 1.

- **P5 — HOLDS.** Re-probed this cycle:

      Children Job Summary
      Pending  Running  Dead
      0        0        161
      Error querying job: Unexpected response code: 403 (Permission denied)

  and `nomad job allocs backup-postgres` returns `No allocations placed`. The
  ACL reads the parent and denies the children, so no run outcome is
  observable. One nuance for R9 below: the summary itself is readable, so
  "the periodic job has launched 161 children" IS observable even though
  success is not. R9's permitted list omits that, which under-states what the
  document may honestly say.

- **P6 — BREAKS.** `.loop/plans/gcs-backups-doc-to-runbook.md:266`
  > - **P6.** No code reads this document, so the rewrite cannot break a gate

  The absence half holds: I repeated the sweep and every hit for
  `gcs-backups` outside `.git` lives under `.loop/`. The consequence half is
  falsified by this plan's own section 8, which adds four tests that parse
  `docs/gcs-backups.md`. After this commit, code reads the document and the
  `uv run --project cli pytest` gate is reachable from the prose. The existing
  two tests do not read it (`cli/tests/test_backup_coverage.py:20-21` point at
  the jobspec and the applications root), which is what made P6 true before
  fix 3 widened R3.

### Implicit premises the widened plan now rests on

- **P7 (implicit) — BREAKS. "R3's set is ten facts: four CPU and memory
  figures and two container images."** `.loop/plans/...:89` and the section 8
  test list. Probe
  `.loop/scratch/gcs-backups-doc-to-runbook.plan-validator/r3_ten_facts.out`,
  identical md5 on a clean rerun:

      == T3 cpu/memory figures ==
        doc pairs: [('500', '512'), ('200', '256'), ('1000', '512')] -> numbers: 6
        source cpu: ['500', '200', '1000'] memory: ['512', '256', '512'] -> numbers: 6
      == T4b container images ==
        doc: [...postgres:18, ...rclone:latest, ...rclone:latest] (count 3 , distinct 2 )
        source: [...postgres:18, ...rclone:latest, ...rclone:latest] (count 3 , distinct 2 )

  There are three tasks, so six figures, not four: `docs/gcs-backups.md:57`
  > `  - Resources: 500 MHz CPU, 512 MB memory`

  `docs/gcs-backups.md:62`
  > `  - Resources: 200 MHz CPU, 256 MB memory`

  `docs/gcs-backups.md:75`
  > `- Resources: 1000 MHz CPU, 512 MB memory`

  against `backup-postgres.hcl:45` (`cpu    = 500`), `:69` (`cpu    = 200`) and
  `backup-minio.hcl:56` (`cpu    = 1000`) plus their three `memory` lines. The
  images are three declarations, and the one "both" drops is the upload task's,
  `deployments/infrastructure/services/backup-postgres.hcl:54`
  > `        image      = "docker.io/rclone/rclone:latest"`

  named in the doc at `docs/gcs-backups.md:58`
  > - **Main task** (`upload`): uses `docker.io/rclone/rclone:latest`, runs `rclone copy` to upload today's dump

  The arithmetic does not close either: 1 + 2 + 4 + 2 + 2 = 11, while
  `.loop/plans/...:189`
  > 4. The doc drifts again. R3 pins ten facts across four tests. It does not

  says ten. Sections 6, 8 and 9 disagree with each other and all three
  disagree with the source.

- **P8 (implicit) — BREAKS. "Both crons are parseable from the document."**
  This is the one that answers your "a test that cannot be written as
  described". `.loop/plans/...:153`
  > - `test_backup_doc_matches_jobspec_schedules_and_images` (R3) — parse both

  continues "cron expressions and both container images from the doc and the
  jobspecs". The document contains no cron expression. Probe:

      == T4a cron expressions ==
        doc cron expressions: [] (count 0 )
        source crons: ['0 2 * * *', '0 3 * * *']
        doc states clock times instead: [('2:00 AM', 'Europe/Amsterdam'), ('3:00 AM', 'Europe/Amsterdam')]

  `docs/gcs-backups.md:51`
  > Periodic batch job running at 2:00 AM Europe/Amsterdam:

  `docs/gcs-backups.md:67`
  > Periodic batch job running at 3:00 AM Europe/Amsterdam (staggered):

  Section 8 also promises "Every test fails if either of its parsers finds
  nothing", so as described this test is red by construction unless either the
  rewrite adds cron strings to the prose, which no requirement in section 6
  asks for and R7's coverage floor does not imply, or the parser translates a
  clock time into a cron, which is not the "parse both sides, assert
  agreement" shape section 8 promises. The other three tests survive: T1's
  fails-when is live today (doc `6.0.0` vs declared `7.27.0`), T2's doc side
  parses (`Constrained to`/`Pinned to` both yield `radxa-dragon-q6a`, matching
  `backup-minio.hcl:15` and its postgres twin), and T3's named fails-when is
  real (I replayed the pre-`be88f27` doc: its CPU figures do redden against the
  jobspecs, output in
  `.loop/scratch/gcs-backups-doc-to-runbook.plan-validator/t3_setcompare.out`).

- **P9 (implicit) — BREAKS. "The eval marker exists and its rows 5 and 6 check
  R7 and R9."** `.loop/plans/...:168`
  > - The scenario set in `.loop/evals/gcs-backups-doc-to-runbook.md` is the

  `ls .loop/evals/` lists 35 markers and none for this slug. R7 (plan line 110)
  says "checked by eval row 5" and R9 (plan lines 119-120) says "checked by
  eval row 6" of a file nobody has written. The `create-eval` skill authors it
  before the ticket may enter `implementing`, so the file is not overdue, but
  the row ordinals bind an ordering that does not exist yet, and the previous
  ticket's plan cited its eval without ordinals. Both requirements keep a real
  section 7 producer (the rewrite row), so the contract's producer rule is met;
  the named CHECK is a phantom.

- **P10 (implicit) — BREAKS. "The document can truthfully assert that no
  restore has been performed."** `.loop/plans/...:111`
  > - R8. The document states, in its own text, two absences: no restore

  continues "procedure exists and none has been performed". The first half is
  checkable and true: no restore procedure exists anywhere in `docs/` or in a
  script (grep over `docs/*.md` returns only unrelated uses in
  `memex-oidc-verification.md`, `openviking-dashboard.md` and `monitoring.md`).
  The second half is not checkable from this repo or this cluster. The very ACL
  denial P5 rests on hides restores as thoroughly as it hides successful runs,
  and no operator action is recorded in-tree. R9 forbids exactly this shape of
  claim in the positive direction; R8 mandates it in the negative one. R8's
  second absence is already hedged correctly ("no read-back of any backup has
  been verified"); the first one is not.

- **P11 (implicit) — HOLDS. "R1's narrowing and R7's floor cohere."** This
  answers your (b). I checked R1 against all fourteen headings of the current
  document: `# Nightly GCS Backup Jobs`, `## Context`, `## Prerequisites`,
  `## Vault Policy Constraint`, `## Architecture` and its three `###` children,
  `## Configuration` and its three `###` children, `## GCS Path Structure`,
  `## Verification`. None of them presents the JOBS as new, which is the
  narrowed ban. `## Prerequisites` presupposes a reader about to run
  `terraform apply`, and R1 now names it as staying, re-framed to
  infrastructure-change work, so the general clause and the carve-out agree
  rather than fighting. The residual case is inside `## Verification`:
  `docs/gcs-backups.md:118`
  > `# Deploy (re-init needed first time to fetch google provider)`

  which frames the PROVIDER as newly added, not the jobs. Under cycle 1's R1 it
  was banned while R7 required it kept; under the narrowed R1 it may stay
  verbatim, and R7 keeps it. The contradiction is gone and no new one replaces
  it. One structural note, not a defect: R1 keeps the `just init` / `just
  apply` block while section 7 turns `## Verification` into the operating
  procedure, so the block wants moving under `## Prerequisites`. R7 explicitly
  permits a move.

- **P12 (implicit) — HOLDS, with a naming residue. "Section 5's scope bullet
  plus R8 make the artifact honest."** This answers your (c). The plan's own
  text is consistent: the front-matter summary says "operator reference",
  section 1 says "operator reference", section 5 bounds the word and points at
  R8, R8 puts the admission in the artifact where a reader in an incident meets
  it, and section 9's failure mode 3 names the exact risk. That is honest
  rather than oversold: the ticket no longer promises recovery and now makes
  the document disclaim it. Two residues. The slug still says `runbook`, which
  is outside every bound section and cosmetic. The document's own H1,
  `docs/gcs-backups.md:1`
  > # Nightly GCS Backup Jobs

  is not cosmetic: "Nightly" is the adverb R9 polices, and section 7 says only
  "rewritten whole" without saying whether the title stays. It is defensible as
  a claim about the jobs' schedule rather than about backups landing, but the
  plan should decide it rather than leave it to the implementer. Recorded as
  required fix 5.

## Most dangerous assumption

**P8.** If the cron premise is wrong, one of the four tests R3 promises cannot
be written in the shape section 8 describes, and the implementer discovers it
only after rewriting the prose. Every other break here is a number or a phrase
to correct; this one is the difference between a test that exists and one that
gets quietly downgraded to "close enough" at implementation time, which is the
failure R3 was widened to prevent.

## Required fixes

1. **Section 6 (R3), section 8 (test 3), section 9 (item 4) — correct the
   counts.** There are six CPU and memory figures across three tasks, not four,
   and three image declarations, not two. Say so, and make section 9's total
   match whatever section 6 enumerates. While there: test 3 should bind each
   figure to its task rather than comparing sets. The drift P4 records is
   exactly a figure appearing against the wrong task, and a set comparison of
   the memory figures stays green through it
   (`.loop/scratch/gcs-backups-doc-to-runbook.plan-validator/t3_setcompare.out`:
   the drifted doc's memory multiset matches the source's).

2. **Section 6 (R3) and section 8 (test 4) — settle the cron fork.** Two
   acceptable answers, and the plan must pick one. `add-cron-to-doc`: state in
   R3 and in section 7's rewrite row that the document carries the literal
   `0 2 * * *` and `0 3 * * *` beside the human-readable times, so the test is
   a string match on both sides. `translate-in-parser`: keep the prose times
   and say in section 8 that the doc-side parser derives the cron from
   "H:MM AM <tz>", naming the translation as part of the test. I recommend
   `add-cron-to-doc`: it keeps the "parse both sides" shape the other three
   tests use, it is what an operator greps for when they open the Nomad UI, and
   it leaves the prose time in place so R7's floor is untouched.

3. **Section 6 (R7, R9) and section 8 — stop citing eval rows that do not
   exist.** Either drop the ordinals and cite the scenario set the way the
   previous ticket's plan did, or say the eval is still to be authored and name
   the two behaviors it must score. As written, R7 and R9 point at rows 5 and 6
   of a file that is not on disk.

4. **Section 6 (R8) — hedge the restore absence to what is checkable.** "No
   restore procedure exists and none has been performed" asserts a history
   nobody in this repo can see. "No restore procedure is documented and no
   restore has been verified" carries the same warning to the reader and stays
   inside what P5's evidence supports.

5. **Section 7 or section 6 (R9) — decide the title.** Say whether
   `# Nightly GCS Backup Jobs` survives, and if it does, note that R9 reads it
   as a claim about the jobs' schedule rather than about backups landing.
   Optional but cheap while you are in R9: the `Children Job Summary` IS
   readable (`Dead 161`), so the document may honestly say the periodic job has
   launched children nightly, only not that those children succeeded.

6. **Premises — repair P6, and tighten P3's one overstated anchor.** P6's "the
   rewrite cannot break a gate other than the writing-style scan" is false once
   this ticket's own tests parse the document; narrow it to the absence it
   really establishes ("nothing outside `.loop/` references this document
   today"). P3's `secrets.tf:2` shows a KV v2 mount at `var.secret_mount`, not
   the literal `secret`; point the mount-name claim at the policy template you
   already cite, which hardcodes it. Your substitution carries the
   "KV v2 mount exists" half of the claim and not the "mounted at `secret`"
   half; the claim is still true, and the live cluster confirms it, but that
   anchor is not what proves it.

## Also checked, clean

- `loopctl verify-plan` returns `valid`.
- R6's gate anchors: `justfile:18` defines `pre_commit`, and
  `.pre-commit-config.yaml:58`
  > `        entry: uv run --project cli mypy --config-file cli/pyproject.toml cli/src cli/tests scripts`

  is the mypy-strict hook covering `cli/tests`, exactly as R6 states.
- Section 8's direct command works today:
  `uv run --project cli pytest cli/tests/test_backup_coverage.py -q` returns
  `2 passed in 0.02s`, so "all six tests" after four are added is right.
- Every test named in section 8 has its file in section 7. Every requirement in
  section 6 names a producer in section 7 or an existing repo capability the
  plan cites. Non-goals are explicit. Q1 carries a recommendation and its
  premise is in the front-matter table.
- Section 5's memex bullet: `deployments/applications/secrets.tf:28` is
  `resource "vault_kv_secret_v2" "memex_db_credentials" {`, whose `name` is
  `default/memex/postgres`, so the per-job path pattern claim holds.
- No file in section 7 is unreached by a requirement.

## Cycle-1 findings, re-attacked

- PV-01 (P2's off-by-one anchor) — resolved; the three call sites all read
  `providers.tf:17` and the line carries the version.
- PV-02 (P3's anchor coverage) — resolved; all eighteen added anchors re-opened
  and support their claims, with the one wording gap in required fix 6.
- PV-03 (section 9's "and cannot") — resolved; the clause is gone. Superseded
  by P7, P8 and the note below on R3's universal clause.
- PV-04 (R3 narrower than P4's evidence) — resolved; R3 now pins the family
  that actually drifted, and `git show be88f27` shows a fourth drift in the
  same family.
- PV-05 (R1 against the coverage floor) — resolved; see P11, checked against
  all fourteen headings.
- PV-06 (the restore-gap contradiction) — resolved; R8 owns it with a producer
  and Q1 records the deferral. New wording defect raised as required fix 4.
- PV-07 (no observable run outcome) — confirmed on a fresh probe and now
  carried as premise P5.
- PV-08 (tree moved mid-pass) — closed; the tree is stable on `main` at
  `ff911d5` for this whole pass.

One cycle-1 observation I am carrying forward rather than making a required
fix: R3's opening sentence still claims universality ("Every doc claim that is
mechanically parseable from both the document and its source is pinned by a
test") while its enumerated set excludes `Europe/Amsterdam` (two per side), the
`entrypoint = ["/bin/sh", "-c"]` override (three per side), `network_mode =
"host"`, and the 180-day lifecycle age, all of which my probe shows parse from
both sides. The enumerated set is a defensible choice on P4's evidence and I am
not asking for more tests. Reword the sentence to describe the chosen set
rather than claiming completeness, in the same edit as required fix 1.

## Scratch

- scratch created at `.loop/scratch/gcs-backups-doc-to-runbook.plan-validator/`
  (`r3_ten_facts.py`, `r3_ten_facts.out`, `r3_rerun.out`, `t3_setcompare.py`,
  `t3_setcompare.out`, `doc_prefix.md`).
- WARN — scratch artifact left at
  `.loop/scratch/gcs-backups-doc-to-runbook.plan-validator/r3_ten_facts.out`
  and its siblings, deliberately: they are the captured probe output this
  verdict cites and the next cycle's evidence. `findings.json` in the same
  directory carries the cycle-2 ledger.

## Side effect to disclose

I ran `loopctl plan-snapshot gcs-backups-doc-to-runbook` to confirm the plan
hash and scope digest in my briefing against the plan on disk. It confirmed
both (`plan 10f6d86d172c / scope dc68d9975987`), and it also REWROTE
`.loop/verdicts/gcs-backups-doc-to-runbook.plan-validator.snapshot.md` from the
cycle-1 plan text to the cycle-2 plan text (160 insertions, 82 deletions). That
is a repo write outside my read-only contract and I did not intend it; I did
not revert it, because reverting means a mutating git command I am also
forbidden. Nothing is masked by it: the snapshot now holds exactly the plan
content this verdict's `plan:` line binds, which is the content I reviewed.
Check it before the flip if the gate reads that file.
