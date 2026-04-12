#!/usr/bin/env python3
"""Memex skill for OpenFang — mirrors the MCP server tool names and parameters.

Tool names and parameter shapes follow the MCP implementation at:
  github.com/JasperHG90/memex/packages/mcp/src/memex_mcp/server.py

Uses the memex CLI for most operations; falls back to HTTP API for note
ingestion (which requires base64 encoding and multipart handling).
"""
import base64, json, os, subprocess, sys, tempfile, urllib.request

payload = json.loads(sys.stdin.read())


def _load_env():
    env = {}
    try:
        with open("/data/memex.env") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    env[k.strip()] = v.strip()
    except FileNotFoundError:
        pass
    return env


env = _load_env()
API_URL = env.get("MEMEX_SERVER_URL", "http://127.0.0.1:8000").rstrip("/") + "/api/v1"
API_KEY = env.get("MEMEX_API_KEY", "")

MEMEX = [
    "/root/.local/bin/memex",
    "--set", f"server_url={env.get('MEMEX_SERVER_URL', 'http://127.0.0.1:8000')}",
    "--set", f"api_key={API_KEY}",
]


def _api_request(path, data=None, params=None, method=None):
    url = f"{API_URL}/{path}"
    if params:
        url += "?" + "&".join(f"{k}={v}" for k, v in params.items())
    body = json.dumps(data).encode() if data is not None else None
    req = urllib.request.Request(url, data=body, headers={
        "Content-Type": "application/json",
        "X-API-Key": API_KEY,
    })
    if method:
        req.method = method
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        detail = e.read().decode()
        try:
            detail = json.loads(detail).get("detail", detail)
        except (json.JSONDecodeError, AttributeError):
            pass
        return {"error": f"HTTP {e.code}: {detail}"}
    except Exception as e:
        return {"error": str(e)}


def _run(*args):
    r = subprocess.run([*MEMEX, *args], capture_output=True, text=True)
    if r.returncode != 0:
        msg = r.stderr.strip() or r.stdout.strip() or f"exit code {r.returncode}"
        return {"error": msg}
    try:
        return json.loads(r.stdout)
    except json.JSONDecodeError:
        return {"result": r.stdout.strip()}


# ── CLI argument helpers ──


def _opt(p, key, flag):
    v = p.get(key)
    if v is not None and v != "":
        return [flag, str(v)]
    return []


def _list_opt(p, key, flag):
    vals = p.get(key)
    if not vals:
        return []
    if isinstance(vals, str):
        vals = [vals]
    args = []
    for v in vals:
        args += [flag, str(v)]
    return args


def _vault_opts(p):
    """Handle vault_id (str), vault_ids (list), or vault (legacy str)."""
    vault = p.get("vault_ids") or p.get("vault_id") or p.get("vault")
    if not vault:
        return []
    if isinstance(vault, str):
        return ["--vault", vault]
    args = []
    for v in vault:
        if v != "*":
            args += ["--vault", v]
    return args


def _namespace_opts(p):
    """Handle namespaces (list) or namespace (str)."""
    ns = p.get("namespaces") or p.get("namespace")
    if not ns:
        return []
    if isinstance(ns, str):
        ns = [ns]
    args = []
    for n in ns:
        args += ["--namespace", n.rstrip(":")]
    return args


def _exclude_strategies(p, all_strategies):
    if not p.get("strategies"):
        return []
    return [f"--no-{s.replace('_', '-')}" for s in all_strategies - set(p["strategies"])]


# ── Search & Discovery ──


def memex_note_search(p):
    args = ["note", "search", "--json",
            *_vault_opts(p),
            *_opt(p, "limit", "--limit"),
            *_opt(p, "after", "--after"),
            *_opt(p, "before", "--before"),
            *_list_opt(p, "tags", "--tag"),
            *_exclude_strategies(p, {"semantic", "keyword", "graph", "temporal"})]
    if p.get("expand_query"):
        args.append("--expand-query")
    if p.get("has_assets"):
        args.append("--has-assets")
    args += ["--", p["query"]]
    return _run(*args)


def memex_memory_search(p):
    args = ["memory", "search", "--json",
            *_vault_opts(p),
            *_opt(p, "limit", "--limit"),
            *_opt(p, "after", "--after"),
            *_opt(p, "before", "--before"),
            *_opt(p, "token_budget", "--token-budget"),
            *_opt(p, "source_context", "--source-context"),
            *_list_opt(p, "tags", "--tag"),
            *_exclude_strategies(p, {"semantic", "keyword", "graph", "temporal", "mental_model"})]
    if p.get("include_superseded"):
        args.append("--include-stale")
    args += ["--", p["query"]]
    return _run(*args)


def memex_find_note(p):
    return _run("note", "find", "--json",
                *_vault_opts(p),
                *_opt(p, "limit", "--limit"),
                "--", p["query"])


def memex_search_user_notes(p):
    return _run("memory", "search", "--json",
                "--source-context", "user_notes",
                *_vault_opts(p),
                *_opt(p, "limit", "--limit"),
                "--", p["query"])


def memex_survey(p):
    return _run("survey", "--json",
                *_vault_opts(p),
                *_opt(p, "limit_per_query", "--limit"),
                *_opt(p, "token_budget", "--token-budget"),
                "--", p["query"])


def memex_get_vault_summary(p):
    return _run("vault", "summary", "--json", *_vault_opts(p))


# ── Entity ──


def memex_list_entities(p):
    return _run("entity", "list", "--json",
                *_vault_opts(p),
                *_opt(p, "query", "--query"),
                *_opt(p, "entity_type", "--type"),
                *_opt(p, "type", "--type"),
                *_opt(p, "limit", "--limit"))


def memex_get_entities(p):
    ids = p.get("entity_ids") or p.get("identifiers", [])
    return _run("entity", "view", *ids, "--json")


def memex_get_entity_mentions(p):
    eid = p.get("entity_id") or p.get("identifier")
    return _run("entity", "mentions", eid, "--json",
                *_opt(p, "limit", "--limit"))


def memex_get_entity_cooccurrences(p):
    eid = p.get("entity_id") or p.get("identifier")
    return _run("entity", "related", eid, "--json",
                *_opt(p, "limit", "--limit"))


# ── Note Add & Lifecycle ──


def memex_add_note(p):
    title = p["title"]
    author = p["author"]
    description = p["description"]
    tags = p.get("tags", [])
    content = p.get("markdown_content") or p.get("content", "")

    fm_lines = [
        f"title: {json.dumps(title)}",
        f"description: {json.dumps(description)}",
        f"author: {json.dumps(author)}",
        f"tags: {json.dumps(tags)}",
    ]
    if p.get("date"):
        fm_lines.append(f"date: {json.dumps(p['date'])}")
    if p.get("template"):
        fm_lines.append(f"template: {json.dumps(p['template'])}")
    full_content = "---\n" + "\n".join(fm_lines) + "\n---\n\n# " + title + "\n\n" + content

    note_key = p.get("note_key") or p.get("key") or f"openfang:add_note:{title}"
    background = p.get("background", True)

    data = {
        "name": title,
        "description": description,
        "content": base64.b64encode(full_content.encode()).decode(),
        "tags": tags,
        "note_key": note_key,
        "vault_id": p.get("vault_id") or p.get("vault"),
        "user_notes": p.get("user_notes"),
    }
    params = {"background": "true"} if background else None
    return _api_request("ingestions", data, params)


def memex_set_note_status(p):
    args = ["note", "set-status", p["note_id"], p["status"], "--json"]
    if p.get("linked_note_id"):
        args += ["--linked", p["linked_note_id"]]
    return _run(*args)


def memex_update_user_notes(p):
    note_id = p["note_id"]
    user_notes = p.get("user_notes")
    if user_notes is None:
        return _run("note", "update-user-notes", note_id, "--clear", "--json")
    return _run("note", "update-user-notes", note_id, "--json", "--", user_notes)


def memex_rename_note(p):
    return _run("note", "rename", p["note_id"], "--", p["new_title"])


def memex_read_note(p):
    return _run("note", "view", p["note_id"], "--json")


# ── Templates ──


def memex_get_template(p):
    slug = p.get("type") or p.get("slug")
    return _run("note", "template", "get", slug)


def memex_list_templates(p):
    return _run("note", "template", "list", "--json")


def memex_register_template(p):
    content = f'name = {json.dumps(p.get("name", p["slug"]))}\n'
    content += f'description = {json.dumps(p.get("description", ""))}\n\n'
    content += f"template = '''\n{p['template']}\n'''\n"
    path = os.path.join(tempfile.gettempdir(), f"{p['slug']}.toml")
    with open(path, "w") as f:
        f.write(content)
    result = _run("note", "template", "register", path)
    os.unlink(path)
    return result


# ── KV Store ──


def memex_kv_write(p):
    args = ["kv", "write", "--key", p["key"]]
    if p.get("ttl_seconds"):
        args += ["--ttl", str(p["ttl_seconds"])]
    args += ["--", p["value"]]
    return _run(*args)


def memex_kv_get(p):
    return _run("kv", "get", p["key"], "--value-only")


def memex_kv_list(p):
    return _run("kv", "list", "--json",
                *_namespace_opts(p),
                *_opt(p, "pattern", "--pattern"))


def memex_kv_search(p):
    return _run("kv", "search", "--json",
                *_namespace_opts(p),
                *_opt(p, "limit", "--limit"),
                "--", p["query"])


# ── Note Reading ──


def memex_list_notes(p):
    return _run("note", "list", "--json",
                *_vault_opts(p),
                *_opt(p, "limit", "--limit"),
                *_opt(p, "after", "--after"),
                *_opt(p, "before", "--before"),
                *_opt(p, "template", "--template"),
                *_opt(p, "status", "--status"),
                *_list_opt(p, "tags", "--tag"))


def memex_recent_notes(p):
    return _run("note", "recent", "--json",
                *_vault_opts(p),
                *_opt(p, "limit", "--limit"),
                *_opt(p, "after", "--after"),
                *_opt(p, "before", "--before"),
                *_opt(p, "template", "--template"))


def memex_get_notes_metadata(p):
    return _run("note", "metadata", *p["note_ids"], "--json")


def memex_get_page_indices(p):
    args = ["note", "page-index", *p["note_ids"], "--json"]
    if p.get("depth") is not None:
        args += ["--depth", str(p["depth"])]
    if p.get("parent_node_id"):
        args += ["--parent", p["parent_node_id"]]
    return _run(*args)


def memex_get_nodes(p):
    return _run("note", "node", *p["node_ids"], "--json")


# ── Assets ──


def memex_list_assets(p):
    args = ["note", "assets", "list", p["note_id"], "--json"]
    args += _vault_opts(p)
    return _run(*args)


def memex_get_resources(p):
    out_dir = p.get("output_dir", "/tmp/memex-assets")
    os.makedirs(out_dir, exist_ok=True)
    return _run("note", "assets", "get", *p["paths"], "-d", out_dir)


def memex_add_assets(p):
    args = ["note", "assets", "add", p["note_id"]]
    for path in p.get("file_paths") or p.get("asset_paths", []):
        args += ["-a", path]
    return _run(*args)


def memex_delete_assets(p):
    args = ["note", "assets", "delete", p["note_id"]]
    for path in p.get("asset_paths", []):
        args += ["-a", path]
    args += ["--json"]
    args += _vault_opts(p)
    return _run(*args)


# ── Vaults ──


def memex_list_vaults(p):
    return _run("vault", "list", "--json")


def memex_active_vault(p):
    return _run("vault", "active", "--json")


# ── Memory Units ──


def memex_get_memory_units(p):
    return _run("memory", "view", *p["unit_ids"], "--json")


def memex_get_lineage(p):
    return _run("memory", "lineage", p["entity_type"], p["entity_id"],
                "--json",
                *_opt(p, "direction", "--direction"),
                *_opt(p, "depth", "--depth"),
                *_opt(p, "limit", "--limit"))


# ── Extra (not in MCP, used by hands) ──


def memex_note_migrate(p):
    return _run("note", "migrate", "--force", p["note_id"], p["target_vault"])


# ── Dispatch ──

TOOLS = {
    # Search & Discovery
    "memex_note_search": memex_note_search,
    "memex_memory_search": memex_memory_search,
    "memex_find_note": memex_find_note,
    "memex_search_user_notes": memex_search_user_notes,
    "memex_survey": memex_survey,
    "memex_get_vault_summary": memex_get_vault_summary,
    # Entity
    "memex_list_entities": memex_list_entities,
    "memex_get_entities": memex_get_entities,
    "memex_get_entity_mentions": memex_get_entity_mentions,
    "memex_get_entity_cooccurrences": memex_get_entity_cooccurrences,
    # Note lifecycle
    "memex_add_note": memex_add_note,
    "memex_set_note_status": memex_set_note_status,
    "memex_update_user_notes": memex_update_user_notes,
    "memex_rename_note": memex_rename_note,
    "memex_read_note": memex_read_note,
    # Templates
    "memex_get_template": memex_get_template,
    "memex_list_templates": memex_list_templates,
    "memex_register_template": memex_register_template,
    # KV
    "memex_kv_write": memex_kv_write,
    "memex_kv_get": memex_kv_get,
    "memex_kv_list": memex_kv_list,
    "memex_kv_search": memex_kv_search,
    # Note reading
    "memex_list_notes": memex_list_notes,
    "memex_recent_notes": memex_recent_notes,
    "memex_get_notes_metadata": memex_get_notes_metadata,
    "memex_get_page_indices": memex_get_page_indices,
    "memex_get_nodes": memex_get_nodes,
    # Assets
    "memex_list_assets": memex_list_assets,
    "memex_get_resources": memex_get_resources,
    "memex_add_assets": memex_add_assets,
    "memex_delete_assets": memex_delete_assets,
    # Vaults
    "memex_list_vaults": memex_list_vaults,
    "memex_active_vault": memex_active_vault,
    # Memory
    "memex_get_memory_units": memex_get_memory_units,
    "memex_get_lineage": memex_get_lineage,
    # Extra (not in MCP, needed by hands)
    "memex_note_migrate": memex_note_migrate,
}

handler = TOOLS.get(payload["tool"])
if not handler:
    print(json.dumps({"error": f"Unknown tool: {payload['tool']}"}))
else:
    print(json.dumps(handler(payload.get("input", {}))))
