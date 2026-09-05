---
verdict: fail
tree: a579f4f96c7f603eed1630da33bcac5965160ea8
---

# Adversarial review — L5-landing-registry-tab

**Scope binding omitted deliberately.** My briefing carried the tree
fingerprint but no 64-hex scope digest and named no
`verdict_binding_inputs`, and `loopctl` exposes no command to mint one. Rather
than fabricate a digest for a path set I was not given, I omit `bound_paths:`,
`scope:` and `citations:` and let this verdict fall back to the whole-tree
binding, which is the stricter of the two. Every anchor below is quoted
verbatim inline.

## Deterministic floor

`loopctl verify-eval-substance L5-landing-registry-tab` → `valid`, exit 0. No
hard-fails, no advisories. Proceeded to the semantic pass.

`loopctl verify --expect-tree a579f4f9...` → `ok`, exit 0.

## Gates, re-run independently

- `just pre_commit` → all 21 hooks pass, 1m15s. Trust stamp written to
  `.loop/scratch/L5-landing-registry-tab.adversarial/trust-stamp.json`.
- `uv run pytest` in the dash backend → 71 passed, 2 deselected, 0.57s.
- `oauth2-proxy guard self-test` reports `(no files to check) Skipped` only
  because the script is still untracked; I ran it by hand (exit 0), plus
  `ruff check`, `ruff format --check` and `mypy --strict` on it (all clean),
  so it will not surprise the commit gate once staged.

Green gates. The findings below are all things no gate exercises.

---

## HIGH 1 — Requirement 20 unmet: neither image version bumps, so nothing ships

`deployments/applications/services.tf:389 =       dash_frontend_version = "0.2.0"`
`deployments/applications/services.tf:390 =       dash_backend_version  = "0.2.0"`

Both are byte-identical to `HEAD`. Requirement 20 is unconditional: "`dash_frontend_version`
and `dash_backend_version` ... each move, since both trees change," and §8's
hand-off asks the reviewer to confirm "**both** values changed."

This is not bookkeeping. `deployments/applications/justfile:54-55` and `:66-67`
derive the image tag by grepping these very lines, and `dash.hcl:45` / `:71`
pull `ghcr.io/jasperhg90/dash-{frontend,backend}:${..._version}`. `0.2.0` is the
already-published L4 tag, so an apply on this diff pulls the *old* images: 411
lines of new frontend and three new backend modules reach the cluster only if
someone overwrites a published tag. The registry tab would simply not appear.

## HIGH 2 — Requirement 12 unmet: a failed sweep empties the tab (confirmed at runtime)

Requirement 12: "A failed sweep must leave the last good cache in place rather
than emptying it."

`registry_client.py:225 =         self._payload = await self._walk()`

The sweep object gets this right: when `_walk()` raises, the assignment never
runs and `self._payload` keeps the last good value. `main.py` then throws it
away:

`main.py:101 =             # Same stance as /api/status: a registry that is unreachable`
`main.py:102 =             # empties the tab, it does not take the page down.`

The handler's `except Exception` sets `payload = {"models": [], "images": [],
"error": str(err)}` with no fallback to `sweep._payload`. I reproduced it
(`.loop/scratch/.../probe_r12.py`, no writes to the tree):

```
after a GOOD sweep   -> models: ['embeddinggemma-q8']
after a FAILED sweep -> models: [] | error: registry.invalid: connection refused
sweep still holds the last good payload internally: ['embeddinggemma-q8']
REQUIREMENT 12 ... HELD: False
```

The comment at `:101-102` is itself the bug's rationale in miniature: it
defends "does not take the page down", which is Requirement 12's *first*
clause, and is silent on the second. §8 mandated the test that would have
caught this — "a raising sweep after a good one still returns the cached
models" — and it is absent, which is why nothing did.

## HIGH 3 — `RegistrySweep` has zero test coverage; five eval rows have no scorer

No test file references `RegistrySweep`, `payload(` or `_walk`. Coverage over
the shipped suite:

```
src/dash_app/registry_client.py   168   57   66%   ... 238-267, 272-298, 302
```

`238-267` is the body of `_walk`; `272-298` is the body of `_entry`. The entire
walk — dedup, classification, blob selection, cache read, cache write — is
unexecuted.

I confirmed this has teeth, not just a coverage number. I copied the backend
into scratch, changed `_entry` to download **every** layer including
`modelkit.model.v1.tar` (309 MB of weights) and `modelpart`, and ran the
shipped suite against it:

`registry_client.py:293 =                 readme = await self.client.get_layer_file(repo, layer["digest"], http)`

```
loaded from: .../scratch/.../mutant/src/dash_app/registry_client.py
mutant active (downloads every layer): True
71 passed
```

**A backend that pulls model weights ships green.** That is the eval's own
Definition of Done ("without touching a weights layer") and its bolded
guardrail row, whose scorer is declared `Deterministic (respx route call
counts) 100%`.

Five eval rows name a deterministic scorer that does not exist:

| Eval row | Declared scorer | Reality |
|---|---|---|
| Guardrail — never pulls model weights | respx route call counts, `1 + R + T + B` | no such test; mutant above passes |
| Each kit is drawn once though two tags point at it | respx call counts | only the pure `group_by_digest`; no blob-fetch counts |
| A newly pushed model appears without a reload | `test_registry_client.py`, fixture sweep | no fixture sweep exists |
| A pushed container image renders as a row | respx fixture | only the pure `image_row`; walk routing untested |
| A restart costs no re-fetching | `test_registry_store.py`, zero blob fetches / zero renders | persistence proven, fetch and render counts never asserted |

§7 and §8 spell out each of these tests, including the exact numbers ("`21`
over the registry-path routes and `29` over all routes"). The implementation
appears correct on inspection — `_entry` fetches only the docs layer, only a
config blob for a plain image, nothing for an index, and `embark.json` is never
parsed (`registry.py:12` records why). But correctness held only by reading is
exactly what this ticket's headline guardrail was supposed to stop being.

---

## MEDIUM 4 — the blob-cap test cannot detect the defect its eval row names

`registry_client.py:105 =                     if total > MAX_BLOB_BYTES:`

The implementation is right: it streams, counts, and refuses before appending.
The test is not:

`tests/test_registry_client.py:114 =     assert "exceeds" in str(caught.value)`

I ran the shipped assertions against a deliberate read-then-measure
implementation (`probe_cap.py`):

```
shipped test's assertions pass against the CORRECT streaming impl : True
shipped test's assertions pass against READ-THEN-MEASURE (forbidden): True
```

The eval's Fails-when is "The body is read whole and then measured, or the cap
constant is silently raised". The second half is covered by
`test_the_cap_constant_is_one_mebibyte`. The first half is not detected at all.
§8 required "the same test asserts the streamed reader never materialized the
whole body"; that assertion is missing. The test does still catch a fully
uncapped rewrite, which is why this is medium and not high.

## MEDIUM 5 — no `cluster`-marked `/api/registry` case

§8 requires "the `/api/registry` case in `tests/test_cluster.py`". The file is
unmodified and greps clean for `registry`.

## MEDIUM 6 — the thread-offload spy covers 2 of 5 store calls

`test_every_public_call_reaches_sqlite_through_the_thread_offload` drives only
`aput_card` and `aget_card`. Coverage confirms `registry_store.py:137-147, 164,
167, 170` unexecuted — `replace_tags`, `aput_tag`, `aknown_digest`,
`aevict_unreferenced_cards`. Worse, `replace_tags` has no async wrapper and is
offloaded through a *separate* helper living in the other module
(`registry_client.py:251, 301-302`), which the store-module spy can never
observe. §8 asked for "drive each public call, assert the spy saw them all, so
a future direct call fails the suite"; a direct `self.store.replace_tags(seen)`
would block the event loop and no test would notice.

## MEDIUM 7 — the credential guardrail tests only the empty error payload

`test_the_registry_payload_never_carries_the_registry_password` builds a config
with `registry_addr="http://registry.invalid"`, so the body it greps is always
`{"models": [], "images": [], "error": ...}`. A password can hardly appear in a
payload with no content. The eval row's input is "A rendered `/api/registry`
payload **and the served `index.html`**"; `index.html` is never checked. The
positive control on `read_registry_credential()` is good practice and I credit
it, but it proves the credential is readable, not that a *populated* payload
omits it.

## LOW 8 — the sweep is built once, at app construction

`main.py`'s `_build_sweep` runs inside `create_app`, so a credential file
absent at that moment pins the route to `"registry credential not rendered yet"`
until a task restart. Nomad renders templates before task start and
`dash.hcl`'s `change_mode = "restart"` covers rotation, so the window is narrow
— but the degraded state is permanent rather than self-healing.

---

## What I checked and am satisfied with

**The SQLite concurrency shape — passes, and I verified it has teeth.**
`registry_store.py:68 =         return sqlite3.connect(self.path)`. The class holds a
`Path` and never a connection, every method opens and closes in a `finally`,
and `check_same_thread` appears only in the header comment explaining its
absence. The concurrency test asserts on rows read back, not on no-raise:

`tests/test_registry_store.py:113 =         await asyncio.gather(*[store.aput_card(f"sha256:{i}", {}, f"<p>{i}</p>") for i in range(8)])`
`tests/test_registry_store.py:119 =         assert card is not None, f"row {i} was lost"`

I re-measured the hazard rather than taking the plan's word: a shared
connection over 40 trials of eight concurrent writes gave `{'raised': 11,
'clean': 25, 'lost': 4}`. So the failure is real and includes silent row loss,
and the read-back assertion catches both modes where a no-raise assertion would
catch only 11 of 15. One caveat worth recording: as a *detector* this test is
probabilistic (~38% per run), so
`test_the_store_holds_a_path_and_never_a_connection` is the deterministic
backstop, and it is correctly present.

**The oauth2-proxy guard — passes.**
`scripts/check_oauth2_proxy_guard.py:27 =     "OAUTH2_PROXY_SKIP_AUTH_ROUTES",`
plus `_REGEX` and `_PREFLIGHT`, named in full, never grepped as `SKIP`.
Negative control I ran: clean file → `[]`, file plus one exemption →
`['OAUTH2_PROXY_SKIP_AUTH_ROUTES']`, and `OAUTH2_PROXY_SKIP_PROVIDER_BUTTON` is
genuinely present in the real file and correctly ignored. The hook's `files:`
regex covers `oauth2-proxy\.hcl` itself, not just the script, so the commit that
would add an exemption is the commit that runs it.

**Resource reservations — unchanged.** `cpu = 50` / `memory = 32` and `cpu =
200` / `memory = 128`, byte-identical to `HEAD`.

**Scope — clean.** Every changed path maps to §7. No new `.tf` file, so
`.claude/rules/terraform-file-layout.md` holds: the host volume went into
`infrastructure/services.tf` (host volumes) and the KV write into
`applications/secrets.tf` (Vault KV), which is exactly the split that rule
mandates. `machine_roles.tf`, `database.tf`, `_http.py` and `tiles.json` are
untouched. `pyproject.toml` gained exactly one dependency with `uv.lock`
committed; no `pytest-asyncio`, `anyio`, `aiosqlite` or `redis`. No
`httpx.Client(` in the new modules. `embark` appears under `src/` only in the
comment explaining why `embark.json` is not parsed.

**The frontend port — read, not executed.** I state plainly that this repo has
no browser or JS test harness, so nothing below was run. Reading
`index.html` against `assets/registry-mockup.html`: tab strip with
`role="tablist"` and ArrowLeft/ArrowRight nav, kit cards whose `.seg` widths are
computed as `(l.size / sum) * 100` so the layer bar is genuinely to scale, modal
ordered card → layers → commands, `cardModal.addEventListener('click', e => { if
(e.target === cardModal) cardModal.close(); })` for backdrop close, and copy
buttons with a clipboard path plus an `execCommand` fallback. The mockup's
page-level chrome is correctly *not* ported: the page keeps its own
`localstack_` wordmark, its existing summary strip and its single existing theme
toggle, all pre-existing lines outside the diff, which is what §11 Q3 excluded.
Requirements 14/15 remain a manual check, as the eval's last row honestly says.

**The `.ssh/id_rsa` placeholder — legitimate, with one housekeeping note.** I
judged rather than accepted it. `terraform validate` resolves
`file("${path.root}/../../.ssh/id_rsa")` at `services.tf:411` for existence
only; it never parses the bytes, so a real key and `placeholder-not-a-key`
produce identical validate results and nothing is masked except the worktree's
own missing artifact. `.gitignore:5` carries `.ssh`, so the file is outside both
the commit and the tree fingerprint (the stamp builder drops ignored paths) —
`loopctl verify --expect-tree` matched with the file in place, and
`detect private key` passed. Two caveats for the operator, neither
blocking: I could not independently confirm "this was the worktree's only
error", since removing the file to re-test would be a write to the tree I am
reading; and the placeholder should be deleted before this worktree is reused,
since a `terraform apply` from here would fail authenticating the `remote-exec`
provisioner.

---

## Verdict

**fail.** Two of the three high findings are defects a green gate is silent
about and that no test would ever raise: the feature cannot deploy (HIGH 1) and
it degrades wrongly under a registry blip (HIGH 2, reproduced at runtime). The
third is the one the ticket cared most about — a backend that downloads model
weights passes this suite 71/71, so the eval's headline guardrail is currently
scored by nobody.

The production code is, as far as reading goes, largely right: the store shape,
the streaming cap, the digest dedup, the docs-only layer fetch and the auth
guard are all correctly built. The gap is that the walk holding almost all of
that behavior is untested, so five eval rows claiming a deterministic 100%
scorer are resting on inspection.

Required to pass:

1. Bump both `dash_frontend_version` and `dash_backend_version`.
2. Fall back to the sweep's last good payload on a failed walk, and add §8's
   "a raising sweep still returns cached models" test.
3. Add the `RegistrySweep` respx tests §7/§8 specify — at minimum the cold
   call-count pair (21 registry-path / 29 total) with explicit assertions that
   no weights, `modelpart` or `embark.json` digest is ever requested; blobs
   fetched once per digest rather than per tag; the warm-store restart case at
   zero blob fetches; and the image and index rows built through the walk.
4. Assert the streamed reader never materializes an oversized body, so the cap
   test can tell streaming from read-then-measure.

Recommended in the same cycle: the `cluster`-marked route case (MEDIUM 5),
widening the thread-offload spy to all five store calls and giving
`replace_tags` a store-side `async` wrapper (MEDIUM 6), and asserting the
credential guardrail against a populated payload and `index.html` (MEDIUM 7).

Findings ledger: `.loop/scratch/L5-landing-registry-tab.adversarial/findings.json`
