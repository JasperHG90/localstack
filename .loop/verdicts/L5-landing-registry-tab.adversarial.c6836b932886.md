---
verdict: pass
tree: d45829a41796e91fe032eecc4642aef015363b37
---

# Adversarial review — L5-landing-registry-tab (cycle 3, final)

**Scope binding omitted deliberately, as in cycle 2.** My briefing carried
the tree fingerprint but no 64-hex scope digest, and named no
`verdict_binding_inputs`. `loopctl` exposes no command to mint one, and a
digest I computed myself would cover a path set nobody asked me to bind.
Omitting the three lines falls this verdict back to the whole-tree binding,
which is stricter. The reviewed path set is listed under "What I read".

**Standing assertion.** `loopctl verify --expect-tree
d45829a41796e91fe032eecc4642aef015363b37` → `ok`, exit 0, before any write.

**Deterministic floor.** `loopctl verify-eval-substance
L5-landing-registry-tab` → `valid`, exit 0, no `warn:` lines. No hard-fail,
no advisory — in particular no plan-drift advisory, which confirms the plan
still hashes to the marker's recorded `plan:` fingerprint and therefore that
nobody hand-edited it. Full semantic pass run.

**Gates, re-run independently.**

- `just pre_commit` — 21 hooks, all Passed. One reported
  `oauth2-proxy guard self-test .... (no files to check) Skipped`, because
  `scripts/check_oauth2_proxy_guard.py` is still untracked and
  `pre-commit --all-files` only walks tracked files. I ran it directly:
  `--self-test` → `self-test: ok`, exit 0; the bare guard against the
  jobspec → exit 0. It will run under the hook from the commit onward.
- `uv run pytest` in `.../dash/backend` — 83 passed, 3 deselected.
- `uv run pytest -m cluster --collect-only` — 3/86 collected, 83 deselected.
  The live-registry tests stay off the default run.

---

## Verdict

**Pass.** Every eval row is met by the shipped code. AR12 and AR15, the two
fixes I required in cycle 2, are genuinely closed. AR13 I asked the
implementer to justify and the justification is correct — I accept it, with
an operator follow-up named below. One finding stays open, AR14, and the
hand-off's claim that it was fixed is wrong; but it is a test-strength gap
over code that is itself correct, so at the cycle cap it does not justify
sinking the ticket.

---

## AR12 — CLOSED. Footnotes present, and accurate.

Both panels carry one, and the prose is better than the mockup's rather than
merely copied.

- `deployments/applications/services/dash/frontend/index.html:558` = `        Nothing here touches the weights. A cold walk reads the catalog, one tag list per`
- `deployments/applications/services/dash/frontend/index.html:568` = `        An image row costs one blob where a ModelKit row costs two: its config blob carries`

I checked every clause against the walk rather than accepting that they are
present:

| Claim | Evidence |
|---|---|
| "Nothing here touches the weights" | `_entry` reads only the config blob and the one `docs` layer. Mutation-tested — see AR3 below. |
| cold = catalog, tag list per repo, `HEAD` per tag, then per digest a manifest + Kitfile + README | `registry_client.py` `:251`, `:252-254`, `:259`, `:301`, `:312`, `:318`. That is `1 + R + T + 3D`, i.e. 25 for four repos — consistent with AR13, not with the plan's 21. |
| "A warm one reads only the first three" | the cache is consulted before the manifest (`:292-299`), so warm = `1 + R + T` = 13. Correct. |
| "each kit is walked and drawn once" | `group_by_digest` keys on `(repo, digest)` (`registry.py:50-61`). |
| image row costs one blob, ModelKit two | image path takes one `get_config_json` (`:307`); ModelKit takes `:312` + `:318`. Correct — and note this **reverses** the mockup, which claimed an image needs "one extra request that a ModelKit row does not". The correction is right. |
| "config blob carries the architecture and the build date" | `registry.py:134` `config.get("architecture")`, `:136` `config.get("created")`. |
| index "carries no layers ... shows its digest and nothing invented" | `registry.py:119-128` returns `arch: None`, `size: None`, `multi_arch: True`. |

The mockup's wrong `1 + R + T + 2D` / 21 and its unverifiable "about 1.2 s"
are both gone. Correcting rather than porting was the right call.

**Structure not disturbed.** I checked the three ways a footnote inside a
tabpanel could break:

- `deployments/applications/services/dash/frontend/index.html:789` = `    grid.textContent = '';`
- `deployments/applications/services/dash/frontend/index.html:838` = `    body.textContent = '';`

Both renders clear only `#kit-grid` / `#images-body`; each footnote is a
sibling of those, inside the panel, so no render wipes it.

- `deployments/applications/services/dash/frontend/index.html:978` = `        other.panel.hidden = i !== j;`

Tab switching toggles the panel, so each footnote hides and shows with its
own tab — which is what you want, and `#panel-images` carries `hidden`
initially so the images note starts hidden. A full tag-balance parse of the
1016-line file reports nothing unclosed and no mismatch, and no CSS rule is
scoped to the panels, so `.footnote` styling applies unchanged.

## AR13 — ACCEPTED as argued. The plan is wrong, not the code.

The implementer asked me to judge this plainly, so: **do not make the code
match the plan's 21.** Reaching 21 means dropping the per-digest manifest
GET, and that cannot be done.

- `deployments/applications/services/dash/backend/src/dash_app/registry_client.py:154` = `        return response.headers.get("Docker-Content-Digest"), False`
- `deployments/applications/services/dash/backend/src/dash_app/registry_client.py:301` = `        manifest, _ = await self.client.get_manifest(repo, digest, http)`

`HEAD` yields a digest header and nothing else. The layers, the config
digest and `artifactType` — everything `is_modelkit`, the layer bar and the
card need — exist only in the manifest body. Without the GET there is no
tab. The shipped `1 + R + T + D + B` = 25 cold / 13 warm is correct and the
plan's `1 + R + T + B` is an arithmetic error made before the HEAD-then-GET
design settled.

The suite already encodes the true shape:

- `deployments/applications/services/dash/backend/tests/test_registry_sweep.py:171` = `    assert sum("/manifests/" in u for u in urls) == 3, "two tag HEADs plus one manifest GET"`

Leaving the artifacts alone was also right. `loopctl eval-amend` and
`eval-rebind` both refuse inside a linked worktree by design, and editing
the plan by hand would have broken the marker's `plan:` fingerprint and
raised a drift advisory the implementer cannot clear. Quietly rewriting a
signed row would defeat the mechanism that exists to catch exactly that.

**Why this does not block.** The wrong count sits in the row's *Expected*
cell. The *Fails-when* cell — the part with teeth — reads "Any request whose
digest matches a weights or `embark.json` layer", and that is met and
mutation-tested. `docs/dash-landing-page.md`, the durable document, now
states 25/13 and breaks `B` down by digest kind; I verified that breakdown
(ModelKit two, image one, index none) against `registry.py:119-138` and it
is right.

**REQUIRED OPERATOR FOLLOW-UP, outside this worktree:** amend the eval's
guardrail row and plan Requirement 7 / §8 from `1 + R + T + B` / 21 to
`1 + R + T + D + B` / 25, then re-bind. The eval's own sign-off line asks
for operator review on return today, so this lands in front of the right
person.

## AR14 — STILL OPEN. The hand-off's claim is incorrect.

The added assertion does not close mutation 6.

- `deployments/applications/services/dash/backend/tests/test_registry_sweep.py:186` = `    assert payload["models"][0]["tags"] == ["0.1.0", "latest"], (`

I re-ran the mutant (`_remember` keeps repo/tags/digest; the cached branch
`setdefault`s instead of assigning) as a pytest plugin loaded from
`.loop/scratch`, writing nothing to the repo tree: **83 passed, 3
deselected** — identical to baseline.

The reason is structural. `test_a_warm_sweep_fetches_no_manifest_and_no_blob`
replays the *same* `mount_modelkit()` fixture for both sweeps, so the stale
tags the mutant serves from the store are byte-identical to the fresh ones.
The assertion is a tautology under the mutant.

Positive control, proving the mutant is behaviorally real: a warm sweep
after `mount_modelkit(tags=("0.1.0", "latest", "1.0.0"))` passes on shipped
code and fails on the mutant with
`stale tags served from the store: ['0.1.0', 'latest']`.

**The shipped code is correct** — `registry_client.py:297` = `            row["tags"] = tags` assigns unconditionally, and `:327` = `        entry = {k: v for k, v in row.items() if k not in ("repo", "tags", "digest")}` strips them on the way in. No eval row is unmet, and no user-visible
behavior is wrong. To actually close it the test must vary the reference
between the two sweeps. Severity stays **low**; recorded, not required.

## AR15 — CLOSED.

- `deployments/applications/services/dash/backend/tests/test_main.py:205` = `    encoded = base64.b64encode(b"push:shibboleth").decode()`
- `deployments/applications/services/dash/backend/tests/test_main.py:206` = `    assert encoded not in raw`

That is the exact token `RegistryClient.__init__` puts on the wire
(`registry_client.py:60`), asserted absent from `/api/registry`,
`/api/status` and the served `index.html`, on top of the pre-existing
plaintext greps and the positive control. The eval row's "nor an
`Authorization` header value" is now covered.

## Settled findings, re-attacked rather than trusted

- **AR3** (walk coverage). Mutation 1 — fetch every layer, tolerate non-tar
  — re-run: **3 failed**, including
  `test_the_walk_never_fetches_a_weights_or_embark_layer`. Holds.
- **AR2** (failed sweep). Mutation 9 — bare re-raise — re-run: **1 failed**,
  `test_a_failed_sweep_serves_the_last_good_payload_with_the_error`. Holds.
- **AR1**. `services.tf:389-390` both `"0.3.0"`. Holds.
- **AR5**. `-m cluster` collects 3/86, deselected by default. Holds.
- **AR10**. Guard and `--self-test` both exit 0; no skip-auth key anywhere.
- **Reservations guardrail.** `dash.hcl` frontend `cpu = 50` / `memory = 32`,
  backend `cpu = 200` / `memory = 128`. Unmoved, as the eval row demands.

## An unasserted literal, checked at runtime

- `deployments/applications/services/dash/backend/src/dash_app/main.py:95` = `                {"models": [], "images": [], "error": "registry credential not rendered yet"}`

No test asserts this string and it is the only occurrence in the repo, so a
green stamp says nothing about it. I ran a reproducer from `.loop/scratch`
against a Config pointing at an absent credential file: `200`, body
`{"models":[],"images":[],"error":"registry credential not rendered yet"}`,
and no SQLite file created — `_build_sweep` short-circuits before
`create_schema`. The literal is accurate.

## Scope

Every changed line traces to the ticket. `secrets.tf` takes the Vault KV
write, `services.tf` the host volume and the upstream variable,
`oauth2-proxy.hcl` the third upstream, `dash.hcl` the volume mount, env and
credential template — each in the file the `one-file-per-subsystem` rule
names, with no new `.tf` file. `.loop/ledger.json` is harness bookkeeping
and its `review_entry_tree` matches the fingerprint I was given. Nothing
unrelated, no adjacent refactors.

## Non-blocking notes

- **AR17 (low).** Both footnotes state the common case as universal: a kit
  with no docs layer costs one blob, not two, and a multi-arch index costs
  none rather than the "one blob" the images note opens with. Each note's
  own later sentence covers the index case, and the mockup generalized the
  same way, so this is not a regression.
- **AR18 (low, cosmetic).** `index.html:997` composes the hint as
  `'registry unreachable: ' + data.error`, so the degraded-credential case
  reads "registry unreachable: registry credential not rendered yet". The
  registry is reachable; the template has not rendered. Honest, just
  misprefixed.
- **AR8, AR11** remain accepted as in cycle 1. `change_mode = "restart"` on
  the credential template covers rotation.

## What I read

`.loop/plans/L5-landing-registry-tab.md`,
`.loop/evals/L5-landing-registry-tab.md`, `.loop/ledger.json`,
`.pre-commit-config.yaml`, `assets/registry-mockup.html`,
`scripts/check_oauth2_proxy_guard.py`, `docs/dash-landing-page.md`,
`deployments/applications/secrets.tf`,
`deployments/applications/services.tf`,
`deployments/applications/services/dash.hcl`,
`deployments/applications/services/registry.hcl`,
`deployments/infrastructure/services.tf`,
`deployments/infrastructure/services/oauth2-proxy.hcl`,
`deployments/applications/services/dash/frontend/index.html`, and under
`deployments/applications/services/dash/backend/`: `pyproject.toml`,
`uv.lock`, `src/dash_app/config.py`, `src/dash_app/main.py`,
`src/dash_app/registry.py`, `src/dash_app/registry_client.py`,
`src/dash_app/registry_store.py`, `tests/test_cluster.py`,
`tests/test_main.py`, `tests/test_registry.py`,
`tests/test_registry_client.py`, `tests/test_registry_store.py`,
`tests/test_registry_sweep.py`.

Ledger: `.loop/scratch/L5-landing-registry-tab.adversarial/findings.json`,
18 findings. Mutants and reproducers were run from the session scratchpad
via `PYTHONPATH` and `-p`; no repo file was written and the tree
fingerprint held throughout.
