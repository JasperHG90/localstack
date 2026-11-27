---
type: spike
title: Spike ovsq-keyless-local-sync/1
description: does SeaweedFS 4.48 STS refuse a StringEquals trust condition on a claim the token lacks, so ci-* and local-ov-sync (local_ov_sync + sub) roles each refuse the other token, and is local-ov-sync scoped to ov-sync/JasperHG90/local/?
tags:
- spike
generated:
  by: process:loopctl/2.4.0
  at: '2026-11-27T18:34:43+00:00'
slug: ovsq-keyless-local-sync
n: 1
outcome_written: true
---

# Spike ovsq-keyless-local-sync/1

does SeaweedFS 4.48 STS refuse a StringEquals trust condition on a claim the token lacks, so ci-* and local-ov-sync (local_ov_sync + sub) roles each refuse the other token, and is local-ov-sync scoped to ov-sync/JasperHG90/local/?

The command exited 0:

```
python3 -I /tmp/claude-1000/-home-vscode-workspace/6de16e53-8023-4b0e-a79f-982be17117b6/scratchpad/spike-ovsq/spike.py
```

## Outcome

Locally, with Vault 2.0.3 (dev mode) and SeaweedFS 4.48 (the pinned image), all 16 required checks passed and the run exited 0. A `StringEquals` condition on a claim the token lacks counts as no match: a `local_ov_sync`-only token got 403 "trust policy denies web identity assumption" from `ci-a-x` (`oidc:ci_repository = a/x`), and a `ci_repository`-only token with the operator's `sub` got the same 403 from `local-ov-sync`. A token with neither claim (only an unrelated one) was refused by both roles.
Controls: the `ci_repository = a/x` token did get `ci-a-x`, and the operator's `local_ov_sync = JasperHG90/local` token did get `local-ov-sync`, so each refusal came from the trust conditions. The same `local_ov_sync` claim from a second userpass entity (a different `sub`) was refused, so both `StringEquals` keys must match.
`local-ov-sync` credentials (Get/Put/Delete on `arn:aws:s3:::ov-sync/JasperHG90/local/*`) could put, get and delete under `JasperHG90/local/`, and got AccessDenied on put to `JasperHG90/localx/`, `JasperHG90/`, `a/x/` and the bucket root, and on delete of `a/x/seed.txt`.
This settles risk 2. Limits: plain-http issuer on a docker network, where production uses https://vault.lab.orangecluster.nl. Tokens came from userpass entities, and the claim names were set by hand in the spike, not rendered from Terraform.

## Files

- `run.json`: the command, when it ran, its exit, the commit and tree it ran on, and where its output went
- `stdout.txt`: its standard output
- `stderr.txt`: its standard error
- `files/spike.py`: a copy of `/tmp/claude-1000/-home-vscode-workspace/6de16e53-8023-4b0e-a79f-982be17117b6/scratchpad/spike-ovsq/spike.py`, which the command used
