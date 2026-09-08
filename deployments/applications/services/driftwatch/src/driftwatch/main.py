"""The service: a scheduler thread that evaluates, and a page that reports.

`create_app` takes its config, goldset and registry as arguments rather than
reading the environment, so a test can drive the whole HTTP surface against a
fake embark without an environment variable in sight. `main` is the only place
that reads the environment and starts a server.

The evaluation runs on a daemon thread rather than in the request path.
Scraping must never trigger a model call: Prometheus polls every 30 seconds
and the canary takes minutes on a cold cache, so a scrape-driven design would
either time out the scrape or hammer the Jetson.
"""

from __future__ import annotations

import logging
import os
import threading
import time
from typing import Any

from prometheus_client import CONTENT_TYPE_LATEST, CollectorRegistry, generate_latest
from starlette.applications import Starlette
from starlette.responses import PlainTextResponse, Response
from starlette.routing import Route

from driftwatch import goldset as goldset_module
from driftwatch import runner
from driftwatch.client import EmbarkClient
from driftwatch.config import Config
from driftwatch.goldset import Goldset, RerankCase
from driftwatch.metrics import Metrics

logger = logging.getLogger("driftwatch")


def run_once(
    config: Config,
    goldset: Goldset,
    rerank_cases: list[RerankCase],
    metrics: Metrics,
) -> None:
    """Evaluate once and publish the result, recording the outcome either way."""
    try:
        with EmbarkClient(
            base_url=config.embark_url,
            api_key=config.read_embark_key(),
            timeout=config.request_timeout,
        ) as client:
            result = runner.evaluate(
                client,
                goldset,
                rerank_cases,
                embedding_model=config.embedding_model,
                rerank_model=config.rerank_model,
                baseline_path=config.baseline_path,
                rerank_pool=config.rerank_pool,
                now=time.time(),
            )
    except Exception:
        # Every failure mode is the same failure from here: the numbers on the
        # dashboard are the previous run's, and the error counter plus the
        # staleness of the last-success gauge are what say so. Re-raising would
        # kill the thread and stop the schedule with it.
        logger.exception("evaluation run failed")
        metrics.runs.labels(outcome="error").inc()
        return

    runner.apply(metrics, result)
    metrics.runs.labels(outcome="ok").inc()
    metrics.last_success.set(time.time())
    logger.info(
        "run ok in %.1fs: embedding recall@10=%.3f, pipeline recall@1=%.3f, rerank recall@1=%.3f",
        result.total_seconds,
        result.embedding.recall_at[10],
        result.pipeline.recall_at[1],
        result.rerank.recall_at[1],
    )


def schedule(
    config: Config,
    goldset: Goldset,
    rerank_cases: list[RerankCase],
    metrics: Metrics,
    stop: threading.Event,
) -> None:
    """Evaluate now, then every `interval_seconds` until `stop` is set."""
    while not stop.is_set():
        run_once(config, goldset, rerank_cases, metrics)
        stop.wait(config.interval_seconds)


def create_app(registry: CollectorRegistry) -> Starlette:
    """The HTTP surface: metrics for Prometheus, health for Nomad."""

    async def metrics_endpoint(request: Any) -> Response:  # noqa: ARG001
        return Response(generate_latest(registry), media_type=CONTENT_TYPE_LATEST)

    async def health_endpoint(request: Any) -> PlainTextResponse:  # noqa: ARG001
        # Liveness, not readiness. The first canary run takes minutes on a cold
        # embark cache, and a check that waited for it would restart the task
        # into the same wait, forever -- the same reason embark's own check
        # probes /healthz rather than /readyz.
        return PlainTextResponse("ok")

    return Starlette(
        routes=[
            Route("/metrics", metrics_endpoint),
            Route("/healthz", health_endpoint),
        ]
    )


def main() -> None:
    import uvicorn

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    config = Config.from_env()
    goldset = goldset_module.load(config.goldset_path)
    rerank_cases = goldset_module.load_rerank(config.rerank_goldset_path)
    metrics = Metrics(CollectorRegistry())
    metrics.prime(
        queries=len(goldset.queries),
        documents=len(goldset.documents),
        rerank_cases=len(rerank_cases),
    )

    stop = threading.Event()
    thread = threading.Thread(
        target=schedule,
        args=(config, goldset, rerank_cases, metrics, stop),
        daemon=True,
        name="driftwatch",
    )
    thread.start()

    port = int(os.environ.get("PORT", "8010"))
    uvicorn.run(create_app(metrics.registry), host="0.0.0.0", port=port)  # noqa: S104


if __name__ == "__main__":
    main()
