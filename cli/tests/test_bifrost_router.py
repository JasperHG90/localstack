"""Bifrost's Jev provider, Complexity Router and router key stay as decided.

The router reroutes only the `router` virtual key's chats by complexity tier,
so every other key keeps its model and pays no classifier call. The assertions
read the rendered config.json in services/bifrost.hcl and the Terraform in
services.tf, since both feed the running gateway.
"""

import importlib.util
import json
import re
import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

# cli/tests/<this file> -> repo root is two up.
REPO_ROOT = Path(__file__).resolve().parents[2]
APPS = REPO_ROOT / "deployments" / "applications"
JOBSPEC = APPS / "services" / "bifrost.hcl"
SERVICES_TF = APPS / "services.tf"
SMOKE = REPO_ROOT / "scripts" / "bifrost_smoke.py"

CLASSIFIER = ("ollama", "clef:27b")
TIERS = {
    "SIMPLE": ("ollama", "gpt-oss:120b"),
    "MEDIUM": ("ollama", "deepseek-v4.1-flash"),
    "COMPLEX": ("ollama", "mistral-large-4"),
}
CLOUD_SUFFIX = re.compile(r"[:-]cloud$")
HAND_MADE_TOP_PRIORITY = 3


def _heredocs(text: str) -> list[str]:
    return re.findall(r"<<EOF\n(.*?)\nEOF", text, flags=re.S)


def _config() -> dict[str, Any]:
    body = next(h for h in _heredocs(JOBSPEC.read_text()) if h.startswith("{\n"))
    config: dict[str, Any] = json.loads(re.sub(r"\$\{[a-z_]+\}", "templated", body))
    return config


def _block(text: str, header: str) -> str:
    start = text.find(header)
    if start == -1:
        pytest.fail(f"no `{header}` block; the check cannot run")
    depth = 0
    for i in range(start, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    pytest.fail(f"`{header}` block never closes")


def _router_key() -> list[dict[str, Any]]:
    block = _block(SERVICES_TF.read_text(), 'resource "bifrost_virtual_key" "router" {')
    entries = []
    for line in re.findall(r"\{ provider = .*?\}(?=,?\n)", block):
        provider = re.search(r'provider = "([^"]+)"', line)
        models = re.search(r"allowed_models = \[([^\]]*)\]", line)
        assert provider and models, line
        entries.append(
            {
                "provider": provider.group(1),
                "allowed_models": re.findall(r'"([^"]+)"', models.group(1)),
                "line": line,
            }
        )
    return entries


def test_typesafe_provider() -> None:
    typesafe = _config()["providers"]["typesafe"]
    assert "network_config" not in typesafe or "base_url" not in typesafe["network_config"]
    assert [k["value"] for k in typesafe["keys"]] == ["env.TYPESAFE_API_KEY"]

    env = next(h for h in _heredocs(JOBSPEC.read_text()) if "BIFROST_ADMIN_USERNAME" in h)
    assert (
        '{{- with secret "${typesafe_secret}" }}\n'
        "TYPESAFE_API_KEY={{ .Data.data.TYPESAFE_API_KEY }}\n"
        "{{- end }}"
    ) in env
    job = _block(SERVICES_TF.read_text(), 'resource "nomad_job" "bifrost" {')
    assert re.search(
        r'typesafe_secret\s*=\s*"\$\{var\.secret_mount\}/data/default/bifrost/typesafe"', job
    )


def test_complexity_router() -> None:
    governance = _config()["governance"]
    analyzer = governance["complexity_analyzer_config"]
    assert analyzer["classifier"] == "decision"
    decision = analyzer["decision"]
    assert (decision["provider"], decision["model"]) == CLASSIFIER
    assert decision["timeout"] == "3s"
    for name in ("simple_keywords", "medium_keywords", "complex_keywords"):
        assert analyzer["keywords"][name], f"{name} is empty"

    rules = sorted(governance["routing_rules"], key=lambda r: r["priority"])
    priorities = [r["priority"] for r in rules]
    # The live store holds hand-made global rules at 0-3 for Claude Code's model
    # aliases. Ours must not reuse a priority, and must run after those.
    assert len(set(priorities)) == len(priorities), priorities
    assert min(priorities) > HAND_MADE_TOP_PRIORITY, priorities
    first, *tier_rules = rules
    assert first["cel_expression"] == 'virtual_key_name != "router"'
    assert first["targets"] == [{"weight": 1}]

    routed = {}
    for rule in tier_rules:
        cel = rule["cel_expression"]
        assert cel.startswith('virtual_key_name == "router" && '), cel
        tier = re.fullmatch(r'.* && complexity_tier == "([A-Z]+)"', cel)
        assert tier, cel
        [target] = rule["targets"]
        routed[tier.group(1)] = (target["provider"], target["model"])
    assert routed == TIERS


def _assert_no_cloud_suffix() -> None:
    config = _config()
    names = [config["governance"]["complexity_analyzer_config"]["decision"]["model"]]
    names += [
        t["model"]
        for r in config["governance"]["routing_rules"]
        for t in r["targets"]
        if "model" in t
    ]
    names += [m for p in config["providers"].values() for k in p["keys"] for m in k["models"]]
    services = SERVICES_TF.read_text()
    for key in re.findall(r'resource "bifrost_virtual_key" "([a-z]+)"', services):
        block = _block(services, f'resource "bifrost_virtual_key" "{key}" {{')
        for models in re.findall(r"allowed_models = \[([^\]]*)\]", block):
            names += re.findall(r'"([^"]+)"', models)
    assert len(names) > 10, names
    assert [n for n in names if CLOUD_SUFFIX.search(n)] == []


def test_router_key() -> None:
    entries = _router_key()
    providers = [e["provider"] for e in entries]
    assert providers == sorted(providers)
    by_provider = {e["provider"]: e for e in entries}
    ollama = by_provider["ollama"]["allowed_models"]
    assert "*" not in ollama
    assert set(ollama) == {CLASSIFIER[1], *(m for _, m in TIERS.values())}
    assert "typesafe" in by_provider
    for e in entries:
        assert 'key_ids = ["*"]' in e["line"]
    _assert_no_cloud_suffix()


def _load_smoke() -> ModuleType:
    spec = importlib.util.spec_from_file_location("bifrost_smoke", SMOKE)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


Served = dict[str, tuple[str, int]]


@pytest.fixture
def gateway() -> Iterator[tuple[str, Served]]:
    """A stub gateway answering each prompt with (served model, classifier calls)."""
    served: Served = {}

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            model, calls = served[body["messages"][0]["content"]]
            payload = {
                "extra_fields": {
                    "routing_info": {"model": model},
                    "routing_metadata": {"calls": [{"request_type": "decisions"}] * calls},
                }
            }
            data = json.dumps(payload).encode()
            self.send_response(200)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, *_: object) -> None:
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_address[1]}", served
    server.shutdown()


@pytest.mark.parametrize(
    ("routed", "calls", "fails"),
    [(True, 1, False), (False, 1, True), (True, 0, True)],
    ids=["routed", "not-routed", "no-classifier-call"],
)
def test_smoke_router_check(
    gateway: tuple[str, Served], routed: bool, calls: int, fails: bool
) -> None:
    smoke = _load_smoke()
    base, served = gateway
    for prompt, want in smoke.ROUTED_PROMPTS:
        served[prompt] = (want if routed else "deepseek-v4.1-flash", calls)
    if fails:
        with pytest.raises(smoke.SmokeFailure):
            smoke.assert_router_routes_by_tier(base, "vk")
    else:
        smoke.assert_router_routes_by_tier(base, "vk")


@pytest.mark.parametrize(
    ("model", "calls", "fails"),
    [
        ("deepseek-v4.1-flash", 0, False),
        ("mistral-large-4", 0, True),
        ("deepseek-v4.1-flash", 1, True),
    ],
    ids=["kept", "rerouted", "classifier-called"],
)
def test_smoke_hermes_check(
    gateway: tuple[str, Served], model: str, calls: int, fails: bool
) -> None:
    smoke = _load_smoke()
    base, served = gateway
    served[smoke.HARD_PROMPT] = (model, calls)
    if fails:
        with pytest.raises(smoke.SmokeFailure):
            smoke.assert_hermes_not_rerouted(base, "vk")
    else:
        smoke.assert_hermes_not_rerouted(base, "vk")
