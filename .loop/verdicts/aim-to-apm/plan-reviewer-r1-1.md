---
type: verdict
title: 'Verdict: aim-to-apm plan-reviewer round 1'
description: 'plan-reviewer verdict for round 1 of aim-to-apm: fail.'
tags:
- verdict
- plan
generated:
  by: claude-opus/5.5
  at: '2026-10-20T21:05:03+00:00'
slug: aim-to-apm
pass: plan-reviewer
round: 1
body_schema: verdict/1
---

## Summary

fail: the approach works, but two gaps need another look. First, python-testing silently changes from always-on to path-scoped in Claude (p1). Second, end-of-file-fixer and check-install already conflict at HEAD, so the Outcome cannot pass as written (p2). Neither one invalidates the plan, and one ticket is still the right size.

## Findings

- p1 (premise, blocking): python-testing's applyTo "**/*.py" becomes paths: in Claude, where today it is always-on.
- p2 (missing, blocking): end-of-file-fixer rewrites files APM and kmctl install, so `just pre_commit` and `just check-install` cannot both pass. sample-findings.json already shows the clash.

## Checked

- Spike 1 (caveman) supports the manual README route. APM writes no
  enabledPlugins or marketplace entry for Claude.
- Spike 2 supports pinning skill folders and installing one repo at several
  commits. The six distinct pins of jasperhg90/skills in aim.lock.toml
  (current.sha) are what the plan names.
- Spike 3 supports .instructions.md and .agent.md from 1c3dd31: they install,
  get pinned, and come back byte for byte under --frozen. The upstream content
  differs from aim's pins. python-testing gains a "test tiers" section,
  plain-language drops the pointer to slop-scan, and both agents changed (29
  and 48 diff lines). The plan already records these diffs for the operator.
- No name clashes with kmctl's package. kmctl ships the rules okf-bundle,
  docs-layout, diagrams-stay-current and manifesto-invariants, the agents
  kmctl-auditor, bundle-weaver and event-analyzer, and its own skill set. The
  aim set overlaps none of them.
- Removing aim's copies first is safe if the build deletes only the 7 rules,
  12 skills and 2 agents aim lists. .claude/rules/minimal-comments.md and
  .claude/agents/plan-premise-auditor.md are local files aim did not write,
  and step 3 must leave them. The caveman entries are in .claude/settings.json
  (gitignored) beside okf@scaccogatto and loop-harness@loopctl, which must
  stay.
- `kmctl plugin patch` (v0.12.1 src/kmctl/opencode.py) writes only kmctl's own
  rules and agents. It does not wipe .opencode/rules/ or .opencode/agents/, so
  copying rules and removing the two agents after it is safe. Its
  agent_problems check covers only kmctl's agents, so `kmctl doctor` will not
  flag them.
- Vendoring slop-scan works: .gitignore uses per-file negations under
  /.claude/rules/*, so one more `!` line lets it through. All 7 rule files
  already end in a newline.
- .mcp.json is tracked. Dropping the two entries leaves `bundle`, which APM
  manages.
