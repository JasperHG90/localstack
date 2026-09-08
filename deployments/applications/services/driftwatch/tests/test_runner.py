from __future__ import annotations

import math
from pathlib import Path

import pytest
import respx

from driftwatch import runner
from driftwatch.client import EmbarkClient
from driftwatch.goldset import Goldset, RerankCase
from tests import fixtures

BASE = "http://embark.test:8000"


def goldset() -> Goldset:
    return Goldset(
        queries=["q0", "q1"],
        documents=["p0", "n0", "p1", "n1"],
        targets=[0, 2],
    )


def run(
    tmp_path: Path,
    *,
    scorer: fixtures.Scorer | None = None,
    query_vectors: dict[str, list[float]] | None = None,
) -> runner.RunResult:
    gold = goldset()
    axes = fixtures.one_hot(gold.documents)
    # Each query shares an axis with the document that answers it, so the
    # embedding stage ranks it first and the rerank stage gets a shortlist
    # that contains the answer.
    queries = query_vectors or {
        "q0": axes["p0"],
        "q1": axes["p1"],
    }
    fixtures.install(
        respx,
        base_url=BASE,
        vectors=axes,
        query_vectors=queries,
        scorer=scorer,
    )
    with EmbarkClient(base_url=BASE, api_key="k", timeout=5.0) as client:
        return runner.evaluate(
            client,
            gold,
            [],
            embedding_model="embedding",
            rerank_model="reranker",
            baseline_path=tmp_path / "baseline.npz",
            rerank_pool=3,
            now=1000.0,
        )


@respx.mock
def test_a_perfect_embedder_scores_recall_one(tmp_path: Path) -> None:
    result = run(tmp_path)

    assert result.embedding.recall_at[1] == pytest.approx(1.0)
    assert result.embedding.mrr == pytest.approx(1.0)


@respx.mock
def test_the_first_run_seeds_the_baseline_and_reports_no_cosine(tmp_path: Path) -> None:
    result = run(tmp_path)

    assert result.reference_cosine is None
    assert result.baseline_recorded_at == 1000.0
    assert (tmp_path / "baseline.npz").exists()


@respx.mock
def test_the_second_run_compares_against_the_first(tmp_path: Path) -> None:
    run(tmp_path)

    result = run(tmp_path)

    assert result.reference_cosine is not None
    mean, worst = result.reference_cosine
    assert mean == pytest.approx(1.0)
    assert worst == pytest.approx(1.0)
    assert result.baseline_recorded_at == 1000.0


@respx.mock
def test_a_changed_model_shows_up_as_a_lower_cosine(tmp_path: Path) -> None:
    run(tmp_path)

    # A second "model" that puts every document on the same axis: the vectors
    # are still the right shape and width, and cosine is what notices.
    gold = goldset()
    flat = {name: [1.0, 1.0, 1.0, 1.0] for name in gold.documents + gold.queries}
    fixtures.install(respx, base_url=BASE, vectors=flat)
    with EmbarkClient(base_url=BASE, api_key="k", timeout=5.0) as client:
        result = runner.evaluate(
            client,
            goldset(),
            [],
            embedding_model="embedding",
            rerank_model="reranker",
            baseline_path=tmp_path / "baseline.npz",
            rerank_pool=3,
            now=2000.0,
        )

    assert result.reference_cosine is not None
    assert result.reference_cosine[0] == pytest.approx(0.5)


@respx.mock
def test_a_baseline_from_a_different_corpus_is_reseeded(tmp_path: Path) -> None:
    import numpy as np

    from driftwatch import baseline as baseline_store

    path = tmp_path / "baseline.npz"
    baseline_store.write(path, np.zeros((7, 3), dtype=np.float32), now=1.0)

    result = run(tmp_path)

    assert result.reference_cosine is None
    assert result.baseline_recorded_at == 1000.0
    stored = baseline_store.read(path, documents=4)
    assert stored is not None


@respx.mock
def test_the_reranker_can_undo_a_good_shortlist(tmp_path: Path) -> None:
    """The reranker is measured on its own: same shortlist, worse order."""

    def worst_first(query: str, candidates: list[str]) -> list[float]:  # noqa: ARG001
        return [float(index) for index in range(len(candidates))]

    result = run(tmp_path, scorer=worst_first)

    assert result.embedding.recall_at[1] == pytest.approx(1.0)
    assert result.pipeline.recall_at[1] == pytest.approx(0.0)


@respx.mock
def test_an_answer_outside_the_shortlist_counts_as_a_miss(tmp_path: Path) -> None:
    gold = Goldset(
        queries=["q0"],
        documents=["p0", "d1", "d2", "d3"],
        targets=[0],
    )
    axes = fixtures.one_hot(gold.documents)
    fixtures.install(
        respx,
        base_url=BASE,
        vectors=axes,
        # The query points at d3, so the answer p0 never makes a shortlist of
        # one and the reranker is never given the chance to find it.
        query_vectors={"q0": axes["d3"]},
    )
    with EmbarkClient(base_url=BASE, api_key="k", timeout=5.0) as client:
        result = runner.evaluate(
            client,
            gold,
            [],
            embedding_model="embedding",
            rerank_model="reranker",
            baseline_path=tmp_path / "baseline.npz",
            rerank_pool=1,
            now=1000.0,
        )

    assert result.pipeline.recall_at[1] == pytest.approx(0.0)
    assert result.pipeline.mrr == pytest.approx(0.5)


@respx.mock
def test_apply_publishes_every_stage(tmp_path: Path) -> None:
    from prometheus_client import CollectorRegistry

    from driftwatch.metrics import Metrics

    metrics = Metrics(CollectorRegistry())
    result = run(tmp_path)

    runner.apply(metrics, result)

    registry = metrics.registry
    assert registry.get_sample_value(
        "driftwatch_recall", {"stage": "embedding", "k": "10"}
    ) == pytest.approx(1.0)
    assert registry.get_sample_value("driftwatch_mrr", {"stage": "pipeline"}) is not None
    assert registry.get_sample_value("driftwatch_embedding_norm_mean") == pytest.approx(1.0)
    assert registry.get_sample_value("driftwatch_neighbor_overlap") is not None
    assert registry.get_sample_value("driftwatch_baseline_recorded_timestamp_seconds") == 1000.0
    # The seeding run measured no drift, so the cosine series reads NaN
    # rather than the 0 an untouched gauge would report as total drift.
    cosine = registry.get_sample_value("driftwatch_reference_cosine_mean")
    assert cosine is not None and math.isnan(cosine)


@respx.mock
def test_a_rerank_that_scores_nothing_is_a_miss(tmp_path: Path) -> None:
    """embark answers 200 with an empty results array when the reranker is
    loaded but cannot score. Every candidate then keeps its -inf placeholder,
    and without a guard they all tie and put the answer at rank `width` --
    publishing recall@10 of 1.0 for a total rerank failure.

    Built at the production shortlist depth of 10 rather than on the shared
    fixture, whose 4-document corpus caps `width` at 4 and so cannot express
    the difference between a miss and a rank-4 hit at k=10.
    """
    documents = [f"d{n}" for n in range(12)]
    gold = Goldset(queries=["q0"], documents=documents, targets=[0])
    axes = fixtures.one_hot(documents)
    fixtures.install(
        respx,
        base_url=BASE,
        vectors=axes,
        query_vectors={"q0": axes["d0"]},
        scorer=lambda query, candidates: [],
    )

    with EmbarkClient(base_url=BASE, api_key="k", timeout=5.0) as client:
        result = runner.evaluate(
            client,
            gold,
            [],
            embedding_model="embedding",
            rerank_model="reranker",
            baseline_path=tmp_path / "baseline.npz",
            rerank_pool=10,
            now=1000.0,
        )

    assert result.embedding.recall_at[1] == pytest.approx(1.0)
    assert result.pipeline.recall_at[10] == pytest.approx(0.0)
    assert result.pipeline.mrr == pytest.approx(1 / 11)


def rerank_cases() -> list[RerankCase]:
    """Two queries over fixed ten-document pools, answers at slots 1 and 7.

    Ten because that is the shipped pool size: a miss is recorded one past the
    pool, so a four-deep fixture would land it at rank 5 and `recall@5` could
    not tell a miss from a hit.
    """
    first = [f"c{n}" for n in range(10)]
    first[1] = "p0"
    second = [f"d{n}" for n in range(10)]
    second[7] = "p1"
    return [
        RerankCase(query="q0", candidates=first, target=1),
        RerankCase(query="q1", candidates=second, target=7),
    ]


def run_rerank(scorer: fixtures.Scorer) -> runner.RunResult:
    gold = goldset()
    axes = fixtures.one_hot(gold.documents)
    fixtures.install(
        respx,
        base_url=BASE,
        vectors=axes,
        query_vectors={"q0": axes["p0"], "q1": axes["p1"]},
        scorer=scorer,
    )
    import tempfile

    with (
        tempfile.TemporaryDirectory() as tmp,
        EmbarkClient(base_url=BASE, api_key="k", timeout=5.0) as client,
    ):
        return runner.evaluate(
            client,
            gold,
            rerank_cases(),
            embedding_model="embedding",
            rerank_model="reranker",
            baseline_path=Path(tmp) / "baseline.npz",
            rerank_pool=3,
            now=1000.0,
        )


@respx.mock
def test_the_isolated_stage_scores_its_own_fixed_pool() -> None:
    """The answer is at index 1 and 3 of pools the embedder never chose, so a
    perfect score here is the reranker's alone."""

    def answer_first(query: str, candidates: list[str]) -> list[float]:
        return [1.0 if text.startswith("p") else 0.0 for text in candidates]

    result = run_rerank(answer_first)

    assert result.rerank.recall_at[1] == pytest.approx(1.0)
    assert result.rerank.mrr == pytest.approx(1.0)


@respx.mock
def test_the_isolated_stage_is_not_bounded_by_the_embedder() -> None:
    """A reranker that demotes the answer scores badly here even though the
    embedding stage in the same run is perfect. That separation is the reason
    this stage exists."""

    def answer_last(query: str, candidates: list[str]) -> list[float]:
        return [0.0 if text.startswith("p") else 1.0 for text in candidates]

    result = run_rerank(answer_last)

    assert result.embedding.recall_at[1] == pytest.approx(1.0)
    assert result.rerank.recall_at[1] == pytest.approx(0.0)
    # Nine candidates tie above the answer, so it lands last in a pool of ten.
    assert result.rerank.mrr == pytest.approx(0.1)


@respx.mock
def test_an_isolated_rerank_that_scores_nothing_is_a_miss() -> None:
    result = run_rerank(lambda query, candidates: [])

    assert result.rerank.recall_at[5] == pytest.approx(0.0)
    # One past the pool: outside every k the set publishes.
    assert result.rerank.mrr == pytest.approx(1 / 11)


@respx.mock
def test_the_three_stages_publish_separately(tmp_path: Path) -> None:
    from prometheus_client import CollectorRegistry

    from driftwatch.metrics import Metrics

    metrics = Metrics(CollectorRegistry())
    runner.apply(metrics, run_rerank(lambda query, candidates: [1.0] * len(candidates)))

    registry = metrics.registry
    for stage in ("embedding", "pipeline", "rerank"):
        assert registry.get_sample_value("driftwatch_mrr", {"stage": stage}) is not None
    # The isolated stage publishes k=3, which the corpus stages do not, and no
    # k=10, which would be 1.0 by construction over a pool that always holds
    # the answer.
    assert registry.get_sample_value("driftwatch_recall", {"stage": "rerank", "k": "3"}) is not None
    assert registry.get_sample_value("driftwatch_recall", {"stage": "rerank", "k": "10"}) is None
    assert (
        registry.get_sample_value("driftwatch_recall", {"stage": "embedding", "k": "10"})
        is not None
    )
