---
type: handoff
title: "OpenViking reset, aim-to-APM migration, CI tailnet access"
description: "OV reset epic is live; aim-to-apm is mid plan review; ci-tailscale-access waits on the operator; Bifrost systemone path answered."
tags: [handoff]
generated:
  by: process:kmctl/0.12.1
  at: 2026-10-21T20:17:34Z
stale_after: 2026-11-04T20:17:34Z
handoff_key: "4ca90099-be7e-4fbd-920f-0030c7cc5d96"
---

# OpenViking reset, aim-to-APM migration, CI tailnet access

## Summary

Three threads, in the order the operator gave them.

**OpenViking reset (epic `ov-reset`, done and live).** The operator wanted to
start over and stop agents capturing into OpenViking on their own. Four
tickets landed on main and were applied on 2026-10-20:
`ov-no-auto-capture` (Hermes uses the tools-only `openviking_tools`
provider, ADR 0020), `ov-fresh-instance` (bucket `openviking-v2`, schema
`openviking_v2`, volume `openviking_data_v2`, one identity `lab`/`jasper`,
Veerle's access removed, ADR 0021), `ov-carry-over` (clips, blogs and leo
copied from the old bucket, blog-scraper merged into `blogs/`, re-indexed,
ADR 0022) and `ov-save-skill` (a `save-to-openviking` Hermes skill that owns
a `.map.md` of roots and asks where to save; `viking_write` and
`create_parent` in the wrapper; local faster-whisper in the image for voice
notes; Hermes `0.22.2-3`, ADR 0023). Everything lives under
`viking://user/jasper/resources/` (operator's choice). The old bucket
`openviking`, schema `openviking` and volume `openviking_data` are a
read-only backup; the cutover baseline matched afterwards.

Two hand repairs happened during the carry-over run. The merged
`blogs/deepmind/gemini-4-argon.md` overview came out blank and was
regenerated. The re-index embedded raw text as each file's abstract
(OpenViking 0.4.17.1's re-index parser misses the `### [name](uri)`
overview format), so the 761 carried text files' level-2 rows were replaced
with the old schema's rows (URI rewritten blog-scraper to blogs, id
`md5('lab:viking:/' || uri)`). Search ranking did not change measurably,
which shows ranking is OpenViking's, not the carry-over's. The operator's
RRF hybrid pipeline (ov-ext) runs on the new store: a trace showed the
keyword leg returning 20 hits in 31 ms and no `keyword leg failed` lines.

**aim-to-APM migration (ticket `aim-to-apm`, planning, round 1 failed and
fixed, round 2 not started).** Goal: everything aim installs comes from
`apm.yml` and aim goes away. Decisions (operator, 2026-10-20/21): drop the
drawio and excalidraw MCP servers; caveman becomes a documented manual
`claude plugin install` because APM 0.33 only unpacks a marketplace plugin
(spike 1); skills stay at aim's pins (folders install pinned and
byte-identical, spike 2); rules and the two subagents come from
jasperhg90/skills at 1c3dd31, which ships `.instructions.md` and
`.agent.md` files APM accepts (plain `.md` files are refused, spike 2;
deploy paths verified, spike 3); `slop-scan-for-docs` is vendored; rules are
copied into `.opencode/rules/` by the install recipes; the two subagents
stay Claude-only because OpenCode rejects their front matter;
`python-testing` becomes scoped to `**/*.py` (accepted); kept as one ticket.
Plan-review round 1 found p1 (that scope change, now accepted and recorded)
and p2 (`just check-install` fails at HEAD because end-of-file-fixer adds a
newline to two kmctl-written files). Step 8 widens the pre-commit `exclude`;
spike 5 proved that plus committing the two files as installed makes
`check-install` pass. The operator then asked to fix the newline at the
source; the two files come from kmctl (`.agents/skills/audit/evals/sample-findings.json`
and `opencode.json`), not the skills repo, so the source fix belongs in the
kmctl repo.

**CI tailnet access (`ci-tailscale-access`, planning; `ci-openviking-sync`,
stub).** A reusable composite action joins the tailnet as an ephemeral
`tag:ci` node and logs into Vault with GitHub OIDC; a second action syncs a
repo's `docs/` and `.okf/` to
`viking://user/jasper/resources/projects/<repo>/` with ovsync. Its three
risks need the operator: the tailnet policy (still allow-all) and GitHub
workload identity federation are console-only, and the cross-repo Vault
JWT test needs a second repository.

## Where it stands

Done and working: the four `ov-reset` tickets are on main and live.
OpenViking `/ready` is 200, Hermes is on `0.22.2-3` with `openviking_tools`,
the `daily-blog-scrape` cron is resumed and saves under `blogs/`, and the
SeaweedFS 404 loop is gone (0.03/s). Backup-s3 ran after the cutover and
completed.

In progress: `aim-to-apm` has every risk settled (spikes 1 to 5) and the
plan edited for round-1 findings, but round 2 has not been opened, and the
plan does not yet say whether the newline fix goes to kmctl upstream or
stays a local exclude. Grant g2 covers operator steps until 2026-10-21
20:54 UTC.

Untested or uncertain: no live save through `save-to-openviking` has run
yet (ticket `ov-save-skill` row r6 is a post-deploy judgment). The carry-over
script's checks are too literal (overview names, exact-title search) and its
how-to omits `OV_URL`/`OV_TOKEN`. The cutover README's step 7 uses
`ov_identity_probe.py`, which fails on an empty instance by design.
`blogs/_lockprobe` is a stray probe folder carried over. Bifrost
`/v1/systemone` returns 405: the routes that exist are
`/typesafe/v1/systemone`, `/v1/decisions` and `/openai/v1/decisions`
(all answer 400 to an empty body); a real call may still fail on the
virtual key's `allowed_models` or a missing TypeSafe provider.

## Next steps

1. Ask the operator whether to open a PR on the kmctl repo that makes
   `plugin patch` and its audit skill write files with a final newline; then
   decide in the `aim-to-apm` plan whether step 8's exclude stays as a guard.
   Run `loopctl review start aim-to-apm` for plan-review round 2, sign the
   eval, build.
2. For `ci-tailscale-access`: write the tailnet policy JSON for the operator
   to paste, have them set up GitHub workload identity federation for
   `tag:ci`, and get their OK to create a private test repo for the
   cross-repo Vault JWT spike.
3. Bifrost decision models: get the client and model the operator uses and
   make one real call to `/v1/decisions` or `/typesafe/v1/systemone`.
4. Small follow-ups: a ticket to fix the carry-over script's checks and docs
   and copy all old file rows itself; fix README step 7; delete
   `blogs/_lockprobe`; `ov-carry-over-cleanup` (stub) once the operator signs
   off; delete the old store only on the operator's word.

## Key references

- Plans: `.loop/plans/aim-to-apm.md`, `.loop/plans/ci-tailscale-access.md`,
  `.loop/plans/ci-openviking-sync.md`, `.loop/plans/ov-carry-over-cleanup.md`.
- Spikes: `.loop/spikes/aim-to-apm/` (1 caveman, 2 single files, 3 deploy
  paths, 5 check-install), `.loop/spikes/ov-*`.
- Decisions: `.okf/decisions/0020-agents-use-openviking-through-tools-only.md`,
  `0021-openviking-starts-over-on-a-v2-store.md`,
  `0022-openviking-carry-over-copies-storage-and-re-indexes.md`,
  `0023-hermes-saves-from-a-skill-owned-map-of-roots.md`.
- Cutover steps: `deployments/applications/services/openviking/README.md`;
  carry-over: `docs/how-to/carry-the-kept-trees-over-to-the-new-openviking.md`,
  `scripts/ov_carry_over.py`.
- Hermes: `deployments/applications/services/hermes/openviking_tools/__init__.py`,
  `deployments/applications/services/hermes/skills/productivity/save-to-openviking/SKILL.md`.
- Upstream issues filed: JasperHG90/openviking_extensions #13 to #20
  (OpenViking 0.5.1 compatibility).
- Bifrost decisions: https://www.getmaxim.ai/bifrost/blog/bifrosts-v1-decisions-one-api-for-decision-models-across-eight-providers
