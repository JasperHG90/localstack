---
type: spike
title: Spike ov-sync-consumer/1
description: does prek 0.5.6 run a local golang-language hook running go vet and go test in a module under applications/ with no system Go, fetching the toolchain itself, in a main checkout and a fresh git worktree?
tags:
- spike
generated:
  by: process:loopctl/2.2.2.dev1+gd84319696
  at: '2026-11-15T19:53:50+00:00'
slug: ov-sync-consumer
n: 1
outcome_written: true
---

# Spike ov-sync-consumer/1

does prek 0.5.6 run a local golang-language hook running go vet and go test in a module under applications/ with no system Go, fetching the toolchain itself, in a main checkout and a fresh git worktree?

The command exited 0:

```
/tmp/claude-1000/-home-vscode-workspace/39954680-d360-4c77-9baf-bede6c6eafa0/scratchpad/spike-ovc3/spike.sh
```

## Outcome

With no system `go`, prek 0.5.6 ran a local `language: golang` hook (`bash -c 'cd applications/demo && go vet ./... && go test ./...'`, `pass_filenames: false`) and passed: it fetched Go 1.27.4 linux/arm64 itself on a cold `PREK_HOME` in about 10 s total, cached at `$PREK_HOME/tools/go/1.27.4` (271 MB; default home is `~/.cache/prek`). Warm reruns took under 1 s.
A failing test made the hook fail (exit 1, `--- FAIL: TestAdd`), and a fresh `git worktree add` checkout passed in 0.33 s on the shared cache.
This rules out the need for a devcontainer rebuild or a docker golang hook, so the docker fallback was not tried. Settles risk 3.
Limits: throwaway repo, module with no dependencies (module downloads untested). With no `language_version`, prek picked the latest Go, so pin one to keep it reproducible.

## Files

- `run.json`: the command, when it ran, its exit, the commit and tree it ran on, and where its output went
- `stdout.txt`: its standard output
- `stderr.txt`: its standard error
- `files/spike.sh`: a copy of `/tmp/claude-1000/-home-vscode-workspace/39954680-d360-4c77-9baf-bede6c6eafa0/scratchpad/spike-ovc3/spike.sh`, which the command used
