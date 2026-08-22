---
verdict: pass
tree: 983d3fcfbf8ea9630fb484dc11ab6f1e11afd1cb
bound_paths: deployments/infrastructure/oidc.tf, deployments/infrastructure/secrets.tf, deployments/infrastructure/services.tf, deployments/infrastructure/services/haproxy.hcl, deployments/infrastructure/services/oauth2-proxy.hcl, docs/haproxy_reverse_proxy.md
scope: cae8a0416ccc9c2ad4a5010cce8dc785bd8cfd00b0cae4a10b30e01b9b8b6b3b
citations:
deployments/infrastructure/oidc.tf:84 =     vault_identity_oidc_client.oauth2_proxy.client_id,
deployments/infrastructure/oidc.tf:176 =   assignments      = ["allow_all"]
deployments/infrastructure/oidc.tf:177 =   client_type      = "confidential"
deployments/infrastructure/services/haproxy.hcl:107 =     acl is_dash       hdr(host) -i dash.lab.orangecluster.nl
deployments/infrastructure/services/haproxy.hcl:118 =     use_backend dash       if is_dash
deployments/infrastructure/services/haproxy.hcl:156 =     server dash1 192.168.2.50:4180 check
deployments/infrastructure/services/oauth2-proxy.hcl:30 =       value     = "radxa-dragon-q6a"
deployments/infrastructure/services/oauth2-proxy.hcl:35 =         static = 4180
deployments/infrastructure/services/oauth2-proxy.hcl:53 =         OAUTH2_PROXY_EMAIL_DOMAINS="*"
deployments/infrastructure/services/oauth2-proxy.hcl:54 =         OAUTH2_PROXY_UPSTREAMS="static://200"
deployments/infrastructure/services/oauth2-proxy.hcl:73 =           path     = "/ping"
deployments/infrastructure/services/oauth2-proxy.hcl:81 =         image        = "quay.io/oauth2-proxy/oauth2-proxy:v7.13.0"
docs/haproxy_reverse_proxy.md:23 = | `bifrost.lab.orangecluster.nl` | radxa-dragon-q6a (192.168.2.50) | 8080 |
docs/haproxy_reverse_proxy.md:24 = | `dash.lab.orangecluster.nl` | radxa-dragon-q6a (192.168.2.50) | 4180 |
docs/haproxy_reverse_proxy.md:28 = with its own native `governance.auth_config` (admin creds from Vault), so
---

## Deterministic floor

Re-ran `loopctl verify-eval-substance L1-landing-oauth2-proxy`: bare
`valid`, exit 0, no `warn:` lines. Clean floor, no hard-fail defects and no
advisories to carry forward. Proceeded to the semantic pass.

## What changed since cycle 1

Per the task briefing and confirmed independently by re-running
`git diff 3bff48172c3dc29467c40677a6540018918ed48a -- deployments/ docs/`,
the only new hunk since cycle 1 is in `docs/haproxy_reverse_proxy.md`: a new
table row for `dash.lab.orangecluster.nl` and a clause noting it sits
behind oauth2-proxy/Vault SSO. The five `deployments/` files are
byte-identical to cycle 1 — spot-checked by re-reading every line cycle 1
cited (`oidc.tf:84,176,177`; `haproxy.hcl:107,118,156`;
`oauth2-proxy.hcl:53,54,73,81`) and confirming each is at the same line
number with the same content.

## Re-attaching cycle-1 findings (re-attack, not rubber-stamp)

All 7 settled findings from cycle 1 (L1-ADV-1 through L1-ADV-7) anchor into
`deployments/infrastructure/*.tf` and `services/*.hcl`, none of which this
cycle's diff touches. Per the reviewer-brief protocol, I re-opened each
anchor and re-read it this cycle rather than trusting the label:

- L1-ADV-1 (client_type=confidential, allow_all assignment, no assignment
  resource, client id in the provider list) — re-read `oidc.tf:84,176,177`
  this cycle, unchanged. Still holds.
- L1-ADV-2 (env var plurality) — re-read `oauth2-proxy.hcl:46-58`,
  unchanged. Still holds.
- L1-ADV-3 (dash ACL/use_backend in https_in, not http_in) — re-read
  `haproxy.hcl:91-118`, unchanged (haproxy.hcl itself has no new hunk this
  cycle). Still holds.
- L1-ADV-4 (health check path `/ping`) — re-read `oauth2-proxy.hcl:69-77`,
  unchanged. Still holds.
- L1-ADV-5 (image tag architecture) — image line unchanged; not
  re-queried against quay.io this cycle since the pinned tag itself did not
  change and the cycle-1 network evidence stands. Still holds.
- L1-ADV-6 (eval marker row 7's stale "ten pre-existing ACLs"/"backend
  mlflow" prose, pre-dating this ticket) — the eval marker's only change
  since cycle 1 is a 3-line `signed-off-by:`/`plan:` footer appended at the
  bottom (loop bookkeeping), not an edit to row 7 or any guardrail row.
  Still an observed non-defect, not re-scored.
- L1-ADV-7 (deterministic floor clean) — re-ran this cycle, see above.
  Still holds.

Full absence-claim entries and reasoning are appended to
`.loop/scratch/L1-landing-oauth2-proxy.adversarial/findings.json` (cycle 2
entries for L1-ADV-1 through L1-ADV-7), each citing its own re-check
evidence rather than inheriting the cycle-1 verdict by assumption.

## The one substantive check this cycle: is the new doc row accurate

Read `deployments/infrastructure/services/oauth2-proxy.hcl` in full:

- `constraint { attribute = "$${attr.unique.hostname}" value = "radxa-dragon-q6a" }`
  at lines 28-31 pins the job to host `radxa-dragon-q6a` — matches the doc
  row's host column.
- `network { port "http" { static = 4180 } }` at lines 33-36 fixes the
  service's port at `4180` — matches the doc row's port column.

Cross-checked the IP: `docs/haproxy_reverse_proxy.md:23`, the pre-existing
`bifrost` row (untouched by this diff), already documents
`radxa-dragon-q6a` as `192.168.2.50`. The new `dash` row uses the same IP
for the same host, which is internally consistent with the doc's own prior
entry. The haproxy backend the diff adds,
`backend dash / server dash1 192.168.2.50:4180 check`
(`haproxy.hcl:155-156`), uses that identical IP:port pair. Host, IP, and
port agree across three independent sources (jobspec constraint + static
port, haproxy backend server line, and the new doc row) — no drift.

The added clause ("`dash` sits behind oauth2-proxy, gated by Vault SSO
with flat any-authenticated-user access") is consistent with the flat
`allow_all` assignment confirmed in cycle 1 (`oidc.tf:176`) and with
`oauth2-proxy.hcl`'s own `OAUTH2_PROXY_EMAIL_DOMAINS="*"` — no false claim
about the access model. Style matches the doc's existing idiom ("`phoenix`
sits behind HTTP basic auth", line 26, pre-existing), so the new sentence
is not an unprompted style change. No line in the added hunk exceeds 80
characters (checked with `awk`).

## Independent gate re-run

The cycle-1 trust stamp (`.loop/scratch/L1-landing-oauth2-proxy.adversarial/trust-stamp.json`)
was keyed to tree `171b339c...`, which differs from this cycle's tree
`983d3fc...` (the docs commit changed the tree). Per the brief, a stamp
whose recorded tree differs from the current briefing's tree is not
trusted, so I re-ran the gate myself rather than reusing it. Ran
`just pre_commit` under the 5-minute ad-hoc bound; it took 1m4s and every
hook passed (check json, check python ast, merge conflicts, yaml, debug
statements, detect private key, fix end of files, Nomad Format, Terraform
Format, Terraform Validate, Ruff lint, Ruff format, Mypy strict, Pytest).
`git status` before and after the run shows no unexpected mutations to
tracked files. Overwrote the trust stamp with a fresh one keyed on tree
`983d3fcfbf8ea9630fb484dc11ab6f1e11afd1cb` since the run exceeded one
minute.

## Scope

Six paths make up the full reviewed set for this cycle: the five
`deployments/` files (unchanged since cycle 1, `oauth2-proxy.hcl` included
as a new file the ticket added) plus `docs/haproxy_reverse_proxy.md` (the
only file with new content this cycle). `.loop/config.json` sets no
`verdict_binding_inputs`, so no extra read-input paths widen the bound
set. Outside this set, `git status` shows only `.loop/ledger.json` and
`.loop/evals/L1-landing-oauth2-proxy.md` changed (loop-owned lifecycle
bookkeeping — a 3-line sign-off footer on the eval marker — neither part
of the reviewed contract nor a functional change). `scope:` above is the
sha256 digest over these six paths' current contents, computed with the
harness's own `loop_harness.stamp.paths_fingerprint` function so it agrees
with whatever the commit gate recomputes.

## Verdict

No regressions in the five infrastructure files (all settled cycle-1
findings re-confirmed), and the new documentation row/clause is accurate:
host, IP, and port agree across the jobspec, the haproxy backend, and the
doc table. Gate re-run green on the current tree. `pass`.
