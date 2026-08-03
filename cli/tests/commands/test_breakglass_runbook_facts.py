"""Drift tests: every fact in the runbook is pinned to the repo file that
states it.

Each test parses the source file, extracts the value, and asserts the
runbook agrees. Each carries a self-check that the parse found something, so
a parser returning None cannot pass vacuously. When the repo fact changes,
the test goes red and forces the runbook edit.

The anchor set for every LAN address includes configure_network.yml, not
haproxy.hcl alone: haproxy still dials 192.168.2.30:8200 after N4 closes
8200 to the LAN, because haproxy runs on the manager itself. Pinning to
haproxy alone produces a permanently green test and zero information.
"""

from pathlib import Path

import pytest

from localstack_cli.commands.breakglass import _load_runbook

RUNBOOK = _load_runbook()

# The repo root: cli/tests/commands/<this file> -> repo root is three up.
REPO_ROOT = Path(__file__).resolve().parents[3]


def _require(value: str | None, what: str) -> str:
    """Self-check: a None from the parser cannot pass vacuously."""
    if not value:
        pytest.fail(f"parser found no {what} — the runbook cannot be checked")
    return value


# -- Manager IP and username -------------------------------------------------


def test_runbook_names_the_manager_ip_from_inventory() -> None:
    inventory = REPO_ROOT / "bootstrap" / "inventory" / "cluster.ini"
    text = inventory.read_text()
    # cluster.ini: firebat ansible_host=192.168.2.30
    match = pytest.importorskip("re").search(r"ansible_host=(\d+\.\d+\.\d+\.\d+)", text)
    ip = _require(match.group(1) if match else None, "manager IP in cluster.ini")
    assert ip in RUNBOOK, (
        f"manager IP {ip} (cluster.ini) not in the runbook. "
        "Update the runbook to match bootstrap/inventory/cluster.ini."
    )


def test_runbook_names_the_manager_username_from_inventory() -> None:
    inventory = REPO_ROOT / "bootstrap" / "inventory" / "cluster.ini"
    text = inventory.read_text()
    assert "firebat" in text, "cluster.ini no longer names firebat — check the inventory"
    assert "firebat" in RUNBOOK, "the runbook does not name the manager user firebat"


# -- unseal_vault recipe -----------------------------------------------------


def test_runbook_names_the_unseal_recipe_from_the_justfile() -> None:
    justfile = REPO_ROOT / "justfile"
    text = justfile.read_text()
    assert "unseal_vault" in text, "the root justfile no longer has an unseal_vault recipe"
    assert "just unseal_vault" in RUNBOOK, (
        "the runbook does not print `just unseal_vault`. Update it to match the root justfile."
    )


# -- /opt/vault/init.json ----------------------------------------------------


def test_runbook_names_the_init_file_path_from_ansible() -> None:
    tasks = REPO_ROOT / "bootstrap" / "roles" / "vault_server" / "tasks" / "main.yml"
    text = tasks.read_text()
    assert "/opt/vault/init.json" in text, (
        "vault_server/tasks/main.yml no longer writes /opt/vault/init.json"
    )
    assert "/opt/vault/init.json" in RUNBOOK, (
        "the runbook does not name /opt/vault/init.json. "
        "Update it to match bootstrap/roles/vault_server/tasks/main.yml."
    )


# -- Vault port --------------------------------------------------------------


def test_runbook_names_the_vault_port_from_the_listener() -> None:
    template = REPO_ROOT / "bootstrap" / "roles" / "vault_server" / "templates" / "vault.hcl.j2"
    text = template.read_text()
    match = pytest.importorskip("re").search(r"address\s*=\s*\"0\.0\.0\.0:(\d+)\"", text)
    port = _require(match.group(1) if match else None, "Vault listener port")
    assert f":{port}" in RUNBOOK or f"127.0.0.1:{port}" in RUNBOOK, (
        f"Vault port {port} (vault.hcl.j2) not in the runbook. "
        "Update the runbook to match the listener config."
    )


# -- Edge hostnames from haproxy ACLs ----------------------------------------


@pytest.mark.parametrize("service", ["vault", "nomad", "consul"])
def test_runbook_names_each_edge_hostname_from_haproxy(service: str) -> None:
    haproxy = REPO_ROOT / "deployments" / "infrastructure" / "services" / "haproxy.hcl"
    text = haproxy.read_text()
    hostname = f"{service}.lab.orangecluster.nl"
    assert hostname in text, f"haproxy.hcl no longer routes {hostname}"
    assert hostname in RUNBOOK, (
        f"the runbook does not name the edge hostname {hostname}. "
        "Update it to match deployments/infrastructure/services/haproxy.hcl."
    )


# -- LAN reachability pins: the requirement-4 anchor that N4 turns red -------


_LAN_PORTS = {
    "consul": ("8500", 13),
    "vault": ("8200", 18),
    "nomad": ("4646", 21),
}


@pytest.mark.parametrize("service", list(_LAN_PORTS))
def test_lan_address_pinned_to_configure_network_yml(service: str) -> None:
    """Each LAN address the runbook prints is pinned to the ufw rule that
    permits it, AND that rule's from_ip is still 192.168.0.0/16. When N4
    narrows from_ip, this test goes red."""
    playbook = REPO_ROOT / "bootstrap" / "playbooks" / "configure_network.yml"
    text = playbook.read_text()
    port, _line = _LAN_PORTS[service]
    assert f"port: {port}" in text, (
        f"configure_network.yml no longer allows port {port} — "
        "the LAN route for this service is gone. Update the runbook."
    )
    # The from_ip for the API ports must still be the broad LAN CIDR. If N4
    # narrowed it, the runbook's conditional LAN paragraph must be corrected.
    # Parse the line carrying this port and check its from_ip.
    import re

    pattern = rf"port:\s*{port}\b.*?from_ip:\s*\"([^\"]+)\""
    match = re.search(pattern, text)
    from_ip = _require(match.group(1) if match else None, f"from_ip for port {port}")
    assert from_ip == "192.168.0.0/16", (
        f"configure_network.yml now allows port {port} from {from_ip}, not "
        "192.168.0.0/16. N4 has landed or the LAN rule changed — update the "
        "conditional LAN paragraph in breakglass_runbook.md."
    )
    # The runbook must still print the matching 192.168.2.30:<port> address.
    assert f"192.168.2.30:{port}" in RUNBOOK, (
        f"the runbook no longer prints 192.168.2.30:{port} but the firewall "
        "still allows it. Update the runbook."
    )


def test_the_lan_anchor_set_contains_configure_network_yml() -> None:
    """A later simplification cannot quietly drop the only pin that can go
    red. This test exists so the next reader does not delete the
    configure_network.yml pin as redundant with haproxy.hcl."""
    # The parametrized test above is the pin. This test asserts the file is
    # present and parseable, so the suite cannot pass if the file moves.
    playbook = REPO_ROOT / "bootstrap" / "playbooks" / "configure_network.yml"
    assert playbook.exists(), (
        "configure_network.yml moved or was deleted. The LAN reachability "
        "pin no longer has a file to anchor against. Update the drift tests."
    )
    assert playbook.read_text(), "configure_network.yml is empty — the pin is vacuous"
