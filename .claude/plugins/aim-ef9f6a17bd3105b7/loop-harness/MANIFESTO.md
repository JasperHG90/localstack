# Manifesto: loop-harness

The model proposes, the harness verifies, git is ground truth. Every
lifecycle claim ("gates passed", "review done", "ticket closed") must be
backed by an artifact bound to the exact tree it certifies, so an agent
cannot talk its way past a stage it has not earned.

This document states what loop-harness is, how it is built, and the rules
it must never break. Each **invariant** cites the code that enforces it;
each **value** is taste we hold but do not mechanically check. The split is
the point: an "invariant" you cannot point at is just a wish.

## 1. Vision

Autonomous coding loops fail in a predictable way: the model reports
success it did not achieve. It says the tests pass, the review is clean, the
scope held, and the operator has no cheap way to tell truth from a
confident summary. loop-harness removes the model's ability to self-certify.
Progress is gated on evidence the operator can audit, not on the model's
account of its own work.

Three commitments follow from that:

- **Evidence over claims.** A stage transition happens only when a
  tree-bound artifact proves its entry criteria. "Gates passed" is a stamp
  binding exit codes to a tree fingerprint, not a sentence in a transcript.
- **No silent judgment calls.** A design question the ticket does not answer
  is a `blocked` state with a coded reason, handed to the operator. The loop
  never guesses its way past an unresolved fork.
- **Fail safe, never fail open.** A harness bug fails OPEN so it cannot wedge
  a session, but a policy ambiguity (a broken config, an absent verdict)
  fails SAFE toward more review, never toward none.

The harness is a plugin for Claude Code and is deliberately dependency-free,
so any repo can adopt it without an install step and any gate is just a
shell command.

## 2. Architecture

The harness is a stdlib-only Python package (`src/loop_harness/`) fronted by
one CLI (`loopctl`) and wired into Claude Code through event hooks
(`hooks/hooks.json`). Skills and agents (`skills/`, `agents/`) are the
behavioral layer the model runs; the Python core is the layer that verifies
what the model did.

**The enforced spine. A ticket's path through the lifecycle:**

```
ready → implementing → gates → self-review → adversarial-review → commit → done
  ↑           │                                      │
  │           └──────────── blocked ────────────────┘   (reachable anywhere,
  └───────────────── (returns to ready) ─────────────    returns only to ready)

findings loop:  adversarial-review → gates   (capped at max_review_cycles)
```

**Module map:**

| Module | Responsibility |
|--------|----------------|
| `cli.py` | The single blessed entry point; dispatches every `loopctl` command. |
| `lifecycle.py` | The state machine: entry criteria for every transition. |
| `ctl.py` | The only supported ledger write path (register / advance / block / done). |
| `ledger.py` | Durable per-ticket state (`Stage`, `TicketEntry`, atomic persistence). |
| `stamp.py` | Evidence stamps: run the gates, bind exit codes to a tree fingerprint. |
| `hooks.py` | The Claude Code surface: commit gate, state guard, session/stop checks. |
| `githook.py` | The optional git-level `pre-commit` backstop: a second enforcement of the commit gate git itself runs, reusing the one policy. |
| `config.py` | Parse and validate `.loop/config.json` (gates, review passes, actions). |
| `reconcile.py` | Correct the ledger from the plans on disk and from git history; register orphan plans, and let git win every commit disagreement. |
| `reflection.py` | Per-ticket judgment reflections and the `distill` aggregation that derives their mechanical numbers. |
| `history.py` | Append-only per-slug gate-failure log the repo keeps so `distill` derives `gates_red` from evidence. |
| `evals.py` | The pre-code Definition-of-Done marker and its content-blind schema. |
| `halt.py` | The kill switch, operator notifications, and the handoff log. |

**Behavioral layer:** `init-loop` bootstraps the harness into a fresh repo;
`create-ticket` and `ticket-planner` author a ticket against one contract;
`implement-ticket` drives one ticket through the lifecycle; `create-eval`
co-authors the Definition of Done before code. The
review passes (`loop-reviewer`, `loop-architect`, `loop-doc-reviewer`) each
write their own tree-bound verdict; `loop-doc-writer` is an advisory action.

**State on disk (`.loop/`):** `config.json` (consumer-owned),
`ledger.json` and `stamp.json` (harness-written only), plus per-slug
`verdicts/`, `reflections/`, `evals/`, and `history/` files, `HALT`, and
`handoff.log`.
All of `.loop/` is excluded from the tree fingerprint EXCEPT `config.json`:
loop bookkeeping never invalidates a green stamp, but the verification
contract (`config.json`, defining the gates and the ignore-list) is bound
into the certified tree, so weakening it stales the stamp.

## 3. Invariants

Rules the harness must never break. Each names the code that enforces it.

### I1. Stages advance one step at a time, forward only.

A transition is legal only to the next stage in `_ORDER`, plus two named
exceptions: the capped findings loop (`adversarial-review → gates`) and
`blocked` (reachable anywhere, returning only to `ready`). No stage may be
skipped.
**Enforcer:** `lifecycle.py`: `if _ORDER.index(target) != _ORDER.index(current) + 1:`

### I2. A commit needs a green stamp AND every enabled pass's tree-bound verdict.

Entering `commit` requires a green stamp and, for every enabled review pass,
a passing verdict whose `tree:` fingerprint equals the exact tree being
committed. An empty pass set (review deliberately disabled) authorizes on
the stamp alone; anything less than a full match blocks.
**Enforcer:** `lifecycle.py`: `f"commit entry needs review pass '{pass_id}' verdict "`

### I3. "Gates passed" is a stamp bound to one exact tree.

The tree fingerprint is defined once (`git write-tree` over a throwaway
index). Every reader calls that one function; two definitions could pass a
gate in one place and block in another.
**Enforcer:** `stamp.py`: `def tree_fingerprint(repo: Path, ignore: tuple[str, ...] = ()) -> str:`

### I4. A stamp goes stale the moment the tree changes.

If the current tree differs from the stamped tree, the stamp is STALE and
authorizes nothing. Any edit after the gates ran forces a re-stamp.
**Enforcer:** `stamp.py`: `if tree != tree_fingerprint(repo):`

### I5. An empty gate list never stamps green.

An unconfigured repo fails loudly rather than certifying an untested tree.
No gates configured is a raised error, not a pass.
**Enforcer:** `stamp.py`: `if not config.gates:`

### I6. Loop bookkeeping never invalidates a code stamp; the contract does.

`.loop/` is stripped from the throwaway index before `write-tree`, so
writing the stamp, updating the ledger, or engaging HALT cannot stale a
green stamp. One deliberate exception: `config.json` is re-bound after the
strip, because the gates and ignore-list it defines are the contract the
stamp certifies against, not bookkeeping. Weakening the contract therefore
stales the stamp, which strengthens evidence-over-claims: the definition of
green cannot change unnoticed.
**Enforcer:** `stamp.py`: `git("rm", "-r", "--cached", "--ignore-unmatch", "-q", ".loop")` strips, then `git("add", "-f", "--", CONFIG_FILE.as_posix())` re-binds the contract.

### I7. The commit gate refuses commits without earned evidence.

A commit is allowed only when the stamp is green and every mid-flight ticket
is at a committable stage with its verdicts bound to the current tree. HALT is
the sole bypass. Two enforcement points share the one `decide_commit_gate`
policy so they cannot drift: the `git commit` PreToolUse hook (fast, at the
Bash-tool layer) and an optional git-level `pre-commit` backstop that git
itself runs, closing the commits a string matcher cannot see (a subprocess,
`eval`, or a human at the terminal).
**Enforcer:** `hooks.py`: `def decide_commit_gate(` (reused by `githook.py`: `def pre_commit(`)

### I8. The commit gate fails safe on a broken config.

A malformed config yields the mandatory adversarial pass, never an empty
set. A config error can only tighten review, never silently drop it.
**Enforcer:** `hooks.py`: `def enabled_passes_failsafe(repo: Path) -> tuple[ReviewPass, ...]:`

### I9. Disabling review is loud and deliberate.

If `require_review` is true and no pass is enabled, config parsing raises.
The only way to a stamp-only commit is to set `require_review: false`
explicitly.
**Enforcer:** `config.py`: `if require_review and not any(p.enabled for p in review_passes):`

### I10. Loop state files are harness-written only.

Direct Edit/Write to `.loop/ledger.json` or `.loop/stamp.json` is blocked;
these change only through `loopctl`. It raises the activation energy for
bypassing stage discipline, and reconcile re-derives from git regardless.
**Enforcer:** `hooks.py`: `def decide_state_guard(file_path: str) -> GateDecision:`

### I11. Git is ground truth; the ledger is corrected from it, never the reverse.

Reconcile downgrades a ledger sitting at `commit` or `done` with no commit
carrying the slug, and upgrades a slug that a commit carries but the ledger
has not closed. The commit history wins every disagreement. The plans pass
(I17) runs first, so an orphan plan whose work is already committed is
registered and then upgraded to `done` in the one pass.
**Enforcer:** `reconcile.py`: `def reconcile(repo: Path, ledger: Ledger) -> list[Correction]:`

### I12. The ledger is written atomically.

Persistence writes a temp file and renames it into place, so a crash
mid-save never leaves a half-written ledger.
**Enforcer:** `ledger.py`: `os.replace(tmp_name, path)`

### I13. A ticket cannot close without a schema-valid reflection.

`loopctl finish` (via `ctl.done`) refuses to close a ticket unless a
slug-anchored commit exists and `.loop/reflections/<slug>.md` satisfies the
schema. Existence and shape are enforced; prose is never graded. The schema
asks only for judgment (friction plus prose); the mechanical numbers
(`cycles`, `gates_red`) are derived at distill time from the ledger and the
gate-failure history, never self-reported.
**Enforcer:** `ctl.py`: `reflection = verify_reflection(repo, slug)`

### I14. When required, implementing cannot begin without an eval marker.

With `require_eval: true`, entering `implementing` requires a schema-valid
eval marker: the Definition of Done is authored before code, not after.
**Enforcer:** `lifecycle.py`: `if require_eval and not eval_marker_present:`

### I15. The eval marker is checked for shape, never for substance.

The schema is a slug-bound `eval: <slug>` header plus at least one scenario
row. A single gibberish row satisfies it. The harness gates on the discipline
of writing acceptance criteria first, and leaves their quality to the
operator.
**Enforcer:** `evals.py`: `def verify_eval(repo: Path, slug: str) -> EvalVerdict:`

### I16. The repo remembers gate failures.

A RED `loopctl stamp` appends one event (slug, timestamp, failing commands
with exit codes, tree fingerprint) to an append-only per-slug log at
`.loop/history/<slug>.jsonl`, so the count of red gate runs over a ticket's
life is evidence the repo holds rather than a number the agent recalls. The
append is best-effort: a broken history write degrades to a warning and never
turns a gate result into a crash.
**Enforcer:** `cli.py`: `_record_gate_failure(repo, results, config)`

### I17. A plan on disk maps to a ledger entry; drop retires, never deletes.

Reconcile registers any plan file under the repo-contained `plans_dir` whose
slug is absent from the ledger, so the ledger is a re-derivable index of the
plans, not a precious artifact a missed registration can silently lose;
registration keys on the plan's existence, so it is always recoverable on the
next run. A `dropped` entry is a reversible retirement that stays in the ledger
(so a surviving plan never resurrects it, and `register` restores it). Reconcile
never deletes an entry; an active entry (not `done`, `blocked`, or dropped)
whose plan vanished only warns.
**Enforcer:** `reconcile.py`: `def reconcile_plans(repo: Path, ledger: Ledger, config: LoopConfig) -> tuple[list[str], list[str]]:`

## 4. Values

Rules we hold by discipline, with no mechanical enforcer. Honestly labeled,
because calling them invariants would be a lie.

- **Dependency-free core.** `src/loop_harness/` is stdlib-only so consumers
  need no install step. Nothing in CI fails a new import; it is a line we
  hold by review, not by a gate.
- **Hooks fail open on internal error.** Every hook wraps its body and
  returns "allow" on an unexpected exception, so a harness bug never wedges
  commits or sessions. This is the deliberate counterpart to I8: bugs fail
  open, policy fails safe.
- **Surgical scope.** Every changed line should trace to the ticket's code
  surface. Enforced socially by self-review and the adversarial reviewer,
  not by a check that can read intent.
- **Simplicity first.** The minimum code that solves the problem; no
  speculative abstraction or configurability nobody asked for.
- **Tests and docstrings ship with the code.** Every code change carries a
  test; every Python object carries a numpy-style docstring. Repo gates
  press on this, but the standard itself is a value.
- **Advisory stages stay honest.** An `action_stage` writes no verdict and
  gates nothing, because the harness has no tree-bound artifact to prove it
  ran. Doc freshness is enforced by the `documentation` review pass, which
  writes a verdict, not by the writer action that only edits docs.
- **The operator owns decisions.** The loop surfaces forks and enforces
  evidence; design choices, disputed findings, and the HALT switch belong to
  the operator. Pair the loop with a decision record the operator owns.

## 5. Notable historical decisions

Kept for the *why*; §1–§4 are the current-state authority. The full record
lives in `DECISIONS.md`.

- **Reflection enforces at `finish`, not as a new stage** (decision R1). The
  rule is to enforce at an existing point rather than grow the state machine.
  This grain governs later extensions.
- **Review became N selectable passes without a new stage** (decision S1).
  The single reviewer generalized to a list of `review_passes`, each writing
  its own tree-bound verdict, all running inside the unchanged
  `adversarial-review` stage. The `Stage` enum and `_ORDER` stayed closed;
  only the commit criterion widened (N verdicts, not one).
- **Action stages are advisory by honesty** (decision S3). Recording that an
  unverifiable action "ran" would be exactly the self-certification the
  harness exists to prevent, so actions gate nothing and doc freshness is
  enforced by a review pass instead.
- **Custom stages reference project-bound artifacts by name** (decision S4).
  A custom pass or action names an agent or skill in the consumer's
  `.claude/` locations; the harness resolves no paths, and hooks stay the
  separate, event-driven surface.
