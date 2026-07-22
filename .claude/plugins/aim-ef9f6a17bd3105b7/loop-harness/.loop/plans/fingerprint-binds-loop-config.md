# fingerprint-binds-loop-config: bind `.loop/config.json` into the tree fingerprint so weakening the verification contract stales the stamp

## 1. Title

Include `.loop/config.json` in the tree fingerprint (while keeping every
other `.loop/` file excluded) so any change to the gate commands or the
`fingerprint_ignore` list flips a green stamp to STALE and forces a
re-stamp plus re-review, closing the hole where an agent silently weakens
the definition of "green."

## 2. Size / Effort

**S.** One narrow change to `tree_fingerprint` in `stamp.py` (re-bind a
single path after the `.loop` strip), a matched set of tests in
`tests/test_stamp.py`, and doc/manifesto edits that keep the invariant text
honest. No new module, no config schema change, no signature change to any
caller. What little size there is comes from the manifesto/DECISIONS update
and the adversarial edge cases the tests must cover.

## 3. Triggered by

Verified vulnerability: the harness's promise is "evidence over claims" — a
green stamp binds gate exit codes to a git tree fingerprint, and a changed
tree invalidates the stamp. But the *definition of what "green" means* lives
in `.loop/config.json` (`gates` and `fingerprint_ignore`), and
`tree_fingerprint` strips ALL of `.loop/` before `git write-tree`
(`stamp.py:110`). Config is therefore OUTSIDE the evidence. An agent that
cannot make the suite pass can weaken a gate (`... || true`, `pytest -k
nothing`, swap the command) or widen `fingerprint_ignore` to exclude the
files it just changed; the stamp stays OK and "fresh", and `verify_stamp`
never notices, because config is outside the fingerprint and verify does not
compare the stamp's recorded gate commands against the current config. The
verification contract is agent-editable and unbound.

## 4. Context (today's state)

- `tree_fingerprint` builds a throwaway index with `git add -A .`, then
  strips the whole `.loop/` directory before `git write-tree`:
  `stamp.py:109-115`. The strip line is `git("rm", "-r", "--cached",
  "--ignore-unmatch", "-q", ".loop")` at `stamp.py:110`, followed by a loop
  applying each `fingerprint_ignore` pathspec (`stamp.py:111-114`).
- The docstring rationale for excluding `.loop/` is `stamp.py:67-77`: "the
  stamp certifies the CODE tree, so loop state ... never invalidates it."
  This is correct for churny state files but wrong for `config.json`, which
  is not state — it is the contract the stamp certifies against.
- `config.json` holds the contract keys: `gates` (`config.py:189`,
  `config.py:222-228`) and `fingerprint_ignore` (`config.py:197`,
  `config.py:229-241`). It is git-tracked (present at
  `.loop/config.json`), so a weakening edit does show in `git diff` — but
  that is a human/agent backstop, not a mechanical one.
- Existing partial defenses (KEEP, do not duplicate): an empty gate list is
  blocked at write (`run_gates` raises, `stamp.py:131-135`, invariant I5)
  and at verify (a zero-gate stamp is INVALID, `stamp.py:194-195`).
- The `stamp-fingerprint-ignore-list` ticket (done) added the config-driven
  `fingerprint_ignore` list; the recent commit `commit-gate-false-positive-
  on-strings` and `stamp-fingerprint-ignore-list` (`git log`) are its
  lineage. That ignore-list is itself part of the contract this ticket now
  binds, so it must be bound too — and it must not become a lever to
  un-bind `config.json` (see §6 R4 and §9).
- The tree fingerprint is single-sourced: every caller routes through
  `tree_fingerprint` (`ctl.py:70-72`, `cli.py:44-46`, `hooks.py:418-423`,
  `stamp.py:167`, `stamp.py:202`), each resolving the ignore-list from
  `LoopConfig.fingerprint_ignore`. This ticket changes only the one
  function, so all callers inherit the new policy with no signature change.

## 5. Non-goals / out of scope

- **Do NOT add a hook or state-guard that forbids editing `config.json`.**
  Explicitly rejected: (1) a state-guard blocks only Edit/Write, so a Bash
  write bypasses it — it fails against the exact adversarial case; (2)
  editing config is a legitimate, documented workflow
  (`docs/tutorials/custom-reviews-and-actions.md` walks a user through
  editing config to add a review pass). The goal is not "config cannot
  change" but "changing the contract invalidates the evidence."
- **Do NOT bind the whole `.loop/` directory.** Only `config.json`. The
  churny state files (`ledger.json`, `stamp.json`, `verdicts/*`,
  `reflections/*`, `handoff.log`, `HALT`, and any future state log) must
  stay excluded. A sibling ticket (`reflection-derives-mechanical-facts`,
  #3) ADDS a new churny state file under `.loop/`; the allowlist-of-one
  approach (bind only `config.json`) keeps that automatically excluded.
- Do not change any gate command, add a config key, or alter the
  `fingerprint_ignore` semantics for non-`.loop` paths.
- Do not add config-key-level normalization/hashing unless the operator
  chooses that fork in §11 (default recommendation is whole-file binding).
- Do not compare recorded stamp gate commands against current config inside
  `verify_stamp` (an alternative mechanism) — binding the file into the
  fingerprint is the chosen, simpler mechanism and makes that redundant.

## 6. Requirements & restrictions

- **R1. Bind `config.json` into the fingerprint.** After the change, a
  change to `.loop/config.json` (its `gates` or `fingerprint_ignore`, and —
  under the recommended whole-file fork — any of its bytes) must change the
  `tree_fingerprint` output, so `verify_stamp` reads STALE and the loop
  re-stamps and re-reviews. This directly serves "Evidence over claims"
  (`MANIFESTO.md:24-26`) and strengthens I4 ("A stamp goes stale the moment
  the tree changes", `MANIFESTO.md:112-116`).
- **R2. Bind ONLY `config.json`.** Every other path under `.loop/` stays
  out of the fingerprint. This preserves invariant I6 ("Loop bookkeeping
  never invalidates a code stamp", `MANIFESTO.md:124-129`) for state files
  while carving `config.json` out of the "bookkeeping" category, because
  config is contract, not bookkeeping.
- **R3. Single-sourced policy.** The include/exclude decision stays inside
  `tree_fingerprint` so `write_stamp` and `verify_stamp` (and every other
  caller) use byte-identical policy. Do not add a second definition —
  invariant I3 (`MANIFESTO.md:105-110`, and the module docstring
  `stamp.py:8-10`) forbids two fingerprints.
- **R4. The binding must be undefeatable by `fingerprint_ignore`.** An
  adversarial config that lists `.loop/config.json` (or a broad pathspec
  such as `.loop/` or `.`) in `fingerprint_ignore` must NOT remove
  `config.json` from the fingerprint. The natural implementation is to
  re-bind `config.json` AFTER both the `.loop` strip and the ignore loop, so
  no ignore pattern can subtract it. (Ordering matters: the ignore loop runs
  at `stamp.py:111-114`; the re-bind must come after it.)
- **R5. Fail-safe on absence.** When `.loop/config.json` does not exist
  (a repo running on default config), the fingerprint behaves exactly as
  today (whole tree minus `.loop`), with no error. Re-binding a missing
  path must be guarded (`--ignore-unmatch`, or an existence check) so it
  never makes `write-tree` fatal — a fatal `git` here would be swallowed by
  the commit hook's fail-open (`hooks.py:425-427`) and silently disable the
  gate, the same failure mode `config.py:235-240` guards against.
- **R6. Keep the manifesto honest.** This ticket MODIFIES the mechanism
  behind I6 and the architecture note at `MANIFESTO.md:79-83` ("The whole
  `.loop/` directory is excluded"). Update I6's prose and its enforcer
  citation, and the §2 architecture text, to state that `config.json` is
  bound as part of the certified evidence while the rest of `.loop/` is
  excluded. State plainly that this STRENGTHENS the evidence-over-claims
  promise (it closes an unbound-contract hole); it does not weaken any
  invariant. The architectural review pass reviews against `MANIFESTO.md`
  (`.loop/config.json` `review_passes[architectural].baseline`), so stale
  manifesto text will (correctly) block the commit.
- **R7. Record the decision.** Add a decision entry to `DECISIONS.md`
  capturing the fork resolution from §11 (whole-file vs contract-keys) and
  the config-binding rationale, referencing `stamp-fingerprint-ignore-list`.
- **Repo restrictions.** Dependency-free stdlib core
  (`MANIFESTO.md:197-199`); surgical scope — every changed line traces to
  this ticket (`CLAUDE.md` §3, `MANIFESTO.md:204-206`); simplicity first,
  the minimum code (`CLAUDE.md` §2); every Python object keeps a numpy-style
  docstring updated to match new behavior
  (`.claude/rules/python-docstrings.md`); tests never mock git — use real
  temp repos (`.claude/rules/python-testing.md`,
  `dont-mock-what-you-can-run`).

## 7. Code surface

- `src/loop_harness/stamp.py:109-115` — inside `tree_fingerprint`, after the
  `.loop` strip (`stamp.py:110`) AND after the `fingerprint_ignore` loop
  (`stamp.py:111-114`), re-bind `config.json` into the index so it survives
  into `write-tree`. Recommended shape (implementer confirms exact git
  pathspec behavior against a real repo):
  `if (repo / CONFIG_FILE).exists(): git("add", "--", str(CONFIG_FILE))`,
  importing `CONFIG_FILE` from `loop_harness.config` (config.py does not
  import stamp, so no import cycle). Do NOT hardcode the path string
  separately — single-source it from `config.CONFIG_FILE` (`config.py:20`).
- `src/loop_harness/stamp.py:61-94` — update the `tree_fingerprint`
  docstring: `.loop/` is stripped EXCEPT `.loop/config.json`, which is bound
  because it defines the verification contract the stamp certifies against,
  and the binding is not defeatable by `fingerprint_ignore`.
- `tests/test_stamp.py` — add the tests named in §8 (this is the declared
  home for every test §8 names).
- `MANIFESTO.md:79-83` and `MANIFESTO.md:124-129` (I6) — update the
  exclusion prose and I6's enforcer citation per R6.
- `DECISIONS.md` — append the decision entry per R7 (file ends at the S4
  block; add a new lettered entry or subsection).
- `docs/onboarding.md:179` and `docs/onboarding.md:200` — the mermaid label
  "minus .loop/" and the prose "the ... directory is stripped out before the
  fingerprint" become inaccurate; qualify them with "except config.json".
  (`README.md:85-89` describes `fingerprint_ignore` correctly and needs no
  change; check it reads consistently after the manifesto edit.)
- `docs/tutorials/custom-reviews-and-actions.md:99-120` — the "edit
  `.loop/config.json` to add your pass" step now implies a re-stamp; add at
  most a one-line note that editing config re-stales the stamp and the loop
  will re-run the gates. Keep it minimal (slop rules apply to docs).

## 8. Tests & validation gates

**Gates the repo actually runs** (from `justfile` `check` and
`.pre-commit-config.yaml`; run via the task runner, not bare tools):

- `uv run pytest` (full suite).
- `uvx prek run --all-files` — runs `ruff check --fix`, `ruff format`, and
  `mypy`. (`just check` runs both, matching the configured `gates`.)
- Review gate: adversarial pass (`loop-reviewer`) AND architectural pass
  (`loop-architect`, baseline `MANIFESTO.md`), both enabled in
  `.loop/config.json`; each writes a tree-bound verdict (I2,
  `MANIFESTO.md:97-103`). The architectural pass will read the manifesto
  edits from R6.

**Reproducing test first** (the vulnerability, written before the fix):

- `test_config_edit_stales_the_stamp` — create `.loop/config.json` with real
  gates, `write_stamp` green, then edit `gates` in `config.json` (a
  weakening edit, e.g. append `|| true`), and assert `verify_stamp` returns
  `StampStatus.STALE`. This FAILS on today's code (config is stripped) and
  passes after the fix. Use `load_config(repo).fingerprint_ignore` for the
  ignore arg so write and verify share policy.

**Tests that fence the requirements** (all in `tests/test_stamp.py`):

- `test_fingerprint_ignore_cannot_exclude_config` (R4) — set
  `fingerprint_ignore` to `[".loop/config.json"]` (and a parametrized case
  for `".loop/"`), stamp green, edit `config.json` `gates`, assert the
  fingerprint still changes / verify reads STALE. Proves the ignore-list
  cannot re-open the hole.
- `test_churny_loop_state_still_never_stales` (R2) — extends the existing
  `test_loop_state_never_invalidates_the_stamp` (`test_stamp.py:77-83`):
  after a green stamp, writing `.loop/ledger.json`, `.loop/stamp.json`,
  `.loop/HALT`, AND a novel unrelated state file (e.g.
  `.loop/reflections/x.md` or `.loop/handoff.log`, standing in for the
  sibling #3 file) must keep the stamp OK.
- `test_config_binding_backward_compatible_when_absent` (R5) — with NO
  `.loop/config.json` present, `tree_fingerprint`/`verify_stamp` behave as
  today (no crash; a non-`.loop` change still stales). Guards the fail-safe.
- Confirm the existing `test_all_callers_fingerprint_identically_via_config`
  (`test_stamp.py:168-185`) still passes: `config.json` is unchanged between
  write and verify there, so it stays OK — a green witness that legitimate,
  unchanged config does not falsely stale.

Note: the `repo` conftest fixture (`tests/conftest.py`) does NOT create
`.loop/config.json`; tests that exercise binding must create it explicitly
under `tmp_path` (real files, no mocking).

## 9. Risk assessment

- **Blast radius.** One function (`tree_fingerprint`), consumed by every
  stamp read/write. A mistake here changes what "green" means everywhere at
  once — but the change is additive (bind one more path), single-sourced, and
  fully covered by the fingerprint tests.
- **Reversibility.** High. Reverting the re-bind line restores prior
  behavior; no data migration, no persisted format change (the stamp payload
  shape at `stamp.py:166-170` is unchanged — only the hashed input widens).
- **Likeliest failure modes.** (1) Re-binding BEFORE the ignore loop instead
  of after, leaving `fingerprint_ignore` able to subtract `config.json`
  (R4 hole) — the R4 test catches it. (2) A fatal `git add` on a missing
  `config.json` swallowed by the hook's fail-open, silently disabling the
  gate (`hooks.py:425-427`) — the R5 test catches it. (3) Over-reach:
  binding more of `.loop/` than `config.json`, staling stamps on every
  ledger write — the R2 test catches it. (4) Stale manifesto text failing
  the architectural pass — expected and desired; fix by completing R6.
- **Not a full fix by itself.** Binding forces a re-stamp and re-review on a
  contract change; the re-review is where the adversarial/architectural pass
  sees the config diff and can reject a weakening. This ticket makes the
  cheat non-silent and mechanically re-gated; it does not (and cannot)
  mechanically judge whether a given config edit is legitimate. State this
  honestly in the manifesto note (R6).

## 10. Subtickets

Small enough for one PR; ordered for a clean loop:

1. Add `test_config_edit_stales_the_stamp` (reproducing test) and watch it
   fail on current code. → verify: the test fails for the right reason
   (fingerprint unchanged after config edit).
2. Implement the re-bind in `tree_fingerprint` (after the ignore loop),
   guarded for absence; update its docstring. → verify: reproducing test
   passes; full suite green.
3. Add the R2 / R4 / R5 fence tests. → verify: all pass; no existing stamp
   test regresses.
4. Update `MANIFESTO.md` (I6 + §2 exclusion note) and `DECISIONS.md`; qualify
   `docs/onboarding.md` and the tutorial. → verify: `uvx prek run
   --all-files` clean; architectural pass reviews against the updated
   manifesto.

## 11. Open questions

- **Q1 (for DECISIONS.md): bind the whole `config.json` file, or only the
  contract keys (`gates` + `fingerprint_ignore`)?**
  - *Whole file* (recommended): trivial to implement (bind the path),
    strictly single-sourced through `tree_fingerprint`, and — because
    `review_passes`/`require_review`/`require_eval` also shape what
    "committable" means — it binds the *entire* verification contract, which
    is more correct for the stated goal. Cost: a cosmetic edit
    (`notify_title`, `plans_dir`) also re-stales the stamp and forces a
    re-stamp. Every such re-stamp is legitimate (re-run gates on the exact
    tree), so this is churn, not incorrectness.
  - *Contract keys only*: avoids re-staling on cosmetic edits, but needs a
    normalized hash of a chosen key subset injected into the index — more
    code, and it forces a second judgment call (WHICH keys are
    contract-relevant: just `gates`+`fingerprint_ignore`, or also the review
    passes?), which drifts and can silently under-bind.
  - **Recommendation: whole file.** It is the simplest code, honors
    simplicity-first, binds the full contract, and its only downside is
    harmless re-stamps. This is an operator-observable behavior choice, so
    record it in `DECISIONS.md` rather than deciding silently.
- **Q2: should `config.py` ALSO reject a `fingerprint_ignore` entry that
  targets `.loop/config.json`, as defense-in-depth?** With the R4 re-bind,
  such an entry is already neutralized (the re-bind wins), so validation is
  redundant code. **Recommendation: no — rely on the re-bind and prove it
  with the R4 test.** Add validation only if the operator wants a loud
  `ConfigError` on that pathspec instead of silent neutralization.
