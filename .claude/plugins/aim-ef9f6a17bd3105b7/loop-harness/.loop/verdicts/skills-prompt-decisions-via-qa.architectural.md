# Architectural review: skills-prompt-decisions-via-qa (cycle 3, final)

verdict: pass
tree: c3a009577c204e496d4952cc8d16e9e35828b74d
pass: architectural
baseline: MANIFESTO.md
ticket: .loop/plans/skills-prompt-decisions-via-qa.md
reviewed_at: 2026-07-06

## Scope of this pass

Cycles 1 and 2 both PASSED. The only change since cycle 2 is the one-line
documentation fix the prior pass flagged as advisory A1: the `DECISIONS.md`
section-Q preamble no longer cites the deleted
`.claude/rules/decision-prompts.md` and now names `AGENTS.md`, resolving the
internal contradiction. This pass re-confirms no architectural regression at
the new bound tree `c3a009577c204e496d4952cc8d16e9e35828b74d`.

## Tree binding (verified independently)

- `.loop/stamp.json` tree = `c3a009577c204e496d4952cc8d16e9e35828b74d`, equal
  to the bound tree in the briefing. Both gates recorded exit 0.
- `loopctl verify` -> `ok` (stamp green against the current tree).
- Fingerprint-relevant (non-`.loop/`) tracked changes are exactly the five
  behavioral-layer markdown files: `AGENTS.md`, `DECISIONS.md`,
  `agents/ticket-planner.md`, `skills/create-eval/SKILL.md`,
  `skills/create-ticket/SKILL.md`.
- `.loop/config.json` NOT modified, so the contract re-bound into the
  fingerprint (I6/I8/I9) is unchanged and the stamp is not staled by a config
  edit.

## The A1 fix (resolved)

`DECISIONS.md` section Q is now internally consistent. The Q preamble reads
"The convention is recorded in `AGENTS.md` (Project conventions) so future
skills inherit it (Q2)", agreeing with Q2's body (which names `AGENTS.md` and
explains why `.claude/rules/` is not viable: aim-vendored, `.claude/`
gitignored). No tracked file cites the deleted
`.claude/rules/decision-prompts.md`; the only remaining references
(`grep -rn decision-prompts`) are in `.loop/plans/skills-prompt-decisions-via-qa.md`,
the historical plan, which is excluded from the tree fingerprint. The cycle-2
advisory is closed.

## Conformance findings (all upheld)

1. Layer boundary respected (MANIFESTO §2, "Behavioral layer", lines 74-79).
   Every change is instruction-layer prose. No `src/loop_harness/`, no
   `hooks/`, no lifecycle, no ledger schema, no config touched
   (`git diff HEAD --name-only | grep -E 'src/|\.py$|hooks/hooks.json|config.json'`
   -> NONE). Invariants I1-I17 are each anchored to `src/loop_harness/` code
   the diff does not modify, so no enforcer is altered. No invariant eroded.

2. New convention home is architecturally sound. `AGENTS.md` is the tracked
   agent-instructions file (`CLAUDE.md` is a symlink to it), auto-loaded into
   agent context, so the convention is discoverable from the repo rather than
   from Memex KV alone. MANIFESTO is silent on where conventions live, so no
   rule is invented; the placement conflicts with nothing in §1-§4.

3. "No silent judgment calls" / "operator owns decisions" strengthened
   (MANIFESTO §1 lines 27-29; §4 lines 251-253). Discrete operator forks
   convert to `AskUserQuestion` (unmissable); the async `loopctl block`-code
   route for the unattended `implement-ticket` path is preserved (AGENTS.md
   "Decision prompts" para 3; DECISIONS.md Q3). Consistent with the blocked
   commitment and with I14 (the `require_eval` mandatory branch is surfaced,
   not softened).

4. Driver/subagent boundary preserved (matches decision S4 grain, MANIFESTO
   §5). `agents/ticket-planner.md` still returns a path and does NOT call
   `AskUserQuestion`; the prompt fires in the `create-ticket` driver
   (DECISIONS.md Q4).

5. Surgical scope (MANIFESTO §4 value). Every changed region traces to the
   ticket's code surface; no adjacent prose "improved", no unrelated files
   touched.

## Verdict

pass. Nothing regressed since cycle 2. The change stays entirely in the
behavioral/instruction layer; touches no `src/`, hook, lifecycle, or config;
erodes no invariant; the A1 documentation contradiction in `DECISIONS.md`
section Q is resolved and the section is internally consistent; scope is
surgical; and the working tree fingerprints to the bound tree
`c3a009577c204e496d4952cc8d16e9e35828b74d` (`loopctl verify` -> ok). No open
findings.
