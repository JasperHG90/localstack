# driftwatch

A daily canary over the two models the retrieval stack runs on. It embeds a
fixed set of 30 questions and the 60 documents that answer them, ranks each
question against the whole corpus, reranks the shortlist, and publishes what it
measured as Prometheus gauges.

The dashboard is **Retrieval Quality (Drift Canary)**,
`/d/localstack-retrieval-quality`. The alerts are the `retrieval-quality` group
in `deployments/infrastructure/services/grafana/alert-rules.yaml`.

## What it measures, and why each one is here

| Series | Catches |
|---|---|
| `driftwatch_recall{stage,k}`, `driftwatch_mrr{stage}` | The ranking getting worse, per stage. See below. |
| `driftwatch_reference_cosine_mean`, `_min` | The served model changing under a store full of vectors the old model wrote. |
| `driftwatch_embedding_norm_mean`, `_stddev` | Preprocessing faults cosine is blind to: a dropped normalization, a truncation, a tokenizer change. |
| `driftwatch_neighbor_overlap` | The embedder losing the ability to tell queries apart. Rises before recall falls. |
| `driftwatch_runs_total{outcome}`, `_last_success_timestamp_seconds` | The canary itself having stopped, which would otherwise leave a green dashboard of stale numbers. |
| `driftwatch_stage_seconds{stage}`, `driftwatch_run_seconds` | Whether the run hit embark's cache. A sudden expensive run means the model artifact changed. |

## The three stages

| `stage` | What it scores | Moves when |
|---|---|---|
| `embedding` | Every canary query against the whole 60-document corpus, by cosine. | The embedder changes. |
| `pipeline` | The embedder's top 10, reordered by the cross-encoder. What a caller gets. | Either model changes. |
| `rerank` | The cross-encoder over ten candidates fixed per query in `rerank-goldset.jsonl`. | The reranker changes, and nothing else. |

`pipeline` alone cannot attribute a regression: its candidates come from the
embedder, so a drop there could be either model. `rerank` is the fix. Its pool
is the same ten documents every run whatever the embedder does, so `rerank`
falling while `embedding` holds is a reranker regression, and the reverse is
an embedder regression.

`rerank` publishes k of 1, 3 and 5 rather than 1, 5 and 10. Every ranking of a
pool that holds the answer puts it at 10 or better, so recall@10 would read
1.0 on any run that scored anything at all. It is not strictly constant, since
a response that scores nothing records rank 11, but the lower k already go to
zero in that case.

NDCG is deliberately absent. Every query here has exactly one relevant
document, so NDCG@k collapses to `1 / log2(rank + 1)`, a monotone function of the
rank MRR already reports.

## The baseline

`/var/lib/driftwatch/baseline.npz` on radxa, on the `driftwatch_data` host
volume. The first successful run writes it; every run after that compares
against it.

A run that has just seeded reports `NaN` for the two cosine series rather than
the 1.0 it would trivially measure against itself. Grafana draws a gap and no
alert fires, which is what "not measured yet" should look like.

**After a deliberate model change:** re-embed the corpus in OpenViking first,
then delete the file. The next run seeds a new baseline and the one after it
starts measuring drift against the new model.

```
ssh radxa@192.168.2.50 sudo rm /var/lib/driftwatch/baseline.npz
```

Changing `goldset.jsonl` needs no such step. The file records how many
documents it was written against, so a different corpus is refused and
re-seeded automatically.

## The canary sets

`goldset.jsonl`, one `{"query", "positive", "negative"}` object per line. That
is the format `embark_forge.goldset` already reads, so this file and the one
embark's own quantization gate uses are the same artifact in the same shape.

The 30 rows are every second row of embark's `goldsets/embark-docs/eval.jsonl`,
which spreads the sample across its topics rather than taking the first half.
The corpus is the deduplicated union of both document columns, so a negative is
a plausible distractor another query's answer has to outrank, not a row that
gets ignored.

`rerank-goldset.jsonl` holds the same 30 queries, each with a fixed pool of
ten: its own answer, the hard negative embark hand-authored for it, then the
four rows after it contributing their negative before their positive, wrapping
at the end. The pool is rotated left by the row's index modulo ten, so the
answer sits at a different slot in every row and an off-by-one in the rank
arithmetic cannot score a perfect run.

`build_rerank_goldset.py` is that rule as code, and `just rerank-goldset
<path-to-embark>/goldsets/embark-docs/eval.jsonl` runs it. Rebuild whenever
`goldset.jsonl` changes: the two sets must cover the same queries, and
`test_the_rerank_pool_holds_the_hard_negative_for_its_query` fails when they
drift apart.

The hard negative is the point. A cross-encoder's failure mode is the
adjacent, plausible, wrong answer, and a pool of other rows' answers does not
supply one. embark's gold set already carries one per query, hand-written, and
this set is where it gets used.

Both are rendered into the job by `services.tf`, not baked into the image:
changing which queries are watched is a `terraform apply`. Changing the
embedding set re-seeds the baseline; changing the rerank set costs nothing,
because that stage holds no state between runs.

## Why it dials embark directly

Bifrost drops `input_type`, and that field picks the model's query prefix over
its document prefix. A bi-encoder embedded with the wrong one retrieves worse
and reports nothing. Measuring the model means talking to the model.

The gateway path stays measured from the other side: OpenViking's own
`openviking_embedding_call_duration_seconds` is these same models through
Bifrost, so the gap between the two dashboards is the gateway's contribution.

embark's firewall already admits radxa on port 8000
(`local.firewall_rules.embark`), so this needs no new rule.

## Building the image

There is no CI for this. Build and push by hand, the same way embark and
OpenViking are built:

```
just build
just push
```

The tag comes from the one `driftwatch_image` line in
`deployments/applications/services.tf`, so what is built and what is deployed
cannot drift. `--platform linux/arm64` because it runs on radxa.

## Running it locally

```
uv run pytest
uv run ruff check . && uv run ruff format --check .
uv run mypy src tests
```

The default test run needs no network and no models: the HTTP boundary is
faked with respx and everything above it is the real code.

## Deploy order

Infrastructure first, then applications. The `driftwatch_data` host volume is
a `nomad_dynamic_host_volume` in `deployments/infrastructure`, and this job
mounts it, so applying the applications root first registers a job that no
node can satisfy and leaves the alloc pending.

That root also carries the `ScrapeJobMissing` alert, which now asserts a
`driftwatch` scrape job exists. Between the two applies there is a window
where the volume is there and the service is not, and the alert fires. It
clears about one evaluation cycle after the job registers in Consul, so keep
the second apply prompt rather than reordering around it.
