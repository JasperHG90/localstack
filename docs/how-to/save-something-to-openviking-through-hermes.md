---
description: "Ask Hermes on Telegram to save a link, a note or a voice note into the right folder of your OpenViking resources."
stale_after: 2027-01-20
sources:
  - resource: deployments/applications/services/hermes/skills/productivity/save-to-openviking/SKILL.md
  - resource: deployments/applications/services/hermes/SOUL.md
  - resource: deployments/applications/services/hermes/openviking_tools/__init__.py
  - resource: deployments/applications/services/hermes.hcl
---

# How to save something to OpenViking through Hermes

## Introduction

Tell Hermes "save this" on Telegram and it files the link, note or voice
note under `viking://user/jasper/resources/`. It picks the folder from a
map file, `.map.md`, at the top of that folder. If you name no place, it
proposes one and waits for your answer.

## Prerequisites

- A Telegram chat with the Hermes bot, on image `0.22.2-3` or later (the
  `hermes_version` in `deployments/applications/services.tf`). See
  [Hermes, the agent gateway](../../.okf/components/hermes.md).
- For step 5, a shell that can call OpenViking. See
  [How to call OpenViking from the CLI](call-openviking-from-the-cli.md).

## Directions

### Step 1: Save a link to a place you name

Send the link and the folder, relative to your resources folder:

```text
save this https://www.anthropic.com/engineering/building-effective-agents to blogs/anthropic
```

Hermes saves it without asking and replies with the new `viking://` URI.
The first save also writes the map, so the map exists from here on.

### Step 2: Save a link without a place

```text
save this https://www.anthropic.com/engineering/writing-tools-for-agents
```

Hermes reads the map, proposes a folder such as `blogs/anthropic/`, and
asks you to confirm or name another. Nothing is saved until you answer.
Saving into `projects/` or `leo/` needs you to name that folder: those two
are written by syncs.

### Step 3: Add a new top-level folder

Name a folder whose first part is not in the map:

```text
save this note to notes/ideas: try the base Whisper model before small
```

Hermes asks for a one-line description of `notes/`, adds a line for it to
the map, then saves. Later saves into `notes/` need no description.

### Step 4: Save a voice note's transcript

Send a voice note, then:

```text
save the transcript to notes/standups
```

Hermes transcribes the voice note on the node, writes the text to a file
named like `2026-10-20-standup-plan.md`, and saves it under the folder, in
a subfolder named after the file. The very first voice note takes a few
seconds longer while the speech model downloads. The model stays on the data
volume, so restarts do not download it again.

### Step 5: Read the map

From a shell, with `OV_URL` and `OV_TOKEN` set as in
[How to call OpenViking from the CLI](call-openviking-from-the-cli.md):

```console
$ curl -s -H "Authorization: Bearer $OV_TOKEN" \
    "$OV_URL/api/v1/content/read?uri=viking://user/jasper/resources/.map.md"
```

You should see the four seed folders (`projects/`, `leo/`, `blogs/`,
`clips/`) and the `notes/` line from step 3. Only Hermes writes the map:
read it from the shell or from Claude Code, but do not edit it there.

## Additional resources

- [OpenViking](../reference/openviking.md)
- [ADR 0023: Hermes saves from a skill-owned map of roots](../../.okf/decisions/0023-hermes-saves-from-a-skill-owned-map-of-roots.md)
