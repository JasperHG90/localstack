---
verdict: pass-with-required-fixes
tree: aaca078cdd39b0c662c62978a79e81dd594c0e74
---

# Documentation pass, cycle 2 — L5-landing-registry-tab

Scope binding omitted deliberately, as in cycle 1. The briefing carried a
tree fingerprint but no 64-hex scope digest and no
`verdict_binding_inputs`. A digest computed here would be one I was not
given, which the contract forbids, so this verdict falls back to
whole-tree binding, which is stricter.

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
`deployments/applications/services/dash/backend/tests/test_cluster.py`,
`deployments/applications/services/dash/backend/tests/test_main.py`,
`deployments/applications/services/dash/backend/tests/test_registry.py`,
`deployments/applications/services/dash/backend/tests/test_registry_client.py`,
`deployments/applications/services/dash/backend/tests/test_registry_store.py`,
`deployments/applications/services/dash/backend/tests/test_registry_sweep.py`,
`deployments/applications/services/dash/frontend/index.html`,
`deployments/infrastructure/services.tf`,
`deployments/infrastructure/services/oauth2-proxy.hcl`,
`docs/dash-landing-page.md`, `scripts/check_oauth2_proxy_guard.py`.

## Verdict

**pass-with-required-fixes.** Six of the seven cycle-1 findings are
closed, and DOC-2 is closed by a code change with a test behind it rather
than by a doc edit. Two narrow gaps remain in the one doc the ticket
names, both against enumerated ticket requirements, both a sentence each
to fix. Nothing else in the diff strands a doc.

Gates were not re-run: `.loop/stamp.json` records `just pre_commit` at
exit 0 against this exact tree fingerprint, and `loopctl verify
--expect-tree aaca078c…` returned `ok`. No trust stamp was needed. I did
run one bounded ad-hoc check, `uv run pytest tests/test_registry_sweep.py
-q` (11 passed, 0.16 s), because DOC-2's numbers rest on it.

## Required fixes

### DOC-4 (residual) — the cost formula is wrong for two of the three
### digest kinds the code handles. Severity: medium.

`docs/dash-landing-page.md:46-47` states one cost for every digest:

    tag list per repository, one conditional `HEAD` per tag, then per distinct
    digest one manifest and its two small blobs: `1 + R + T + 3D`, which is 25

The code has three costs, and this diff's own tests prove all three. A
ModelKit digest costs a manifest plus two blobs
(`test_registry_sweep.py:171-172` asserts exactly that shape). A plain
image digest costs a manifest plus **one** config blob
(`test_registry_sweep.py:236` mocks the single `sha256:imgcfg` fetch). A
manifest index costs a manifest and **no** blob
(`test_registry_sweep.py:266` = `assert blob_calls() == []`).

`3D` is right for today's catalog, which is four ModelKit repos, so the
25 and the 13 are both correct as written and I confirmed them. The
problem is that the doc hands the reader a general rule two lines after
promising the catalog will not stay that way:
`docs/dash-landing-page.md:38` = "split is decided per repository by the
manifest's `artifactType`, so an" (image pushed tomorrow appears without
a config change). The day that promise comes true, the formula
overstates.

This is also the one item of Requirement 22 still unbuilt.
`.loop/plans/L5-landing-registry-tab.md:1069-1070` requires the doc cover
"why an image row costs one config blob and a multi-arch row costs none".
`grep -ni 'multi-arch\|config blob' docs/dash-landing-page.md` returns
nothing. The cycle-1 DOC-4 list held six items; five landed and this one
was dropped without being answered.

Fix: one sentence after `:49` giving the per-kind blob count, and a
qualifier on `3D` naming it the all-ModelKit case.

### DOC-5 (residual) — half the webhook caveat is still only in the
### script. Severity: low.

`docs/dash-landing-page.md:105-106` now carries the part about cost:

    push on every registry write; it needs an inbound route on dash and its
    own shared secret, which is why it is not here. And **if `dash` ever runs

That is real progress, and the `count > 1` half of Decision 6 is now
there in full. The missing half is the safety rule.
`.loop/plans/L5-landing-registry-tab.md:1220-1227` states it: an inbound
POST carries no browser session, so taking the hatch needs exactly the
exemption forbidden above, and if it is ever taken the exemption must be
scoped to that one webhook path, carry its own shared-secret check, and
never widen to `/api/*` or to the registry view.

The section that states the rule this caveat qualifies carries none of
it. `docs/dash-landing-page.md:115-116`:

    guarded because the jobspec sets no skip-auth key at all, and
    `scripts/check_oauth2_proxy_guard.py` runs as a pre-commit hook to keep it

The "never widen to `/api/*` or to the view" bound still lives only where
cycle 1 found it, in the guard's stderr:
`scripts/check_oauth2_proxy_guard.py:69` = `"path, scope the exemption to
that one path with its own shared "`. A reader is not misled today, since
nothing in the doc is false. But the reader who later wants the webhook
learns the bound only by tripping a pre-commit hook, which is what §7's
EDIT list routed into the doc to prevent.

Fix: one sentence appended to the "Reaching it" paragraph.

## Confirmed closed

**DOC-1 (was high).** `docs/dash-landing-page.md:168-178` now says two
same-origin calls and "one path-scoped upstream per API route", and
`:113` says "a third `OAUTH2_PROXY_UPSTREAMS` entry". The
self-contradiction is gone. Verified against
`deployments/applications/services/dash/frontend/index.html:979` = `const
response = await fetch('/api/registry' + (force ? '?refresh=1' : ''), {
cache: 'no-store' });` and `:709` (the `/api/status` fetch), and against
`deployments/infrastructure/services/oauth2-proxy.hcl:68` =
`OAUTH2_PROXY_UPSTREAMS="${dash_frontend_upstream},${dash_backend_upstream},${dash_registry_upstream}"`,
three interpolations. The new trailing-slash sentence at `:177-178`
matches the ticket's Q8 probe ("/api/registry/ to FRONTEND") and both
call sites use the bare path.

One clarity nit, not a required fix: `:173-174` reads "plus one
path-scoped upstream per API route, both pointed at the backend task's
loopback port (8001)". The nearest plural antecedent for "both" is the
catch-all plus the path-scoped one, which would put the catch-all on 8001
and be wrong. `deployments/infrastructure/services.tf:533-537` shows the
catch-all on 8000 and the two API routes on 8001, so the intended reading
is the two API upstreams. Worth disambiguating if the doc is touched
anyway.

**DOC-2 (was medium) — closed by a code change, and I confirmed the code
change is real.** `_entry` now consults the store before any manifest
fetch:
`deployments/applications/services/dash/backend/src/dash_app/registry_client.py:292`
= `cached = await self.store.aget_card(digest)`, with the manifest GET at
`:301` sitting after the early return at `:293`. The store holds one
entry per digest including its layers:
`deployments/applications/services/dash/backend/src/dash_app/registry_store.py:47`
= `entry_json TEXT,`.

Both doc numbers check out. Cold `1 + R + T + 3D`:
`test_registry_sweep.py:171` asserts three manifest-URL requests ("two tag
HEADs plus one manifest GET") and `:172` asserts two blobs, so 1 + 1 + 2 +
3 = 7 on the one-repo/two-tag/one-digest fixture, exactly the formula.
Warm `1 + R + T`:
`test_a_warm_sweep_fetches_no_manifest_and_no_blob` asserts both the empty
blob list and an empty manifest-GET list. Against today's catalog, ticket
Q8/Q2 record four ModelKit repos and eight tags collapsing onto four
digests, giving 1 + 4 + 8 + 12 = 25 cold and 1 + 4 + 8 = 13 warm. The doc
is right on both, and the `HEAD` paragraph at `:53-55` correctly explains
what separates them. The suite passes 11/11.

**DOC-3 (was low).** `docs/dash-landing-page.md:67-68` now reads "while
the browser tab is visible (`document.visibilityState`)". Matches
`index.html:996` = `if (document.visibilityState === 'visible')
refreshRegistry(false);` on a 60000 ms interval (`:740`, `:994`), with the
15 s `/api/status` loop separate at `:999`.

**DOC-6 (was low).** `docs/dash-landing-page.md:12` = "and a `backend`
task (status computation and the registry view). The backend carries its
own". Matches `main.py`'s new `/api/registry` route.

**DOC-4, five of six.** `markdown-it-py` and why the render is
server-side at `:78-81` (matches `registry.py:29-34`); the eight-way bound
and why eight at `:83-86` (matches `registry_client.py:42`, `:67`, `:244`);
`asyncio.to_thread` plus connection-per-call and that both failures land
on `/api/status` at `:88-92` (matches `registry_store.py:54-56`, `:60`,
and its header block); what `If-None-Match` does not buy at `:94-95`,
including the 147 ms / 181 ms figures, which are the ticket's real Q12
measurement; the scaling ceiling at `:97-101` and both escape hatches at
`:103-109`, including Decision 6's `count > 1` trigger. Every backticked
identifier in the new section resolves, and the numbers trace to ticket
§9's table rather than being invented.

**Prose (was DOC-7, advisory).** Now at target. Three em-dashes in 1378
words is 2.2 per 1000, and one of the three (`:189`) predates this diff.
No ` -- `, no smart quotes, no tier-1 slop, no British spellings, no
self-narration, no throat-clearing. Both code nits are fixed: no ` - ` as
punctuation anywhere in `registry_store.py`, and no "materialised" in any
new source (`registry_client.py:92` reads "materialized").

Two low-confidence residues, surfaced for a human rather than auto-fixed,
per the rules' own guidance on this category. One prose semicolon splice
at `docs/dash-landing-page.md:105` = "push on every registry write; it
needs an inbound route on dash and its" — two independent clauses. And
three bare-trailing contrastive negations at `:94`, `:113`, `:176`, of
which `:176` is largely inherited from the pre-diff sentence. Neither
blocks.

## New, cycle 2

**DOC-9, advisory.** The DOC-6 fix appended to `:12` without re-wrapping.
`awk 'length>80'` over the file returns exactly one hit, that line, at 92
columns; every other line is at or under 80.
`.claude/rules/slop-scan-for-docs.md` Layer 2 item 1 requires the 80-char
wrap. No hook enforces it, so this is style, not a gate failure. Worth
folding into whichever edit fixes DOC-4 and DOC-5.

## Swept and clean

**The new schema strands no doc.** No doc anywhere names the `cards`
table's columns, so `kitfile_json`/`card_html` becoming `entry_json`
leaves nothing stale. `docs/dash-landing-page.md:60` says only "A `cards`
row is keyed by a manifest digest", which is still true against
`registry_store.py:45-50`. The `_remember` helper is internal and owes no
doc.

**The version bump needs no doc edit, and no release doc should be
invented for it.** `deployments/applications/services.tf:389` =
`dash_frontend_version = "0.3.0"` and `:390` the same for the backend.
`docs/dash-landing-page.md:155-159` cites `<dash_backend_version>` as a
placeholder and tells the reader to bump `services.tf` before rebuilding
rather than quoting a number, so it is already correct. I searched
`docs/` and `README.md` for any pinned dash version and found none, and
the repo carries no release, changelog, or deployment-record doc. There
is nothing here to update and nothing here to create.

**DOC-8 — no change in scope, still holds.** I re-opened the anchor
rather than trusting cycle 1. `docs/vault-human-auth.md:96-99` is a
"Measured:" observation introduced by "include", so the new `dash_data`
volume is not owed an entry there.
`docs/haproxy_reverse_proxy.md:24`, `:28` still correctly place dash
behind oauth2-proxy on 4180, which the new route does not change. No
repo-wide host-volume, Vault-path, scripts, or pre-commit-hook inventory
doc exists, so the new `dash_data` volume, the new
`default/dash/registry` KV path
(`deployments/applications/secrets.tf:104-112`), the new
`scripts/check_oauth2_proxy_guard.py`, and its three new hooks strand
nothing. Do not invent an inventory doc the repo never had.

## Note for another pass, not a doc finding

The shipped schema `cards(digest, entry_json, fetched_at)`
(`registry_store.py:45-50`) diverges from Requirement 23's enumerated
`cards(digest PK, kitfile_json, card_html, fetched_at)`
(`.loop/plans/L5-landing-registry-tab.md:1080`, restated at `:322`). The
change is well-motivated and the docstring at `:79-83` records why. It is
a contract deviation the adversarial or architectural pass should rule
on, and I raise it only so it is not lost between passes. It has no doc
consequence, since no doc names the columns.
