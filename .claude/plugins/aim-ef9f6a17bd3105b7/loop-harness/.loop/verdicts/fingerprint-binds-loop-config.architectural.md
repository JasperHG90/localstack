# Architectural review: fingerprint-binds-loop-config

verdict: pass
tree: 80884e2e73346a07d18904a07e9a254c3ddcfc95

pass id: architectural
baseline: MANIFESTO.md
ticket: .loop/plans/fingerprint-binds-loop-config.md

## Scope reviewed

`git diff HEAD` (HEAD = 8ce8e87). Changed: `src/loop_harness/stamp.py`,
`tests/test_stamp.py`, `MANIFESTO.md`, `docs/onboarding.md`,
`docs/tutorials/custom-reviews-and-actions.md`, plus harness-written
`.loop/ledger.json` (excluded bookkeeping). Working tree verified against the
bound fingerprint via `loopctl verify` -> `ok`.

## Findings tied to baseline rules

### I3 — single definition of the fingerprint. UPHELD.
The enforcer citation was updated to
`def tree_fingerprint(repo: Path, ignore: tuple[str, ...] = ()) -> str:`,
which matches the sole definition at `stamp.py:61`. `grep` confirms exactly
one `def tree_fingerprint` and one `write-tree` call site
(`stamp.py:129`). All four callers route through it with no second
definition: `hooks.py:423`, `ctl.py:72`, `stamp.py:181`, `stamp.py:216`. The
pre-existing citation drift (old `def tree_fingerprint(repo: Path)`) is now
honest. No drift.

### I6 — loop bookkeeping never invalidates a code stamp; the contract does. UPHELD.
Both enforcer fragments resolve to real code and describe behavior
accurately:
- strip: `git("rm", "-r", "--cached", "--ignore-unmatch", "-q", ".loop")` at
  `stamp.py:117`.
- re-bind: `git("add", "-f", "--", CONFIG_FILE.as_posix())` at `stamp.py:128`.
The re-bind runs AFTER the `.loop` strip (`:117`) and AFTER the
`fingerprint_ignore` loop (`:118-121`), guarded by
`if (repo / CONFIG_FILE).exists():` (`:127`). Ordering is correct for R4: no
ignore pattern can subtract `config.json`. The `-f` flag correctly force-binds
config even when a consumer gitignores `.loop/`, and the existence guard keeps
a missing config non-fatal (R5 fail-safe, so a fatal `git` cannot be swallowed
by the hook fail-open at `hooks.py:425-427`). The new I6 prose and the §2
disk-state note (`MANIFESTO.md:82-85`) accurately state that `config.json` is
bound while the rest of `.loop/` is excluded, and correctly frame this as
strengthening evidence-over-claims. `CONFIG_FILE = Path(".loop") /
"config.json"` (`config.py:20`) is single-sourced, not re-hardcoded.

### I5 — an empty gate list never stamps green. NOT WEAKENED.
`if not config.gates:` is untouched; the change is confined to
`tree_fingerprint` and does not touch `run_gates` or `verify_stamp`'s
zero-gate INVALID path.

### I1 / R1 / S1 — closed enum, enforce at an existing point. NOT WEAKENED.
No new `Stage`, no new `_ORDER` entry, no new hook, no new state-guard. The
change is additive inside one existing function. This matches the recorded
rejection of a config-editing hook (`DECISIONS.md` F4) and honors the
"enforce at an existing point rather than grow the state machine" grain.

### Dependency-free stdlib core. NOT WEAKENED.
The only new import is the internal `CONFIG_FILE` from `loop_harness.config`.
Confirmed no import cycle (`config.py` does not import `stamp`). No
third-party dependency added.

### Surgical scope. UPHELD.
Every changed line traces to the ticket's code surface (re-bind + docstring,
matched fence tests, manifesto I6/§2, onboarding + tutorial doc qualifiers).
`.loop/ledger.json` is harness-written bookkeeping, excluded from the
fingerprint, not a scope violation.

### DECISIONS.md section F. PRESENT AND CONSISTENT.
`git show HEAD:DECISIONS.md` confirms section F (F1-F4) is committed at HEAD
and matches the implemented behavior: whole-file binding (F2), no `config.py`
validation of a self-excluding ignore-list (F3), and the rejected hook (F4).
Whole-config binding (vs contract-keys-only) is architecturally sound per F2:
simplest code, single-sourced, binds the entire contract; the only cost is a
harmless legitimate re-stamp on cosmetic edits.

## Non-blocking observations (baseline is silent; not required fixes)

- The R4 fence test parametrizes `.loop/config.json`, `.loop/`, and `.loop`,
  but not the whole-tree pathspec `.` that the ticket R4 text also names.
  Architecturally the re-bind still handles `.` correctly (config is re-added
  after the full strip), so this is a test-coverage nit owned by the
  adversarial reviewer, not an architectural violation.

## Verdict

pass. Every architectural invariant the change touches (I3, I5, I6, and the
§2 architecture note) is upheld, the enforcer citations resolve to real code
and describe actual behavior, the closed-enum / enforce-at-an-existing-point
grain is preserved, and the change is single-sourced, dependency-free, and
surgically scoped. The mechanism is consistent with the committed DECISIONS.md
section F.
