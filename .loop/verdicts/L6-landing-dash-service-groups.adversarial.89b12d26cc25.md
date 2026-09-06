---
verdict: fail
tree: cf395cc75c12edb3508115774beeac945a1bf8e2
---

# Adversarial review: L6-landing-dash-service-groups (cycle 1)

No scope digest was supplied in my briefing, so I omit the
`bound_paths`/`scope`/`citations` binding and let this verdict fall back to
the stricter whole-tree binding.

## Deterministic floor

`loopctl verify-eval-substance L6-landing-dash-service-groups` returns
`valid`, exit 0. No hard-fail, no advisory: no comment-only grep scorer, no
stale `depends_on`, no amendment that dropped a required check, no empty
`Fails-when` cell, no plan-drift, no positional row citation, no
`assessed-statically-not-executed` row. Proceeded to the deep pass.

`loopctl verify --expect-tree cf395cc7...` passed before the review and again
after I re-ran the gate, so nothing I did moved the tree.

## Gate, re-run independently

`just pre_commit`: all 27 hooks Passed, exit 0 (~95s). Trust stamp at
`.loop/scratch/L6-landing-dash-service-groups.adversarial/trust-stamp.json`,
keyed on this cycle's fingerprint. Backend suite: 71 passed, 2 deselected
(the two `cluster`-marked tests, excluded by `addopts`, as P17 says).

## Verdict

**fail.** The backend is correct and well-tested; I could not break it. The
frontend carries two defects that no gate in this repo can see, and one of
them ships a wrong outbound link on 6 of the 15 tiles. Both fixes are
one-line CSS changes.

---

## F1 — HIGH — the panel's frontend button never hides

`deployments/applications/services/dash/frontend/index.html:314` (inside
`.fe-button {` at `:313`):

    display: flex;

`:488`:

    <a class="fe-button" id="modal-fe" hidden href="#" target="_blank" rel="noopener noreferrer"></a>

`:574`:

    feEl.hidden = !s.fe;

`hidden` hides an element through the UA stylesheet rule
`[hidden] { display: none }`. The CSS cascade sorts by ORIGIN before it ever
looks at specificity, and a normal author declaration outranks a normal
user-agent one. `.fe-button { display: flex }` is an author declaration, so
`feEl.hidden = true` sets the attribute and changes nothing on screen.

The same file proves the asymmetry rather than my reading of the spec.
`:478` is the sibling case:

    <div id="modal-connect" hidden>

That is a bare `div` with no author `display` rule anywhere, so its `hidden`
works. One of the two `hidden` toggles in this diff is load-bearing and the
other cannot be, and nothing in the file normalizes `[hidden]`.

What ships: the six connect-only tiles (postgres, redis, tempo, prometheus,
nats, hermes) get an accent-colored button in their panel that their service
does not have. On first load it is an empty ~40px bar with `href="#"`. After
the operator opens any tile that does have an `fe`, `feEl.href` and
`feEl.textContent` are never reassigned for a connect-only tile, so the
postgres panel offers a button labeled and linked for grafana. That is a
wrong destination, not just a cosmetic artifact.

Why nothing catches it: `.pre-commit-config.yaml:117` states the frontend
holds no Python and defines no JS or CSS hook (P12), and the eval's four
manual browser rows exercise only `openviking` (fe + connect) and `grafana`
(fe only). Neither is a connect-only tile, so rows 1-4 would score green with
this bug present. The eval's blind spot sits exactly on the defect.

Honest bound on this finding: there is no browser and no JS runtime in this
environment (`node`, `nodejs`, `deno`, `bun`, `npx` all absent), so I derived
this from the cascade rule and the file's own internal inconsistency rather
than executing the page. I did not write a reproducer into the tree, which
would have breached read-only and moved the stamp's fingerprint.

Fix: either add `[hidden] { display: none !important; }` to the stylesheet,
or stop using the attribute here and toggle a class that sets `display: none`.

## F2 — MEDIUM — the corner icon is a click dead zone on any tile with no `fe`

`:226`:

    .card-corner { position: relative; z-index: 1; display: flex; line-height: 0; }

`:510`:

      : `<span class="card-corner">${CONNECT_ICON}</span>`;

`:584`:

    const opener = event.target.closest('.card-open');

The stacking is right for the case R6 asks about and wrong for the other one.
`.card-open` is absolutely positioned with `z-index: auto`, so it paints above
the card's in-flow content and takes a click anywhere on the card. Correct.
`.card-corner` carries `z-index: 1`, so it paints above `.card-open`. Also
correct, and necessary, for `a.card-corner` — that is how eval row 4's
one-click escape survives, and the delegated listener does the right thing
there, since `closest('.card-open')` walking up from the anchor finds nothing
(the button is a sibling, not an ancestor) and returns early without opening
a panel behind the new tab.

But the selector is not scoped to the anchor. On a tile with no `fe` the
corner is `span.card-corner`, which gets the same `z-index: 1` and the same
lift above the button, and the same `closest` walk returns null. So clicking
the connect icon on postgres, redis, tempo, prometheus, nats or hermes does
nothing at all. R5 says "Every card opens the panel" and the eval's
Definition of Done says "one click on any tile opens one panel"; a ~15px
region on 6 of 15 cards does not. The icon is also the one element on those
cards that advertises "there are connection details here", so it is a likely
click target, and `cursor` reverts to the default over it because
`cursor: pointer` lives on `.card-open`.

No `pointer-events` declaration exists anywhere in the file (grep: zero hits),
so nothing else rescues this.

Fix: `span.card-corner { pointer-events: none; }`, or scope the z-index to
`a.card-corner`.

## F3 — LOW — `all_tiles` is dead code

`deployments/applications/services/dash/backend/src/dash_app/tiles.py:213`:

    def all_tiles(groups: list[Group]) -> list[Tile]:

Repo-wide grep returns the definition and nothing else: no caller in `src/`,
no test, no doc. Section 7's `tiles.py` row names `Group`, `_parse_group`, the
rewritten `_parse_tile` and the regrouped `load_tiles`, and does not name this.
It fails R14 (every change ships a test), R17 (every changed line traces to a
requirement) and AGENTS.md section 2 (nothing speculative). Delete it.

## F4 — LOW — the signed eval was amended inside the implementation diff

`.loop/evals/L6-landing-dash-service-groups.md:18`, row 2's `Fails-when` cell,
changed from "This row is `TODO.md:6` itself." to "This row is the TODO item
this ticket closes, which the ticket also deletes from TODO.md."

The substance is intact — the actual fail conditions ("The panel shows only
the button, or only the instructions; or `openviking-api` still has its own
tile") are unchanged, and `verify-eval-substance` agrees. The reason for the
edit is legitimate: the ticket deletes `TODO.md:6`, so the old citation would
dangle. Two things to name anyway. The eval file is not in section 7's
declared code surface, so this is an undeclared change under R17. And the
`signed-off-by` line and its timestamp are unchanged, so the signature now
covers text edited after signing, by the party under review. `loopctl` has an
`eval-amend` path for exactly this and it was not used. Not a blocker; record
it.

---

## What I attacked and could not break

**The worst-of fold and its tie-break (briefing item 2).** `_SEVERITY` at
`status.py:49` is `{"up": 0, "unknown": 1, "degraded": 2, "down": 3}`, which is
R4's order with `unknown` above `up`. The tie-break claim holds: CPython's
`max` replaces only on strictly greater, so it returns the FIRST maximal
element, and `_tile_state` at `:170` feeds it `job_states` in config order.
Probed directly: `max([("a",1),("b",1),("c",0)], key=...)` returns `("a",1)`,
and returns `("a",1)` again when the list is reordered so the zero comes
first. The tie case is pinned by a test, in
`test_unknown_states_keeps_the_shape_but_knows_nothing`: two jobs both
`unknown`, asserting `tile.node == "n1"`.

The agent-endpoint rung still works and is covered. Mutating
`_status_from_consul` so `"no check"` stops reading `up` turns
`test_an_agent_endpoint_tile_with_no_registered_check_still_reports_up` red.

**`build_routes` and `join()` (briefing item 3).** `dict.fromkeys` is correct:
it preserves first-seen order and uniquifies, and `join()` only reads
`route.name`. But the de-dup is a no-op, not a fix. Removing it left the suite
green (71 passed), and reading `join()` says why: duplicate routes with the
same name produce byte-identical `ServiceRow`s, `routed_jobs` is a set, and
`compute_tile_states` collapses the rows through `{row.name: row for ...}`
anyway. So the docstring's "join() would otherwise emit a row per route and the
later one would win" is true and harmless — the later one is the same row. The
code is fine; the comment claims more than the behavior. Logged as O1.

**R12's guardrail (briefing item 4).** The fix is right and the test bites. The
`dash.hcl:112-131` comment now spells neither opener ("a dollar sign or a
percent sign followed by an opening brace") and says why it cannot, which is
the kind of comment `minimal-comments` warrants: it records an outside
constraint no source can state. `terraform-validate` passed in my gate run.
I injected both openers into a copy of `tiles.json` in scratch:
`%{ if true }X%{ endif }` in a tile `desc` turns
`test_the_shipped_config_carries_no_nomad_template_opener` red on its own, and
so does a JSON-valid `${NOMAD_ALLOC_ID}`. Eval row 7 holds for both openers.

The exemption you claimed for that test's negative assertions is legitimate,
and for a checkable reason rather than by assertion. The vacuous-pass risk for
`assert "${" not in raw` is a wrong or empty `SHIPPED_TILES`. `Path.read_text()`
raises on a missing file rather than returning `""`, so the test would error,
not pass; and the same module's
`test_the_shipped_config_parses_into_the_six_expected_groups` calls
`load_tiles(SHIPPED_TILES)` and pins the full 6-group, 15-tile structure, which
is a positive control on the constant itself. Same reasoning covers the
no-memex test. Both guards are over a fixed artifact the module already proves
is real and non-empty.

**Test quality generally (briefing item 6).** Nine mutations in a scratch
harness with its own venv (my first attempt was contaminated — a copied `.venv`
whose console scripts still shebang the original interpreter, so pytest loaded
the pristine source and every mutation "survived"; I caught that with a probe
test printing `dash_app.status.__file__` and rebuilt from a clean `uv sync`).
Results:

| mutation | caught by |
|---|---|
| `worst()` returns `statuses[0]` | `test_a_two_job_tile_reports_the_worst_of_the_two` |
| `_tile_json` drops `status` | `test_a_fetch_failure_...` (eval row 8's own Fails-when) |
| deciding job becomes `job_states[0]` | `test_a_two_job_tile_reports_the_deciding_jobs_node_and_counts` |
| `fe` always emitted, `null` when absent | `test_a_tile_with_only_connect_emits_no_fe_key` |
| groups sorted by key | `test_status_payload_carries_groups_in_config_order` |
| agent rung: `"no check"` stops reading `up` | `test_an_agent_endpoint_tile_with_no_registered_check_still_reports_up` |
| `%{` opener in `tiles.json` | `test_the_shipped_config_carries_no_nomad_template_opener` |
| `${IDENT}` opener in `tiles.json` | same |
| `build_routes` de-dup removed | nothing (no-op, see O1) |

The negative assertions that construct their own input do carry controls:
`test_a_tile_with_only_connect_emits_no_fe_key` asserts `"fe" in grafana` in
the same payload, and `test_a_two_job_tile_reports_the_worst_of_the_two`
re-runs the same tile with both jobs healthy and asserts `up`. The
deciding-job `counts` assertion is not tautological either — I probed the two
values and they differ (`registry` `'1/1'`, `registry-ui` `'0/0'`), so picking
the wrong deciding job fails it.

One factoring note, not a defect: section 8 asked for the two-job test to be
parametrized over the severity order. The implementation instead parametrizes
`worst()` directly with all 8 orderings (including `["up","unknown"] ->
"unknown"`) and tests the integration once at `compute_tile_states`. Since
`_tile_state` calls `worst` directly, that is the same coverage with less
duplication.

**Scope (briefing item 5).** `git diff --name-only HEAD` lists 16 paths. All 14
files section 7 declares changed, and each change matches its declared row.
The two extras are `.loop/ledger.json`, which the harness writes itself
(`stage: ready -> adversarial-review`), and the eval marker, which is F4.

Shipped config checked against R2 by parsing it: six groups in the declared
order with the declared titles and hints, tiles in the declared order, 15
total, no memex, no `openviking-api`, no `registry-ui`, prometheus present with
`connect` and no `fe`, registry naming both jobs on both nodes. Zero `${` and
zero `%{`; the one bare `$` is `tiles.json:288`, which P10 measured as safe.
R13's bump to `0.3.0` matches what `deployments/applications/justfile:54` and
`:89` grep out of `services.tf`. R18's two `cluster` tests are updated to the
grouped payload and renamed, and the module docstring now says plainly that
the gate does not run them.

**Other frontend checks that came back clean.** The delegated listener is
attached to `#groups`, which `refresh()` never replaces (it only rewrites
`innerHTML`), so delegation survives a refresh. `.card-open` is an empty
button, so `event.target` is the button itself. `Element.closest` works from an
SVG child, which is what makes the corner-anchor case (F2's good half) behave.
`sortTiles` and the three fixed grid ids are gone with no dangling reference,
and `.connect-card` is removed from both the CSS and the JS. `dialog.connect-modal`
sets no `display`, so `showModal()` is unaffected. `s.icon` is still injected
unescaped in both the card chip and `modal-icon`, exactly as before this diff —
operator-authored config, pre-existing, not a regression. `.section:last-of-type`
now actually matches (the sections are `#groups`' only div children), which
trims the last group's bottom margin; cosmetic, harmless.

## Required before this can land

1. Make `#modal-fe` actually hide (F1).
2. Make the corner icon on a connect-only tile open the panel (F2).
3. Delete `all_tiles` (F3).
4. Note F4 for the operator; amend through `loopctl eval-amend` next time.

Findings ledger for the next cycle:
`.loop/scratch/L6-landing-dash-service-groups.adversarial/findings.json`.
