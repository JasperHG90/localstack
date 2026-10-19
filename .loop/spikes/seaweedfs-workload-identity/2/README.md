---
type: spike
title: Spike seaweedfs-workload-identity/2
description: can a SeaweedFS STS trust policy bind a role to one Nomad job via the nomad_job_id or sub claim, so another job is refused?
tags:
- spike
generated:
  by: process:loopctl/2.2.2.dev1+gd84319696
  at: '2026-10-19T17:58:52+00:00'
slug: seaweedfs-workload-identity
n: 2
outcome_written: true
---

# Spike seaweedfs-workload-identity/2

can a SeaweedFS STS trust policy bind a role to one Nomad job via the nomad_job_id or sub claim, so another job is refused?

The command exited 0:

```
uv run --no-project -q /tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/spike-wi-1/spike_wi.py
```

## Outcome

On SeaweedFS 4.48 with a fake Nomad-shaped OIDC issuer, a role trust policy with `StringEquals {"oidc:nomad_job_id": "tempo"}` and `StringLike {"oidc:sub": "global:default:tempo:*"}` (Principal `{"Federated": "nomad"}`, the provider name) binds the role to one job: all 17 required checks passed, exit 0.
A loki token (aud `seaweedfs`) asking for TempoRole gets 403 "trust policy denies web identity assumption", while the same token gets an unconditioned control role, so the refusal comes from the claim condition. A tempo job in namespace `prod`, a token signed with a rogue key, and an `aud=minio` token are all refused. TempoRole creds put/get/list `tempo` and get AccessDenied on `loki`, and LokiRole the reverse.
`roleMapping` is not used on the STS path: no RoleArn without `policyClaim` gives "RoleArn is required". On the Bearer path a loki JWT gets 403 on `tempo`, and a roleMapping rule deliberately pointing at TempoRole is still refused by its trust policy.
Alternative: provider `policyClaim: "nomad_job_id"` lets a call with no RoleArn get the policy named after the job (MinIO's model) and scoped correctly, but the claim is split on commas, so a job ID `evil,tempo` got tempo's access. Prefer the trust-policy roles, or check that Nomad forbids commas in job IDs.
This settles risk 1 for the keyless design. Limits: the issuer was fake (plain http, one RS256 key), and RoleSessionName is required, which is the client-fit risk.

## Files

- `run.json`: the command, when it ran, its exit, the commit and tree it ran on, and where its output went
- `stdout.txt`: its standard output
- `stderr.txt`: its standard error
- `files/spike_wi.py`: a copy of `/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/spike-wi-1/spike_wi.py`, which the command used
