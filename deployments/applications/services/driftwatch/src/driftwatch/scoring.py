"""Turning two matrices of vectors into the numbers a dashboard can watch.

Everything here is pure: it takes arrays and returns floats, so the whole
measurement is testable without a model, a network or a clock.

Ties are broken against the document being measured -- a document that scores
exactly as well as the answer is counted as ranking above it. On float scores
a tie means two identical texts, and reporting the optimistic rank there would
let a model that cannot separate them look like one that can.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray


@dataclass(frozen=True)
class RankingMetrics:
    """How well one ranking stage put the answer near the top.

    Attributes
    ----------
    recall_at :
        Fraction of queries whose answer landed in the top k, keyed by k.
    mrr :
        Mean reciprocal rank over every query.
    """

    recall_at: dict[int, float]
    mrr: float


def unit(vectors: NDArray[np.float32]) -> NDArray[np.float32]:
    """Scale each row to length 1, leaving a zero row as it is."""
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    scaled: NDArray[np.float32] = (vectors / np.maximum(norms, 1e-12)).astype(np.float32)
    return scaled


def cosine_scores(
    queries: NDArray[np.float32], documents: NDArray[np.float32]
) -> NDArray[np.float32]:
    """Cosine similarity of every query against every document."""
    scores: NDArray[np.float32] = unit(queries) @ unit(documents).T
    return scores


def ranks_from_scores(scores: NDArray[np.float32], targets: list[int]) -> list[int]:
    """The 1-based rank each target holds in its own row of `scores`."""
    ranks: list[int] = []
    for row, target in zip(scores, targets, strict=True):
        target_score = row[target]
        better = int(np.sum(row > target_score))
        tied = int(np.sum(row == target_score)) - 1
        ranks.append(1 + better + tied)
    return ranks


def metrics_from_ranks(ranks: list[int], ks: tuple[int, ...] = (1, 5, 10)) -> RankingMetrics:
    """Fold a list of ranks into recall at each k, plus MRR.

    NDCG is not among them. Every query here has exactly one relevant
    document, so NDCG@k collapses to ``1 / log2(rank + 1)`` -- a monotone
    function of the same rank MRR already reports, and one more series to
    read for no extra information.
    """
    if not ranks:
        return RankingMetrics(recall_at={k: 0.0 for k in ks}, mrr=0.0)
    array = np.asarray(ranks, dtype=np.float64)
    return RankingMetrics(
        recall_at={k: float(np.mean(array <= k)) for k in ks},
        mrr=float(np.mean(1.0 / array)),
    )


def norm_stats(vectors: NDArray[np.float32]) -> tuple[float, float]:
    """Mean and standard deviation of the vectors' lengths.

    A jump here is a preprocessing fault rather than a ranking one: a lost
    normalization step, a truncation, a tokenizer that changed under the
    model. Cosine cannot see any of them, because it divides magnitude out.
    """
    norms = np.linalg.norm(vectors, axis=1)
    return float(np.mean(norms)), float(np.std(norms))


def reference_cosine(
    current: NDArray[np.float32], baseline: NDArray[np.float32]
) -> tuple[float, float]:
    """Mean and worst cosine between each document's current and baseline vector.

    Raises
    ------
    ValueError
        If the two matrices disagree on shape. A width change is a different
        model, not drift within one, and the caller re-seeds instead.
    """
    if current.shape != baseline.shape:
        raise ValueError(f"baseline is {baseline.shape}, current is {current.shape}")
    per_document = np.sum(unit(current) * unit(baseline), axis=1)
    return float(np.mean(per_document)), float(np.min(per_document))


def neighbor_overlap(scores: NDArray[np.float32], k: int) -> float:
    """Mean Jaccard overlap of the top-k document sets across every query pair.

    The signal is discriminative power. Unrelated queries should retrieve
    unrelated documents; when a model degrades toward returning the same
    handful of documents whatever it is asked, this rises long before recall
    on the canary set falls.
    """
    query_count = scores.shape[0]
    if query_count < 2:
        return 0.0
    width = min(k, scores.shape[1])
    tops = [frozenset(np.argsort(-row)[:width].tolist()) for row in scores]
    overlaps = [
        len(tops[i] & tops[j]) / len(tops[i] | tops[j])
        for i in range(query_count)
        for j in range(i + 1, query_count)
    ]
    return float(np.mean(overlaps))
