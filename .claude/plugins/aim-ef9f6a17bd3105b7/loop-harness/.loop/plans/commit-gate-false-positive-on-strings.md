# commit-gate-false-positive-on-strings

## 1. Title

Gate `git commit` only when the command actually invokes the subcommand,
not when "git commit" appears as string data (echo argument, `--grep`
value, comment).

## 2. Size / Effort

**S–M.** One helper plus two call-site swaps in `hooks.py`, and a handful
of parametrized test rows. The effort is not volume; it is picking a
tokenizer boundary that kills the false positives without regressing the
true positives the suite already pins (compound commands like
`git add -A && git commit`), and being honest in code and tests about
where shell-parsing fidelity stops.

## 3. Triggered by

Confirmed empirically. A read-only `git log` command carrying the
substring "git commit" inside an `echo`/`--grep` argument was blocked by
the commit gate on a stale stamp. A non-committing command must never be
gated. Reproduced cases:

- `echo "=== all git commit subjects ==="` — blocked (false positive)
- `git log --grep="git commit"` — blocked (false positive)
- `# git commit here later` (a comment) — blocked (false positive)

## 4. Context

The gate's command detector is a raw substring regex:

- `src/loop_harness/hooks.py:45` — `_GIT_COMMIT_RE = re.compile(r"\bgit\s+commit\b")`,
  with the deliberately-narrow intent comment at `hooks.py:43-44` (matches
  `git commit`, not `git -C <path> commit`).
- `src/loop_harness/hooks.py:151` — `if not _GIT_COMMIT_RE.search(command):`
  inside the pure `decide_commit_gate`. This is the policy gate.
- `src/loop_harness/hooks.py:223` — `if not _GIT_COMMIT_RE.search(command):`
  inside `_pre_commit_gate`, a fast-path pre-filter before the expensive
  ledger/stamp/verdict work.

Because `.search()` runs against the whole Bash command string, the regex
matches "git commit" wherever it appears as text: a quoted echo argument,
a `--grep=`/`-m` value, or a `#` comment. The `\b...\b` boundaries only
stop `git commitish` (pinned by the existing negative case at
`tests/test_hooks.py:34`); they do nothing about quoting, argument values,
or comments. The result is a read-only command gated as if it were a
commit.

## 5. Non-goals / out of scope

- **Target-repo resolution.** The gate reads `Path.cwd()`
  (`hooks.py:225`) and so gates the session repo, missing
  `cd other && git commit` and `git -C other commit`. That is a DIFFERENT
  defect owned by the sibling ticket `commit-gate-targets-the-committed-repo`.
  Do not touch cwd/`-C` target logic here. See §9 for the coordination.
- **Weakening true-positive detection.** A real `git commit -m "..."`,
  including inside compound commands (`git add -A && git commit -m 'y'`,
  `cd /repo && git commit`), must STILL be gated. This ticket only removes
  false positives; it must not open a hole.
- **A full shell parser.** No dependency, no attempt to model subshells,
  process substitution, `eval`, or heredocs exactly. Pick a pragmatic
  boundary and document it (see §11).
- **Extending detection to `git -C <path> commit`.** The current comment
  at `hooks.py:43-44` deliberately excludes it; keep that parity here (the
  sibling ticket owns `-C`).

## 6. Requirements & restrictions

R1. The gate fires when, and only when, the command genuinely invokes
`git commit` as a subcommand. "git commit" inside a quoted string, an
`=`-joined or space-separated argument value (`--grep`, `-m`), or a `#`
comment must NOT trigger the gate.

R2. True positives are preserved. At minimum every command currently
pinned as blocked stays blocked: `git commit`, `git commit -m 'x'`,
`git add -A && git commit -m 'y'`, `cd /repo && git commit`
(`tests/test_hooks.py:45`, `:57`, `:62`, `:67`, and the loop-commit cases
that pass literal `"git commit"`).

R3. Parity with today's narrow intent: detect `git` immediately followed
by the `commit` subcommand. Do NOT start matching `git -C <path> commit`
(`hooks.py:43-44`); that belongs to the sibling.

R4. **Core stays stdlib-only** (MANIFESTO.md §4 Values, "Dependency-free
core", `MANIFESTO.md:197-199`). `shlex` is stdlib and is the intended
tool; adding any third-party parser violates this value.

R5. **Hooks fail toward safety, wrapped by fail-open.** The outer hook
bodies already wrap in `try/except` and return allow on internal error
(`hooks.py:242-244`, `hooks.py:317-319`; MANIFESTO.md §4 "Hooks fail open
on internal error", `MANIFESTO.md:200-203`). The pure `decide_commit_gate`
must not introduce an unhandled raise that changes gate policy silently —
see the shlex-parse-failure fork in §11 (Q1).

R6. **A test ships with the change** (`.claude/rules/python-testing.md`,
"all-code-needs-tests"). This is a bug fix, so a reproducing test comes
first: assert each false-positive command from §3 is ALLOWED, then make
it pass, and add a true-positive guardrail row.

R7. **Numpy docstrings on touched objects** (`.claude/rules/python-docstrings.md`,
"python-objects-need-docstrings"). Any new helper carries a one-line
summary plus `Parameters`/`Returns`; if `_GIT_COMMIT_RE`'s intent comment
moves into a helper, the contract note moves with it.

R8. **Surgical scope** (MANIFESTO.md §4, `MANIFESTO.md:204-206`). Every
changed line traces to this defect. Do not refactor the surrounding gate
logic.

## 7. Code surface

- `src/loop_harness/hooks.py:45` — replace the raw-substring
  `_GIT_COMMIT_RE` usage with a detector that decides on tokens, not text.
  Recommended shape: a private helper
  `_invokes_git_commit(command: str) -> bool` that (a) drops `#` comments,
  (b) splits the command on shell sequencing operators (`&&`, `||`, `;`,
  `|`, newlines) into segments, (c) `shlex.split`s each segment, and (d)
  returns True when a segment's leading token is `git` and its next token
  is `commit`. Keep the raw regex only if it is used as the documented
  fallback for a shlex parse failure (see §11 Q1). Add `import shlex`
  (stdlib, R4).
- `src/loop_harness/hooks.py:151` — swap `_GIT_COMMIT_RE.search(command)`
  for the new helper inside `decide_commit_gate`.
- `src/loop_harness/hooks.py:223` — swap the identical pre-filter in
  `_pre_commit_gate` for the same helper, so both call sites share one
  definition of "is this a commit" (no drift between fast-path and policy).
- `tests/test_hooks.py` — home for every test named in §8. Extend the
  existing parametrized negative case (`:32-40`) with the three §3
  false-positive strings, and the positive case (`:43-51`) with a
  no-space-quoted true-positive guardrail. Mirror the file's existing
  `decide_commit_gate(command, halted=None, verdict=...)` call style
  (`tests/test_hooks.py:38`).

## 8. Tests & validation gates

Gate commands (from `.loop/config.json:2-5`), run both before declaring
done:

- `git add --intent-to-add -A . && uv run pytest`
- `uvx prek run --all-files`

Discover and follow the project's task runner / `prek` invocation per
`.claude/rules/prek-code-quality.md`; run tests through `uv`, never bare
`pytest` (`.claude/rules/python-testing.md`). Tests are linted and
type-checked like production code; do not silence a gate to go green
(`.claude/rules/pre-existing-issues.md`).

Tests to add, all in `tests/test_hooks.py` (§7):

- **Reproducers (bug-first, must ALLOW).** Add to
  `test_non_commit_commands_pass_untouched` (`:32`):
  `echo "=== all git commit subjects ==="`,
  `git log --grep="git commit"`, and `# git commit here later`. Each must
  yield `allow=True` and an empty message, exactly as the existing
  negatives do.
- **True-positive regression guard (must BLOCK).** Confirm the existing
  blocked set still blocks after the swap: `git commit`,
  `git commit -m 'x'`, `git add -A && git commit -m 'y'`,
  `cd /repo && git commit` (already at `:45`; keep them green, do not
  delete). Add one adversarial guardrail the operator should decide on:
  an operator-glued `git add&&git commit` (see §11 Q2) — assert the
  behavior you land on, and let the row document the boundary.
- **Boundary honesty.** If Q1 lands as "regex fallback on parse failure",
  add a row for a malformed-quote command carrying a real commit (e.g.
  `git commit -m "oops) — assert it still BLOCKS (fails toward the gate),
  proving the fallback direction.

## 9. Risk assessment

- **Blast radius.** Narrow but load-bearing. The helper is the single
  predicate that decides whether the commit gate engages at all. A false
  negative here (a real commit read as non-commit) silently disables the
  gate for that command — worse than the bug being fixed. R2's regression
  guards exist for exactly this.
- **Reversibility.** High. Pure-function change plus tests; revert is a
  one-file rollback. No state, no migration.
- **Likeliest failure modes.**
  1. Tokenizer regresses a compound true positive (`&&`/`;`/`|` handling).
     Mitigated by keeping the existing blocked parametrizations green.
  2. `shlex.split` raises `ValueError` on unbalanced quotes and, absent a
     decision, either fails open (allows a real commit) or wedges. Forced
     to a decision in §11 Q1.
  3. Operator-glued operators without whitespace (`git add&&git commit`)
     tokenize as one blob and slip the gate — a true-positive the OLD
     substring regex happened to catch. Named in §11 Q2 so it is a chosen
     boundary, not an accident.
- **Sibling collision.** `commit-gate-targets-the-committed-repo` edits
  the same detection area (adding `git -C <path> commit` / cwd handling).
  Whichever lands first, the other rebases onto the shared helper. Keep
  this change to a self-contained `_invokes_git_commit` so the sibling
  extends one function rather than a scattered regex.

## 10. Subtickets

Small enough for one loop pass; ordered so each step is independently
verifiable:

1. Add the `_invokes_git_commit` helper (comments-stripped, segment-split,
   shlex-tokenized) with a numpy docstring. Verify: the three §3
   reproducers return False and the R2 true positives return True in a
   scratch unit test.
2. Swap both call sites (`hooks.py:151`, `:223`) to the helper; remove or
   demote `_GIT_COMMIT_RE` per the Q1 outcome. Verify: full `uv run pytest`
   green, including the extended parametrizations.
3. Add the §8 test rows (reproducers, regression guard, boundary row).
   Verify: both gate commands (§8) pass.

## 11. Open questions

**Q1 — shlex parse failure direction.** `shlex.split` raises `ValueError`
on unbalanced quotes. `decide_commit_gate` is a pure function; an
unhandled raise propagates to the outer hook wrapper, which fails OPEN and
ALLOWS the command (`hooks.py:242-244`) — meaning a malformed-but-committing
command would slip the gate. That contradicts the gate's fail-SAFE stance
(MANIFESTO I8, `MANIFESTO.md:138-143`) even though the outer hook is
fail-open by design. *Recommendation:* catch the `ValueError` inside the
helper and fall back to the old substring regex for that command only
(conservative: still gates, reintroducing the false positive only for the
rare malformed input). This keeps the pure function total and points
ambiguity toward the gate, not around it. Operator to confirm.

**Q2 — operator-glued sequencing (`git add&&git commit`).** Splitting on
whitespace-delimited operators misses operators with no surrounding space.
The old raw-substring regex caught these as a side effect; a strict
tokenizer would not, creating a true-positive regression on an unusual but
legal command. *Recommendation:* split on the operator tokens `&&`, `||`,
`;`, `|`, and newlines regardless of adjacent whitespace (regex split, not
`str.split`), so `git add&&git commit` still yields a `git commit`
segment. Accept that deeper constructs (subshells `$(...)`, backgrounding,
`eval`) remain out of scope and documented. Operator to confirm the
boundary is acceptable.

**Q3 — comment stripping fidelity.** A leading `#` on a command line is a
comment, but `#` mid-token (`git commit -m "fix #42"`) is data, not a
comment — and `shlex.split(comments=True)` would wrongly truncate at the
`#`. *Recommendation:* do NOT use `shlex(comments=True)` blanket; strip
only a `#` that begins a segment (after operator-splitting and left-strip),
leaving in-string `#` to shlex's quote handling. This keeps
`# git commit later` a no-op while not corrupting a commit message that
contains `#`. Operator to confirm.

**Q4 — keep `_GIT_COMMIT_RE` as a named constant?** If Q1 lands as
"regex fallback", the pattern stays; otherwise it is dead. *Recommendation:*
keep it iff it is the Q1 fallback, and move the `hooks.py:43-44` intent
comment onto the new helper's docstring so the "narrow, not `-C`"
contract travels with the logic the sibling ticket will extend.

## Eval marker (required before pickup)

`.loop/config.json` sets `require_eval: true` (`.loop/config.json:9`). Per
MANIFESTO I14 (`MANIFESTO.md:178-182`), the loop refuses to enter
`implementing` until a schema-valid eval marker
(`.loop/evals/commit-gate-false-positive-on-strings.md`) exists. Author it
before implementation.
