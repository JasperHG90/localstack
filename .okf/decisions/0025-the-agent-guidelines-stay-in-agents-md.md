---
type: decision
title: "ADR 0025: The agent guidelines stay in AGENTS.md"
description: "After aim goes, the behavioral guidelines aim wrote into AGENTS.md stay there as plain text instead of moving into a rule."
tags: [decision]
generated:
  by: process:kmctl/0.12.1
  at: 2026-10-28T10:28:16Z
status: stable
sources:
  - resource: "AGENTS.md"
---

# ADR 0025: The agent guidelines stay in AGENTS.md

## Context

aim wrote two marked regions into `AGENTS.md`: a header saying the regions are
generated, and the behavioral guidelines (think before coding, simplicity
first, surgical changes, goal-driven execution). The aim-to-apm ticket removes
aim, so nothing regenerates those regions any more. APM can install the
guidelines as a rule instead.

## Decision

The aim header goes, the two `aim: guidelines` marker lines go, and the
guidelines stay in `AGENTS.md` as plain text that people edit by hand.
`AGENTS.md` is the one file both harnesses load: Claude Code reads it through
the `CLAUDE.md` symlink, and OpenCode reads it natively.

Rejected: moving the guidelines into a rule. All but five files in
`.claude/rules/` are gitignored and installed, so the text would leave the
repository, and OpenCode would see it only through the rule copy in the
install recipes.

## Consequences

The guidelines are now this repository's own text. A change to the upstream
guidelines no longer reaches `AGENTS.md` on its own. `CLAUDE.md` stays a
tracked symlink, so nothing has to recreate it after aim goes.
