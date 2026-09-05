---
verdict: pass-with-required-fixes
tree: d45829a41796e91fe032eecc4642aef015363b37
---

# Documentation pass, cycle 3 (final) - L5-landing-registry-tab

Scope binding omitted deliberately, as in cycles 1 and 2. The briefing
carried a tree fingerprint but no 64-hex scope digest and no
`verdict_binding_inputs`. A digest computed here would be one I was not
given, which the contract forbids, so this verdict falls back to
whole-tree binding, which is stricter. No path in this change is deleted,
so nothing is left unbound by the fallback.

`loopctl verify --expect-tree d45829a41796e91fe032eecc4642aef015363b37`
returned `ok` before any review work.

Paths reviewed (the full path set of the change, not only the anchors
cited below): `.pre-commit-config.yaml`,
`deployments/applications/secrets.tf`,
`deployments/applications/services.tf`,
`deployments/applications/services/dash.hcl`,
`deployments/applications/services/dash/backend/pyproject.toml`,
`deployments/applications/services/dash/backend/uv.lock`,
`deployments/applications/services/dash/backend/src/dash_app/config.py`,
`deployments/applications/services/dash/backend/src/dash_app/main.py`,
`deployments/applications/services/dash/backend/src/dash_app/registry.py`,
`deployments/applications/services/dash/backend/src/dash_app/registry_client.py`,
`deployments/applications/services/dash/backend/src/dash_app/registry_store.py`,
`deployments/applications/services/dash/backend/tests/test_cluster.py`,
`deployments/applications/services/dash/backend/tests/test_main.py`,
`deployments/applications/services/dash/backend/tests/test_registry.py`,
`deployments/applications/services/dash/backend/tests/test_registry_client.py`,
`deployments/applications/services/dash/backend/tests/test_registry_store.py`,
`deployments/applications/services/dash/backend/tests/test_registry_sweep.py`,
`deployments/applications/services/dash/frontend/index.html`,
`deployments/infrastructure/services.tf`,
`deployments/infrastructure/services/oauth2-proxy.hcl`,
`docs/dash-landing-page.md`, `scripts/check_oauth2_proxy_guard.py`,
`.loop/ledger.json`.

## Verdict

**pass-with-required-fixes.** `docs/dash-landing-page.md` now matches the
code on every claim I checked, and the two new operator-facing footnotes
in `index.html` match it too. Both cycle-2 residuals and the advisory are
closed. One gap remains and it is narrow: the `###` comment block that
documents `OAUTH2_PROXY_UPSTREAMS` still describes the two-upstream world
and the single fetch, in the same file whose upstream line this diff
changed, and `docs/dash-landing-page.md` sends the reader to that file by
name. One comment block, no re-review needed.

## Required fix

### DOC-12, medium: the jobspec comment above the line the diff changed

`deployments/infrastructure/services/oauth2-proxy.hcl:46-57` is stale in
two ways, both created by this diff.

    deployments/infrastructure/services/oauth2-proxy.hcl:46 = ### OAUTH2_PROXY_UPSTREAMS below carries two upstreams for dash's
    deployments/infrastructure/services/oauth2-proxy.hcl:47 = ### frontend/backend split (L4): a catch-all to the frontend's
    deployments/infrastructure/services/oauth2-proxy.hcl:54 = ### "/"). `index.html`'s one fetch call is an exact, unparameterized
    deployments/infrastructure/services/oauth2-proxy.hcl:68 = OAUTH2_PROXY_UPSTREAMS="${dash_frontend_upstream},${dash_backend_upstream},${dash_registry_upstream}"

1. `:46-49` says the variable "carries two upstreams", a catch-all and a
   path-scoped one to `/api/status`. Line `:68`, eleven lines below it,
   now interpolates three. `deployments/infrastructure/services.tf:535-537`
   adds the third.
2. `:54-55` says "`index.html`'s one fetch call is an exact,
   unparameterized `/api/status`", and that premise is what the whole
   comment rests on. `index.html` now makes two fetches, and the registry
   one is parameterized when the refresh button fires:

    deployments/applications/services/dash/frontend/index.html:992 = const response = await fetch('/api/registry' + (force ? '?refresh=1' : ''), { cache: 'no-store' });

The routing itself is correct. The plan's P11 probe recorded
`/api/registry?tab=models` reaching the registry upstream, so a query
string still matches an exact path mapping. The defect is the prose, not
the config: a reader reasoning from `:54` would conclude the refresh
button is unrouted, or would not know.

This matters here rather than being a stray comment nit because
`docs/dash-landing-page.md:184-186` names this file and this variable and
points the reader at it, and because the reader the doc points there is
the one adding a fourth upstream.

What the comment must now say: three upstreams, not two; that `index.html`
makes two fetches, both on bare paths; and that a query string still
matches while a trailing slash does not, which is the part `:54`'s
"unparameterized" claim used to cover and no longer does.

Cost check, so nobody skips this on the wrong grounds: the
`one-file-per-subsystem` rule warns that editing a comment inside a
jobspec re-registers the job, because `templatefile` folds the whole file
into `nomad_job.jobspec`. That cost is already paid. Line `:68` changed
in this same diff, so the jobspec hash has already moved and the job
re-registers on this apply whether or not the comment is touched. Fixing
it adds nothing.

Incidental, not required: `:55` ends with ` -- ` in prose, which the
slop-scan rule flags. It is pre-existing. If the block is being rewritten
anyway, it costs nothing to drop.

## Closed since cycle 2

### DOC-4, was partially-resolved, now resolved

Requirement 22's last item landed at `docs/dash-landing-page.md:52-59`. I
verified each of the three costs against the code and the tests rather
than against the summary I was handed, and all three hold.

    docs/dash-landing-page.md:52 = `B` is the blob count, and it differs by what the digest holds. A ModelKit
    docs/dash-landing-page.md:53 = costs two, a Kitfile and a `README.md`. A container image costs one, its

- ModelKit, two blobs. `registry_client.py:312-314` reads the Kitfile
  from `manifest.config.digest`; `:316-319` reads the one docs layer.
  `test_registry_sweep.py:160` asserts `len(blob_calls()) == 2` with the
  comment "one Kitfile and one README, not one pair per tag", and `:172`
  asserts it again inside the cold-cost test.
- Container image, one blob. `registry_client.py:303-308` takes the
  non-ModelKit branch, fetches only `manifest.config.digest`, and touches
  no layer.

        deployments/applications/services/dash/backend/src/dash_app/registry_client.py:307 = config = await self.client.get_config_json(repo, config_ref, http)

  The doc's "where the architecture and build date live" is exact:
  `registry.py:134` reads `config.get("architecture")` and `:136` reads
  `config.get("created")`. `test_registry_sweep.py:246` confirms
  `arch == "arm64"` reaches the row. Note the doc does not claim size
  comes from that blob, and it should not: `registry.py:129` sums the
  manifest's layer sizes.
- Multi-arch index, no blob. An index carries no `config` key, so
  `config_ref` at `registry_client.py:305-306` is None and the branch
  never fires. `registry.py:119-128` then returns `arch: None`,
  `size: None`, `multi_arch: True`.

        docs/dash-landing-page.md:55 = multi-arch tag resolves to an index, which carries no config and no layers,
        docs/dash-landing-page.md:56 = so it costs none and its row shows no architecture and no size rather than
        deployments/applications/services/dash/backend/tests/test_registry_sweep.py:269 = assert blob_calls() == []

The totals hold too. The plan's Q2 and its measured line record `R=4 T=8
D=4` with two blobs per digest, so cold is `1 + 4 + 8 + 4 + 8 = 25` and
warm is `1 + 4 + 8 = 13`, exactly as `docs/dash-landing-page.md:48-50`
states. `test_registry_sweep.py:169-172` proves the same shape at one
repo, two tags, one digest: 1 catalog, 1 tag list, 3 manifest URLs, 2
blobs, which is 7 and matches `1 + R + T + D + B`.

    deployments/applications/services/dash/backend/tests/test_registry_sweep.py:171 = assert sum("/manifests/" in u for u in urls) == 3, "two tag HEADs plus one manifest GET"

One nit I am not raising as a finding: "A ModelKit costs two" is the
common case. A kit packed without a docs layer costs one, and the doc
already says so at `:42-44`, two paragraphs above.

### DOC-5, was partially-resolved, now resolved

`docs/dash-landing-page.md:113-118` now carries the whole hazard, and it
matches the guard's own message.

    docs/dash-landing-page.md:114 = shared secret, and that is the awkward part: a POST from the registry
    docs/dash-landing-page.md:118 = own shared secret. It must never widen to `/api/*` or to the view itself.
    scripts/check_oauth2_proxy_guard.py:69 = "path, scope the exemption to that one path with its own shared "

All three parts Requirement 27 asks for are present: no browser session on
an inbound POST, so the route needs exactly the exemption the guard
refuses; name the one path and check its own shared secret; never widen to
`/api/*` or the view.

### DOC-9, was open, now resolved

`awk 'length>80'` over `docs/dash-landing-page.md` returns nothing. The
DOC-6 sentence is re-wrapped across `:11-13`.

### DOC-7 residue, now clear

The cycle-2 semicolon splice is rewritten into `:113-114`. A splice scan
with fenced and inline code stripped returns nothing. 3 em-dashes in 1503
words is 2.0 per 1000, at the target ceiling, and `:203` is pre-existing.
No ` -- `, no smart quotes, no tier-1 slop, no British spellings.

## New and clean

### DOC-11, the two panel footnotes: accurate, and no formula shipped

    deployments/applications/services/dash/frontend/index.html:558 = Nothing here touches the weights. A cold walk reads the catalog, one tag list per
    deployments/applications/services/dash/frontend/index.html:568 = An image row costs one blob where a ModelKit row costs two: its config blob carries

The models footnote at `:557-563` states cold and warm in words with no
count, so the mockup's wrong `1 + R + T + 2D` and its 21 did not ship.
Every clause checks out: the cold order matches `registry_client.py:251-268`
and `:301-319`; "a warm one reads only the first three" matches
`test_registry_sweep.py:176-196`, which asserts no blob and no manifest
GET; "both tags of every repo resolve to one digest" matches
`registry.py:54-56` and `test_registry_sweep.py:154-160`.

The images footnote at `:567-572` is right on all three counts, and the
last clause is more literal than it looks: "shows its digest and nothing
invented" holds because the table really does draw a digest column
(`index.html:852`, `:861`) and renders an em-dash for size and pushed on a
multi-arch row (`:863-864`), with `multi-arch` in the arch cell rather
than a guessed architecture (`:862`).

Neither footnote contradicts `docs/dash-landing-page.md:52-59`. Prose: no
em-dashes, no ` -- `, no splice, no tier-1 slop, no self-narration. "An
image row costs one blob where a ModelKit row costs two" is a contrast,
but it carries two real numbers and both halves are load-bearing, so it
stays.

## The deviation you flagged: not blocking, but record it

### DOC-13, advisory

You are right that the plan and the eval are wrong and the doc is right.
`.loop/evals/L5-landing-registry-tab.md:20` still requires "exactly
`1 + R + T + B` registry-path requests", and the plan repeats 21 at
`:292-294`, `:802-803` and `:3169-3170`. The formula omits the manifest
GET, which no correct implementation can skip: the Kitfile and README blob
digests are only readable from the manifest. `test_registry_sweep.py:169-172`
settles it at one repo, two tags, one digest, where the shipped walk costs
7 and the plan's formula predicts 6.

This does not block the documentation pass. `.loop/plans` and `.loop/evals`
are harness artifacts, not the repo's documentation set, and no reader
following `docs/` is misled by them. It should also not be hand-edited:
the marker is signed, `eval-amend` refuses inside a linked worktree, and
forging a signed row to make an artifact agree is worse than a recorded
disagreement.

Carry it to the integrator as a follow-up: run `loopctl eval-amend` from
the primary worktree to correct that guardrail row to `1 + R + T + D + B`.
Leaving it silent is the only bad option, because it hands a later scorer
a pass criterion the shipped test contradicts.

## Re-attacked and still settled

- **DOC-1.** Two fetches at `index.html:722` and `:992`; three upstreams
  at `oauth2-proxy.hcl:68`. The doc at `:184-193` is right. Re-reading
  this anchor is what turned up DOC-12 eleven lines above the line cycle 2
  cited.
- **DOC-2.** Verified again under DOC-4 above.
- **DOC-3.** `index.html:753` sets `REGISTRY_POLL_MS = 60000`, `:1009`
  gates on `document.visibilityState === 'visible'`, `:1012` runs the
  separate 15 s status loop. `docs/dash-landing-page.md:74-78` matches.
- **DOC-6.** `main.py:110-111` registers both routes.
  `docs/dash-landing-page.md:11-13` matches.
- **DOC-8, extended.** I swept the new surfaces this cycle created, not
  just last cycle's. No doc holds a repo-wide host-volume inventory:
  `docs/monitoring.md:405-407` lists volumes scoped to that rollout's own
  `services.tf` section, so `dash_data` owes it nothing.
  `docs/credential-rotation.md` never mentions the registry, and a
  repo-wide search for `registry_push`, `default/registry/auth`,
  `embark_registry` and `registry.lab.orangecluster` across `docs/`,
  `README.md`, `ROADMAP.md` and embark's own directory returns only
  `docs/dash-landing-page.md`, so the new `default/dash/registry`
  credential drifts nothing. No doc enumerates pre-commit hooks;
  `ROADMAP.md:21` says "All 14 hooks pass" inside a historical D1 status
  row, which the anti-goals say to leave alone. `ROADMAP.md` has no
  landing-epic or dash row at all.
- **DOC-10.** No doc names the `cards` columns, and
  `docs/dash-landing-page.md:68` still only says "keyed by a manifest
  digest", which `registry_store.py` still satisfies. No doc pins an image
  version, so `0.2.0` to `0.3.0` at `services.tf:389-390` needs no edit.

## Also re-verified in the doc, all matching

`1 MiB` cap against `MAX_BLOB_BYTES = 1_048_576` and the 128 MB
reservation against `dash.hcl:165`, which is inside `task "backend"`
starting at `:55`. `/var/lib/dash/registry.db` against `dash.hcl:90`.
Eight-way against `registry_client.py:42`, `:67` and `:244`.
`asyncio.to_thread` and connection-per-call against `registry_store.py:56`
and `:67`. `markdown-it-py` against `pyproject.toml:8`. The 147 ms against
181 ms figure against the plan's Q12 probe. The 25 / 50 / 100 scaling
ceiling against the plan's own table.
