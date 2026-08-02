"""A real HTTP server standing in for Vault, Nomad and Consul at once.

The client code is a thin wrapper over `urllib`, so mocking the transport
would assert little more than that the mock was called. Serving the real
status codes exercises the part that can actually be wrong: which code means
healthy, which means reachable-but-unusable, and whether the request carried
the header it needed to.

Requests are recorded, because several claims are about what was SENT: that
brokering authenticates with `X-Vault-Token`, and that a fresh credential is
not re-brokered. Both need the request, not the reply.
"""

import json
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HEALTHY_LEADER = '"192.168.2.30:8300"'

LOOKUP_SELF = {
    "data": {
        "display_name": "userpass-jasper",
        "meta": {"username": "jasper"},
        # 7h30m, so the formatting shows rather than rounding to nothing.
        "ttl": 27000,
        "policies": ["default"],
        "identity_policies": ["developer"],
        "entity_id": "351f302a",
    }
}

# The three policy keys are what the live cluster really returns, measured
# 2026-08-02. They differ, and that difference is the point: F2 sets
# `token_policies = []` and F11 grants through an identity group, so a reader
# that trusts `token_policies` alone sees `default` and concludes the user has
# no grants.
LOGIN_RESPONSE = {
    "auth": {
        "client_token": "hvs.session-token",
        "accessor": "vault-accessor",
        "entity_id": "351f302a",
        "policies": ["default", "developer"],
        "token_policies": ["default"],
        "identity_policies": ["developer"],
        "lease_duration": 2764800,
        "renewable": True,
    }
}

# Measured against the live cluster on 2026-08-02. The two engines disagree
# about what the token and accessor are called, which is the whole reason
# `broker.py` has a mapping table.
NOMAD_CREDS = {
    "lease_id": "nomad/creds/deploy/P91NPuNOuvLcSSgUqmNUrNsD",
    "lease_duration": 1800,
    "renewable": True,
    "data": {"secret_id": "nomad-secret-id", "accessor_id": "nomad-accessor-id"},
}

CONSUL_CREDS = {
    "lease_id": "consul/creds/deploy/eeJyUe15gUdzFNQ6wh2PHNCE",
    "lease_duration": 1800,
    "renewable": True,
    "data": {
        "token": "consul-token",
        "accessor": "consul-accessor",
        "consul_namespace": "",
        "local": False,
        "partition": "",
    },
}

HEALTHY_ROUTES: dict[str, tuple[int, bytes]] = {
    "/v1/sys/health": (200, b'{"sealed":false}'),
    "/v1/agent/health": (200, b'{"server":{"ok":true}}'),
    "/v1/status/leader": (200, HEALTHY_LEADER.encode()),
    "/v1/auth/token/lookup-self": (200, json.dumps(LOOKUP_SELF).encode()),
    "/v1/auth/userpass/login/operator": (200, json.dumps(LOGIN_RESPONSE).encode()),
    "/v1/auth/token/revoke-self": (204, b""),
    "/v1/auth/token/renew-self": (
        200,
        json.dumps({"auth": {"lease_duration": 2764800, "renewable": True}}).encode(),
    ),
    "/v1/nomad/creds/deploy": (200, json.dumps(NOMAD_CREDS).encode()),
    "/v1/consul/creds/deploy": (200, json.dumps(CONSUL_CREDS).encode()),
}


@dataclass
class Request:
    """One request the server answered."""

    method: str
    path: str
    token: str | None
    body: bytes = b""

    def json(self) -> dict[str, object]:
        return dict(json.loads(self.body)) if self.body else {}


class FakeCluster(ThreadingHTTPServer):
    """Each route's reply is a `(status, body)` a test may rewrite."""

    routes: dict[str, tuple[int, bytes]]
    requests: list[Request] = field(default_factory=list)

    def requests_for(self, path: str) -> list[Request]:
        return [item for item in self.requests if item.path == path]


class Handler(BaseHTTPRequestHandler):
    def _respond(self) -> None:
        server: FakeCluster = self.server  # type: ignore[assignment]
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length) if length else b""
        server.requests.append(
            Request(
                method=self.command,
                path=self.path,
                token=self.headers.get("X-Vault-Token"),
                body=body,
            )
        )
        status, reply = server.routes.get(self.path, (404, b"no such route"))
        self.send_response(status)
        self.send_header("Content-Length", str(len(reply)))
        self.end_headers()
        if reply:
            self.wfile.write(reply)

    def do_GET(self) -> None:  # noqa: N802  (BaseHTTPRequestHandler's contract)
        self._respond()

    def do_POST(self) -> None:  # noqa: N802
        self._respond()

    def do_PUT(self) -> None:  # noqa: N802
        self._respond()

    def log_message(self, format: str, *args: object) -> None:
        """Silence the default stderr access log."""
