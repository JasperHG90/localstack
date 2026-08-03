"""The `localstack monitor` app: one screen, four widgets, four workers.

The refresh contract is the whole design. Each source is fetched by its own
worker with its own timeout, off the UI thread, so a sealed Vault or a downed
Nomad degrades one panel and nothing else. A TUI that hangs on a dead source
is worse than no TUI, because it hangs at the exact moment someone needs it.

One ordering survives: the job fetch runs after the node fetch, because a
`system` job cannot be judged without a node count. Vault and Consul wait on
nothing, and a failed node fetch still hands off, so the job panel is never
stuck behind a dead source.

A fetch that fails keeps the last value and marks it stale rather than
blanking. Blanking throws away the only information on screen precisely when
it is wanted. With no previous value there is nothing to keep, so the panel
says "no data yet" instead of showing an empty table that would read as
"nothing is running".
"""

from collections.abc import Callable
from typing import Any

from textual import work
from textual.app import App, ComposeResult
from textual.containers import Horizontal, VerticalScroll
from textual.widgets import Footer, Header

from localstack_cli.api import consul, nomad, vault
from localstack_cli.api.errors import ClusterError
from localstack_cli.api.health import judge_all
from localstack_cli.tui.widgets import ConsulPanel, JobPanel, NodePanel, Panel, Result, VaultPanel

REFRESH_SECONDS = 5.0

# Each source is fetched by a zero-argument callable, so a test injects data
# without any HTTP and the app has no idea which it got.
Fetch = Callable[[], Any]


class Sources:
    """The four reads, bound to addresses and a token.

    Built here rather than inside the app so a test can hand over four
    callables and never touch the network.
    """

    def __init__(
        self,
        vault_addr: str,
        nomad_addr: str,
        consul_addr: str,
        nomad_token: str | None,
    ) -> None:
        self.seal: Fetch = lambda: vault.seal_status(vault_addr)
        self.nodes: Fetch = lambda: nomad.list_nodes(nomad_addr, nomad_token)
        self.checks: Fetch = lambda: consul.list_checks(consul_addr)
        self._jobs: Fetch = lambda: nomad.job_statuses(nomad_addr, nomad_token)

    def jobs(self, nodes: list[nomad.Node]) -> Any:
        """Job health needs the node count, so it is not a bare fetch."""
        return judge_all(self._jobs(), nodes)


class MonitorApp(App[None]):
    """Is the cluster fine, and is my job running?"""

    CSS = """
    Screen { layout: vertical; }
    #top { height: auto; }
    Panel { border: round $primary; padding: 0 1; width: 1fr; }
    #jobs { height: 1fr; }
    """

    BINDINGS = [("q", "quit", "Quit"), ("r", "refresh", "Refresh now")]

    def __init__(
        self,
        seal: Fetch,
        nodes: Fetch,
        jobs: Callable[[list[Any]], Any],
        checks: Fetch,
        refresh_seconds: float = REFRESH_SECONDS,
    ) -> None:
        super().__init__()
        self._fetch_seal = seal
        self._fetch_nodes = nodes
        self._fetch_jobs = jobs
        self._fetch_checks = checks
        self._refresh_seconds = refresh_seconds
        # Held so a failed fetch can keep showing the last good value.
        self._last: dict[str, Result[Any]] = {}
        self._known_nodes: list[Any] = []

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="top"):
            yield VaultPanel(id="vault")
            yield NodePanel(id="nodes")
            yield ConsulPanel(id="consul")
        with VerticalScroll(id="jobs"):
            yield JobPanel(id="jobs-panel")
        yield Footer()

    def on_mount(self) -> None:
        for name in ("vault", "nodes", "consul", "jobs-panel"):
            self.query_one(f"#{name}", Panel).show(Result())
        self.action_refresh()
        if self._refresh_seconds > 0:
            self.set_interval(self._refresh_seconds, self.action_refresh)

    def action_refresh(self) -> None:
        self.refresh_all()

    def refresh_all(self) -> None:
        """Start the fetches. None of them runs on the UI thread.

        This is the requirement the whole design exists for. Fetching in
        line would freeze the screen for the full timeout of whichever
        source is slowest, at the exact moment someone opened the panel to
        find out what is wrong. Each worker is `exclusive` within its own
        group, so a fetch still running when the next tick arrives is
        replaced rather than queued behind itself.

        Three groups start here, not four. The job fetch is started by the
        node fetch instead, because judging a `system` job needs the node
        count. That is the one ordering the data actually requires; Vault
        and Consul wait on nothing.
        """
        self._work_vault()
        self._work_nodes()
        self._work_consul()

    @work(thread=True, group="vault", exclusive=True)
    def _work_vault(self) -> None:
        self._fetch_into("vault", self._fetch_seal)

    @work(thread=True, group="nodes", exclusive=True)
    def _work_nodes(self) -> None:
        self._fetch_into("nodes", self._fetch_nodes)
        # Judging a `system` job needs the node count, so the job fetch runs
        # once this one has produced the freshest count available. Racing
        # them instead would show "unknown" for every system job on the first
        # refresh. This chain is inside the worker thread, so it still blocks
        # neither the UI nor the other two sources.
        self._work_jobs()

    @work(thread=True, group="jobs", exclusive=True)
    def _work_jobs(self) -> None:
        self._fetch_into("jobs-panel", lambda: self._fetch_jobs(self._known_nodes))

    @work(thread=True, group="consul", exclusive=True)
    def _work_consul(self) -> None:
        self._fetch_into("consul", self._fetch_checks)

    def _fetch_into(self, panel_id: str, fetch: Fetch) -> None:
        """Run one fetch and hand the outcome back to the UI thread."""
        previous = self._last.get(panel_id, Result())
        try:
            result: Result[Any] = Result(value=fetch())
        except ClusterError as error:
            # Keep the last value and say it is old. There may be none, and
            # then the panel says so rather than showing an empty table.
            result = Result(value=previous.value, problem=str(error))
        except Exception as error:  # noqa: BLE001
            # Anything the fetch layer did not classify. Textual's default is
            # to kill the app when a worker raises, so an unexpected error in
            # one source would take all four panels down. A monitoring panel
            # that dies is the one outcome worse than a panel showing a
            # problem, so it renders the problem instead.
            result = Result(value=previous.value, problem=f"{type(error).__name__}: {error}")

        if panel_id == "nodes" and result.value is not None:
            self._known_nodes = list(result.value)
        self._last[panel_id] = result

        # Widgets are only safe to touch from the UI thread.
        self.call_from_thread(self._show, panel_id, result)

    def _show(self, panel_id: str, result: Result[Any]) -> None:
        self.query_one(f"#{panel_id}", Panel).show(result)


def build(
    vault_addr: str,
    nomad_addr: str,
    consul_addr: str,
    nomad_token: str | None,
    refresh_seconds: float = REFRESH_SECONDS,
) -> MonitorApp:
    """The app wired to the real cluster."""
    sources = Sources(vault_addr, nomad_addr, consul_addr, nomad_token)
    return MonitorApp(
        seal=sources.seal,
        nodes=sources.nodes,
        jobs=sources.jobs,
        checks=sources.checks,
        refresh_seconds=refresh_seconds,
    )
