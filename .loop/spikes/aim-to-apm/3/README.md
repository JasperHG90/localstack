---
type: spike
title: Spike aim-to-apm/3
description: does APM 0.33.0 deploy .instructions.md rules and .agent.md agents from jasperhg90/skills@1c3dd31 as loadable .claude/rules/*.md and .claude/agents/*.md (front matter usable), pinned in apm.lock.yaml and restored byte for byte by apm install --frozen, and where do they land for opencode?
tags:
- spike
generated:
  by: process:loopctl/2.2.2.dev1+gd84319696
  at: '2026-10-20T21:01:31+00:00'
slug: aim-to-apm
n: 3
outcome_written: true
---

# Spike aim-to-apm/3

does APM 0.33.0 deploy .instructions.md rules and .agent.md agents from jasperhg90/skills@1c3dd31 as loadable .claude/rules/*.md and .claude/agents/*.md (front matter usable), pinned in apm.lock.yaml and restored byte for byte by apm install --frozen, and where do they land for opencode?

The command exited 0:

```
/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/spike-apm4/spike.sh
```

## Outcome

APM 0.33.0 accepts the string shorthand `jasperhg90/skills/rules/<name>.instructions.md#<sha>` and `.../agents/<name>.agent.md#<sha>` next to a skill folder at another pin (`.../skills/tools/generate-art#516c105...`), and installs all 6 (exit 0).
For Claude, rules land as `.claude/rules/<name>.md` and agents as `.claude/agents/<name>.md`. Agents are byte-identical to upstream, so `name`, `description`, `tools`, `model` and `color` survive. Rules keep their body byte for byte but APM rewrites the front matter: `name`/`description`/`title` are dropped (no front matter, so Claude loads them always), and `applyTo: "docs/**,.okf/**,README.md"` becomes a `paths:` list of the three globs.
`apm.lock.yaml` records commit 1c3dd31 for each rule and agent and 516c105 for the skill, and `apm install --frozen` restored all 13 deployed files byte for byte after deletion.
OpenCode: agents land byte-identical in `.opencode/agents/<name>.md`, but APM warns OpenCode will reject both at load (`tools` is a string, not a map; `color` is a name like `blue`, not hex). Rules get no OpenCode file: APM says to run `apm compile` to write them into AGENTS.md, which this spike did not test.
Settles risk 1 for Claude. For OpenCode the agents need upstream front-matter changes (or a skip) and the rules need `apm compile`; the spike did not start Claude Code or OpenCode to confirm loading.

## Files

- `run.json`: the command, when it ran, its exit, the commit and tree it ran on, and where its output went
- `stdout.txt`: its standard output
- `stderr.txt`: its standard error
- `files/spike.sh`: a copy of `/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/spike-apm4/spike.sh`, which the command used
