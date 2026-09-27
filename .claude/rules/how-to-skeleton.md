---
title: how-to-skeleton
description: The one shape every page in `docs/how-to/` has. Read before writing or editing a how-to.
---

# How-to skeleton

A reader at work scans for the next command, so every page in `docs/how-to/`
has the same shape and does one task one way.

```markdown
# How to <verb> <object>

## Introduction
## Prerequisites
## Directions
### Step 1: <verb> <object>
### Step N: <verb> <object>
## Additional resources
```

<constraint name="four-sections-in-order">
WHY: a reader who has used one how-to finds the commands in every other one
without reading the prose around them.

The title starts `# How to`. The page has exactly the four H2 sections above,
in that order. Every heading below H2 is a `### Step N:` inside Directions,
numbered from one without gaps. `cli/tests/test_how_to_skeleton.py` refuses
anything else.
</constraint>

<constraint name="instructions-only">
WHY: background and lookup tables slow down a reader who is in the middle of a
task, and they go stale where nobody maintaining the reference looks.

Introduction says what the reader gets and when they need it, in a few
sentences. Prerequisites is a bullet list of what must exist before step 1,
each linked to where to get it. A step is one action, its command, and what the
reader should see, so the reader can tell it worked. A trap the reader will hit
during the step stays in the step. Tables of routes, ports, flags and roles go
in `docs/reference/`, and the step links to them. Why the cluster is shaped a
way goes in `docs/explanation/`. Additional resources is a short list of links.
</constraint>
