---
verdict: fail
tree: dadc0099718d866d4a57b82b8bd71cc35ab8cd47
---

# Adversarial review, cycle 4 — L5-landing-registry-tab

Scope binding omitted deliberately: the briefing supplied a tree fingerprint
but no 64-hex scope digest and no `verdict_binding_inputs`. Per the reviewer
contract this falls back to whole-tree binding, which is stricter.

Deterministic floor: `loopctl verify-eval-substance L5-landing-registry-tab`
returns `valid`, exit 0, with no advisories. Proceeded to the semantic pass.

The architecture split is sound and I would have passed it. I cannot, for one
reason that is not about the code.

---

## BLOCKER — AR19: the tree moved during this review

`loopctl verify --expect-tree dadc0099718d866d4a57b82b8bd71cc35ab8cd47` exited
0 as my first act. The same command at the end of the pass:

    tree-mismatch: expected dadc0099718d866d4a57b82b8bd71cc35ab8cd47,
    got 47a15a75b19c4d19be03ee1044a8262d5b80c5f5

and `loopctl verify` now reports `stale: tree changed since the gates ran:
re-run loopctl stamp`. mtimes confirm the window:

    13:08:34  deployments/applications/services/registry-ui/frontend/index.html
    13:08:34  deployments/applications/services/registry-ui/frontend/nginx.conf
    13:08:59  scripts/check_oauth2_proxy_guard.py
    13:09:05  .pre-commit-config.yaml
    13:09:11  docs/dash-landing-page.md
    13:09:18  docs/haproxy_reverse_proxy.md

Every one of those is inside the review window, and three of them are files I
had already read and scored. The artifact I reviewed is not the artifact on
disk, and the tree on disk has not been through the gates.

This forecloses a pass by construction. A `pass` bound to `dadc0099…`
authorizes a tree that no longer exists. A `pass` bound to `47a15a75…` would be
a fingerprint I was never given and never reviewed against, which the reviewer
contract forbids outright. There is no third option, so the verdict is `fail`
on procedure regardless of the merits below.

The edits appear to be answering findings I raised in this pass (the guard
regex at `.pre-commit-config.yaml:83` now reads
`oauth2-proxy(-registry-ui)?\.hcl`, and the models footnote has been
rewritten). That is the right direction and I am not scoring it. It needs one
more stamp-and-dispatch cycle, not a rubber stamp on a tree I never saw.

---

## Confirmed on the reviewed tree

### HIGH — AR10 (REGRESSED): the oauth2-proxy guard guards the wrong file

`scripts/check_oauth2_proxy_guard.py:21`

    JOBSPEC = Path("deployments/infrastructure/services/oauth2-proxy.hcl")

and `.pre-commit-config.yaml:83` as reviewed

    files: '^(deployments/infrastructure/services/oauth2-proxy\.hcl|scripts/check_oauth2_proxy_guard\.py)$'

After the split, `/api/registry` is fronted by
`oauth2-proxy-registry-ui.hcl`, which the guard neither reads nor triggers on.
dash's proxy, the only file it checks, no longer has anything to do with the
registry view.

Proven by experiment in an isolated copy, not inferred. Adding
`OAUTH2_PROXY_SKIP_AUTH_ROUTES="/api/registry"` to
`oauth2-proxy-registry-ui.hcl` passes all 25 pre-commit hooks, the guard
included. Positive control: the identical key in `oauth2-proxy.hcl` fails the
guard with `auth exemption present: OAUTH2_PROXY_SKIP_AUTH_ROUTES`. So the
mechanism works and is simply pointed at the wrong target.

Eval row 11, a bolded guardrail, is unenforced for the service it now governs.
This is the single most serious code finding in the pass. The concurrent edit
at 13:09:05 appears to fix the regex; the script's hardcoded `JOBSPEC` at :21
is a second half that a regex change alone does not address, and I have not
reviewed either.

### HIGH — AR7 and AR15 (REGRESSED): the credential guardrail lost its scorer

Eval row 10, bolded, names `test_main.py`. Eval row 13 names it too. There is
no `test_main.py` under `deployments/applications/services/registry-ui/backend/tests/`.
dash's copy was correctly reverted to HEAD, taking the registry assertions with
it, and nothing replaced them:

    grep -rn "shibboleth\|b64encode\|Authorization\|credential" tests/   -> no output
    grep -rn "create_app\|Config"                                tests/  -> no output

`src/registry_ui/main.py` (69 lines) and `src/registry_ui/config.py` (61 lines)
have zero test coverage. `create_app`, `_build_sweep`, `registry_endpoint`,
`Config.from_env` and `read_registry_credential` are all unexercised.

The code is correct. A scratch reproducer against the real `create_app` shows
neither the plaintext password nor `base64("push:shibboleth")` in the
`/api/registry` body, and the degraded path returns 200 with
`{"models":[],"images":[],"error":"registry credential not rendered yet"}`
creating no db file. So this is a missing-scorer defect, not a leak: two
cycle-3 findings closed on evidence now have no evidence behind them.

### MEDIUM — AR12 (REGRESSED): the mockup's wrong arithmetic came back

`frontend/index.html:452-458`, byte-identical to
`assets/registry-mockup.html:452-458`:

    per distinct digest — `1 + R + T + 2D`, which is 21 requests and about
    1.2 s eight-way against this registry.

Re-deriving `index.html` from the mockup restored prose cycle 3 had removed.
The service's own test contradicts it —
`tests/test_registry_sweep.py:171-173` asserts three manifest operations per
digest (two tag HEADs plus one manifest GET) plus two blobs, so the shape is
`1 + R + T + 3D`, which is 25 for the live four-repo catalog, not 21. The
"about 1.2 s" figure is unverifiable and was cut for that reason. Rewritten at
13:08:34, after the reviewed fingerprint; unreviewed.

### MEDIUM — AR20: the docs described the abandoned design

On the reviewed tree `docs/dash-landing-page.md` asserted, among others, that
dash's backend does "status computation and the registry view" (dash is
byte-identical to HEAD), that the store sits "on the `dash_data` host volume
(`/var/lib/dash/registry.db`)" (it is `registry_ui_data` at
`/var/lib/registry-ui/registry.db`, `registry-ui.hcl:77,83`), that
`/api/registry` is "a third `OAUTH2_PROXY_UPSTREAMS` entry" (it is the second
entry on a second proxy), and that the credential is "dash's own copy at
`default/dash/registry`" (it is `default/registry-ui/registry`, `secrets.tf`).

The concurrent edit deleted the section outright and added no replacement, so
the new service now ships undocumented. Both states are wrong. The
documentation pass owns the remedy; I record it because the reviewed text made
false claims about a file I had just verified was untouched.

### LOW — AR21: three carried-over prose artifacts

`registry_store.py:1` still says "on the `dash_data` volume".
`oauth2-proxy-registry-ui.hcl:47-58` is dash's comment verbatim, explaining a
path-scoped upstream to "the backend's `/api/status`" and resting its
exact-match reasoning on "`index.html`'s one fetch call is an exact,
unparameterized `/api/status`". registry-ui's upstream is `/api/registry` and
its refresh button sends `/api/registry?refresh=1`, so the stated
justification no longer describes the traffic. Path-only matching should still
route it, but that is now an unverified case resting on a comment about a
different service. `check_oauth2_proxy_guard.py:4` and its stderr at :67 still
say "dash's registry view"; I confirmed that string by running the guard
against a mutated copy rather than reading it.

### LOW — AR14, AR17, AR18: carried forward unchanged

AR14 re-attacked and still open. Mutation D (`_remember` persists repo/tags,
`_entry` setdefaults instead of overwriting) leaves 47 passed, 1 deselected.
The warm sweep replays the same fixture, so the tags assertion at
`test_registry_sweep.py:186` is a tautology under the mutant. Shipped code is
correct; the test is weak. AR17 and AR18 unchanged, cosmetic, both re-verified.

---

## What I verified as sound (AR22)

The split itself is good work, and every structural claim in the hand-off
checked out independently.

**dash is fully reverted.** `git diff HEAD` on both
`deployments/applications/services/dash` and `dash.hcl` is empty, with no
untracked file underneath. The only `registry` hits in that subtree are PyPI
URLs in a pre-existing `uv.lock`. `oauth2-proxy.hcl` is byte-identical to HEAD,
so the parameterize-then-revert is clean. Eval row 12 (dash's reservations do
not move) is satisfied trivially.

**The mirror is faithful.** `registry-ui.hcl` differs from `dash.hcl` only in
ports (8002/8003), the volume stanza, the health-check path, and the credential
template. Own uv project, own four pre-commit hooks.

**The three guardrails survived the package move.** I re-ran all of them
against a copy outside the repo:

| Mutation | Result |
|---|---|
| `_entry` fetches every layer | 3 failures incl. `test_the_walk_never_fetches_a_weights_or_embark_layer` (5 blobs vs 2) |
| shared SQLite connection, `check_same_thread=False`, `close()` no-op | 19 failures on 3/3 runs, incl. both named store tests |
| blob cap moved outside the stream | `test_the_oversized_blob_is_abandoned_mid_stream_not_read_whole` fails, `assert 48 < 48` |
| bare re-raise on failed sweep (AR2) | `test_a_failed_sweep_serves_the_last_good_payload_with_the_error` fails |
| `areplace_tags` bypasses the offload (AR6) | `test_every_public_call_reaches_sqlite_through_the_thread_offload` fails |

**The frontend is the mockup.** All 418 lines of CSS are byte-identical. The
kit-card loop, modal, tab nav, copy buttons and theme toggle are preserved and
merely wrapped in `renderKits()`; the hardcoded `KITS` array is replaced by a
`/api/registry` fetch. Requirement 14/15 is met structurally. The one prose
regression is AR12 above.

**Routing and isolation hold.** 4180 and 4181 both on 192.168.2.50, both
hostnames under the `*.lab.orangecluster.nl` wildcard cert, both redirect URIs
on the OIDC client via locals. KV path `default/registry-ui/registry` matches
`job_id` under the `nomad-workloads` scope, so the `vault {}` block resolves.

**Layout rule honored.** No new `.tf` file; job in `services.tf`, KV write in
`secrets.tf`, volume in the infrastructure `services.tf`. A second oauth2-proxy
jobspec *file* is the per-service convention, not a violation of
`terraform-file-layout.md` — that rule governs `.tf` files in a Terraform root,
and `services/*.hcl` jobspecs are already one-per-service.

**Gates, re-run independently.** `pre-commit run --all-files` in an isolated
copy: 25/25 hooks pass, and a byte-diff confirms nothing was rewritten. I ran
it outside the repo because `end-of-file-fixer` and `nomad fmt -recursive`
write in place and would have moved the fingerprint. Backend suite: 47 passed,
1 deselected, matching the hand-off.

---

## On the stale plan and eval

It does not block, and leaving them is right. `eval-amend` and `eval-rebind`
both refuse inside a linked worktree by design, and hand-editing a signed
marker would bypass its audit. Two things for the operator to carry, though:

The `1 + R + T + B` = 21 count (AR13) is arithmetically wrong independent of
the architecture change. I re-derived it: the walk needs the manifest GET at
`registry_client.py:301` because `head_manifest` returns only a digest header,
so the true shape is `1 + R + T + 3D` = 25 live. The code is right and the plan
is wrong.

More consequential: rows 10 and 13 name `test_main.py` and row 11 names the
oauth2-proxy guard. Those two scorers are not merely stale prose — they are the
two findings above. The eval is the spec, and re-pointing it at the new
architecture is what would have caught both.

---

## Verdict

`fail`. AR19 alone is dispositive: the reviewed tree no longer exists, so no
verdict I write can honestly authorize what is on disk. AR10 and AR7/AR15 are
independently blocking on the tree I did review — a bolded guardrail whose
gate is pointed at the wrong file, and two more whose scorer was deleted in the
move.

I recognize this is cycle 4 at the cap, and I want to be plain about what I am
and am not saying. The architecture is right, the revert is total, the
guardrails survived, and the gates are green. This is not a rejection of the
split. It is a refusal to certify a tree that changed under me, with two real
regressions found in the version I could see. Re-stamp and dispatch once more,
or take it to the operator for an explicit acceptance of the remaining
findings — both are better than a green stamp on an artifact nobody reviewed.
