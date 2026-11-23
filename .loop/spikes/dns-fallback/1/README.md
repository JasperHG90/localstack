---
type: spike
title: Spike dns-fallback/1
description: do NetworkManager 1.36 on orange_pi_4a and 1.46 on radxa document and parse a conf.d global-dns drop-in with servers and options, and does NM write resolv.conf itself on both, read-only with no reload
tags:
- spike
generated:
  by: process:loopctl/2.4.0
  at: '2026-11-23T22:12:12+00:00'
slug: dns-fallback
n: 1
outcome_written: true
---

# Spike dns-fallback/1

do NetworkManager 1.36 on orange_pi_4a and 1.46 on radxa document and parse a conf.d global-dns drop-in with servers and options, and does NM write resolv.conf itself on both, read-only with no reload

The command exited 1:

```
/tmp/claude-1000/-home-vscode-workspace/db4d3754-e336-4dc3-9c87-72f6ad3fd0c2/scratchpad/spike-dns/check.sh
```

## Outcome

Superseded by spike 2. The evidence was the same, but one check was wrong. On radxa (NM 1.46.0) the
"global DNS overrides connection DNS" grep looked for the 1.36 wording only. The 1.46 man page says
"the name servers and domains defined globally override the ones from active connections". The
other 13 checks passed on both nodes. This run shows nothing against the mechanism.

## Files

- `run.json`: the command, when it ran, its exit, the commit and tree it ran on, and where its output went
- `stdout.txt`: its standard output
- `stderr.txt`: its standard error
- `files/check.sh`: a copy of `/tmp/claude-1000/-home-vscode-workspace/db4d3754-e336-4dc3-9c87-72f6ad3fd0c2/scratchpad/spike-dns/check.sh`, which the command used
