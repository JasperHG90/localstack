---
type: spike
title: Spike ci-openviking-sync/1
description: does SeaweedFS 4.48 STS trust a Vault identity-token issuer, bind roles on a literal ci_repository claim, and enforce a per-prefix policy inside the shared ov-sync bucket?
tags:
- spike
generated:
  by: process:loopctl/2.2.2.dev1+gd84319696
  at: '2026-11-15T19:55:40+00:00'
slug: ci-openviking-sync
n: 1
outcome_written: true
---

# Spike ci-openviking-sync/1

does SeaweedFS 4.48 STS trust a Vault identity-token issuer, bind roles on a literal ci_repository claim, and enforce a per-prefix policy inside the shared ov-sync bucket?

The command exited 0:

```
python3 -I /tmp/claude-1000/-home-vscode-workspace/39954680-d360-4c77-9baf-bede6c6eafa0/scratchpad/spike-sync1/spike.py
```

## Outcome

Locally, with Vault 2.0.3 (the cluster's version, dev mode) and SeaweedFS 4.48, all 17 required checks passed and the run exited 0. SeaweedFS STS trusted Vault's identity issuer (`http://sync1-vault:8200/v1/identity/oidc`, client `seaweedfs`) as a second OIDC provider next to a `nomad` provider. Vault's tokens carried `aud: seaweedfs` and a literal `ci_repository`.
An `a/x` token got credentials for `ci-a-x` and got 403 "trust policy denies web identity assumption" for `ci-b-y`. A `b/y` token did get `ci-b-y`, so the refusal came from the `StringEquals oidc:ci_repository` condition. A token with `aud: openviking` was refused: "audience matches none of the configured client IDs".
`ci-a-x` credentials (GetObject, PutObject and DeleteObject on `arn:aws:s3:::ov-sync/a/x/*`), used through aws-cli 2.27.0, could put, get and delete under `a/x/`, `.okf/` included. They got AccessDenied on put, get and delete under `b/y/` (the `b/y` seed survived), and on `a/xx/`, `a/` and the bucket root. ListObjectsV2 was denied. A missing manifest gave NoSuchKey, not AccessDenied.
This settles the plan's one risk: prefix scope holds inside a shared bucket, and the Vault issuer is accepted.
Limits: the issuer was plain http on a docker network, where production uses https://vault.lab.orangecluster.nl. The Nomad provider pointed at an issuer that does not resolve and did not block startup. Tokens came from a userpass entity, not a jwt-github login.

## Files

- `run.json`: the command, when it ran, its exit, the commit and tree it ran on, and where its output went
- `stdout.txt`: its standard output
- `stderr.txt`: its standard error
- `files/spike.py`: a copy of `/tmp/claude-1000/-home-vscode-workspace/39954680-d360-4c77-9baf-bede6c6eafa0/scratchpad/spike-sync1/spike.py`, which the command used
