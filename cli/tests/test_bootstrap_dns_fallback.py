"""The DNS playbook gives the NetworkManager nodes fallback resolvers.

radxa and orange_pi_4a write /etc/resolv.conf from NetworkManager with only the
router in it, so one dropped query fails a lookup. The play drops a
NetworkManager global-DNS file that lists public fallbacks after the router.
"""

import configparser
from pathlib import Path
from typing import Any

import yaml

# cli/tests/<this file> -> repo root is two up.
REPO_ROOT = Path(__file__).resolve().parents[2]
PLAYBOOK = REPO_ROOT / "bootstrap" / "playbooks" / "configure_dns.yml"
DROP_IN = "/etc/NetworkManager/conf.d/90-dns-fallback.conf"


def dns_play() -> dict[str, Any]:
    plays: list[dict[str, Any]] = yaml.safe_load(PLAYBOOK.read_text())
    matches = [
        play
        for play in plays
        if any(
            task.get("ansible.builtin.copy", {}).get("dest") == DROP_IN
            for task in play.get("tasks", [])
        )
    ]
    assert len(matches) == 1, f"expected one play writing {DROP_IN}"
    return matches[0]


def drop_in() -> configparser.ConfigParser:
    task = next(
        task
        for task in dns_play()["tasks"]
        if task.get("ansible.builtin.copy", {}).get("dest") == DROP_IN
    )
    parser = configparser.ConfigParser()
    parser.read_string(task["ansible.builtin.copy"]["content"])
    return parser


def test_play_targets_only_the_networkmanager_nodes() -> None:
    hosts = dns_play()["hosts"].split(":")
    assert sorted(hosts) == ["orange_pi_4a", "radxa"]


def test_router_comes_first_then_public_fallbacks() -> None:
    servers = drop_in()["global-dns-domain-*"]["servers"]
    assert servers.split(",") == ["192.168.2.254", "1.1.1.1", "9.9.9.9"]


def test_short_timeout_and_search_domain_are_kept() -> None:
    global_dns = drop_in()["global-dns"]
    assert global_dns["options"].split(",") == ["timeout:1", "attempts:2"]
    assert global_dns["searches"] == "home"
