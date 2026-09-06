---
verdict: pass
tree: 35683c0103cf5c6f71feaaa9a52f288b730bfb2e
---

# Documentation freshness: L6-landing-dash-service-groups (cycle 2)

## Scope binding

No scope digest and no `verdict_binding_inputs` were handed to this pass, so
the three SCOPE BINDING lines are omitted on purpose and this verdict falls
back to the whole-tree binding, which is stricter. I did not compute a digest
of my own: the brief forbids writing one I was not given, and `loopctl`
exposes no scope-digest command for a tree-bound pass.

Every anchor below is quoted verbatim from the tree named above. Paths in the
reviewed diff (`git diff HEAD`):

    .loop/ledger.json
    TODO.md
    deployments/applications/services.tf
    deployments/applications/services/dash.hcl
    deployments/applications/services/dash/backend/src/dash_app/live.py
    deployments/applications/services/dash/backend/src/dash_app/main.py
    deployments/applications/services/dash/backend/src/dash_app/status.py
    deployments/applications/services/dash/backend/src/dash_app/tiles.py
    deployments/applications/services/dash/backend/tests/test_cluster.py
    deployments/applications/services/dash/backend/tests/test_main.py
    deployments/applications/services/dash/backend/tests/test_status.py
    deployments/applications/services/dash/backend/tests/test_tiles.py
    deployments/applications/services/dash/frontend/index.html
    deployments/applications/services/dash/tiles.json
    docs/dash-landing-page.md

`.loop/evals/L6-landing-dash-service-groups.md` was in cycle 1's path set and
has left it: `git diff HEAD -- .loop/evals/` is now empty, so the file is
byte-identical to HEAD and carries nothing this pass can stale.

## Verdict

Pass. The one required fix from cycle 1 is genuinely applied, the two
advisories stay advisory, and nothing in this cycle's delta opened new drift.
Every documented surface this ticket touches is described correctly by
`docs/dash-landing-page.md` at this tree.

## DOC-1 — RESOLVED (was the required fix)

The anchor now reads, verbatim:

    docs/dash-landing-page.md:53 = - `hint`: the gray line beside the heading. Optional.

A British-spelling sweep over the whole doc
(`grey|colour|behaviour|organis|optimis|centre|licence|defence|catalogue|artefact`)
returns nothing. I re-checked the claim the line makes rather than only its
spelling, and both halves hold:

- `deployments/applications/services/dash/backend/src/dash_app/tiles.py:183 =     return Group(key=key, title=title, hint=raw.get("hint") or "", tiles=tiles)`
  — `hint` really is optional.
- `deployments/applications/services/dash/frontend/index.html:185` styles
  `.section-eyebrow .hint` with `var(--text-faint)`, which is
  `oklch(58% 0.012 340)`. At chroma 0.012 that is a gray, so "gray line"
  describes what renders.

## DOC-2 — ADVISORY, unchanged

    docs/dash-landing-page.md:12 = has one. A service with both gets both, which is the point. A tile that

"which is the point" is still an emphasis crutch under the tier-5 list. I
re-read it in place and it is weaker than a pure crutch: it points back at the
`TODO.md:6` item this ticket deletes, so it carries a thread. Low confidence,
surfaced not auto-rewritten, and not worth a cycle. Still advisory.

## DOC-4 — ADVISORY, unchanged

    docs/dash-landing-page.md:79 = Two characters are forbidden anywhere in the file: `${` and `%{`. Terraform

Still two two-character sequences called "two characters". Still a wording nit
and not drift, for three reasons I re-verified this cycle:

- The backticked tokens are exact, so a reader bans the right thing.
- `deployments/applications/services/dash.hcl:121 =       ### source. A heredoc needs no quote-escaping. tiles.json must carry`
  opens the jobspec comment that states the rule precisely ("a dollar sign or a
  percent sign followed by an opening brace"), and that comment is the one a
  reader hits when editing the splice.
- The doc's next promise is backed:
  `docs/dash-landing-page.md:83 = the job. A bare `$` is fine and already ships. The backend suite asserts`
  is true at
  `deployments/applications/services/dash/backend/tests/test_tiles.py:279 =     assert "%{" not in raw`
  with the `${` assertion on the line above it.

## DOC-3, DOC-5, DOC-6, DOC-7 — absence claims, re-checked not assumed

- DOC-3 — no change in scope, still holds. `docs/dash-landing-page.md:5`'s
  contrastive negation is load-bearing (it names the exact schema shift), so it
  survives the tier-5 keep test.
- DOC-5 — no change in scope, still holds, and I re-ran the grep rather than
  trusting cycle 1. `category|sortTiles|dashboard tile|agent tile|backend tile`
  over tracked `*.md` outside `.loop` hits only Hermes skill metadata. `memex`
  hits no doc that calls it a dash tile. `docs/registry-ui.md` names `dash` four
  times, every one a task-shape analogy, never the tile schema.
- DOC-6 — no change in scope, still holds. `api/status` outside `.loop` hits
  only `docs/dash-landing-page.md:112` and `:116`, both about the route path and
  the oauth2-proxy upstream split. No doc states the payload shape, so
  `tiles` becoming `groups` stales nothing a reader could follow.
- DOC-7 — no change in scope, still holds. Both rebuild recipes in
  `deployments/applications/justfile` read the tag out of `services.tf`, which
  now carries `0.3.0` for both images, so the doc's bump-then-rebuild-then-apply
  order at `docs/dash-landing-page.md:99-108` is still correct.

## DOC-8 — the trimmed `build_routes` docstring is now true — CLEARED

    deployments/applications/services/dash/backend/src/dash_app/status.py:130 =     """One synthetic `Route` per job, named after that job.
    deployments/applications/services/dash/backend/src/dash_app/status.py:132 =     De-duplicated by name, because two tiles may name the same job.

Checked clause by clause against the body at
`deployments/applications/services/dash/backend/src/dash_app/status.py:136 =     names = dict.fromkeys(job.name for group in groups for tile in group.tiles for job in tile.jobs)`:

- One route per job, named after that job: matches.
- De-duplicated by name: `dict.fromkeys` dedups and keeps first-seen order.
- "two tiles may name the same job" is a real possibility, not a hypothetical
  the parser forbids. `tiles.py` rejects a duplicate group key (`:206`) and a
  duplicate tile key (`:178`) and never a repeated job name.
- The blank `hostname`/`backend_host`/`backend_port` clause is scoped to
  `join()`'s HEALTH computation, and `_job_state` reads only `row.health` and
  `row.job_source`, so the scoping is honest. `join()` does read the other
  fields, but only into `ServiceRow.url` and `.backend`, which nothing here
  touches.

No claim about what the de-duplication *prevents* survives the trim, which is
exactly the overclaim that had to go.

## DOC-9 — dropping `all_tiles` documents nothing — CLEARED

Repo-wide grep for `all_tiles` across `py/md/html/hcl/json/tf` returns two
`.loop` review artifacts and nothing else: the adversarial verdict that asked
for the deletion, and its ledger. No doc, no docstring, no jobspec comment
named it. The helper had no caller, so no reader loses a name they were told
to use.

## DOC-10 — the two frontend fixes close a doc/behavior gap — CLEARED

    deployments/applications/services/dash/frontend/index.html:73 =   [hidden] { display: none !important; }
    deployments/applications/services/dash/frontend/index.html:231 =   a.card-corner { position: relative; z-index: 1; }

Neither touches a documented surface: no doc names a CSS class, a z-index, or
the `hidden` attribute. Both move the page toward the doc rather than away
from it, which is the direction that matters here:

- `:73` makes `el.hidden` actually hide `#modal-connect` and `#modal-fe`. An
  author `display` on `.fe-button` would otherwise outrank the UA rule, so a
  tile with no `fe` would have rendered an empty button. That would have
  falsified `docs/dash-landing-page.md:10 = Clicking a tile opens a panel: the status of every job behind the service,`
  and the "if it has one" qualifier two lines down.
- `:231` narrows the lift to the anchor form. The `fe` anchor
  (`index.html:514`) still sits above the stretched `.card-open` button, so
  `docs/dash-landing-page.md:13 = only linked out never showed you its API. Tiles that have a UI also keep a`
  and its "still one click" close stay true. A tile with no `fe` renders a
  plain `span.card-corner` that no longer swallows the click, so "clicking a
  tile opens a panel" is now true over the whole card.

## DOC-11 — the rest of the schema reference still matches the code — CLEARED

I re-walked every schema claim in "Adding, removing, or reordering a tile"
against the shipped config and the parser rather than trusting cycle 1:

- Six groups in the doc's stated order (Platform, Storage, Telemetry, Events,
  Agentic, Artifacts), matching `docs/dash-landing-page.md:4-5`.
- `openviking` is one tile carrying both `fe` and `connect`; `registry` is one
  tile over `registry@ubuntu` and `registry-ui@radxa-dragon-q6a`, matching
  `docs/dash-landing-page.md:6-8`.
- `docs/dash-landing-page.md:66 = - `fe`: `{url, label}` for a service with a browser UI. `label` is the panel`
  is backed by
  `deployments/applications/services/dash/backend/src/dash_app/tiles.py:20 = DEFAULT_FE_LABEL = "open"`
  and by `index.html:582`, where `feEl.textContent = s.fe.label` puts it on the
  panel button and nowhere else.
- The at-least-one-of-`fe`/`connect` rule at `docs/dash-landing-page.md:73` is
  enforced at `tiles.py:145-146`.
- The worst-of-its-jobs fold and the deciding job's node
  (`docs/dash-landing-page.md:63-65`) match `status._SEVERITY`, `worst`, and
  `_tile_state`.
- `docs/dash-landing-page.md:129`'s "each tile's own `jobs` array" matches
  `build_routes`.

One nit I looked at and am not raising: `docs/dash-landing-page.md:51` says a
group `key` is "used for nothing but catching duplicates", while `_group_json`
does emit it in the payload. The page's only consumer ignores it (`groupHtml`
reads `title`, `hint`, `tiles`), so the sentence is true for the operator it
addresses. It is also unchanged from the diff cycle 1 reviewed, not new drift.

## What I ran

`uv run --project .../dash/backend pytest .../tests -q` — `71 passed, 2
deselected, 1 warning in 0.15s`. Bounded at 300s; it took 0.15s, hits no
network and mutates nothing outside the worktree, so it earns no trust stamp
and I re-ran it rather than trusting a stale result.

Ledger updated at
`.loop/scratch/L6-landing-dash-service-groups.documentation/findings.json`:
DOC-1 flipped to `resolved` on re-read, DOC-2 through DOC-7 re-attacked in
place with cycle-2 evidence, DOC-8 through DOC-11 appended.
