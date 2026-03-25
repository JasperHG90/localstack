# Creating Agents in OpenFang

## What is an Agent?

An agent is a persistent conversational identity backed by an LLM. It has its own system prompt, model configuration, memory scope, and set of available tools. Agents are the primary way users interact with OpenFang — each one is a separate "personality" with its own context and capabilities.

Agents are defined by a **workspace directory** containing an `agent.toml` manifest and optional markdown files that shape the agent's behavior.

## Workspace Structure

```
workspaces/
└── my-agent/
    ├── agent.toml       # Required: manifest with model, capabilities, identity
    ├── SOUL.md          # Core personality and behavioral rules
    ├── IDENTITY.md      # Name, role, voice, tone
    ├── MEMORY.md        # Persistent facts the agent should always know
    ├── BOOTSTRAP.md     # First-run instructions (what to do on startup)
    ├── TOOLS.md         # Guidance on when and how to use available tools
    ├── AGENTS.md        # How to interact with other agents
    └── USER.md          # What the agent knows about the user(s)
```

### agent.toml — The Manifest

This is the only required file. It defines the agent's identity, model, and security scope.

```toml
name = "my-agent"
version = "0.1.0"
description = "One-line summary of what this agent does"
author = "your-name"
module = "builtin:chat"

[model]
provider = "minimax"
model = "minimax/MiniMax-M2.7"
api_key_env = "MINIMAX_API_KEY"
system_prompt = """Your core system instruction goes here.
Keep it focused — use the markdown files for detailed guidance."""

[capabilities]
tools = ["*"]
memory_read = ["app:openfang:my-agent:*"]
memory_write = ["app:openfang:my-agent:*"]
```

#### Fields

| Field | Purpose |
|-------|---------|
| `name` | Unique identifier, used in URLs, CLI commands, and inter-agent references |
| `version` | Semver string for tracking changes |
| `description` | Shown in the dashboard agent picker |
| `module` | Agent type. `builtin:chat` is the standard conversational agent |
| `system_prompt` | The LLM system prompt. This is the most important field — it defines behavior |

#### `[model]` Section

| Field | Purpose |
|-------|---------|
| `provider` | LLM provider name (e.g. `minimax`, `openai`, `anthropic`) |
| `model` | Model identifier as `provider/model-name` |
| `api_key_env` | Environment variable that holds the API key |

#### `[capabilities]` Section — Security Scoping

Controls what the agent can access. This exists because agents sharing a system should not automatically see each other's data.

| Field | Purpose |
|-------|---------|
| `tools` | Which tools the agent can use. `["*"]` for all, or list specific ones |
| `memory_read` | Which memory namespaces the agent can read from |
| `memory_write` | Which memory namespaces the agent can write to |

**Memory namespace patterns:**

| Pattern | Meaning | When to use |
|---------|---------|-------------|
| `["*"]` | Full access to everything | Single-agent setups, admin agents |
| `["self.*"]` | Only the agent's own memory | Default isolation — start here |
| `["app:openfang:my-agent:*"]` | Scoped to a specific app namespace | Multi-agent setups with clear boundaries |
| `["shared.*"]` | Shared team memory | Agents that need to collaborate |

Start restrictive and widen only when needed. An agent that can read `["*"]` can see every other agent's memory.

### Workspace Markdown Files

These files are optional but they let you break up what would otherwise be an enormous system prompt into focused documents. OpenFang concatenates them into the agent's context.

#### SOUL.md — Why: Core Behavioral Rules

The agent's personality and non-negotiable rules. This is where you define *how* the agent behaves, not *what* it does.

**Put here:** Tone, communication style, ethical boundaries, response format preferences, things the agent should always/never do.

```markdown
# Soul

- Be direct. Lead with the answer, not the reasoning.
- If you don't know something, say so. Never fabricate.
- Prefer action over asking for permission.
- When uncertain between two approaches, pick the simpler one.
- Never apologize for being an AI.
```

#### IDENTITY.md — Why: Public-Facing Persona

How the agent presents itself to users. Separated from SOUL.md because identity can change (e.g. rebrand, different audience) without changing core behavior.

**Put here:** Name, role title, areas of expertise, how to introduce itself.

```markdown
# Identity

- Name: Atlas
- Role: Infrastructure assistant
- Expertise: Terraform, Nomad, Vault, networking
- Voice: Technical but approachable. Uses analogies for complex topics.
```

#### MEMORY.md — Why: Persistent Facts

Facts the agent should know across all conversations without needing to re-learn them. Different from the agent's runtime memory store — this is baked-in knowledge.

**Put here:** Team conventions, project context, known constraints, frequently referenced information.

```markdown
# Memory

- The cluster runs on Orange Pi boards with Armbian.
- Container runtime is Podman, not Docker.
- All secrets live in Vault KV2 under `secret/data/default/`.
- The main branch is always deployable.
```

#### BOOTSTRAP.md — Why: First-Run Setup

Instructions the agent should follow when it starts for the first time or when a new conversation begins. Useful for agents that need to establish context before being useful.

**Put here:** Initialization steps, data to load, connections to verify.

```markdown
# Bootstrap

1. Check Memex connectivity by listing recent documents.
2. Verify MCP tools are available.
3. Greet the user and summarize what you can help with.
```

#### TOOLS.md — Why: Tool Usage Guidance

The LLM knows *that* tools exist, but not *when* or *how* you want them used. This file bridges that gap with your preferences.

**Put here:** When to use which tool, preferred tool ordering, tools to avoid in certain contexts, output format expectations.

```markdown
# Tools

- Always search Memex before answering knowledge questions.
- Use `memory_store` to save facts the user shares about themselves.
- Prefer `web_fetch` over asking the user to look things up.
- Never use `file_write` without confirming the path with the user.
```

#### AGENTS.md — Why: Multi-Agent Coordination

How this agent should interact with other agents. Only relevant if you have multiple agents running.

**Put here:** Which agents to delegate to, when to escalate, shared protocols.

#### USER.md — Why: User Context

What the agent knows about the user(s) it serves. Useful for personalization without relying on runtime memory.

**Put here:** User role, expertise level, preferences, timezone, communication style.

## Lifecycle

```bash
# Spawn an agent from its manifest
openfang agent spawn /path/to/agent.toml

# List running agents
openfang agent list

# Stop an agent
openfang agent stop <agent-id>
```

Agents can also be spawned from the dashboard by clicking a template card, or via the API.

## Tips

- **Start small.** Begin with just `agent.toml` and a `system_prompt`. Add markdown files only when the system prompt gets unwieldy.
- **Keep system_prompt short** when using markdown files — it should be the executive summary, with details delegated to the workspace files.
- **Test changes fast.** Edit files, `just sync_agents`, and start a new conversation. No image rebuild needed.
- **One agent per concern.** A coding agent and a research agent are better than one agent trying to do both.
