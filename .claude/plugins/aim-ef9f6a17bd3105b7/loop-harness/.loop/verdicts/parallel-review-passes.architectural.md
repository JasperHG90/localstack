verdict: pass
tree: 2a680c7ad39df5099cf2b9dcad51437c5deb9cf4

# Architectural review: parallel-review-passes

Baseline: `MANIFESTO.md` (repo root). Scope reviewed: `git diff
skills/implement-ticket/SKILL.md` (driver prose only; no Python changed).
Independently confirmed: `python3 scripts/loopctl.py verify` -> `ok`, and
`tree_fingerprint(cwd)` == `2a680c7ad39df5099cf2b9dcad51437c5deb9cf4`
(matches the briefing).

## Verdict rationale

The change fans out the enabled review passes concurrently, captures ONE
shared tree fingerprint, joins on all verdicts before deciding, and re-runs
ALL passes on any finding. It touches only `skills/implement-ticket/
SKILL.md`. It respects every architectural rule the manifesto states and
introduces no new cross-boundary dependency, no relocated responsibility,
and no broken invariant anchor. Pass.

## Findings

### F1. Driver/harness boundary preserved (informational, no action)

MANIFESTO §2 draws the load-bearing boundary: "Skills and agents
(`skills/`, `agents/`) are the behavioral layer the model runs; the Python
core is the layer that verifies what the model did." The diff lives
entirely in the behavioral layer (`skills/implement-ticket/SKILL.md:67-92,
137-140`). No verification moved into the driver: the commit gate
(`hooks.py: decide_commit_gate`, I7) and the commit entry criterion
(`lifecycle.py`, I2) are unchanged and remain the sole arbiters of
validity. Concurrency is a dispatch property of the driver; the gate reads
verdict files as an unordered set and does not observe dispatch order or
timing. Boundary upheld.

### F2. I2 / I3 / I4 preserved under fan-out (informational)

- I2 ("a commit needs a green stamp AND every enabled pass's tree-bound
  verdict"): the rewrite keeps "the commit gate requires a passing,
  tree-bound verdict from EVERY enabled pass" (`SKILL.md:82-83`) and each
  agent still "writes its OWN verdict file, including the `tree:` line the
  commit gate parses" (`SKILL.md:80-81`). Fan-out changes when passes run,
  not what each must produce. The evidence-over-claims invariant (§1) is not
  weakened; the gate is the enforcer and is untouched.
- I3 ("the tree fingerprint is defined once; every reader calls that one
  function"): capturing ONE shared `T` and binding all passes to it is
  strictly more aligned with I3 than the prior model where each reviewer
  re-derived its own fingerprint. The single-`T` capture removes the
  divergent-fingerprint hazard the ticket names as its main failure mode.
- I4 ("a stamp goes stale the moment the tree changes"): the driver
  confirms `loopctl verify` is OK before reading `T` (`SKILL.md:68-72`), and
  the findings loop re-stamps and re-captures a fresh `T` before re-running
  (`SKILL.md:86-91`). Consistent with I4.

### F3. Reading `.loop/stamp.json` from the driver is within the boundary (informational)

MANIFESTO §2 lists `stamp.json` as "harness-written only", and I10 blocks
Edit/Write to it (`hooks.py: decide_state_guard`). The driver only READS the
`tree` field (`SKILL.md:69-70`); it does not write it. The written value is
`tree_fingerprint(repo)` itself (`stamp.py: write_stamp` payload `"tree":
tree_fingerprint(repo)`), so the value the driver consumes is the exact
output of the single fingerprint function I3 mandates, validated to equal
the current tree by the mandatory `loopctl verify` (I4) that precedes the
read. The manifesto is SILENT on drivers reading harness-written state; the
harness-written-only rule governs writes, not reads, so this is not a
violation. The ticket's settled OQ2 chose the stamp.json read over a
first-class `loopctl fingerprint` command; the manifesto does not require
first-class commands for read access, so declining one is a taste call, not
a rule break.

### F4. Consistency with the Driver contract and decision S1 (informational)

The reconciled Driver-contract sentence (`SKILL.md:137-140`) now reads: the
passes "run concurrently as one fan-out batch and the driver awaits the join
before deciding; stopping while they run is permitted (stage
`adversarial-review` does not block the stop-check)." This is accurate
against the harness: `_STOP_BLOCKING_STAGES = _ACTIVE_STAGES -
{Stage.ADVERSARIAL_REVIEW}` (`hooks.py:53`) confirms a stop during
adversarial-review is permitted. No contradiction with the rest of the
lifecycle prose. The change also honors decision S1 (§5): review stays N
selectable passes inside the unchanged `adversarial-review` stage, each
writing its own tree-bound verdict; the `Stage` enum, `_ORDER`, and the
commit criterion are untouched. The all-or-nothing re-run
(`SKILL.md:89-91`) matches the capped findings loop (I1's named exception,
`lifecycle.py`) rather than inventing a partial-rerun path.

### F5. Manifesto silence noted (no rule invented)

The manifesto says nothing about dispatch concurrency, parallelism, or
wall-clock. DECISIONS.md and MANIFESTO I1-I3 constrain stage order and the
commit gate, not how many reviewers run at once. I therefore assert no
architectural rule on concurrency and judge the change only against the
boundary, the invariants, and decision grain it does touch. All hold.

## Out of scope for this pass

Line-level prose quality (e.g. the semicolon in `SKILL.md:139` joining two
independent clauses) belongs to the adversarial/doc reviewer and the slop
scan, not architecture. Gate execution (pytest/prek) is certified by the
tree-bound green stamp and owned by the adversarial pass; I did not
re-litigate it beyond `loopctl verify`.
