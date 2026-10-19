---
description: Re-seed the driftwatch baseline after a deliberate embedding model change, so EmbeddingModelDrift stops firing.
stale_after: 2027-01-19
sources:
  - resource: deployments/applications/services/driftwatch.hcl
  - resource: deployments/applications/services/driftwatch/src/driftwatch/runner.py
---

# How to re-seed the driftwatch baseline

## Introduction

After a deliberate embedding model change, `EmbeddingModelDrift` keeps firing
until driftwatch measures against the new model. Re-seeding the baseline makes
the new model the reference.

## Prerequisites

- The model change confirmed as deliberate.
- The corpus in Postgres re-embedded with the new model. Until it is, the
  store is not trustworthy, so re-seed only after it.
- A Nomad token that can `alloc exec` into the `driftwatch` job.

## Directions

### Step 1: Delete the baseline

The file is on the `driftwatch_data` host volume, which the task mounts at
`/var/lib/driftwatch`. That path exists only inside the task, so delete the
file from there rather than over SSH on radxa:

```
nomad alloc exec -job driftwatch -task driftwatch \
  rm /var/lib/driftwatch/baseline.npz
```

### Step 2: Wait for two canary runs

The canary runs once a day. The next run writes a fresh baseline and
reports no cosine at all, which Grafana draws as a gap. The run after that
starts measuring drift against the new model.

## Additional resources

- [Retrieval quality reference](../reference/retrieval-quality.md)
- [How to respond to a retrieval-quality alert](respond-to-a-retrieval-quality-alert.md)
