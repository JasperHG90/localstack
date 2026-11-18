---
type: plan
title: 'Plan: ov-save-skill'
description: A Hermes skill, save-to-openviking, that saves a shared link, file, note or voice-message transcript under viking://user/jasper/resources/, picking the folder from a map file the skill owns and asking when the user named no place.
tags:
- plan
generated:
  by: process:loopctl/2.2.2.dev1+gd84319696
  at: '2026-10-20T14:37:56+00:00'
slug: ov-save-skill
epic: ov-reset
depends_on:
- ov-no-auto-capture
priority: 2
---

# ov-save-skill

<!-- This template was registered in planning. To capture an idea as a stub
instead (intent for later, promoted by the operator), write the plan with
`status: draft` in its front matter before running loopctl ticket register.
A hand-written plan's front matter needs type: plan, title, description and
slug; loopctl ticket register fills in generated. Optional: epic, depends_on,
priority, status, strictness and blocking. -->

Relayed from: none
<!-- When this ticket carries a finding raised while building another ticket,
replace "none" with that ticket's slug and the finding, in one line (ADR 0001). -->

## Intent

The operator wants to tell Hermes "save this" (a shared blog post, a file, a
note, the transcript of a voice message) and have it land in the right
folder under `viking://user/jasper/resources/` (account `lab`, user `jasper`;
the operator's choice over the shared `viking://resources/`). When the
operator names no place, Hermes asks. Today nothing tells Hermes where
things go. After `ov-no-auto-capture`, Hermes has the six `viking_*` tools
and no automatic recall, so the knowledge has to sit in a skill.

**The map.** A file the skill owns,
viking://user/jasper/resources/.map.md, lists the roots under the
resources folder and the rule for each, not every leaf:

- `projects/<repo>/`: one per repository, `docs/` and `.okf/`, written by
  the CI ovsync job (ticket ci-openviking-sync). Do not hand-edit.
- `leo/`: Leo's meeting transcripts, digests and notes, written by
  leo-consumer. Do not hand-edit.
- `blogs/<source>/`: the daily `blog-scraper` cron plus posts the operator
  shares (`ov-carry-over` merges `blog-scraper/` into it).
- `clips/<slug>/`: written by ov-clip.

Automated writers only add children under roots the map already
describes, so they never make it stale. A new root only appears when the
operator picks a new place, and that goes through the skill, which writes
the root and its one-line description into the map at once. The map
replaces walking the live tree, which is slow: `fs/tree` on
`viking://user` took about 19 s. One `fs/ls` takes 0.04 to 0.07 s, but
walking two levels and reading each `.abstract.md` is a dozen or more calls
through the model's tool loop. Reading the map is one `viking_read`.

**The skill.** A new file
deployments/applications/services/hermes/skills/productivity/save-to-openviking/SKILL.md
(in a new folder, so written without backticks: `loopctl plan lint` refuses a
lone new file in a new folder),
shipped by the existing `fileset` over the skills folder in
`deployments/applications/services.tf` into `/opt/data/skills-library`
(`deployments/applications/services/hermes.hcl`). No Terraform edit and no
image rebuild. Its steps:

1. Read the map with `viking_read(uri=".../.map.md", level="full")`. If it
   does not exist, write the seed map (the four roots above, held verbatim
   in the skill) first. This is how the map is seeded: the first save
   creates it, and the how-to's last step triggers that save on purpose.
2. Work out the kind and the target. A URL goes through
   `viking_add_resource(url=..., parent=<folder>, reason=...)`. A voice
   message arrives as the gateway's quoted transcript at the top of the
   user's message (hermes-agent gateway/run_inbound.py,
   `_enrich_message_with_transcription`). The skill writes it to a local
   Markdown file named `YYYY-MM-DD-<short-title>.md` with the date and
   source in a header, then calls `viking_add_resource` on that path with
   `parent=`. A file or a typed note goes the same way. The plugin uploads
   a local path through `temp_upload` (plugin 2.1.1 `_tool_add_resource`).
3. If the operator named a place, save there without asking. If not,
   propose the best-fitting root, and a subfolder under it, from the map,
   and ask the operator to confirm or name another. Do not save before the
   answer.
4. A root the map marks as owned by a sync (`projects/`, `leo/`) gets a
   hand save only after the operator confirms that root by name. A shared
   blog post goes to `blogs/<source>/`, the same layout the scraper uses
   (`deployments/applications/services/hermes/skills/productivity/blog-scraper/SKILL.md`,
   which this ticket does not change).
5. If no map entry fits, do one `viking_browse(action="list",
   path="viking://user/jasper/resources/")` before asking. Add any root it
   finds that the map lacks, with a description the operator gives.
6. A new root the operator chooses is appended to the map (root, one-line
   description, owner "hand saves") before the save.
7. If the target name already exists, ask whether to replace it or save
   under a dated name.

**The write tool.** The map is the one exact-key write the six tools
cannot make: `viking_add_resource` parses its input into a resource
directory, and OpenViking's `POST /api/v1/content/write` has no tool. This
ticket adds a seventh tool, `viking_write(uri, content, mode)`, to the
`openviking_tools` wrapper that `ov-no-auto-capture` creates
(deployments/applications/services/hermes/openviking_tools/__init__.py,
not yet in the tree, so cited without backticks). `mode` is `create`,
`replace` or `append`, passed through to `content/write`. The wrapper adds
its schema to `get_tool_schemas()` and routes it in `handle_tool_call`.
The upstream six stay as they are. It sends through the plugin's own
client, so the call takes the same path and token as the other tools (the
loopback `ov-auth-proxy`). The skill uses it with `create` for the seed
and `append` for a new root.

The wrapper also adds `create_parent: true` to every `viking_add_resource`
call that passes `parent`. OpenViking 0.4.17.1 refuses a save whose parent
folder does not exist ("Parent URI does not exist", returned as a bare 404)
unless the request sets that flag, and plugin 2.1.1 never sends it, so
without this the first save into any new folder fails
(spike:ov-save-skill/11). The static block the wrapper returns from
`system_prompt_block` lists seven tools.

The wrapper ships in the image, so `hermes_version` in
`deployments/applications/services.tf` moves to `0.22.2-3`
(`just rebuild_hermes`), and the pin in `cli/tests/test_hermes_version.py`
moves with it.

**The prompt.** `deployments/applications/services/hermes/SOUL.md` gets
one line in its OpenViking section: to save anything to OpenViking, use
the `save-to-openviking` skill, and ask where when the operator did not
say. Its tool table gains `viking_write`, and "Do not shell out to curl"
stays as it is.

**Tests.** `new:cli/tests/test_hermes_save_skill.py` reads the skill and
SOUL from the repo and checks that the skill: has front matter Hermes
loads (name, description, category); reads `.map.md` before saving; asks
when no place was given and does not save before the answer; appends a new
root to the map; falls back to exactly one `list` of the resources root;
seeds the four roots; writes the map only with `viking_write`; holds no
hardcoded list of leaf folders beyond the seed; and that SOUL points at
the skill and lists `viking_write`. The wrapper's test file from
`ov-no-auto-capture` (cli/tests/test_hermes_openviking_tools.py) gains
cases for `viking_write`: it is in `get_tool_schemas()` with the three
modes; a call sends `POST /api/v1/content/write` with `uri`, `content` and
`mode` to a stand-in client and returns its result; an unknown mode or a
missing `uri` returns a tool error and sends nothing; a
`viking_add_resource` call with `parent` reaches the client with
`create_parent: true`, and one without `parent` does not; the upstream six
still pass through otherwise. All run under `uv run --directory cli pytest`.

**Docs and knowledge.**
`new:docs/how-to/save-something-to-openviking-through-hermes.md` on the
skeleton in `.claude/rules/how-to-skeleton.md`: send a link with and
without a place, send a voice note and save its transcript, add a new
root, and read the map from Claude Code with the call in
`docs/how-to/call-openviking-from-the-cli.md` (Claude Code reads the map,
it does not write it). `kmctl check --fix` regenerates
`docs/how-to/README.md`. A `kmctl new decision` record chooses a
skill-owned map of roots over a live tree walk and over a periodic job
that rebuilds the map. `.okf/components/hermes.md` names the skill and the
map. `.okf/summary.md` is updated or acked.

**Outcome.** In a live Telegram chat after deploy: "save this <url>" with
no place makes Hermes read the map, propose a folder and ask before
writing; "save this to blogs/anthropic" writes there without asking; a
voice note and "save the transcript" lands as a Markdown file in the
folder the operator confirmed; a new root the operator names shows up in
`.map.md` with its description. `just pre_commit` and
`uv run --directory cli pytest` pass.

**Voice (operator's choice: local Whisper baked into the image).** The
Dockerfile installs faster-whisper 1.2.1 into Hermes's venv, pinned to
Hermes's own uv.lock so the audio libraries match (an unpinned install pulls
PyAV 19.0.1, which breaks every transcription, spike:ov-save-skill/8):

```
RUN cd /opt/hermes && /opt/hermes/tools/uv-0.12.3-linux-arm64/uv export --frozen --no-hashes --extra stt-whisper --no-emit-project -q -o /tmp/stt.txt && /opt/hermes/tools/uv-0.12.3-linux-arm64/uv pip install --no-cache --python /opt/hermes/.venv/bin/python -c /tmp/stt.txt faster-whisper==1.2.1 && rm /tmp/stt.txt
```

`config.yaml` pins `stt.provider: local` and `stt.local.model: base`. The
`base` model (142 MB) downloads on first use to the cache under the job's data
volume (`HOME` is the data dir), so it survives restarts. A test pins the Dockerfile line and the
config keys. ADR 0019's image section gains a note.



## Could invalidate this plan

- Hermes may not transcribe Telegram voice notes in the deployed image.
  STT is on by default and auto-detects local faster-whisper first, but the
  base image does not ship it: hermes-agent's `[all]` extra dropped
  `voice` on 2026-05-12, and `_transcribe_local` lazy-installs
  `stt-whisper` into the venv on the first voice message
  (tools/transcription_local.py, `_try_lazy_install_stt`). That needs the
  process user to write the venv, network, a model download and room in the
  2048 MB cap. No cloud STT key is set in
  `deployments/applications/services/hermes.hcl`. If it fails, the agent
  gets only an audio path and the voice half needs an STT choice (bake the
  extra into `deployments/applications/services/hermes/Dockerfile`, or a
  cloud provider) that this plan does not make. Waiting on a spike.
  The default image has no STT engine and Hermes never installs one on the
  gateway path (spike:ov-save-skill/1, spike:ov-save-skill/3), so voice
  needs the bake-in above. Settled by spike:ov-save-skill/10: with that line
  in an image built from 0.22.2-2 and no `stt` config, the gateway voice
  path transcribed a 5.4 s .ogg/opus correctly (local, `base`); first run
  6.5 s with the download at a 593 MB cgroup peak, then offline from the
  cached model after a restart in 1.9 s at 384 MB. With the ~800 MB
  gateway baseline the worst case is about 1.34 GB of the 2048 MB limit.
  The image grows by 397 MB.
- The map may not work as a dotfile at the resources root. OpenViking
  v0.4.17.1 hides dot-named files from `ls` (storage/viking_fs/_ops.py)
  and refuses direct writes only to `.relations.json` and the generated
  `.abstract.md`/`.overview.md`, so `.map.md` looks allowed, but untested:
  a USER-token `content/write` there (what `viking_write` sends) might be refused, `viking_read` might
  not serve it, or each write might trigger a model summary of the whole
  resources root. Waiting on a spike.
  Settled by spike:ov-save-skill/2: a lab/jasper USER token created,
  replaced and appended the map at the resources root
  (HTTP 200 each), and both content/read and the plugin's `viking_read`
  path returned the exact text. In the default processing mode each write
  makes one VLM call that rewrites only the resources root's
  abstract and overview sidecars, adds no vector row, and the map stays out
  of find, search and plain ls. `viking_write` therefore keeps the default
  mode: `vectors_only` makes the map a top search hit.
- Hermes may not load the skill from a plain "save this <url>" without the
  operator naming it. The skill only works if the model picks it from
  `skills_list` (SOUL's "Skill Discovery" section) with the one SOUL line,
  instead of calling `viking_add_resource` straight away. Waiting on a
  spike.
  Settled by spike:ov-save-skill/9 (a rerun of spike:ov-save-skill/6 with
  the plan's pass condition; /6 failed only on a literal "?" check): on the
  deployed 0.22.2-2 image with the real model, 8 of 8 fresh sessions called
  `skill_view("save-to-openviking")` first; with no place given 5 of 5 made
  no write and asked; with a place given 3 of 3 saved to it without asking.
  After saving, those runs checked the result with curl through `terminal`,
  so the skill says to trust the URI `viking_add_resource` returns and not
  to verify it by hand.
- Saving into a folder that does not exist yet (plan-review round 1,
  finding p1). Settled by spike:ov-save-skill/11: on v0.4.17.1-9 with a
  lab/jasper USER token, a save with `parent=` a missing nested folder
  failed (HTTP 404) without `create_parent`, and with `create_parent: true`
  returned 200, created both folder levels and the file was findable; the
  flag is harmless when the folder exists. The wrapper sends it.
