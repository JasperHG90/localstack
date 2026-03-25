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
    args = []
    for k in keys:
        v = p.get(k)
        if v is not None and v != "":
            args += [OPT[k], str(v)]
    return args

def _exclude_strategies(p, all_strategies):
    if not p.get("strategies"):
        return []
    return [f"--no-{s.replace('_', '-')}" for s in all_strategies - set(p["strategies"])]

# --- Search & Discovery ---

def note_search(p):
    return _run("note", "search", "--json",
                *_opts(p, "vault", "limit", "after", "before"),
                *_exclude_strategies(p, {"semantic", "keyword", "graph", "temporal"}),
                "--", p["query"])

def memory_search(p):
    args = ["memory", "search", "--json",
            *_opts(p, "vault", "limit", "after", "before", "token_budget"),
            *_exclude_strategies(p, {"semantic", "keyword", "graph", "temporal", "mental_model"})]
    if p.get("include_superseded"): args.append("--include-stale")
    args += ["--", p["query"]]
    return _run(*args)

def note_find(p):
    return _run("note", "find", "--json", *_opts(p, "vault", "limit"), "--", p["query"])

def entity_search(p):
    return _run("entity", "list", "--json", *_opts(p, "query", "type", "limit"))

def entity_view(p):
    return _run("entity", "view", *p["identifiers"], "--json")

def entity_related(p):
    return _run("entity", "related", p["identifier"], "--json", *_opts(p, "limit"))

def entity_mentions(p):
    return _run("entity", "mentions", p["identifier"], "--json", *_opts(p, "limit"))

# --- Note Add & Lifecycle ---

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
    args = ["note", "add", *_opts(p, "vault", "key", "user_notes")]
    if p.get("background", True): args.append("--background")
    args += ["--", content]
    return _run(*args)

def note_rename(p):
    return _run("note", "rename", p["note_id"], "--", p["new_title"])

def note_template(p):
    return _run("note", "template", p["template_type"])

# --- KV Store ---

def kv_write(p):
    return _run("kv", "write", "--key", p["key"], "--", p["value"])

def kv_get(p):
    return _run("kv", "get", p["key"], "--value-only")

def kv_list(p):
    return _run("kv", "list", "--json", *_opts(p, "namespace", "pattern"))

def kv_search(p):
    return _run("kv", "search", "--json", *_opts(p, "namespace", "limit"), "--", p["query"])

# --- Note Reading (batch) ---

def note_list(p):
    return _run("note", "list", "--json", *_opts(p, "vault", "limit", "after", "before"))

def note_recent(p):
    return _run("note", "recent", "--json", *_opts(p, "vault", "limit", "after", "before"))

def note_view(p):
    return _run("note", "view", p["note_id"], "--json")

def note_metadata(p):
    return _run("note", "metadata", *p["note_ids"], "--json")

def note_page_index(p):
    return _run("note", "page-index", *p["note_ids"], "--json")

def note_node(p):
    return _run("note", "node", *p["node_ids"], "--json")

def note_list_assets(p):
    return _run("note", "list-assets", p["note_id"], "--json")

def get_resource(p):
    out_dir = p.get("output_dir", "/tmp/memex-assets")
    os.makedirs(out_dir, exist_ok=True)
    return _run("note", "get-asset", *p["paths"], "-d", out_dir)

def list_vaults(p):
    return _run("vault", "list", "--json")

# --- Memory Units ---

def memory_view(p):
    return _run("memory", "view", *p["unit_ids"], "--json")

# --- Dispatch ---

TOOLS = {
    "memex_note_search": note_search,
    "memex_memory_search": memory_search,
    "memex_note_find": note_find,
    "memex_entity_search": entity_search,
    "memex_entity_view": entity_view,
    "memex_entity_related": entity_related,
    "memex_entity_mentions": entity_mentions,
    "memex_note_add": note_add,
    "memex_note_rename": note_rename,
    "memex_note_template": note_template,
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
    "memex_memory_view": memory_view,
}

handler = TOOLS.get(payload["tool"])
if not handler:
    print(json.dumps({"error": f"Unknown tool: {payload['tool']}"}))
else:
    print(json.dumps(handler(payload.get("input", {}))))
