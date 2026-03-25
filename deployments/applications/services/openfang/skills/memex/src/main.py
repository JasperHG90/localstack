#!/usr/bin/env python3
import json, os, subprocess, sys

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
MEMEX = [
    "/root/.local/bin/memex",
    "--set", f"server_url={env.get('MEMEX_SERVER_URL', 'http://127.0.0.1:8000')}",
    "--set", f"api_key={env.get('MEMEX_API_KEY', '')}",
]

def _run(*args):
    r = subprocess.run([*MEMEX, *args], capture_output=True, text=True)
    if r.returncode != 0:
        msg = r.stderr.strip() or r.stdout.strip() or f"exit code {r.returncode}"
        return {"error": msg}
    try:
        return json.loads(r.stdout)
    except json.JSONDecodeError:
        return {"result": r.stdout.strip()}

# --- Search & Discovery ---

def note_search(p):
    args = ["note", "search", p["query"], "--json"]
    if p.get("vault"): args += ["--vault", p["vault"]]
    if p.get("limit"): args += ["--limit", str(p["limit"])]
    if p.get("after"): args += ["--after", p["after"]]
    if p.get("before"): args += ["--before", p["before"]]
    if p.get("strategies"):
        all_strategies = {"semantic", "keyword", "graph", "temporal"}
        for s in all_strategies - set(p["strategies"]):
            args.append(f"--no-{s}")
    return _run(*args)

def memory_search(p):
    args = ["memory", "search", p["query"], "--json"]
    if p.get("vault"): args += ["--vault", p["vault"]]
    if p.get("limit"): args += ["--limit", str(p["limit"])]
    if p.get("token_budget"): args += ["--token-budget", str(p["token_budget"])]
    if p.get("after"): args += ["--after", p["after"]]
    if p.get("before"): args += ["--before", p["before"]]
    if p.get("include_superseded"): args.append("--include-stale")
    if p.get("strategies"):
        all_strategies = {"semantic", "keyword", "graph", "temporal", "mental_model"}
        for s in all_strategies - set(p["strategies"]):
            args.append(f"--no-{s.replace('_', '-')}")
    return _run(*args)

def note_find(p):
    args = ["note", "find", p["query"], "--json"]
    if p.get("vault"): args += ["--vault", p["vault"]]
    if p.get("limit"): args += ["--limit", str(p["limit"])]
    return _run(*args)

def entity_search(p):
    args = ["entity", "list", "--json"]
    if p.get("query"): args += ["--query", p["query"]]
    if p.get("type"): args += ["--type", p["type"]]
    if p.get("limit"): args += ["--limit", str(p["limit"])]
    return _run(*args)

def entity_related(p):
    args = ["entity", "related", p["identifier"], "--json"]
    if p.get("limit"): args += ["--limit", str(p["limit"])]
    return _run(*args)

def entity_mentions(p):
    args = ["entity", "mentions", p["identifier"], "--json"]
    if p.get("limit"): args += ["--limit", str(p["limit"])]
    return _run(*args)

# --- Note Add ---

def note_add(p):
    content = p["content"]
    if p.get("title") or p.get("description") or p.get("tags"):
        parts = ["---"]
        if p.get("title"): parts.append(f"title: {p['title']}")
        if p.get("description"): parts.append(f"description: {p['description']}")
        if p.get("tags"): parts.append(f"tags: {json.dumps(p['tags'])}")
        parts.append("---")
        if p.get("title"): parts.append(f"\n# {p['title']}\n")
        parts.append(content)
        content = "\n".join(parts)
    args = ["note", "add", content]
    if p.get("background", True): args.append("--background")
    if p.get("vault"): args += ["--vault", p["vault"]]
    if p.get("key"): args += ["--key", p["key"]]
    if p.get("user_notes"): args += ["--user-notes", p["user_notes"]]
    return _run(*args)

# --- KV Store ---

def kv_write(p):
    return _run("kv", "write", p["value"], "--key", p["key"])

def kv_get(p):
    return _run("kv", "get", p["key"], "--value-only")

def kv_list(p):
    args = ["kv", "list", "--json"]
    if p.get("namespace"): args += ["--namespace", p["namespace"]]
    if p.get("pattern"): args += ["--pattern", p["pattern"]]
    return _run(*args)

def kv_search(p):
    args = ["kv", "search", p["query"], "--json"]
    if p.get("namespace"): args += ["--namespace", p["namespace"]]
    if p.get("limit"): args += ["--limit", str(p["limit"])]
    return _run(*args)

# --- Note Reading ---

def note_list(p):
    args = ["note", "list", "--json"]
    if p.get("vault"): args += ["--vault", p["vault"]]
    if p.get("limit"): args += ["--limit", str(p["limit"])]
    if p.get("after"): args += ["--after", p["after"]]
    if p.get("before"): args += ["--before", p["before"]]
    return _run(*args)

def note_recent(p):
    args = ["note", "recent", "--json"]
    if p.get("vault"): args += ["--vault", p["vault"]]
    if p.get("limit"): args += ["--limit", str(p["limit"])]
    if p.get("after"): args += ["--after", p["after"]]
    if p.get("before"): args += ["--before", p["before"]]
    return _run(*args)

def note_view(p):
    return _run("note", "view", p["note_id"], "--json")

def note_metadata(p):
    return _run("note", "metadata", p["note_id"], "--json")

def note_page_index(p):
    return _run("note", "page-index", p["note_id"], "--json")

def note_node(p):
    return _run("note", "node", p["node_id"], "--json")

def note_list_assets(p):
    return _run("note", "list-assets", p["note_id"], "--json")

def get_resource(p):
    import pathlib
    asset_path = p["path"]
    out_dir = p.get("output_dir", "/tmp/memex-assets")
    filename = pathlib.Path(asset_path).name
    out_path = os.path.join(out_dir, filename)
    os.makedirs(out_dir, exist_ok=True)
    return _run("note", "get-asset", asset_path, "-o", out_path)

def list_vaults(p):
    return _run("vault", "list", "--json")

# --- Dispatch ---

TOOLS = {
    "memex_note_search": note_search,
    "memex_memory_search": memory_search,
    "memex_note_find": note_find,
    "memex_entity_search": entity_search,
    "memex_entity_related": entity_related,
    "memex_entity_mentions": entity_mentions,
    "memex_note_add": note_add,
    "memex_kv_write": kv_write,
    "memex_kv_get": kv_get,
    "memex_kv_list": kv_list,
    "memex_kv_search": kv_search,
    "memex_note_list": note_list,
    "memex_note_recent": note_recent,
    "memex_note_view": note_view,
    "memex_note_metadata": note_metadata,
    "memex_note_page_index": note_page_index,
    "memex_note_node": note_node,
    "memex_note_list_assets": note_list_assets,
    "memex_get_resource": get_resource,
    "memex_list_vaults": list_vaults,
}

handler = TOOLS.get(payload["tool"])
if not handler:
    print(json.dumps({"error": f"Unknown tool: {payload['tool']}"}))
else:
    print(json.dumps(handler(payload.get("input", {}))))
