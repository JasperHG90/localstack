"""The Prometheus series this service exists to publish.

Gauges, not histograms: one run produces one number per series, and the run
is the sample. Prometheus keeps the history, so nothing here has to.

Registered against a registry of its own rather than prometheus_client's
module-level default, so two apps in one test process cannot collide on a
duplicate series name. Same reason embark builds one per application.
"""

from __future__ import annotations

import math

from prometheus_client import CollectorRegistry, Counter, Gauge


class Metrics:
    """Every series one evaluation run writes, bound to one registry."""

    def __init__(self, registry: CollectorRegistry) -> None:
        self.registry = registry

        self.recall = Gauge(
            "driftwatch_recall",
            "Fraction of canary queries whose answer landed in the top k.",
            ["stage", "k"],
            registry=registry,
        )
        self.mrr = Gauge(
            "driftwatch_mrr",
            "Mean reciprocal rank of the answer over the canary queries.",
            ["stage"],
            registry=registry,
        )
        self.reference_cosine_mean = Gauge(
            "driftwatch_reference_cosine_mean",
            "Mean cosine between each canary document's current and baseline vector.",
            registry=registry,
        )
        self.reference_cosine_min = Gauge(
            "driftwatch_reference_cosine_min",
            "Worst per-document cosine against the baseline.",
            registry=registry,
        )
        self.norm_mean = Gauge(
            "driftwatch_embedding_norm_mean",
            "Mean length of the canary document vectors, before normalization.",
            registry=registry,
        )
        self.norm_stddev = Gauge(
            "driftwatch_embedding_norm_stddev",
            "Standard deviation of those lengths.",
            registry=registry,
        )
        self.neighbor_overlap = Gauge(
            "driftwatch_neighbor_overlap",
            "Mean Jaccard overlap of the top-k document sets across canary query pairs.",
            registry=registry,
        )
        self.stage_seconds = Gauge(
            "driftwatch_stage_seconds",
            "Wall-clock seconds one stage spent calling embark. The stage label\n"
            "means the same three things here as on driftwatch_recall.",
            ["stage"],
            registry=registry,
        )
        self.run_seconds = Gauge(
            "driftwatch_run_seconds",
            "Wall-clock seconds the whole run took.",
            registry=registry,
        )
        self.runs = Counter(
            "driftwatch_runs",
            "Evaluation runs, by how they ended.",
            ["outcome"],
            registry=registry,
        )
        self.last_success = Gauge(
            "driftwatch_last_success_timestamp_seconds",
            "When the last run finished without error.",
            registry=registry,
        )
        self.baseline_recorded = Gauge(
            "driftwatch_baseline_recorded_timestamp_seconds",
            "When the baseline being compared against was written. 0 when there is none.",
            registry=registry,
        )
        self.goldset_queries = Gauge(
            "driftwatch_goldset_queries",
            "Queries in the canary set.",
            registry=registry,
        )
        self.goldset_documents = Gauge(
            "driftwatch_goldset_documents",
            "Documents in the canary corpus.",
            registry=registry,
        )
        self.rerank_cases = Gauge(
            "driftwatch_rerank_goldset_cases",
            "Queries in the rerank canary set, each with its own fixed candidate pool.",
            registry=registry,
        )

    def prime(self, *, queries: int, documents: int, rerank_cases: int) -> None:
        """Publish the series that hold before any run has finished.

        A counter with no series yet is a query that returns nothing, which
        Grafana renders as "No data" and an alert reads as neither firing nor
        healthy. Zeroing both outcomes at startup means an alert on the error
        rate is armed from the first scrape rather than from the first error.
        """
        self.runs.labels(outcome="ok").inc(0)
        self.runs.labels(outcome="error").inc(0)
        self.goldset_queries.set(queries)
        self.goldset_documents.set(documents)
        self.rerank_cases.set(rerank_cases)
        self.mark_reference_unmeasured()

    def mark_reference_unmeasured(self) -> None:
        """Say "no baseline comparison" without saying "cosine 0".

        An unlabelled prometheus_client gauge exists from the moment it is
        built, holding 0. On these two series 0 is the worst reading there is,
        so leaving them at the default would report total drift for every run
        before the first comparison and again after every re-seed. NaN is the
        exposition format's way of saying nothing was measured: Grafana draws
        a gap, and a PromQL threshold comparison against NaN is false, so no
        alert fires on it.
        """
        self.reference_cosine_mean.set(math.nan)
        self.reference_cosine_min.set(math.nan)
