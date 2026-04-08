#!/usr/bin/env python3
import base64, json, os, subprocess, sys, urllib.request

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
API_URL = env.get('MEMEX_SERVER_URL', 'http://127.0.0.1:8000').rstrip('/') + '/api/v1'
API_KEY = env.get('MEMEX_API_KEY', '')

MEMEX = [
    "/root/.local/bin/memex",
    "--set", f"server_url={env.get('MEMEX_SERVER_URL', 'http://127.0.0.1:8000')}",
    "--set", f"api_key={API_KEY}",
]

def _api_post(path, data, params=None):
    url = f"{API_URL}/{path}"
    if params:
        url += "?" + "&".join(f"{k}={v}" for k, v in params.items())
    body = json.dumps(data).encode()
    req = urllib.request.Request(url, data=body, headers={
        "Content-Type": "application/json",
        "X-API-Key": API_KEY,
    })
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
    "direction": "--direction",
    "depth": "--depth",
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
    title = p["title"]
    author = p["author"]
    description = p["description"]
    tags = p.get("tags", [])
    content = p["content"]

    fm_lines = [
        f"title: {json.dumps(title)}",
        f"description: {json.dumps(description)}",
        f"author: {json.dumps(author)}",
        f"tags: {json.dumps(tags)}",
    ]
    full_content = "---\n" + "\n".join(fm_lines) + "\n---\n\n# " + title + "\n\n" + content

    note_key = p.get("key") or f"openfang:add_note:{title}"
    background = p.get("background", True)

    data = {
        "name": title,
        "description": description,
        "content": base64.b64encode(full_content.encode()).decode(),
        "tags": tags,
        "note_key": note_key,
        "vault_id": p.get("vault"),
        "user_notes": p.get("user_notes"),
    }
    params = {"background": "true"} if background else None
    return _api_post("ingestions", data, params)

def note_migrate(p):
    return _run("note", "migrate", p["note_id"], "--vault", p["target_vault"])

def note_rename(p):
    return _run("note", "rename", p["note_id"], "--", p["new_title"])

def note_template_get(p):
    return _run("note", "template", "get", p["slug"])

def note_template_list(p):
    return _run("note", "template", "list", "--json")

def note_template_register(p):
    import tempfile
    content = f'name = {json.dumps(p["name"])}\n'
    content += f'description = {json.dumps(p["description"])}\n\n'
    content += f"template = '''\n{p['template']}\n'''\n"
    path = os.path.join(tempfile.gettempdir(), f"{p['slug']}.toml")
    with open(path, "w") as f:
        f.write(content)
    result = _run("note", "template", "register", path)
    os.unlink(path)
    return result

# --- KV Store ---

def kv_write(p):
    return _run("kv", "write", "--key", p["key"], "--", p["value"])

def kv_get(p):
    return _run("kv", "get", p["key"], "--value-only")

def _sanitize_namespace(p):
    ns = p.get("namespace")
    if ns:
        p["namespace"] = ns.rstrip(":")

def kv_list(p):
    _sanitize_namespace(p)
    return _run("kv", "list", "--json", *_opts(p, "namespace", "pattern"))

def kv_search(p):
    _sanitize_namespace(p)
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
    return _run("note", "assets", "list", p["note_id"], "--json")

def get_resource(p):
    out_dir = p.get("output_dir", "/tmp/memex-assets")
    os.makedirs(out_dir, exist_ok=True)
    return _run("note", "assets", "get", *p["paths"], "-d", out_dir)

def note_add_asset(p):
    args = ["note", "assets", "add", p["note_id"]]
    for path in p["asset_paths"]:
        args += ["-a", path]
    return _run(*args)

def list_vaults(p):
    return _run("vault", "list", "--json")

# --- Session ---

def session_briefing(p):
    limit = p.get("note_limit", 10)
    vaults = _run("vault", "list", "--json")
    kv_facts = _run("kv", "list", "--json")
    recent = _run("note", "recent", "--json", "--limit", str(limit))
    return {"vaults": vaults, "kv_facts": kv_facts, "recent_notes": recent}

# --- Memory Units ---

def memory_view(p):
    return _run("memory", "view", *p["unit_ids"], "--json")

def get_lineage(p):
    return _run("memory", "lineage", p["entity_type"], p["entity_id"],
                "--json", *_opts(p, "direction", "depth", "limit"))

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
    "memex_note_migrate": note_migrate,
    "memex_note_rename": note_rename,
    "memex_note_template_get": note_template_get,
    "memex_note_template_list": note_template_list,
    "memex_note_template_register": note_template_register,
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
    "memex_note_add_asset": note_add_asset,
    "memex_list_vaults": list_vaults,
    "memex_session_briefing": session_briefing,
    "memex_memory_view": memory_view,
    "memex_get_lineage": get_lineage,
}

handler = TOOLS.get(payload["tool"])
if not handler:
    print(json.dumps({"error": f"Unknown tool: {payload['tool']}"}))
else:
    print(json.dumps(handler(payload.get("input", {}))))
