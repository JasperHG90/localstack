---
verdict: fail
tree: a579f4f96c7f603eed1630da33bcac5965160ea8
---

# Documentation pass — L5-landing-registry-tab

Scope binding omitted deliberately. The briefing carried a tree
fingerprint but no 64-hex scope digest and no `verdict_binding_inputs`,
and a digest computed here would be one I was not given. Per the
reviewer contract this verdict falls back to whole-tree binding, which
is stricter.

## Verdict

**fail.** The diff changes a behavior `docs/dash-landing-page.md`
already describes and leaves the describing paragraph untouched, and the
new section it does add states a request shape the shipped code does not
have. A reader following the current doc is wrong in three places.

Paths reviewed: `.pre-commit-config.yaml`,
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
`deployments/applications/services/dash/backend/tests/test_main.py`,
`deployments/applications/services/dash/backend/tests/test_registry.py`,
`deployments/applications/services/dash/backend/tests/test_registry_client.py`,
`deployments/applications/services/dash/backend/tests/test_registry_store.py`,
`deployments/applications/services/dash/frontend/index.html`,
`deployments/infrastructure/services.tf`,
`deployments/infrastructure/services/oauth2-proxy.hcl`,
`docs/dash-landing-page.md`,
`scripts/check_oauth2_proxy_guard.py`.

---

## DOC-1 — HIGH — a whole doc section is now false

`docs/dash-landing-page.md` §"How the browser reaches two tasks through
one route" describes the exact contract this ticket changed, and the
diff does not touch it.

Evidence:

    docs/dash-landing-page.md:124 = ## How the browser reaches two tasks through one route
    docs/dash-landing-page.md:126 = `index.html` makes one same-origin call, `fetch('/api/status')`. Since the
    docs/dash-landing-page.md:129 = `OAUTH2_PROXY_UPSTREAMS`): a catch-all upstream to the frontend task's
    docs/dash-landing-page.md:130 = loopback port (8000) and a second upstream scoped to `/api/status`,
    docs/dash-landing-page.md:133 = `/api/status` exactly, not as a prefix, which is exactly what the one
    docs/dash-landing-page.md:134 = fetch call needs.

Against the shipped code:

    deployments/applications/services/dash/frontend/index.html:709 =       const response = await fetch('/api/status', { cache: 'no-store' });
    deployments/applications/services/dash/frontend/index.html:979 =       const response = await fetch('/api/registry' + (force ? '?refresh=1' : ''), { cache: 'no-store' });
    deployments/infrastructure/services/oauth2-proxy.hcl:68 =         OAUTH2_PROXY_UPSTREAMS="${dash_frontend_upstream},${dash_backend_upstream},${dash_registry_upstream}"

Three false claims: "one same-origin call" (two now), the enumeration of
exactly two upstreams (three now), and "the one fetch call" as the
justification for exact-match routing. The new §"Reaching it"
(`:71-72`) asserts the third upstream but does not repair `:126-134`,
so the doc now contradicts itself: `:129-130` says there are two, `:71`
says there are three. Fix the older section rather than leaving the
reader to reconcile them.

## DOC-2 — MEDIUM — the request formula does not match the shipped walk

    docs/dash-landing-page.md:47 = a Kitfile plus a `README.md` — `1 + R + T + 2D`, 21 registry-side requests

The sentence at `:45-49` says the backend reads "one manifest per tag,
and then per distinct digest a Kitfile plus a `README.md`". The shipped
walk does two distinct things:

    deployments/applications/services/dash/backend/src/dash_app/registry_client.py:245 =                 digest, _unchanged = await self.client.head_manifest(repo, tag, known, http)
    deployments/applications/services/dash/backend/src/dash_app/registry_client.py:272 =         manifest, _ = await self.client.get_manifest(repo, digest, http)

`:245` is a `HEAD` per (repo, tag) pair; `:272` is a full manifest `GET`
per distinct (repo, digest) group. The formula omits the second term.
Against today's catalog (R=4, T=8, D=4) the shipped cold walk is
`1 + 4 + 8 + 4 + 8 = 25` registry-side requests, not 21, and the warm
walk is 17, not 13. The doc also calls a `HEAD` "one manifest", which
misdescribes the request the freshness path issues.

The plan's 21 assumed a manifest `GET` per tag with no separate `HEAD`
(`.loop/plans/L5-landing-registry-tab.md:293-299`). The implementation
took a different, cheaper-per-request shape and the doc kept the old
number. Either number may be the right one to ship; the doc has to state
the one the code produces. Note nothing asserts this: no cold-walk
call-count test exists in `tests/test_registry_client.py`, so the doc is
the only place the figure lives and there is no gate on it.

## DOC-3 — LOW — the poll's visibility scope is overstated

    docs/dash-landing-page.md:61 = polls once a minute while the registry section is visible, never on the
    deployments/applications/services/dash/frontend/index.html:996 =     if (document.visibilityState === 'visible') refreshRegistry(false);

The gate is on the whole document's visibility (the browser tab is not
hidden), not on the registry section being scrolled into view and not on
which of the models/images tabs is selected. A reader planning registry
load from this sentence would under-count. The 60 s cadence and the
"never on the 15 s health loop" half are both correct
(`index.html:990`, `:999`).

## DOC-4 — MEDIUM — six topics Requirement 22 puts in this doc are absent

`.loop/plans/L5-landing-registry-tab.md:1062-1074` enumerates what
`docs/dash-landing-page.md` must cover. The shipped section
(`docs/dash-landing-page.md:34-81`) carries the route, the credential,
the third upstream, the store, the sweep, the never-invalidated card
row, the 1 MiB cap, the `embark.json` refusal and the no-skip-auth rule.
Missing:

1. **`markdown-it-py` and why the render is server-side.** `:41-42`
   says a card is "rendered from the kit's `docs` layer" and names
   neither the dependency nor the actor. The new dependency is a
   user-facing fact for anyone rebuilding the image
   (`pyproject.toml` gains `markdown-it-py>=4.2.0`), and the escaping
   posture is the mitigation for a registry README reaching the DOM
   (`registry.py:27-29`).
2. **The eight-way concurrency bound.** Not mentioned anywhere in the
   doc; `registry_client.py:42` sets it and `:16-17` carries the reason.
3. **The scaling ceiling and its two escape hatches**
   (`notifications.endpoints`, Redis). Decision 6
   (`.loop/plans/L5-landing-registry-tab.md:2370-2379`) routes the
   `count > 1` trigger into this doc by name, "so it is discoverable
   from outside this plan". It is not there, so the failure Decision 6
   calls silent stays undiscoverable.
4. **Why an image row costs one config blob and a multi-arch row costs
   none.** `image_row` (`registry.py:106-138`) is the whole reason the
   images tab is affordable; the doc says nothing.
5. **`asyncio.to_thread` and the connection-per-call rule.** The store's
   central constraint (`registry_store.py:7-13`, `:61`) is invisible in
   the doc.
6. **What `If-None-Match` does NOT buy.** `:58-60` states what a `304`
   means but not that it saves time and not a single request, which is
   the half a reader would otherwise get wrong.

## DOC-5 — LOW — the webhook caveat did not land in the doc

Ticket §7 and Requirement 27 route the loosening rule into
`docs/dash-landing-page.md`. It lives only in the guard's stderr:

    scripts/check_oauth2_proxy_guard.py:68 =             "session gate. If a registry webhook ever needs an unauthenticated "

`docs/dash-landing-page.md:71-75` states the prohibition without stating
how it may ever be relaxed, so the one reader who needs it (whoever
takes the `notifications.endpoints` hatch) meets it only after tripping
a hook.

## DOC-6 — LOW — the backend task's job description is now partial

    docs/dash-landing-page.md:11 = The job holds two tasks: a `frontend` task (static files only, no Python)
    docs/dash-landing-page.md:12 = and a `backend` task (status computation). The backend carries its own

The backend now serves `/api/registry` as well. One clause.

Related, and NOT a finding: `:138-141`'s "No `submit-job`, no
`host-volume-*`, no management capability" is still true. That describes
dash's Nomad ACL role, which `machine_roles.tf` does not change; the
`dash_data` mount is a jobspec volume, not a token capability. Leave it.

## DOC-7 — ADVISORY — prose

Mechanical scan of the new section (`docs/dash-landing-page.md:34-81`,
382 words): no British spellings, no smart quotes, no ` -- `, no
semicolon splices, no tier-1 slop, no lines over 80 chars. Two things:

- **Em-dash density.** Two em-dashes (`:47`, `:55`) in 382 words is
  5.2 per 1000, over the 0-2 target and over prevention mode's zero.
  `:55`'s reads better as a colon.
- **Contrastive negation, four times in one section.** `:38-39`
  ("without a config change"), `:48-49` ("not registry metadata"),
  `:61` ("never on the 15 s health loop"), `:71-72` ("not a widening
  of the `/api/status` one"), `:77-78` ("not the registry's own port").
  Each is individually defensible and two are load-bearing, but five
  in 382 words is a tic. Keep `:71-72` and `:77-78`; state `:48-49`
  positively.

Nit, no fix demanded: `:38` says the split is "decided per repository";
`is_modelkit` (`registry.py:45-47`) decides per manifest, so a repo
holding both kinds would split across tabs.

## Code comments — checked, no finding

`.claude/rules/minimal-comments.md` exempts one header block per file,
and every new block earns it by recording something the source cannot:
the `307` trap and the httpx read ordering
(`registry_client.py:8-15`), the shared-connection failure
(`registry_store.py:9-13`), the `artifactType` discriminator
(`registry.py:7-13`). The measurements in those blocks are not bare
prose: `tests/test_registry_store.py` asserts them
(`test_eight_concurrent_writes_all_land`,
`test_the_store_holds_a_path_and_never_a_connection`,
`test_every_public_call_reaches_sqlite_through_the_thread_offload`), and
`tests/test_registry_client.py:137-138` asserts the pool bound and
`follow_redirects`. Two nits, neither blocking: `registry_store.py:12`
uses ` - ` where an em-dash or colon belongs, and
`registry_client.py:92` spells "materialised".

## Swept and clean

No other doc in the repo describes a world this diff removed.
`docs/haproxy_reverse_proxy.md:24-28` (dash at 4180, behind
oauth2-proxy) still holds. `docs/vault-human-auth.md:97-99` lists
attachable host volumes with "include", already non-exhaustive before
this diff (it omits `embark_data` too), so `dash_data`'s absence is not
a falsehood. `docs/monitoring.md:405-407`'s volume list is scoped to
monitoring. `deployments/applications/services/embark/README.md`
describes the registry from a puller's side and is untouched by a
read-only consumer. `README.md:62`'s hook list was already partial
before this diff. `docs/credential-rotation.md` covers Tailscale and
GitHub only, and no repo-wide secrets, host-volume or scripts inventory
exists, so `default/dash/registry`, `dash_data` and
`scripts/check_oauth2_proxy_guard.py` need no home outside
`docs/dash-landing-page.md`. Do not invent one.

## To pass

Fix DOC-1 and DOC-2 (both make the doc state something false), and land
DOC-4's item 3 (Decision 6 names this doc as the discovery surface for a
silent failure). DOC-3, DOC-5, DOC-6 and the rest of DOC-4 are one or
two sentences each and should ride along. DOC-7 is advisory.
