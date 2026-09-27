# How to verify an OpenViking deployment

## Introduction

`scripts/check_openviking_config.py` does **not** measure anything about a
running service. These checks need a deployment and nothing in this repo
automates them. Run them after an apply.

## Prerequisites

- A Vault login that can mint an OpenViking token, see
  [How to call OpenViking from the CLI](call-openviking-from-the-cli.md).
- `OV_URL` set to `https://openviking-api.lab.orangecluster.nl`.
- `python3` and a checkout of this repo, for the scripts under `scripts/`.

## Directions

### Step 1: Confirm an unauthenticated call is refused

An unauthenticated call is refused. This is the one that justifies opening
1933 to the LAN, so it is the one to run first after an apply.

```console
$ curl -s -o /dev/null -w "%{http_code}" "$OV_URL/api/v1/fs/ls"   # expect 401
```

### Step 2: Check the service is up

The service is up and its backends opened.

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

The whole identity chain, both directions. Asserts the token is accepted and
reaches its OWN tree, that no credential and a foreign audience are refused,
and reports whether an account that was never created is usable.

```console
$ python3 scripts/ov_identity_probe.py --account lab --user jasper
```

### Step 6: Check embeddings reach embark

Embeddings reach embark through the gateway.

```console
$ python3 scripts/bifrost_smoke.py
```

### Step 7: Check rerank reaches embark

Rerank reaches embark, in the bare-string shape OpenViking sends.
`bifrost_smoke.py` does NOT cover this: its rerank calls assert a 401 and
deliberately send the object form, so a green run says nothing about it.

```console
$ python3 scripts/embark_rerank.py
```

### Step 8: Time an authenticated call

How long an authenticated call takes. Unmeasured. Under oidc the cost per
request is JWT signature verification rather than an Argon2id hash, and the
JWKS is fetched over the network at request time, so the number is worth
having on an SBC. Record what this comes out at.

```console
$ OV_TOKEN=$(vault read -field=token identity/oidc/token/openviking)
$ curl -s -o /dev/null -w "%{time_total}\n" \
    -H "Authorization: Bearer $OV_TOKEN" "$OV_URL/api/v1/fs/ls?uri=viking://"
```

If that latency turns out unacceptable, the thing to change is the guard in
`scripts/check_openviking_config.py`, which now forbids turning the hashing
off. That is deliberate: the trade is worth making in the open.

## Additional resources

- [OpenViking](../reference/openviking.md), including what the config guard
  asserts
- [OpenViking identity](../explanation/openviking-identity.md)
