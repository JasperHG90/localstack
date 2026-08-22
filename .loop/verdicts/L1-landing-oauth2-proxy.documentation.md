---
verdict: pass
tree: 983d3fcfbf8ea9630fb484dc11ab6f1e11afd1cb
bound_paths: deployments/infrastructure/oidc.tf, deployments/infrastructure/secrets.tf, deployments/infrastructure/services.tf, deployments/infrastructure/services/haproxy.hcl, deployments/infrastructure/services/oauth2-proxy.hcl, docs/haproxy_reverse_proxy.md
scope: cae8a0416ccc9c2ad4a5010cce8dc785bd8cfd00b0cae4a10b30e01b9b8b6b3b
citations:
docs/haproxy_reverse_proxy.md:23 = | `bifrost.lab.orangecluster.nl` | radxa-dragon-q6a (192.168.2.50) | 8080 |
docs/haproxy_reverse_proxy.md:24 = | `dash.lab.orangecluster.nl` | radxa-dragon-q6a (192.168.2.50) | 4180 |
docs/haproxy_reverse_proxy.md:28 = HAProxy no longer gates it. `dash` sits behind oauth2-proxy, gated by Vault
docs/haproxy_reverse_proxy.md:29 = SSO with flat any-authenticated-user access. The rest are open to anyone who
deployments/infrastructure/oidc.tf:25 = ###      known consumers (G1, R1, R4, L1) declare flat access and want this.
deployments/infrastructure/oidc.tf:176 =   assignments      = ["allow_all"]
deployments/infrastructure/services/oauth2-proxy.hcl:29 =       attribute = "$${attr.unique.hostname}"
deployments/infrastructure/services/oauth2-proxy.hcl:30 =       value     = "radxa-dragon-q6a"
deployments/infrastructure/services/oauth2-proxy.hcl:35 =         static = 4180
deployments/infrastructure/services/oauth2-proxy.hcl:53 =         OAUTH2_PROXY_EMAIL_DOMAINS="*"
deployments/infrastructure/services/haproxy.hcl:155 = backend dash
deployments/infrastructure/services/haproxy.hcl:156 =     server dash1 192.168.2.50:4180 check
---

## Note on this pass

This is a fresh, authoritative review. A dispatch mistake earlier raced two
review agents onto this same verdict path; I disregarded whatever was there
and re-derived every claim below directly from the current repo state
(worktree `L1-landing-oauth2-proxy`, tree `983d3fc...`).

## Citation-scope note

`docs/vault-human-auth.md` and `docs/cluster-roles.md` are not in this
diff and are not named as a `verdict_binding_inputs` read-input in
`.loop/config.json`, so they are outside my `bound_paths` and I do not put
formal `path:line` anchors from them in the `citations:` block above
(citing outside the bound set is malformed per the brief). I did read both
files in full to answer the ticket's question, and I quote their relevant
lines by path:line in prose below for the reader's benefit — those
in-prose references are informational, not citation-block anchors, and
carry no scope-binding weight.

## Tree / gate check

`.loop/stamp.json` reports tree `983d3fcfbf8ea9630fb484dc11ab6f1e11afd1cb`,
matching the briefing exactly — used as given. The stamp records `just
pre_commit` at exit 0 on this same tree. The same-cycle adversarial-pass
verdict (`.loop/verdicts/L1-landing-oauth2-proxy.adversarial.md`) independently
re-ran the gate on this tree this cycle and recorded a clean pass, so I did
not re-run the full gate a third time; nothing in this documentation-only
review touches gate-relevant code.

## Scope

The diff (`git diff 3bff481... -- deployments/ docs/`) touches exactly six
files, all bound above. `paths_fingerprint` over those six paths (computed
with the harness's own `loop_harness.stamp.paths_fingerprint`, the same
function the gate uses) reproduces `cae8a041...`, matching the same-cycle
adversarial verdict's scope digest for the identical six-path set — expected,
since scope is a pure function of path contents and both verdicts bind the
same paths on the same tree.

## What the ticket asked me to check

1. Is the new `docs/haproxy_reverse_proxy.md` row/sentence accurate?
2. Do `docs/vault-human-auth.md` and `docs/cluster-roles.md` stay factually
   correct, checked fresh rather than assumed?

## 1. The new `dash` route row and auth-status sentence — accurate, complete

`docs/haproxy_reverse_proxy.md:24` adds:
`| `dash.lab.orangecluster.nl` | radxa-dragon-q6a (192.168.2.50) | 4180 |`

Cross-checked against every other source of truth this diff touches:

- **Host**: `oauth2-proxy.hcl:28-31`'s `constraint` pins the job to
  `attr.unique.hostname == "radxa-dragon-q6a"` — matches the row's host
  column.
- **Port**: `oauth2-proxy.hcl:33-36`'s `network { port "http" { static = 4180
  } }` fixes the service port at 4180 — matches the row's port column.
- **IP**: the doc's own pre-existing `bifrost` row (`haproxy_reverse_proxy.md:23`,
  untouched by this diff) already documents `radxa-dragon-q6a` as
  `192.168.2.50`. The new `haproxy.hcl:155-156` backend, `backend dash /
  server dash1 192.168.2.50:4180 check`, uses that identical IP:port pair.

Host, IP, and port agree across three independent sources (jobspec
constraint + static port, the new HAProxy backend, and the new doc row) —
no drift.

The added sentence, "`dash` sits behind oauth2-proxy, gated by Vault SSO
with flat any-authenticated-user access" (`haproxy_reverse_proxy.md:28-29`),
is accurate: `oidc.tf:176` sets `assignments = ["allow_all"]` with no
`vault_identity_oidc_assignment` resource created for `oauth2_proxy`
(confirmed by reading the whole new block, `oidc.tf:152-187`), and
`oauth2-proxy.hcl:53` sets `OAUTH2_PROXY_EMAIL_DOMAINS="*"`. Both confirm
flat, any-authenticated-user access, matching the sentence's claim exactly.
Style matches the doc's existing idiom for `phoenix`/`bifrost` on the same
paragraph, and every touched line stays under 80 characters (checked with
`awk`).

## 2. `docs/vault-human-auth.md` and `docs/cluster-roles.md` — re-verified fresh, still correct

Both docs carry (unchanged by this diff — confirmed the `git diff` against
docs/ touches only `haproxy_reverse_proxy.md`) the claim: "Four of the six
known consumers ... declare flat access and want this"
(`vault-human-auth.md:285-286`: "allowed in\" is \"anyone who can log in\".
Four of the six known consumers / declare flat access and want this.";
`cluster-roles.md:172-173`: "the answer is \"anyone who can log in\". Four
of the six known consumers want / this."). The consumers are named
explicitly in `oidc.tf`'s own header comment, `oidc.tf:25`
(in my bound citations above): "known consumers (G1, R1, R4, L1) declare
flat access and want this."

I did not take the ticket's framing as given. I read `oidc.tf:152-187` in
full to confirm the L1 client this diff adds actually lands in the shape
the docs predicted: `assignments = ["allow_all"]` (`oidc.tf:176`,
in my bound citations), `client_type = "confidential"` (correct per the
docs' own KV2-vs-Terraform-reference distinction, since oauth2-proxy reads
its secret at run time through a template rather than as a Terraform
resource reference), and no assignment resource anywhere in the new block.
This was a forward-looking prediction before the diff landed and is now a
confirmed fact after it — neither doc makes any claim this diff falsifies,
so neither needed an edit. Verified, not assumed.

## One thing found beyond what was asked, judged not to require a fix

`docs/vault-human-auth.md:39-43`'s "What Terraform creates" table claims
`oidc.tf` holds only "the OIDC signing key, the shared `groups` scope, the
provider, and one throwaway smoke-test client" (`vault-human-auth.md:42`),
and `secrets.tf` holds only "Two KV2 writes: the operator password, and the
smoke client's credentials" (`vault-human-auth.md:43`). This diff appends a
real (non-throwaway) client directly into `oidc.tf` (the "--- L1:
oauth2-proxy ---" block, `oidc.tf:152-187`) and two new KV2 writes directly
into `secrets.tf` (`oauth2_proxy_oidc_client`, `oauth2_proxy_cookie_secret`,
both new resources added by this diff), so that table's per-file
enumeration is now incomplete for both rows.

I am not treating this as a required fix, for three reasons: (1) the table
has never functioned as a live per-consumer registry — the earlier `nomad`
and `memex` OIDC clients are not reflected in it either, because those
tickets used dedicated files (`nomad_oidc.tf`, `memex_oidc.tf`) the table
never lists; (2) L1's own plan
(`.loop/plans/L1-landing-oauth2-proxy.md:371-385`) explicitly directs
appending to `oidc.tf` and `secrets.tf` rather than creating a new file, and
never names this table as part of L1's doc surface — the placement is a
plan-directed architecture choice, not an oversight this diff introduced
unilaterally, and judging that choice is outside this review's mandate;
(3) the new code is thoroughly self-documenting and cross-references the
exact `vault-human-auth.md` procedure lines it follows
(`oidc.tf:152-163`), so a reader following the doc's "Adding a service"
section to `oidc.tf` is not misled about any behavior, default, command, or
error contract — only about a summary table's literal completeness. Logged
as an observation in the findings ledger (`L1-DOC-4`), not a defect.

## Other docs under `docs/`

Searched the tree for `oauth2`, `dash.lab`, and route/ACL counts.
`docs/cli-read-commands.md:66-68` explicitly reads routes live from the
running Nomad job rather than any static list, so it cannot go stale from a
new backend. `docs/monitoring.md`, `docs/tls-certificates.md`,
`docs/riscv-integration.md` mention `haproxy.hcl` only as a generic
"how to add a backend" pointer naming no specific hostnames. No CHANGELOG
file exists; `README.md` has no `oauth2`/`dash` references. Nothing else
under `docs/` is left factually wrong by this diff.

## Verdict

`pass`. The one documented surface this diff changes — the HAProxy route
table and auth-status prose in `docs/haproxy_reverse_proxy.md` — is
accurate and complete, cross-checked against the jobspec and the new
HAProxy backend. The two docs named in the brief remain factually correct,
re-verified against the landed code rather than assumed. The one gap found
(`vault-human-auth.md`'s inventory table) is a pre-existing, plan-directed
convention gap that misstates no behavior and is logged as an observation,
not a required fix.
