---
epic = "audit"
depends_on = []
priority = 52
summary = "Re-audit the thirteen plans that never had a plan-level review, for one failure pattern: premises falsified by work that shipped after authoring, while the path:line anchors still resolve so the existing gates see nothing wrong. Output is a triage verdict per plan plus mechanical corrections."
tags = ["audit", "planning", "process"]
---

# A1 — Sweep every unreviewed plan for premises that went stale

## Title
Audit the thirteen plans that have never had a plan-level adversarial review,
for one specific failure pattern with a 100% hit rate on the four already
reviewed: premises invalidated by work that shipped after authoring, while the
`path:line` anchors still resolve so nothing looks wrong.

## Size / Effort
**Medium.** Thirteen plans, but a narrow lens: this is a pattern sweep, not
thirteen deep reviews. Output is a triage verdict per plan plus mechanical
corrections. The judgment cost is deciding which plans need a deep review
afterward.

## Triggered by
On 2026-07-25 the four unreviewed *actionable* tickets — F1, S2, S3, C1 — were
each adversarially reviewed. **All four were rejected**, three with defects
that would have failed on first contact:

- F1 described the shared `nomad-workloads` Vault policy as job-scoped by
  citing 11 lines of a 24-line file, and would have shipped that false claim
  in the one document downstream tickets are meant to trust.
- S2's rotation test could not fire (only `default_ttl` set, so Nomad renews
  to `max_ttl`), and its "load-bearing wrinkle" was superseded by F3.
- C1 specified an operator-cancelled deliverable, with an eval marker
  unsatisfiable by the ticket actually wanted.
- S3 restated conclusions already load-bearing in four other tickets, on a
  premise F3 falsified three hours after it was authored.

Common cause: every plan was written 2026-07-24, before F3 shipped that
evening. **The anchors still resolve — it is the surrounding claims that went
false**, which is why the existing gates cannot see it. Thirteen plans have
not been checked for the same pattern.

## Context (today's state)
- **Reviewed and corrected already (do NOT re-audit):** F1, S2, C1 (all
  rewritten 2026-07-25), T1, T2, T3 (authored 2026-07-25 post-review), S3 and
  F4 (dropped).
- **In scope, thirteen plans:** `F2`, `F7`, `F8`, `L1`, `L2`, `M1`, `M2`,
  `R1`, `R2`, `R3`, `R4`, `S1`, `F9`.
  F9 is included because it is the only actionable unreviewed ticket, though
  it was authored 2026-07-25 from a live-verified finding and is expected to
  come back clean.
- **Known-latent defects to confirm**, both surfaced in passing by the F1 and
  S3 reviews:
  - **M1's stated dependency was never deliverable.** M1 requires MinIO's
    `identity_openid` `config_url`, which needs an OIDC discovery document.
    `curl http://192.168.2.30:4646/.well-known/openid-configuration` returns
    `OIDC Discovery endpoint disabled` and `oidc_issuer` is unset cluster-wide.
    F1 delivers JWKS only. F1's new Q7 records the fork.
  - **R1 and R2 inlined S3's conclusions** as settled fact, with issue
    numbers, before S3 ever ran. Those conclusions may be right; nothing
    verified them.
- **The epic brief itself contains at least one false premise:** it claims
  memex already verifies Nomad WI JWTs against JWKS, but
  `deployments/applications/services/memex.hcl` carries only static
  `MEMEX_SERVER__AUTH__KEYS`, with no JWKS or OIDC issuer. Anything downstream
  resting on that claim inherits the error.
- **RESCOPED 2026-07-30 (operator).** This bullet previously read: "Reviews
  cost roughly 90-150k tokens and 7-16 minutes each. Thirteen deep reviews is
  not the shape; one pattern sweep is." The operator has directed that all
  thirteen plans be reviewed by the loop's own planning-review agent
  (`loop-plan-reviewer`, `.loop/config.json` pass id `plan-validator`) rather
  than by a hand-rolled pattern sweep. The cost is accepted. The mechanism
  changes; the deliverable and every guardrail below do not.

## Non-goals / out of scope
- **Renaming `.localstack` hostnames. T3 owns that sweep** and already
  enumerates the affected plans and evals. Note stale hostnames if seen, but
  do not fix them here — duplicating T3's work invites merge conflicts in the
  same files.
- **RESCOPED 2026-07-30 (operator).** This non-goal previously read: "Deep
  adversarial review of any single plan. A1 decides WHICH plans need that; it
  does not perform it." A1 now DOES perform a premise-falsification review of
  every in-scope plan, via `loop-plan-reviewer`. What A1 still does not do is
  ACT on the structural findings: applying a reviewer's required fixes to a
  plan remains out of scope (requirement 4 stands unchanged), and each such
  plan is handed on with its fix list.
- Re-auditing F1, S2, C1, T1, T2, T3, or anything dropped.
- Implementing or fixing anything outside `.loop/plans/` and `.loop/evals/`.
- Changing any ticket's `depends_on` **except** where the sweep proves an edge
  is wrong (a dependency that cannot deliver what the dependent needs, per the
  M1 case). Record the change and why.
- Rewriting a plan wholesale. Where a defect is structural rather than
  mechanical, flag it for a deep review instead — the C1 rewrite took a full
  pass on its own.

## Requirements & restrictions
1. Every in-scope plan gets an explicit verdict: **clean**, **mechanical
   fixes applied**, or **needs deep review** with the reason.
2. Check each plan for the five defect classes observed:
   - **Stale premise.** A claim about current state that was true at
     authoring and is not now. F3 (2026-07-24 evening) and the T1/T2/T3
     re-plan (2026-07-25) are the two events that moved the world.
     **CORRECTED 2026-07-30: there are more than two.** The bifrost work is
     the third, and it is itself three commits into
     `deployments/applications/{providers,secrets,services}.tf`: `ac3267b`
     (B1, 2026-07-29, 76 insertions), `e17d8d0` (2026-07-30, 67) and
     `64f4adb` (2026-07-30, 9). The sixth Postgres role `bifrost` came from
     **`e17d8d0`**, not `ac3267b`, which never touches `database.tf`. Seven
     in-scope plans cite those files: F8 (13 citations), R3 (9), R1 (5),
     M2 (3), M1 (2), R4 (2), F7 (1). This is the class where the anchor still
     resolves but to different content, so it is invisible to a resolve-only
     check.
   - **Inlined conclusion.** A fact asserted as settled that another,
     unrun ticket was supposed to establish.
   - **Broken dependency edge.** A `depends_on` naming a ticket that cannot
     deliver what this one needs. The M1 case is the template.
   - **Shape-check eval.** A marker whose rows are `ls`, `grep`, or file
     existence and would pass against wrong content. `require_eval` protects
     the loop only if the marker asserts truth.
   - **Unresolvable anchor.** A `path:line` that no longer resolves, or
     resolves to different content than described.
   **ADDED 2026-07-30 (operator rescope).** The check is performed by
   dispatching `loop-plan-reviewer` once per in-scope plan, briefed per its
   own Inputs contract (repo root, plan path and slug, pass id
   `plan-validator`, the plan's sha256 fingerprint, verdict path
   `.loop/verdicts/<slug>.plan-validator.md`) plus the five defect classes
   above as required attack surface. The reviewer's `SOUND` / `PARTIALLY
   SOUND` / `BROKEN` premise verdict is the evidence behind this ticket's
   clean / fixed / needs-deep-review triage; it does not replace it, because
   the reviewer judges plan readiness while A1 judges what to do next.
3. **Verify against the live cluster, not the repo alone.** Three of the four
   findings that mattered (the policy scope, the disabled OIDC endpoint, port
   53 on firebat) were only visible by querying the running system.
   `VAULT_ADDR`, `NOMAD_ADDR`, `CONSUL_HTTP_ADDR` and their tokens are set.
4. **Fix only the mechanical.** A stale anchor, a dead `depends_on`, a
   one-line premise correction. Anything requiring judgment about what the
   ticket should now do goes on the deep-review list.
5. Where a correction is applied, mark it inline with the date and what it
   replaced — the C1 failure was an operator rescope appended rather than
   applied, leaving the contradiction in place for a reader to trip over.
6. Do NOT silently resolve an open question. A fork the sweep uncovers is
   recorded with a recommendation for the operator, per the loop's
   `unresolved-design-fork` discipline.
7. `.claude/rules/adversarial-reviews.md`: adversarial review before done.

## Code surface
Only planning artifacts. No source, no infrastructure.
- `.loop/plans/{F2,F7,F8,L1,L2,M1,M2,R1,R2,R3,R4,S1,F9}-*.md` — inline
  corrections where mechanical.
- `.loop/evals/*.md` for the same slugs — corrections where a row is a shape
  check that would pass against wrong content.
- `.loop/verdicts/{F2,F7,F8,L1,L2,M1,M2,R1,R2,R3,R4,S1,F9}-*.plan-validator.md`
  **(new, ADDED 2026-07-30 with the operator rescope)** — one
  `loop-plan-reviewer` verdict per in-scope plan, each binding the plan sha256
  it reviewed. These are the audit's primary evidence; the triage doc
  summarizes them and must not contradict them.
- `docs/notes/audit/plan-premise-sweep-2026-07.md` **(new)** — the triage
  table: one row per plan, its verdict, the defects found, what was fixed
  inline, and what is deferred to a deep review. This is the deliverable a
  human reads.

## Tests & validation gates
No code changes, so the usual gates prove little. `.loop/` and `.claude/` are
excluded from pre-commit (`.pre-commit-config.yaml:1`), meaning **plan and
eval edits are not linted at all** — the gate cannot check this ticket's main
output. The eval marker is the real acceptance layer here.

### Repo gate
- **Command:** `just pre_commit` -> all Passed (covers only the new `docs/`
  page, via `end-of-file-fixer`).
- **Worktree prerequisite:** `just worktree_setup <path>` (`justfile:30-32`).
- **Command:** `loopctl reconcile` -> `ledger consistent with git`, proving no
  front-matter edit broke the ledger projection.
- **Command:** `loopctl eval <slug>` for every marker touched -> `valid`.

### Evals
The authoritative set is `.loop/evals/A1-audit-plan-premise-sweep.md`.

## Risk assessment
- **Blast radius: the plans, not the cluster.** Nothing here is applied. The
  realistic harm is a bad correction misleading a later implementer — which is
  the same harm the ticket exists to prevent, so requirement 5's inline
  marking matters.
- **Overlap with T3.** Both touch the same plan files. T3 owns hostnames; A1
  owns premises. If both run before either commits, they conflict. Mitigate by
  keeping A1 off hostname edits entirely (non-goal 1).
- **Scope creep is the likeliest failure.** Thirteen plans with defects is an
  invitation to rewrite them. Requirement 4 and the deep-review list are the
  guard.
- **A clean verdict may be wrong.** A sweep is shallower than a deep review;
  "clean" here means "no instance of the five known patterns", not "correct".
  The doc must say so, or a later reader over-trusts it.
- **Reversibility: total.** Plan-file edits, revertable in one commit.

## Subtickets (ordered)
1. Establish the ground truth the sweep checks against: re-verify the live
   claims (policy scopes, OIDC discovery, JWT roles, what each job actually
   uses) once, so thirteen plans are checked against one verified picture
   rather than thirteen re-derivations.
2. Review the six with the most dependents first — F2, M1, R3, S1, F7, F8 —
   so a defect that propagates is found early. **AMENDED 2026-07-30: "Sweep"
   here now means dispatching `loop-plan-reviewer` per requirement 2, in one
   concurrent batch, not a hand-rolled read.**
3. Review the remaining seven: L1, L2, M2, R1, R2, R4, F9, same mechanism.
4. Apply mechanical corrections inline, marked per requirement 5.
5. Write `docs/notes/audit/plan-premise-sweep-2026-07.md` with the triage
   table and the deep-review list.
6. `loopctl reconcile` and `loopctl eval` on everything touched.
7. Adversarial review.

## Operator decisions of 2026-07-30 (provenance)

Recorded here because the repo otherwise holds no evidence of them, and A1's
adversarial review correctly refused to take the implementer's word for it.
Three decisions were put to the operator as explicit prompts and answered
before any of them was acted on:

1. **Mechanism.** "Review by `loop-plan-reviewer`, apply mechanical fixes,
   triage the rest" was chosen over "review only" and over "review and harden
   every plan to a pass". This overrides the non-goal above and leaves
   requirement 4 intact.
2. **Rescope recording.** "Amend both the plan and the eval, marked inline"
   was chosen over amending only the plan and over doing the work silently.
3. **Eval sign-off.** The marker was unsigned and blocked pickup. The operator
   was shown the amended thirteen-row marker and approved it, and only then
   was `signed-off-by: jasperginn 2026-07-30` written. It was not
   self-authored. The line is agent-settable either way, so it buys
   auditability and an explicit gate, never proof a human approved: that is
   exactly why this section exists.

## Open questions
- **Q1 → RESOLVED (operator, 2026-07-25): A1 gates every unreviewed ticket.**
  All thirteen in-scope plans carry `A1-audit-plan-premise-sweep` in their
  `depends_on`. The already-reviewed tickets (T1, T2, T3, F1, S2, C1) are
  deliberately NOT gated, so the ready TLS chain keeps moving.
  A weaker proposal — rely on priority ordering — was considered and rejected:
  priority is a soft preference that never gates pickup, and the argument that
  the dependency graph "already blocks" these tickets only holds at this
  instant. The graph unblocks over time. The moment T3 completes, F2 becomes
  actionable, and without a hard edge nothing stops it being implemented on an
  unaudited premise. That is exactly the failure this ticket exists to prevent.
  The edges stay in place after A1 closes: a satisfied dependency is harmless
  and records that the ticket was gated on the audit.
- **Q2 — What happens to a plan the sweep finds beyond repair?** S3 was
  dropped rather than fixed. *Recommendation:* A1 may recommend a drop but
  must not perform one. Dropping a ticket is an operator decision, and the
  sweep's shallower lens is not grounds for it.
- **Q3 — Does the epic brief itself get corrected?** The memex/JWKS claim is
  false and lives above the ticket layer. *Recommendation:* record it in the
  audit doc and surface it; correcting the brief is out of scope, since
  nothing in `.loop/` owns it.
