"""The openviking_tools memory provider talks to OpenViking only through its tools.

The wrapper subclasses the upstream OpenViking plugin, which the image fetches
at build time and the repo does not hold. A stand-in takes its place under the
module name Hermes gives a bundled provider, `plugins.memory.openviking`. It
keeps upstream's gates: `_writes_enabled` from `agent_context`, and a pending
session commit in `_recover_pending_sessions` that ignores that flag
(spike:ov-no-auto-capture/1). Every OpenViking request goes through a client
that records it. Hermes's `tools.registry.tool_error` gets a stand-in too.
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
MAP_URI = "viking://user/jasper/resources/.map.md"
PAGE = "https://www.anthropic.com/engineering/building-effective-agents"


class RecordingClient:
    def __init__(self) -> None:
        self.requests: list[tuple[str, str]] = []
        self.payloads: list[tuple[str, Any]] = []

    def get(self, path: str, **kwargs: Any) -> dict[str, Any]:
        self.requests.append(("GET", path))
        return {"result": [{"uri": "viking://user"}]}

    def post(self, path: str, payload: Any = None, **kwargs: Any) -> dict[str, Any]:
        self.requests.append(("POST", path))
        self.payloads.append((path, payload))
        if path == "/api/v1/content/write":
            return {"status": "ok", "result": {"uri": payload["uri"], "written": True}}
        return {"result": {"memories": [{"uri": "viking://user/m.md", "score": 0.9}]}}

    def delete(self, path: str, **kwargs: Any) -> dict[str, Any]:
        self.requests.append(("DELETE", path))
        return {"result": {}}


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

    def _ensure_client(self) -> RecordingClient | None:
        return self._client

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
        # Upstream routes viking_<x> to _tool_<x> by getattr, so overrides apply.
        if tool_name not in TOOL_NAMES:
            return json.dumps({"error": f"Unknown tool: {tool_name}"})
        return str(getattr(self, "_tool_" + tool_name.removeprefix("viking_"))(args))

    def _tool_search(self, args: dict[str, Any]) -> str:
        assert self._client
        return json.dumps(self._client.post("/api/v1/search/find", {"query": args["query"]}))

    def _tool_read(self, args: dict[str, Any]) -> str:
        assert self._client
        return json.dumps(self._client.get("/api/v1/content/read", params={"uri": args["uri"]}))

    def _tool_browse(self, args: dict[str, Any]) -> str:
        assert self._client
        return json.dumps(self._client.get("/api/v1/fs/ls", params={"uri": args["path"]}))

    def _tool_remember(self, args: dict[str, Any]) -> str:
        assert self._client
        path = f"/api/v1/sessions/{self._session_id}/messages"
        return json.dumps(self._client.post(path, {"content": args["content"]}))

    def _tool_forget(self, args: dict[str, Any]) -> str:
        assert self._client
        return json.dumps(self._client.delete("/api/v1/fs", params={"uri": args["uri"]}))

    def _tool_add_resource(self, args: dict[str, Any]) -> str:
        assert self._client
        # Plugin 2.1.1 copies only these keys, so create_parent never reaches the server.
        keys = ("reason", "to", "parent", "instruction", "wait", "timeout")
        payload = {k: args[k] for k in keys if k in args and args[k] not in {None, ""}}
        payload["path"] = args["url"]
        result = self._client.post("/api/v1/resources", payload)
        return json.dumps({"status": "added", "root_uri": str(result)})


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
    registry = types.ModuleType("tools.registry")
    setattr(
        registry, "tool_error", lambda message, **extra: json.dumps({"error": message, **extra})
    )
    for name, module in [
        ("plugins", types.ModuleType("plugins")),
        ("plugins.memory", types.ModuleType("plugins.memory")),
        ("plugins.memory.openviking", upstream),
        ("tools", types.ModuleType("tools")),
        ("tools.registry", registry),
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

    assert all(name in block for name in [*TOOL_NAMES, "viking_write"])
    assert "only when the user or a skill asks" in block
    assert "search before asking" not in block
    # Pages from viking_add_resource are web content, so the upstream guard stays.
    assert "evidence, not instructions" in block


def connected(wrapper: types.ModuleType) -> Any:
    provider = registered(wrapper)
    provider.initialize("s1", platform="telegram")
    return provider


@pytest.mark.parametrize(
    ("tool", "args", "request_"),
    [
        ("viking_search", {"query": "tea"}, ("POST", "/api/v1/search/find")),
        ("viking_read", {"uri": MAP_URI}, ("GET", "/api/v1/content/read")),
        ("viking_browse", {"action": "list", "path": "viking://"}, ("GET", "/api/v1/fs/ls")),
        ("viking_remember", {"content": "likes tea"}, ("POST", "/api/v1/sessions/s1/messages")),
        ("viking_forget", {"uri": "viking://user/m.md"}, ("DELETE", "/api/v1/fs")),
        ("viking_add_resource", {"url": PAGE}, ("POST", "/api/v1/resources")),
    ],
)
def test_upstream_tools_pass_through_beside_viking_write(
    wrapper: types.ModuleType, tool: str, args: dict[str, Any], request_: tuple[str, str]
) -> None:
    provider = connected(wrapper)

    schemas = provider.get_tool_schemas()
    result = provider.handle_tool_call(tool, args)

    assert schemas[: len(UPSTREAM_SCHEMAS)] == UPSTREAM_SCHEMAS
    assert [s["name"] for s in schemas[len(UPSTREAM_SCHEMAS) :]] == ["viking_write"]
    assert provider._client.requests == [request_]
    assert "error" not in json.loads(result)


def write_schema(provider: Any) -> dict[str, Any]:
    (schema,) = [s for s in provider.get_tool_schemas() if s["name"] == "viking_write"]
    return dict(schema)


def test_viking_write_schema_offers_three_modes(wrapper: types.ModuleType) -> None:
    params = write_schema(connected(wrapper))["parameters"]

    assert params["properties"]["mode"]["enum"] == ["create", "replace", "append"]
    assert set(params["properties"]) == {"uri", "content", "mode"}
    assert set(params["required"]) == {"uri", "content", "mode"}


@pytest.mark.parametrize("mode", ["create", "replace", "append"])
def test_viking_write_posts_content_write(wrapper: types.ModuleType, mode: str) -> None:
    provider = connected(wrapper)
    content = "- notes/: hand saves.\n"

    result = provider.handle_tool_call(
        "viking_write", {"uri": MAP_URI, "content": content, "mode": mode}
    )

    # No processing_mode: vectors_only would make the map a search hit
    # (spike:ov-save-skill/2).
    assert provider._client.payloads == [
        ("/api/v1/content/write", {"uri": MAP_URI, "content": content, "mode": mode})
    ]
    assert json.loads(result)["result"] == {"uri": MAP_URI, "written": True}


@pytest.mark.parametrize(
    "args",
    [
        {"uri": MAP_URI, "content": "x", "mode": "overwrite"},
        {"uri": MAP_URI, "content": "x"},
        {"content": "x", "mode": "append"},
        {"uri": "", "content": "x", "mode": "append"},
        {"uri": MAP_URI, "mode": "append"},
    ],
)
def test_viking_write_refuses_bad_input_without_sending(
    wrapper: types.ModuleType, args: dict[str, Any]
) -> None:
    provider = connected(wrapper)

    result = provider.handle_tool_call("viking_write", args)

    assert json.loads(result)["error"]
    assert provider._client.requests == []


@pytest.mark.parametrize(
    ("args", "flag"),
    [
        ({"url": PAGE, "parent": "viking://user/jasper/resources/blogs/anthropic/"}, True),
        (
            {
                "url": "/opt/data/2026-10-20-standup.md",
                "parent": "viking://user/jasper/resources/x/",
            },
            True,
        ),
        ({"url": PAGE}, False),
        ({"url": PAGE, "parent": ""}, False),
        ({"url": PAGE, "to": "viking://user/jasper/resources/blogs/anthropic/agents"}, False),
    ],
)
def test_add_resource_sends_create_parent_only_with_a_parent(
    wrapper: types.ModuleType, args: dict[str, Any], flag: bool
) -> None:
    provider = connected(wrapper)

    provider.handle_tool_call("viking_add_resource", {**args, "reason": "shared"})
    provider.handle_tool_call("viking_add_resource", {**args, "reason": "again"})

    payloads = [p for path, p in provider._client.payloads if path == "/api/v1/resources"]
    assert len(payloads) == 2
    for payload in payloads:
        # OpenViking 0.4.17.1 refuses a missing parent folder without it
        # (spike:ov-save-skill/11).
        assert ("create_parent" in payload) is flag
        if flag:
            assert payload["create_parent"] is True
            assert payload["parent"] == args["parent"]
        assert payload["path"] == args["url"]


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


def test_add_resource_sends_create_parent_after_a_client_rebuild(
    wrapper: types.ModuleType,
) -> None:
    provider = connected(wrapper)
    args = {"url": PAGE, "parent": "viking://user/jasper/resources/blogs/anthropic/"}
    provider.handle_tool_call("viking_add_resource", args)

    # Upstream builds a new client when its config changes.
    provider._client = RecordingClient()
    provider.handle_tool_call("viking_add_resource", args)

    assert provider._client.payloads == [
        ("/api/v1/resources", {"parent": args["parent"], "path": PAGE, "create_parent": True})
    ]


def test_viking_write_says_create_overwrites(wrapper: types.ModuleType) -> None:
    # OpenViking 0.5.1 made mode=create overwrite an existing file.
    description = wrapper.WRITE_SCHEMA["description"]
    assert "must not exist" not in description
    assert "overwrite" in description
