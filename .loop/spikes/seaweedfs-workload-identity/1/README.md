---
type: spike
title: Spike seaweedfs-workload-identity/1
description: can SeaweedFS STS discover and parse Nomad workload identity JWKS (issuer match, key types, TLS trust)?
tags:
- spike
generated:
  by: process:loopctl/2.2.2.dev1+gd84319696
  at: '2026-10-19T17:53:57+00:00'
slug: seaweedfs-workload-identity
n: 1
outcome_written: true
---

# Spike seaweedfs-workload-identity/1

can SeaweedFS STS discover and parse Nomad workload identity JWKS (issuer match, key types, TLS trust)?

The command exited 0:

```
python3 -I /tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/spike-wi-3/check_discovery.py
```

## Outcome

Nomad's discovery document says issuer `https://nomad.lab.orangecluster.nl` and jwks_uri `https://nomad.lab.orangecluster.nl/.well-known/jwks.json`. That equals `{issuer}/.well-known/jwks.json`, so SeaweedFS's discovery step and its fallback both land on the same URL. The issuer matches exactly, which SeaweedFS's discovery issuer check requires.
The JWKS holds 4 keys, all `kty=RSA, alg=RS256`, with no OKP/EdDSA key, even though discovery advertises `RS256, EdDSA`. SeaweedFS 4.40 and 4.48 (identical `weed/iam/oidc/oidc_provider.go`) parse only `RSA` and `EC` keys and accept only RSA/ECDSA signing methods. That rules out a key-type mismatch today.
TLS verified against the system roots alone (public Let's Encrypt cert), so no `tlsCaCert` is needed. SeaweedFS uses `x509.SystemCertPool`, and its alpine image installs `curl`, which pulls in the CA bundle (read from the Dockerfile, not run).
Limits: this ran from the devcontainer, not from inside a SeaweedFS container on orangepi4a. Reachability from that node rests on MinIO, also on orangepi4a, fetching the same URL today. No real workload JWT header was inspected, so the claim that every token is RS256 rests on the JWKS holding only RSA keys.
Settles risk 3, as long as Nomad never adds an EdDSA key. If it does, SeaweedFS would reject the tokens with "unsupported key type: OKP".

## Files

- `run.json`: the command, when it ran, its exit, the commit and tree it ran on, and where its output went
- `stdout.txt`: its standard output
- `stderr.txt`: its standard error
- `files/check_discovery.py`: a copy of `/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/spike-wi-3/check_discovery.py`, which the command used
