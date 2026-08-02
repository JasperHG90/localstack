---
verdict: pass
tree: c20ec46e3b3365a5f7154659f8d0c4ea34326300
---

# F14 — final re-bind at `c20ec46e…`

Both REQUIRED fixes are applied and both are correct. The tree moved by exactly
the one sentence you said it would, the gate is green, and the cluster reports
no drift. Commit it.

Per your instruction I did not re-walk the entity metadata repair, the
join/leave agreement, the gate content, or LOW-1. I verified the four things
you listed.

## 1. The eval's chronology and generalisation

**Chronology — correct now.** `.loop/evals/F14-manual-eval-results.md:46-56`
states the order you described: the probe evicted both metadata keys, the very
next apply repaired that first eviction and that is where Requirement 2's
"2 changed" came from, clearing the probe key evicted them a second time, and
that second one sat as live drift until a plan found it and a further
`0 added, 1 changed` apply repaired it. The file's own Requirement 2 block
agrees rather than contradicts: `:84-86` attributes the second changed resource
to the operator entity and calls it the repair of the probe's clobber.

The lesson sentence at `:55-56` — "Terraform healing the first one is what made
the second easy to miss" — is the one that earns the paragraph. It names why the
drift survived, not just that it happened.

Independently confirmed on the cluster: `vault read
identity/entity/name/operator` returns `metadata {'kind': 'human', 'managed_by':
'terraform'}`, both keys present. The repair is real, not asserted.

**Generalisation — matches the file's own measurement now.** `:58-64` reads
"Fields omitted from a write **are** preserved … What is not preserved is the
rest of a **map-valued field** … Fields merge; maps do not." That is exactly what
this file measures in two places: `:166-171` records that a membership-only write
left `policies ['admin']` and `type internal` intact, and `:46-52` records that
writing one `metadata` key dropped the other. The old claim ("a probe that writes
one field silently drops the rest") contradicted the first of those; the new one
is entailed by both. `docs/cluster-roles.md:96-100` tells the operator the same
thing in the same direction, so eval and runbook no longer disagree.

## 2. The membership-evidence sentence in `docs/cluster-roles.md`

`docs/cluster-roles.md:49-51`:

> Verified rather than assumed: a member added by hand survives an apply that
> really writes the group, rather than one that merely skipped the diff.

Accurate, and accurate without the count. The evidence it points at is the
write-path re-run at `.loop/evals/F14-manual-eval-results.md:75-91`, where a
`metadata` description forced Terraform to write the group and the hand-added
member was present before and after. The sentence now claims exactly that and
nothing more. Dropping `(0 added, 2 changed)` removes the only part a reader
could not check: the second change was the unrelated operator entity, and the
count does not reproduce now that the drift is repaired. The distinction between
a real write and a skipped diff is load-bearing here, so keeping the contrast is
right; it is the trailing negation that had to go, and it did.

## 3. Scope

`git diff a33da432 c20ec46e` is one file, `docs/cluster-roles.md`, 2 insertions
and 2 deletions, and they are that sentence. Nothing else inside the fingerprint
moved.

The eval rewrite is invisible to the fingerprint by design, and I checked the
mechanism rather than taking it on trust: `tree_fingerprint()` strips `.loop`
from the throwaway index and re-binds only `.loop/config.json`
(`loop_harness/stamp.py:124-137`), so `.loop/evals/` and `.loop/verdicts/` cannot
move the hash. `.loop/config.json` is unchanged, so the verification contract is
the one both reviews ran under.

## 4. Fingerprint, gate, drift

- **Fingerprint.** Recomputed by hand with the `tree_fingerprint()` procedure
  (throwaway `GIT_INDEX_FILE`, `git add -A .`, `git rm -r --cached .loop`,
  re-add `.loop/config.json`, `write-tree`) =
  `c20ec46e3b3365a5f7154659f8d0c4ea34326300`. Matches the briefing and
  `.loop/stamp.json`. `fingerprint_ignore` is unset, so the ignore list is empty
  and nothing is exempt.
- **Gate.** `just pre_commit` re-run here: 8 passed, 2 skipped (no Python
  files), exit 0. Terraform fmt and validate both green.
- **Drift.** `terraform plan -lock=false -var-file=./vars/prod.tfvars` in
  `deployments/infrastructure`: `No changes. Your infrastructure matches the
  configuration.` `-detailed-exitcode` returns 0, which is the machine-checkable
  form of the same answer. Only the two pre-existing `vault_kv_secret_v2`
  deprecation warnings, untouched by this ticket.
- **Working tree.** Eight paths, all tracked and staged, no untracked strays.
  Line width is under 80 everywhere in both files except the four
  `docs/cluster-roles.md` table rows, which are pre-existing and unchanged.

## Findings

**INFO — tense slip in the repaired sentence.** `docs/cluster-roles.md:50-51`
pairs a present-tense verb with a past-tense one: "an apply that really *writes*
the group, rather than one that merely *skipped* the diff." Both clauses describe
the same kind of thing, so both should be present tense. Cosmetic, does not
change the meaning, and not worth moving the tree for. Fold it in if this file is
ever touched again.

No MEDIUM or HIGH findings. Nothing blocks the commit.

## Verdict

**pass** at `c20ec46e3b3365a5f7154659f8d0c4ea34326300`. Bind and commit.
