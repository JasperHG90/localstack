---
description: "Test a change to the acme job against Let's Encrypt staging, prove it does not re-issue, and switch back to production."
stale_after: 2027-01-19
sources:
  - resource: deployments/infrastructure/services/acme.hcl
  - resource: deployments/infrastructure/services.tf
  - resource: deployments/infrastructure/variables.tf
---

# How to test ACME job changes on staging

## Introduction

Use this before changing the `acme` job's invocation. It points the job at
the Let's Encrypt staging endpoint so a mistake cannot use up production
issuance, then switches back once the job is proven idempotent.

## Prerequisites

- A Terraform setup that can apply `deployments/infrastructure/`, and a
  `localstack login` session for `eval "$(localstack env)"`.
- The current setting of `var.acme_server`, see
  [ACME environment](../reference/tls-certificates.md#acme-environment).

## Directions

### Step 1: Point acme_server at staging and apply

Set the staging endpoint in `deployments/infrastructure/vars/prod.tfvars`:

```hcl
acme_server = "https://acme-staging-v02.api.letsencrypt.org/directory"
```

Then apply only the job:

```sh
cd deployments/infrastructure
eval "$(localstack env)"
terraform apply -var-file=./vars/prod.tfvars -target=nomad_job.acme
```

Staging certificates are untrusted by design, which is what makes them safe
for experiments. State is namespaced by environment, so the two keep
separate accounts and certificates under `/acme-state/staging` and
`/acme-state/production`, and switching does not disturb the other.

**The edge serves the staging certificate while you test.** The job's
`store` task writes whatever bundle the run holds to `default/haproxy/tls`,
and HAProxy restarts on that change. Browsers warn on every
`*.lab.orangecluster.nl` site until step 3 puts the production bundle back.

### Step 2: Prove idempotency on staging

Keep the [idempotency gate](../reference/tls-certificates.md#acme-environment)
in mind whenever the invocation changes. Let's Encrypt allows 5
certificates per exact set of names per 7 days, so a job that re-issues on
every run exhausts that in under a week and then cannot issue at all until the
window rolls forward.

Run the job twice and read the `issue` task's log from each run:

```sh
nomad job periodic force acme
nomad job status acme                  # lists the child jobs, acme/periodic-<id>
nomad job status acme/periodic-<id>    # find the child's allocation ID
nomad alloc logs <alloc-id> issue
```

The first run issues a staging certificate. The second should report
`Skip renewal` with the certificate serial unchanged. If it issues again,
fix the job before going further.

### Step 3: Switch back to production

Remove the `acme_server` line from
`deployments/infrastructure/vars/prod.tfvars`, so the variable falls back to its production default, apply the job again
as in step 1, and run it once more with `nomad job periodic force acme`.
The production certificate is not due, so lego skips renewal and the
`store` task writes the production bundle back to `default/haproxy/tls`.

## Additional resources

- [TLS certificates](../reference/tls-certificates.md)
- [How to check the edge certificate](check-the-edge-certificate.md)
