# commit-gate-git-hook-backstop

## 1. Title

Add a git-level `pre-commit` backstop that runs the same
`decide_commit_gate` policy, so git itself refuses any commit lacking
green tree-bound evidence regardless of how the commit is spelled or who
issues it, closing the classes no Bash-string matcher can reach.

## 2. Size / Effort

**L.** A new install/uninstall surface that reaches into the consumer's
`.git/` (sensitive), a new hook entry point that reuses the existing pure
policy, a generated bootstrap script that must locate `loop_harness`
without `${CLAUDE_PLUGIN_ROOT}`, and integration tests that drive real
`git commit` through the installed hook in real temp repos. Effort is
driven by the co-existence and lifecycle decisions (not clobbering an
existing hook or `core.hooksPath`) and by getting the fail-open vs
fail-safe split exactly right at a second enforcement point, not by line
count.

## 3. Triggered by

An accepted, documented gap in the commit gate. The gate is a Claude Code
`PreToolUse` hook that pattern-matches `git commit` in the Bash tool's
command string (`hooks/hooks.json:14-24`, `hooks.py` `_invokes_git_commit`
at `src/loop_harness/hooks.py:127`, `decide_commit_gate` at
`src/loop_harness/hooks.py:285`, `_pre_commit_gate` at
`src/loop_harness/hooks.py:386`). It can only see a commit that (a) goes
through the Bash tool AND (b) surfaces as a matchable string. It
structurally cannot catch three classes, each recorded as an accepted
out-of-scope under-gate in the sibling verdicts
(`.loop/verdicts/commit-gate-false-positive-on-strings.architectural.md:77-79,92-97`;
`.loop/plans/commit-gate-false-positive-on-strings.md:229-230`):

1. Command-substitution / eval / wrapped forms: `$(git commit ...)`,
   `eval "git commit ..."`, `bash -c "git commit ..."`. `shlex` collapses
   the quoted body to one token, so the token-aware matcher never sees a
   `git` token followed by a `commit` subcommand.
2. A python/node subprocess that shells out to git, never surfacing a
   matchable Bash command string at all.
3. A human committing from their own terminal in the same repo, which
   never passes through a Claude Code hook.

There is currently NO git-level hook: no `.git/hooks/pre-commit` is
installed and `core.hooksPath` is unset (verified in this repo).

## 4. Context

Today's state, cited to code:

- `src/loop_harness/hooks.py:285-354` — `decide_commit_gate`, the PURE
  policy. It first guards on `_invokes_git_commit(command)` at
  `src/loop_harness/hooks.py:319`, then bypasses on an engaged HALT
  (`src/loop_harness/hooks.py:321-325`), then requires a green stamp
  (`src/loop_harness/hooks.py:326-333`) and, for every mid-flight ticket,
  a committable stage with tree-bound verdicts via `validate_transition`
  (`src/loop_harness/hooks.py:334-352`). This is the single policy the git
  hook must reuse so the two enforcement points cannot drift.
- `src/loop_harness/hooks.py:386-433` — `_pre_commit_gate`, the existing
  PreToolUse entry. Its evidence-assembly block at
  `src/loop_harness/hooks.py:411-424` (`load_ledger`, filter `active`,
  `enabled_passes_failsafe`, `fingerprint_ignore_failsafe`,
  `verify_stamp`, `pass_verdict_tree`, `tree_fingerprint`) is exactly the
  evidence the git-hook entry must also assemble — but keyed off the
  committed repo's own root, which the git hook gets for free (see below).
- `src/loop_harness/hooks.py:229-235` — `loop_active(repo)`, the dormancy
  switch: a repo without `.loop/` no-ops.
- `src/loop_harness/hooks.py:357-369` / `:372-383` —
  `enabled_passes_failsafe` and `fingerprint_ignore_failsafe`: the config
  fail-safe helpers to reuse verbatim.
- `src/loop_harness/hooks.py:425-427` — the outer `except` that makes
  `_pre_commit_gate` fail OPEN (return 0) on any internal error. The
  module docstring at `src/loop_harness/hooks.py:3-6` states this contract;
  MANIFESTO.md:200-203 names it a value ("Hooks fail open on internal
  error"), the deliberate counterpart to fail-safe (MANIFESTO.md:30-32,
  I8 at MANIFESTO.md:138-142).
- `src/loop_harness/hooks.py:547-560` — `main()` dispatches hook entries by
  name (`session-start`, `pre-commit-gate`, `stop-check`, `state-guard`).
  A git-hook entry needs a dispatch path here or in a new module.
- `src/loop_harness/halt.py:21-30` — `engaged(repo)`: the HALT read the git
  hook must consult so `.loop/HALT` steps it aside exactly as it bypasses
  the PreToolUse gate (`src/loop_harness/hooks.py:321-325`).
- `scripts/run_hook.py` — the model for a stdlib-only bootstrap that
  prepends the plugin `src/` to `sys.path` and dispatches. Crucially it
  uses `${CLAUDE_PLUGIN_ROOT}` from `hooks/hooks.json`; a git hook has NO
  such environment, so the generated hook must bake the plugin path in at
  install time (see §7, §9).
- `src/loop_harness/cli.py:112-120` — `cmd_init` (scaffolds
  `.loop/config.json` via `config.write_example_config` at
  `src/loop_harness/config.py:379-394`); `src/loop_harness/cli.py:126-160`
  — the `loopctl` subparser table and dispatch, where an install/uninstall
  command (or a hook into `init`) would wire in.

What is missing: a second, un-bypassable enforcement point at the git
layer. The git `pre-commit` hook runs with cwd = the committed repo, so it
naturally evaluates the correct repository — unlike the PreToolUse hook,
which reads the session cwd (the very bug the sibling ticket
`commit-gate-targets-the-committed-repo` fixes). It also receives no
command string and no arguments, so it does not and cannot rely on the
string matcher at all.

**Relationship to the in-flight sibling
`commit-gate-targets-the-committed-repo`** (currently in
adversarial-review; its implementation is the uncommitted diff on
`hooks.py`/`test_hooks.py`, verdicts written at
`.loop/verdicts/commit-gate-targets-the-committed-repo.*`). That ticket
fixes the *matcher* and *repo resolution* for `git -C <path> commit` and
`cd <path> && git commit`. This ticket is COMPLEMENTARY, not a duplicate:
no string matcher, however good, can catch the three classes in §3 that
never surface as a matchable Bash tool string. The two tickets share only
`decide_commit_gate`, which the sibling deliberately keeps as a pure
function over already-resolved evidence — this ticket reuses it unchanged.
See §11 for sequencing.

## 5. Non-goals / out of scope

- **Removing or weakening the PreToolUse gate.** It stays as the fast,
  friendly early-block (good UX message, blocks before the command runs).
  This ticket adds a backstop; it does not replace the front-line gate.
- **Touching the string matcher (`_invokes_git_commit`,
  `_GIT_COMMIT_RE`, `_resolve_commit_repo`).** The git hook has no command
  string; it does not use them. Leave them to the sibling ticket. Do not
  re-touch the matcher lines.
- **Changing `decide_commit_gate`'s signature or policy.** Reuse it as-is.
  Any policy change would be a separate ticket.
- **A general git-hooks framework.** Install exactly one `pre-commit`
  backstop. No `pre-push`, `commit-msg`, or other hooks; no configurable
  hook set.
- **Auto-installing into unrelated repos.** Dormancy holds: the installed
  hook must no-op in a repo without `.loop/`, and installation itself is
  an explicit, scoped action on a consumer repo (see §11 Q1).
- **Rewriting a consumer's existing `pre-commit` hook or hijacking an
  existing `core.hooksPath`.** Co-existence strategy is decided in §11 Q2,
  but silently clobbering is out of scope in every reading.

## 6. Requirements & restrictions

Requirements:

- **R1. Git-level enforcement.** Provide a git `pre-commit` hook that, when
  a commit is attempted in a loop-consumer repo, evaluates the SAME
  `decide_commit_gate` policy against that repo's evidence and blocks
  (non-zero exit) when the tree lacks a green stamp and every enabled
  pass's tree-bound verdict, exactly as the PreToolUse gate does. This
  strengthens invariant I7 (MANIFESTO.md:131-136, "The commit gate refuses
  commits without earned evidence") by adding an actor- and
  spelling-independent enforcement point git cannot route around.
- **R2. Single policy, no drift.** The git-hook entry reuses
  `decide_commit_gate` (`src/loop_harness/hooks.py:285`) and the config
  fail-safe helpers (`enabled_passes_failsafe`,
  `fingerprint_ignore_failsafe`, `src/loop_harness/hooks.py:357-383`);
  it does not reimplement the evidence rules. Because the hook has no
  command string, it must satisfy `decide_commit_gate`'s
  `_invokes_git_commit` guard deliberately (see §11 Q5 for the two ways).
- **R3. HALT bypass parity.** An engaged `.loop/HALT` steps the git hook
  aside (allow), mirroring the PreToolUse bypass at
  `src/loop_harness/hooks.py:321-325` and `halt.engaged`
  (`src/loop_harness/halt.py:21-30`). When HALT is engaged the operator is
  in control at BOTH enforcement points.
- **R4. Dormancy.** In a repo without `.loop/` the installed hook no-ops
  (allow), via `loop_active` (`src/loop_harness/hooks.py:229-235`). A
  consumer who later removes `.loop/` is not wedged by a stale hook.
- **R5. Fail-open vs fail-safe split, preserved at the second point.** A
  genuine no-evidence state fails SAFE (block); an INTERNAL hook error
  (a harness bug, an unreadable file, a `loop_harness` import failure)
  fails OPEN (allow), so the backstop can never wedge a user's commits over
  a harness defect. This is the same split the PreToolUse hook honors
  (`src/loop_harness/hooks.py:425-427`; module docstring
  `src/loop_harness/hooks.py:3-6`) and the manifesto's stated rule
  (MANIFESTO.md:30-32; fail-open value MANIFESTO.md:200-203; fail-safe I8
  MANIFESTO.md:138-142).
- **R6. Non-destructive install.** Installation MUST NOT clobber an
  existing `pre-commit` hook or an existing `core.hooksPath`. The
  co-existence strategy (detect-and-chain, or refuse-and-warn) is an
  operator decision (§11 Q2); whichever is chosen, an unmanaged existing
  hook is never silently destroyed.
- **R7. Uninstall / lifecycle.** The operator can remove the backstop, and
  removal restores any pre-existing hook the install displaced or chained
  (§11 Q4). Install is idempotent (re-running does not stack duplicates).

Restrictions (repo principles, each cited):

- **Stdlib-only core.** No new dependency; install, the generated
  bootstrap, and the entry point are `pathlib`/`subprocess`/string work
  (MANIFESTO.md:34-37 and MANIFESTO.md:197-199, "Dependency-free core";
  `.claude/rules/uv-installer.md`). If a dependency somehow becomes
  unavoidable, add it with `uv add`, not `uv pip`.
- **No silent judgment calls.** Every fork in §11 that the request, this
  repo, or `DECISIONS.md` does not settle is surfaced for the operator, and
  a genuinely unresolved one is a `blocked` state with a coded reason, not
  a guess (MANIFESTO.md:27-29; "the operator owns decisions"
  MANIFESTO.md:216-218). A plugin reaching into a user's `.git/` is exactly
  the kind of choice that belongs to the operator, and any load-bearing
  decision that lands should be recorded in the harness's own `DECISIONS.md`.
- **Surgical scope.** Every changed line traces to this backstop; do not
  refactor the existing gate, matcher, or `_pre_commit_gate` beyond what
  R2 reuse requires (`CLAUDE.md` §3; MANIFESTO.md:204-205).
- **Simplicity first.** The minimum that installs one hook, reuses the
  policy, and co-exists safely; no speculative hooks-framework
  configurability (`CLAUDE.md` §2; MANIFESTO.md:206-207).
- **Tests and docstrings ship with the code.** Every touched Python
  object carries a numpy-style docstring
  (`.claude/rules/python-docstrings.md`); every change ships a test, and a
  behavior gap is proven by a test first (`.claude/rules/python-testing.md`;
  MANIFESTO.md:209-211).
- **Never mock git.** Tests use real temp git repos under `tmp_path` and
  drive real `git commit` through the installed hook, per the existing
  `repo` fixture at `tests/conftest.py:18-27`
  (`.claude/rules/python-testing.md`, `dont-mock-what-you-can-run`).

## 7. Code surface

The exact files and anchors this change touches, each with the change:

- `src/loop_harness/githook.py` (NEW module) — the git-backstop surface,
  stdlib-only, numpy docstrings on every object:
  - `install(repo)` — write the managed `pre-commit` hook (or the
    `core.hooksPath` directory entry, per §11 Q3), non-destructively per
    R6, idempotently per R7, baking in the absolute plugin path the
    generated script needs to locate `loop_harness` (there is no
    `${CLAUDE_PLUGIN_ROOT}` at git-hook time; the plugin root is
    `Path(__file__).resolve().parents[2]`, the same anchor `run_hook.py`
    reaches via `sys.path`).
  - `uninstall(repo)` — remove the managed hook and restore any displaced
    hook (R7).
  - The `pre-commit` entry function — assemble evidence for `repo =
    Path.cwd()` (git runs the hook in the committed repo root) by mirroring
    the block at `src/loop_harness/hooks.py:411-424`, consult
    `halt.engaged` (R3) and `loop_active` (R4), call `decide_commit_gate`
    (R2), and translate its `GateDecision` to a git exit code (0 allow,
    non-zero block). Wrap the body so an internal error fails OPEN (R5),
    matching `src/loop_harness/hooks.py:425-427`.
  - Reuse `enabled_passes_failsafe` / `fingerprint_ignore_failsafe` /
    `pass_verdict_tree` from `hooks.py` (`src/loop_harness/hooks.py:357-383`,
    `:272-282`) rather than duplicating config fail-safe logic.
  - *(If the operator's §11 Q5 answer is "extract a shared evidence-check
    core", that refactor lands in `hooks.py` and both entries call it;
    default is to pass a canonical `"git commit"` command into the
    unchanged `decide_commit_gate` so its `_invokes_git_commit` guard is
    satisfied without any hooks.py edit.)*
- `scripts/run_git_hook.py` OR the generated hook body (NEW) — the
  stdlib-only shim git executes, modeled on `scripts/run_hook.py`:
  bootstrap `sys.path` to the baked-in plugin `src/`, import the entry, and
  fail OPEN loudly on an import error (mirroring `run_hook.py`'s
  `except (ImportError, AttributeError)` block that exits 0 with a stderr
  note). This is what `install()` writes into (or points `core.hooksPath`
  at).
- `src/loop_harness/cli.py:126-160` — register the operator-facing
  command(s) in the `loopctl` subparser table and dispatch: per §11 Q1,
  either an explicit `loopctl install-git-hook` / `uninstall-git-hook`
  pair, and/or wiring `install()` into `cmd_init`
  (`src/loop_harness/cli.py:112-120`). Add the `cmd_*` handler(s)
  alongside the existing ones.
- `src/loop_harness/hooks.py:547-560` — ONLY if §11 Q5 resolves to a new
  named hook entry rather than a self-contained `githook.py` entry: add the
  dispatch choice to `main()`. Default keeps the entry in `githook.py` and
  leaves `hooks.main` untouched.
- `tests/test_githook.py` (NEW) — all tests from §8 live here (they drive
  install + real `git commit`, distinct from the PreToolUse tests in
  `tests/test_hooks.py`). Use the `repo` fixture from
  `tests/conftest.py:18-27` and `git()` helper; add local fixtures for a
  second repo and a pre-existing-hook repo as needed.

Note: `hooks/hooks.json:14-24` (the PreToolUse wiring) is unchanged — the
git hook is installed into `.git/`, not declared in the plugin manifest.

## 8. Tests & validation gates

Gate commands (from `.loop/config.json` `gates`), run both before
declaring done (`.claude/rules/prek-code-quality.md`,
`.claude/rules/python-testing.md`):

- `git add --intent-to-add -A . && uv run pytest`
- `uvx prek run --all-files`

Review gates (from `.loop/config.json` `review_passes`): the `adversarial`
pass (`loop-reviewer`) and the `architectural` pass (`loop-architect`,
baseline `MANIFESTO.md`). `require_eval: true`, so the loop refuses pickup
until a schema-valid eval marker
(`.loop/evals/commit-gate-git-hook-backstop.md`) exists (I14,
MANIFESTO.md:178-182) — see the closing next-step.

Tests to add, all in `tests/test_githook.py` (§7), all using real temp git
repos and driving a real `git commit` through the INSTALLED hook (no git
mocking). Because the backstop's whole value is catching what the string
matcher cannot, several tests deliberately commit via forms the PreToolUse
hook would miss:

1. **Backstop-proves-the-gap tests (write first).** In a loop-consumer
   repo with NO green stamp, install the hook, then attempt a commit and
   assert git itself rejects it (non-zero, reason on stderr) for each of:
   (a) a plain `git commit`; (b) `git -C <repo> commit` issued from
   elsewhere; (c) a commit inside command substitution or a subprocess
   (e.g. `python -c "subprocess.run(['git','commit',...])"`). These are the
   §3 classes; before this ticket nothing blocks them.
2. **Green evidence passes.** Same repo with a green stamp and (mid-flight)
   tree-bound verdicts bound to the current tree; assert `git commit`
   succeeds through the installed hook. Guards against over-blocking.
3. **HALT steps the git hook aside (R3).** With `.loop/HALT` engaged and no
   green evidence, assert the commit succeeds — the git hook allows,
   mirroring the PreToolUse bypass.
4. **Dormant repo no-ops (R4).** Install, then remove `.loop/` (or install
   never ran there); assert an ordinary commit is unaffected.
5. **Internal error fails OPEN (R5).** Force an internal failure in the
   entry's evidence path (e.g. an unreadable/corrupt loop state or a
   monkeypatched raise) and assert the commit is ALLOWED, not wedged —
   kept distinct from the fail-safe block in test 1.
6. **Non-destructive install + uninstall (R6, R7).** Installing over a repo
   that already has a `pre-commit` hook (or a set `core.hooksPath`) honors
   the §11 Q2 strategy: either the pre-existing hook still runs
   (detect-and-chain) or install refuses with a clear warning
   (refuse-and-warn); assert the pre-existing hook is never silently lost.
   Assert `uninstall` restores the prior state and that re-running
   `install` is idempotent (no duplicate/stacked hook).

## 9. Risk assessment

- **Blast radius.** Writing into the consumer's `.git/` is the sensitive
  surface: an over-eager install could disable or overwrite a user's own
  hooks or hijack `core.hooksPath` (which, once set, disables the default
  `.git/hooks` entirely). Contained to the new `githook.py`, the generated
  shim, and the `loopctl` wiring; `decide_commit_gate`, the matcher, and
  the PreToolUse hook are untouched.
- **Reversibility.** Moderate. Code is contained and revertible, but a
  botched install leaves state IN THE USER'S REPO (`.git/hooks/pre-commit`
  or `core.hooksPath`). Uninstall (R7) and non-destructive install (R6)
  are the mitigations; test 6 guards them.
- **Likeliest failure modes.**
  (a) *Clobbering* — silently replacing a user's `pre-commit` or
  `core.hooksPath`. Mitigated by R6 and test 6; the §11 Q2 fork decides the
  strategy.
  (b) *Wedging commits* — treating an internal error (or an import failure
  because the baked-in plugin path moved) as a policy block, freezing the
  user's ability to commit. Mitigated by R5, the loud fail-open shim
  (modeled on `run_hook.py`), and test 5. A plugin that CAN block every
  commit must fail open on its own bugs or it becomes the outage.
  (c) *Policy drift* — reimplementing the evidence rules in the git entry
  so the two gates disagree. Mitigated by R2 (reuse `decide_commit_gate`)
  and by tests 1-2 asserting identical allow/block outcomes.
  (d) *Path fragility* — the generated hook bakes an absolute plugin path;
  moving or reinstalling the plugin breaks the import. Mitigated by the
  fail-open-loud shim (a broken import allows the commit with a stderr
  note, never blocks) and, if chosen, re-running install after a move.
  (e) *Sibling churn* — needlessly re-touching matcher lines the sibling
  owns. Mitigated by §5 (do not touch the matcher) and the §11 sequencing.

## 10. Subtickets

Ordered, dependency-aware:

1. **Land after the sibling (or rebase onto it).** Confirm
   `commit-gate-targets-the-committed-repo` has merged, or rebase onto it,
   so `decide_commit_gate` is stable before reusing it (§11 Q6).
2. **Resolve the §11 forks with the operator** (install trigger,
   co-existence, hooksPath vs `.git/hooks`, uninstall, policy-reuse
   mechanism). Record the load-bearing choices in `DECISIONS.md`.
3. **Backstop-proves-the-gap tests first.** Add test 1 (§8) and watch it
   fail (nothing blocks the §3 forms today) — proves the gap and the
   backstop mechanics.
4. **Git-hook entry.** Implement the `pre-commit` entry in `githook.py`:
   assemble evidence keyed to the committed repo, reuse
   `decide_commit_gate`, honor HALT (R3), dormancy (R4), and the fail-open
   wrapper (R5). Make test 1 pass; add tests 2-5.
5. **Install / uninstall + shim.** Implement non-destructive, idempotent
   `install`/`uninstall` per the resolved co-existence strategy, and the
   fail-open-loud bootstrap shim. Add test 6.
6. **Operator surface.** Wire the resolved `loopctl` command(s) and/or
   `cmd_init` hook in `cli.py`.
7. **Run gates** (§8) and both review passes.

## 11. Open questions

Each fork the request, repo, or `DECISIONS.md` leaves open, with a
recommendation. Load-bearing answers should be recorded in `DECISIONS.md`
(the harness's own decision record).

1. **[Primary fork] Install trigger.** Automatic on `loopctl init` vs an
   explicit `loopctl install-git-hook` command vs an opt-in config flag. A
   plugin writing into a user's `.git/` on init is surprising and hard to
   audit. *Recommendation:* an explicit `loopctl install-git-hook`
   (with matching `uninstall-git-hook`), printed in the SessionStart
   guidance, so installation is a deliberate, visible, reversible operator
   act — not a side effect of scaffolding a config. Keep `cmd_init`
   config-only. Confirm before implementation.
2. **Co-existence with an existing hook / hooksPath.** MUST NOT clobber
   (R6), but detect-and-chain (run the existing hook, then ours) vs
   refuse-and-warn (do nothing, tell the operator to resolve it) is a real
   choice. *Recommendation:* refuse-and-warn for a pre-existing unmanaged
   `pre-commit` or a set `core.hooksPath` on first cut (simplicity, no
   fragile hook-chaining shim, no risk of mis-ordering someone's
   formatter); document that the operator can chain manually. Revisit
   chaining only if a consumer needs it. Confirm.
3. **`core.hooksPath` vs `.git/hooks/pre-commit`.** The request prefers a
   harness-managed `core.hooksPath` dir. But setting `core.hooksPath`
   DISABLES the default `.git/hooks` entirely (a bigger footprint and a
   sharper co-existence hazard with Q2), while a single
   `.git/hooks/pre-commit` file is more surgical but does not survive some
   worktree/submodule layouts. *Recommendation:* install a single managed
   `.git/hooks/pre-commit` (surgical, easy to detect/uninstall, least
   surprising), and treat a set `core.hooksPath` as the refuse-and-warn
   case from Q2. Confirm; if the operator wants `core.hooksPath`, R6/R7 and
   test 6 must cover restoring the prior value.
4. **Uninstall / lifecycle.** How the operator removes it and what state is
   restored. *Recommendation:* `loopctl uninstall-git-hook` removes only
   the managed hook, restores any displaced hook (only reachable if Q2
   later grows chaining), and is a no-op when nothing managed is present.
   Confirm the command name and that removal never touches an unmanaged
   hook.
5. **How the git entry satisfies `decide_commit_gate`'s command guard.**
   The hook has no command string, but `decide_commit_gate` returns
   `allow=True` immediately unless `_invokes_git_commit(command)` fires
   (`src/loop_harness/hooks.py:319-320`). Option A: pass a canonical
   `"git commit"` string so the guard fires — zero change to `hooks.py`,
   maximal reuse. Option B: extract the post-guard evidence logic
   (`src/loop_harness/hooks.py:321-354`) into a shared helper both entries
   call. *Recommendation:* Option A (no `hooks.py` edit, no divergence
   surface, aligns with "reuse the single policy function"). Flag Option B
   only if the operator wants the guard responsibility split out. Confirm.
6. **Sequencing vs the in-flight sibling.** `decide_commit_gate` is shared;
   the sibling `commit-gate-targets-the-committed-repo` is in
   adversarial-review. *Recommendation:* land this ticket AFTER the
   sibling merges (or rebase onto it), so the reused policy is stable and
   no matcher lines are churned twice. The coupling is small (the git hook
   never touches the matcher), so this is ordering hygiene, not a hard
   dependency. Confirm the operator wants them kept separate rather than
   folded.
