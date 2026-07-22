# Architectural review: implement-ticket-prek-before-stamp

verdict: pass
tree: 060db5cc0f75a2aacb4360088bf2be90df394900

pass: architectural
baseline: MANIFESTO.md
diff scope: skills/implement-ticket/SKILL.md (step 3, "Gate")

## Summary

Re-run after a one-word precision fix. The change adds a pre-stamp
fast-hooks instruction to step 3 of the implement-ticket SKILL. It conforms
to the architectural baseline. The stamp remains the authoritative,
tree-bound gate; the new fast pass is explicitly positioned as a convenience
that gates nothing, which is exactly the posture the MANIFESTO demands. No
invariant is eroded, and the edit is surgical and within the ticket's
declared scope. The prior round's non-blocking observation is now resolved.

## Findings against baseline rules

### F1. Stamp authority preserved (I3 / I4) — CONFORMS

The amendment does not position the fast pass as a substitute for the
evidence stamp. The added prose at `skills/implement-ticket/SKILL.md:63-66`
states verbatim: "This pass is a convenience, not a substitute for the
stamp: the type hook still runs over its whole configured target inside it,
and `loopctl stamp` re-runs every gate." This upholds I3 ("'Gates passed' is
a stamp bound to one exact tree", MANIFESTO.md:105-110) and I4 ("A stamp
goes stale the moment the tree changes", MANIFESTO.md:112-116): the fast
pass produces no lifecycle artifact, and the stamp still runs and re-runs
every gate afterward. Ordering the fast pass BEFORE the stamp
(`SKILL.md:59-62`) is the correct move for I4 — any rewrites land in the
tree before it is fingerprinted, mirroring the existing "before the stamp"
rule for tree-mutating action stages at `SKILL.md:54-58`.

### F2. "Advisory stages stay honest" value — CONFORMS

MANIFESTO §4 (MANIFESTO.md:212-215) holds that an unverifiable pre-step must
claim nothing and gate nothing (see also decision S3, MANIFESTO.md:233-236).
The new pass writes no verdict, produces no stamp, and is called a
"convenience" — it claims no lifecycle progress. Nothing in the edit lets
the agent talk past a stage it has not earned (§1, "removes the model's
ability to self-certify", MANIFESTO.md:18).

### F3. Generic register maintained — CONFORMS

MANIFESTO §1 commits the harness to being dependency-free so "any gate is
just a shell command" (MANIFESTO.md:34-37), and the SKILL's own register
(`SKILL.md:12-15`) speaks in terms of the repo's configured commands and a
task runner that wraps them. The edit phrases the instruction as "the repo's
configured lint/format/type hooks ... through the blessed invocation" and
gives `uvx prek run --files <changed>` only as a parenthetical "(here, ...)"
example, not a hardcoded requirement. This keeps the SKILL portable across
consumers whose fast layer is not prek.

### F4. Surgical and in-scope — CONFORMS

MANIFESTO §4 "Surgical scope" (MANIFESTO.md:204-206): every changed line
should trace to the ticket. Only step 3's body changed
(`git diff -- skills/implement-ticket/SKILL.md`). No gate reordering (pytest
stays inside the stamp; the fast pass is additive ahead of it, per ticket §5
non-goal and §6). No `.loop/config.json` or `justfile` change. The
`description` frontmatter at `SKILL.md:3` was left unchanged, which is
acceptable — "gate via `loopctl stamp`" is still accurate since the stamp
remains the gate.

### F5. Prior-round observation RESOLVED — CONFORMS

Last round I flagged "commit any rewrites" as loose: read literally as
`git commit`, a commit at step 3 would be refused by the commit gate hook
(I7, "The commit gate refuses commits without earned evidence",
MANIFESTO.md:131-136), since no green stamp or verdicts exist yet. The
wording is now "let any rewrites land in the tree"
(`skills/implement-ticket/SKILL.md:62`), which matches the "committed with
the code" precedent for tree-mutating pre-stamp work at `SKILL.md:54-58` and
describes exactly the intended action — the rewrites sit in the working tree
so the stamp certifies them, and are then stamped, reviewed, and committed
with the code. The fix aligns the prose with the evidence model and removes
the only reading in tension with I7. Observation cleared.

## Verdict

pass. The change upholds the stamp-as-authoritative-gate invariants (I3,
I4), the "advisory stays honest" value, and the harness's dependency-free
generic register; it is surgical and within scope; and the prior-round
wording observation is resolved.

verdict: pass
tree: 060db5cc0f75a2aacb4360088bf2be90df394900
