---
type: plan
title: 'Plan: aim-to-apm'
description: Declare everything aim installs (rules, skills and subagents) in apm.yml at pinned refs, install it with the existing kmctl-install recipes for Claude and OpenCode, and delete aim.toml, aim.lock.toml and the aim markers in AGENTS.md.
tags:
- plan
generated:
  by: process:loopctl/2.2.2.dev1+gd84319696
  at: '2026-10-20T20:41:40+00:00'
slug: aim-to-apm
epic: null
depends_on: []
priority: null
---

# aim-to-apm

Relayed from: none

## Intent

Operator's words: "Migrate aim to APM".

Today two tools install agent tooling into this repo. APM installs kmctl's
package from `apm.yml`, locked in `apm.lock.yaml`. aim (agent-integrations-manager)
installs the rest from `aim.toml`, locked in `aim.lock.toml`, for Claude only
(`layout_profile = "claude"`). The devcontainer stopped installing aim
(`.okf/log.md`), so nothing installs aim's set on a fresh checkout anymore.
This ticket moves aim's set into `apm.yml` and deletes aim, so one command
installs everything for both targets in `apm.yml` (claude, opencode).

What aim installs today (counted from `aim.toml`):

- 7 rules: adversarial-reviews, pre-existing-issues, prek-code-quality,
  python-testing, uv-installer and plain-language from the rules folder of
  github.com/jasperhg90/skills, and slop-scan-for-docs from
  github.com/athola/claude-night-market.
- 12 skills: 10 from jasperhg90/skills (manifesto, deep-explain, doc-write,
  python-review, readme-creator, release, generate-art,
  remove-image-background, agent-creator, rule-creator), adhd from
  uditakhourii/adhd, bencium-impact-designer from bencium/bencium-marketplace.
- 2 subagents: adversarial-reviewer and feature-planner from
  jasperhg90/skills.
- 2 MCP servers from the MCP registry, written into `.mcp.json`:
  io.github.yohasacura/drawio-mcp and io.github.cmd8/excalidraw-mcp. Both
  fail to connect in Claude Code today (drawio: CONNECTION_CLOSED, excalidraw:
  npx not found). Nothing in the repo uses them; the `.drawio.png` files under
  `docs/reference/architecture/` are static images.
- 1 Claude plugin: caveman v1.9.1 (commit e2c09c9) from the
  github.com/juliusbrussee/caveman marketplace, copied to
  `.claude/plugins/aim-10ae737f6885d841/` and enabled in the gitignored
  Claude settings file in `.claude/`.

### What the build does

1. Snapshot aim's installed copies under `.claude/rules/`, `.claude/skills/`
   and `.claude/agents/` to a scratch folder, for the byte comparison below.
2. Add the skills, rules and subagents to `apm.yml` under `dependencies.apm`.
   - Skills: each skill folder pinned to the commit `aim.lock.toml` records as
     its `current.sha`, so their content stays what is installed now
     (jasperhg90/skills is locked at six different commits; APM installs one
     repo at several commits, spike:aim-to-apm/2).
   - Rules and subagents from jasperhg90/skills: APM 0.33.0 refuses a single
     plain `.md` file (spike:aim-to-apm/2), so they come from the APM-named
     files the skills repo now ships (rules named `.instructions.md`, agents
     named `.agent.md`), pinned to commit 1c3dd31 (2026-10-18, "check
     rules and agents are named for apm"). Their content may differ from
     aim's older pins: the build records the diff against the step 1
     snapshot for the operator.
   - `slop-scan-for-docs` (athola/claude-night-market) is a plain `.md` in a
     third-party repo, so APM cannot install it. It is committed in this
     repository in the `.claude/rules` folder, byte-identical to
     aim's pin, and `.gitignore` lets it through.
3. Delete aim's copies from `.claude/`, plus `.claude/plugins/aim-10ae737f6885d841/`
   and its `enabledPlugins` and `extraKnownMarketplaces` entries, so `apm install`
   does not stop on files it did not write. Then run `just kmctl-install` and
   commit `apm.yml`, `apm.lock.yaml` and every tracked file it writes under
   `.agents/skills/` and `.opencode/`.
4. MCP servers: drop drawio-mcp and excalidraw-mcp (operator, 2026-10-20).
   They do not go into `apm.yml`, and their entries leave `.mcp.json`.
5. caveman: `README.md` documents a manual step, `claude plugin marketplace
   add juliusbrussee/caveman` then `claude plugin install caveman@caveman`.
   The operator preferred APM if it could (2026-10-20), but APM 0.33.0 only
   unpacks a marketplace plugin into loose skills, agents, commands and
   merged hooks, with no `enabledPlugins` or marketplace entry
   (spike:aim-to-apm/1), so caveman stays out of `apm.yml`. The aim copy and
   its settings entries are gone.
6. OpenCode rules: in the `kmctl-install` and `kmctl-install-frozen` recipes,
   after `kmctl plugin patch`, add one line that copies the 7 APM-installed
   rule files from `.claude/rules/` into `.opencode/rules/`, where the
   `opencode.json` instructions glob already loads them (operator,
   2026-10-20). Commit the 7 files it writes there, so `check-install` sees
   them. APM 0.33.0 writes no OpenCode rules itself (spike:aim-to-apm/3).
   The same recipes then remove the two subagents APM writes to
   `.opencode/agents/`: their `tools` (a string) and `color` (`blue`) front
   matter is not valid for OpenCode, which APM warns it will reject
   (spike:aim-to-apm/3). aim never installed them for OpenCode, so they stay
   Claude-only until the skills repo makes that front matter OpenCode-valid.
7. Delete `aim.toml` and `aim.lock.toml`. In `AGENTS.md`, delete the aim
   header block and the two `aim: guidelines` marker lines, and keep the
   guidelines text as plain text. Decision: the guidelines stay in
   `AGENTS.md`, not in a rule, because `AGENTS.md` is the one file both
   harnesses load (Claude Code through the `CLAUDE.md` symlink, OpenCode
   natively), and all but four of `.claude/rules/` are gitignored. Record this
   with `kmctl new decision`, naming moving it into a rule as the rejected
   option. Git tracks `CLAUDE.md` as a symlink (mode 120000), so it stays
   after aim goes, and nothing has to recreate it.
8. Docs: the "Knowledge management with kmctl" section of `README.md` says
   `apm.yml` also carries the agent tooling, and how to get anything APM
   cannot install (the caveman plugin). That section names `just
   install`, `just init` and `just check`, but `justfile` defines
   `kmctl-install`, `kmctl-init` and `kmctl-check`. Fix the names to match
   `justfile` (pre-existing drift). Update `.okf/summary.md` or run `kmctl summary
   ack`, then run `kmctl check`.

`justfile`, `apm.yml` and `README.md` are rendered from kmctl's copier template
(`.copier-answers.yml`). `just kmctl-upgrade` runs `copier update`, which
merges changes made since the last render, so edits made here survive an
upgrade, possibly with a conflict to resolve. Keep the `justfile` change as
small as possible.

### OpenCode: what APM does not do

kmctl v0.12.1's OpenCode module (src/kmctl/opencode.py in the kmctl repo,
backed by kmctl's spike opencode-harness/1) says APM 0.33.0 writes skills to
`.agents/skills/` and copies agents to `.opencode/agents/` unchanged, but
writes no rules for OpenCode. Agents keep Claude Code's front matter, and
OpenCode drops it silently. `kmctl plugin patch` fills those gaps only for
kmctl's own four rules and three agents. So `apm install` alone will not put
aim's 7 rules into `.opencode/rules/`, which `opencode.json` loads. The
2 subagents land in `.opencode/agents/` with front matter OpenCode ignores.
Step 6 closes the rules gap.

### Outcome

On a clean clone, `just kmctl-install-frozen` (the recipe the operator calls
`just install-frozen`) puts all 7 rules, 12 skills and 2 subagents in
`.claude/`; caveman comes from the documented manual step. Each skill file is byte-identical to
the step 1 snapshot (`diff -r` is empty). Rules and subagents match
jasperhg90/skills at 1c3dd31 as APM deploys them, and their diff against the
step 1 snapshot is recorded for the operator; `slop-scan-for-docs` is
byte-identical to aim's copy. For OpenCode, the 12 skills land in
`.agents/skills/`, no subagent stays in `.opencode/agents/`, and the 7 rules in
`.opencode/rules/`, each rule byte-identical to its `.claude/rules/` copy.
`.mcp.json` holds no drawio-mcp or excalidraw-mcp entry. `apm.lock.yaml` records each
dependency at its pinned commit. `aim.toml`, `aim.lock.toml` and every `aim:`
marker in `AGENTS.md` are gone. `CLAUDE.md` still resolves to `AGENTS.md`.
`just check-install` passes on a clean checkout. `just pre_commit` and `uv run
--directory cli pytest` pass.

## Could invalidate this plan

- APM 0.33.0 may not deploy rules and subagents where Claude loads them.
  Settled by spike:aim-to-apm/3 (after spike:aim-to-apm/2 showed plain `.md`
  files are refused): from jasperhg90/skills at 1c3dd31 the
  `.instructions.md` rules land as `.md` files in `.claude/rules` with their
  body unchanged (APM rewrites `applyTo` front matter to `paths:` and drops
  name and description), the `.agent.md` subagents land byte-identical in
  `.claude/agents`, a skill folder at another pin installs beside them,
  `apm.lock.yaml` pins each, and `apm install --frozen` restores all of them
  byte for byte.
