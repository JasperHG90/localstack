---
type: component
title: driftwatch, the retrieval-quality canary
description: "How the daily driftwatch canary is put together: a small Python service on radxa that calls embark directly, two gold sets rendered in by Terraform, a baseline file on a host volume that re-seeds itself on some changes and not others, and alert rules that mix 14-day trends with fixed thresholds."
tags: [driftwatch, retrieval, canary, embark, embeddings, rerank, alerting]
status: stable
generated:
  by: claude-opus/5.5
  at: 2026-09-27
sources:
  - id: driftwatch-jobspec
    resource: git:3ec5d1e:deployments/applications/services/driftwatch.hcl
  - id: driftwatch-readme
    resource: git:3ec5d1e:deployments/applications/services/driftwatch/README.md
  - id: driftwatch-baseline
    resource: git:3ec5d1e:deployments/applications/services/driftwatch/src/driftwatch/baseline.py
  - id: driftwatch-runner
    resource: git:3ec5d1e:deployments/applications/services/driftwatch/src/driftwatch/runner.py
  - id: app-services
    resource: git:3ec5d1e:deployments/applications/services.tf
  - id: app-secrets
    resource: git:3ec5d1e:deployments/applications/secrets.tf
  - id: infra-services
    resource: git:3ec5d1e:deployments/infrastructure/services.tf
  - id: alert-rules
    resource: git:3ec5d1e:deployments/infrastructure/services/grafana/alert-rules.yaml
    note: "The working tree differs from 3ec5d1e (uncommitted operator edits), and this concept describes the working tree."
  - id: observability-commit
    resource: git:2411a2f
---

# driftwatch, the retrieval-quality canary

driftwatch runs once a day, embeds and reranks a fixed set of 30 questions
against 60 documents, and publishes what it measured as Prometheus gauges. It
answers one question: are the two retrieval models still as good as they were?
The user-facing pages are `docs/reference/retrieval-quality.md` (the series and
panels) and `docs/explanation/retrieval-quality-canary.md` (why it is shaped
this way). This page covers how it is wired and what a maintainer can break.

It landed with the embark and OpenViking dashboards in `2411a2f` (2026-09-08)
and has not been ticketed through `.loop`.

## The pieces

| Piece | Where |
|---|---|
| Jobspec | `deployments/applications/services/driftwatch.hcl` |
| Source, tests, `pyproject.toml`, `uv.lock` | `deployments/applications/services/driftwatch/` |
| Gold sets | `goldset.jsonl` and `rerank-goldset.jsonl` in the same directory |
| Rerank set builder | `build_rerank_goldset.py`, run by `just rerank-goldset` |
| Image build | the `Dockerfile` and `justfile` there, tag read from `driftwatch_image` in `services.tf` |
| Terraform wiring | `local.driftwatch_*` and `nomad_job.driftwatch` in `deployments/applications/services.tf` |
| embark key copy | `default/driftwatch/embark` in `deployments/applications/secrets.tf` |
| Baseline volume | `nomad_dynamic_host_volume.driftwatch_data` in `deployments/infrastructure/services.tf` |
| Firewall | `local.firewall_rules.driftwatch`: port 8010 from radxa and `ubuntu` only |
| Dashboard and alerts | `grafana/retrieval-quality.json`, the `retrieval-quality` group in `alert-rules.yaml` |

The job runs on `radxa-dragon-q6a` (192.168.2.50), port 8010. Prometheus finds
it through the `prometheus` Consul tag on the shared `consul_services` job.

## Apply order

Infrastructure first, then applications. The host volume is in the
infrastructure root, and a job registered before it stays pending. The
infrastructure root also holds `ScrapeJobMissing`, which asserts that a
`driftwatch` scrape job exists. driftwatch is found through Consul, so the
alert fires if the job is still unregistered 10 minutes after the
infrastructure apply, and clears once it registers. In the applications
root the job `depends_on` `nomad_job.embark` and the key secret.

## Design points that are easy to undo by accident

- **It calls embark at `http://192.168.2.46:8000`, not Bifrost.** Bifrost drops
  `input_type`, which picks the model's query prefix over its document prefix,
  so a canary behind the gateway would measure the wrong thing and say nothing.
  The model names are embark's own served names, `embedding` and `reranker`,
  the keys of `embark/models.json`, not Bifrost's `embark/...` aliases. embark's
  firewall already admits radxa, so no new rule was needed.
- **It runs on radxa, not the Jetson,** to stay off the node it measures.
- **It is cheap because embark caches.** embark keys its Redis cache on a
  fingerprint of the served model artifact, so a second run against an
  unchanged model is answered from cache and costs no GPU time. A model change
  makes the next run slow, and `driftwatch_run_seconds` shows it.
- **The key is a file, read every run.** `secrets/embark.key` is not an env
  var, so a rotated key is picked up at the next run without a restart. It is
  embark's `read` key, copied under driftwatch's own prefix because the
  `nomad-workloads` role lets a job read only that.
- **The health check is `/healthz`.** The first run against a cold cache takes
  minutes, and a readiness check would restart the task into the same wait.

## The gold sets

Both files are rendered into the job at deploy time, so changing
which queries are watched is a `terraform apply`. `services.tf` splits each
file on newlines and round-trips every row through `jsondecode` and
`jsonencode`. A malformed row fails the plan, and each row comes out as one
compact line, which the JSONL reader needs.

`goldset.jsonl` is every second row of embark's own
`goldsets/embark-docs/eval.jsonl`, in the `{"query", "positive", "negative"}`
shape embark's quantization gate reads. The corpus is the deduplicated union
of both document columns. `rerank-goldset.jsonl` gives each of the same 30
queries a fixed pool of ten, including the hand-written hard negative, rotated
so the answer is at a different slot in each row. It is generated by
`build_rerank_goldset.py` and must be rebuilt whenever `goldset.jsonl` changes.
`test_the_rerank_pool_holds_the_hard_negative_for_its_query` fails when the
two drift apart.

The fixed pool is what lets a regression be attributed. The `pipeline` stage
reranks the embedder's shortlist, so a drop there could be either model. The
`rerank` stage sees the same ten documents whatever the embedder does.

## The baseline, and when it re-seeds

`/var/lib/driftwatch/baseline.npz` on the `driftwatch_data` volume holds the
corpus vectors from the first successful run. Every later run compares
against it for `driftwatch_reference_cosine_*`. The volume exists so a
restart does not re-seed and hide drift for a day.

Re-seeding happens in three ways, and only one of them is an operator step:

| Change | What happens |
|---|---|
| Document count changes (a new `goldset.jsonl`) | `baseline.read` refuses the file, and the runner writes a new one |
| Vector width changes (an embedder with a new dimension) | `scoring.reference_cosine` raises on the shape, and the runner writes a new one |
| Same width, different model | nothing automatic, and drift fires until someone deletes the file |

The second row matters for the next embedder swap. A dimension change re-seeds
silently, so `EmbeddingModelDrift` will not fire for it. A same-dimension swap
fires until the operator re-embeds OpenViking's collection and deletes the
file, in that order: `docs/how-to/reseed-the-driftwatch-baseline.md`. The run
that seeds reports `NaN` for the cosine series, which Grafana draws as a gap.

`baseline.py`'s module docstring says the file records the vector width and
that the reader refuses a width change. The reader checks the document count
only, and the width check happens in `runner.py` as described above.

## The alerts

The `retrieval-quality` group in
`deployments/infrastructure/services/grafana/alert-rules.yaml` evaluates every
five minutes. Its header comment says every rule compares against the last
fortnight, and the rules below it do not all agree:

- Five driftwatch rules compare today against a 14-day average, because 60
  documents of embark's own docs is not a benchmark and says only whether the
  number moved. They carry `for: 26h`, one daily run plus slack, so two
  consecutive runs must agree.
- `EmbeddingModelDrift`, the one critical rule, is a fixed floor:
  `driftwatch_reference_cosine_mean < 0.92` for 1h.
- `RerankDemotesAnswers` compares the `pipeline` stage against the `embedding`
  stage in the same run.
- `CanaryStale` fires when no run has succeeded for more than 48 hours. The same
  group holds three OpenViking retrieval rules that read OpenViking's metrics
  rather than driftwatch's. What to do when one fires is
  `docs/how-to/respond-to-a-retrieval-quality-alert.md`.

The 26h figure on the trend rules is tied to `DRIFTWATCH_INTERVAL_SECONDS =
"86400"` in the jobspec. Changing the cadence without changing `for` makes the
rules either flap or never fire.

## Invariants and what enforces them

| Must stay true | Enforced by |
|---|---|
| Gold set rows parse | `jsondecode` at plan time |
| Both gold sets cover the same queries | the driftwatch test suite |
| driftwatch calls embark, not Bifrost | nothing but the comments |
| Model names match `embark/models.json` keys | nothing, and a mismatch fails every run until `CanaryStale` fires |
| Alert `for` matches the run interval | nothing |
| Image built equals image deployed | the `justfile` reading the `driftwatch_image` line |

The test suite runs with `uv run pytest` inside the service directory and
needs no network. No pre-commit hook and no CI workflow in this repository
runs it.

## Related

- [embark](/components/embark.md)
- [The observability pipeline](/components/observability-pipeline.md)
- [Host volumes](/components/host-volumes.md)
