eval: A1-audit-plan-premise-sweep

**Definition of Done:** Each of the thirteen in-scope plans (F2, F7, F8, L1,
L2, M1, M2, R1, R2, R3, R4, S1, F9) carries an explicit verdict — clean,
mechanical fixes applied, or needs deep review — recorded in
`docs/notes/audit/plan-premise-sweep-2026-07.md`, checked against the LIVE
cluster rather than the repo alone, with mechanical corrections applied inline
and marked, and nothing rewritten wholesale or silently resolved.

**The sweep's own trap:** a verdict of "clean" from a shallow sweep is not a
statement of correctness, only that none of the five known patterns appeared.
Row 8 exists so the audit doc cannot overclaim, because a later reader will
otherwise treat "clean" as "reviewed".

**RESCOPED 2026-07-30 (operator).** The mechanism changed: every in-scope plan
is now reviewed by the loop's `loop-plan-reviewer` agent (pass id
`plan-validator`) instead of a hand-rolled pattern sweep. Row 12 is added to
bind that evidence. Rows 1-11 are unchanged and still hold: the deliverable,
the guardrails, and the "clean is not correct" trap survive the mechanism
change. Note the trap now cuts the other way too — a plan the reviewer calls
`SOUND` is a genuine premise review, so its row must not be softened to the
shallow-sweep caveat, and a plan the reviewer calls `BROKEN` is NOT thereby
fixed by this ticket (requirement 4 still forbids acting on structural
findings).

| Behavior | Input | Expected | Scorer | Threshold |
| --- | --- | --- | --- | --- |
| Every in-scope plan gets a verdict, and none is silently skipped | `grep -c '^|' docs/notes/audit/plan-premise-sweep-2026-07.md` and read the table | Exactly thirteen verdict rows, one per in-scope slug (F2, F7, F8, L1, L2, M1, M2, R1, R2, R3, R4, S1, F9), each reading `clean`, `fixed`, or `needs deep review`. No slug absent, no slug added | deterministic check (thirteen rows, one per named slug) | 100% |
| **The known-latent M1 defect is confirmed or refuted, not skipped** | `curl -s http://192.168.2.30:4646/.well-known/openid-configuration`; then read M1's requirements and the audit row for M1 | The endpoint returns `OIDC Discovery endpoint disabled`. M1's row states plainly whether M1 requires a `config_url` (an OIDC discovery document) that F1 does not deliver, and either corrects M1's dependency edge or records the fork for the operator. This is the one defect already known to exist, so a sweep that misses it has not worked | deterministic check (M1's row addresses the discovery-endpoint gap) | 100% |
| **The audit is grounded in the running system, not just the repo** | Read the audit doc's ground-truth section | It records live readback for at least: the `nomad-workloads` policy scope, `vault list auth/jwt-nomad/role`, Nomad's OIDC discovery state, and what each live job actually uses. Three of the four findings that mattered in the 2026-07-25 reviews were invisible from the repo alone | model + rubric (adversarial review agent) | 4/5 |
| **Guardrail: no plan is rewritten wholesale** | `git diff --stat .loop/plans/` | No single in-scope plan shows a diff approaching a rewrite. Mechanical corrections only; a plan needing more goes on the deep-review list. C1's rewrite took a full pass on its own, and thirteen of those is not this ticket | deterministic check (no in-scope plan rewritten end to end) | 100% |
| **Guardrail: every correction is marked, never appended as a contradiction** | Inspect each applied correction in `.loop/plans/` | Each carries a date and what it replaced, inline at the point of the claim. C1 failed precisely because an operator rescope was appended rather than applied, leaving 470 lines contradicting the last 29 with nothing marking which was authoritative | deterministic check (every correction carries a date and its superseded claim) | 100% |
| **Guardrail: the sweep does not touch what T3 owns** | `git diff .loop/plans .loop/evals` filtered for hostname changes | No `.localstack` to `.lab.orangecluster.nl` renames. T3 owns that sweep over the same files, and doing it here causes a conflict in exactly the files both tickets edit | deterministic check (no hostname renames in the diff) | 100% |
| **Guardrail: no open question is silently resolved** | Review every fork the sweep surfaced | Each is recorded with a recommendation for the operator, none decided in the plan text. Per the loop's `unresolved-design-fork` discipline, picking silently is the failure the block exists to prevent | deterministic check (each surfaced fork appears as an open question, not a resolution) | 100% |
| **The audit doc states its own limits** | Read the doc's framing | It says explicitly that "clean" means "no instance of the five known patterns was found", NOT "this plan is correct", and names which plans still warrant a deep review. Without this a later reader treats a shallow pass as a thorough one — and A1 becomes the same kind of false assurance it was created to remove | model + rubric (adversarial review agent) | 4/5 |
| The ledger survives the front-matter edits | `loopctl reconcile`; then `loopctl graph` | `ledger consistent with git`, and every `depends_on` in every edited plan resolves to a real slug. A typo in a dependency reads as an unsatisfiable edge and silently strands a ticket forever | deterministic check (`loopctl reconcile` clean, all edges resolve) | 100% |
| Every eval marker the sweep touches is still schema-valid | `loopctl eval <slug>` for each marker modified | `valid` for every one. A marker corrected into an invalid shape blocks its ticket at pickup under `require_eval` | deterministic check (`loopctl eval` valid for all touched markers) | 100% |
| Shape-check evals are identified wherever they exist | Read the audit doc's eval findings | Any in-scope marker whose rows are `ls`, `grep`, or file-existence checks that would pass against wrong content is named. This is the systemic defect: S3's marker was entirely shape checks, and F1's row 6 was a green check asserting something false | model + rubric (adversarial review agent) | 4/5 |
| **ADDED 2026-07-30: every triage verdict is backed by a real reviewer verdict bound to the plan it reviewed** | `ls .loop/verdicts/*.plan-validator.md`; for each, compare its `plan:` fingerprint (or the fingerprint named in a `fail` verdict's body) against `sha256sum .loop/plans/<slug>.md` | Thirteen verdict files exist, one per in-scope slug, each written by `loop-plan-reviewer` and each bound to the sha256 of the plan as reviewed. A triage row in the audit doc with no matching verdict file is an unevidenced claim, and a verdict bound to a stale hash reviewed a plan that no longer exists | deterministic check (thirteen verdict files, fingerprints match the reviewed plans) | 100% |
| **ADDED 2026-07-30: the audit doc does not overstate or understate the reviewer** | For each in-scope slug, read its `plan-validator` verdict, then its row in the audit doc | Each row's triage matches its verdict's premise finding: no plan the reviewer called `BROKEN` is recorded as `clean`, and no plan it called `SOUND` is recorded as `needs deep review` without a stated reason beyond the reviewer's own findings. Summarizing thirteen reviews into one table is exactly where a finding gets quietly lost | model + rubric (adversarial review agent) | 5/5 |

signed-off-by: jasperginn 2026-07-30
