eval: skills-prompt-decisions-via-qa

Definition of Done: the repo's skills surface genuine discrete operator
decisions via `AskUserQuestion` (recommended option first), while free-form
authoring stays prose and the mandatory registration step is never turned
back into a question.

| Behavior | Input | Expected | Scorer | Threshold |
|----------|-------|----------|--------|-----------|
| create-eval's discrete forks are asked via Q&A | create-eval Step 2 (scenario count) and Step 3 (keep/cut a row, the Scorer, the Threshold) | Each of these four forks instructs `AskUserQuestion` with the recommended option first | Human (adversarial review of SKILL.md) | Must hold for all four |
| Free-form authoring stays prose (guardrail — the operator's explicit warning) | create-eval Step 3 drafting of each row's Behavior/Input/Expected text | These are NOT converted to `AskUserQuestion`; they stay prose collaboration, with an explicit boundary note stating so | Human (review) + deterministic check that no free-form step names `AskUserQuestion` | 100% (no free-form step converted) |
| The create-ticket eval handoff becomes a Q&A | The "after the ticket, offer the eval" decision point | The eval-handoff decision instructs `AskUserQuestion` (recommended: author now; options such as author / defer / skip) | Deterministic (`create-ticket/SKILL.md` names `AskUserQuestion` at the eval handoff) | 100% |
| require_eval makes the eval mandatory, not a question (guardrail) | `require_eval: true` in config | The skill STATES the eval is mandatory rather than asking whether to author it | Human (review) | Must hold |
| Registration is never turned back into a question (guardrail — sibling conflict) | The create-ticket region the reconcile ticket made a mandatory, silent step | No `AskUserQuestion` and no prose "do you want to register?" is introduced for registration | Deterministic (no registration question present in `create-ticket/SKILL.md`) | 100% |
| The Q&A fires in the driver, not the planner subagent (guardrail) | `ticket-planner` is a read-only, return-a-path subagent | `agents/ticket-planner.md` is NOT given an `AskUserQuestion` call; the prompt lives in the create-ticket driver | Deterministic (`ticket-planner.md` contains no `AskUserQuestion` call) | 100% |
| implement-ticket's unattended forks stay block-codes (guardrail) | implement-ticket's design forks, on a loop that may run unattended | They remain `loopctl block <code>`; no `AskUserQuestion` is added to that skill | Deterministic (`implement-ticket/SKILL.md` adds no `AskUserQuestion`) | 100% |
| Every converted fork leads with the recommended option | Each converted `AskUserQuestion` instruction | It names concrete options with the recommended one first | Human (review) | Must hold |
| The convention has a durable, tracked home so future skills inherit it | The convention (today only in Memex KV); `.claude/` is aim-vendored and gitignored | `AGENTS.md` (Project conventions) states the discrete-fork-to-Q&A rule and the iterative-stays-prose boundary in a tracked, auto-loaded file | Deterministic (the section exists and states both) | 100% |
