---
verdict: pass
tree: 35683c0103cf5c6f71feaaa9a52f288b730bfb2e
---

# Adversarial review, cycle 2 — L6-landing-dash-service-groups

All four cycle-1 findings are fixed at the defect, not moved. Ten mutations
on this tree confirm the guardrails still bite. The gate is green. Nothing
left is above info severity.

## Scope binding

Written without the `bound_paths:` / `scope:` / `citations:` lines, so this
verdict falls back to whole-tree binding. My briefing carried the tree
fingerprint but no scope digest, and a digest I computed for a path set I
chose myself is not the one the gate would compare against. The fallback is
stricter, so the omission is safe.

## Deterministic floor

`loopctl verify-eval-substance L6-landing-dash-service-groups` returns
`valid`, exit 0, with zero advisories. No hard-fail, no warn line, so no
plan-drift instruction to act on. Proceeded to the semantic pass.

## Gate, re-run independently

The cycle-1 trust stamp was keyed to tree `cf395cc7...`, which is not this
cycle's fingerprint, so per the reviewer brief I re-ran rather than trusted
it. `just pre_commit`: 28 hooks, every one `Passed`, exit 0. Stamp rewritten
for `35683c01...` at
`.loop/scratch/L6-landing-dash-service-groups.adversarial/trust-stamp.json`.

## Cycle-1 findings, re-attacked

**F1 — FIXED (was high).** `index.html:73` now carries
`[hidden] { display: none !important; }`. This defeats the author `display`
because an important author declaration outranks any normal author
declaration regardless of specificity, and `.fe-button`'s
`display: flex` (`index.html:318-319`) is normal author. Checked both
toggled elements and the blast radius you asked about: exactly two elements
in the page carry the `hidden` attribute, `index.html:483`
(`<div id="modal-connect" hidden>`) and `index.html:493`
(`<a class="fe-button" id="modal-fe" hidden ...>`). The only other grep hit
is `aria-hidden="true"` at `index.html:436`, which the `[hidden]` selector
does not match: it selects the attribute named `hidden`, not one whose name
ends in it. So no element in the page relies on being `hidden` yet
displayed, and the `!important` reaches nothing else. The stale-content
concern is closed too: when `#modal-fe` is hidden it keeps the previous
tile's `href` and text, but `display: none` takes it out of the tab order
and out of the accessibility tree, so it is neither clickable nor
announced.

**F2 — FIXED (was medium).** The lift is now scoped to the anchor:
`index.html:230` is `.card-corner { display: flex; line-height: 0; }` and
`index.html:231` is `a.card-corner { position: relative; z-index: 1; }`.
You asked me to check the paint-order claim rather than take it from you, so:
`.card-open` is `position: absolute` with `z-index: auto`, which places it
in the positioned-descendants step of the painting order, above the in-flow
non-positioned content of `.card`. `span.card-corner` is now statically
positioned and sits inside `.card-top`, which is also non-positioned, so it
paints in that earlier step, underneath. Hit testing follows paint order, so
a click on the span lands on the button; `background: none` does not opt out
of hit testing, only `pointer-events: none` would, and there is no such rule
in the file. The delegated listener at `index.html:589`
(`const opener = event.target.closest('.card-open');`) then gets the button
as `event.target` and opens the panel.

Row 4 did not regress. `a.card-corner` has a positive `z-index`, so it forms
a stacking context painted after the positioned-descendants step, above the
button. A click there hits the anchor; `closest('.card-open')` walks
anchor to `.card-top` to `.card` and matches nothing, returns null, the
handler returns early, and the anchor's own `target="_blank"` navigation
runs. New tab, no panel behind it.

**F3 — FIXED (was low).** `all_tiles` is gone from `tiles.py`. A repo-wide
grep now returns only review artifacts: the cycle-1 verdict and the findings
ledger. No source, no test. Gate green after the removal, so nothing
depended on it.

**F4 — FIXED (was low).** Confirmed as you asked. `git diff HEAD --
.loop/evals/` is empty and `git diff HEAD --name-only -- .loop/evals/`
returns zero paths, so the marker is byte-identical to what was signed.
Reverting rather than amending was the right call: `eval-amend` refuses
inside a linked worktree by design.

**O1 — RESOLVED (was info).** The `build_routes` docstring now reads
`De-duplicated by name, because two tiles may name the same job.`
(`status.py:132`). That is a claim about what the schema permits, not about
observed behavior, so it no longer overclaims. I confirmed the shipped
config has no job named by two tiles, so the dedupe is defensive; keeping it
is right, because the schema allows the collision even though today's file
does not contain one.

**O2 — no change in scope, still holds.** `JobState.checks` is written at
`status.py:165` and read nowhere. Carried over from the old unread
`TileState.checks`, so CLAUDE.md section 3 says leave it. Info only.

**O3 — no change in scope, still holds.** The eval was reverted to the
signed text, so row 6 is byte-identical to cycle 1. Its named scorer is
still narrower than its Expected column, and the coverage is still complete
across three tests. A wording issue in the eval, not a coverage gap.

## New this cycle

**F5 — INFO. The eval's `TODO.md:6` citation now dangles.** Confirmed, and
I agree with your read that this is eval quality for the operator rather
than a blocker. Row 2's substance is unaffected and is met: the shipped
`openviking` tile carries both an `fe` and a `connect`, and there is no
`openviking-api` tile. The citation was true when the marker was signed, and
it records the ticket's own trigger. `verify-eval-substance` is structurally
blind to it: it checks `depends_on`, grep scorers, dropped amendment fields
and empty `Fails-when` cells, not prose citations. Not fixable from inside
the worktree; leaving it to the operator is correct.

**N1 — INFO. Redundant width.** `.card-open` declares both `inset: 0`
(`index.html:216`) and `width: 100%` (`index.html:217`). With `left` and
`right` both zero, a non-auto width over-constrains the box and `right` is
dropped. The containing block is `.card`'s padding box and the button has
`box-sizing: border-box` with no border and no padding, so the computed
width is identical either way. Cosmetic.

**N2 — INFO. New byte class in tiles.json.** Three non-ASCII em dashes
enter at `tiles.json:175`, `:177` and `:321`, where the old file had zero
non-ASCII bytes. Terraform's `jsonencode` leaves valid UTF-8 as-is and the
Nomad heredoc carries it, and `check-json` plus `terraform validate` both
pass, so this is not a correctness risk. Worth naming only because the last
rendering layer, `terraform apply` into the jobspec parser, is the one layer
no gate reaches. Eval row 9 is where it gets exercised.

## What I verified rather than assumed

**Mutations, on this tree.** I copied `src` and `tests` into
`.loop/scratch/` and ran the backend's own venv against them. Baseline
71 passed, 2 deselected. Each mutation below was caught:

| Mutation | Tests turned red |
|---|---|
| `_tile_json` drops `status` (eval row 8's own Fails-when) | 3 |
| `worst` returns the first status instead of the worst | 8 |
| `_tile_state` picks the first job as deciding, not the worst | 2 |
| `_group_json` reverses tile order within a group | 2 |
| payload reverses group order | 2 |
| `compute_tile_states` reverses tiles within a group | 3 |
| `_tile_json` always emits an `fe` key | 1 |
| `%{ if true }X%{ endif }` in a tile `desc` (eval row 7) | 1 |
| `${"x"}` in a tile `desc` (eval row 7) | 1 |
| `prometheus` removed from `tiles.json` (eval row 5) | 2 |

One mutation survived and I discarded it as a no-op rather than a gap:
sorting a group's tiles by key. The fixture's config order is already
alphabetical, so that mutation changes no observable output. Reversing the
order, which does, is caught at all three layers above.

**Error-message literals.** No test asserts on any `TileConfigError`
message text, so a green gate says nothing about them. I ran all 17 through
the real call path with `PYTHONDONTWRITEBYTECODE=1`, so nothing was written
into the tree. Every one raises `TileConfigError` and names the tile or
group, the block and the field, for example
`tile 'a' 'connect' is missing required field 'example'` and
`group 'g' needs a non-empty 'tiles' array`. Two read a little awkwardly
where `_require`'s `where` string is composed, but all are correct and
diagnostic. Also confirmed at runtime that `fe` defaults its label to
`open` and that `"fe": null` is treated as absent rather than malformed.

**Config against the ticket.** The shipped `tiles.json` parses to exactly
six groups in the order `platform, storage, telemetry, events, agentic,
artifacts`, with all six titles and all six hints matching R2's table
verbatim, and exactly the fifteen keys eval row 5 names, with `platform`
reading `nomad, consul, vault`. `memex`, `openviking-api` and `registry-ui`
are all absent as tile keys, `registry` names both of its jobs on the two
nodes R9 specifies, and `openviking` carries both blocks.

**Panel order.** R5 asks for name and desc, then per-job rows, then
`connect`, then the frontend button. The dialog's DOM order is exactly that:
`modal-head`, then `#modal-jobs` (`:482`), `#modal-connect` (`:483`),
`#modal-fe` (`:493`).

**Scope.** The diff touches thirteen files, and all thirteen appear in the
plan's section 7 code-surface table. The fourteenth path, `.loop/ledger.json`,
is harness bookkeeping (stage, attempts, review cycles, entry tree), not a
code change. No file outside the declared surface, and no stray edit inside
one that I could not trace to a requirement.

**Guardrail premise.** I checked the `${` / `%{` ban is real rather than
folklore. `services.tf:589` builds the config through
`jsonencode(jsondecode(file(...)))` and `dash.hcl` splices it into a
`<<-EOH` heredoc, whose body Nomad's own HCL2 parser scans for template
openers. `templatefile` substitution does not re-scan the substituted value,
so the danger is at the Nomad layer, which is what the comment and the test
say. I also confirmed the file's `\n` escapes are not a new risk: the old
config already shipped one, so heredocs leaving backslash escapes alone is
established by production, not inferred.

## Stated limits

I could not execute the frontend either. No browser and no JS runtime exist
here: `node`, `deno`, `bun` and `qjs` are all absent. Everything above about
`index.html`, F1 and F2 included, is derived from the CSS cascade and
painting-order specs plus the file's own text, not from a run. The four
human-scored eval rows and row 9 remain genuinely unscored by me, as the
eval itself warns. A green `just pre_commit` is not that eval passing.

I re-asserted the tree fingerprint after removing the scratch harness: still
`ok`. My only writes outside this verdict were under
`.loop/scratch/L6-landing-dash-service-groups.adversarial/`.
