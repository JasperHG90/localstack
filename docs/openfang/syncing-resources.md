# Syncing OpenFang Resources

OpenFang resources (agents, skills, workflows, triggers) are defined locally in `deployments/applications/services/openfang/` and synced into the running container via `just sync_openfang`. This guide covers the directory layout, how each resource type works, and how the sync mechanism ties them together.

## Directory Layout

```
services/openfang/
├── Dockerfile
├── register.sh            # Registration script (runs inside container)
├── triggers.json          # Trigger definitions
├── agents/                # Agent workspaces
│   └── custom_assistant/
│       ├── agent.toml
│       ├── SOUL.md
│       ├── IDENTITY.md
│       ├── MEMORY.md
│       ├── BOOTSTRAP.md
│       ├── TOOLS.md
│       ├── AGENTS.md
│       └── USER.md
├── skills/                # Skill packages
│   └── memex-memory/
│       └── SKILL.md
└── workflows/             # Workflow definitions (JSON)
    └── .gitkeep
```

Each directory maps to a location inside the container:

| Local path | Container path | Auto-loaded on boot? | Registration command |
|---|---|---|---|
| `agents/*` | `/data/workspaces/` | Yes (persisted in SQLite) | `openfang agent spawn <manifest>` |
| `skills/*` | `/data/skills/` | Yes | `openfang skill install <dir>` |
| `workflows/*.json` | `/data/workflows/` | No | `openfang workflow create <file>` |
| `triggers.json` | `/data/triggers.json` | No | `openfang trigger create <agent_id> <pattern>` |

## Skills

Skills extend agent capabilities. OpenFang supports two kinds:

### prompt_only Skills (SKILL.md)

A markdown file with YAML frontmatter. The content gets injected into the agent's system prompt at spawn time. Use these for domain knowledge, conventions, or configuration that the agent needs to know.

```markdown
---
name: my-skill
description: What this skill provides
---

# Skill Content

Instructions and knowledge go here.
```

Supported frontmatter fields: `name`, `description`, `metadata`, `license`, `compatibility`, `argument-hint`, `disable-model-invocation`, `user-invocable`.

Place the file in a directory under `skills/`:

```
skills/
└── my-skill/
    └── SKILL.md
```

### Executable Skills (skill.toml)

For skills that provide tools (Python, WASM, Node.js), use a `skill.toml` manifest:

```toml
[skill]
name = "my-tool"
version = "0.1.0"
description = "Provides custom tools"
author = "your-name"

[runtime]
type = "python"
entry = "src/main.py"

[[tools.provided]]
name = "my_tool"
description = "What it does"
input_schema = { type = "object", properties = { query = { type = "string" } }, required = ["query"] }

[requirements]
tools = ["web_fetch"]
```

### Attaching Skills to Agents

Reference skills by name in `agent.toml`:

```toml
skills = ["memex-memory", "my-tool"]
```

The kernel loads skill tools and prompts at agent spawn time, merging them with the agent's base capabilities.

## Workflows

Workflows orchestrate multi-agent pipelines. Define them as JSON files in `workflows/`:

```json
{
  "name": "my-pipeline",
  "description": "What this workflow does",
  "steps": [
    {
      "name": "step-1",
      "agent_name": "custom_assistant",
      "prompt": "{{input}}",
      "mode": "sequential",
      "timeout_secs": 120,
      "error_mode": "fail",
      "output_var": "result"
    },
    {
      "name": "step-2",
      "agent_name": "another_agent",
      "prompt": "Process: {{result}}",
      "mode": "sequential",
      "timeout_secs": 60,
      "error_mode": "skip"
    }
  ]
}
```

### Step Modes

| Mode | Behavior |
|------|----------|
| `sequential` | Steps run in order; prior output becomes `{{input}}` for the next step |
| `fan_out` | Consecutive fan-out steps run in parallel with the same input |
| `collect` | Joins all preceding fan-out outputs with `\n\n---\n\n` separators |
| `conditional` | Runs only if previous output contains a specified substring |
| `loop` | Repeats up to `max_iterations` times; stops early if output contains `until` substring |

### Error Modes

| Mode | Behavior |
|------|----------|
| `fail` | Workflow aborts immediately (default) |
| `skip` | Step silently skips; workflow continues with unchanged input |
| `retry` | Retries up to `max_retries` times |

### Variable Substitution

- `{{input}}` — previous step's output (always available)
- `{{variable_name}}` — references stored outputs from steps that set `output_var`

## Triggers

Triggers watch the kernel's event bus and fire prompts to agents when events match. Since triggers require runtime agent UUIDs, they are defined in a custom `triggers.json` format (not a native OpenFang format) that the registration script resolves.

```json
[
  {
    "agent_name": "scribe",
    "pattern": "{\"memory_update\":{}}",
    "prompt": "A memory event occurred: {{event}}. Save to Memex.",
    "max_fires": 0
  }
]
```

### Fields

| Field | Purpose |
|-------|---------|
| `agent_name` | Name of the agent to notify (resolved to UUID during sync) |
| `pattern` | JSON event pattern string |
| `prompt` | Template sent to the agent; `{{event}}` is replaced with the event description |
| `max_fires` | Auto-disable after N firings; `0` for unlimited |

### Event Patterns

| Pattern | Matches |
|---------|---------|
| `{"all":{}}` | Every event |
| `{"lifecycle":{}}` | Agent spawn, termination, crash |
| `{"agent_spawned":{"name_pattern":"*"}}` | Agent creation (optional name filter) |
| `{"agent_terminated":{}}` | Agent termination or crash |
| `{"system":{}}` | Health checks, quota warnings |
| `{"system_keyword":{"keyword":"error"}}` | System events containing keyword |
| `{"memory_update":{}}` | Any memory change |
| `{"memory_key_pattern":{"pattern":"user:*"}}` | Memory updates matching key pattern |
| `{"content_match":{"substring":"decision"}}` | Events with substring in description |

## The Sync Mechanism

### register.sh

A shell script that runs inside the container after all files are copied. It registers resources in dependency order: skills first (agents may reference them), then agents (triggers need their UUIDs), then workflows, then triggers.

```bash
#!/bin/sh
set -e

# Skills
for d in /data/skills/*/; do
    [ -d "$d" ] && openfang skill install "$d" 2>/dev/null || true
done

# Agents
for f in /data/workspaces/*/agent.toml; do
    [ -f "$f" ] && openfang agent spawn "$f" || true
done

# Workflows
for f in /data/workflows/*.json; do
    [ -f "$f" ] && openfang workflow create "$f" 2>/dev/null || true
done

# Triggers (requires jq)
if [ -f /data/triggers.json ] && command -v jq >/dev/null 2>&1; then
    jq -c '.[]' /data/triggers.json | while read -r t; do
        name=$(echo "$t" | jq -r .agent_name)
        pattern=$(echo "$t" | jq -r .pattern)
        prompt=$(echo "$t" | jq -r .prompt)
        max_fires=$(echo "$t" | jq -r .max_fires)
        agent_id=$(openfang agent list 2>/dev/null \
            | grep "$name" | awk '{print $1}' | head -1)
        [ -n "$agent_id" ] && openfang trigger create "$agent_id" "$pattern" \
            --prompt "$prompt" --max-fires "$max_fires" 2>/dev/null || true
    done
fi
```

The trigger section resolves `agent_name` to UUID by grepping `openfang agent list` output. `jq` is required in the container image for this (added to the Dockerfile).

### just sync_openfang

The justfile target runs three SSH commands:

1. **mkdir** — create staging directory on the remote host
2. **scp** — copy all resource directories + register.sh to the remote
3. **compound exec** — `podman cp` each directory to its container path, run `register.sh`, clean up

```bash
just sync_openfang                          # Defaults: host=192.168.2.47, user=raspberry
just sync_openfang host=10.0.0.5 user=pi    # Override target host
```

## Worked Example: memex-memory Skill

The `memex-memory` skill solves a specific problem: `memory_read` and `memory_write` in `agent.toml` only scope OpenFang's native SQLite memory. When using Memex (via MCP) as the memory backend, the agent has no built-in way to know which KV namespaces it should read from or write to.

A `prompt_only` skill injects this configuration into the system prompt:

```markdown
---
name: memex-memory
description: Memex KV namespace conventions and memory scope declarations
---

# Memex Memory Configuration

## Namespace Scopes

Your agent name (from your manifest) determines your private namespace.
Use `app:openfang:<your-agent-name>:` as your private prefix.

### Read access
- `global:*` — cross-agent shared facts
- `user:*` — user preferences and personal info
- `app:openfang:<your-agent-name>:*` — your private agent-scoped memory

### Write access
- `user:*` — user preferences and personal info
- `app:openfang:<your-agent-name>:*` — your private agent-scoped memory
```

The agent loads it via `agent.toml`:

```toml
skills = ["memex-memory"]

[capabilities]
tools = ["*"]
memory_read = []    # Native memory disabled
memory_write = []   # All persistence via Memex MCP
```

This approach:

- **Separates concerns** — memory config lives in a skill, not mixed into AGENTS.md behavioral guidelines
- **Is explicit** — the agent sees its namespace scopes as part of its system prompt, not as a side-channel config field
- **Scales to multi-agent** — create per-agent skills or a shared skill with a namespace table

## Adding a New Resource

### New agent

1. Create a directory under `agents/` with at least an `agent.toml`
2. Run `just sync_openfang`

### New skill

1. Create a directory under `skills/` with a `SKILL.md` (prompt_only) or `skill.toml` + entry point
2. Reference the skill in the target agent's `agent.toml`: `skills = ["my-skill"]`
3. Run `just sync_openfang`

### New workflow

1. Create a JSON file under `workflows/`
2. Run `just sync_openfang`

### New trigger

1. Add an entry to `triggers.json`
2. Ensure the target agent exists (it must be spawned before the trigger can reference it)
3. Run `just sync_openfang`
