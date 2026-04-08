#!/usr/bin/env python3
import json
import subprocess
import sys
import tempfile

payload = json.loads(sys.stdin.read())

GH = ["gh"]


def _gh(*args, input_data=None):
    r = subprocess.run(
        [*GH, *args],
        capture_output=True,
        text=True,
        input=input_data,
    )
    if r.returncode != 0:
        msg = r.stderr.strip() or r.stdout.strip() or f"exit code {r.returncode}"
        return {"error": msg}
    out = r.stdout.strip()
    if not out:
        return {"result": "ok"}
    try:
        return json.loads(out)
    except json.JSONDecodeError:
        return {"result": out}


# --- Repository ---

def repo_view(p):
    return _gh(
        "repo", "view", p["repo"],
        "--json", "name,description,primaryLanguage,repositoryTopics,defaultBranchRef,visibility,url",
    )


def repo_readme(p):
    return _gh(
        "api", f"repos/{p['repo']}/readme",
        "--header", "Accept: application/vnd.github.v3.raw",
    )


def file_read(p):
    args = ["api", f"repos/{p['repo']}/contents/{p['path']}",
            "--header", "Accept: application/vnd.github.v3.raw"]
    if p.get("ref"):
        args += ["-f", f"ref={p['ref']}"]
    return _gh(*args)


# --- Issues ---

def issue_create(p):
    args = ["issue", "create", "--repo", p["repo"],
            "--title", p["title"], "--body", p["body"]]
    for label in p.get("labels", []):
        args += ["--label", label]
    return _gh(*args)


def issue_list(p):
    limit = str(p.get("limit", 20))
    state = p.get("state", "open")
    args = ["issue", "list", "--repo", p["repo"],
            "--state", state, "--limit", limit, "--json",
            "number,title,state,labels,createdAt,url"]
    if p.get("label"):
        args += ["--label", p["label"]]
    return _gh(*args)


# --- Pull Requests ---

def pr_create(p):
    args = ["pr", "create", "--repo", p["repo"],
            "--title", p["title"], "--body", p["body"],
            "--head", p["head"]]
    if p.get("base"):
        args += ["--base", p["base"]]
    for label in p.get("labels", []):
        args += ["--label", label]
    return _gh(*args)


# --- Labels ---

def label_ensure(p):
    color = p.get("color", "7057ff")
    desc = p.get("description", "")
    # Try to create; if it already exists, gh returns an error — that's fine.
    result = _gh("label", "create", p["name"],
                 "--repo", p["repo"],
                 "--color", color,
                 "--description", desc)
    if isinstance(result, dict) and result.get("error", ""):
        err = result["error"].lower()
        if "already exists" in err or "already_exists" in err:
            return {"result": "label already exists"}
    return result


# --- Dispatch ---

TOOLS = {
    "github_repo_view": repo_view,
    "github_repo_readme": repo_readme,
    "github_file_read": file_read,
    "github_issue_create": issue_create,
    "github_issue_list": issue_list,
    "github_pr_create": pr_create,
    "github_label_ensure": label_ensure,
}

handler = TOOLS.get(payload["tool"])
if not handler:
    print(json.dumps({"error": f"Unknown tool: {payload['tool']}"}))
else:
    print(json.dumps(handler(payload.get("input", {}))))
