eval: reconcile-registers-orphan-plans

Definition of Done: reconcile makes the ledger a re-derivable index of the
plans on disk — orphan plans auto-register (repo-contained, idempotent,
always recoverable later), a non-terminal entry whose plan vanished is
flagged but never deleted, and `loopctl drop` retires a ticket reversibly
without reconcile ever resurrecting it.

| Behavior | Input | Expected | Scorer | Threshold |
|----------|-------|----------|--------|-----------|
| A forward orphan is auto-registered | A plan file `<plans_dir>/foo.md` with an empty ledger; run reconcile | Slug `foo` is registered at stage `ready` | Deterministic (`test_*`) | 100% |
| An existing entry is never resurrected or duplicated (guardrail) | An entry already present (test both a non-terminal stage and a `blocked` entry) with its plan file present; run reconcile | Its stage and the entry set are unchanged; no duplicate row | Deterministic (`test_*`) | 100% |
| A non-terminal reverse orphan is flagged, not deleted | An entry at `ready`/`implementing` whose plan file is missing; run reconcile | A warning is emitted and the entry is NOT removed or modified | Deterministic (`test_*`) | 100% |
| A terminal reverse orphan is silent (noise guardrail) | A `done` entry whose plan file is missing; run reconcile | No warning is emitted | Deterministic (`test_*`) | 100% |
| Cross-repo containment: plans outside the repo are ignored (guardrail) | `plans_dir` resolves outside the repo tree (e.g. the shared-home `~/.claude/plans`) and holds a plan file; run reconcile | That plan is NOT auto-registered into this ledger | Deterministic (`test_*`) | 100% |
| A failed/missed registration is always recoverable later | A plan whose registration did not persist; run reconcile again, and separately `loopctl register <slug>` | The orphan is registered on the next reconcile; `register` on an already-present slug is a clean no-op that never duplicates | Deterministic (`test_*`) | 100% |
| An already-committed orphan self-heals in one pass | An orphan plan whose slug-anchored commit already exists; run one reconcile | The entry lands at `done` (plans pass registers, git pass upgrades) in the single pass | Deterministic (`test_*`) | 100% |
| Drop survives reconcile — anti-resurrection (guardrail, load-bearing) | Register a slug, `loopctl drop` it, keep its plan file on disk; run reconcile | The entry is still present, still dropped, stage unchanged, and NOT re-registered or re-activated | Deterministic (`test_*`) | 100% |
| A dropped entry with a missing plan is silent (guardrail) | A dropped entry whose plan file is absent; run reconcile | No reverse-orphan warning is emitted | Deterministic (`test_*`) | 100% |
| Drop is reversible (un-drop round-trip) | Drop a ticket, then re-register (un-drop) it | The ticket is active again and no longer dropped | Deterministic (`test_*`) | 100% |
| SessionStart enforces the invariant every session | A repo with an orphan plan present at session start | The SessionStart reconcile registers it (the ledger gains the row) and prints it; fail-open is preserved | Deterministic (`test_*`) | 100% |
| Reconcile never deletes a ledger entry, in any state (invariant guardrail) | Reconcile run over entries in every state (done, blocked, dropped, reverse-orphan) | No entry is ever removed from the ledger | Deterministic (`test_*`) | 100% |
