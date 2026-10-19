---
description: "Check a deployed OpenViking after an apply: auth refusal, readiness, identity isolation, and the embark paths through Bifrost."
stale_after: 2027-01-19
sources:
  - resource: deployments/applications/services/openviking.hcl
  - resource: deployments/applications/services/ov-dash.hcl
  - resource: scripts/ov_identity_probe.py
  - resource: scripts/bifrost_smoke.py
  - resource: scripts/embark_rerank.py
  - resource: scripts/check_openviking_config.py
---

# How to verify an OpenViking deployment

## Introduction

Check a deployed OpenViking after an apply: that it refuses anonymous
calls, answers authenticated ones in the caller's own tree, and reaches
embark through Bifrost. `scripts/check_openviking_config.py` checks the
config statically and does **not** measure anything about a running
service. These checks need a deployment, and nothing in this repo automates
them.

## Prerequisites

- A Vault login that can mint an OpenViking token, see
  [How to call OpenViking from the CLI](call-openviking-from-the-cli.md).
- `OV_URL` set to `https://openviking-api.lab.orangecluster.nl`.
- `python3` and a checkout of this repo, for the scripts under `scripts/`.

## Directions

### Step 1: Confirm an unauthenticated call is refused

This is the check that justifies opening port 1933 to the LAN, so run it
first after an apply.

```console
$ curl -s -o /dev/null -w "%{http_code}" "$OV_URL/api/v1/fs/ls"   # expect 401
```

### Step 2: Check the service is up

`/ready` answers once the service is up and its backends are open. A clean
boot takes about two minutes, but a boot after an unclean stop can take
most of an hour (one took 44m46s), so a failing `/ready` soon after a
restart is not yet a fault. Nomad allows the deployment 60 minutes to turn
healthy.

```console
$ curl -s "$OV_URL/ready"
```

### Step 3: Confirm Studio is unmounted

Studio is unmounted, so this one is expected to fail with a 404.

```console
$ curl -s -o /dev/null -w "%{http_code}\n" "$OV_URL/studio/"   # expect 404
```

### Step 4: Check ov-dash answers

ov-dash answers on the short hostname. `/health` needs no session.

```console
$ curl -s -o /dev/null -w "%{http_code}\n" \
    https://openviking.lab.orangecluster.nl/health             # expect 200
```

### Step 5: Probe the identity chain

The probe tests the whole identity chain in both directions. It asserts that
the token is accepted and reaches its OWN tree, that a call with no
credential and one with a foreign audience are refused, and it reports
whether an account that was never created is usable.

```console
$ python3 scripts/ov_identity_probe.py --account lab --user jasper
```

### Step 6: Check embeddings reach embark

This checks that embeddings reach embark through the Bifrost gateway.

```console
$ python3 scripts/bifrost_smoke.py
```

### Step 7: Check rerank reaches embark

This checks that rerank reaches embark, in the bare-string shape OpenViking
sends. `scripts/bifrost_smoke.py` does NOT cover this: its rerank calls
assert a 401 and deliberately send the object form, so a green run says
nothing about it.

```console
$ python3 scripts/embark_rerank.py
```

### Step 8: Time an authenticated call

Time an authenticated call. Under `oidc` each request costs a JWT signature
check, and the JWKS is fetched over the network at request time, so the
number is worth knowing on a single-board computer.

```console
$ OV_TOKEN=$(vault read -field=token identity/oidc/token/openviking)
$ curl -s -o /dev/null -w "%{time_total}\n" \
    -H "Authorization: Bearer $OV_TOKEN" "$OV_URL/api/v1/fs/ls?uri=viking://"
```

## Additional resources

- [OpenViking](../reference/openviking.md), including what the config guard
  asserts
- [OpenViking identity](../explanation/openviking-identity.md)
