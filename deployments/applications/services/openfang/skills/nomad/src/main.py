#!/usr/bin/env python3
"""OpenFang skill: Nomad cluster API access.

Reads NOMAD_TOKEN from /data/nomad.env, written by register.sh —
same pattern as the memex skill with /data/memex.env.
"""
import json, os, sys
from urllib.request import Request, urlopen
from urllib.parse import urlencode
from urllib.error import HTTPError, URLError

payload = json.loads(sys.stdin.read())

MAX_LOG_BYTES = 200_000  # hard cap on log output to avoid blowing context


def _load_env():
    env = {}
    try:
        with open("/data/nomad.env") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    env[k.strip()] = v.strip()
    except FileNotFoundError:
        pass
    return env


_env = _load_env()
NOMAD_ADDR = _env.get("NOMAD_ADDR", "http://192.168.2.30:4646")
NOMAD_TOKEN = _env.get("NOMAD_TOKEN", "")
CONSUL_ADDR = _env.get("CONSUL_ADDR", "http://192.168.2.30:8500")


def _request(base_url, path, params=None, token=None, timeout=15, max_bytes=None):
    url = f"{base_url}{path}"
    if params:
        url += "?" + urlencode({k: v for k, v in params.items() if v is not None})
    req = Request(url)
    if token:
        req.add_header("X-Nomad-Token", token)
    try:
        with urlopen(req, timeout=timeout) as resp:
            limit = max_bytes or 2_000_000
            data = resp.read(limit)
            ct = resp.headers.get("Content-Type", "")
            if "application/json" in ct:
                return json.loads(data)
            return {"result": data.decode("utf-8", errors="replace")}
    except HTTPError as e:
        body = e.read(4096).decode("utf-8", errors="replace")
        return {"error": f"HTTP {e.code}: {body}"}
    except URLError as e:
        return {"error": f"Connection failed: {e.reason}"}
    except TimeoutError:
        return {"error": "Request timed out"}


def _nomad(path, params=None, **kwargs):
    return _request(NOMAD_ADDR, path, params=params, token=NOMAD_TOKEN, **kwargs)


# --- Allocation Tools ---

def alloc_logs(p):
    alloc_id = p["alloc_id"]
    task = p["task"]
    log_type = p.get("log_type", "stdout")
    lines = p.get("lines", 200)
    # Fetch a generous byte chunk to cover the requested line count.
    # Assume ~200 bytes/line as a rough estimate.
    fetch_bytes = min(lines * 200, MAX_LOG_BYTES)
    params = {
        "task": task,
        "type": log_type,
        "plain": "true",
        "offset": str(fetch_bytes),
        "origin": "end",
    }
    resp = _nomad(
        f"/v1/client/fs/logs/{alloc_id}",
        params=params,
        timeout=20,
        max_bytes=fetch_bytes,
    )
    # Trim to the requested number of lines.
    if isinstance(resp, dict) and "result" in resp:
        all_lines = resp["result"].splitlines()
        if len(all_lines) > lines:
            resp["result"] = "\n".join(all_lines[-lines:])
        resp["lines_returned"] = min(len(all_lines), lines)
    return resp


def alloc_status(p):
    return _nomad(f"/v1/allocation/{p['alloc_id']}")


def alloc_stats(p):
    return _nomad(f"/v1/client/allocation/{p['alloc_id']}/stats")


# --- Job Tools ---

def job_list(p):
    params = {}
    if p.get("namespace"):
        params["namespace"] = p["namespace"]
    return _nomad("/v1/jobs", params=params or None)


def job_status(p):
    return _nomad(f"/v1/job/{p['job_id']}")


def job_summary(p):
    return _nomad(f"/v1/job/{p['job_id']}/summary")


def job_allocs(p):
    return _nomad(f"/v1/job/{p['job_id']}/allocations")


# --- Node Tools ---

def node_list(p):
    return _nomad("/v1/nodes")


def node_status(p):
    return _nomad(f"/v1/node/{p['node_id']}")


def node_allocs(p):
    return _nomad(f"/v1/node/{p['node_id']}/allocations")


# --- Evaluation Tools ---

def eval_list(p):
    limit = p.get("limit", 50)
    return _nomad("/v1/evaluations", params={"per_page": str(limit)})


# --- Consul Service Health ---

def consul_health(p):
    state = p.get("state", "critical")
    addr = p.get("consul_addr") or CONSUL_ADDR
    return _request(addr, f"/v1/health/state/{state}", timeout=10)


# --- Dispatch ---

TOOLS = {
    "nomad_alloc_logs": alloc_logs,
    "nomad_alloc_status": alloc_status,
    "nomad_alloc_stats": alloc_stats,
    "nomad_job_list": job_list,
    "nomad_job_status": job_status,
    "nomad_job_summary": job_summary,
    "nomad_job_allocs": job_allocs,
    "nomad_node_list": node_list,
    "nomad_node_status": node_status,
    "nomad_node_allocs": node_allocs,
    "nomad_eval_list": eval_list,
    "nomad_consul_health": consul_health,
}

handler = TOOLS.get(payload["tool"])
if not handler:
    print(json.dumps({"error": f"Unknown tool: {payload['tool']}"}))
else:
    print(json.dumps(handler(payload.get("input", {}))))
