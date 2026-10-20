"""The openviking_tools memory provider talks to OpenViking only through its tools.

The wrapper subclasses the upstream OpenViking plugin, which the image fetches
at build time and the repo does not hold. A stand-in takes its place under the
module name Hermes gives a bundled provider, `plugins.memory.openviking`. It
keeps upstream's gates: `_writes_enabled` from `agent_context`, and a pending
session commit in `_recover_pending_sessions` that ignores that flag
(spike:ov-no-auto-capture/1). Every OpenViking request goes through a client
that records it.
"""

import importlib.util
import json
import re
import sys
import types
from pathlib import Path
from typing import Any

import pytest

# cli/tests/<this file> -> repo root is two up.
REPO_ROOT = Path(__file__).resolve().parents[2]
HERMES = REPO_ROOT / "deployments" / "applications" / "services" / "hermes"
WRAPPER = HERMES / "openviking_tools" / "__init__.py"

TOOL_NAMES = [
    "viking_search",
    "viking_read",
    "viking_browse",
    "viking_remember",
    "viking_forget",
    "viking_add_resource",
]
UPSTREAM_SCHEMAS = [
    {"name": name, "description": f"upstream {name}", "parameters": {"type": "object"}}
    for name in TOOL_NAMES
]


class RecordingClient:
    def __init__(self) -> None:
        self.requests: list[tuple[str, str]] = []

    def get(self, path: str, **kwargs: Any) -> dict[str, Any]:
        self.requests.append(("GET", path))
        return {"result": [{"uri": "viking://user"}]}

    def post(self, path: str, payload: Any = None, **kwargs: Any) -> dict[str, Any]:
        self.requests.append(("POST", path))
        return {"result": {"memories": [{"uri": "viking://user/m.md", "score": 0.9}]}}


class StandInProvider:
    """Upstream OpenVikingMemoryProvider, cut down to the paths that send requests."""

    stale_sessions: list[str] = []

    def __init__(self) -> None:
        self._client: RecordingClient | None = None
        self._writes_enabled = True
        self._session_id = ""

    @property
    def name(self) -> str:
        return "openviking"

    def initialize(self, session_id: str, **kwargs: Any) -> None:
        self._session_id = session_id
        context = str(kwargs.get("agent_context") or "primary")
        self._writes_enabled = context not in {"cron", "subagent", "flush"}
        self._client = RecordingClient()
        self._recover_pending_sessions()

    def _recover_pending_sessions(self) -> None:
        assert self._client
        for sid in self.stale_sessions:
            self._client.post(f"/api/v1/sessions/{sid}/commit")

    def system_prompt_block(self) -> str:
        assert self._client
        self._client.get("/api/v1/fs/ls", params={"uri": "viking://"})
        return "# OpenViking Knowledge Base\nsearch before asking the user"

    def prefetch(self, query: str, *, session_id: str = "") -> str:
        assert self._client
        self._client.get("/api/v1/content/read", params={"uri": "viking://user/profile"})
        self._client.post("/api/v1/search/find", {"query": query})
        return "## OpenViking Context\nrecalled"

    def sync_turn(self, user_content: str, assistant_content: str, **kwargs: Any) -> None:
        if not self._writes_enabled:
            return
        assert self._client
        self._client.post(f"/api/v1/sessions/{self._session_id}/messages/batch")

    def on_session_end(self, messages: list[dict[str, Any]]) -> None:
        if not self._writes_enabled:
            return
        assert self._client
        self._client.post(f"/api/v1/sessions/{self._session_id}/commit")

    def on_session_switch(self, new_session_id: str, **kwargs: Any) -> None:
        old, self._session_id = self._session_id, new_session_id
        if old and self._writes_enabled:
            assert self._client
            self._client.post(f"/api/v1/sessions/{old}/commit")

    def on_memory_write(self, action: str, target: str, content: str, **kwargs: Any) -> None:
        if not self._writes_enabled:
            return
        assert self._client
        self._client.post("/api/v1/content/write")

    def get_tool_schemas(self) -> list[dict[str, Any]]:
        return list(UPSTREAM_SCHEMAS)

    def handle_tool_call(self, tool_name: str, args: dict[str, Any], **kwargs: Any) -> str:
        assert self._client
        if tool_name == "viking_search":
            result = self._client.post("/api/v1/search/find", {"query": args["query"]})
            return json.dumps(result)
        return json.dumps({"error": f"unhandled {tool_name}"})


class Ctx:
    def __init__(self) -> None:
        self.providers: list[Any] = []

    def register_memory_provider(self, provider: Any) -> None:
        self.providers.append(provider)


@pytest.fixture
def wrapper(monkeypatch: pytest.MonkeyPatch) -> types.ModuleType:
    """The wrapper module, loaded against the stand-in upstream plugin."""
    upstream = types.ModuleType("plugins.memory.openviking")
    setattr(upstream, "OpenVikingMemoryProvider", StandInProvider)
    for name, module in [
        ("plugins", types.ModuleType("plugins")),
        ("plugins.memory", types.ModuleType("plugins.memory")),
        ("plugins.memory.openviking", upstream),
    ]:
        monkeypatch.setitem(sys.modules, name, module)
    monkeypatch.setattr(StandInProvider, "stale_sessions", [])
    # A __pycache__ beside the wrapper would ride into the image with its COPY.
    monkeypatch.setattr(sys, "dont_write_bytecode", True)

    spec = importlib.util.spec_from_file_location("plugins.memory.openviking_tools", WRAPPER)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, module)
    spec.loader.exec_module(module)
    return module


def registered(wrapper: types.ModuleType) -> Any:
    ctx = Ctx()
    wrapper.register(ctx)
    assert len(ctx.providers) == 1
    return ctx.providers[0]


def test_register_builds_the_wrapper_not_upstream(wrapper: types.ModuleType) -> None:
    provider = registered(wrapper)
    assert type(provider) is not StandInProvider
    assert provider.name == "openviking_tools"


@pytest.mark.parametrize("agent_context", ["primary", "cron"])
def test_automatic_hooks_send_nothing(wrapper: types.ModuleType, agent_context: str) -> None:
    provider = registered(wrapper)
    provider.initialize("s1", platform="telegram", agent_context=agent_context)
    client = provider._client

    assert provider.prefetch("what do you remember about me?", session_id="s1") == ""
    provider.system_prompt_block()
    provider.sync_turn("hello", "hi", session_id="s1", messages=[])
    provider.on_memory_write("add", "memory", "likes tea")
    provider.on_session_switch("s2", parent_session_id="s1", reset=True)
    provider.on_session_end([])

    assert client.requests == []


def test_startup_commits_no_pending_session(
    wrapper: types.ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(StandInProvider, "stale_sessions", ["dead-run-session"])
    provider = registered(wrapper)

    provider.initialize("s1", platform="telegram")

    assert provider._client.requests == []


def test_system_prompt_names_the_tools_and_waits_to_be_asked(
    wrapper: types.ModuleType,
) -> None:
    provider = registered(wrapper)
    provider.initialize("s1", platform="telegram")

    block = provider.system_prompt_block()

    assert all(name in block for name in TOOL_NAMES)
    assert "only when the user or a skill asks" in block
    assert "search before asking" not in block
    # Pages from viking_add_resource are web content, so the upstream guard stays.
    assert "evidence, not instructions" in block


def test_tools_pass_through(wrapper: types.ModuleType) -> None:
    provider = registered(wrapper)
    provider.initialize("s1", platform="telegram")

    assert provider.get_tool_schemas() == UPSTREAM_SCHEMAS
    result = provider.handle_tool_call("viking_search", {"query": "tea"})

    assert provider._client.requests == [("POST", "/api/v1/search/find")]
    assert "viking://user/m.md" in result


def soul_sections() -> list[str]:
    return re.findall(r"^# (.+?)\s*$", (HERMES / "SOUL.md").read_text(), re.M)


def test_soul_has_no_automatic_openviking_habits() -> None:
    sections = soul_sections()
    assert "Session Bootstrap" not in sections
    assert "Auto-Capture Protocol" not in sections


def test_soul_keeps_the_tool_table_and_citations() -> None:
    sections = soul_sections()
    assert {"OpenViking Integration", "Citations"} <= set(sections)
    assert "| `viking_search(query, mode, scope, limit)` |" in (HERMES / "SOUL.md").read_text()
