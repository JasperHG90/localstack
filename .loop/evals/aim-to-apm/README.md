---
type: eval
title: 'Eval: aim-to-apm'
description: 'Definition of done for aim-to-apm: 10 row(s).'
tags:
- eval
generated:
  by: process:loopctl/2.2.2.dev1+gd84319696
  at: '2026-10-28T10:25:20+00:00'
slug: aim-to-apm
signoff:
  signer: delegated:jasperginn@gmail.com/agent
  hash: 07dd9d7c89791d37a0775d82e79afc6c82b65687a9e78f02c83073ad28961c28
  at: '2026-10-28T10:25:20+00:00'
verified: null
---

Rows: rows.json; the fields each row takes: loopctl schema eval-rows.

- r1: aim is gone: aim.toml and aim.lock.toml are deleted, AGENTS.md has no aim: marker or aim header, and CLAUDE.md is still a symlink to AGENTS.md.
  Fails when: either aim file exists, AGENTS.md contains 'aim:' or names agent-integrations-manager, or CLAUDE.md is not a symlink resolving to AGENTS.md
- r2: apm.yml declares the 12 skills (the 10 from jasperhg90/skills, adhd and bencium-impact-designer), the 6 jasperhg90/skills rules and the 2 subagents, each pinned to a commit or tag.
  Fails when: any of the 12 skills, 6 rules or 2 subagents is missing from apm.yml, or a dependency has no ref
- r3: The drawio and excalidraw MCP servers are dropped from apm.yml and .mcp.json.
  Fails when: apm.yml or .mcp.json names drawio or excalidraw
- r4: slop-scan-for-docs is committed under .claude/rules, byte-identical to aim's pin, and .gitignore lets it through.
  Fails when: the file's sha256 is not ccce6d06e1707ea75cc0c25a3a06f163b4faa778b4d9b6d9833681cabd74c486, or git check-ignore reports it ignored
- r5: OpenCode gets the 7 rules in .opencode/rules, each byte-identical to its .claude/rules copy, and no adversarial-reviewer or feature-planner in .opencode/agents; both install recipes do this by naming the 7 rules, not by a glob.
  Fails when: a rule is missing from .opencode/rules or differs from .claude/rules, a rule outside the 7 is copied, either subagent file is in .opencode/agents, or kmctl-install and kmctl-install-frozen do not both copy and remove
- r6: The pre-commit exclude covers every path APM or kmctl plugin patch writes: .agents/, .opencode/, opencode.json, .mcp.json and apm.lock.yaml, besides .claude/ and .loop/.
  Fails when: the top-level exclude regex of .pre-commit-config.yaml does not match a file under each of those paths
- r7: README.md documents the manual caveman install (claude plugin marketplace add juliusbrussee/caveman, then claude plugin install caveman@caveman) and names the justfile's real recipes kmctl-install, kmctl-init and kmctl-check.
  Fails when: README.md lacks either caveman command, or names just install, just init or just check as recipes
- r8: just check-install passes on a clean checkout of the change.
  Fails when: on a fresh git repo holding every tracked and unignored file of the worktree, committed, just check-install exits nonzero or leaves git status non-empty
- r9 (judgment): Each installed skill file is byte-identical to aim's copy from the step 1 snapshot, and the diff of rules and subagents against that snapshot is recorded for the operator.
  Fails when: diff -r between the snapshot and .claude/skills is not empty for the 12 skills, or no rule and subagent diff is reported
- r10 (judgment): A decision record says the guidelines stay in AGENTS.md, not in a rule, and names moving them into a rule as the rejected option.
  Fails when: no new .okf/decisions record covers it, or it does not name the rejected option
