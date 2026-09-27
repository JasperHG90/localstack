# How to connect Claude Code to OpenViking

## Introduction

This gives Claude Code recall from and capture into OpenViking. For Claude
Code, use the memory plugin, not an MCP registration.

## Prerequisites

- A `~/.openviking/ovcli.conf` holding an OpenViking identity token. The
  token comes from
  [How to call OpenViking from the CLI](call-openviking-from-the-cli.md),
  which does not write this file.
- Claude Code installed.

## Directions

### Step 1: Install the memory plugin

```console
$ bash <(curl -fsSL https://raw.githubusercontent.com/volcengine/OpenViking/\
main/examples/memory-plugin-shared/install.sh)
```

It hooks the session lifecycle for auto-recall and auto-capture and reads
`~/.openviking/ovcli.conf`. The installer's legacy path registers a stdio MCP
proxy instead; plugin mode does not, so a separate `claude mcp add` is
redundant with it.

## Additional resources

- [OpenViking](../reference/openviking.md)
- [OpenViking identity](../explanation/openviking-identity.md)
