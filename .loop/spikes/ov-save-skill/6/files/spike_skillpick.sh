#!/usr/bin/env bash
# ov-save-skill risk 3: does "save this <url>" make Hermes load save-to-openviking?
# Real model (ollama/deepseek-v4.1-flash via the lab Bifrost, hermes virtual key
# read from a file outside the repo), stub OpenViking on 127.0.0.1:1934.
# PLACEMENT=soul (default): pointer line in SOUL.md. PLACEMENT=block: pointer in
# the openviking_tools wrapper's static system_prompt_block instead.
# Exit 0 only if 5/5 no-place runs view the skill then ask without writing, and
# 3/3 with-place runs view the skill then save to blogs/anthropic without asking.
set -u
PLACEMENT=${PLACEMENT:-soul}
KEYFILE=/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/spike-skillpick/bifrost.key
BIFROST_URL=https://bifrost.lab.orangecluster.nl/v1
W=$(mktemp -d); mkdir -p $W/spike $W/ctx/openviking_tools
echo "== placement: $PLACEMENT"

POINTER='To save anything to OpenViking (a link, a file, a note, a voice-message transcript), load the `save-to-openviking` skill first and follow it. If the operator did not say where, ask before saving.'

cat > $W/ctx/openviking_tools/__init__.py <<'SPIKEEOF'
"""ov-no-auto-capture wrapper as settled by spike:ov-no-auto-capture/2."""

import os

from plugins.memory.openviking import OpenVikingMemoryProvider

_PROMPT = (
    "# OpenViking Knowledge Base\n"
    "Tools: viking_search, viking_read, viking_browse, viking_remember, "
    "viking_forget, viking_add_resource. Use them only when the user or a "
    "skill asks for OpenViking."
)
if os.environ.get("SPIKE_BLOCK_POINTER"):
    _PROMPT += "\n" + os.environ["SPIKE_BLOCK_POINTER"]


class OpenVikingToolsProvider(OpenVikingMemoryProvider):
    def initialize(self, session_id: str, **kwargs) -> None:
        super().initialize(session_id, **{**kwargs, "agent_context": "flush"})

    def _recover_pending_sessions(self) -> None:
        return

    def prefetch(self, query: str, *, session_id: str = "") -> str:
        return ""

    def system_prompt_block(self) -> str:
        return _PROMPT


def register(ctx) -> None:
    ctx.register_memory_provider(OpenVikingToolsProvider())
SPIKEEOF
cat > $W/ctx/openviking_tools/plugin.yaml <<'SPIKEEOF'
name: openviking_tools
version: 0.1.0
description: "OpenViking tools only: no automatic recall or capture."
pip_dependencies:
  - httpx
requires_env: []
hooks: []
SPIKEEOF

cat > $W/skill.md <<'SPIKEEOF'
---
name: save-to-openviking
description: Save a shared link, file, note or voice-message transcript to OpenViking under viking://user/jasper/resources/, picking the folder from the resources map and asking the operator when they named no place.
version: 0.1.0
metadata:
  hermes:
    tags: [openviking, save, bookmark, resources, links, notes, voice]
    category: productivity
---
## When to Use

Whenever the operator asks to save, keep, store, file or bookmark something
(a URL, a file, a typed note, the transcript of a voice message) in
OpenViking or "my knowledge base", with or without naming a place.

## Steps

1. Read the map: `viking_read(uri="viking://user/jasper/resources/.map.md", level="full")`.
   If it does not exist, write the seed map below first (see "Writing the map").
2. Work out the kind and the target.
   - A URL: `viking_add_resource(url=<url>, parent=<folder URI>, reason=<one line>)`.
   - A voice message arrives as the gateway's quoted transcript at the top of
     the message. Write it to a local file `YYYY-MM-DD-<short-title>.md` with
     the date and source in a header, then `viking_add_resource` on that path
     with `parent=`. A file or a typed note goes the same way.
3. If the operator named a place (for example "to blogs/anthropic"), save
   there without asking: `parent="viking://user/jasper/resources/<place>/"`.
   If not, propose the best-fitting root and a subfolder under it from the
   map, and ask the operator to confirm or name another. **Do not save
   before the answer.**
4. `projects/` and `leo/` are owned by syncs. Save there only after the
   operator confirms that root by name. A shared blog post goes to
   `blogs/<source>/`, where `<source>` is the site or author.
5. If no map entry fits, do one
   `viking_browse(action="list", path="viking://user/jasper/resources/")`
   before asking. Add any root it finds that the map lacks, with a
   description the operator gives.
6. A new root the operator chooses is appended to the map (root, one-line
   description, owner "hand saves") before the save.
7. If the target name already exists, ask whether to replace it or save
   under a dated name.

## Writing the map

The map is the one write the viking_* tools cannot make. Use the terminal:

    curl -s -X POST "$OPENVIKING_ENDPOINT/api/v1/content/write" \
      -H 'Content-Type: application/json' \
      -d '{"uri": "viking://user/jasper/resources/.map.md", "mode": "append", "content": "..."}'

`mode` is `create` for the seed and `append` for a new root.

## Seed map

    # Resources map
    - projects/<repo>/: one per repository, docs/ and .okf/, written by CI ovsync. Do not hand-edit.
    - leo/: Leo's meeting transcripts, digests and notes, written by leo-consumer. Do not hand-edit.
    - blogs/<source>/: the daily blog-scraper cron plus posts the operator shares.
    - clips/<slug>/: written by ov-clip.
SPIKEEOF

cat > $W/render.py <<'SPIKEEOF'
"""Render /opt/data from hermes.hcl, SOUL.md and the skills folder as the job does.

usage: render.py REPO OUT_DIR SKILL_MD PLACEMENT POINTER
"""

import re
import sys
from pathlib import Path

repo, out, skill_md, placement, pointer = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]), sys.argv[4], sys.argv[5]
svc = repo / "deployments/applications/services"
hcl = (svc / "hermes.hcl").read_text()
templates = {dest: data for data, dest in re.findall(
    r'data = <<EOF\n(.*?)\nEOF\n\s*\n\s*destination = "([^"]+)"', hcl, re.S)}


def fill(text):
    return text.replace("${hermes_dashboard_public_url}", "http://127.0.0.1:9119").replace("$${", "${")


cfg = fill(templates["local/config.yaml"])
cfg = cfg.replace('  provider: "openviking"\n', '  provider: "openviking_tools"\n')
assert 'provider: "openviking_tools"' in cfg
# Spike only: the post-turn self-improvement fork patched the skill between runs
# in spike:ov-save-skill/4; off so all runs see the same draft.
cfg = cfg.replace("auxiliary:\n", "auxiliary:\n  background_review:\n    enabled: false\n", 1)
assert "background_review" in cfg

soul = (svc / "hermes/SOUL.md").read_text()
for start, end in [("# Session Bootstrap\n", "# OpenViking Integration\n"),
                   ("# Auto-Capture Protocol\n", "# Citations\n")]:
    i, j = soul.index(start), soul.index(end)
    soul = soul[:i] + soul[j:]
curl_line = "Six tools, and they are the whole surface. Do not shell out to curl."
assert curl_line in soul
if placement == "soul":
    soul = soul.replace(curl_line, curl_line[:-1] + ", except for the map write in the "
                        "`save-to-openviking` skill.\n\n" + pointer)

files = {
    "config.yaml": cfg,
    "SOUL.md": soul,
    "plugins/model-providers/bifrost/__init__.py": fill(templates["local/model-providers/bifrost/__init__.py"]),
    "plugins/model-providers/bifrost/plugin.yaml": fill(templates["local/model-providers/bifrost/plugin.yaml"]),
    "skills-library/productivity/save-to-openviking/SKILL.md": skill_md.read_text(),
    # The OPENVIKING_* lines setup.sh writes to /opt/data/.env (services.tf values).
    ".env": "OPENVIKING_API_KEY=unused\nOPENVIKING_ACCOUNT=lab\nOPENVIKING_USER=jasper\n"
            "OPENVIKING_ENDPOINT=http://127.0.0.1:1934\nHERMES_YOLO_MODE=true\nHERMES_HOME=/opt/data\n",
}
for f in (svc / "hermes/skills").rglob("SKILL.md"):
    files["skills-library/" + str(f.relative_to(svc / "hermes/skills"))] = f.read_text()
for rel, body in files.items():
    p = out / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(body)
for d in ["sessions", "memories", "cron", "hooks", "logs", "skills"]:
    (out / d).mkdir(exist_ok=True)
print("render: SOUL has pointer:", "save-to-openviking" in soul,
      "| skills-library:", sorted(k.split("/", 1)[1].rsplit("/", 1)[0] for k in files if k.startswith("skills-library/")))
SPIKEEOF

cat > $W/spike/stub.py <<'SPIKEEOF'
"""Stub OpenViking on 127.0.0.1:1934, logging requests as JSON lines. The map exists."""

import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

LOG = sys.argv[1]
lock = threading.Lock()
MAP = """# Resources map
- projects/<repo>/: one per repository, docs/ and .okf/, written by CI ovsync. Do not hand-edit.
- leo/: Leo's meeting transcripts, digests and notes, written by leo-consumer. Do not hand-edit.
- blogs/<source>/: the daily blog-scraper cron plus posts the operator shares.
- clips/<slug>/: written by ov-clip.
"""
ROOTS = ["projects", "leo", "blogs", "clips"]


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _json(self, obj):
        data = json.dumps(obj).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def handle_any(self):
        n = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(n) if n else b""
        with lock, open(LOG, "a") as f:
            f.write(json.dumps({"method": self.command, "path": self.path,
                                "body": body[:1500].decode("utf-8", "replace")}) + "\n")
        p = self.path.split("?")[0]
        if p == "/health":
            return self._json({"status": "ok", "healthy": True, "version": "0.4.17"})
        if p == "/api/v1/system/status":
            return self._json({"status": "ok", "result": {"initialized": True, "user": "jasper"}})
        if p.startswith("/api/v1/content/"):
            if ".map.md" in self.path:
                return self._json({"status": "ok", "result": MAP})
            return self._json({"status": "ok", "result": ""})
        if p == "/api/v1/fs/stat":
            return self._json({"status": "ok", "result": {"isDir": ".map.md" not in self.path}})
        if p in ("/api/v1/fs/ls", "/api/v1/fs/tree"):
            return self._json({"status": "ok", "result": [
                {"name": r, "rel_path": r, "isDir": True,
                 "uri": f"viking://user/jasper/resources/{r}/"} for r in ROOTS]})
        if p == "/api/v1/resources":
            return self._json({"status": "ok", "result": {"root_uri": "viking://user/jasper/resources/x"}})
        if p.startswith("/api/v1/search/"):
            return self._json({"status": "ok", "result": {"memories": [], "resources": [], "skills": [], "total": 0}})
        return self._json({"status": "ok", "result": {}})

    do_GET = do_POST = do_PUT = do_DELETE = handle_any


ThreadingHTTPServer(("127.0.0.1", 1934), H).serve_forever()
SPIKEEOF

cat > $W/spike/driver.py <<'SPIKEEOF'
"""Run 5 no-place and 3 with-place 'save this' turns, each a fresh session."""

import json
import os
import sys

sys.path.insert(0, "/opt/hermes")
from hermes_cli.config import load_config  # noqa: E402
from run_agent import AIAgent  # noqa: E402

LOG = "/tmp/requests.jsonl"
SKILL = "save-to-openviking"
cfg = load_config()
toolsets = cfg["platform_toolsets"]["telegram"]


def stub_lines():
    try:
        with open(LOG) as f:
            return [json.loads(x) for x in f]
    except FileNotFoundError:
        return []


def calls_of(messages):
    out = []
    for m in messages:
        for tc in (m.get("tool_calls") or []) if m.get("role") == "assistant" else []:
            fn = tc.get("function", {}) if isinstance(tc, dict) else {}
            try:
                args = json.loads(fn.get("arguments") or "{}")
            except Exception:
                args = {"raw": fn.get("arguments")}
            out.append((fn.get("name"), args))
    return out


def first(calls, pred):
    return next((i for i, c in enumerate(calls) if pred(c)), None)


def run(i, msg, place):
    seen = len(stub_lines())
    agent = AIAgent(base_url=os.environ["SPIKE_BIFROST_URL"], api_key=os.environ["BIFROST_API_KEY"],
                    provider="custom", model="ollama/deepseek-v4.1-flash", quiet_mode=True,
                    platform="telegram", user_id="4242", enabled_toolsets=toolsets,
                    session_id=f"skillpick-{i}", max_iterations=12)
    if i == 0:
        try:
            sp = agent._build_system_prompt()
        except Exception as e:
            sp = ""
            print("system prompt not built:", e)
        print("system prompt mentions skill:", SKILL in (sp or ""), "| pointer in prompt:",
              "load the `save-to-openviking` skill first" in (sp or ""))
    r = agent.run_conversation(msg)
    calls = calls_of(r.get("messages", []))
    reqs = stub_lines()[seen:]
    writes = [e for e in reqs if e["method"] == "POST" and e["path"].split("?")[0] in
              ("/api/v1/resources", "/api/v1/content/write", "/api/v1/resources/temp_upload")]
    view = first(calls, lambda c: c[0] == "skill_view" and SKILL in json.dumps(c[1]))
    add = first(calls, lambda c: c[0] == "viking_add_resource")
    reply = str(r.get("final_response") or "")
    if place:
        target_ok = add is not None and "blogs/anthropic" in json.dumps(calls[add][1])
        ok = view is not None and target_ok and view < add and len(writes) >= 1
    else:
        ok = view is not None and add is None and not writes and "?" in reply
    print(f"\n-- run {i} [{'place' if place else 'no place'}] {'PASS' if ok else 'FAIL'}: {msg}")
    for n, a in calls:
        print(f"   {n} {json.dumps(a)[:220]}")
    print("   stub writes:", [(e['path'], e['body'][:200]) for e in writes])
    print("   reply:", reply.replace("\n", " ")[:400])
    try:
        agent.shutdown_memory_provider(list(r.get("messages", [])))
    except Exception:
        pass
    return ok


URL = "https://www.anthropic.com/engineering/building-effective-agents"
runs = [(f"save this {URL}", False)] * 5 + [(f"save this {URL} to blogs/anthropic", True)] * 3
res = [run(i, m, p) for i, (m, p) in enumerate(runs)]
np_ok, p_ok = sum(res[:5]), sum(res[5:])
print(f"\n== no-place {np_ok}/5, with-place {p_ok}/3")
sys.exit(0 if (np_ok, p_ok) == (5, 3) else 1)
SPIKEEOF

ID=skillpick$$-$RANDOM
IMG=$ID-img
cleanup() { docker rm -f $ID-c >/dev/null 2>&1; docker rmi -f $IMG >/dev/null 2>&1; rm -rf $W; }
trap cleanup EXIT

printf '%s\n' "FROM ghcr.io/jasperhg90/hermes:0.22.2-1" \
  "COPY openviking_tools /opt/hermes/plugins/memory/openviking_tools" > $W/ctx/Dockerfile
docker build -q -t $IMG $W/ctx >/dev/null || exit 2
python3 -I $W/render.py "$PWD" $W/data $W/skill.md "$PLACEMENT" "$POINTER" || exit 2
mkdir -p $W/data/skills-library-jasperhg90
curl -fsSL https://github.com/JasperHG90/skills/archive/main.tar.gz \
  | tar xz -C $W/data/skills-library-jasperhg90 --strip-components=1 \
  && echo "external skills: $(find $W/data/skills-library-jasperhg90/skills -name SKILL.md | wc -l) SKILL.md" \
  || echo "WARN: external skills not fetched"

BLOCK=""; [ "$PLACEMENT" = block ] && BLOCK="$POINTER"
docker create --name $ID-c --entrypoint sh \
  -e HERMES_HOME=/opt/data -e HERMES_YOLO_MODE=true \
  -e OPENVIKING_ENDPOINT=http://127.0.0.1:1934 -e OPENVIKING_API_KEY=unused \
  -e OPENVIKING_ACCOUNT=lab -e OPENVIKING_USER=jasper \
  -e BIFROST_API_KEY="$(cat $KEYFILE)" -e SPIKE_BIFROST_URL=$BIFROST_URL \
  -e SPIKE_BLOCK_POINTER="$BLOCK" \
  $IMG -c 'chown -R hermes:hermes /opt/data && cd /opt/hermes \
    && (python3 -u /spike/stub.py /tmp/requests.jsonl &) \
    && python3 tools/skills_sync.py >/dev/null 2>&1; sleep 1; python3 -u /spike/driver.py' >/dev/null
docker cp $W/data/. $ID-c:/opt/data/
docker cp $W/spike $ID-c:/spike
docker start -a $ID-c 2>/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/spike-skillpick/container-stderr-$PLACEMENT.txt
RC=$?
echo "== result: driver exit $RC"
exit $RC
