---
verdict: pass
tree: eb35aca72cef9675632137d49838c5d3d5b30a76
---

# OV1-openviking-service — adversarial, cycle 4 (delta re-bind)

**No scope-binding lines.** My briefing carried a tree fingerprint but no
`scope:` digest, no bound path set and no `verdict_binding_inputs`. Writing a
digest I computed myself would bind a set nobody asked me to review, so the
three lines are omitted and this verdict falls back to the whole-tree binding,
which is stricter. Same as cycles 1, 2 and 3.

## Deterministic floor

`loopctl verify-eval-substance OV1-openviking-service` → `valid`, exit 0, no
hard-fails and no advisories. `loopctl verify --expect-tree eb35aca7…` → `ok`,
exit 0, taken from the briefing rather than derived from the tree. Proceeded to
the semantic pass.

## Gate

Re-run on THIS tree, not trusted from the cycle-3 stamp (its fingerprint
`4312c61e…` differs, so the brief requires the re-run): `just pre_commit`
exit 0, every hook Passed. The two openviking hooks again report
`(no files to check) Skipped` under `--all-files`, because `openviking.hcl` and
`check_openviking_config.py` are untracked and `pre-commit run --all-files`
walks `git ls-files`. Forced every hook over all 19 new and changed paths with
`pre-commit run --files …`: exit 0, with `openviking config holds its measured
values` and its `--self-test` both **Passed**. Stamp rewritten at
`.loop/scratch/OV1-openviking-service.adversarial/trust-stamp.json`.

## Verdict

**Pass.** All four delta edits are real and correct. The DOC-19 bug was a
genuine defect in my own earlier A14 fix, and the correction now delivers the
header — proven at runtime, not read off the page. Nothing in the delta
stranded prose that argued for the old state; I hunted the pattern a fourth
time and the one hit I found is non-falsifying and matches a class I already
ruled not-required. My three carried advisories remain open and remain
non-blocking. Bind and commit.

---

## The four edits

### 1. A15 — the host-volume comment. CLOSED.

`deployments/infrastructure/services.tf:217` now reads:

```
### OpenViking's workspace and RAGFS's local scratch.
```

The `its OAuth SQLite db` clause is gone, and the twin at
`deployments/applications/services/openviking.hcl:32` now agrees:
`### Holds ov.conf's workspace and RAGFS's local scratch. The vectors live`.
The two anchors no longer disagree about the same volume.

The claim the clause made was false, which is why deleting it was the right fix
rather than propagating it: OpenViking's `OAuthConfig.enabled` defaults to
`False` and `app.py` gates the `OAuthStore` and every `/oauth` route behind
`if ov_cfg.oauth.enabled:`, and the rendered `ov.conf` carries no `oauth` key,
so the SQLite db is never created.

Swept the whole tree outside `.loop/` for surviving OAuth-db prose: zero hits.
`docs/openviking.md:36-39` ("OpenViking's own OAuth 2.1 implementation is
**off**") corroborates the deletion rather than contradicting it.

### 2. A16 — the `--no-deps` comment. CLOSED, counts and claim now right.

`Dockerfile.openviking:36-39` now reads:

```
# whose whole purpose is a reproducible pin. ov_postgres needs openviking and
# pydantic, which the base image carries, plus psycopg and psycopg_pool, which
# RUN #2 supplies. Do not strip `pool` from RUN #2 as redundant: the adapter
# imports ConnectionPool at startup.
```

I did not take the accounting on trust. I fetched all six modules of
`ov_postgres` at tag `ov-postgres-v0.2.0` and enumerated every top-level import
across the package. The complete third-party set is exactly four:
`openviking`, `psycopg` (including `psycopg.rows`), `psycopg_pool`, `pydantic`.
Nothing else. So:

- base image carries **two** — `openviking`, `pydantic` (both in OpenViking
  v0.4.17.1's `uv.lock`). Was wrongly "three".
- RUN #2 supplies **two** — `psycopg` and `psycopg_pool`, via
  `psycopg[binary,pool]==3.2.3`, whose metadata declares
  `psycopg-pool; extra == "pool"`. Was wrongly "psycopg" alone.

The new warning is also correct and is the part that matters: `adapter.py:28`
is `from psycopg_pool import ConnectionPool` at **module level**, so "imports
ConnectionPool at startup" is accurate — OpenViking resolves the dotted backend
with `importlib`, which executes that import. A reader who stripped `pool` as
redundant would break the server at first collection open. That hazard is now
written down where the temptation lives.

The cited precedent is verbatim correct: `Dockerfile.embark:32-33` is
`# --no-deps: every transitive dependency is already in the venv from the base`
/ `# image, and resolving them again here would pull CPU wheels back in.`

The flag itself is untouched — `Dockerfile.openviking:40` still carries
`--no-deps`, so A13's closure stands. Only the comment moved.

### 3. DOC-19 — the ssh header check. CLOSED, and it was a real bug.

`docs/openviking.md:109-111` is now one single-quoted remote string:

```
$ ssh radxa@192.168.2.50 'curl -s -o /dev/null -w "%{http_code}" \
    -H "Authorization: Bearer <token minted for another client>" \
    http://127.0.0.1:1933/api/v1/collections'   # expect 401
```

This is a literal no gate exercises, so I checked it against runtime rather
than scoring it from the diff. Reproducer built entirely in the scratchpad,
outside the repo tree: a local `http.server` that logs the `Authorization`
header, plus a shim reproducing ssh's exact semantics (join the post-host argv
with spaces, hand the result to a remote `sh -c`).

| Form | What the server received | stdout |
|---|---|---|
| **Fixed** (`:109-111`) | `Authorization='Bearer TESTTOKEN'` | `401` |
| **Old, unquoted** | `Authorization=None` | `000000401` |
| **`/ready`** (`:97`) | reached, unchanged | `401` |

The fix works: the header is delivered. And the old form failed exactly as the
new comment says. `000000401` is three `-w` outputs, not one: curl received
`-H Authorization:` (header removal) plus `Bearer` and `TESTTOKEN` as two stray
URLs that fail with `000` each, then the real URL's `401`. An operator reading
the tail of that output sees `401` and concludes the check passed while no
token was ever sent. That is a test that greens on nothing, and it is now gone.

The trap is recorded at `:105-108`, and every clause of it is accurate:
ssh does join argv with spaces and hand the result to a shell; `-H
Authorization:` is how curl removes a header; the result is a plain
unauthenticated 401. The mechanism that makes the fix work is that a backslash
inside single quotes is not a local escape, so the continuations arrive at the
remote shell intact and are consumed there, with the inner double quotes
surviving to keep the header one argv element.

Two further checks, since a doc command is run by hand and gets no second
chance:

- **The neighbouring `/ready` line at `:97` is still correct.** It carries no
  quotes and no shell metacharacters (`:` and `/` are not), so it re-parses to
  the identical three words. Confirmed against the server.
- **Run verbatim with the placeholder left in, it is safe.** I executed the
  fixed line with `<token minted for another client>` unsubstituted. The angle
  brackets sit inside the double quotes inside the single quotes, so no
  redirection fires and no stray file is created on the node. Exactly one URL
  is fetched, which is itself corroboration that the argv is right.

### 4. DOC-9 — the consumer-client list. Correct and complete.

`docs/vault-human-auth.md:42` gains `openviking`. `deployments/infrastructure/oidc.tf`
declares exactly six `vault_identity_oidc_client` resources: `smoke` (:160 —
the "one throwaway smoke-test client" the row names separately), `nomad`
(:222), `memex` (:384), `oauth2_proxy` (:425), `openviking` (:462), `grafana`
(:500). The parenthetical is an exact set match. Order differs from file order
and is not a claim. It is the only consumer-client enumeration in `docs/`.

---

## What the delta could have broken

I re-ran the stranded-prose hunt across the whole tree, since every previous
cycle turned one up. One hit, and it does not block.

### OV1-A18 (LOW, advisory) — a proxy count the delta made non-exhaustive

`deployments/infrastructure/secrets.tf:260-261` reads
`### redirect URIs, and one cookie secret. The two proxies gate different` /
`### hostnames, so their cookies never collide.`, and `:252` says `### Not
duplication for its own sake: both proxies declare a bare vault {},`. Three
jobs now share `random_password.oauth2_proxy_cookie_secret`.

**Not required, and I am saying so explicitly so the next cycle does not
re-litigate it.** Nothing here becomes false:

- `one OIDC client carrying both redirect URIs` is still literally correct.
  `oidc.tf:429-432` still lists exactly two, because openviking got its **own**
  client at `:462` rather than a third redirect URI on the shared one.
- The two-proxy statements remain true *of those two*. They are non-exhaustive,
  not wrong.
- The invariant for the newcomer is restated at the newcomer's own site,
  `secrets.tf:296-298`, which is where a reader looking at that resource lands.

This is the same shape as OV1-A17, which I already ruled not-required, so
requiring it here would be inconsistent with my own standard. Contrast OV1-A8,
which I *did* require in cycle 3: there `storage.tf` asserted openviking had no
Vault KV entry while the diff gave it one — a flatly false statement. The
author has already fixed the counts in this class that were load-bearing:
`services.tf:409-411` now reads "Three proxies, three ports", and
`docs/haproxy_reverse_proxy.md` now names all three.

### Everything else in the diff is unchanged from the tree I passed

I re-read the full diff of every tracked modified file and confirmed no hunk
moved except `services.tf:217` and `vault-human-auth.md:42`. The image build,
the OIDC chain, R11/R13, the checker, the `ov.conf` templating and the
`storage.tf` scope call are as cleared and were not re-derived, per the
briefing.

---

## Carried advisories — all three still open, all three still non-blocking

Re-attacked, not rubber-stamped. None should hold this commit.

- **OV1-A10 (LOW).** `grep -c openviking_base_image` in `openviking.hcl` is
  still `0` while `services.tf:405` passes it as a `templatefile` variable.
  `templatefile` tolerates unreferenced vars and `terraform validate` passes.
  The pin still does its job: `services/openviking/justfile:24` greps that line
  out of `services.tf`, and `:45`/`:49` guard a missing value and a `:latest`
  tag. Cosmetic placement.
- **OV1-A12 (INFORMATIONAL).** Absence claim, no change in scope. R1's radxa
  headroom precondition is still unretired; `grep` for
  `headroom|memory_max|1536|2560` in `docs/openviking.md` returns nothing. A
  deploy-time obligation, not a commit gate.
- **OV1-A17 (INFORMATIONAL).** `check_oauth2_proxy_guard.py:4` still says
  "dash and registry-ui each sit entirely behind their own oauth2-proxy" while
  three jobspecs exist. The operative sentence two lines down — "over every
  oauth2-proxy jobspec in the repo" — is correct, the hook's `files:` pattern
  covers all three, and P2 proved the guard fires on the new jobspec.
- **OV1-A11 (LOW, settled).** Checker untouched by the delta. Forced
  `openviking-config-guard` and its `--self-test` over the untracked paths:
  both Passed. Holds as recorded.

---

## Evidence anchors

- `deployments/infrastructure/services.tf:217` = `### OpenViking's workspace and RAGFS's local scratch.`
- `deployments/applications/services/openviking.hcl:32` = `    ### Holds ov.conf's workspace and RAGFS's local scratch. The vectors live`
- `deployments/applications/services/openviking/Dockerfile.openviking:38` = `# RUN #2 supplies. Do not strip `pool` from RUN #2 as redundant: the adapter`
- `deployments/applications/services/openviking/Dockerfile.openviking:40` = `RUN /usr/local/bin/python3.13 -m pip install --no-deps --upgrade \`
- `docs/openviking.md:107` = `# `-H Authorization:`, which is how curl REMOVES a header, and would report`
- `docs/openviking.md:109` = `$ ssh radxa@192.168.2.50 'curl -s -o /dev/null -w "%{http_code}" \`
- `docs/vault-human-auth.md:42` = `| `oidc.tf` | The OIDC signing key, the shared `groups` and `email` scopes, the provider, one throwaway smoke-test client, and the consumer clients added since (nomad, memex, oauth2-proxy, grafana, openviking) |`
- `deployments/infrastructure/oidc.tf:462` = `resource "vault_identity_oidc_client" "openviking" {`
- `deployments/infrastructure/secrets.tf:260` = `### redirect URIs, and one cookie secret. The two proxies gate different`
- Upstream, tag `ov-postgres-v0.2.0`, `src/ov_postgres/adapter.py:28` = `from psycopg_pool import ConnectionPool`

Ledger updated at `.loop/scratch/OV1-openviking-service.adversarial/findings.json`
(27 entries): A15 and A16 closed, A13/A14 re-attacked and their closures
upheld, A10/A11/A12/A17 re-confirmed open and non-blocking, P7 and P8 added as
verified-clean, A18 added as advisory.
