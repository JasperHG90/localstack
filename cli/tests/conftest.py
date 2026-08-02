"""Shared fixtures.

Every test runs against a real HTTP server or a real closed port, never a
mocked urllib.
"""

import socket
import threading
from collections.abc import Iterator
from pathlib import Path

import pytest

from localstack_cli.config import CONSUL_HTTP_ADDR, NOMAD_ADDR, VAULT_ADDR
from localstack_cli.status import VAULT_TOKEN
from tests.fixtures.cluster import HEALTHY_ROUTES, FakeCluster, Handler


@pytest.fixture
def cluster() -> Iterator[FakeCluster]:
    server = FakeCluster(("127.0.0.1", 0), Handler)
    server.routes = dict(HEALTHY_ROUTES)
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
def isolated_environment(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, closed_addr: str) -> None:
    """Keep tests off the real cluster and out of the real home directory.

    `~/.vault-token` is a real file on a developer machine, so `HOME` moves
    to a temp directory. Addresses default to a closed port, so a test that
    forgets to point somewhere fails fast instead of probing production.
    """
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv(VAULT_TOKEN, raising=False)
    for name in (VAULT_ADDR, NOMAD_ADDR, CONSUL_HTTP_ADDR):
        monkeypatch.setenv(name, closed_addr)
