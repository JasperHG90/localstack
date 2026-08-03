"""The panel, rendered.

No HTTP anywhere here: every source is an injected callable, so the app never
learns whether its data came from a cluster or a file. The fixtures are the
full live capture, not a hand-picked subset.

The terminal size is fixed, because a snapshot is only deterministic if the
viewport is.
"""

import asyncio
import json
import threading
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path
from typing import Any

from localstack_cli.api.consul import Check
from localstack_cli.api.errors import (
    MissingCapability,
    NotAuthenticated,
    Timeout,
    Unreachable,
)
from localstack_cli.api.health import Health, judge_all
from localstack_cli.api.nomad import Job, Node, _parse_job
from localstack_cli.api.vault import SealStatus
from localstack_cli.tui.monitor import MonitorApp
from localstack_cli.tui.widgets import Result

FIXTURES = Path(__file__).parent / "fixtures" / "capture"
TERMINAL = (100, 44)


def load(name: str) -> Any:
    return json.loads((FIXTURES / f"{name}.json").read_text())


def cluster_jobs() -> list[Job]:
    return [_parse_job(item) for item in load("jobs_statuses")]


def cluster_nodes() -> list[Node]:
    return [
        Node(
            name=str(item["Name"]),
            status=str(item["Status"]),
            eligibility=str(item["SchedulingEligibility"]),
            draining=bool(item["Drain"]),
        )
        for item in load("nodes")
    ]


def cluster_checks() -> list[Check]:
    return [
        Check(
            name=str(item["Name"]),
            status=str(item["Status"]),
            node=str(item["Node"]),
            service=str(item.get("ServiceName", "")),
        )
        for item in load("consul_health")
    ]


def cluster_seal(**overrides: Any) -> SealStatus:
    raw = load("seal_status")
    return replace(
        SealStatus(
            sealed=bool(raw["sealed"]),
            threshold=int(raw["t"]),
            shares=int(raw["n"]),
            progress=int(raw["progress"]),
            version=str(raw["version"]),
        ),
        **overrides,
    )


def raises(error: Exception) -> Callable[..., Any]:
    def fetch(*_: Any) -> Any:
        raise error

    return fetch


def app(
    seal: Callable[[], Any] | None = None,
    nodes: Callable[[], Any] | None = None,
    jobs: Callable[[list[Any]], Any] | None = None,
    checks: Callable[[], Any] | None = None,
    refresh_seconds: float = 0.0,
) -> MonitorApp:
    """A healthy cluster by default; pass a fetcher to break one source."""
    return MonitorApp(
        seal=seal or cluster_seal,
        nodes=nodes or cluster_nodes,
        jobs=jobs or (lambda known: judge_all(cluster_jobs(), known)),
        checks=checks or cluster_checks,
        refresh_seconds=refresh_seconds,
    )


async def settle(application: MonitorApp) -> None:
    """Wait for every fetch worker to finish.

    The fetches run in workers precisely so they do not block the UI, which
    means a test that reads a panel straight after mounting reads it before
    the data lands.
    """
    # Twice, because the node worker starts the job worker when it finishes,
    # so one wait can return before the chained worker has been registered.
    for _ in range(4):
        await application.workers.wait_for_complete()
        await asyncio.sleep(0.05)
    await application.workers.wait_for_complete()


def test_a_healthy_cluster(snap_compare: Any) -> None:
    assert snap_compare(app(), terminal_size=TERMINAL)


def test_vault_sealed(snap_compare: Any) -> None:
    """The common real outage here, and the panel that always renders."""
    assert snap_compare(
        app(seal=lambda: cluster_seal(sealed=True, progress=1)), terminal_size=TERMINAL
    )


def test_nomad_denied(snap_compare: Any) -> None:
    """A 403 names the capability rather than showing an empty table."""
    assert snap_compare(
        app(
            nodes=raises(MissingCapability("nomad", "node:read")),
            jobs=raises(MissingCapability("nomad", "list-jobs")),
        ),
        terminal_size=TERMINAL,
    )


def test_expired_token(snap_compare: Any) -> None:
    """A different render from the 403 one: this points at `localstack login`."""
    assert snap_compare(
        app(nodes=raises(NotAuthenticated("nomad")), jobs=raises(NotAuthenticated("nomad"))),
        terminal_size=TERMINAL,
    )


def test_nomad_unreachable(snap_compare: Any) -> None:
    assert snap_compare(
        app(
            nodes=raises(Unreachable("nomad", "https://nomad.lab.example/v1/nodes")),
            jobs=raises(Unreachable("nomad", "https://nomad.lab.example/v1/jobs/statuses")),
        ),
        terminal_size=TERMINAL,
    )


def test_a_service_job_below_its_desired_count(snap_compare: Any) -> None:
    """The failure must be visible without scrolling past 18 healthy rows."""

    def degraded(known: list[Any]) -> Any:
        jobs = [
            replace(job, desired=3) if job.name == "postgres" else job for job in cluster_jobs()
        ]
        return judge_all(jobs, known)

    assert snap_compare(app(jobs=degraded), terminal_size=TERMINAL)


def test_consul_has_failing_checks(snap_compare: Any) -> None:
    def failing_checks() -> list[Check]:
        every = cluster_checks()
        return [
            replace(every[0], status="critical"),
            replace(every[1], status="warning"),
            *every[2:],
        ]

    assert snap_compare(app(checks=failing_checks), terminal_size=TERMINAL)


async def test_a_slow_source_keeps_its_last_value_marked_stale() -> None:
    """One good fetch, then two that time out. The value must survive.

    Blanking would throw away the only information on screen at the moment
    it is wanted.
    """
    calls = {"n": 0}

    def sometimes_slow() -> list[Node]:
        calls["n"] += 1
        if calls["n"] == 1:
            return cluster_nodes()
        raise Timeout("nomad", "2.0s")

    application = app(nodes=sometimes_slow)
    async with application.run_test(size=TERMINAL):
        await settle(application)
        application.refresh_all()
        await settle(application)
        application.refresh_all()
        await settle(application)
        rendered = str(application.query_one("#nodes").render())

    assert "stale" in rendered
    assert "firebat" in rendered
    assert "timed out" in rendered


async def test_a_cold_start_that_times_out_says_no_data_yet() -> None:
    """With no previous value there is nothing to keep.

    An empty table would read as "nothing is running", which is a different
    and much worse claim than "nothing is known yet".
    """
    application = app(nodes=raises(Timeout("nomad", "2.0s")))
    async with application.run_test(size=TERMINAL):
        await settle(application)
        rendered = str(application.query_one("#nodes").render())

    assert "timed out" in rendered
    assert "firebat" not in rendered


async def test_one_dead_source_leaves_the_others_alone() -> None:
    """The requirement the whole worker design exists for."""
    application = app(seal=raises(Unreachable("vault", "https://vault.lab.example")))
    async with application.run_test(size=TERMINAL):
        await settle(application)
        vault_text = str(application.query_one("#vault").render())
        nodes_text = str(application.query_one("#nodes").render())
        jobs_text = str(application.query_one("#jobs-panel").render())
        consul_text = str(application.query_one("#consul").render())

    assert "unreachable" in vault_text
    assert "firebat" in nodes_text
    assert "memex" in jobs_text
    assert "0 failing of 41" in consul_text


async def test_the_panel_shows_exactly_four_widgets() -> None:
    """R1: a fifth is scope creep and needs its own ticket."""
    from localstack_cli.tui.widgets import Panel

    application = app()
    async with application.run_test(size=TERMINAL):
        await settle(application)
        panels = [node for node in application.screen.walk_children() if isinstance(node, Panel)]

    assert len(panels) == 4
    assert {type(panel).__name__ for panel in panels} == {
        "VaultPanel",
        "NodePanel",
        "JobPanel",
        "ConsulPanel",
    }


async def test_no_lifetime_counter_reaches_the_screen() -> None:
    """R2: the counters are not rendered as a substitute for history."""
    application = app()
    async with application.run_test(size=TERMINAL):
        await settle(application)
        everything = " ".join(
            str(application.query_one(f"#{name}").render())
            for name in ("vault", "nodes", "jobs-panel", "consul")
        )

    for word in ("Failed:", "Lost:", "Complete:"):
        assert word not in everything


async def test_the_healthy_cluster_renders_every_job_healthy() -> None:
    """The regression that would make the panel useless: 11 of 19 wrong."""
    application = app()
    async with application.run_test(size=TERMINAL):
        await settle(application)
        rendered = str(application.query_one("#jobs-panel").render())

    assert MARKS_DEGRADED not in rendered
    assert rendered.count("ok") >= 19


MARKS_DEGRADED = "DEGRADED"


async def test_refreshing_by_key_refetches() -> None:
    """`r` forces a refresh now, which is the other half of a 0 interval."""
    calls = {"n": 0}

    def counted() -> list[Node]:
        calls["n"] += 1
        return cluster_nodes()

    application = app(nodes=counted)
    async with application.run_test(size=TERMINAL) as pilot:
        await settle(application)
        before = calls["n"]
        await pilot.press("r")
        await pilot.pause()

    assert calls["n"] > before


def test_health_marks_cover_every_state() -> None:
    """A new `Health` member must not render as a KeyError."""
    from localstack_cli.tui.widgets import MARKS

    assert set(MARKS) == set(Health)


async def test_a_slow_source_does_not_delay_the_others() -> None:
    """R5, proved rather than assumed.

    Vault and Consul must be filled while the node fetch is still running.
    The job panel is not checked here: it is started BY the node fetch, so it
    legitimately waits on it. Run the fetches in line instead of in workers
    and this fails, because then every panel waits out the slowest source,
    which is exactly the freeze the worker design exists to prevent.
    """
    started = threading.Event()
    release = threading.Event()

    def slow_nodes() -> list[Node]:
        started.set()
        release.wait(timeout=5)
        return cluster_nodes()

    application = app(nodes=slow_nodes)
    try:
        async with application.run_test(size=TERMINAL):
            # Give the slow worker time to start and the fast ones to finish.
            await asyncio.wait_for(asyncio.to_thread(started.wait, 5), timeout=5)
            for _ in range(50):
                await asyncio.sleep(0.02)
                if "unsealed" in str(application.query_one("#vault").render()):
                    break

            vault_text = str(application.query_one("#vault").render())
            consul_text = str(application.query_one("#consul").render())
            nodes_text = str(application.query_one("#nodes").render())

            # The slow one is still waiting while the others are done.
            assert "unsealed" in vault_text
            assert "0 failing of 41" in consul_text
            assert "firebat" not in nodes_text

            release.set()
            await settle(application)
            assert "firebat" in str(application.query_one("#nodes").render())
    finally:
        release.set()


async def test_a_system_job_with_no_node_count_renders_as_unknown() -> None:
    """The counts must not read `5/0`, which would claim a desired count.

    Reachable whenever `/v1/nodes` is denied while `/v1/jobs/statuses` works.
    """
    application = app(nodes=raises(MissingCapability("nomad", "node:read")))
    async with application.run_test(size=TERMINAL):
        await settle(application)
        rendered = str(application.query_one("#jobs-panel").render())

    assert "unknown" in rendered
    assert "5/?" in rendered
    assert "5/0" not in rendered


async def test_the_job_panel_still_renders_when_the_node_fetch_dies() -> None:
    """The chain must hand off on failure, not leave the panel empty."""
    application = app(nodes=raises(Unreachable("nomad", "https://nomad.lab.example")))
    async with application.run_test(size=TERMINAL):
        await settle(application)
        rendered = str(application.query_one("#jobs-panel").render())

    assert "memex" in rendered


async def test_an_unexpected_error_degrades_one_panel_rather_than_the_app() -> None:
    """Textual kills the app when a worker raises, so nothing may escape."""

    def broken() -> list[Check]:
        raise ValueError("something the fetch layer never classified")

    application = app(checks=broken)
    async with application.run_test(size=TERMINAL):
        await settle(application)
        consul_text = str(application.query_one("#consul").render())
        vault_text = str(application.query_one("#vault").render())

    assert "ValueError" in consul_text
    assert "unsealed" in vault_text


def test_an_empty_but_successful_fetch_says_so() -> None:
    """A blank panel reads as broken. Nothing found is a real answer."""
    from localstack_cli.tui.widgets import NodePanel

    assert "none" in NodePanel().render_result(Result(value=[]))
