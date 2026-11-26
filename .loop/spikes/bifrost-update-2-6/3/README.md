---
type: spike
title: Spike bifrost-update-2-6/3
description: does Bifrost 2.6.0 complete a TLS handshake with ollama.com, Gemini and typesafe (api.typesafe.ai) as configured in bifrost.hcl, as 2.3.1 does?
tags:
- spike
generated:
  by: process:loopctl/2.4.0
  at: '2026-11-26T14:00:41+00:00'
slug: bifrost-update-2-6
n: 3
outcome_written: true
---

# Spike bifrost-update-2-6/3

does Bifrost 2.6.0 complete a TLS handshake with ollama.com, Gemini and typesafe (api.typesafe.ai) as configured in bifrost.hcl, as 2.3.1 does?

The command exited 0:

```
/home/vscode/spike-scratch/bifrost-3/run.sh
```

## Outcome

On both 2.6.0 and 2.3.1, with the `bifrost.hcl` provider blocks and bogus keys, every upstream answered with an HTTP error after TLS: Gemini 400 `API key not valid`, typesafe (default `https://api.typesafe.ai`) 401 `authentication_error`, and ollama.com 502 `upstream_credentials_exhausted`. Bifrost returns that last one only after every key gets a permanent per-key HTTP error. No response or log line held an x509 or certificate error.
A negative control showed a TLS failure would not be hidden. The same ollama block pointed at `untrusted-root.badssl.com` returned 502 `provider_connection_failed` with `x509: certificate signed by unknown authority` on both versions.
This rules out an x509 chain rejection by Go 1.27.3 for these three hosts. It settles risk 2.
Limits: this ran from the devcontainer's network on 2026-11-26. It used Docker's arm64 images, not the cluster nodes, so a CDN serving a different chain per region is not covered. It sent one call per provider, with chat for ollama and Gemini and `/v1/decisions` for typesafe.

## Files

- `run.json`: the command, when it ran, its exit, the commit and tree it ran on, and where its output went
- `stdout.txt`: its standard output
- `stderr.txt`: its standard error
- `files/run.sh`: a copy of `/home/vscode/spike-scratch/bifrost-3/run.sh`, which the command used
- `files/config.json`: a copy of `/home/vscode/spike-scratch/bifrost-3/config.json`, which the command used
