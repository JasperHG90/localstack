"""Shared fixtures.

Every test runs against a real HTTP server or a real closed port, never a
mocked urllib.
"""

import socket
import threading
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from localstack_cli.auth.vault_token_file import VAULT_TOKEN
from localstack_cli.config import CONSUL_HTTP_ADDR, NOMAD_ADDR, VAULT_ADDR
from tests.fixtures.cluster import HEALTHY_ROUTES, FakeCluster, Handler


@pytest.fixture
def cluster() -> Iterator[FakeCluster]:
    server = FakeCluster(("127.0.0.1", 0), Handler)
    server.routes = dict(HEALTHY_ROUTES)
    server.requests = []
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


@pytest.fixture
def cluster_addr(cluster: FakeCluster) -> str:
    host, port = cluster.server_address[0], cluster.server_address[1]
    return f"http://{host!s}:{port}"


@pytest.fixture
def closed_addr() -> str:
    """An address nothing listens on, so connect fails at once.

    Better than an unroutable IP, which would wait out the full timeout and
    make the suite slow for no extra coverage.
    """
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    return f"http://127.0.0.1:{port}"


@pytest.fixture(autouse=True)
def no_outbound_network(
    request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch
) -> Iterator[None]:
    """Refuse any connection that leaves this machine.

    The default suite must be offline. The failure this guards is silent: a
    seam that looks redirected but is not (a default argument frozen at
    import, say) still reaches the real host, and the test passes or fails on
    whether the network happens to be up.

    Blocking is not enough on its own. Probe code that catches broadly, as
    `breakglass` does by design, swallows the refusal and the test stays
    green while the run has already tried to reach production. So every
    refusal is also recorded and re-raised at teardown, where nothing is left
    to catch it.

    Tests marked `cluster` are exempt, since hitting the real cluster is
    their job.
    """
    if request.node.get_closest_marker("cluster"):
        yield
        return

    real_connect = socket.socket.connect
    refused: list[str] = []

    def guarded(self: socket.socket, address: Any) -> None:
        if isinstance(address, tuple) and address[0] not in ("127.0.0.1", "::1", "localhost"):
            refused.append(str(address[0]))
            raise AssertionError(f"offline suite: refused a connection to {address[0]}")
        real_connect(self, address)

    monkeypatch.setattr(socket.socket, "connect", guarded)
    yield
    assert refused == [], (
        f"the default suite is offline, but this test tried to reach {sorted(set(refused))}. "
        "Point the code under test at a local server, or mark the test `cluster`."
    )


@pytest.fixture(autouse=True)
def isolated_environment(
    request: pytest.FixtureRequest,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    closed_addr: str,
) -> None:
    """Keep tests off the real cluster and out of the real home directory.

    `~/.vault-token` is a real file on a developer machine, so `HOME` moves
    to a temp directory. Addresses default to a closed port, so a test that
    forgets to point somewhere fails fast instead of probing production.

    Tests marked `cluster` keep the real environment. Reaching the real
    cluster is their job, and they need the tokens this otherwise deletes.
    """
    if request.node.get_closest_marker("cluster"):
        return
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    # The session cache follows XDG_CONFIG_HOME, so it lands under tmp_path
    # too and no test can read or write the developer's real one.
    monkeypatch.setenv("XDG_CONFIG_HOME", str(home / ".config"))
    monkeypatch.delenv(VAULT_TOKEN, raising=False)
    for name in (VAULT_ADDR, NOMAD_ADDR, CONSUL_HTTP_ADDR):
        monkeypatch.setenv(name, closed_addr)
