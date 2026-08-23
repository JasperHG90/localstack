---
verdict: pass
tree: 0eb318b976f808889f953340b1405b2f65196cac
bound_paths: .pre-commit-config.yaml, deployments/applications/justfile,
  deployments/applications/services.tf,
  deployments/applications/services/dash.hcl,
  deployments/applications/services/dash/Dockerfile,
  deployments/applications/services/dash/app/.gitignore,
  deployments/applications/services/dash/app/pyproject.toml,
  deployments/applications/services/dash/app/src/dash_app/__init__.py,
  deployments/applications/services/dash/app/src/dash_app/config.py,
  deployments/applications/services/dash/app/src/dash_app/frontend/index.html,
  deployments/applications/services/dash/app/src/dash_app/live.py,
  deployments/applications/services/dash/app/src/dash_app/main.py,
  deployments/applications/services/dash/app/src/dash_app/status.py,
  deployments/applications/services/dash/app/src/dash_app/tiles.py,
  deployments/applications/services/dash/app/tests/__init__.py,
  deployments/applications/services/dash/app/tests/test_cluster.py,
  deployments/applications/services/dash/app/tests/test_main.py,
  deployments/applications/services/dash/app/tests/test_status.py,
  deployments/applications/services/dash/app/tests/test_tiles.py,
  deployments/applications/services/dash/app/uv.lock,
  deployments/applications/services/dash/tiles.json,
  deployments/infrastructure/nomad_dash_read_role.tf,
  deployments/infrastructure/services.tf,
  deployments/infrastructure/services/oauth2-proxy.hcl,
  docs/dash-landing-page.md
scope: 5a435f64fc8311d90d19e3809225c40e8ec8b20e8df41f1efb1f1cb952244cda
citations:
  deployments/applications/services/dash/Dockerfile:18
  deployments/applications/services/dash/Dockerfile:28
  deployments/applications/services/dash.hcl:58
  deployments/applications/services/dash.hcl:69
  deployments/applications/services/dash/app/tests/test_cluster.py:18
  deployments/applications/services/dash/app/pyproject.toml:34
  docs/dash-landing-page.md:61
  docs/dash-landing-page.md:62
  docs/dash-landing-page.md:55
  docs/dash-landing-page.md:31
  docs/dash-landing-page.md:16
  deployments/infrastructure/nomad_dash_read_role.tf:25
  deployments/infrastructure/nomad_dash_read_role.tf:26
  deployments/infrastructure/nomad_dash_read_role.tf:31
---

# Documentation review: L3-landing-dash-app (cycle 2)

**Verdict: pass.** The three fixes applied since the cycle-1 PASS
(Dockerfile `--no-editable`, `dash.hcl`'s `.Data.secret_id` correction, and
the new `test_cluster.py`) are internal build/deploy mechanics and test
tooling; none of them are surfaces `docs/dash-landing-page.md` (or any
other repo doc) describes, so none left the docs stale. Re-run confirms the
slop scan is still clean and cycle 1's non-blocking observation still holds
unchanged.

## Cycle note (reviewer-brief resume rule)

`.loop/scratch/L3-landing-dash-app.documentation/findings.json` held nine
findings (`L3-DOC-1` through `L3-DOC-9`) from cycle 1
(`tree_fingerprint: 414d359e...`, `review_cycles: 1` per
`.loop/ledger.json`'s `L3-landing-dash-app` entry at review time). This
cycle re-attacked all nine (see below) and appended five new findings
(`L3-DOC-10` through `L3-DOC-14`) covering the fix-cycle diff. No trust
stamp is written: every check this pass ran was a cheap, read-only file
comparison (`grep`, `sed`, `git diff`, direct file reads), none over the
1-minute self-report threshold. A fail-first placeholder verdict
(`verdict: fail`) was written as the first act of this pass and is
overwritten in place by this file, per the brief's second rule.

## Re-attack of the tasked questions

1. **Does the "What the status backend can and cannot read" section (or
   anywhere else in `docs/dash-landing-page.md`) go stale from the
   Dockerfile/template fixes?** No, confirmed rather than assumed
   (`L3-DOC-10`, `L3-DOC-11`). The Dockerfile's `--no-editable` fix
   (`deployments/applications/services/dash/Dockerfile:18,28`) is a build
   detail: the doc's "Rebuilding and deploying the image" section only
   documents the `just rebuild_dash` / `just apply` command sequence and
   the image-tag source (`docs/dash-landing-page.md:55`), never `uv sync`
   flags or editable-install mode. `grep` across `docs/` and `README.md`
   for `no-editable` / `uv sync` / `editable` returns zero hits anywhere
   in the repo: no doc claimed the old (broken) behavior, so none needed
   updating. The `dash.hcl` template fix (`.Data.data.secret_id` to
   `.Data.secret_id`, `deployments/applications/services/dash.hcl:58,69`)
   is likewise untouched by any doc claim: the "What the status backend
   can and cannot read" section (`docs/dash-landing-page.md:61-67`)
   describes only the Nomad ACL grant
   (`read-job`/`list-jobs`/`node:read`, still matching
   `nomad_dash_read_role.tf:25,26,31` unchanged) and the
   tiles.json-vs-HAProxy-spec boundary, never the Vault template's
   field-access syntax in either its broken or fixed form. `grep -rln
   secret_id docs/` finds only `docs/nats-postgres-cdc-bridge.md`, an
   unrelated doc about a different secrets engine this diff never
   touches.
2. **Should `test_cluster.py` change how the doc describes testing?** No,
   confirmed non-blocking (`L3-DOC-12`). `docs/dash-landing-page.md`
   describes no test suite, marker, or verification procedure anywhere
   (`grep` for `test|pytest|verify|cluster` matches only the doc's own
   title, "the cluster landing page," and unrelated cluster-as-in-Nomad
   prose). The new `cluster` marker
   (`deployments/applications/services/dash/app/pyproject.toml:34`)
   mirrors `cli/pyproject.toml`'s identical, pre-existing marker
   (`cli/pyproject.toml:42`), which was itself never documented anywhere
   in the repo. The new test follows an established, already-undocumented
   convention rather than deviating from a documented one, so nothing
   here is a doc-staleness gap this diff introduced. Worth a human call on
   whether the repo should start documenting test markers in general, but
   that gap predates this diff and stays out of scope for this verdict.
3. **Slop scan re-run.** Clean, matching cycle 1 exactly (`L3-DOC-13`):
   415 words, 0 em dashes, 0 double-dash substitutions, 0 lines over 80
   chars, 0 actual smart-quote characters (checked with a Python regex
   over U+2018/2019/201C/201D, not the shell's ASCII-apostrophe
   false-positive), 0 prose semicolon splices, 0 tier-1 slop words, 0
   throat-clearing, 0 hedging seesaw, 0 not-just/not-only, 0
   spatial-copula slop, 0 genuine British spellings (the two raw `grep`
   hits were "behavior"/"color," already-correct American spellings
   caught by an optional-`u` pattern, not real findings). The file was
   not touched by this fix cycle, so this is confirmation, not new risk.
4. **L3-DOC-5 absence claim.** `docs/vault-human-auth.md` is absent from
   this cycle's changed-file set: `git status`/`git diff` show only the
   Dockerfile, `dash.hcl`, and the new `test_cluster.py` changed since the
   cycle-1 PASS. Re-read `vault-human-auth.md:9-33` and `:325-336` and
   confirmed the content is byte-identical to what cycle 1 cited (the
   "Logging in" section still documents CLI `vault login
   -method=userpass username=operator`
   (`docs/dash-landing-page.md:16` still points there), and the
   browser/SSO quirk paragraph at `:328-335` is unchanged). L3-DOC-5
   stands, unchanged and still non-blocking: the pointer is CLI-flavored
   rather than browser/SSO-flavored, factually usable rather than wrong,
   and this diff neither touched nor could have touched it.

## Re-attack of the original nine findings (all reconfirmed, no reversal)

`L3-DOC-1` (tile schema), `L3-DOC-2` (`rebuild_dash`/`just apply`),
`L3-DOC-3` (ACL grant), `L3-DOC-4` (SSO-quirk citation), `L3-DOC-6`
(no stale `OAUTH2_PROXY_UPSTREAMS` claim), `L3-DOC-7`
(`haproxy_reverse_proxy.md`'s pre-existing dash row), `L3-DOC-8`
(README's curated, non-exhaustive Applications list), and `L3-DOC-9`
(cycle-1 slop scan) all re-check clean against the current tree; none of
the files they anchor to (`nomad_dash_read_role.tf`, the justfile,
`tiles.py`, `docs/haproxy_reverse_proxy.md`, `README.md`) changed between
cycle 1 and cycle 2, so no re-derivation was needed beyond confirming
they are still untouched and still correct. Full detail for each is in
`.loop/scratch/L3-landing-dash-app.documentation/findings.json`.

## Non-blocking observation (carried forward, not required to fix)

`L3-DOC-5`: `docs/dash-landing-page.md:16` points at
`docs/vault-human-auth.md`'s "Logging in" section for "the login flow
itself," but that section documents CLI `vault login` for the lab's
single human operator, not the browser-driven Vault-UI OIDC/SSO redirect a
dash visitor actually completes (that flow is described instead at
`vault-human-auth.md:328-335`, separately and correctly cited for the
quirk). The section does supply the transferable facts a browser login
also needs, and this is a single-operator homelab where CLI and UI logins
share one identity, so the pointer is CLI-flavored, not factually wrong.
Unchanged from cycle 1; still non-blocking.
