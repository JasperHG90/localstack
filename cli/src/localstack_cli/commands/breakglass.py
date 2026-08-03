"""`localstack breakglass`: the recovery runbook, plus read-only probes.

This command is the one you reach for when you cannot authenticate or the
cluster is not answering. It prints a runbook with a section per failure
mode, and optionally runs unauthenticated probes to say which one you are
in. It never holds, reads, sends, or prints a credential.

Credential boundary (load-bearing, see the plan's non-goals):

- No read of `VAULT_TOKEN`, `VAULT_UNSEAL_KEY_*`, `NOMAD_TOKEN`,
  `CONSUL_HTTP_TOKEN` for any purpose, including "just to check".
- No subprocess, no SSH, no `vault`/`nomad`/`consul`/`ansible`/`terraform`.
- No read of `/opt/vault/init.json`. The runbook names it; the code never
  opens it.
- No credential on any probe. The probes are unauthenticated GETs.

Probes are read-only, time-bounded, and non-fatal. A failed probe degrades
to printing the whole runbook rather than raising. The command always exits
0, because it is documentation and a non-zero exit invites a wrapper to
swallow the output.
"""

from __future__ import annotations

import sys
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from importlib import resources

import typer

app = typer.Typer()

# Long enough for a cluster on the far side of a tailnet, short enough that a
# down node does not make the runbook feel broken. Matches status.py.
PROBE_TIMEOUT_SECONDS = 3.0

# The edge hostnames the runbook names. Each routes by Host header through
# HAProxy on 443 to the matching plaintext backend on the manager.
EDGE = {
    "vault": "https://vault.lab.orangecluster.nl",
    "nomad": "https://nomad.lab.orangecluster.nl",
    "consul": "https://consul.lab.orangecluster.nl",
}

# The direct LAN addresses. Conditional: they answer only from
# 192.168.0.0/16 and only while configure_network.yml allows the port from
# that CIDR. N4-netsec-edge-only-service-access removes that allow.
LAN = {
    "vault": "http://192.168.2.30:8200",
    "nomad": "http://192.168.2.30:4646",
    "consul": "http://192.168.2.30:8500",
}

# The per-service health path. Vault's /v1/sys/health encodes state in the
# status code (200 active, 429 standby, 503 sealed, 501 uninitialized), so a
# sealed Vault is "answered", not "unreachable".
HEALTH_PATH = {
    "vault": "/v1/sys/health",
    "nomad": "/v1/agent/health",
    "consul": "/v1/status/leader",
}

# The three finding classes from requirement 9. Edge up with LAN dark is a
# firewall change, not an outage; everything dark is your own connectivity
# or the cluster; a service answering with a bad state names the section.
FIREWALL_CHANGE = (
    "the direct LAN addresses did not answer but the edge did, "
    "so the services are up. This is what a firewall change looks like, "
    "not an outage"
)


@dataclass(frozen=True)
class ProbeResult:
    """One probe's outcome: did it answer, and what did it say."""

    name: str
    route: str
    answered: bool
    detail: str


def _get(url: str) -> tuple[int | None, bytes | None, str | None]:
    """GET a URL, returning (status, body, error).

    An HTTP error status is still an answer: a 503 from Vault proves the
    address is right. A network error (timeout, refused, DNS) is not an
    answer and returns (None, None, reason).
    """
    request = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=PROBE_TIMEOUT_SECONDS) as response:
            return int(response.status), response.read(), None
    except urllib.error.HTTPError as error:
        # An HTTPError is still a response from the server.
        return int(error.code), error.read(), None
    except OSError as error:
        return None, None, _reason(error)


def _reason(error: OSError) -> str:
    """Collapse a socket error to one line."""
    if isinstance(error, TimeoutError):
        return "timed out"
    message = str(getattr(error, "reason", error)) or error.__class__.__name__
    return message.removeprefix("[Errno 111] ").strip()


def _probe(service: str, base: str) -> ProbeResult:
    """Probe one service at one base URL."""
    url = base + HEALTH_PATH[service]
    status, body, error = _get(url)
    if error is not None:
        return ProbeResult(service, base, False, error)
    assert status is not None  # _get guarantees status when error is None
    if service == "vault" and status == 503:
        return ProbeResult(service, base, True, "sealed")
    if service == "consul" and status == 200:
        assert body is not None
        leader = body.decode(errors="replace").strip().strip('"')
        if not leader:
            return ProbeResult(service, base, True, "no leader")
        return ProbeResult(service, base, True, f"leader {leader}")
    if status == 200:
        return ProbeResult(service, base, True, "ok")
    return ProbeResult(service, base, True, f"HTTP {status}")


def _run_probes() -> dict[str, dict[str, ProbeResult]]:
    """Probe edge (tier 1) and LAN (tier 2) for all three services.

    Edge first: the edge is the path that survives N4. LAN addresses are
    tier 2, secondary and interpreted, never reported raw.
    """
    services = ("vault", "nomad", "consul")
    results: dict[str, dict[str, ProbeResult]] = {s: {} for s in services}

    def probe_edge(svc: str) -> None:
        results[svc]["edge"] = _probe(svc, EDGE[svc])

    def probe_lan(svc: str) -> None:
        results[svc]["lan"] = _probe(svc, LAN[svc])

    with ThreadPoolExecutor(max_workers=6) as pool:
        for s in services:
            pool.submit(probe_edge, s)
            pool.submit(probe_lan, s)
    return results


def _diagnose(results: dict[str, dict[str, ProbeResult]]) -> str:
    """Render the requirement-9 finding from the probe matrix.

    The banned output is a bare "Vault unreachable". Three probes going dark
    at once while the edge answers is the signature of a policy change, and
    saying "unreachable" there sends the reader to fix a cluster that is
    fine.
    """
    edge_up = [r.name for r in (results[s]["edge"] for s in results) if r.answered]
    lan_up = [r.name for r in (results[s]["lan"] for s in results) if r.answered]

    # A service answering with a bad state (Vault sealed, Consul no leader)
    # names the section that treats it.
    bad_states: list[str] = []
    for svc in results:
        edge = results[svc]["edge"]
        if edge.answered and edge.detail in ("sealed", "no leader"):
            bad_states.append(f"{svc}: {edge.detail}")

    if bad_states:
        lines = [f"Reachable but reporting a bad state: {', '.join(bad_states)}."]
        for svc, detail in [(s.split(": ")[0], s.split(": ")[1]) for s in bad_states]:
            if detail == "sealed":
                lines.append("See the 'Vault is sealed' section.")
            elif detail == "no leader":
                lines.append("See the 'Consul is unreachable' section.")
        return "\n".join(lines)

    # Edge answers, LAN does not: a firewall change, not an outage.
    if edge_up and not lan_up:
        return f"{FIREWALL_CHANGE}. See the SSH plus loopback route in each service section."

    # Nothing answers, including the edge: your connectivity or the cluster.
    if not edge_up and not lan_up:
        return (
            "Nothing answered, including the edge. Check your own "
            "connectivity first (the prelude), then the cluster. See "
            "'Check your own connectivity first' and 'Edge down, cluster up'."
        )

    # Everything answers: nothing is broken.
    if edge_up and lan_up:
        return "All probes answered. The cluster is reachable."

    # Mixed: some edge up, some LAN up. Report what answered.
    return (
        f"Edge answered for: {', '.join(edge_up) or 'none'}. "
        f"LAN answered for: {', '.join(lan_up) or 'none'}. "
        "Read the matching section for any service that did not answer."
    )


def _load_runbook() -> str:
    """Load the runbook markdown shipped as package data."""
    return (
        resources.files("localstack_cli.commands")
        .joinpath("breakglass_runbook.md")
        .read_text(encoding="utf-8")
    )


@app.command()
def breakglass(
    no_probe: bool = typer.Option(
        False,
        "--no-probe",
        help="Skip the reachability probes; print the runbook only.",
    ),
) -> None:
    """Print the break-glass recovery runbook, with optional probes.

    Probes are read-only, unauthenticated, and non-fatal. The command always
    exits 0: it is documentation, and a non-zero exit invites a wrapper to
    swallow the output.
    """
    runbook = _load_runbook()
    if no_probe:
        sys.stdout.write(runbook)
        return

    try:
        results = _run_probes()
        diagnosis = _diagnose(results)
    except Exception:  # noqa: BLE001
        # A probe failure must never take the command down. Degrade to
        # printing the whole runbook rather than a stack trace.
        diagnosis = ""

    if diagnosis:
        sys.stdout.write("## Probe diagnosis\n\n")
        sys.stdout.write(diagnosis)
        sys.stdout.write("\n\n")
    sys.stdout.write(runbook)
