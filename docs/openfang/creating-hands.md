# Creating Hands in OpenFang

## What is a Hand?

A Hand is an autonomous, task-oriented worker. Unlike agents (which are conversational and wait for user input), Hands execute structured procedures on a schedule or in response to events. Think of agents as assistants you talk to, and Hands as background jobs that get things done.

Hands are designed for repeatable workflows: processing invoices, monitoring feeds, generating reports, syncing data. They run their procedure, report results to the dashboard, and go idle until the next trigger.

## Three-File Structure

```
my-hand/
├── HAND.toml          # Required: manifest (identity, tools, schedule, settings)
├── system-prompt.md   # Required: operational playbook (the procedure to follow)
└── SKILL.md           # Optional: domain knowledge reference
```

### HAND.toml — The Manifest

Defines what the Hand is, what it needs, and when it runs.

```toml
[hand]
id = "daily-digest"
name = "Daily Digest"
description = "Summarizes new Memex documents and sends a Telegram digest"
category = "Productivity"
icon = "newspaper"
version = "1.0.0"

[hand.requires]
tools = ["memory_search", "web_fetch", "telegram_send"]

[hand.settings]
digest_length = { type = "string", default = "short", options = ["short", "detailed"] }
include_links = { type = "bool", default = true }
max_items = { type = "int", default = 10, min = 1, max = 50 }

[hand.agent]
model = "minimax/MiniMax-M2.7"
temperature = 0.2
max_iterations = 30

[hand.schedule]
cron = "0 8 * * *"  # Every day at 8 AM

[hand.dashboard]
metrics = ["documents_summarized", "digest_sent"]

[[hand.dashboard.widgets]]
type = "stat"
metric = "documents_summarized"
period = "7d"
```

#### Sections Explained

**`[hand]` — Identity**

| Field | Purpose |
|-------|---------|
| `id` | Unique identifier, used in CLI commands and chaining |
| `name` | Display name in the dashboard |
| `description` | What it does — shown in the Hand gallery |
| `category` | Grouping label (e.g. `Finance`, `DevOps`, `Productivity`) |
| `icon` | Dashboard icon name |
| `version` | Semver for tracking changes |

**`[hand.requires]` — Dependencies**

Lists the tools the Hand needs. The Hand will fail to install if these tools are not available. This exists so you know upfront what a Hand depends on, rather than discovering it at runtime.

```toml
[hand.requires]
tools = ["web_fetch", "file_write", "file_read"]
```

**`[hand.settings]` — User-Configurable Options**

Settings let users customize Hand behavior without editing the system prompt. Each setting has a type and a default value, with optional constraints.

```toml
[hand.settings]
output_format = { type = "string", default = "csv", options = ["csv", "json", "xlsx"] }
auto_validate = { type = "bool", default = true }
threshold = { type = "float", default = 0.95, min = 0.5, max = 1.0 }
tags = { type = "string[]", default = ["inbox"] }
```

Why separate settings from the system prompt? Because settings are surfaced in the dashboard UI as form fields, letting users change behavior without touching any files.

Supported types: `string`, `bool`, `int`, `float`, `string[]`

**`[hand.agent]` — LLM Configuration**

```toml
[hand.agent]
model = "minimax/MiniMax-M2.7"
temperature = 0.1
max_iterations = 50
```

- `temperature` — Lower for structured/deterministic tasks, higher for creative ones. Most Hands should use 0.1-0.3.
- `max_iterations` — Safety cap on how many LLM calls the Hand makes per run. Prevents runaway loops.

**`[hand.schedule]` — When to Run**

Standard cron expression. The Hand activates on this schedule and runs its procedure.

```toml
[hand.schedule]
cron = "0 9 * * 1-5"  # Weekdays at 9 AM
```

Omit this section for Hands that are only triggered manually or by events.

**`[hand.triggers]` — Event-Based Activation**

Hands can also run in response to events instead of (or in addition to) a schedule.

```toml
[hand.triggers]
events = ["file_created", "webhook_received"]
webhook_path = "/hooks/my-hand"
```

**`[hand.chain]` — Multi-Hand Orchestration**

Hands can be chained so one Hand's output feeds into another. This is for multi-step pipelines where each stage has a distinct concern.

```toml
[hand.chain]
after = ["data-fetcher"]
input_from = "data-fetcher.output"
```

**`[hand.dashboard]` — Metrics and Widgets**

Define what metrics the Hand tracks and how they appear on the dashboard.

```toml
[hand.dashboard]
metrics = ["items_processed", "errors"]

[[hand.dashboard.widgets]]
type = "chart"
metric = "items_processed"
period = "7d"
style = "bar"

[[hand.dashboard.widgets]]
type = "stat"
metric = "errors"
alert_above = 5
```

Why? Hands run autonomously — the dashboard is how you know they're working. Define metrics for anything you'd want to check at a glance.

### system-prompt.md — The Operational Playbook

This is the most important file. It tells the Hand *exactly what to do* in a step-by-step procedure.

**Key principle: be procedural, not descriptive.** Don't write "You are a digest generator." Write "Phase 1: Query Memex for documents created in the last 24 hours."

```markdown
# Daily Digest — Operational Playbook

## Phase 1: Gather
1. Query Memex for all documents created since the last run.
2. If no new documents, skip to Phase 4 with an empty digest.
3. Sort documents by creation date, newest first.
4. Cap at max_items setting.

## Phase 2: Summarize
1. For each document, generate a 1-2 sentence summary.
2. If include_links is true, append the document URL.
3. If digest_length is "detailed", include key quotes from each document.
4. If digest_length is "short", keep each summary under 50 words.

## Phase 3: Send
1. Format the digest as a numbered list.
2. Add a header: "Daily Digest — {date} — {count} new documents"
3. Send via Telegram to the configured channel.
4. Log: documents_summarized = {count}, digest_sent = 1.

## Phase 4: Idle
1. Report metrics to dashboard.
2. If any errors occurred, log them with context.
3. Wait for next scheduled run.

## Error Recovery
- If Memex is unreachable: retry once after 30 seconds. If still down, log error, skip run.
- If Telegram send fails: save digest to file as fallback, alert on next run.
- If a document fails to summarize: skip it, include "[could not summarize]" placeholder.
```

#### Why Phases?

Phases give the LLM a clear execution model. Without them, the model may try to do everything at once, skip steps, or get confused about ordering. Numbered phases with numbered steps create a reliable, debuggable procedure.

#### Best Practices

- **Include decision trees.** "If X, do Y, else Z" removes ambiguity.
- **Define error recovery for every phase.** The Hand runs unattended — it needs to handle failures gracefully.
- **Set quality gates.** "Do not proceed to Phase 3 until all items have been validated."
- **Reference settings by name.** "If `digest_length` is `detailed`..." ties the procedure to user-configurable options.

### SKILL.md — Domain Knowledge Reference

SKILL.md provides reference knowledge the Hand needs to do its job well. It's separated from the system prompt because knowledge and procedure are different concerns: the procedure says *what to do*, skills say *what you need to know to do it right*.

```markdown
---
domain: productivity
version: "1.0"
sources:
  - "Internal Memex API docs"
---

# Digest Knowledge Base

## Document Types
- Notes: short-form, personal. Summarize the key takeaway.
- Articles: long-form, external. Summarize the thesis and main arguments.
- Bookmarks: URL + optional annotation. Include the title and annotation.

## Summarization Guidelines
- Lead with the conclusion, not the setup.
- Preserve proper nouns and technical terms exactly.
- If the document is a list, summarize the theme rather than listing items.

## Telegram Formatting
- Use bold for document titles: *Title*
- Use monospace for IDs or technical values: `doc-123`
- Max message length is 4096 characters. Split if needed.
```

#### When to use SKILL.md vs system-prompt.md

| system-prompt.md | SKILL.md |
|-----------------|----------|
| "Extract line items from the invoice" | "Common invoice formats: PDF, XML, scanned..." |
| "Validate the total against line items" | "Tax rates by jurisdiction: ..." |
| "If confidence < threshold, flag for review" | "Known pitfalls: multi-page invoices split items..." |

The system prompt says **do this**. The skill file says **here's what you need to know**.

## Lifecycle

```bash
# Install a Hand from a local directory
openfang hand install ./my-hand/

# Activate it (starts running on schedule)
openfang hand activate daily-digest

# Check status
openfang hand status daily-digest

# Pause (keeps config, stops execution)
openfang hand pause daily-digest

# Resume
openfang hand resume daily-digest

# Deactivate (fully stops)
openfang hand deactivate daily-digest

# Validate before publishing
openfang hand validate ./my-hand/
```

## Tips

- **Start with the procedure.** Write `system-prompt.md` first, then figure out what tools and settings it needs for `HAND.toml`.
- **Keep iterations low at first.** Set `max_iterations = 10` while testing, increase once you know the Hand works correctly.
- **Use low temperature.** Hands should be deterministic. 0.1-0.3 is the sweet spot for most tasks.
- **Test manually before scheduling.** Run the Hand once from the CLI or dashboard, verify the output, then add a cron schedule.
- **One Hand per job.** If a workflow has distinct stages, chain multiple Hands rather than building one complex one.
- **Dashboard metrics are your observability.** Define metrics for anything you'd want to check without reading logs.
