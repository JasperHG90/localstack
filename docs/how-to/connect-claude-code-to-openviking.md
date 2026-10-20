---
description: Remove the OpenViking memory plugin from Claude Code, so Claude Code reads and writes OpenViking only when you ask.
stale_after: 2027-01-19
sources:
  - resource: deployments/applications/services/openviking.hcl
---

# How to connect Claude Code to OpenViking on request

## Introduction

This leaves Claude Code with no automatic link to OpenViking. The memory
plugin searched OpenViking at the start of each prompt and saved each session
into it. Remove it if you installed it, then call OpenViking yourself when you
want it.

## Prerequisites

- [Claude Code](https://code.claude.com/docs/en/setup) installed.
- A Vault login that can mint an OpenViking token, for step 4. See
  [How to call OpenViking from the CLI](call-openviking-from-the-cli.md).

## Directions

### Step 1: Find the memory plugin

```console
$ claude plugin list
```

Look for `openviking-memory@openviking`. If it is not listed, skip to step 4.
An older installer named the marketplace `openviking-plugins-local`. If you
see `openviking-memory@openviking-plugins-local`, use that id and marketplace
name in step 2.

### Step 2: Uninstall the plugin and its marketplace

```console
$ claude plugin uninstall openviking-memory@openviking
$ claude plugin marketplace remove openviking
```

These are the commands the installer prints for removal.

### Step 3: Check that it is gone

```console
$ claude plugin list
$ claude plugin marketplace list
```

Neither list should name `openviking-memory` or `openviking`. Start a new
Claude Code session so the old hooks stop running.

### Step 4: Call OpenViking when you want it

Follow [How to call OpenViking from the CLI](call-openviking-from-the-cli.md)
and paste what you need into the session, or ask Claude Code to run those
commands for you.

## Additional resources

- [OpenViking](../reference/openviking.md)
- [OpenViking identity](../explanation/openviking-identity.md)
