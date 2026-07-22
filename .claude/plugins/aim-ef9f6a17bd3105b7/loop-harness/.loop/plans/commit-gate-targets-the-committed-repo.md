# commit-gate-targets-the-committed-repo

## 1. Title

The commit gate must evaluate the repository the `git commit` actually
runs in, not the session's `cwd`, closing the `cd <path> && git commit`
wrong-repo and `git -C <path> commit` bypass holes.

## 2. Size / Effort

**M.** One focused change in `hooks.py` (a target-repo resolver plus its
use in `_pre_commit_gate`), a widened command matcher shared with a
sibling ticket, and a handful of real-temp-repo tests. Effort is driven
less by line count than by getting the fail-safe boundary right
(undeterminable target must block, not allow) and by coordinating the
`_GIT_COMMIT_RE` edit with the sibling ticket.

## 3. Triggered by

A confirmed, repeatedly reproduced defect: the commit gate is a
PreToolUse hook that fires *before* the Bash command runs, so any `cd`
inside the command has not taken effect. `_pre_commit_gate` reads
`repo = Path.cwd()` (the session directory) and evaluates the gate
against it, so:

1. `cd other-repo && git commit ...` is gated against the *session*
   repo's stamp/ledger/verdicts, not the repo the commit lands in. The
   committed repo is never gated.
2. `git -C other-repo commit ...` does not match `_GIT_COMMIT_RE` at all
   and bypasses the gate entirely.

The gate's guarantee ("blocked until THIS repo's evidence is green") is
inverted: it protects the session directory, not the committed
repository.

## 4. Context

Today's state, cited to code:

- `src/loop_harness/hooks.py:45` — `_GIT_COMMIT_RE =
  re.compile(r"\bgit\s+commit\b")`. The comment at
  `src/loop_harness/hooks.py:43-44` states the `-C` exclusion is
  *deliberate* ("matches `git commit`, not `git -C <path> commit`, so
  commits to throwaway repos elsewhere are not gated"). That rationale is
  the bug: a `-C` commit into a loop-consumer repo escapes the gate.
- `src/loop_harness/hooks.py:218-244` — `_pre_commit_gate`. At
  `src/loop_harness/hooks.py:225` it sets `repo = Path.cwd()` and from
  there resolves `loop_active(repo)`, `load_ledger(repo)`,
  `verify_stamp(repo, ...)`, `tree_fingerprint(repo, ...)`, and
  `pass_verdict_tree(repo, ...)` — every evidence lookup is anchored to
  `cwd`, never to the commit's real target.
- `src/loop_harness/hooks.py:61-67` — `loop_active(repo)` is the dormancy
  switch: a repo without `.loop/` is not a consumer and the hook must
  no-op there. This is evaluated against `cwd` today; it must be
  evaluated against the resolved target.
- `src/loop_harness/hooks.py:151-152` — `decide_commit_gate` re-runs
  `_GIT_COMMIT_RE.search(command)` as its first guard. This pure policy
  function receives the already-resolved evidence; it does not resolve
  the repo and should not need to. The repo resolution belongs upstream
  in `_pre_commit_gate`.
- The module docstring at `src/loop_harness/hooks.py:3-10` states the
  fail-open (internal error) and dormancy contracts the change must
  preserve.

What is wrong: the resolution of *which repo* is hard-coded to `cwd` and
the command matcher is blind to the two most common ways a `git commit`
runs somewhere other than `cwd`.

## 5. Non-goals / out of scope

- **The string-data false positive.** `_GIT_COMMIT_RE` also
  substring-matches `git commit` inside `echo`/`grep`/comment text. That
  is a *different* defect owned by the sibling ticket
  `commit-gate-false-positive-on-strings`. Do not fix it here. This
  ticket may assume the command is a genuine git invocation when
  resolving its target. See §9 and §11 for the coordination.
- **General shell parsing.** Do not build a POSIX shell parser. Handle
  the two named forms (a leading `cd <path> &&` prefix and a `git -C
  <path> commit` form) and fail safe on anything else (§11).
- **Changing the pure policy signature.** `decide_commit_gate` stays a
  pure function over already-resolved evidence. Do not push repo
  resolution into it.
- **Windows path semantics / non-`&&` chaining** (`;`, `||`, subshells,
  `pushd`) beyond recognizing them as undeterminable. Resolving them is
  out of scope; recognizing them as "cannot determine → fail safe" is in
  scope.

## 6. Requirements & restrictions

Requirements:

- **R1.** Resolve the directory the `git commit` will actually run in
  from `(command, cwd)`: parse a leading `cd <path> &&` prefix (relative
  paths resolved against `cwd`) and a `git -C <path> commit` form, and
  evaluate the gate — dormancy check, stamp, ledger, verdicts, tree
  fingerprint — against that resolved directory.
- **R2.** Detect the `-C` commit form so it is gated at all (today it
  slips past `_GIT_COMMIT_RE` entirely).
- **R3.** When the target repo cannot be determined unambiguously, **fail
  safe: block** with a clear reason on stderr (exit 2), never allow. This
  is a policy ambiguity, which fails safe toward more checking
  (MANIFESTO.md:30-32; MANIFESTO.md:138 I8), distinct from an internal
  *error*, which still fails open (MANIFESTO.md:200; module docstring
  `src/loop_harness/hooks.py:3-6`). See the §11 open question on the
  exact fail-safe scope.
- **R4.** Preserve dormancy: if the *resolved target* has no `.loop/`, it
  is not a consumer and the hook no-ops (allow), even when the session
  `cwd` is a consumer, and vice versa (`loop_active` at
  `src/loop_harness/hooks.py:61-67`).
- **R5.** Preserve the internal-error fail-open contract: the outer
  `try/except` in `_pre_commit_gate` still returns 0 on an unexpected
  exception (`src/loop_harness/hooks.py:242-244`). Only a determinable
  policy violation (bad stamp / unbound verdict / wrong stage) or an
  undeterminable target (R3) blocks.

Restrictions (repo principles, each cited):

- **Stdlib-only core.** No new dependency; resolution is string/`pathlib`
  work (MANIFESTO.md:197-199, "Dependency-free core"; also
  `.claude/rules/uv-installer.md`). Use `uv add` only if a dependency
  becomes unavoidable, which it should not.
- **Fail-open vs fail-safe split.** Bugs fail open, policy ambiguity
  fails safe (MANIFESTO.md:30-32; MANIFESTO.md:138-140 I8;
  MANIFESTO.md:200-202). R3 sits on the fail-safe side.
- **Surgical scope.** Every changed line traces to this defect; do not
  refactor adjacent gate logic (`CLAUDE.md` §3; MANIFESTO.md:203-205).
- **Simplicity first.** Minimum resolver that handles the two named forms
  plus a safe fallback; no speculative shell grammar (`CLAUDE.md` §2;
  MANIFESTO.md:206-207).
- **Every change ships with a test; a bug fix writes the reproducing test
  first** (`.claude/rules/python-testing.md`). Use real temp git repos
  under `tmp_path`, never mocks of the git layer (same rule,
  `dont-mock-what-you-can-run`; the existing `repo` fixture in
  `tests/conftest.py:18-27` is the model).
- **Numpy docstrings on every touched object** including the new private
  resolver (`.claude/rules/python-docstrings.md`).

## 7. Code surface

- `src/loop_harness/hooks.py:43-45` — widen `_GIT_COMMIT_RE` (or add a
  companion matcher) so `git -C <path> commit` is recognized as a gated
  commit, and update the now-false comment at lines 43-44. **Coordinate
  with the sibling ticket, which also edits this regex (§11).**
- `src/loop_harness/hooks.py` (new helper, near the other module-level
  helpers) — a private target-repo resolver, e.g. `_resolve_commit_repo(
  command: str, cwd: Path) -> Path | None`, returning the resolved
  directory or `None` when the target is undeterminable. Numpy docstring
  required.
- `src/loop_harness/hooks.py:225` — replace `repo = Path.cwd()` with a
  call to the resolver against `Path.cwd()`; on `None`, block with a
  clear fail-safe reason (R3) rather than proceeding against `cwd`. All
  downstream lookups (lines 226-241) then key off the resolved `repo`.
- `src/loop_harness/hooks.py:151-152` — leave `decide_commit_gate`'s
  matcher guard as-is unless the sibling's regex change forces a touch;
  if the matcher moves, keep this call consistent. Note the overlap; do
  not silently diverge the two match sites.
- `tests/test_hooks.py` — add the cases in §8. The existing parametrized
  `cd /repo && git commit` case at `tests/test_hooks.py:45` currently
  only asserts the *pure* policy blocks on a missing stamp; the new
  wrong-repo/bypass behavior must be exercised at the `_pre_commit_gate`
  /`hooks.main(["pre-commit-gate"])` integration level, following the
  pattern at `tests/test_hooks.py:279-297` (real repo, `monkeypatch.chdir`,
  stdin JSON payload, assert exit code).

## 8. Tests & validation gates

Gate commands (from `.loop/config.json` `gates`):

- `git add --intent-to-add -A . && uv run pytest`
- `uvx prek run --all-files`

Run both before declaring done (`.claude/rules/prek-code-quality.md`,
`.claude/rules/python-testing.md`). Review gates: the `adversarial`
(`loop-reviewer`) and `architectural` (`loop-architect`, baseline
`MANIFESTO.md`) passes in `.loop/config.json`; `require_eval: true`, so
the loop refuses pickup until the eval marker exists (see the closing
next-step).

Tests to add, all in `tests/test_hooks.py` (§7), all using real temp git
repos via the `repo` fixture / `tmp_path` and `monkeypatch.chdir`, driven
through `hooks.main(["pre-commit-gate"])` with a stdin JSON payload
(pattern at `tests/test_hooks.py:227-244` and `279-297`):

1. **Reproducing test — `cd` wrong-repo (write first).** Session `cwd` is
   a loop repo with a GREEN stamp; a *separate* target repo is loop-active
   but has NO green evidence. Command `cd <target> && git commit -m x`.
   Assert the gate blocks (exit 2) because it now evaluates the *target*'s
   (missing) evidence, not the session's green stamp. Before the fix this
   returns 0 (allowed against the wrong repo).
2. **Reproducing test — `-C` bypass (write first).** Command
   `git -C <target> commit -m x` where `<target>` is a loop repo lacking
   green evidence. Assert the gate blocks (exit 2). Before the fix
   `_GIT_COMMIT_RE` does not match and it returns 0.
3. **Undeterminable target fails safe.** A command whose target cannot be
   resolved (e.g. a form the resolver does not handle, per the §11
   resolution) with the session `cwd` a loop consumer. Assert exit 2 and a
   clear reason on stderr — fail safe, not fail open.
4. **Dormant target no-ops (R4).** `cd <target> && git commit -m x` (or
   the `-C` form) where `<target>` has no `.loop/`. Assert exit 0: a
   non-consumer target is never gated even from a consumer session.
5. **Happy path preserved.** The resolved target is a loop repo with a
   green stamp and (if mid-flight) bound verdicts; assert exit 0. Guards
   against the fix over-blocking correct commits.
6. **Internal-error fail-open preserved (R5).** Confirm an unexpected
   exception inside the resolved-repo path still returns 0 (extend or
   mirror the existing fail-open expectations). Keep this distinct from
   the fail-safe block in test 3.

## 9. Risk assessment

- **Blast radius.** One hook (`_pre_commit_gate`) and one shared regex.
  The regex is the sensitive surface: widening it to catch `-C` must not
  start matching non-commit commands, and it overlaps the sibling ticket.
  The pure `decide_commit_gate` policy and all other hooks are untouched.
- **Reversibility.** High. The change is contained to command parsing and
  repo resolution; reverting restores the prior (buggy) behavior with no
  state migration.
- **Likeliest failure modes.**
  (a) *Over-blocking* — a too-aggressive "undeterminable" fallback blocks
  legitimate commits and wedges the loop. Mitigated by test 5 and a
  narrow resolver; the §11 fork decides how wide "undeterminable" is.
  (b) *Under-resolving* — a `cd` with a quoted/relative path or trailing
  args resolves wrong, gating the wrong repo again. Mitigated by tests 1
  and 4 exercising relative-path resolution against `cwd`.
  (c) *Sibling collision* — both tickets edit `_GIT_COMMIT_RE`; a
  careless merge reintroduces one defect while fixing the other. Mitigated
  by the §11 coordination note and rebasing whichever lands second.
  (d) *Fail-open/fail-safe inversion* — treating an undeterminable target
  as an internal error (fail open) instead of a policy ambiguity (fail
  safe) silently reopens the hole. Mitigated by tests 3 and 6 asserting
  the two paths independently.

## 10. Subtickets

Ordered, dependency-aware:

1. **Reproducing tests first.** Add tests 1 and 2 (§8) and watch them
   fail against current `main` — proves the defect and the wrong-repo /
   bypass mechanics.
2. **Target-repo resolver.** Add `_resolve_commit_repo(command, cwd)`
   handling the `cd <path> &&` prefix and `git -C <path> commit` form,
   returning `None` when undeterminable. Numpy docstring. Unit-cover the
   resolver directly (parametrized) plus the fail-safe `None` path.
3. **Widen command detection.** Update `_GIT_COMMIT_RE` (or add a
   companion) so `-C` commits are recognized, and fix the stale comment
   at lines 43-44. Reconcile with the sibling ticket per §11.
4. **Wire the resolver into `_pre_commit_gate`.** Replace `Path.cwd()` at
   line 225; block on `None` (fail safe); key all downstream lookups off
   the resolved repo. Make tests 1-2 pass; add tests 3-6.
5. **Run gates** (§8) and the two review passes.

## 11. Open questions

1. **[Primary fork — the operator decision this ticket exists to
   surface] How wide is "undeterminable target → fail safe block"?** When
   the resolver cannot pin the target (multiple `cd`s, `;`/`||`/subshell
   chaining, `pushd`, a variable-expanded path like `cd $DIR`,
   command-substitution), the safe reading of the fail-safe/fail-open
   split (MANIFESTO.md:30-32, I8) is to **block** with a clear reason.
   But blocking every unparseable-but-real commit could wedge legitimate
   workflows.
   *Recommendation:* block (exit 2) with an explicit, actionable message
   ("loop gate: cannot determine the commit's target repo from
   `<command>`; run the commit as a bare `git commit` in the target repo,
   or engage HALT") **only when the session `cwd` is itself loop-active**
   — i.e. when there is a gated repo that the commit could plausibly be
   escaping. If `cwd` is dormant and the target is unresolvable, there is
   no consumer to protect, so no-op (allow). This keeps fail-safe scoped
   to actual consumers and avoids gating unrelated repos, consistent with
   dormancy (R4). Confirm this scoping before implementation.

2. **Should the `-C` detection also cover `git --git-dir=`/`--work-tree=`
   forms?** These are rarer ways to commit elsewhere. *Recommendation:*
   out of scope for this ticket (simplicity first); if pinned to
   handling, treat an unhandled `--git-dir`/`--work-tree` as
   *undeterminable* (fail safe per Q1) rather than silently gating `cwd`.
   Flagging so the operator can widen scope deliberately rather than
   discovering a third bypass later.

3. **Merge order with `commit-gate-false-positive-on-strings`.** Both
   edit `_GIT_COMMIT_RE`. *Recommendation:* land this target-resolution
   ticket independently of order, but whichever lands second rebases onto
   the first and re-runs both suites, since the sibling narrows the regex
   (to stop string false positives) while this one widens it (to catch
   `-C`). The end state must be a single matcher that catches `git
   commit` and `git -C <path> commit` in real command position while
   ignoring occurrences inside string data. Confirm whether the operator
   wants the two matchers unified in one ticket instead; default is to
   keep them separate and rebase.
