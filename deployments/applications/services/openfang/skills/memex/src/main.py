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

# Map param keys to CLI flags. str values pass through; int values are stringified.
OPT = {
    "vault": "--vault",
    "limit": "--limit",
    "after": "--after",
    "before": "--before",
    "query": "--query",
    "type": "--type",
    "namespace": "--namespace",
    "pattern": "--pattern",
    "key": "--key",
    "token_budget": "--token-budget",
    "user_notes": "--user-notes",
}

def _opts(p, *keys):
    """Build CLI flags from params. Only includes keys present and truthy."""
    args = []
    for k in keys:
        v = p.get(k)
        if v is not None and v != "":
            args += [OPT[k], str(v)]
    return args

def _exclude_strategies(p, all_strategies):
    """Build --no-X flags for strategies not in the provided list."""
    if not p.get("strategies"):
        return []
    return [f"--no-{s.replace('_', '-')}" for s in all_strategies - set(p["strategies"])]

# --- Search & Discovery ---

def note_search(p):
    return _run("note", "search", p["query"], "--json",
                *_opts(p, "vault", "limit", "after", "before"),
                *_exclude_strategies(p, {"semantic", "keyword", "graph", "temporal"}))

def memory_search(p):
    args = ["memory", "search", p["query"], "--json",
            *_opts(p, "vault", "limit", "after", "before", "token_budget"),
            *_exclude_strategies(p, {"semantic", "keyword", "graph", "temporal", "mental_model"})]
    if p.get("include_superseded"): args.append("--include-stale")
    return _run(*args)

def note_find(p):
    return _run("note", "find", p["query"], "--json", *_opts(p, "vault", "limit"))

def entity_search(p):
    return _run("entity", "list", "--json", *_opts(p, "query", "type", "limit"))

def entity_related(p):
    return _run("entity", "related", p["identifier"], "--json", *_opts(p, "limit"))

def entity_mentions(p):
    return _run("entity", "mentions", p["identifier"], "--json", *_opts(p, "limit"))

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
    args = ["note", "add", content, *_opts(p, "vault", "key", "user_notes")]
    if p.get("background", True): args.append("--background")
    return _run(*args)

# --- KV Store ---

def kv_write(p):
    return _run("kv", "write", p["value"], "--key", p["key"])

def kv_get(p):
    return _run("kv", "get", p["key"], "--value-only")

def kv_list(p):
    return _run("kv", "list", "--json", *_opts(p, "namespace", "pattern"))

def kv_search(p):
    return _run("kv", "search", p["query"], "--json", *_opts(p, "namespace", "limit"))

# --- Note Reading ---

def note_list(p):
    return _run("note", "list", "--json", *_opts(p, "vault", "limit", "after", "before"))

def note_recent(p):
    return _run("note", "recent", "--json", *_opts(p, "vault", "limit", "after", "before"))

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
    out_dir = p.get("output_dir", "/tmp/memex-assets")
    filename = os.path.basename(p["path"])
    out_path = os.path.join(out_dir, filename)
    os.makedirs(out_dir, exist_ok=True)
    return _run("note", "get-asset", p["path"], "-o", out_path)

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
