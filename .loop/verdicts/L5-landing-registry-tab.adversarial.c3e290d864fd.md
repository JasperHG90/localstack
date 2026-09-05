---
verdict: pass-with-required-fixes
tree: aaca078cdd39b0c662c62978a79e81dd594c0e74
---

# Adversarial review — L5-landing-registry-tab (cycle 2)

**Scope binding omitted deliberately.** My briefing carried the tree
fingerprint but no 64-hex scope digest, and named no
`verdict_binding_inputs`. `loopctl` exposes no command to mint one, and a
digest I computed myself would cover a path set nobody asked me to bind.
Omitting the three lines falls the verdict back to the whole-tree binding,
which is stricter. The paths I reviewed are listed under "What I read"
below.

**Deterministic floor.** `loopctl verify-eval-substance L5-landing-registry-tab`
→ `valid`, exit 0, no `warn:` lines. No hard-fail, no advisory, so I ran the
full semantic pass.

**Standing assertion.** `loopctl verify --expect-tree
aaca078cdd39b0c662c62978a79e81dd594c0e74` exited 0 before my first write and
again after all scratch work, so nothing I did moved the tree. All scratch
artifacts live under `.loop/scratch/`, which `.loop/.gitignore:4` excludes.

---

## Verdict

All seven cycle-1 findings are genuinely closed. I re-attacked each one with
a mutation rather than reading the hand-off, and every fix holds under the
mutation that would have exposed it. The gates pass independently. The
shipped code is correct: the walk never touches a weights layer, the store
survives eight concurrent writers, the blob cap is streamed not buffered,
the rendered card is safe as an `innerHTML` source, both reservations are
byte-identical, both image tags moved, and the guard admits no exemption.

Two things are not closed, and neither is a code defect:

- a named clause of Requirement 14 was dropped from the port (AR12);
- the plan and the signed eval both state a cold-walk cost the shipped walk
  does not hit, and no test pins any count for the real catalog (AR13).

Both are cheap. Neither risks the cluster. Hence
`pass-with-required-fixes` rather than `fail`.

---

## Cycle-1 findings, re-attacked

I did not trust the hand-off summary. Each fix below was tested by breaking
it in an isolated copy of the backend project (`uv sync --frozen` into
`.loop/scratch/.../c2/mutant`, baseline 83 passed) and confirming the named
test goes red.

### AR1 — versions unbumped (was high) — CLOSED

`deployments/applications/services.tf:389` = `      dash_frontend_version = "0.3.0"`
`deployments/applications/services.tf:390` = `      dash_backend_version  = "0.3.0"`

One hunk moves both. Requirement 20's failure mode ("one moved and one left
behind") is not present.

### AR2 — a failed sweep emptied the tab (was high) — CLOSED

`registry_client.py:240` = `            return {**self._payload, "error": self._error}`

**Mutation 9:** replaced the whole `except` branch with a bare re-raise.
Result: `test_a_failed_sweep_serves_the_last_good_payload_with_the_error`
fails, 82 pass. The guardrail is real, not shape-checking.

I also pressed on the broad `except Exception` the briefing asked about. It
does **not** swallow anything it should not: `asyncio.CancelledError`,
`KeyboardInterrupt` and `SystemExit` are all `BaseException` subclasses in
3.12 and pass straight through. What it does catch — a `KeyError` from a
malformed manifest, say — is surfaced verbatim in the payload's `error`
string rather than hidden, which is Requirement 12's stance. No finding.

### AR3 — RegistrySweep untested (was high) — CLOSED

`tests/test_registry_sweep.py:150` = `        assert forbidden not in fetched, f"the walk pulled {forbidden}"`

**Mutation 1, the one I was asked to re-run:** `_entry` fetches every layer
and tolerates a non-tar body, so the weights, tokenizer and `embark.json`
blobs are all pulled. Result: **3 failures**, including the named guardrail
`test_the_walk_never_fetches_a_weights_or_embark_layer`, plus the two-tag
and cold-count tests. In cycle 1 the equivalent mutant passed 71/71.

The fixture claim checks out: `test_registry_sweep.py:120-123` mocks all
three forbidden digests at `200`, so the mutant fetches successfully and
fails on the assertion rather than on a 404. The test also carries positive
controls at `:147-148` (the Kitfile and the README really are fetched), so
the negative assertions are not vacuous.

### AR4 — cap test could not detect read-then-measure (was medium) — CLOSED

`tests/test_registry_client.py:152` = `    assert pulled["n"] < total_chunks, "the whole body was consumed despite the cap"`

**Mutation 2, the claim I was asked to re-verify:** moved the cap check
outside the `async for`, so the body is appended whole and then measured.
Result: exactly one failure, `test_the_oversized_blob_is_abandoned_mid_stream_not_read_whole`,
at line 152. The implementer's claim is independently confirmed.

### AR5 — no cluster-marked `/api/registry` case (was medium) — CLOSED

`tests/test_cluster.py:20` = `pytestmark = pytest.mark.cluster`,
`:68` = `def test_the_registry_route_returns_models_from_the_live_registry() -> None:`

`uv run pytest -m cluster --collect-only -q` → `3/86 tests collected (83
deselected)`, the third being the new case. Default run deselects it.

### AR6 — spy drove 2 of 5 calls; duplicate offload helper (was medium) — CLOSED

`tests/test_registry_store.py:103-110` asserts all six async calls in order.
`grep -rn "_to_thread_store" src/` returns nothing, so the duplicate helper
is gone and `replace_tags` goes through the store's own `areplace_tags`
(`registry_store.py:176-177`).

**Mutation 8:** made `areplace_tags` call `self.replace_tags(seen)` directly.
Result: `test_every_public_call_reaches_sqlite_through_the_thread_offload`
fails. The spy is load-bearing.

### AR7 — credential guardrail asserted nothing (was medium) — CLOSED

`tests/test_main.py:204` = `    index = (Path(__file__).resolve().parents[2] / "frontend" / "index.html").read_text()`

The test now opens with a positive control
(`config.read_registry_credential() == ("push", "shibboleth")`), so the
negative assertions are no longer vacuous, and it greps `/api/status` and
the served `index.html` as the eval row's Input names. See AR15 for the one
gap left.

### AR8, AR9, AR10, AR11 — unchanged

AR9 re-confirmed by **mutation 7** (one shared connection, `check_same_thread=False`,
every `close()` made a no-op): `test_eight_concurrent_writes_all_land` **and**
`test_the_store_holds_a_path_and_never_a_connection` fail on 3 of 3 runs, so
Requirement 25's headline guardrail is deterministic and not flaky.

AR10 re-confirmed: `python3 scripts/check_oauth2_proxy_guard.py --self-test`
→ `self-test: ok`, exit 0. `git diff HEAD | grep SKIP_AUTH` → nothing.

AR11 unchanged: the 22-byte `.ssh/id_rsa` placeholder is still in the
worktree. Gitignored, outside the tree fingerprint, housekeeping only.

---

## New findings

### AR12 — MEDIUM — Requirement 14's two panel footnotes were not ported

`deployments/applications/services/dash/frontend/index.html:555` = `      <div class="kit-grid" id="kit-grid"></div>`
`deployments/applications/services/dash/frontend/index.html:556` = `    </div>`

The mockup carries a `<p class="footnote">` immediately after the kit grid
(`assets/registry-mockup.html:452-458`) and another after the images table
(`:504-508`). The shipped section runs kit-grid → close → images panel with
neither. `grep -n "footnote"` on the shipped `index.html` returns only the
pre-existing status footnote at `:563`.

Requirement 14 lists them as one of six bullets, cites both by line, and
goes on to prescribe how to correct their prose ("the images one says a
multi-arch tag 'resolves through an index first', which this ticket does
**not** do... that clause is corrected"). An implementer told exactly what
to write did not write it. That is a scope omission, not a judgment call.

It compounds AR13: the models footnote is the only place on the page the
walk's cost would have been stated to the operator, and Requirement 14
required that copy to "describe the shipped walk, not blind".

**Required fix:** port both footnotes, with the models one carrying the
measured `1 + R + T + 3D` / 25 rather than the plan's 21, and the images one
carrying the correction Requirement 14 spells out.

### AR13 — MEDIUM — the shipped cold walk costs 25 requests, not the 21 the plan and the eval name

`tests/test_registry_sweep.py:171` = `    assert sum("/manifests/" in u for u in urls) == 3, "two tag HEADs plus one manifest GET"`

I measured the walk rather than reading the formula. A four-repo, two-tag
fixture with the `307` modelled on both blob routes, driven through the real
`RegistrySweep`:

```
COLD total client round trips : 33
COLD registry-path requests   : 25
  catalog 1 | tags/list 4 | manifests 12 | blobs 8
WARM registry-path requests   : 13
```

The warm sweep is 13, exactly as designed — the restructure the briefing
described did land. The cold walk is **25 / 33**, not the **21 / 29** that
Requirement 7, §8 and the eval's bolded guardrail row all name. The gap is
structural: `_entry` HEADs each tag for its digest and then GETs the
manifest once per digest, so the real shape is `1 + R + T + D + B`. The
plan's `1 + R + T + B` model never counted a manifest body, which the walk
cannot do without — the `HEAD` returns a digest in a header and nothing
else. Reaching 21 would need the cold path to GET manifests per tag instead
of HEAD-then-GET.

Two consequences:

1. **The eval marker is stale.** Its guardrail row's Expected reads
   "exactly `1 + R + T + B` registry-path requests". Whoever scores it
   against the shipped code will read 25 and see a mismatch. Note the row's
   **Fails-when** names only the weights/`embark.json` condition, which the
   code does satisfy, so the row does not strictly fail — but its Expected
   is wrong and should not stay signed that way. `loopctl eval-amend`
   refuses inside a linked worktree, so this is **operator work**, not
   implementer work.

2. **No test pins any count for the real catalog.** §8 was specific: "the
   count is asserted twice: `21` over the registry-path routes and `29` over
   all routes", with the `307` modelled, because "a fixture that stubs only
   the MinIO destination would count 21 and pass while production fails on
   the redirect". The shipped sweep tests assert a one-repo shape and
   `mount_modelkit` (`test_registry_sweep.py:112-117`) serves blobs at a
   direct 200 with no redirect.

   The redirect risk itself **is** covered, just not at the walk level:
   **mutation 5** (`follow_redirects=False`) fails
   `test_a_blob_follows_the_307_to_its_final_body` and
   `test_the_client_is_built_async_and_bounded_at_eight_connections`. So §9's
   named production failure cannot ship silently. That materially lowers the
   risk here to "the numbers in the frozen artifacts are wrong", not "the
   redirect is untested".

`docs/dash-landing-page.md:47` = `digest one manifest and its two small blobs: `1 + R + T + 3D`, which is 25`
is already correct, so the divergence lives only in the plan and the eval.

**Required fix:** amend the eval's guardrail row and Requirement 7 to the
measured shape (operator), and add one sweep test asserting the count for a
multi-repo fixture that models the `307`, so the number is pinned somewhere
a gate can see it.

### AR14 — LOW — the warm path's `repo`/`tags` correctness is unpinned

`registry_client.py:292` = `        cached = await self.store.aget_card(digest)`
`registry_client.py:327` = `        entry = {k: v for k, v in row.items() if k not in ("repo", "tags", "digest")}`

The briefing asked me to check whether `_remember` stores the right subset
and whether a cached entry still yields the correct reference. It does, on
both counts: `_remember` strips the three reference-scoped keys, and the
cached branch (`:296-298`) reassigns them unconditionally from the live
sweep. Everything the store keeps is genuinely digest-scoped — `created`,
`description`, `authors`, `layers`, `card_html` for a model; `arch`, `size`,
`pushed`, `multi_arch` for an image, where `size` is summed from the
manifest's own layers. Correct.

But nothing tests it. **Mutation 6** (store the reference *and* `setdefault`
instead of assigning on read — the shape that serves a stale tag list after
a new tag is pushed onto an existing digest) passes **83/83**.
`test_a_warm_sweep_fetches_no_manifest_and_no_blob:185` asserts `repo` but
not `tags`. One added assertion closes it.

I also checked the cached path for bypassed validation. It trusts the stored
`kind` instead of re-running `is_modelkit`, which is sound because the
digest is content-addressed. Eviction still works
(`test_a_vanished_digest_is_evicted_from_the_store`). The `cards` schema
change from `kitfile_json, card_html` to `entry_json` leaves no stale-read
path in production, because the `dash_data` volume is created by this ticket
and no database with the old columns exists anywhere.

### AR15 — LOW — the credential guardrail greps the password but not the encoded header

`tests/test_main.py:205` = `    assert "shibboleth" not in index`

The eval row also names "nor an `Authorization` header value". The base64
form of `push:shibboleth` would pass every assertion in the test. No code
path puts it near a response, so this is coverage, not a leak.

---

## Confirmed good (checked, nothing to fix)

**The rendered card is safe as an `innerHTML` source.** `registry.py:29`
uses `MarkdownIt("js-default")` and `index.html:906` assigns `card_html`
straight to `.innerHTML`, so I probed the renderer directly rather than
trusting the preset name:

| input | output |
|---|---|
| `<script>alert(1)</script>` | `&lt;script&gt;alert(1)&lt;/script&gt;` |
| `[x](javascript:alert(1))` | literal text, no `<a>` |
| `[x](data:text/html,...)` | literal text, no `<a>` |
| `<img src=x onerror=...>` | escaped |
| GFM table | `<table>` |
| fenced block | `<pre><code class="language-python">` |

Requirement 5 holds, and `html` is never set to `True` anywhere.

**The unrendered-credential literal.** `main.py:95` =
`                {"models": [], "images": [], "error": "registry credential not rendered yet"}`
is a string no test asserts on and the first of its kind at that anchor, so
I checked it against runtime rather than scoring it from the diff. A
reproducer outside the repo tree (temp dir, no repo write) drove three
variants — missing file, empty file, half-written JSON — and all three
returned `200` with that exact body and created no database file. The copy
is accurate: the credential really is unread on that path.

**The §8 adversarial hand-off checklist**, run item by item:

- no diff in `machine_roles.tf`, `database.tf` or `_http.py`; `tiles.json`
  `git diff --stat` empty
- no new `.tf` file; exactly one new resource block,
  `nomad_dynamic_host_volume.dash_data`, in `deployments/infrastructure/services.tf`,
  constrained to `radxa-dragon-q6a` to match `dash.hcl:6-9`
- `embark` under the backend `src/` tree appears once, at `registry.py:12`,
  in the comment explaining why `embark.json` is not parsed
- no `redis`, no `aiosqlite`, no `pytest-asyncio`, no `anyio`; exactly one
  dependency added (`markdown-it-py>=4.2.0`) with `uv.lock` updated
- `httpx.Client(` appears only at the pre-existing `_http.py:42`; the new
  modules are async throughout
- `MAX_CONNECTIONS = 8` feeds both `httpx.Limits` (`:67`) and
  `asyncio.Semaphore` (`:244`)
- no module-level `sqlite3.Connection`, no `check_same_thread=False` outside
  the header comment explaining its absence; the only synchronous store call
  outside `_to_thread` is `create_schema()`, invoked from `main()` before
  `uvicorn.run`, so no loop exists to block
- the only `DELETE` touching `cards` is eviction by unreferenced digest;
  `fetched_at` is written and never read, so nothing expires on age
- route is bare `/api/registry` in both `main.py:107` and the frontend
  `fetch` (`index.html:979`); `?refresh=1` is a query parameter and reaches
  only the sweep floor, never the digest cache
  (`test_a_warm_sweep_fetches_no_manifest_and_no_blob` drives `force=True`
  and asserts zero blobs and zero manifest GETs)
- one theme toggle (`index.html:516`), the pre-existing one; no second
- no `SKIP_AUTH_*` key anywhere in the diff or in `oauth2-proxy.hcl`
- `dash.hcl` reservations byte-identical: the diff touches no `cpu`,
  `memory` or `resources` line
- `secrets.tf` writes `default/dash/registry` with `username` and `password`
  only, carrying `random_password.registry_push.result`, never an htpasswd
  hash

**Gates, re-run independently, not taken from the hand-off:**

| gate | result |
|---|---|
| `just pre_commit` | exit 0, every hook passed |
| `uv run pytest` (backend) | 83 passed, 3 deselected |
| `ruff check` on `src` + `tests` | All checks passed |
| `ruff format --check` | 26 files already formatted |
| `mypy --strict` | Success: no issues found in 26 source files |
| `check_oauth2_proxy_guard.py --self-test` | `self-test: ok` |

One note on the gate run: `oauth2-proxy guard self-test` reported "(no files
to check) Skipped" because `scripts/check_oauth2_proxy_guard.py` is still
untracked and `--all-files` walks the index. It will fire on the commit that
adds it. I ran it by hand; it passes. Same reason `ruff` did not see the new
untracked modules through the hook, which is why I ran it on them directly.

---

## What I read

Diff paths reviewed (modified): `.loop/ledger.json`,
`.pre-commit-config.yaml`, `deployments/applications/secrets.tf`,
`deployments/applications/services.tf`,
`deployments/applications/services/dash.hcl`,
`deployments/applications/services/dash/backend/pyproject.toml`,
`deployments/applications/services/dash/backend/src/dash_app/config.py`,
`deployments/applications/services/dash/backend/src/dash_app/main.py`,
`deployments/applications/services/dash/backend/tests/test_cluster.py`,
`deployments/applications/services/dash/backend/tests/test_main.py`,
`deployments/applications/services/dash/backend/uv.lock`,
`deployments/applications/services/dash/frontend/index.html`,
`deployments/infrastructure/services.tf`,
`deployments/infrastructure/services/oauth2-proxy.hcl`,
`docs/dash-landing-page.md`.

Diff paths reviewed (added):
`deployments/applications/services/dash/backend/src/dash_app/registry.py`,
`.../registry_client.py`, `.../registry_store.py`,
`deployments/applications/services/dash/backend/tests/test_registry.py`,
`.../test_registry_client.py`, `.../test_registry_store.py`,
`.../test_registry_sweep.py`, `scripts/check_oauth2_proxy_guard.py`.

Contract read: `.loop/plans/L5-landing-registry-tab.md` (§6, §7, §8),
`.loop/evals/L5-landing-registry-tab.md`, `assets/registry-mockup.html`.

Scratch artifacts (gitignored, tree unchanged):
`.loop/scratch/L5-landing-registry-tab.adversarial/findings.json`,
`trust-stamp.json`, and `c2/` holding `probe_count.py` and the isolated
mutant project.

---

## What must happen before done

1. **AR12** — port the two panel footnotes into the registry section, with
   the models one carrying the measured cost and the images one carrying
   Requirement 14's prescribed correction. Implementer.
2. **AR13** — amend the eval's weights guardrail row and Requirement 7 from
   `1 + R + T + B` / 21 to the measured `1 + R + T + D + B` / 25, and add a
   sweep test that pins a multi-repo count against a fixture modelling the
   `307`. The eval half is operator work: `loopctl eval-amend` refuses
   inside a linked worktree by design.
3. **AR14, AR15** — optional, one assertion each.
