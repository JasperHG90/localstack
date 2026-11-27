---
type: spike
title: Spike bifrost-update-2-6/6
description: does Bifrost 2.7.0 complete a TLS handshake with ollama.com, Gemini and typesafe (api.typesafe.ai) as configured in bifrost.hcl, with 2.6.0 as control and an untrusted-root control showing an x509 failure would surface?
tags:
- spike
generated:
  by: process:loopctl/2.4.0
  at: '2026-11-27T10:48:30+00:00'
slug: bifrost-update-2-6
n: 6
outcome_written: true
---

# Spike bifrost-update-2-6/6

does Bifrost 2.7.0 complete a TLS handshake with ollama.com, Gemini and typesafe (api.typesafe.ai) as configured in bifrost.hcl, with 2.6.0 as control and an untrusted-root control showing an x509 failure would surface?

The command exited 0:

```
/home/vscode/spike-scratch/bifrost-27-3/run.sh
```

## Outcome

On 2.7.0 and the 2.6.0 control, with the `bifrost.hcl` provider blocks and bogus keys, every upstream answered with an HTTP error after TLS: Gemini 400 `API key not valid`, typesafe (default `https://api.typesafe.ai`) 401 `authentication_error`, and ollama.com 502 `upstream_credentials_exhausted`, which Bifrost returns only after every key gets a permanent per-key HTTP error. No response or log line held an x509 or certificate error.
The negative control shows a TLS failure would surface. The same ollama block pointed at `untrusted-root.badssl.com` returned 502 `provider_connection_failed` with `x509: certificate signed by unknown authority` on both versions.
Both images are built with go1.27.4, read from the buildinfo header of `/app/main` (2.7.0 `sha256:5d36913f...`, 2.6.0 `sha256:5968d007...`). That differs from the go1.27.3 that spike 3 recorded for 2.6.0. Release notes were not checked.
This rules out an x509 chain rejection by 2.7.0 for these three hosts. It settles risk 2.
Limits: one run from the devcontainer's network on 2026-11-27, on Docker's arm64 images rather than the cluster nodes, so a CDN serving a different chain per region is not covered. One call per provider.

## Files

- `run.json`: the command, when it ran, its exit, the commit and tree it ran on, and where its output went
- `stdout.txt`: its standard output
- `stderr.txt`: its standard error
- `files/run.sh`: a copy of `/home/vscode/spike-scratch/bifrost-27-3/run.sh`, which the command used
- `files/config.json`: a copy of `/home/vscode/spike-scratch/bifrost-27-3/config.json`, which the command used
- `files/gover.py`: a copy of `/home/vscode/spike-scratch/bifrost-27-3/gover.py`, which the command used
