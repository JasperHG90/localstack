---
type: spike
title: Spike aim-to-apm/1
description: can APM 0.33.0 install the caveman marketplace plugin (pinned e2c09c9) as an enabled Claude Code plugin (enabledPlugins + marketplace) like aim did, rather than loose files?
tags:
- spike
generated:
  by: process:loopctl/2.2.2.dev1+gd84319696
  at: '2026-10-20T20:54:34+00:00'
slug: aim-to-apm
n: 1
outcome_written: true
---

# Spike aim-to-apm/1

can APM 0.33.0 install the caveman marketplace plugin (pinned e2c09c9) as an enabled Claude Code plugin (enabledPlugins + marketplace) like aim did, rather than loose files?

The command exited 1:

```
/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/spike-apm3/check.sh
```

## Outcome

APM 0.33.0 installs `juliusbrussee/caveman#e2c09c9` (apm exit 0) but not as a Claude Code plugin: `.claude/settings.json` gets no `enabledPlugins` and no `extraKnownMarketplaces` entry. APM writes those keys only for Copilot (`apm_cli/copilot_plugins/`).
Instead it unpacks the plugin as loose files: 8 skills into `.claude/skills/`, 3 agents into `.claude/agents/`, 5 commands into `.claude/commands/`, and the hook scripts into `.claude/hooks/caveman/src/hooks/`. It merges the plugin's SessionStart and UserPromptSubmit hooks into `.claude/settings.json`, rewriting `${CLAUDE_PLUGIN_ROOT}` to `${CLAUDE_PROJECT_DIR}/.claude/hooks/caveman`.
So the skills and the two hooks are likely active, but without the plugin namespace or a plugin toggle, and with 3 agents and 5 commands aim did not put in `.claude/`. The spike did not start Claude Code to confirm the hooks run.
Risk 3 holds: APM cannot reproduce aim's enabled-plugin install, so step 5 takes the manual `claude plugin marketplace add` and `claude plugin install` route.

## Files

- `run.json`: the command, when it ran, its exit, the commit and tree it ran on, and where its output went
- `stdout.txt`: its standard output
- `stderr.txt`: its standard error
- `files/check.sh`: a copy of `/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/spike-apm3/check.sh`, which the command used
