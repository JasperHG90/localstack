---
verdict: pass-with-required-fixes
tree: cf395cc75c12edb3508115774beeac945a1bf8e2
---

# Documentation freshness: L6-landing-dash-service-groups

## Scope binding

No scope digest and no `verdict_binding_inputs` were handed to this pass, so
the three SCOPE BINDING lines are omitted on purpose and this verdict falls
back to the whole-tree binding, which is stricter. I did not compute a digest
of my own: the brief forbids writing one I was not given.

Every anchor below is quoted verbatim from the tree named above. Paths in the
reviewed diff: `.loop/evals/L6-landing-dash-service-groups.md`,
`.loop/ledger.json`, `TODO.md`, `deployments/applications/services.tf`,
`deployments/applications/services/dash.hcl`,
`deployments/applications/services/dash/backend/src/dash_app/live.py`,
`deployments/applications/services/dash/backend/src/dash_app/main.py`,
`deployments/applications/services/dash/backend/src/dash_app/status.py`,
`deployments/applications/services/dash/backend/src/dash_app/tiles.py`,
`deployments/applications/services/dash/backend/tests/test_cluster.py`,
`deployments/applications/services/dash/backend/tests/test_main.py`,
`deployments/applications/services/dash/backend/tests/test_status.py`,
`deployments/applications/services/dash/backend/tests/test_tiles.py`,
`deployments/applications/services/dash/frontend/index.html`,
`deployments/applications/services/dash/tiles.json`,
`docs/dash-landing-page.md`.

## Verdict

The change touches three documented surfaces, and the same diff updates all
three. No reader following the current docs would now be wrong. One required
fix, and it is a repo-rule violation rather than drift: a British spelling in
a line this diff added.

## Required fix

**DOC-1. `grey` in new prose. Severity: low. Required.**

`docs/dash-landing-page.md:53 = - `hint`: the grey line beside the heading. Optional.`

`.claude/rules/slop-scan-for-docs.md` Layer 2 item 8 sets the target at zero
British spellings in prevention mode, and lists this word in its own scan
regex. The repo carries no `.slop-config.yaml` opt-out, and no other tracked
`.md` uses `grey` or `gray`, so there is no house convention to defer to.
Change `grey` to `gray`. One word.

This is the only item blocking. It misleads nobody about behavior; it is
flagged because the briefing asked for the slop rule to be applied and the
rule states a zero target rather than a preference.

## Documented surfaces, checked one by one

**The tile config schema. Updated in step.** The doc's schema reference now
matches the parser field for field.

- `docs/dash-landing-page.md:73 = A tile needs `fe`, `connect`, or both. One with neither fails to parse.`
  against
  `deployments/applications/services/dash/backend/src/dash_app/tiles.py:146 =         raise TileConfigError(f"tile {key!r} needs an 'fe' or 'connect' block, or both")`
- `docs/dash-landing-page.md:60 = - `jobs`: one or more `{name, node}` pairs. `name` is the Nomad job (or the`
  against `_parse_jobs` and `JobRef`.
- The `open` default the doc claims for `fe.label` is real:
  `deployments/applications/services/dash/backend/src/dash_app/tiles.py:113 =         label=raw.get("label") or DEFAULT_FE_LABEL,`
  with `DEFAULT_FE_LABEL = "open"`.
- Group `key`, `title`, optional `hint`, non-empty `tiles`: all match
  `_parse_group`. Tile-key uniqueness across groups matches the shared
  `seen_tiles` set.
- The removed fields leave no trace: `grep` for `category` and `sortTiles`
  across the tile config, the backend package and `index.html` returns zero
  hits.

**The forbidden-character rule. Documented and enforced.**

`docs/dash-landing-page.md:79 = Two characters are forbidden anywhere in the file: `${` and `%{`. Terraform`
and
`docs/dash-landing-page.md:83 = the job. A bare `$` is fine and already ships. The backend suite asserts`

Both halves check out. The test exists:
`deployments/applications/services/dash/backend/tests/test_tiles.py:278 =     assert "${" not in raw`
with the `%{` assertion on the next line. The bare `$` claim is true: the
`openviking` tile's `connect.example` ships `$OV_KEY`. The jobspec comment
says the same thing and now says it correctly:
`deployments/applications/services/dash.hcl:122 =       ### no template opener: a dollar sign or a percent sign followed by an`
The stale claim it replaced ("contains no dollar-sign characters (confirmed
by grep)") is gone, which closes a doc bug that predates this ticket.

**The two-job registry tile. Documented.** `docs/dash-landing-page.md:7-8`
names `registry` as one tile covering the OCI API and the `registry-ui`
browser view; `:63-65` states the worst-of fold and that the card names the
deciding job's node; `:17-18` gives the reason. The shipped config carries
`registry` on `ubuntu` and `registry-ui` on `radxa-dragon-q6a` under
`artifacts`, and `_tile_state` folds via `worst` with `unknown` above `up`.

**The backend's read scope. Updated in step.**
`docs/dash-landing-page.md:129 = matching comes entirely from each tile's own `jobs` array, not from`
replaces the old `tiles.json`'s own `job` field. Correct.

## Surfaces checked and cleared

**DOC-5. Nothing anywhere still describes the old schema.** `git grep` for
`tile` across tracked `*.md`, `*.hcl` and `*.tf` outside `services/dash`
returns only `services.tf:581-589` and the `dash.hcl` template comments, both
of which describe how the file is spliced, never what is inside it. No
README, no `SKILL.md` (the nine under `services/hermes/skills/`), no
`.claude/rules/` file and no other service doc mentions a dash tile schema.
`docs/registry-ui.md` cites `dash` four times, all about the two-task job
shape and the pre-commit hooks, never about tiles.

**Nothing calls memex, openviking-api or registry-ui a dash tile.** `memex`
appears in nine docs, all about the Nomad job, the MinIO bucket, the CDC
bridge and OIDC, none about the landing page. `openviking-api` appears in
`docs/openviking.md:13,136,146` as the API hostname, which is still live and
which the `openviking` tile's own `connect.address` points at. `registry-ui`
appears in `docs/haproxy_reverse_proxy.md:25,30` as an edge route and
throughout `docs/registry-ui.md` as its own service. All three remain true.
The new doc mentions memex zero times.

**DOC-6. The `/api/status` shape change touches no documented surface.**
`git show HEAD:docs/dash-landing-page.md` documented the route path and the
oauth2-proxy upstream split, never the payload. So dropping the top-level
`tiles` key for
`deployments/applications/services/dash/backend/src/dash_app/main.py:92 =             "groups": [_group_json(state) for state in states],`
staled nothing. The endpoint has one consumer, the frontend shipped in the
same job. `git grep api/status` finds it in `dash.hcl:55` (a health check on
the path), `oauth2-proxy.hcl:49-55` and `infrastructure/services.tf:561-564`
(routing, path only), and `docs/dash-landing-page.md:112-119` (routing, path
only). Not one of them names a field.

**DOC-7. The deploy story still reads correctly at 0.3.0.**
`deployments/applications/services.tf:599 =       dash_frontend_version = "0.3.0"`
and `:600` for the backend. `docs/dash-landing-page.md:92-97` already orders
`rebuild_dash_backend`, `rebuild_dash_frontend`, then `just apply`, and
`:102-103` says both tags are read out of `services.tf`, so bump them there
first. `justfile:54` and `:89` each grep `services.tf` for the version, so
the recipe picks up `0.3.0` with no doc edit. Both images rebuilt before the
apply is exactly what the doc prescribes.

**TODO.md.** Line 6 is gone; the file now ends at
`TODO.md:4 = - Remove stale ollama provider keys`. The item this ticket
closes is the item deleted. The eval's row 2 was reworded in the same diff to
stop citing `TODO.md:6`, so no dangling anchor is left behind.

## Advisories, not blocking

**DOC-2. Emphasis crutch.**
`docs/dash-landing-page.md:12 = has one. A service with both gets both, which is the point. A tile that`
"which is the point" carries nothing; the sentence after it does the arguing.
Cut three words on the next touch.

**DOC-3. Contrastive negation, and I would keep it.**
`docs/dash-landing-page.md:5 = Storage, Telemetry, Events, Agentic, Artifacts. A tile is one SERVICE, not`
This is the copula-led trailing form the tier-5 list flags. The rule keeps a
contrast that is load-bearing, and this one names the exact shift a returning
reader holds a stale model of. It survives. Surfaced for the record, not for
action.

**DOC-4. "Two characters" is imprecise.**
`docs/dash-landing-page.md:79` calls `${` and `%{` "two characters" when they
are two two-character sequences. The backticked tokens carry the meaning, so
nobody bans the wrong thing. The jobspec comment at `dash.hcl:122` states it
precisely if a rewording is ever wanted.

## Slop scan, all three layers

Layer 0 clean: no identity leak, no `TODO`/`FIXME`/`XXX`/`HACK`, and every
backticked identifier and path in the new prose resolves. I checked each one
against the tree: the config path, all fifteen schema field names, the `open`
default, `services/dash.hcl` (correct relative to `deployments/applications`,
which the same section establishes), the `prometheus` tile, `just apply`,
both rebuild recipes, and `localstack secret <job>`.

Layer 1, document economy, 6/6. The lead states the single takeaway in its
first clause. Every sentence in the new prose instances or bounds it; the one
exception is DOC-2. The thesis is echoed in the lead, in the schema section
and in the status paragraph, and nothing else repeats. 942 words for a page
an operator reads before editing a config file: the write cost matches the
read cost.

Layer 2, mechanical: 0 new em dashes (the one at `:131` is untouched
pre-existing prose), 0 ` -- ` in prose, 0 semicolon splices, 0 tier-1 slop, 0
smart quotes, 0 prose arrows or `+` conjunctions, longest line 80 characters.
Tier-5: 0 spatial copulas, 0 throat-clearing openers, 0 significance cluster,
0 participial tails, 0 performative honesty, 0 three-fragment bursts, 0
prior-art markers, 0 loop/cascade vocabulary. The hits are DOC-1, DOC-2 and
DOC-3 above, and the two `, not` matches at `:27` and `:119` are unchanged
pre-existing lines outside this diff.

Layer 3, evidence-backed claims: the doc makes one, "The backend suite
asserts both openers are absent", and the test at `test_tiles.py:270-279`
backs it. No "production-ready", "robust", "fast" or "scalable" anywhere.

## Cross-cycle state

Cycle 1 of this pass. No prior `findings.json` existed at
`.loop/scratch/L6-landing-dash-service-groups.documentation/findings.json`,
so there were no settled findings to re-attack. Seven findings written there
for the next cycle. No trust stamp was written: every check in this pass was
a `git grep`, a `sed` or a `python3` read, all well under the wall clock and
none of them mutating, so none qualified.
