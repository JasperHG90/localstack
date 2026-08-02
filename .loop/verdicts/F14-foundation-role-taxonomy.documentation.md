---
verdict: pass
tree: c20ec46e3b3365a5f7154659f8d0c4ea34326300
---

# F14-foundation-role-taxonomy: documentation re-bind

Scope of this pass: the two sentences that moved since my `pass` at
`a33da432`, and the claim that nothing else in the docs moved. The full
walk (introduction/block agreement in `docs/cluster-roles.md` and
`docs/vault-human-auth.md`, the runbook commands against a throwaway dev
server, the `oidc.tf` header list agreeing with both docs) is not
re-litigated.

## 1. The rewritten sentence is accurate

`docs/cluster-roles.md:49-51`

> Verified rather than assumed: a member added by hand survives an apply
> that really writes the group, rather than one that merely skipped the
> diff.

Both halves are backed by the eval file:

- "an apply that really writes the group" is
  `.loop/evals/F14-manual-eval-results.md:77-88`: a real change to the
  group (adding the `metadata` description) with a hand-added member
  present, member present before and after.
- "rather than one that merely skipped the diff" is the weaker first test
  at `.loop/evals/F14-manual-eval-results.md:66-76`, where the apply was a
  no-op and the eval itself says so.

The `metadata` description that made that apply a real write is in the
tree at `deployments/infrastructure/roles.tf:133-135`, so the measurement
matches the config a reader will find.

The sentence still carries why the real write is the stronger evidence: it
names the two applies and says which one the member survived. The reader
of a runbook needs the conclusion. The reasoning ("it proves the
provider's *diff* ignores the field, not that the write path preserves
it", `.loop/evals/F14-manual-eval-results.md:75-77`) stays in the eval,
which is the right split.

Dropping the `(0 added, 2 changed)` parenthetical removes a hazard rather
than evidence. That count no longer reproduces: the second changed
resource was the operator entity being repaired, and
`.loop/evals/F14-manual-eval-results.md:56` records that `terraform plan`
now reports no changes. A reader who re-ran the test and saw `1 changed`
would have concluded the doc was wrong about something it was right about.

## 2. No contradiction with the eval file

The eval's corrected fields-vs-maps generalisation
(`.loop/evals/F14-manual-eval-results.md:58-64`) and the doc's claim
(`docs/cluster-roles.md:96-100`) agree, and both agree with the measured
finding at `.loop/evals/F14-manual-eval-results.md:166-171`: omitted
fields are preserved, the membership list is replaced.

The new map-valued-field caveat does not open a gap in the doc. The
`admin` group does carry a map (`metadata.description`,
`deployments/infrastructure/roles.tf:133-135`), but the runbook at
`docs/cluster-roles.md:86-93` writes only `member_entity_ids` and never
sets a metadata key, so the map is omitted, not partially written. An
operator following the doc verbatim cannot trigger the map eviction the
eval describes. No warning is owed and none is missing.

The corrected chronology is internally consistent. Eviction one is
repaired by the next apply, which is the Requirement 2 write-path test
(`.loop/evals/F14-manual-eval-results.md:51-53` and `:84-86` describe the
same apply from both ends). Eviction two sat as drift until a reviewer's
plan found it (`:53-56`). Nothing in `docs/cluster-roles.md` depends on
that ordering, so there is no drift to propagate.

## 3. Nothing else in the docs moved

`git diff main --stat` touches two files under `docs/`:
`docs/cluster-roles.md` and `docs/vault-human-auth.md`. Modification times
place the verdict I wrote last pass at 13:51:45 and every other artifact
before it: `docs/vault-human-auth.md` at 13:21:02,
`deployments/infrastructure/roles.tf` at 13:32:25,
`deployments/infrastructure/oidc.tf` at 13:32:59. Only
`docs/cluster-roles.md` and `.loop/evals/F14-manual-eval-results.md` are
newer, both at 13:53:12. Every other file under `docs/` sits at 12:55:43,
untouched by this branch.

Spot checks on the surfaces that could have drifted underneath the edit
all hold: the four-answer list in `docs/cluster-roles.md:143-157` matches
`docs/vault-human-auth.md:236-268` and the header comment at
`deployments/infrastructure/oidc.tf:13-23`; no doc cites a
`terraform apply` resource count anywhere; every file path the doc names
(`developer_group.tf`, `roles.tf`, `oidc.tf`, `docs/vault-human-auth.md`)
resolves.

`Break-glass` in `deployments/infrastructure/roles.tf:134` is unchanged,
as agreed. I am not reopening it.

## Findings

**No blocking findings.** Two informational nits, neither a doc-drift
issue and neither worth staling the tree for. Recording them so the next
editor of this file has them, not as fixes required before commit.

- INFO, `docs/cluster-roles.md:49-51`: the sentence now carries "rather
  than" twice ("Verified rather than assumed", then "rather than one that
  merely skipped the diff"). It reads a little doubled. It does not
  mislead.
- INFO, `docs/cluster-roles.md:49`: the membership-survival claim has no
  provenance anchor, while the neighboring fields claim at line 97 has
  "Measured on 2026-08-02". Fold the date in only if this file is being
  edited for another reason.

## Verdict

pass. No documented surface in this diff is stale. A reader following
`docs/cluster-roles.md` or `docs/vault-human-auth.md` as they stand at
`c20ec46e3b3365a5f7154659f8d0c4ea34326300` will be right about what the
code does. Bind and commit.
