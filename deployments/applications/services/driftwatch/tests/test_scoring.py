from __future__ import annotations

import numpy as np
import pytest

from driftwatch import scoring


def test_unit_leaves_a_zero_row_alone() -> None:
    vectors = np.asarray([[3.0, 4.0], [0.0, 0.0]], dtype=np.float32)

    scaled = scoring.unit(vectors)

    assert np.allclose(scaled[0], [0.6, 0.8])
    assert np.allclose(scaled[1], [0.0, 0.0])


def test_rank_is_one_when_the_answer_wins() -> None:
    scores = np.asarray([[0.9, 0.1, 0.2]], dtype=np.float32)

    assert scoring.ranks_from_scores(scores, [0]) == [1]


def test_a_tie_ranks_the_answer_below_what_it_tied_with() -> None:
    """Pessimistic on purpose: a model that cannot separate two texts should not
    be scored as though it had."""
    scores = np.asarray([[0.5, 0.5, 0.1]], dtype=np.float32)

    assert scoring.ranks_from_scores(scores, [0]) == [2]


def test_recall_and_mrr_come_from_the_ranks() -> None:
    metrics = scoring.metrics_from_ranks([1, 2, 11], ks=(1, 5, 10))

    assert metrics.recall_at[1] == pytest.approx(1 / 3)
    assert metrics.recall_at[5] == pytest.approx(2 / 3)
    assert metrics.recall_at[10] == pytest.approx(2 / 3)
    assert metrics.mrr == pytest.approx((1 + 0.5 + 1 / 11) / 3)


def test_no_ranks_scores_zero_rather_than_dividing_by_zero() -> None:
    metrics = scoring.metrics_from_ranks([])

    assert metrics.mrr == 0.0
    assert metrics.recall_at[10] == 0.0


def test_norm_stats_report_magnitude_cosine_throws_away() -> None:
    vectors = np.asarray([[3.0, 4.0], [6.0, 8.0]], dtype=np.float32)

    mean, stddev = scoring.norm_stats(vectors)

    assert mean == pytest.approx(7.5)
    assert stddev == pytest.approx(2.5)


def test_reference_cosine_is_one_against_itself() -> None:
    vectors = np.asarray([[1.0, 2.0], [3.0, 4.0]], dtype=np.float32)

    mean, worst = scoring.reference_cosine(vectors, vectors)

    assert mean == pytest.approx(1.0)
    assert worst == pytest.approx(1.0)


def test_reference_cosine_ignores_a_pure_rescale() -> None:
    """Doubling every vector is invisible to cosine, which is what norm_stats
    is there to catch instead."""
    vectors = np.asarray([[1.0, 2.0], [3.0, 4.0]], dtype=np.float32)

    mean, _ = scoring.reference_cosine(vectors * 2, vectors)

    assert mean == pytest.approx(1.0)


def test_reference_cosine_refuses_a_different_shape() -> None:
    with pytest.raises(ValueError, match="baseline is"):
        scoring.reference_cosine(
            np.zeros((2, 3), dtype=np.float32), np.zeros((2, 4), dtype=np.float32)
        )


def test_neighbor_overlap_is_one_when_every_query_returns_the_same_documents() -> None:
    scores = np.asarray([[0.9, 0.8, 0.1], [0.9, 0.8, 0.1]], dtype=np.float32)

    assert scoring.neighbor_overlap(scores, k=2) == pytest.approx(1.0)


def test_neighbor_overlap_is_zero_when_the_top_sets_are_disjoint() -> None:
    scores = np.asarray([[0.9, 0.1, 0.0], [0.0, 0.1, 0.9]], dtype=np.float32)

    assert scoring.neighbor_overlap(scores, k=1) == pytest.approx(0.0)


def test_neighbor_overlap_needs_a_pair() -> None:
    scores = np.asarray([[0.9, 0.1]], dtype=np.float32)

    assert scoring.neighbor_overlap(scores, k=1) == 0.0
