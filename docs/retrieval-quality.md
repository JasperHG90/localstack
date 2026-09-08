# Watching retrieval quality

Retrieval fails quietly. When an embedding model is swapped, requantized, or
loses a preprocessing step, every request still returns 200, every latency
panel stays flat, and the answers get worse. Three Grafana dashboards and one
small service exist to make that failure loud.

| Dashboard | Answers |
|---|---|
| `/d/localstack-embark` | Are the two models serving, and how fast? |
| `/d/localstack-openviking` | Is live retrieval finding and ranking things? |
| `/d/localstack-retrieval-quality` | Are the models still as good as they were? |

The first two read metrics the services already published. The third reads a
service built for it, `driftwatch`, which runs a fixed canary set through both
models once a day.

## The three failures worth naming

**The model changed.** New weights, a new quantization, a new prefix. The
vectors already in Postgres were written by the old model, so the store is now
mixing two embedding spaces and comparing them with cosine as though it were
not. `driftwatch_reference_cosine_mean` is what notices.

**The preprocessing changed.** A dropped normalization, a truncation, a
tokenizer that moved. Cosine cannot see any of these, because it divides
magnitude out. `driftwatch_embedding_norm_stddev` is what notices.

**The reranker stopped helping.** OpenViking asks embark to reorder a
shortlist. When that call fails, OpenViking serves the results in vector order
and reports no error at all. `openviking_retrieval_rerank_fallback_total` is
what notices, and `driftwatch_recall{stage="rerank"}` is what notices when the
reranker answers but answers badly.

## Reading the canary

driftwatch embeds 30 questions and the 60 documents that answer them, ranks
each question against the whole corpus, then hands the top 10 to the reranker
and looks at where the answer ended up. It then scores the reranker a second
time, on its own, against ten candidates fixed per query in a separate gold
set.

That second pass exists because the first cannot attribute a regression. A
reranker measured only on what the embedder shortlisted moves when the
*embedder* moves. The fixed pool is the same ten documents every run, so
`rerank` falling while `embedding` holds is the reranker, and the reverse is
the embedder. Each pool also carries the hard negative embark hand-authored
for that query: the adjacent, plausible, wrong answer a cross-encoder exists
to reject, which a corpus of other rows' answers does not supply.

- `driftwatch_recall{stage="embedding", k="10"}` is the headline: how often
  vector search alone puts the answer in its top 10.
- `driftwatch_recall{stage="pipeline", k="1"}` next to
  `driftwatch_recall{stage="embedding", k="1"}` says whether the cross-encoder
  earns its latency. The pipeline line below the embedding line means it is
  demoting right answers.
- `driftwatch_recall{stage="rerank", k="1"}` is the reranker on a pool the
  embedder never touched. It is the only number on the page that moves for the
  reranker and nothing else.
- `driftwatch_reference_cosine_mean` is today's vectors against the vectors
  recorded when the baseline was seeded.

Every alert on these compares today against the last fortnight rather than
against a fixed floor. Sixty documents of embark's own docs is not a
benchmark, so the absolute number means little; the change means everything.

`for: 26h` on the trend alerts is "two consecutive runs" written in the unit
Grafana understands, since the canary runs daily.

## What to do when one fires

**EmbeddingModelDrift.** Find out whether the model change was deliberate. If
it was, the corpus in Postgres has to be re-embedded before the store is
trustworthy, and only then should the baseline be re-seeded:

```
ssh radxa@192.168.2.50 sudo rm /var/lib/driftwatch/baseline.npz
```

The next run writes a fresh baseline and reports no cosine at all. The run
after that starts measuring drift against the new model.

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

## Where the numbers come from

| Service | Job label | Route |
|---|---|---|
| embark | `embark` | `:8000/metrics`, unguarded, found through the Consul `prometheus` tag |
| OpenViking | `openviking` | `:1933/metrics`, its one route with no auth dependency |
| driftwatch | `driftwatch` | `:8010/metrics`, found through the Consul `prometheus` tag |

embark's cache, coalescing and auth counters carry an `embark_` prefix; its
HTTP series come from prometheus-fastapi-instrumentator and carry the
library's `http_` names, so every query for them has to filter on
`job="embark"`.

Per-request cache counts and batch sizes are not in Prometheus at all. embark
sets them as `embark.*` attributes on the request span, so they are in Tempo,
reachable from any log line through the trace id.

## The panels that read from traces

The "Hybrid retrieval, from traces" row on `/d/localstack-openviking` is not
Prometheus. ov-postgres and ov-retrieval emit spans, Tempo keeps recent ones
queryable through its local-blocks processor, and Grafana runs TraceQL metrics
over them.

It earns its place by doing the one thing a counter cannot: aggregating a span
attribute's value. `avg_over_time(span.ov_retrieval.keyword_hits)` is how many
URIs the keyword leg contributed, a number that exists nowhere else.

The `outcome` attribute is the other half. Prometheus can show the funnel
collapsing; only the span says the pass declined to run and why.
`backend_lacks_similarity` means ov-postgres is too old to offer
`pairwise_similarity`, so hybrid retrieval quietly ranks without its diversity
pass and every other signal stays green.

Those panels are pinned to a 2-hour window and ignore the dashboard time
picker. Tempo rejects a TraceQL metrics query spanning more than 3 hours
(`metrics query time range exceeds the maximum allowed duration of 3h0m0s`),
and raising that cap would invite queries that scan days of blocks out of
MinIO. Traces are for the last few hours; Prometheus keeps the 30-day trend.

## Why driftwatch dials embark directly

Bifrost drops `input_type`, and that field picks the model's query prefix over
its document prefix. A bi-encoder embedded with the wrong one retrieves worse
and reports nothing.

The gateway path is still measured, from the other side:
`openviking_embedding_call_duration_seconds` is the same models through
Bifrost, so the gap between the two dashboards is what the gateway costs.

## What a canary cannot tell you

It ranks a fixed corpus that always contains the answer, so it cannot see a
live query finding nothing. That is what the zero-result panels on
`/d/localstack-openviking` are for, and they measure the corpus rather than
the model.

But a zero result is frequently the right answer. Nobody ingested anything
that answers the question, and retrieval correctly said so. Nothing in
Prometheus can tell that apart from retrieval failing to surface something
that is there, so `OpenVikingZeroResults` watches the change against the
trailing fortnight rather than any absolute level.

`OpenVikingNoCandidates` is the half that is unambiguous.
`openviking_vector_scanned_total` counts what each descent step handed back,
so a populated store returns candidates that then score badly, while an empty
or wrongly-scoped one returns none. Under one candidate per retrieval is not a
content gap, it is searching the wrong place. The likeliest cause here is
account scoping: an `ov_account` that was never created answers 200 over an
empty tree.

Neither can tell you that content was deleted, because no metric here records
an ingest. A canary that stays green while zero results climb narrows it to
the corpus, and the funnel narrows it again, but the last step is looking.

See also `docs/monitoring.md` for the stack itself, and
`deployments/applications/services/driftwatch/README.md` for how the canary set
is built and how the image is pushed.
