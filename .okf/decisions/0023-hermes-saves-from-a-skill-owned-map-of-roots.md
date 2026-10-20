---
type: decision
title: "ADR 0023: Hermes saves from a skill-owned map of roots"
description: "The save-to-openviking skill finds a folder from a map of resource roots that it owns, over walking the live tree on each save and over a job that rebuilds the map."
tags: [adr, decision, hermes, openviking, skills]
generated:
  by: claude-opus/5.5
  at: 2026-10-20T16:19:44Z
status: stable
sources:
  - resource: "deployments/applications/services/hermes/skills/productivity/save-to-openviking/SKILL.md"
  - resource: "deployments/applications/services/hermes/openviking_tools/__init__.py"
  - resource: "cli/tests/test_hermes_save_skill.py"
---

# ADR 0023: Hermes saves from a skill-owned map of roots

## Context

The operator wants to say "save this" to Hermes and have the link, file, note
or voice transcript land in the right folder under
`viking://user/jasper/resources/`. After
[ADR 0020](/decisions/0020-agents-use-openviking-through-tools-only.md)
Hermes has no automatic recall, so where things go has to be written down
somewhere Hermes reads on a save. Walking the live tree is slow: `fs/tree` on
`viking://user` took about 19 s, and two levels of `fs/ls` plus each folder's
`.abstract.md` is a dozen or more calls through the model's tool loop.

## Decision

The `save-to-openviking` skill owns one file,
`viking://user/jasper/resources/.map.md`, that lists the top-level folders
(roots) and the rule for each, not every leaf. A save reads it with one
`viking_read`. The first save writes the seed (`projects/<repo>/`, `leo/`,
`blogs/<source>/`, `clips/<slug>/`). A root the operator picks is appended
before the save. When no entry fits, the skill does one `viking_browse` list of
the resources folder, then asks. Automated writers add only children under
roots the map already names, so they never make it stale.

The six upstream tools cannot write an exact file, so the `openviking_tools`
wrapper adds a seventh, `viking_write`, that posts `content/write` through the
plugin's own client in the default processing mode. A dotfile there is hidden
from `ls`, stays out of search, and costs one model call per write to refresh
the resources folder's summary (spike:ov-save-skill/2).

Rejected: walking the live tree on every save, for the cost above. Also
rejected: a periodic job that rebuilds the map from the tree. It would be one
more scheduled writer to run and watch, its descriptions would come from
generated summaries instead of the operator, and between runs a new root would
still be missing.

## Consequences

- A root made outside the skill (by hand, or by a new automated writer) is
  missing from the map until a save finds it with the one `list` fallback and
  the operator describes it. A new automated writer should add its root to the
  seed in the skill.
- The map is only as right as its writes. Claude Code and the shell read it
  and do not write it.
- `cli/tests/test_hermes_save_skill.py` pins the skill's steps and the
  `SOUL.md` line that sends Hermes to it, and
  `cli/tests/test_hermes_openviking_tools.py` pins `viking_write`.
