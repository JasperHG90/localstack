---
verdict: fail
tree: dadc0099718d866d4a57b82b8bd71cc35ab8cd47
---

<!--
SCOPE BINDING OMITTED, DELIBERATELY. The cycle-4 briefing gave a tree
fingerprint but no 64-hex scope digest and named no verdict_binding_inputs.
The floor is not mine to choose and I must never write a digest I computed
for a set I chose, so the three lines (bound_paths / scope / citations) are
omitted and this verdict falls back to the whole-tree binding, which is
stricter. Cycle 3 recorded the same condition
(.loop/scratch/L5-landing-registry-tab.documentation/trust-stamp.json:
"scope_digest_given": null).
-->

# Documentation pass — cycle 4 (at the cap) — FAIL

The docs do not match the tree. `docs/dash-landing-page.md` documents a
registry view that dash no longer has, the new `registry-ui` service has no
doc at all, and the shipped UI carries a request-cost formula that
contradicts the shipped code. Below is the exact scope, in the order you
asked for it.

Gates were not re-run: the cycle-3 trust stamp is keyed to tree
`d45829a41796e91fe032eecc4642aef015363b37` and does not apply to this one,
and re-running gates is not this pass's job. Every ad-hoc run below was
bounded with `timeout`. No mutating git command was run.

---

## 1. What must be removed from `docs/dash-landing-page.md` — DOC-14, high

`deployments/applications/services/dash/` is byte-identical to HEAD
(`git diff HEAD -- deployments/applications/services/dash` prints nothing),
so every sentence the cycle-2/3 edits added describes a feature dash does
not have. **The correct target is HEAD's version of the file, byte for
byte.** Three ranges, and they are provably complete:

**(a) Lines 12-13 → one line.** Delete the `(status computation and the
registry view)` phrase.

- Current `docs/dash-landing-page.md:12` = ``and a `backend` task (status computation``
- Current `docs/dash-landing-page.md:13` = ``and the registry view). The backend carries its own``
- Replace both with the single HEAD line:
  ``and a `backend` task (status computation). The backend carries its own``

**(b) Lines 35-138 → delete entirely (104 lines).** This is the whole
registry block, including the two subsections you named and the blank line
that separated it from the next heading:

| Range | What it is |
|---|---|
| 35-63 | `## The registry tab` heading and its four paragraphs, including the `1 + R + T + D + B` = 25 / 13 costs at :48-49 and the `B` breakdown at :52-59 |
| 64-82 | `### Why it stays cheap` — the `dash_data` SQLite store, the sweep, the 1 MiB blob cap |
| 83-123 | `### What it costs, and when that stops being true` — server-side render, eight-way bound, `asyncio.to_thread`, `If-None-Match`, the scaling ceiling, both escape hatches |
| 124-137 | `### Reaching it` — the third upstream and the `default/dash/registry` credential |
| 138 | the trailing blank line before `## Adding or removing a tile` at :139 |

Boundary anchors, verified: `docs/dash-landing-page.md:35` = `## The
registry tab`; `docs/dash-landing-page.md:137` = `so reading the registry's
own path would 403.`; `docs/dash-landing-page.md:139` = `## Adding or
removing a tile`.

**(c) Lines 182-192 → restore HEAD's lines 77-85.** Back to one fetch and
two upstreams.

- Current `docs/dash-landing-page.md:182` = ``` `index.html` makes two same-origin calls, `fetch('/api/status')` and ```
- Current `docs/dash-landing-page.md:187` = `loopback port (8000), plus one path-scoped upstream per API route, both`
- Restore verbatim from `git show HEAD:docs/dash-landing-page.md`, lines
  77-85, which read "makes one same-origin call", "a second upstream scoped
  to `/api/status`", and "which is exactly what the one fetch call needs".

The section heading at :180 (`## How the browser reaches two tasks through
one route`) is unchanged in the diff and stays as is.

**Proof the three ranges are exactly sufficient.** I reconstructed the file
by applying (a), (b) and (c) and diffed the result against
`git show HEAD:docs/dash-landing-page.md`. The diff is empty. Nothing else
in the file drifted, and nothing outside those ranges needs touching.
Artifacts left at
`.loop/scratch/L5-landing-registry-tab.documentation/head-dash.md` and
`restored-dash.md`.

---

## 2. The new doc: `docs/registry-ui.md` — DOC-19, high

`docs/registry-ui.md` is the right path and the right shape: a top-level
service doc beside `docs/dash-landing-page.md`, following the same section
order. Nothing in `docs/` or `README.md` names the service today.

Requirement 22 (`.loop/plans/L5-landing-registry-tab.md:1062-1074`) is
still the topic list; the split changes four of its items. Take each fact
from the anchor beside it, not from memory.

### Requirement 22 items that carry over UNCHANGED

| Topic | Verified against |
|---|---|
| `1 + R + T + D + B` = 25 cold, `1 + R + T` = 13 warm, four repos | `registry_client.py:243-281` (the walk); `tests/test_registry_sweep.py:169-172` asserts 1 catalog + 1 tag list + 3 manifest URLs + 2 blobs at R=1 T=2 D=1 |
| `B` differs by digest kind: ModelKit 2 (Kitfile + `README.md`), image 1 (config blob), index 0 | `registry_client.py:312-319` / `:303-308` / `:305-306`; tests at `:160`, `:172`, `:246-247`, `:267-269` |
| digest-keyed `cards` row, never invalidated, only evicted | `registry_store.py:44-50`, `:5-6`; eviction at `test_registry_sweep.py:277-284` |
| 8-way bounded concurrency, `httpx.Limits(max_connections=8)` + matching semaphore | `registry_client.py:42`, `:67`, `:244` |
| every DB call crosses `asyncio.to_thread`, each opening its own connection | `registry_store.py:54-56`, `:159-177`, and the trap note at `:7-13` |
| `If-None-Match` buys time, not requests (147 ms vs 181 ms; count unchanged) | `registry_client.py:134`, `:142` |
| 1 MiB blob cap, counted as it streams | `registry_client.py:41`, `:105-107` |
| scaling ceiling (~25 comfortable, ~50 strained, ~100 breaks) and both escape hatches (`notifications.endpoints`, Redis) | prose carried from the deleted `:105-123` |
| `embark.json` is listed as a layer and never parsed | prose carried from the deleted `:57-59` |
| server-side render with `markdown-it-py`, once per digest | `pyproject.toml:8`; `registry_client.py:292` (cache before manifest) |

### Requirement 22 items that CHANGED with the split — rewrite, do not copy

1. **The volume.** Not `dash_data` and not `/var/lib/dash/registry.db`. It
   is the `registry_ui_data` dynamic host volume
   (`deployments/infrastructure/services.tf:197-213`, 100 MiB min / 1 GiB
   max on `radxa-dragon-q6a`), mounted at `/var/lib/registry-ui`
   (`registry-ui.hcl:75-78`), with the database at
   `registry-ui.hcl:83` = `REGISTRY_DB_PATH = "/var/lib/registry-ui/registry.db"`.
2. **The credential.** Not `default/dash/registry`. It is
   `deployments/applications/secrets.tf:109` =
   `name  = "default/registry-ui/registry"`, rendered to
   `/secrets/registry.json` by `registry-ui.hcl:94-102`. The 403 reasoning
   is unchanged and worth keeping: `nomad-workloads` scopes a job to
   `secret/data/default/<job_id>/*`, so reading `default/registry/auth`
   would 403. Keep the "reads through `registry.lab.orangecluster.nl`, not
   the registry's own port" sentence — still true
   (`services.tf:415-417`).
3. **Reaching it.** Not "a third `OAUTH2_PROXY_UPSTREAMS` entry" on dash's
   proxy. registry-ui has **its own oauth2-proxy instance**,
   `oauth2-proxy-registry-ui.hcl`, listening on
   `oauth2-proxy-registry-ui.hcl:38` = `static = 4181`, with exactly two
   upstreams: `deployments/infrastructure/services.tf:555` =
   `frontend_upstream = "http://127.0.0.1:8002"` and `:556` =
   `backend_upstream  = "http://127.0.0.1:8003/api/registry"`. HAProxy
   routes `registry-ui.lab.orangecluster.nl` to it
   (`haproxy.hcl:109`, `:122`, `:184` = `server registryui1
   192.168.2.50:4181 check`). Say plainly that the exact-match rule still
   holds and that `/api/registry/` with a trailing slash would fall through
   to the frontend.
4. **The no-skip-auth rule and the webhook caveat.** Keep the caveat, but
   state the guard's real reach honestly: `scripts/check_oauth2_proxy_guard.py:21`
   pins `JOBSPEC` to `oauth2-proxy.hcl` alone, so the guard does **not**
   cover this service's proxy today (DOC-18). Do not write a sentence that
   claims it does.

### Topics dash's doc never had to cover, and this one does — DOC-24

5. **The service is its own job, not a section on dash.** Two tasks,
   `frontend` (8002) and `backend` (8003), on `radxa-dragon-q6a`, own image
   pair, own SQLite store, own proxy. Say why: neither service can take the
   other down (`deployments/applications/services.tf:403-406`).
6. **A second oauth2-proxy instance is new in this repo.** Name what it
   shares and what it does not: the SAME Vault OIDC client and cookie
   secret (`services.tf:547-548`), a DIFFERENT redirect URI
   (`oidc.tf:430` = `local.registry_ui_redirect_url,`), a different listen
   port, different upstreams. Name the second redirect URI on the one
   client explicitly, because `docs/vault-human-auth.md:268-276` tells a
   reader adding a service to create its own
   `vault_identity_oidc_client`, and this deliberately did not.
7. **The hostname.** `https://registry-ui.lab.orangecluster.nl`. No DNS or
   TLS work: the wildcard covers it (`docs/dns.md:18-19`).
8. **The 30 s sweep floor.** `registry_client.py:205` =
   `floor_seconds: float = 30.0`. The browser polls every 60 s
   (`frontend/index.html:762` = `var POLL_MS = 60000;`) while the tab is
   visible (`:794-796`), and the `refresh` button forces a sweep past the
   floor (`:791`, `registry_client.py:217-219`). Dash's doc never had a
   floor to describe.
9. **Rebuild and deploy.** Mirror dash's "Rebuilding and deploying the
   images" section: `just rebuild_registry_ui_backend`,
   `just rebuild_registry_ui_frontend`, `just apply`
   (`deployments/applications/justfile:61-81`). Tags are read out of
   `deployments/applications/services.tf:411-412`, so bump them there
   first. Cite the versions as placeholders, never a literal `0.1.0`
   (DOC-10).
10. **Degraded behavior.** An unreachable registry returns the last good
    payload with an `error` field beside it rather than emptying the tab
    (`registry_client.py:222-241`, `main.py:47-53`;
    `test_registry_sweep.py:293-299`). An unrendered Vault template yields
    an empty payload with an error, not a 500 (`main.py:42-45`,
    `config.py:42-48`).
11. **The `cluster` test marker.** `pyproject.toml:33-36` excludes
    `tests/test_cluster.py` from the default run; it is the only test that
    touches the live registry. Run it on purpose with `-m cluster`.

---

## 3. What else in the repo now describes a world that does not exist

### DOC-15, high — the shipped UI states the wrong cost model

`deployments/applications/services/registry-ui/frontend/index.html:455` =
`per distinct digest &mdash; <code>1 + R + T + 2D</code>, which is 21 requests and about`

The whole footnote (`:452-458`) also says "then a manifest per tag". Both
are the mockup's numbers, and both are wrong against the code that shipped:
the walk `HEAD`s per tag and GETs a manifest only per distinct digest the
store lacks (`registry_client.py:283-292`, cache consulted before the
manifest), giving `1 + R + T + D + B` = 25 cold and 13 warm. Cycle 3 closed
DOC-11 because this text had NOT reached dash's `index.html`. It reached
this one. This is user-facing prose on the page itself, so it outranks the
markdown doc in blast radius. Fix it to match, or drop the formula and keep
only the qualitative claim.

The images footnote at `:468-472` is accurate; leave it.

### DOC-16, medium — `docs/haproxy_reverse_proxy.md` is now an incomplete routing table

`docs/haproxy_reverse_proxy.md:24` =
`| `dash.lab.orangecluster.nl` | radxa-dragon-q6a (192.168.2.50) | 4180 |`

The table at `:13-24` needs one more row:
`| registry-ui.lab.orangecluster.nl | radxa-dragon-q6a (192.168.2.50) | 4181 |`,
because `haproxy.hcl:109` adds `acl is_registryui`, `:122` adds
`use_backend registryui`, and `:183-184` adds the backend. The gating
paragraph at `:26-32` — `docs/haproxy_reverse_proxy.md:28` = `HAProxy no
longer gates it. `dash` sits behind oauth2-proxy, gated by Vault` — names
only dash and should name registry-ui too, on its own proxy instance.
This overturns half of cycle-2's DOC-8 absence claim.

### DOC-17, medium — the copied proxy's comment describes dash's route

`deployments/infrastructure/services/oauth2-proxy-registry-ui.hcl:47` =
`      ### OAUTH2_PROXY_UPSTREAMS below carries two upstreams for dash's`

`:47-58` is a verbatim copy of dash's block. `:49-50` says the path-scoped
upstream points at "the backend's `/api/status`"; `:55-56` says
"`index.html`'s one fetch call is an exact, unparameterized
`/api/status`". This job's backend upstream is `/api/registry`
(`services.tf:556`). The routing is right; the prose sends a reader to the
wrong route. Keep the measured exact-vs-prefix finding, which is still the
reason this shape works, and change the route it names.

Also `oauth2-proxy-registry-ui.hcl:7` = ``### Reusable pattern: R1 (MLflow)
and R4 (Phoenix) copy this job. Keep`` — inside the copy this reads as if
this file were the pattern. Point it back at `oauth2-proxy.hcl`.

### DOC-18, medium — the guard promises more than it enforces

`scripts/check_oauth2_proxy_guard.py:21` =
`JOBSPEC = Path("deployments/infrastructure/services/oauth2-proxy.hcl")`

and `.pre-commit-config.yaml:83` scopes the hook to that one file plus the
script. Meanwhile `scripts/check_oauth2_proxy_guard.py:4` = `dash sits
entirely behind oauth2-proxy, and it does so because the jobspec` and `:67`
= `"dash's registry view and its route must stay behind oauth2-proxy's "`.
The proxy that actually gates the registry view is now
`oauth2-proxy-registry-ui.hcl`, which the script never reads and the hook
never fires on. Either widen `JOBSPEC` to both files and the `files:`
regex with it, or rewrite the docstring and the stderr so they stop
claiming a guarantee that does not reach the new service. Do not leave the
prose as it stands.

### DOC-12 — RE-CHECKED against the original file, and CLOSED there

You asked me not to assume this one. `git diff HEAD --
deployments/infrastructure/services/oauth2-proxy.hcl` prints nothing, and
its comment at `deployments/infrastructure/services/oauth2-proxy.hcl:46` =
`      ### OAUTH2_PROXY_UPSTREAMS below carries two upstreams for dash's`
is **accurate again** now that dash is reverted: two upstreams, one exact
unparameterized `/api/status` fetch, three sentences that all hold. Cycle
3's finding is closed on the original. It moves to the copy as DOC-17.

### DOC-20, low — three stale module docstrings in the new backend

`deployments/applications/services/registry-ui/backend/src/registry_ui/registry_store.py:1`
= `"""The registry view's persisted store, on the dash_data volume.` — the
volume is `registry_ui_data`.

`.../registry_client.py:4` = ``\`_http.py\` stays the sync, JSON-only helper
\`/api/status\` depends on.`` — this app serves only `/api/registry`
(`main.py:57`).

`.../_http.py:1` = `"""Minimal HTTP GET helper for the backend's own
Nomad/Consul calls.` and `:7` = ``app has no login flow to prompt through:
\`main.py\`'s \`/api/status\` handler`` — this backend makes no Nomad or
Consul call, and only `FetchError` is imported from that module;
`get_json` is unused here. Docstrings are API surface under the repo's
minimal-comments rule, so these count.

### DOC-21, high — the frontend's nginx comment and its listen port name dash

`deployments/applications/services/registry-ui/frontend/nginx.conf:1` =
``# Listens on the frontend task's own port (dash.hcl's group-level \`http\``
and `:5` = `    listen 8000;`

The file is a byte-copy of dash's. The registry-ui job allocates 8002
(`registry-ui.hcl:13` = `        static = 8002`) and the proxy dials
`http://127.0.0.1:8002` (`services.tf:555`). With `network_mode = "host"`
on the same node as dash, the container listens on 8000, so the proxy
reaches nothing and the port collides with dash's frontend.
`frontend/Dockerfile:10` = `EXPOSE 8000` is the cosmetic half. I raise it
here because the comment is wrong; the port itself is the adversarial
pass's to confirm, and it should not ship either way.

### DOC-22, low — the firewall comment and rule still know one proxy

`deployments/infrastructure/services.tf:390` = `      rules    = ["allow
from 192.168.2.30 to any port 4180 proto tcp"]`, under a comment at
`:384-386` naming "oauth2-proxy on radxa-dragon-q6a (L1)" in the singular.
Port 4181 is not opened, though `haproxy.hcl:184` dials it. Same call as
DOC-21: the comment is mine, the missing rule is the adversarial pass's.

Separately, `deployments/infrastructure/services/oauth2-proxy.hcl:6` =
`### Reusable pattern: R1 (MLflow) and R4 (Phoenix) copy this job. Keep` —
this now has its first actual copy, and naming
`oauth2-proxy-registry-ui.hcl` there turns an aspiration into a pointer.
That is the item 4 you asked about, and it is worth the line.

### DOC-23, low — `oidc.tf`'s block header and an unrecorded choice

`deployments/infrastructure/oidc.tf:407` = `### --- L1: oauth2-proxy
(landing page gate) ---------------------------------`. The block now
carries two redirect URIs on one client (`:429-430`) and gates two
hostnames. Nothing records why a second redirect URI rather than a second
`vault_identity_oidc_client`, which is what
`docs/vault-human-auth.md:268-276` tells a reader to create. An absence is
exactly what a comment is for.

### Swept and CLEAN — do not touch these

- `README.md` — `:14` lists applications and never listed dash either;
  `:62` describes pre-commit generically and never enumerated dash's
  hooks. No drift introduced by this diff. Do not add a service list the
  README never had.
- `docs/dns.md` and `docs/tls-certificates.md` — wildcard-based
  (`docs/dns.md:18-19`), so a new hostname needs no entry.
- `docs/monitoring.md:405` — that "Dynamic host volumes" list is a
  prometheus/grafana plan section, not a repo-wide inventory.
- `docs/vault-human-auth.md:42` — names `oidc.tf`'s CLIENTS, and no client
  was added.
- `docs/credential-rotation.md` — never covered the registry credential;
  do not invent a section for it.
- No repo-wide host-volume, port or Vault-path inventory doc exists. Do not
  create one to hold `registry_ui_data`, 4181, or
  `default/registry-ui/registry`.

### Carried, not blocking — DOC-13

`.loop/plans/...:292-294, :802-803, :3169-3170` and `.loop/evals/...:20`
still state `1 + R + T + B` = 21. The split adds two more: Requirement 22
(`plan:1062-1074`) names `docs/dash-landing-page.md` as the doc to write,
and Requirement 23 (`plan:1075-1080`) names a `dash_data` volume. All four
are harness artifacts, not the repo's documentation set, and the marker is
signed, so hand them to the integrator for `loopctl eval-amend` from the
primary worktree rather than hand-editing.

---

## Ledger

23 entries at
`.loop/scratch/L5-landing-registry-tab.documentation/findings.json`. Cycle
4 re-attacked all thirteen prior findings: DOC-11 and DOC-12 overturned on
fresh evidence, DOC-8 partially overturned, DOC-1 through DOC-7 and DOC-9
marked moot-in-place with their facts carried into the DOC-19 content list,
DOC-10 and DOC-13 re-confirmed as absence claims. New: DOC-14 through
DOC-24.

**Verdict: fail.** Three items are enough on their own: `docs/dash-landing-page.md`
describes a feature dash does not have (DOC-14), the new service ships with
no doc (DOC-19), and the shipped page states a request cost the shipped
code contradicts (DOC-15).
