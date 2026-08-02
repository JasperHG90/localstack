"""A real HTTP server standing in for Vault, Nomad and Consul at once.

The probes are thin wrappers over `urllib`, so mocking the transport would
assert little more than that the mock was called. Serving the real status
codes exercises the part that can actually be wrong: which code means
healthy, and which means reachable-but-unusable.
"""

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HEALTHY_LEADER = '"192.168.2.30:8300"'

LOOKUP_SELF = {
    "data": {
        "display_name": "userpass-jasper",
        "meta": {"username": "jasper"},
        # 7h30m, so the formatting shows rather than rounding to nothing.
        "ttl": 27000,
    }
}

HEALTHY_ROUTES: dict[str, tuple[int, bytes]] = {
    "/v1/sys/health": (200, b'{"sealed":false}'),
    "/v1/agent/health": (200, b'{"server":{"ok":true}}'),
    "/v1/status/leader": (200, HEALTHY_LEADER.encode()),
    "/v1/auth/token/lookup-self": (200, json.dumps(LOOKUP_SELF).encode()),
}


class FakeCluster(ThreadingHTTPServer):
    """Each route's reply is a `(status, body)` a test may rewrite."""

    routes: dict[str, tuple[int, bytes]]


class Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802  (BaseHTTPRequestHandler's contract)
        server: FakeCluster = self.server  # type: ignore[assignment]
        status, body = server.routes.get(self.path, (404, b"no such route"))
        self.send_response(status)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:
        """Silence the default stderr access log."""
