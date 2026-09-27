# How to test ACME job changes on staging

## Introduction

Use this before changing the `acme` job's invocation. It points the job at
the Let's Encrypt staging endpoint so a mistake cannot use up production
issuance, then switches back once the job is proven idempotent.

## Prerequisites

- A Terraform setup that can apply `deployments/infrastructure/`.
- The current setting of `var.acme_server`, see
  [ACME environment](../reference/tls-certificates.md#acme-environment).

## Directions

### Step 1: Point acme_server at staging and apply

To test changes to the job, point `acme_server` back at
`https://acme-staging-v02.api.letsencrypt.org/directory` and apply. Staging
certificates are untrusted by design, which is what makes them safe for
experiments. State is namespaced by environment, so the two keep separate
accounts and certificates under `/acme-state/staging` and
`/acme-state/production`, and switching does not disturb the other.

### Step 2: Prove idempotency on staging

Keep the [idempotency gate](../reference/tls-certificates.md#acme-environment)
in mind whenever the invocation changes. Let's Encrypt allows 5
certificates per exact set of names per 7 days, so a job that re-issues on
every run exhausts that in under a week and then cannot issue at all until the
window rolls forward. Prove idempotency on staging, then come back.
The [ACME environment](../reference/tls-certificates.md#acme-environment)
reference records what the proof looked like last time.

## Additional resources

- [TLS certificates](../reference/tls-certificates.md)
- [How to check the edge certificate](check-the-edge-certificate.md)
