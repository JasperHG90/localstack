"""One evaluation run, and how its numbers reach the metric registry.

The run measures three stages across two canary sets:

`embedding` is the whole corpus ranked by cosine against each query -- what
the vector store does before anything else touches the results.

`pipeline` is what a caller actually gets: the embedding stage's top
candidates, reordered by the cross-encoder. Its recall can never beat what the
first stage handed it, so on its own it cannot say which half regressed.

`rerank` is the cross-encoder alone, over a candidate pool fixed in
`rerank-goldset.jsonl` rather than taken from the embedder. That is what makes
the attribution possible: `rerank` moving while `embedding` holds is a
reranker regression, and `embedding` moving while `rerank` holds is an
embedder regression. Measuring the reranker only through the embedder, which
is what `pipeline` does, cannot separate the two.

Its pool also carries the hard negative embark's gold set hand-authored for
each query: the adjacent, plausible, wrong answer. That is the input a
cross-encoder exists to reject, and one a corpus of other rows' answers does
not supply.

embark caches by a fingerprint of the served model artifact, so a run that
follows another with the same model is answered from Redis and costs no GPU
time. A model swap changes the fingerprint and the next run measures the new
model. That is why a daily canary against a fixed set is affordable here.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from numpy.typing import NDArray

from driftwatch import baseline as baseline_store
from driftwatch import scoring
from driftwatch.client import EmbarkClient
from driftwatch.goldset import Goldset, RerankCase
from driftwatch.metrics import Metrics

NEIGHBOR_K = 10
RECALL_KS = (1, 5, 10)
# The isolated rerank stage scores a pool of ten that always holds the answer.
# Every ranking it can produce puts the answer at 10 or better, so recall@10
# would read 1.0 on every run that scored anything at all. It is not constant --
# a response that scores nothing records rank 11 and drops it to 0 -- but the
# lower k already go to 0 in that case, so the series adds a flat line and no
# information.
RERANK_RECALL_KS = (1, 3, 5)


@dataclass(frozen=True)
class RunResult:
    """Everything one run measured."""

    embedding: scoring.RankingMetrics
    pipeline: scoring.RankingMetrics
    rerank: scoring.RankingMetrics
    norm_mean: float
    norm_stddev: float
    neighbor_overlap: float
    reference_cosine: tuple[float, float] | None
    baseline_recorded_at: float
    embed_seconds: float
    pipeline_seconds: float
    rerank_seconds: float
    total_seconds: float


def evaluate(
    client: EmbarkClient,
    goldset: Goldset,
    rerank_cases: list[RerankCase],
    *,
    embedding_model: str,
    rerank_model: str,
    baseline_path: Path,
    rerank_pool: int,
    now: float,
) -> RunResult:
    """Run both canary sets through all three stages and score the result."""
    started = time.monotonic()

    embed_started = time.monotonic()
    documents = client.embed(goldset.documents, model=embedding_model, input_type="document")
    queries = client.embed(goldset.queries, model=embedding_model, input_type="query")
    embed_seconds = time.monotonic() - embed_started

    scores = scoring.cosine_scores(queries, documents)
    embedding_metrics = scoring.metrics_from_ranks(
        scoring.ranks_from_scores(scores, goldset.targets), RECALL_KS
    )
    norm_mean, norm_stddev = scoring.norm_stats(documents)
    overlap = scoring.neighbor_overlap(scores, NEIGHBOR_K)

    reference, recorded_at = _compare_to_baseline(baseline_path, documents, now=now)

    pipeline_started = time.monotonic()
    pipeline_metrics = _pipeline_stage(
        client,
        goldset,
        scores,
        model=rerank_model,
        pool=rerank_pool,
    )
    pipeline_seconds = time.monotonic() - pipeline_started

    rerank_started = time.monotonic()
    rerank_metrics = _rerank_stage(client, rerank_cases, model=rerank_model)
    rerank_seconds = time.monotonic() - rerank_started

    return RunResult(
        embedding=embedding_metrics,
        pipeline=pipeline_metrics,
        rerank=rerank_metrics,
        norm_mean=norm_mean,
        norm_stddev=norm_stddev,
        neighbor_overlap=overlap,
        reference_cosine=reference,
        baseline_recorded_at=recorded_at,
        embed_seconds=embed_seconds,
        pipeline_seconds=pipeline_seconds,
        rerank_seconds=rerank_seconds,
        total_seconds=time.monotonic() - started,
    )


def _compare_to_baseline(
    path: Path, documents: NDArray[np.float32], *, now: float
) -> tuple[tuple[float, float] | None, float]:
    """Score the current vectors against the stored baseline, seeding one if needed.

    A run that just wrote the baseline reports no cosine at all rather than
    the 1.0 it would trivially measure against itself. An absent series reads
    as "not measured yet"; a 1.0 reads as "perfectly stable", and only one of
    those is true.
    """
    try:
        stored = baseline_store.read(path, documents=documents.shape[0])
    except baseline_store.BaselineMismatch:
        # A different corpus or a different vector width. Both mean the stored
        # vectors answer a question nobody asked any more, so the file is
        # replaced rather than repaired.
        stored = None

    if stored is None:
        written = baseline_store.write(path, documents, now=now)
        return None, written.recorded_at

    try:
        return scoring.reference_cosine(documents, stored.vectors), stored.recorded_at
    except ValueError:
        written = baseline_store.write(path, documents, now=now)
        return None, written.recorded_at


def _pipeline_stage(
    client: EmbarkClient,
    goldset: Goldset,
    scores: NDArray[np.float32],
    *,
    model: str,
    pool: int,
) -> scoring.RankingMetrics:
    """Rerank each query's shortlist and score where the answer ended up.

    Two cases are recorded as a miss at rank ``width + 1``, one past the
    widest k the shortlist can express: a query whose answer never made the
    shortlist, and a rerank response that scored none of the candidates it was
    sent. `width` is the shortlist size actually used, which is `pool` capped
    at the corpus size.

    The second case is not hypothetical padding. embark answers 200 with an
    empty `results` array when the reranker is loaded but cannot score, and
    without this every candidate would keep its -inf placeholder, tie, and
    land the answer at rank `width` -- publishing recall@10 of 1.0 for a total
    rerank failure.
    """
    width = min(pool, scores.shape[1])
    ranks: list[int] = []

    for query_index, query in enumerate(goldset.queries):
        row = scores[query_index]
        target = goldset.targets[query_index]
        shortlist = np.argsort(-row)[:width].tolist()
        if target not in shortlist:
            ranks.append(width + 1)
            continue

        candidates = [goldset.documents[index] for index in shortlist]
        hits = client.rerank(query, candidates, model=model)
        # A candidate the reranker did not score keeps -inf, so it sorts below
        # every scored one instead of silently tying at zero.
        reranked = np.full(len(candidates), -np.inf, dtype=np.float32)
        for hit in hits:
            if 0 <= hit.index < len(candidates):
                reranked[hit.index] = hit.score
        if not np.isfinite(reranked).any():
            ranks.append(width + 1)
            continue
        ranks.append(scoring.ranks_from_scores(reranked[None, :], [shortlist.index(target)])[0])

    return scoring.metrics_from_ranks(ranks, RECALL_KS)


def _rerank_stage(
    client: EmbarkClient,
    cases: list[RerankCase],
    *,
    model: str,
) -> scoring.RankingMetrics:
    """Score the reranker over the pool the gold set fixes, not one the embedder chose.

    A response that scored none of the candidates is a miss at one past the
    pool, the same rule `_pipeline_stage` applies and for the same reason: an
    all-`-inf` row ties, and a tie would otherwise land the answer mid-pool and
    read as a partial success.
    """
    ranks: list[int] = []

    for case in cases:
        hits = client.rerank(case.query, case.candidates, model=model)
        scored = np.full(len(case.candidates), -np.inf, dtype=np.float32)
        for hit in hits:
            if 0 <= hit.index < len(case.candidates):
                scored[hit.index] = hit.score
        if not np.isfinite(scored).any():
            ranks.append(len(case.candidates) + 1)
            continue
        ranks.append(scoring.ranks_from_scores(scored[None, :], [case.target])[0])

    return scoring.metrics_from_ranks(ranks, RERANK_RECALL_KS)


def apply(metrics: Metrics, result: RunResult) -> None:
    """Publish one run's numbers onto the registry."""
    for stage, ranking in (
        ("embedding", result.embedding),
        ("pipeline", result.pipeline),
        ("rerank", result.rerank),
    ):
        for k, value in ranking.recall_at.items():
            metrics.recall.labels(stage=stage, k=str(k)).set(value)
        metrics.mrr.labels(stage=stage).set(ranking.mrr)

    metrics.norm_mean.set(result.norm_mean)
    metrics.norm_stddev.set(result.norm_stddev)
    metrics.neighbor_overlap.set(result.neighbor_overlap)
    metrics.stage_seconds.labels(stage="embedding").set(result.embed_seconds)
    metrics.stage_seconds.labels(stage="pipeline").set(result.pipeline_seconds)
    metrics.stage_seconds.labels(stage="rerank").set(result.rerank_seconds)
    metrics.run_seconds.set(result.total_seconds)
    metrics.baseline_recorded.set(result.baseline_recorded_at)

    if result.reference_cosine is None:
        metrics.mark_reference_unmeasured()
    else:
        mean, worst = result.reference_cosine
        metrics.reference_cosine_mean.set(mean)
        metrics.reference_cosine_min.set(worst)
