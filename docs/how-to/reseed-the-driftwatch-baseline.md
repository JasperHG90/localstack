# How to re-seed the driftwatch baseline

## Introduction

After a deliberate embedding model change, `EmbeddingModelDrift` keeps firing
until driftwatch measures against the new model. Re-seeding the baseline makes
the new model the reference.

## Prerequisites

- The model change confirmed as deliberate.
- The corpus in Postgres re-embedded with the new model. Until it is, the
  store is not trustworthy, so re-seed only after it.
- SSH access to `radxa@192.168.2.50`.

## Directions

### Step 1: Delete the baseline

```
ssh radxa@192.168.2.50 sudo rm /var/lib/driftwatch/baseline.npz
```

### Step 2: Wait for two canary runs

The next run writes a fresh baseline and reports no cosine at all. The run
after that starts measuring drift against the new model.

## Additional resources

- [Retrieval quality reference](../reference/retrieval-quality.md)
- [How to respond to a retrieval-quality alert](respond-to-a-retrieval-quality-alert.md)
