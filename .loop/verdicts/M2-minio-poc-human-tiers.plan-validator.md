---
verdict: pass-with-required-fixes
plan: 3225faf977ce46fc997ec4d407c562aadff37039f3af1d088961490d659fbee2
bound_paths: front-matter, 5, 6, 7, 8, 9, 10, premises
scope: b9af3c5bc44988a2b5a9de3b8331783196d208130d6138d01c9608d683d9ad1c
fix_sections: 8, premises
citations:
  deployments/infrastructure/roles.tf:153-165 = "app-memex-admins"  = "Full access to memex through Vault SSO"
  deployments/infrastructure/roles.tf:174-178 = app_user_group_members = { "app-memex-admins" = [vault_identity_entity.operator.id] }
  deployments/infrastructure/roles.tf:187-189 = member_entity_ids = lookup(local.app_user_group_members, each.key, [])
  deployments/infrastructure/oidc.tf:79-86 = oidc_provider_client_ids = [ vault_identity_oidc_client.smoke.client_id, ... ]
  deployments/infrastructure/services.tf:328-333 = resource "nomad_job" "minio" { jobspec = templatefile(...) }
  deployments/infrastructure/services/minio.hcl:32-40 = template { data = <<-EOH ... MINIO_PROMETHEUS_AUTH_TYPE="public" EOH destination = "secrets/file.env" env = true }
  deployments/applications/modules/bucket/main.tf:11-27 = resource "minio_iam_policy" "policy_read_write" { ... "Action": ["s3:*"] ... }
  .loop/plans/M2-minio-poc-human-tiers.md:209-211 = "writer = put/get/list + multipart + delete (Resolved fork Q5); reader = get/list."
  .loop/plans/M2-minio-poc-human-tiers.md:381-388 = "Mirror the JSON statement shape in deployments/applications/modules/bucket/main.tf:11-45."
  .loop/plans/M2-minio-poc-human-tiers.md:498-506 = the four §8 step-5 / row-6 sub-parts (reader, admin-refused, writer, admin)
  .loop/plans/M2-minio-poc-human-tiers.md:509-526 = the parenthetical explaining the fifth-review expansion to three windows / four sub-parts
  .loop/plans/M2-minio-poc-human-tiers.md:528-529 = "Steps 1-4 are runnable now once this ticket's Terraform is applied and the job redeployed; step 5 is the manual residual."
  .loop/plans/M2-minio-poc-human-tiers.md:619-621 = "run the scripted evals (steps 1-4) and the manual browser check (step 5), and record the reader-refused-by-admin result."
  .loop/plans/M2-minio-poc-human-tiers.md:676 = "1. **Reader window.** Edit `local.app_user_group_members` to move"
  .loop/plans/M2-minio-poc-human-tiers.md:685 = "2. **Writer window.** Edit `local.app_user_group_members` again to"
  .loop/plans/M2-minio-poc-human-tiers.md:690 = "3. **Admin window (final, steady state).** Revert"
  .loop/plans/M2-minio-poc-human-tiers.md:892-905 = P16, unchanged text: "three sub-parts... §8 step 5 and §11 step 2 now split the row's sub-parts across both windows"
  .loop/plans/M2-minio-poc-human-tiers.md:923-931 = P18 text
  .loop/plans/M2-minio-poc-human-tiers.md:932-940 = P19 text
  .loop/evals/M2-minio-poc-human-tiers.md:10 = "Same check as the row below's Reader sub-part. (No independent scripted mechanism exists...)"
  .loop/evals/M2-minio-poc-human-tiers.md:12 = "(c) writer window — a `minio-writers` member clicks Writer, has put/get/list but not delete-bucket/policy actions"
  .loop/verdicts/M2-minio-poc-human-tiers.plan-validator.snapshot.md:892-905 = P16, byte-identical to the current plan's P16 (confirms no fix was made here across the two rounds)
---

# Plan review, pass 5: M2-minio-poc-human-tiers

## Premise verdict: PARTIALLY SOUND

`loopctl verify-plan M2-minio-poc-human-tiers` → `valid` (same ambiguous-basename
warnings as last pass on `secrets.tf`/`services.tf`/`providers.tf`, no hard
fail). `loopctl verify-eval-substance M2-minio-poc-human-tiers` → `valid`.
Plan fingerprint confirmed two ways: `sha256sum .loop/plans/M2-minio-poc-human-tiers.md`
→ `3225faf977ce46fc997ec4d407c562aadff37039f3af1d088961490d659fbee2`, matching
what I was given, and a scratch replica of `loop_harness.stamp.plan_fingerprint`
(no `sections=` argument) reproduced the identical whole-file hash from source,
which also cross-validates the section-keyed `scope:` digest computed by the
same script (see "What I did this pass"). Both deterministic gates are clean,
so this is a semantic pass, not a mechanical one.

**P18 and P19, this pass's headline items, are genuinely closed.** The
Writer tier is now dynamically exercised (a real login, a real policy check)
and eval row 4's dead-end mechanism is honestly retired in favor of row 6's
reader sub-part, which the plan's own non-goals independently corroborate
(§5's STS non-goal names the exact mechanism that would have been needed and
places it out of scope, so there was never a way to build row 4 as originally
conceived). The three-window sequence in §11 is internally consistent: no
membership overlap, no gap, and it returns to exactly the steady state §7
ships.

**But two defects survive this round**, one carried over and one newly
introduced as a side effect of this round's own fix. Required fix #3 from
my own prior verdict (`.loop/plans/M2-minio-poc-human-tiers.md:528-529`,
the "Steps 1-4 are runnable now" line) was on the required-fix list and was
not applied — the operator's own summary of "fixes made" for this round
does not mention it, and the line is byte-identical to the version I
reviewed last pass. And **P16**, a premise this round's diff never touched,
now asserts something false about the plan's own current text: it says the
close-out "has three sub-parts" split across "both windows" with "§11 step
2" as the admin window, when the plan's own §8/§11 (edited THIS round to
fix P18) now have four sub-parts across three windows, and §11 step 2 is
the *Writer* window, not Admin. Neither defect is architecturally
load-bearing and neither blocks an implementer from building or running a
correct acceptance pass — the substantive text (§8, §11) is self-consistent
on its own — but both are real, both are confined to §8 and Premises, and
both are cheap fixes an operator should not have to re-discover a sixth
time. Hence `pass-with-required-fixes`, not `pass`.

## What I did this pass

Read the full plan fresh, end to end, treating §5/§6/§7/§8/§10/§11 as one
unit per the brief. Diffed the current plan against the 4th-round snapshot
(`.loop/verdicts/M2-minio-poc-human-tiers.plan-validator.snapshot.md`) at
the section level (`csplit` on `^## ` headings, then `diff` each pair) to
scope exactly what changed: only §8, §11, and Premises differ; front-matter,
§5, §6, §7, §9, §10, and both "Resolved forks" blocks are byte-identical to
the version I already reviewed and passed last round. This let me spend the
budget on the actual delta (P18/P19's fix, plus a fresh full read for a
sixth defect) rather than re-deriving sections nothing touched.

Re-read `roles.tf:153-165,174-178,187-189`, `oidc.tf:79-86`,
`services.tf:328-333`, `minio.hcl:32-40`, and
`modules/bucket/main.tf:11-45` directly (not trusting last pass's read) to
confirm the repo hasn't drifted under the plan since the last review — it
hasn't; `git log -- .loop/plans/M2-minio-poc-human-tiers.md` shows no
commits since `A1-audit-plan-premise-sweep`, and none of these files
changed. Ran `mc --help`, `mc admin --help`, `mc admin accesskey --help`,
and `which aws` fresh this pass (not reusing last pass's captured output)
to re-verify P19's environment claim independently.

To compute the `scope:` digest without running `loopctl plan-snapshot`
(which writes a snapshot file outside my read-only contract), I wrote a
scratch script that reproduces `loop_harness.stamp.plan_fingerprint` /
`_plan_section_bytes` / `plan_check._split_sections` from the harness's own
source (`src/loop_harness/stamp.py:637-675`, `src/loop_harness/plan_check.py:304-343`),
read directly from this repo's vendored plugin. Its whole-plan-fingerprint
output matched the independently-computed `sha256sum` exactly
(`3225faf977ce...`), which cross-validates that the section-keyed digest it
also printed (`b9af3c5bc4498...`) is a faithful reproduction of the
harness's own algorithm, not a guess.

Scratch used: `.loop/scratch/M2-minio-poc-human-tiers.plan-validator/`
(`compute_scope.py`, the section-digest replica). Removed at end of pass.

## Per-assumption findings

- **P1, P2, P7, P8, P9, P11, P12, P13 — no change in scope, still hold.**
  None of these premises' underlying repo anchors changed since last pass
  (confirmed via `git log`, no commits touch this plan or the cited
  infrastructure files), and the plan's own prose for §4/§9 (where most of
  them are grounded) is outside this round's diff (only §8/§11/Premises
  changed). Re-read `roles.tf:153-165`, `services.tf:328-333`,
  `minio.hcl:32-40` fresh this pass as a spot check (see "What I did"
  above) and confirmed all three resolve exactly as last pass reported.

- **P3, P4, P5, P6 — no change in scope, still hold.** These are upstream
  MinIO source claims (symbol-cited, not line-cited, per the plan's own
  convention) about a pinned release tag that has not changed. Not
  re-fetched this pass; nothing in this round's diff touches them or the
  claims they support.

- **P10 — UNCERTAIN, unchanged, as the plan itself discloses.** Still an
  inference (the `access_denied` shape for an assignment mismatch), still
  flagged by the plan as such, still requires this ticket's own Terraform
  applied to reproduce live. Not re-attempted this pass for the same reason
  as last pass: out of scope for a plan-only review.

- **P17 — HOLDS, no change in scope.** `roles.tf:174-178` and `:187-189`
  re-read fresh this pass:
  > "app-memex-admins" = [vault_identity_entity.operator.id]
  > member_entity_ids = lookup(local.app_user_group_members, each.key, [])
  Exactly as last pass confirmed. §7's bullet adding the `app-minio-admins`
  entry (unchanged this round, part of the byte-identical §7) is still the
  only membership producer, and §11's now-three-window sequence (see P18
  below) still routes every membership change through this exact local.

- **P18 — HOLDS. The Writer-tier acceptance gap is closed.**
  `.loop/plans/M2-minio-poc-human-tiers.md:498-506`:
  > - a `minio-readers` member clicks the **Reader** login button, ...
  > - the same user clicks the **Admin** login button and is refused ...
  > - a `minio-writers` member clicks the **Writer** login button and
  >   has put/get/list access, but not delete-bucket or policy actions;
  > - a `minio-admins` member clicks the **Admin** button and has full
  >   access.
  Four sub-parts, one per tier transition plus the reader→admin refusal,
  where last pass found only two tiers named. `.loop/plans/M2-minio-poc-human-tiers.md:676,685,690`:
  > 1. **Reader window.** ...
  > 2. **Writer window.** ...
  > 3. **Admin window (final, steady state).** ...
  Three windows, where last pass found two. I independently walked the
  sequence for overlap/gap rather than trusting the labels: window 1 sets
  `app-minio-readers` = [operator] with the admins entry removed (line
  676-681, "remove the `app-minio-admins` entry for this step"); window 2
  explicitly removes the window-1 reader entry before adding the writer one
  (line 685-687, "remove the `app-minio-readers` entry from step 1"); window
  3 explicitly reverts to "no entry for `app-minio-readers` or
  `app-minio-writers`" and restores `app-minio-admins` (line 690-693). At no
  point does the map hold two tier keys at once, and the final state is
  textually identical to §7's shipped `local.app_user_group_members` bullet
  (`operator` in `app-minio-admins` only) — confirmed by direct comparison,
  not inference. No overlap, no gap, ends at the exact steady state §7
  ships.
  On the operator's specific cross-check (does the writer window's positive
  check verify against real IAM policy semantics for `minio-writer`): §6.2
  (`.loop/plans/M2-minio-poc-human-tiers.md:209-211`)
  > writer = put/get/list + multipart + delete (Resolved fork Q5)
  and Q5 (`:728-730`)
  > Full write including `s3:DeleteObject`
  give an unambiguous semantic requirement, but §7's applications-layer
  bullet (`:381-388`) gives NO independent action-set enumeration of its
  own — it only says to mirror `modules/bucket/main.tf:11-45`'s JSON
  *shape* and match `role_policy` name strings. `modules/bucket/main.tf:11-27`
  itself uses `"Action": ["s3:*"]` for its own read-write policy — a
  wildcard that, if copied literally into the writer tier instead of
  translated from §6.2's specific list, WOULD include `s3:DeleteBucket` and
  contradict row 6's own expectation ("not delete-bucket ... actions").
  This is a real specificity gap — §7 never pins the exact IAM action
  strings the way it pins, e.g., the exact env var names and URL literals
  elsewhere in this same ticket — but I do not rate it a required fix: the
  three tiers' whole point is different action sets, so a competent
  implementer reading §6.2 right next to §7 has no plausible reading that
  copies `s3:*` for all three; and even if they did, `mc admin policy info`
  (eval step 2, deterministic, 100% threshold) and row 6's manual
  delete-bucket check would catch it at acceptance time rather than pass
  silently. Reported as an observation, not folded into required fixes.

- **P19 — HOLDS. Row 4's mechanism gap is honestly, non-circularly
  resolved.** `.loop/evals/M2-minio-poc-human-tiers.md:10`:
  > Same check as the row below's Reader sub-part. (No independent
  > scripted mechanism exists: `aws` is not on PATH and `mc` has no
  > OIDC/web-identity flow in this environment ...)
  Re-probed this pass, not reused from last pass: `which aws` → no output
  (absent); `mc admin --help` (captured fresh) lists no OIDC/STS/web-identity
  subcommand; `mc admin accesskey --help` (captured fresh) lists
  `sts-revoke` (revoking an existing STS session) but no create/obtain
  command — there is no way to mint a web-identity session with `mc` alone,
  confirming the plan's claim rather than assuming it. The redefinition is
  not circular: row 4's Input/Expected/Scorer cells now literally point at
  row 6's reader sub-part rather than asserting a second, independent
  measurement of the same fact, and this is additionally consistent with
  §5's own non-goal
  (`.loop/plans/M2-minio-poc-human-tiers.md:184-185`, unchanged, not part of
  this round's diff): "The machine/service (STS `AssumeRoleWithWebIdentity`
  or access-key) path... is out of scope" — the one mechanism that could
  have scripted row 4 was already excluded by the plan's own design, not
  merely unavailable in this sandbox. Nothing row 4 originally wanted (a
  reader obtains a session and gets read-only S3) is dropped: it is
  observed exactly once, by row 6, instead of twice by two mechanisms one
  of which never existed.

- **P16 — BREAKS, as literally written, against the plan's own current
  text.** `.loop/plans/M2-minio-poc-human-tiers.md:892-903`:
  > The manual browser close-out (§8 step 5, eval row 6) has
  > three sub-parts, and they do not all belong to the same §11
  > sequencing window: two (reader clicks Reader; same session clicks
  > Admin, refused) require `operator` to still be `app-minio-readers`-
  > only, and one (admin clicks Admin, full access) requires `operator`
  > already promoted to `app-minio-admins`. ... §8 step 5 and §11 step 2
  > now split the row's sub-parts across both windows explicitly
  This is false against the plan's own current §8/§11: row 6 now has FOUR
  sub-parts (reader-positive, reader-denied-admin, writer-positive,
  admin-positive — see P18 above), split across THREE windows, not two;
  and `.loop/plans/M2-minio-poc-human-tiers.md:685` shows §11 step 2 is now
  the **Writer** window, not the Admin window P16 describes. I confirmed
  this is not a stale reading on my part by diffing P16's exact text
  against the 4th-round snapshot
  (`.loop/verdicts/M2-minio-poc-human-tiers.plan-validator.snapshot.md:892-905`):
  byte-identical. P16 was accurate when written (against that round's
  two-window, three-sub-part §8/§11) and was simply never revisited when
  this round's P18 fix rewrote the sections it describes. The underlying
  MECHANISM claim inside P16 — Vault's `/authorize` assignment check reads
  group membership fresh per request, with no cache — is untouched by this
  and I have no reason to doubt it still holds (it is a claim about Vault's
  own code, not about this plan's structure, and nothing in this round
  touched Vault or its cited source). Only the plan's self-descriptive
  cross-reference (sub-part count, window numbering) is what's false. This
  is confined and mechanical to fix — rewrite lines 892-903 to say "four
  sub-parts" across "three windows" and correct "§11 step 2" to name the
  Writer window (with a corresponding mention of step 3 for Admin) — but it
  is a premise, in the reviewed floor, and it is currently a false
  statement about this plan's own content, so it is marked `BREAKS` rather
  than softened.

- **Additional required fix, carried over from last pass, still
  unaddressed.** `.loop/plans/M2-minio-poc-human-tiers.md:528-529`:
  > Steps 1-4 are runnable now once this ticket's Terraform is applied and
  > the job redeployed; step 5 is the manual residual.
  This was required fix #3 in my prior verdict (bound to plan hash
  `2d4dbd37ec655...`). It is byte-identical in the current plan (confirmed
  by the section diff in "What I did this pass" — §8's opening "Repo gate"
  paragraph and this closing line both fall outside the lines the P18/P19
  fix touched). The underlying issue is unchanged: read literally, this
  says step 4 needs nothing beyond the initial shipped-state apply, which
  is false on the plan's own terms since step 4's "should succeed" half
  needs `operator` in `app-minio-readers`, a state only §11 step 1's
  temporary edit produces. §11 step 1 itself already gets this right
  (`.loop/plans/M2-minio-poc-human-tiers.md:676-684` names row 5 — this
  ticket's own numbering for the cross-tier-deny check — as run in that
  window). The operator's summary of "fixes made" for this round lists four
  items and this line is not among them, consistent with the diff showing
  no edit here.

## Additional observations (not required fixes)

- `.loop/plans/M2-minio-poc-human-tiers.md:619-621` (§10 subticket 4) still
  says "record the reader-refused-by-admin result" with no mention of the
  writer-tier result or the now-three-apply sequence. This phrase is
  byte-identical across all reviewed rounds (confirmed against the 4th-round
  snapshot), so it is not a regression introduced by this round's fix, and
  §11's own text (unaffected) already requires the fuller record ("Document
  the exact sequence, the group membership at each step, and the three
  applies in the acceptance notes"). §10 is a decomposition summary, not the
  operative instruction, so I do not require this be fixed, but the operator
  may want to tidy it while touching §8/Premises for the two required fixes
  above.
- Neither the scripted cross-tier-deny check (row 5 / §8 step 4) nor the
  manual close-out (row 6) ever tests a Writer entity being refused by the
  Admin or Reader clients, or an Admin/Reader entity being refused by the
  Writer client — only Reader-refused-by-Admin is dynamically proven. The
  underlying Vault mechanism (`pathOIDCAuthorize`/`entityHasAssignment`,
  per P16) is generic and not tier-specific code, so one dynamic proof
  gives real, if not exhaustive, confidence the same code path holds for
  every tier pair; row 3's static `group_ids` check covers the rest. This
  is the same level of rigor a prior round already accepted for the
  two-tier case, extended unchanged to three, so I treat it as an
  acceptable POC-scope simplification rather than a gap to fix.
- Row 6's writer sub-part checks the negative (no delete-bucket, no policy
  admin) but never affirmatively exercises the "delete" grant Q5 gives
  writer (`s3:DeleteObject`). The security-relevant half (no privilege
  escalation) is tested; the purely-affirmative half is not. Minor, and
  consistent with the same asymmetry already present (and accepted) in the
  reader/admin sub-parts before this round.

## Most dangerous assumption

Unchanged from what actually underlies this round's fix: **the load-bearing
half of P16** — that Vault's `/authorize` assignment check
(`pathOIDCAuthorize`/`entityHasAssignment`) reads group membership fresh on
every request, with nothing cached or snapshotted at login time. Every
window in §11's sequence, old or new, depends on this: if Vault instead
cached membership at token-issuance or session-start, the three-window
dance would prove nothing — a session could retain admin-level access after
a membership edit, and the "reader refused by admin client" and "writer
refused by delete/policy actions" checks could pass against a broken
implementation for the wrong reason. This premise's mechanism claim still
holds; only its self-descriptive counts are stale (see P16 above).

## Required fixes (for `pass-with-required-fixes`)

1. Fix `.loop/plans/M2-minio-poc-human-tiers.md:528-529` ("Steps 1-4 are
   runnable now...") to state that step 4's "should succeed" half
   additionally requires §11 step 1's window — carried over, unaddressed,
   from the prior verdict. Touches §8.
2. Update P16 (`:892-905`) to match the plan's own current §8/§11: four
   sub-parts, not three; three windows, not two; and correct "§11 step 2"
   to name the Writer window (adding a corresponding reference to step 3
   for Admin). Touches Premises.

Both fixes are confined, mechanical, and do not touch the underlying
architecture, which I independently re-confirmed against the unchanged repo
state this pass.
