---
verdict: pass
tree: 917fa74d0e395554e063ca37319d47396dfef0ca
---

# Documentation review — F9-foundation-scope-nomad-workloads-policy (cycle 4, final)

**Nothing blocks.** Every documented surface this change touches is updated
in step. The cycle-3 required fix is applied and, checked claim by claim
against the files, it is accurate. Two minor findings below are non-blocking
and neither would lead a reader into a wrong action.

## The cycle-3 required fix: verified accurate in every particular

The appended note is `docs/notes/audit/plan-premise-sweep-2026-07.md:78-86`.
Each factual claim, checked against the tree:

| Claim | Check | Result |
| --- | --- | --- |
| "the committed template is 21 lines" | `wc -l` on the template | 21. Correct. |
| "with three `path` blocks" | `grep -c '^path'` | 3. Correct. |
| "grants 3, 4 and 5 are removed" | A1's numbering at `:68-71` is unscoped `secret/metadata/*` list, `bootstrap/data/*` rwu, `bootstrap/metadata/*` list; all three gone from the template | Correct. |
| "only the two job-scoped `secret/data` reads and the namespace-scoped `secret/metadata` list remain" | template `:1-3`, `:5-7`, `:9-11` | Correct, and complete: no fourth block. |
| "The LIVE policy still renders six blocks" | pre-change template had 6 `path` blocks (`git show HEAD:` + `grep -c`), and the loop does not apply | Correct. |
| "F9's runbook extends this line with the date the live cluster changes" | plan `:281-289`, step 4 | Correct, and step 4 matches: it says the note is already in the commit and tells the operator to extend it after step 2. |

**The two-audience framing is genuinely right, not a hedge.** The superseded
paragraph mixes claims of two kinds. Its line count and its enumeration of
five grants describe the repo file, and both are now false of the repo. Its
readback sentence, "`vault policy read nomad-workloads`, which renders six
`path` blocks" (`:75-76`), describes the cluster and stays true until an
operator applies. The note does not paper over the first kind: it names the
new line count and says which numbered grants went, so a reader who reads
both paragraphs holds the correct repo state and the correct cluster state
at once. "Stale about the repo, accurate about the cluster" is a fair
description of that split, not a phrase covering a gap.

The note is an append, not a rewrite. A1's dated snapshot at `:62-76` stands
untouched, so the audit record survives as a record.

## Other doc surfaces the diff touches: none stale

I swept every markdown file, README and SKILL.md in the tree for references
to this policy and its removed grants.

- `docs/gcs-backups.md:27` — describes the policy as scoping secret reads to
  `secret/data/<namespace>/<job_id>/*`. That grant survives; the sentence
  never mentioned the removed ones. Still true, correctly untouched.
- `docs/credential-rotation.md` — documents rotation of the two bootstrap
  credentials as host-level Ansible work (`:34-40`, "Why Ansible (Not Nomad
  Periodic Jobs)"). It never claimed a Nomad workload reads `bootstrap/*`,
  so removing that grant makes the repo more consistent with it, not less.
  Subticket 4's "update if affected" resolves to: not affected. Correct call.
- `deployments/infrastructure/acme.tf:36-40`,
  `services/haproxy.hcl:34-38`, `deployments/applications/secrets.tf:103,116,126`
  — in-code comments about the shared policy. Each describes only the
  job-scoped read, which survives. No drift.
- No README, architecture doc or SKILL.md describes the removed grants.

The template's own replacement comment
(`bootstrap/roles/nomad_server/templates/vault_nomad_workloads.hcl.j2:13-21`)
points at `.loop/plans/` while open and `.loop/archive/<slug>/plan.md` once
closed. Both paths resolve: `.loop/archive/F3-.../plan.md` and siblings exist.
No hallucinated path. Its reason for not restating the revoked rules (Vault
stores policy text verbatim, so a restatement would make a grep for a revoked
grant match) is sound and matches the runbook's `grep -ci 'bootstrap'`
assertion at plan `:260`.

## Slop scan on new prose

`docs/notes/audit/plan-premise-sweep-2026-07.md:78-86`: 0 em dashes, no
` -- ` substitution, no semicolon splice, no tier-1 or tier-5 slop terms, no
British spellings, all lines under 80 chars. Clean.

## Minor findings (non-blocking, no cycle left, recorded for the operator)

**m1 — the arithmetic fix landed in one artifact but not the other.**
`.loop/plans/F1-foundation-nomad-wi-jwt-trust.md:186` still reads "the
template drops from 24 lines to 20". It drops to 21, as the audit note
correctly states. My cycle-3 M3 was reported fixed; it was fixed at
`plan-premise-sweep-2026-07.md:81` and missed here.

Not blocking, for three reasons that all have to hold and do: `.loop/plans/`
is an internal planning artifact, not a documented user surface; the very
next clause of that sentence is "**Do not re-plan F1 from line numbers** —
Re-read the file and the live policy instead", so the number is decorative
and the instruction it supports is correct; and the ledger's F1 blocker
carries the accurate substance ("Re-plan against the 3-block policy"). An
F1 planner reading this is pointed at the file, not at the number. One-word
fix whenever F1 is next opened.

**m2 — cosmetic date and wrap.** The template comment is dated
`F9 (2026-07-30)` (the decision date in the plan) while the audit note is
dated `2026-07-31` (the merge date). Both are defensible; the pair reads as
an inconsistency at a glance. Separately,
`plan-premise-sweep-2026-07.md:80` wraps at 46 chars mid-paragraph, ragged
against its neighbors. Neither misleads anyone.

## Scope note

The live policy still renders six blocks because an operator applies this,
not the loop. That is the ticket's stated design (plan `:206`, `:291-293`),
it is what the audit note now says out loud, and it is not drift.
