"""Read the edge's routing table out of a rendered `haproxy.cfg`.

Pure: it takes the config text as an argument and returns dataclasses. That
is not tidiness, it is the security boundary.

The running haproxy jobspec used to carry the openfang basic-auth password in
plaintext, rendered by Terraform into the template Nomad serves. Any command
that fetched that job held a live credential in memory, and one `--json` dump
or one traceback would print it. That password went with the phoenix backend
it guarded, so today's jobspec carries none. The boundary stays: a future
backend can reintroduce one, and this module is what keeps that from becoming
a leak. So it copies out exactly four fields per route and nothing else. The
input text is never stored on a dataclass, never returned, and never put into
an exception message.

The routing table comes from the API, never from the Terraform source under
the deployments tree. That file is a `templatefile` input holding `${...}`
interpolations inside a heredoc. It is not what the edge is running, and two
live jobs have no file there at all.
"""

import re
from dataclasses import dataclass

from localstack_cli.api.errors import ClusterError

# `acl is_<name>  hdr(host) -i <hostname>`
ACL = re.compile(r"^\s*acl\s+is_(?P<name>\S+)\s+hdr\(host\)\s+-i\s+(?P<host>\S+)\s*$", re.M)
# `use_backend <backend> if is_<name>`
USE_BACKEND = re.compile(r"^\s*use_backend\s+(?P<backend>\S+)\s+if\s+is_(?P<name>\S+)\s*$", re.M)
# `backend <name>` opening a block.
BACKEND = re.compile(r"^backend\s+(?P<backend>\S+)\s*$", re.M)
# `server <id> <host>:<port> ...` inside one.
SERVER = re.compile(r"^\s*server\s+\S+\s+(?P<host>[^\s:]+):(?P<port>\d+)", re.M)


class HaproxyParseError(ClusterError):
    """The config could not be read.

    Carries no input text, deliberately. An exception that quotes the config
    it failed on would print the credential that config contains.

    A `ClusterError` rather than a bare `RuntimeError` so the command layer
    catches it. Escaping to typer would put a traceback on screen whose
    frames still hold the template text.
    """


@dataclass(frozen=True)
class Route:
    """One hostname the edge serves, and where it sends it."""

    name: str
    hostname: str
    backend_host: str
    backend_port: int

    @property
    def url(self) -> str:
        return f"https://{self.hostname}"


def _backend_servers(config: str) -> dict[str, tuple[str, int]]:
    """The first `server` line of each `backend` block."""
    servers: dict[str, tuple[str, int]] = {}
    blocks = list(BACKEND.finditer(config))
    for index, match in enumerate(blocks):
        end = blocks[index + 1].start() if index + 1 < len(blocks) else len(config)
        body = config[match.end() : end]
        server = SERVER.search(body)
        if server:
            servers[match.group("backend")] = (server.group("host"), int(server.group("port")))
    return servers


def parse_routes(config: str) -> list[Route]:
    """Every routed hostname, with the backend behind it.

    A route needs all three parts: an ACL naming the hostname, a
    `use_backend` selecting on that ACL, and a `backend` block with a server.
    A route missing any of them is dropped rather than half-rendered.
    """
    hostnames = {match.group("name"): match.group("host") for match in ACL.finditer(config)}
    backends = {
        match.group("name"): match.group("backend") for match in USE_BACKEND.finditer(config)
    }
    servers = _backend_servers(config)

    if not hostnames:
        raise HaproxyParseError("haproxy", "no `acl ... hdr(host)` lines in the edge config")

    routes = []
    for name, hostname in sorted(hostnames.items()):
        backend = backends.get(name)
        if backend is None or backend not in servers:
            continue
        host, port = servers[backend]
        routes.append(Route(name=name, hostname=hostname, backend_host=host, backend_port=port))
    return routes
