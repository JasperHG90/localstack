# Architectural review (cycle 2) — commit-gate-false-positive-on-strings

verdict: pass
tree: cff704c4e93b950acf4b65e4392fd8842e773c1d

pass id: architectural
baseline: MANIFESTO.md

## Scope reviewed

`src/loop_harness/hooks.py` (the `_invokes_git_commit` helper, now matching
on adjacent token pairs via `itertools.pairwise`; `_SEQUENCING_RE`;
`import shlex`; `_GIT_COMMIT_RE` demoted to a documented parse-failure
fallback; two call-site swaps) and `tests/test_hooks.py`. Judged against the
MANIFESTO's architecture (§2), invariants (§3), and values (§4), plus the
accepted DoD in `.loop/evals/commit-gate-false-positive-on-strings.md`.

Fingerprint independently reproduced: `git read-tree HEAD` + `git add -A`
over a throwaway index with `.loop` stripped (per I6, MANIFESTO.md:124-129)
yields `cff704c4e93b950acf4b65e4392fd8842e773c1d`, matching the briefing.
This verdict is bound to that tree.

## What changed since cycle 1

Prior finding F1 (I7 erosion — a real commit behind a `VAR=value` / `sudo` /
`env` prefix escaped the gate) is fixed. Prior F2 (document the accepted
subshell/eval boundary) and the architect-noted F3 (over-gating on operators
inside quotes) are now documented as accepted safe-direction boundaries in
the helper docstring.

## Invariant / value checks

### I7 — commit gate refuses commits without earned evidence (MANIFESTO.md:131-136) — RESTORED
The prior escape is closed. `_invokes_git_commit` (hooks.py:69) now returns
True when ANY adjacent token pair is `git` then `commit` via
`itertools.pairwise` (hooks.py:118-119), instead of only inspecting the
first two tokens. Real invocations behind a leading assignment or wrapper
now gate again:
- `FOO=bar git commit`, `GIT_COMMITTER_DATE=2020 git commit --amend`,
  `sudo git commit`, `env GIT_AUTHOR_NAME=x git commit` — pinned True at
  tests/test_hooks.py:73-77, with `GIT_COMMITTER_DATE=2020 git commit`
  pinned as blocked at tests/test_hooks.py:92.
- Direct, compound, and operator-glued forms still gate: `git commit`,
  `git add -A && git commit -m 'y'`, `git add&&git commit -m 'z'`
  (tests/test_hooks.py:63-67).
The enforcer `decide_commit_gate` still requires a green stamp and
tree-bound verdicts for every command detected as a commit
(hooks.py:213-214 onward). No real-commit escape remains among the direct
invocation forms I7 is anchored to. I7 holds.

### §4 Dependency-free core (MANIFESTO.md:197-199) — HELD
New imports are `shlex` (hooks.py:31) and `itertools.pairwise`
(hooks.py:34); `re` was already present. All stdlib. No third-party parser.
Ticket R4 and the eval marker's stdlib-only guardrail row satisfied.

### I3-style single definition of the commit predicate (MANIFESTO.md:105-110; ticket §7) — HELD
Both call sites share one predicate: the policy gate at hooks.py:213 (inside
`decide_commit_gate`) and the fast-path pre-filter at hooks.py:285 (inside
`_pre_commit_gate`) both call `_invokes_git_commit`. `_GIT_COMMIT_RE` is now
referenced only from inside that helper (hooks.py:113). No fast-path /
policy drift.

### §1 fail-safe vs fail-open split (MANIFESTO.md:30-32) + I8 (MANIFESTO.md:138-143) — RESPECTED
The `shlex.split` `ValueError` on unbalanced quotes is caught inside the
helper (hooks.py:112-116) and falls back to the substring regex, returning
True when it matches, so `decide_commit_gate` stays a total pure function
and a malformed-but-committing command still gates (`git commit -m "oops`
pinned True at tests/test_hooks.py:69 and blocked at :91). Had the raise
propagated, the outer wrapper (hooks.py behavioral value, MANIFESTO.md:
200-203) would fail OPEN and let it through, contradicting the gate's
fail-SAFE stance. The direction is correct: bugs fail open, policy fails
safe. R5 satisfied.

### Over-gate boundary — sound documented choice, not a hidden invariant risk
The docstring (hooks.py:82-93) documents the accepted boundary: adjacency
favors safety over precision, `echo git commit` over-gates rather than risk
a miss (tests/test_hooks.py:78), and the unmodeled constructs — subshells
`$(...)`, `eval`, backgrounding, heredoc bodies, and operators inside quotes
— are named out of scope (ticket §5, §11). Over-gating blocks a harmless
non-commit command: the fail-SAFE direction, consistent with §1 and I8.
Disclosed in code and traced to ticket scope, so it is a chosen boundary,
not a concealed erosion. Prior F2 and F3 are addressed here.

### §4 Surgical scope (MANIFESTO.md:204-206) — HELD
Every changed line traces to the detector swap: one helper, two call-site
swaps, the regex demotion, and tests. No unrelated refactor. I1, I2,
I4-I6, I9-I15 untouched.

## Baseline-silent observation (not a violation)

Residual detection under-gate on unmodeled shell constructs
(`$(git commit)`, `eval "git commit"`, heredoc bodies): the old substring
regex caught these, the token-aware detector does not, because `shlex`
collapses a quoted `"git commit"` into one token and command substitution
splits `$(git` / `commit)`. MANIFESTO is SILENT on shell-parsing fidelity
for these forms, and the helper docstring plus ticket §5/§11 declare them
out of scope. I raise no invariant rule here — the baseline anchors none —
but flag it so the operator knows the boundary persists by design, owned by
scope rather than by accident. These are not the direct-invocation forms an
agent normally uses to commit, so the practical I7 surface is intact.

## Verdict rationale

The architectural shape is sound and cycle-1's blocking finding is resolved:
I7 parity is restored for env-prefixed and `env`/`sudo`-wrapped real
commits, the core stays stdlib-only, both call sites share one predicate
with no drift, the Q1 fallback keeps the pure gate function total in the
fail-safe direction, and the over-gate boundary is now a documented,
sound architectural choice rather than a hidden invariant risk. No
architectural violation remains.

verdict: pass
tree: cff704c4e93b950acf4b65e4392fd8842e773c1d
