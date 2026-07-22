eval: implement-ticket-prek-before-stamp

Definition of Done: step 3 of `implement-ticket/SKILL.md` tells the
implementer to clear the cheap lint/format/type hooks before the stamp,
without weakening the stamp or hardcoding prek.

| Behavior | Input | Expected | Scorer | Threshold |
|----------|-------|----------|--------|-----------|
| Step 3 instructs clearing the fast hooks before the stamp | Read amended step 3 | A pre-stamp instruction to run the cheap lint/format/type hooks over changed files and clear rewrites/failures, then stamp | Human review | Must hold |
| The pre-stamp pass never weakens the stamp (guardrail) | Read amended step 3 | Framed as a convenience, not a substitute for `loopctl stamp`; pytest stays where it is | Human review | Must hold |
| Wording never invites silencing or skipping a check (guardrail) | Grep the edit for `type: ignore`, `--force-exclude`, "skip mypy", "no-verify" | None present; no phrasing licenses silencing a check | Deterministic (grep) | 100% |
| Instruction stays generic, prek only as example | Read amended step 3 | Targets "the repo's configured hooks / blessed invocation"; `uvx prek run` shown as the example, not hardcoded as the rule | Human review | Must hold |
| No hallucinated command or path in the edit | Every backticked command and `path:line` in the diff | Each resolves to a real thing (slop-scan Layer 0) | Deterministic | 100% |
| Doc-quality gate passes on the file | Run the slop scan and 80-char wrap check on `skills/implement-ticket/SKILL.md` | Layers 0-2 pass; em-dash budget met | Deterministic | Pass |
| Change is surgical and repo gates stay green | `git diff` scope plus `loopctl stamp` | Only step 3 (and optionally the frontmatter clause) changed, no renumbering; pytest and prek green | Deterministic | 100% |
