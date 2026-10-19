---
description: See when the edge's wildcard certificate last renewed, whether the nightly acme job succeeded, and whether clients trust it.
stale_after: 2027-01-19
sources:
  - resource: deployments/infrastructure/services/acme.hcl
  - resource: deployments/infrastructure/services.tf
  - resource: deployments/infrastructure/services/haproxy.hcl
---

# How to check the edge certificate

## Introduction

Use this to see when the wildcard certificate last renewed, whether the
nightly `acme` job succeeded, and whether clients trust what the edge serves.

## Prerequisites

- A Vault and Nomad session, from `localstack login` (see
  [`localstack login`](../reference/cli-login.md)).
- `openssl` and `curl`, on the LAN or the tailnet.

## Directions

### Step 1: Check when it last renewed and what is stored

```bash
vault kv get -field=certificate secret/default/haproxy/tls \
  | openssl x509 -noout -issuer -subject -dates -ext subjectAltName
```

The issuer should be a Let's Encrypt intermediate. If it names
`(STAGING)` anything, the job is still pointed at the staging endpoint.

### Step 2: Check that last night's run succeeded

`acme` is a periodic job that runs at 04:00 Amsterdam time each day. `nomad job status acme`
lists the runs it launched, each a child job named `acme/periodic-<id>`. Take
the newest, find its allocation, and read the `store` task's log:

```bash
nomad job status acme
nomad job status acme/periodic-<id>
nomad alloc logs <alloc-id> store
```

A good run ends with `stored <name> to secret/default/haproxy/tls`.

A successful run that had nothing to do still exits 0 and the store task still
republishes the existing certificate, so a green run does not by itself mean a
renewal happened. Check the certificate dates for that.

### Step 3: Check that the certificate a client sees validates

```bash
curl -sS -o /dev/null -w '%{http_code}\n' https://grafana.lab.orangecluster.nl/
```

No `-k`, no `--cacert`. Needing either means the certificate is not publicly
trusted and something is wrong.

## Additional resources

- [TLS certificates](../reference/tls-certificates.md)
- [How to recover a failed certificate renewal](recover-a-failed-certificate-renewal.md)
