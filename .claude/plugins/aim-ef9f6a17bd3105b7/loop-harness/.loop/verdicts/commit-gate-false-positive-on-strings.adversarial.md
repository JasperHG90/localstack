verdict: pass
tree: cff704c4e93b950acf4b65e4392fd8842e773c1d

# Adversarial re-review (cycle 2) — commit-gate-false-positive-on-strings

Pass: adversarial. Re-audited the full change at the bound tree via
`git diff HEAD` on `src/loop_harness/hooks.py` and `tests/test_hooks.py`.
Both gates re-run independently and pass:

- `git add --intent-to-add -A . && uv run pytest` — 218 passed.
- `uvx prek run --all-files` — ruff-lint, ruff-format, mypy all Passed.

The detector was also exercised directly against the pinned cases and the
adversarial probes below.

## F1 (prior required fix) — CONFIRMED FIXED

The detector no longer requires `tokens[0] == "git"`. `_invokes_git_commit`
(`src/loop_harness/hooks.py:69`) now matches when ANY adjacent token pair is
`git` then `commit` via
`any(a == "git" and b == "commit" for a, b in pairwise(tokens))`
(`hooks.py:120`). Verified empirically that env-prefixed and wrapper-prefixed
real commits gate again:

- `FOO=bar git commit` → True
- `GIT_COMMITTER_DATE=2020 git commit --amend` → True
- `sudo git commit` → True
- `env GIT_AUTHOR_NAME=x git commit` → True

Pinned by new rows in `test_invokes_git_commit` (`tests/test_hooks.py:67-70`)
and the F1 gate-level row `GIT_COMMITTER_DATE=2020 git commit` in
`test_commit_without_stamp_is_blocked` (`tests/test_hooks.py:93`).

## No new false negative introduced

- Token adjacency via `pairwise` is a strict superset of the interim
  `tokens[0]` predicate, so nothing the prior fix caught is lost.
- `git -c user.name=x commit` and `git -C other commit -m x` return False —
  the ORIGINAL raw regex `\bgit\s+commit\b` also missed these (git not
  immediately followed by commit), so this is parity, not a regression, and
  R3 assigns the `-C` form to the sibling ticket.
- The only theoretical new miss versus the original substring regex is a
  commit nested in a quoted wrapper (`bash -c "git commit"`): shlex collapses
  the quoted body to one token, so no adjacency fires. This is the documented
  "no full shell parser / subshells / quoted bodies out of scope" boundary
  (ticket §5, §11; docstring `hooks.py:89-93`). An agent issues `git commit`
  directly, not nested in a shell string, so practical evasion risk is
  negligible. Informational, not blocking.

## Original three false positives — remain fixed

- `echo "=== all git commit subjects ==="` → allow=True
- `git log --grep="git commit"` → allow=True
- `# git commit here later` → allow=True

Pinned in `test_non_commit_commands_pass_untouched` (`tests/test_hooks.py:41-43`)
and `test_invokes_git_commit` (`tests/test_hooks.py:56-58`). Each fails
against the pre-fix code at HEAD (raw regex substring-matched them →
allow=False), so the reproducers are genuine, not tautologies.

## R3 `-C` parity — preserved

`git -C other commit -m x` → False (verified empirically; pinned at
`tests/test_hooks.py:59`). The "narrow, not `-C`" intent note moved onto the
helper docstring (`hooks.py:73-75`), carrying the contract with the logic the
sibling ticket will extend.

## Over-gate boundary — honestly documented, hides no real miss

The `echo git commit` (unquoted) over-gate returns True and is documented in
the docstring (`hooks.py:86-88`) and pinned as a test row
(`tests/test_hooks.py:71`). This is a false POSITIVE (over-gating a
non-commit), the safe direction, not a hidden false negative. I hit a live
instance of the related "operators inside quotes" boundary:
`echo "a && git commit"` over-gates because `_SEQUENCING_RE` splits on `&&`
inside quotes and the fragment then fails shlex and falls back to the
substring regex. That is exactly the "operators inside quotes out of scope"
case named in the docstring (`hooks.py:92`) and §11 Q2. It re-admits the
false-positive class only for quoted data that ALSO carries a shell operator
— a narrow, declared trade erring toward the gate. Informational.

## Boundary forks Q1/Q2/Q3 — all honored

- Q1: `git commit -m "oops` (unbalanced quote) → shlex raises, falls back to
  `_GIT_COMMIT_RE.search` → True (still gates). `hooks.py:114-118`;
  rows `tests/test_hooks.py:66`, `:91`.
- Q2: `git add&&git commit -m z` → True via whitespace-agnostic
  `_SEQUENCING_RE` split (`hooks.py:52`). Rows `tests/test_hooks.py:64`, `:90`.
- Q3: `git commit -m "fix #42"` → True; a `#` inside a token is not a comment
  because only a segment whose lstrip starts with `#` is skipped
  (`hooks.py:112`). Rows `tests/test_hooks.py:65`, `:92`.

## Other requirements

- R4 stdlib-only: only `shlex` (`hooks.py:31`) and `itertools.pairwise`
  (`hooks.py:36`) added — both stdlib. No third-party parser.
- R5 fail-toward-safety: the shlex ValueError is caught inside the pure
  helper; `decide_commit_gate` introduces no unhandled raise.
- Both call sites share one predicate: `hooks.py:213` (policy) and
  `hooks.py:285` (pre-filter) both call `_invokes_git_commit` — no drift.
- R7 docstring: numpy-style summary + Parameters + Returns on the new helper
  (`hooks.py:70-101`).
- R8 surgical scope: code diff is confined to the detector helper, its two
  call sites, and the import lines, plus the test additions. No unrelated
  refactor. `.loop/ledger.json` and the verdict files are harness artifacts,
  not reviewed code.

## Conclusion

F1 is genuinely fixed, no in-scope false negative is introduced, the three
original false positives stay fixed, `-C` parity holds, the over-gate is
documented and safe-direction, the new tests are meaningful against the
pre-fix code, and both gates pass. No blocking or required-fix findings.
