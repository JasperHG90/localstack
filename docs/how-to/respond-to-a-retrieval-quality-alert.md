# How to respond to a retrieval-quality alert

## Introduction

Each rule in the `retrieval-quality` alert group points at a different part of
the retrieval stack. Find the rule that fired below and follow its check.

## Prerequisites

- A Grafana login, from
  [How to sign in to Grafana](sign-in-to-grafana.md).
- The metrics these rules read, listed in
  [Retrieval quality](../reference/retrieval-quality.md).

## Directions

### Step 1: Follow the check for the rule that fired

**EmbeddingModelDrift.** Find out whether the model change was deliberate. If
it was, the corpus in Postgres has to be re-embedded before the store is
trustworthy, and only then should the baseline be re-seeded, as
[How to re-seed the driftwatch baseline](reseed-the-driftwatch-baseline.md)
shows.

**RerankCanaryDrop.** The reranker got worse on a pool that did not change,
so this is the rerank model and not the shortlist it was handed. Check the
rerank model pin in `services/embark/models.json` and its quantization.
`RerankDemotesAnswers` stays quiet through this whenever the reranker is still
beating a bare cosine ordering, which is why the two rules are separate.

**PipelineRecallDrop.** The delivered result got worse. Read it beside the
other two: if `embedding` and `rerank` both held, the reranker degraded on
inputs only the embedder produces, which neither of the other rerank rules can
see. `RerankCanaryDrop` watches a pool that never changes, and
`RerankDemotesAnswers` only fires once the reranker is ranking worse than bare
cosine.

**CanaryRecallDrop with a steady cosine.** The vectors did not move but the
ranking did. Look at the retrieval settings the job sets rather than at the
model: `OV_RETRIEVAL_*` in `deployments/applications/services/openviking.hcl`
governs the keyword leg, the fusion constant and the diversity pass.

**EmbeddingNormsUnstable.** A preprocessing fault. Compare the embark image
pin against `services/embark/models.json`, and check that the ModelKit the
prestart task pulled is the one the config asks for.

**OpenVikingRerankFallback.** The rerank path is embark reached through
Bifrost. Check both: `/d/localstack-embark` for the model, and the Bifrost
dashboard for the gateway.

**CanaryStale.** No successful run in 48 hours, so every quality number is
older than it looks and the drift alerts are comparing today against a
fortnight that stopped moving. A driftwatch that has never succeeded reads the
same way, because the gauge starts at zero. Check
`driftwatch_runs_total{outcome="error"}` and the task logs.

## Additional resources

- [Retrieval quality reference](../reference/retrieval-quality.md)
- [The retrieval-quality canary](../explanation/retrieval-quality-canary.md)
