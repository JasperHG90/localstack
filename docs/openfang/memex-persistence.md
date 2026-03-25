# Automatic Memex Persistence in OpenFang

OpenFang has no hook or middleware system — you cannot register a callback that runs before/after every message, tool call, or agent response. This guide covers the available mechanisms that approximate hooks, combined into a layered strategy that makes Memex persistence as automatic as possible.

## The Problem

OpenFang agents and Hands have a native SQLite-backed memory system. If you want to replace or supplement it with Memex (via MCP), persistence depends on the LLM choosing to call Memex tools. Prompt instructions help, but they are suggestions — the model can skip them under token pressure, long conversations, or ambiguous situations.

The goal: every noteworthy piece of information gets saved to Memex, even when the agent "forgets" to do it.

## Strategy Overview

Three layers, each catching what the previous one misses:

| Layer | Mechanism | Catches |
|-------|-----------|---------|
| 1. Prompt constraints | `<constraint>` blocks in agent markdown files | Happy path — agent saves proactively |
| 2. Triggers + scribe agent | `memory_update` and `agent_terminated` triggers | Fallback — mirrors native memory writes and captures hand output |
| 3. Workflow wrapper | Post-response step with a dedicated scribe | Belt-and-suspenders — guaranteed post-response evaluation |

Use layer 1 for all agents. Add layer 2 for hands and as a safety net. Add layer 3 for high-value interactive agents where you cannot afford to miss anything.

## Layer 1: Prompt Constraints

OpenFang gives higher weight to `<constraint>` blocks than regular markdown instructions. Place these in `AGENTS.md` (or `TOOLS.md` for tool-specific rules).

### Capture constraint

Add to your agent's `AGENTS.md`:

```markdown
<constraint>
After EVERY substantive response, evaluate whether any of the following apply:
1. Completed a multi-step task (save what was done, decisions, outcome)
2. Diagnosed a bug or root cause (save symptom, cause, fix)
3. Made or discovered an architectural decision (save decision, rationale)
4. Learned a user preference or workflow pattern
5. Resolved a tricky configuration or environment issue

If ANY apply, call `memex_add_note` (with `background: true`) in the SAME tool-call
batch as your response tools. This is non-negotiable — treat it as a tool-call
prerequisite, not a post-hoc suggestion.

Keep notes concise (hard max: 300 tokens). Capture the key insight, not a report.
</constraint>
```

### Self-check constraint

A second constraint forces the agent to evaluate before finalizing:

```markdown
<constraint>
Before finalizing any response longer than 2 sentences, ask yourself:
"Did I learn anything new worth remembering?"
If yes, call `memex_kv_write` (for facts/preferences) or `memex_add_note`
(for richer context) in the same tool-call batch.
Do not mention this self-check to the user.
</constraint>
```

### KV writes for structured facts

When the user states a preference, convention, or static fact, agents should store it as a KV entry rather than a note. KV entries are faster to retrieve and better for facts that get looked up by key.

```markdown
<constraint>
When the user states a preference, convention, or reusable fact, proactively store
it via `memex_kv_write`. Use namespace prefixes:
- `user:` for personal preferences
- `project:<id>:` for project-scoped facts
- `global:` for cross-cutting conventions
</constraint>
```

### Bootstrap: load KV at session start

In `AGENTS.md` or `BOOTSTRAP.md`, instruct the agent to hydrate from Memex on first message:

```markdown
<constraint>
On first user message, before responding:
1. Call `memex_kv_list()` to read all KV entries.
2. Filter to keys matching your `memory_read` namespace.
3. Apply matching preferences/facts to all subsequent responses.
Do not mention this step to the user.
</constraint>
```

This replaces the native memory's session-start context loading.

## Layer 2: Triggers + Scribe Agent

Triggers watch the kernel's event bus and fire prompts to agents when events match. This is the closest OpenFang gets to hooks.

### Create a scribe agent

The scribe is a minimal agent whose only job is writing to Memex.

```
agents/scribe/
├── agent.toml
└── SOUL.md
```

**agent.toml:**

```toml
name = "scribe"
version = "0.1.0"
description = "Mirrors events and agent outputs to Memex"
author = "jasper"
module = "builtin:chat"

[model]
provider = "minimax"
model = "minimax/MiniMax-M2.7"
api_key_env = "MINIMAX_API_KEY"
system_prompt = """You are a background scribe. You receive event descriptions and
save them to Memex. You never respond to users directly. Be concise — max 300 tokens
per note. Use memex_add_note with background: true, author: 'openfang-scribe'."""

[capabilities]
tools = ["memex_add_note", "memex_kv_write", "memex_kv_search"]
memory_read = ["*"]
memory_write = []
```

**SOUL.md:**

```markdown
# Soul

You are a silent background worker. Your only job:
1. Receive an event description.
2. Determine if it contains information worth persisting.
3. If yes, save it to Memex via `memex_add_note` or `memex_kv_write`.
4. If no, do nothing.

Rules:
- Never respond to users.
- Never fabricate information — only save what is in the event description.
- Deduplicate: before saving, call `memex_kv_search` to check if the fact already exists.
- Max 300 tokens per note. Capture the insight, not a transcript.
```

### Trigger: mirror native memory writes

Catches any agent or hand that writes to native memory instead of Memex:

```bash
openfang trigger create \
  --agent scribe \
  --event memory_update \
  --prompt "A memory write occurred: {{event}}. Extract the key information and save it to Memex using memex_add_note (background: true, author: 'openfang-scribe'). Deduplicate first."
```

### Trigger: capture hand completion

Hands run autonomously and may produce results that never touch memory at all. Catch their termination:

```bash
openfang trigger create \
  --agent scribe \
  --event agent_terminated \
  --prompt "An agent/hand finished: {{event}}. If this contains results, findings, or decisions worth persisting, save a concise summary to Memex via memex_add_note (background: true, author: 'openfang-scribe'). If the run was trivial or routine, do nothing."
```

### Trigger: keyword-based capture

For specific topics you always want captured:

```bash
openfang trigger create \
  --agent scribe \
  --event content_match \
  --match "decision" \
  --prompt "An event mentions a decision: {{event}}. Save the decision and its rationale to Memex."
```

### Managing triggers

```bash
openfang trigger list                    # List all triggers
openfang trigger list --agent scribe     # Filter by agent
openfang trigger delete <trigger-id>     # Remove a trigger
```

Triggers support `max_fires` to auto-disable after N firings. Set to `0` for indefinite.

## Layer 3: Workflow Wrapper

For high-value interactive agents, wrap the conversation in a workflow that guarantees a post-response Memex evaluation.

```bash
openfang workflow create --file assistant-with-memex.toml
```

**assistant-with-memex.toml:**

```toml
name = "assistant-with-memex"
description = "Routes through custom_assistant, then evaluates for Memex capture"

[[steps]]
agent = "custom_assistant"
prompt = "{{input}}"
output_var = "response"
timeout_secs = 120
error_mode = "fail"

[[steps]]
agent = "scribe"
prompt = """Review this exchange and determine if anything is worth saving to Memex.

User: {{input}}
Assistant: {{response}}

If noteworthy (new fact, preference, decision, or task outcome), save via
memex_add_note or memex_kv_write. If routine, do nothing.
Respond with only: SAVED or SKIPPED."""
timeout_secs = 30
error_mode = "skip"
```

The second step runs after every response. `error_mode = "skip"` ensures that if the scribe fails, the user still gets their response.

**Trade-off:** This adds latency (one extra LLM call per exchange) and cost. Use it only for agents where missed persistence is unacceptable.

### Running the workflow

Users interact with the workflow instead of the agent directly:

```bash
# Via CLI
openfang workflow run assistant-with-memex --input "What's the status of the migration?"

# Via API
POST /api/workflows/assistant-with-memex/run
{"input": "What's the status of the migration?"}
```

## Hand-Specific Considerations

Hands use a different file structure (`HAND.toml` + `system-prompt.md` + `SKILL.md`) and run autonomously. You cannot add `AGENTS.md` constraint blocks to them.

### Option A: Add Memex steps to the hand's system prompt

In the hand's `system-prompt.md`, add a final phase:

```markdown
## Phase N: Persist to Memex

1. Review all findings, decisions, and outputs from this run.
2. Call `memex_add_note` with:
   - `background: true`
   - `author: "<hand-id>"`
   - A concise summary (max 300 tokens)
3. If any user-relevant preferences or facts were discovered, call `memex_kv_write`.
4. This phase is MANDATORY — do not skip it even if the run produced no actionable results.
   In that case, save a note: "Run completed with no actionable output."
```

### Option B: Chain a scribe hand after the primary hand

Use `[hand.chain]` to run the scribe as a second stage:

```toml
# In the scribe hand's HAND.toml
[hand.chain]
after = ["daily-digest"]
input_from = "daily-digest.output"
```

The scribe hand receives the primary hand's output and saves it to Memex.

### Option C: Rely on the `agent_terminated` trigger

If you set up the trigger from Layer 2, it will fire when any hand completes. This requires no changes to the hand itself — the scribe agent evaluates the termination event and saves what matters.

This is the lowest-effort option but also the least precise, since the `{{event}}` payload for `agent_terminated` may not contain the full output.

## Recommended Setup

For a typical deployment with one interactive agent and several hands:

1. **Interactive agent (`custom_assistant`):**
   - Layer 1: Add all three constraint blocks to `AGENTS.md`
   - Layer 2: Enable the `memory_update` trigger as a safety net
   - Layer 3: Optional — only if you find the constraints are insufficient

2. **All hands:**
   - Add a "Persist to Memex" final phase to each hand's `system-prompt.md`
   - Enable the `agent_terminated` trigger as a catch-all

3. **Scribe agent:**
   - Deploy once, shared across all triggers and workflows
   - Keep its tool access minimal (`memex_add_note`, `memex_kv_write`, `memex_kv_search`)
   - Give it `memory_read = ["*"]` so triggers can pass it context from any agent

### Disabling native memory (optional)

If you want to fully replace native memory with Memex, restrict the agent's memory scopes to prevent native writes:

```toml
[capabilities]
memory_read = []
memory_write = []
```

This forces the agent to use only MCP tools for persistence. The `memory_update` trigger will no longer fire (since nothing writes to native memory), so you would rely entirely on prompt constraints and workflows.

Only do this if your Memex MCP server is reliable — there is no fallback.
