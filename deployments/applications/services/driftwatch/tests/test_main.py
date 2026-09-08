from __future__ import annotations

import math
from pathlib import Path

import pytest
import respx
from prometheus_client import CollectorRegistry
from starlette.testclient import TestClient

from driftwatch import main
from driftwatch.config import Config
from driftwatch.goldset import Goldset
from driftwatch.metrics import Metrics
from tests import fixtures

BASE = "http://embark.test:8000"


def config(tmp_path: Path) -> Config:
    key_file = tmp_path / "embark.key"
    key_file.write_text("secret\n", encoding="utf-8")
    return Config(
        embark_url=BASE,
        embark_key_file=key_file,
        embedding_model="embedding",
        rerank_model="reranker",
        goldset_path=tmp_path / "goldset.jsonl",
        rerank_goldset_path=tmp_path / "rerank-goldset.jsonl",
        baseline_path=tmp_path / "baseline.npz",
        interval_seconds=3600.0,
        rerank_pool=3,
        request_timeout=5.0,
    )


def goldset() -> Goldset:
    return Goldset(queries=["q0"], documents=["p0", "n0"], targets=[0])


def test_healthz_answers_before_any_run_has_finished() -> None:
    metrics = Metrics(CollectorRegistry())

    with TestClient(main.create_app(metrics.registry)) as client:
        assert client.get("/healthz").status_code == 200


def test_metrics_serves_the_prometheus_exposition_format() -> None:
    metrics = Metrics(CollectorRegistry())
    metrics.prime(queries=30, documents=60, rerank_cases=30)

    with TestClient(main.create_app(metrics.registry)) as client:
        response = client.get("/metrics")

    assert response.status_code == 200
    assert "text/plain" in response.headers["content-type"]
    assert "driftwatch_goldset_queries 30.0" in response.text


def test_priming_arms_both_outcome_series() -> None:
    """An alert on the error rate has to be armed before the first error."""
    metrics = Metrics(CollectorRegistry())

    metrics.prime(queries=1, documents=2, rerank_cases=1)

    cosine = metrics.registry.get_sample_value("driftwatch_reference_cosine_mean")
    assert cosine is not None and math.isnan(cosine)
    assert metrics.registry.get_sample_value("driftwatch_runs_total", {"outcome": "ok"}) == 0.0
    assert metrics.registry.get_sample_value("driftwatch_runs_total", {"outcome": "error"}) == 0.0


@respx.mock
def test_a_successful_run_counts_and_stamps_the_success(tmp_path: Path) -> None:
    metrics = Metrics(CollectorRegistry())
    axes = fixtures.one_hot(["p0", "n0"])
    fixtures.install(respx, base_url=BASE, vectors=axes, query_vectors={"q0": axes["p0"]})

    main.run_once(config(tmp_path), goldset(), [], metrics)

    registry = metrics.registry
    assert registry.get_sample_value("driftwatch_runs_total", {"outcome": "ok"}) == 1.0
    stamped = registry.get_sample_value("driftwatch_last_success_timestamp_seconds")
    assert stamped is not None and stamped > 0


@respx.mock
def test_a_failing_embark_counts_an_error_and_does_not_raise(tmp_path: Path) -> None:
    import httpx

    metrics = Metrics(CollectorRegistry())
    respx.post(f"{BASE}/v1/embeddings").mock(return_value=httpx.Response(503, text="warming"))

    main.run_once(config(tmp_path), goldset(), [], metrics)

    registry = metrics.registry
    assert registry.get_sample_value("driftwatch_runs_total", {"outcome": "error"}) == 1.0
    assert registry.get_sample_value("driftwatch_last_success_timestamp_seconds") == 0.0


def test_a_missing_key_file_is_an_error_not_a_crash(tmp_path: Path) -> None:
    metrics = Metrics(CollectorRegistry())
    broken = config(tmp_path)
    broken.embark_key_file.unlink()

    main.run_once(broken, goldset(), [], metrics)

    assert metrics.registry.get_sample_value(
        "driftwatch_runs_total", {"outcome": "error"}
    ) == pytest.approx(1.0)
