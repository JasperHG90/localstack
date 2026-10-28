---
type: spike
title: Spike devcontainer-ovsync/1
description: with .openviking in HOME read-only and ovcli.conf at an unreachable URL, do ov 0.5.0 and ovsync v0.3.0 fail only on the network, with no write under .openviking?
tags:
- spike
generated:
  by: process:loopctl/2.2.2.dev1+gd84319696
  at: '2026-10-28T09:21:38+00:00'
slug: devcontainer-ovsync
n: 1
outcome_written: true
---

# Spike devcontainer-ovsync/1

with .openviking in HOME read-only and ovcli.conf at an unreachable URL, do ov 0.5.0 and ovsync v0.3.0 fail only on the network, with no write under .openviking?

The command exited 0:

```
/tmp/claude-1000/-home-vscode-workspace/bb29ac4a-7b6b-458a-a055-0c05909aba19/scratchpad/spike-devcontainer-ovsync/spike.sh
```

## Outcome

With `~/.openviking` read-only (touch refused) and `ovcli.conf` pointing at 127.0.0.1:9, strace showed no write, create, rename or unlink under `~/.openviking` from `ov status`, `ov ls viking://` (ov 0.5.0), `ovsync status` or `ovsync run` (v0.3.0), and `find $HOME` did not change. `ovsync run` failed with "Connection refused", `ov ls` with "Connection Error", and `ov status` exited 0 but reported "Unreachable". ovsync keeps its state in `<folder>/.ov-sync.db`, not in HOME.
Catch: ov 0.5.0 refuses every command (exit 2, "needs a display language") unless `~/.openviking/ovcli.settings.conf` exists. `ov language en` writes that file, and `OPENVIKING_LANG=en` does not replace it. ov reads it from `~/.openviking` even when `OPENVIKING_CLI_CONFIG_FILE` points elsewhere. So the read-only mount must already contain `ovcli.settings.conf`. A single-file mount of `ovcli.conf`, or the `OPENVIKING_CLI_CONFIG_FILE` fallback, leaves `ov` unusable.
This settles risk 1 for writes, but the plan must require `ovcli.settings.conf` in the mounted dir. Limit: this was a stub config with no server, so paths that only run after a successful connection were not exercised.

## Files

- `run.json`: the command, when it ran, its exit, the commit and tree it ran on, and where its output went
- `stdout.txt`: its standard output
- `stderr.txt`: its standard error
- `files/spike.sh`: a copy of `/tmp/claude-1000/-home-vscode-workspace/bb29ac4a-7b6b-458a-a055-0c05909aba19/scratchpad/spike-devcontainer-ovsync/spike.sh`, which the command used
