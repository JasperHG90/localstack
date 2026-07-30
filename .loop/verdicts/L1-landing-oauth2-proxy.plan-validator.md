---
verdict: fail
---

# L1-landing-oauth2-proxy — plan-validator verdict

Plan fingerprint verified locally: `sha256sum .loop/plans/L1-landing-oauth2-proxy.md`
returns `5ed0ea356e5596e43690817ea8a5a5244bfdeb1db4bde732d52ad3187da074e0`,
matching the briefing. The `plan:` line is omitted because this is a `fail`.

**Premise verdict: PARTIALLY SOUND, failing on severity.**

The plan was partially repaired in place on 2026-07-25/26 (Requirements 10 and
11, and the two `haproxy.hcl` Code-surface bullets carry dated rewrites), so the
edge-scheme correction landed in *some* sections. It did not land in Context,
Risk assessment, Subtickets, or the eval file, which still describe the
pre-F3 world. Separately, three claims that were never about the edge are
falsified by the live cluster and by oauth2-proxy's own documentation, and the
ticket's Definition of Done cannot pass as written even if the code is perfect.

## Load-bearing assumptions

### P1 — "Edge binds cleartext `*:80` only; there is no TLS bind today." BREAKS

Plan lines 35-37 assert this and anchor it at `haproxy.hcl:11-19, 48-49`. The
live file binds TLS:
`deployments/infrastructure/services/haproxy.hcl:92-96` —
`frontend http_in / bind *:80 / http-request redirect scheme https code 301
unless { ssl_fc }` then `frontend https_in / bind *:443 ssl crt
/secrets/haproxy.pem`. The cited anchor `haproxy.hcl:11-19` is now the `network`
block and itself contains `port "https" { static = 443 }` at `:16-18`, i.e. the
anchor the plan offers as proof of "cleartext only" proves the opposite.
`haproxy.hcl:48-49` is now comment text inside the certificate template.
Live confirmation: `curl -sI https://grafana.lab.orangecluster.nl/` returns
`HTTP/2 302`.

Requirement 11 (plan:133-149) states the corrected fact. Context was never
updated to agree with it. Two sections of the same plan now contradict each
other on the single most load-bearing fact in the ticket.

### P2 — "All routing lives in one frontend; a bad edit to `http_in` breaks everything." BREAKS

Plan lines 38-40, 105-106, 281-285 and Subticket 4 (plan:314-315) all point the
ACL work at `haproxy.hcl:48-75` and name `http_in` as the single routing
frontend. Live: `http_in` (`haproxy.hcl:91-93`) only 301-redirects and carries
no ACL; every `acl`/`use_backend` lives in `https_in`
(`haproxy.hcl:95-118`); backends are at `haproxy.hcl:127-157`. An ACL added at
the line range the plan names lands in the redirect-only frontend and can never
route. Requirement 11 and the Code-surface bullet at plan:167-174 say `https_in`
correctly, but Subticket 4 and the Risk section still say `http_in` /
`:48-75` / `:84-121`. An implementer working the subtickets in order reads the
wrong instruction.

### P3 — "Basic auth (`openfang_users`, `haproxy.hcl:45-46`) is applied to phoenix/mlflow/bifrost at `:100,116,120`." BREAKS

`userlist openfang_users` is at `haproxy.hcl:88-89`, not `:45-46`. The
`http-request auth unless { http_auth(openfang_users) }` lines are at
`haproxy.hcl:143` (phoenix) and `haproxy.hcl:153` (mlflow) only. **`backend
bifrost` (`haproxy.hcl:156-157`) has no basic auth at all** — it was removed by
`B1-bifrost-native-auth-and-virtual-keys` (ledger stage `done`; commit
`ac3267b`). The plan's cited lines `:100`, `:116`, `:120` now resolve to an
`acl` line, a `use_backend` line, and `frontend stats`. The Non-goal at
plan:77-78 ("Do not migrate or remove the existing `openfang` basic-auth on
phoenix/mlflow/bifrost") protects something that no longer exists for bifrost.
Stale premise; low blast radius but it is a factual error in Triggered-by.

### P4 — "No landing-page service and no `dash` ACL/backend exist." HOLDS

`grep -n 'dash\.' deployments/infrastructure/services/haproxy.hcl` returns
nothing. Live: `curl -sI https://dash.lab.orangecluster.nl/` returns
`HTTP/2 503` (TLS handshake succeeds against the wildcard, HAProxy has no
matching backend). This also confirms Requirement 11's cert/DNS claims:
`dash.lab.orangecluster.nl` resolves (to `192.168.2.30`) and the Let's Encrypt
wildcard already covers it. No DNS or SAN work is needed, as the plan says.

### P5 — "No Vault OIDC provider or client resource exists yet; F2 delivers them." HOLDS in the repo, with a live caveat

`grep -rn 'vault_identity_oidc|oidc_provider|issuer' deployments/ --include=*.tf`
returns nothing, so the repo claim holds. But the **live Vault already has**
`identity/oidc/provider/default`, `identity/oidc/client/test`,
`identity/oidc/key/default`, and assignments `allow_all` and `test`
(`vault list identity/oidc/{provider,client,key,assignment}`). The live
`default` provider's issuer is `http://192.168.2.30:8200/v1/identity/oidc/
provider/default`. The evals must therefore name F2's provider explicitly; a
close-out check that happens to hit `default` would pass against the wrong
issuer.

### P6 — "F2 writes `client_id`/`client_secret` to `secret/data/default/oauth2-proxy/oidc`." BREAKS (inlined conclusion)

This is stated as a settled fact in the Resolved-forks block (plan:380-382) and
drives the Code surface (plan:162-166). F2's plan never establishes it. F2's own
resolved Q6 (`.loop/plans/F2-foundation-vault-oidc-provider.md:393-395`) only
says client-secret KV2 writes go "in `secrets.tf` beside the existing credential
blocks" — no path, no key names. Worse, F2's cross-cutting note
(F2 plan:397-402) says the architecture is **one client per fronted service** —
`dash` (L1), `mlflow` (R1), `phoenix` (R4) — "each with its own `redirect_uris`
variable and KV2 secret". A per-service client is much more likely to be written
under a `dash`-named path than a shared `oauth2-proxy/oidc` one. F2 is stage
`ready`, never run (`.loop/ledger.json`), so nothing on disk or in Vault settles
this. The plan does hedge ("Block apply until F2 confirms"), but it hedges the
apply, not the template the implementer writes.

### P7 — "Issuer is `https://vault.lab.orangecluster.nl/v1/identity/oidc/provider/<provider>`." HOLDS

Consistent with F2's resolved Q2/Q3 (F2 plan:375-383: `https_enabled = true`,
issuer host `vault.lab.orangecluster.nl`). Feasible on the live edge: `acl
is_vault` / `use_backend vault` exist on `https_in`
(`haproxy.hcl:100,111,133-134`). Vault's provider issuer format is
`<issuer_host>/v1/identity/oidc/provider/<name>`, confirmed by the live
discovery document.

### P8 — "Flat access: anyone who completes Vault login is allowed through." UNCERTAIN, and in conflict with F2

Requirement 5 (plan:101-104) treats flatness as an oauth2-proxy-side property
(omit `--allowed-*`). That is correct for oauth2-proxy, but the effective gate
sits at Vault: an OIDC client is bound to an assignment, and F2 plans identity
groups including `dashboard-users` explicitly "referenced by the per-client
assignments (this is the per-tier gating mechanism M2 depends on)"
(F2 plan:111-113). If F2 binds the `dash` client to `dashboard-users`, a Vault
user outside that group is refused at the authorize endpoint and L1's stated
policy is false end to end. Vault does ship a built-in `allow_all` assignment
(confirmed live: `vault list identity/oidc/assignment`), so the flat policy is
achievable — but only if F2 uses it for `dash`, which no plan says. Unresolved
cross-ticket contract.

### P9 — "An unauthenticated `curl -sI https://dash…/` returns 302 with `Location:` at the Vault authorize endpoint." BREAKS

This is plan eval 2 (plan:243-249) and eval-file rows 2 and 3
(`.loop/evals/L1-landing-oauth2-proxy.md:14-15`), both at threshold 100%.
oauth2-proxy's own endpoint documentation contradicts it: "`/` - the proxy
endpoint provides authentication and **returns the appropriate 40x error if not
authenticated**"; the redirect to the provider is `/oauth2/start` — "a URL that
will redirect to start the OAuth cycle"
(`https://raw.githubusercontent.com/oauth2-proxy/oauth2-proxy/master/docs/docs/
features/endpoints.md`). With the default `--skip-provider-button=false` an
unauthenticated `/` yields the sign-in page (a 40x), and with the button skipped
it yields a 302 to the same-host `/oauth2/start?rd=…`, not to Vault. Either way
a single `curl -sI` never shows a Vault `Location`. Two more mismatches in the
same row: the expected host is written as `$VAULT_ADDR`, which in this
environment is `http://192.168.2.30:8200`, not F2's
`https://vault.lab.orangecluster.nl`; and the expected path is
`/v1/identity/oidc/provider/<name>/authorize`, whereas the live discovery
document advertises `authorization_endpoint` at
`…/ui/vault/identity/oidc/provider/default/authorize` (`/ui/`, not `/v1/`). The
plan body hedges the `/ui/` form in a parenthesis; the eval file does not.

### P10 — "`curl -sI https://dash…/ | grep -i set-cookie` shows `_oauth2_proxy` with Secure and HttpOnly." BREAKS (high confidence, not executed)

Plan eval 4 (plan:257-261) and eval-file row 5. `_oauth2_proxy` is the *session*
cookie, created at `/oauth2/callback` after a completed exchange. The request
being probed is pre-authentication; what oauth2-proxy sets on the way into the
flow is the CSRF cookie (`--cookie-csrf-*` family, overview.md:121-124), and the
bare `/` response may set no cookie at all. Not executable here (no oauth2-proxy
instance), so I mark the exact cookie name emitted at `/` as unverified — but
the stated expectation cannot be satisfied by an unauthenticated request in any
reading of the documented flow.

### P11 — "Use an arm64-compatible image because cluster nodes are Orange Pi / ARM." BREAKS for the recommended host

Requirement 1 (plan:83-87) and Risk failure mode 4 (plan:300-301) derive the
arm64 constraint from `CLAUDE.md`'s "Orange Pi boards". Live: **`firebat` is
`cpu.arch = amd64`** and is the only amd64 node in the cluster
(`nomad node status -verbose <firebat>`; the other four — `orangepi4a`,
`radxa-dragon-q6a`, `ubuntu`, `jetson-orin-nano` — are `arm64`). Resolved Q6
(plan:387-396) recommends placing oauth2-proxy on `firebat`. An arm64-only image
pinned per Requirement 1 would fail to run at the recommended placement. The
plan's "multi-arch/arm64" phrasing survives by accident; the stated *reason* is
wrong and the requirement as worded misdirects.

### P12 — "firebat placement is fine pending a live capacity check." BREAKS on the check the plan itself ordered

Resolved Q6 defers to a live check. I ran it read-only:
`nomad node status <firebat>` reports `Allocated Resources CPU 3100/3200 MHz`,
i.e. **100 MHz of reservable CPU headroom**, with four allocations already
placed (haproxy, postgres, node-exporter, promtail). Memory is fine
(6.4 GiB/15 GiB). Any `resources { cpu = … }` above 100 will not place on
firebat. The plan's fallback ("If firebat is full, place oauth2-proxy on another
node") is therefore the live answer, not the contingency — and taking it
reintroduces the arm64 question from P11 and changes the `backend dash` server
address from a localhost-style line to a cross-node one.

### P13 — "The HAProxy change is purely additive: one ACL plus one backend." UNCERTAIN, likely incomplete

`grep -n 'forwardfor|X-Forwarded|set-header'
deployments/infrastructure/services/haproxy.hcl` returns nothing: the edge
forwards no `X-Forwarded-Proto`/`X-Forwarded-For`, and TLS terminates at HAProxy
so oauth2-proxy sees plain HTTP. oauth2-proxy's `--reverse-proxy` flag exists
precisely for this ("are we running behind a reverse proxy, controls whether
headers like X-Real-IP are accepted and allows X-Forwarded-{Proto,Host,Uri}
headers to be used on redirect selection", overview.md:217), and the docs warn
about `--trusted-proxy-ip` when it is set (overview.md:197). Neither the
jobspec Requirements nor the HAProxy Code-surface bullets mention either side of
this. An explicitly configured `OAUTH2_PROXY_REDIRECT_URL` mitigates the worst
case, so I do not call this broken — but it is an unstated implementation
requirement sitting under a "purely additive" claim.

### P14 — "`--upstream` points at L2's Homepage service." BREAKS as an ordering premise

Resolved Q1 (plan:369-373) makes L1's upstream L2's Homepage, and eval 5 /
eval-file row 6 require `HTTP/2 200` "reaching the landing-page upstream". But
`.loop/plans/L2-landing-homepage.md:3` declares
`depends_on = ["L1-landing-oauth2-proxy", …]` and the ledger has both L1 and L2
at stage `ready`. L1's Definition of Done therefore depends on a service owned by
a ticket that depends on L1. The plan's own Q1 recommendation (a placeholder
upstream) was overridden by the resolution without replacing the upstream for
the eval. Separately, L1 flags that "L2's ticket text says forward-auth and must
be reconciled" (plan:376-377) — L2 still says forward-auth in 15+ places
including its front-matter summary, so that reconciliation never happened.

### P15 — Gate is `just pre_commit`, Terraform-aware. HOLDS

`justfile:18-19` (`pre_commit: pre-commit run --all-files`) and
`.pre-commit-config.yaml:16-33` (`nomad-fmt`, `terraform-fmt`,
`terraform-validate` via `scripts/tf_validate.sh`), plus
`.pre-commit-config.yaml:1` (`exclude: '^\.(claude|loop)/'`). Discovered, not
assumed. Correct.

### P16 — Requirement 10 ("docs discharged by T3"). HOLDS

`docs/haproxy_reverse_proxy.md:100-113` describes the wildcard
`*.lab.orangecluster.nl` edge and mentions `*.localstack` only as a historical
explanation of why the previous cert failed. `docs/monitoring.md` carries no
stale `.localstack` host. Nothing to do here, as the requirement says.

### P17 — "Providers available: `nomad` and `vault` only (`providers.tf:1-28`)." BREAKS

`deployments/infrastructure/providers.tf:11-18,30-32` also declares and
configures `null` and `google`. The consul-provider half of the claim holds
(commented out at `:19-22`). Minor, but it is a Context statement that is simply
false at its own anchor.

### P18 — Terraform pattern anchors. MIXED

- `secrets.tf:46-66` (Grafana admin `random_password` + `vault_kv_secret_v2`):
  HOLDS exactly.
- `secrets.tf:31-44` (openfang): HOLDS.
- `grafana.hcl:29` (`vault {}`), `:31-45` (service+check), `:48` (pinned tag),
  `:77-84` (`template … env = true`): all HOLD exactly.
- `nats.hcl:50-66` (service+check), `:69` (pinned tag): HOLD.
- `services.tf:301-316` described as the HAProxy `nomad_job`: BREAKS. HAProxy is
  at `services.tf:318-326`; `:306-311` is MinIO.
- `services.tf:333-355` described as the Grafana `nomad_job`: BREAKS. Grafana is
  at `services.tf:346-368`; `:334-343` is Prometheus.
- `vars/prod.tfvars:1-4`: not resolvable in this worktree (the file is
  gitignored and seeded by `just worktree_setup`); `vars/prod.tfvars.example`
  holds three keys. Not counted as a finding.

## Shape-check of the eval file

`.loop/evals/L1-landing-oauth2-proxy.md` has no `ls`, `grep`-as-scorer, or
file-existence rows — every scorer is a live `curl`/`nomad` command or a
model+rubric row, which is the right shape. The defect is the *expectations*,
not the scorer type:

- Row 2 and row 3 (`.loop/evals/…:14-15`) encode P9's falsified redirect shape at
  threshold 100%, with the wrong issuer host (`$VAULT_ADDR` = raw IP here) and
  the wrong authorize path (`/v1/…` vs the advertised `/ui/vault/…`).
- Row 5 (`:17`) encodes P10's cookie claim; its `| grep -i set-cookie` pipeline
  will most likely return empty on the probed request, which reads as a failure
  of correct code.
- Row 6 (`:18`) requires a 200 from the landing upstream, which P14 shows is
  owned by L2.
- The DoD header (`:8-9`) still names F3 as an unmet hard dependency; F3 is
  stage `done`.

## Most dangerous assumption

**P9 (with P10).** The eval file is the ticket's Definition of Done and its rows
are 100%-threshold deterministic checks. As written they assert a single-hop
302 from `/` straight to Vault and a session cookie on an unauthenticated
request — behavior oauth2-proxy's documented endpoint contract does not produce.
A correct implementation fails its own acceptance, and the loop's likeliest
reaction is to "fix" working code until it matches an impossible expectation.
P14 (the L1/L2 upstream circularity) is a close second, because it makes the
final row unreachable regardless of how the redirect rows are worded.

## Required fixes before this plan leaves PLANNING

1. **Rewrite Context (plan:34-40) to the post-F3/T3 edge.** State the `http_in`
   redirect-only frontend and the `https_in :443 ssl` routing frontend with
   current line numbers (`haproxy.hcl:91-93`, `:95-118`, `:127-157`). Delete the
   "cleartext `*:80` only … no TLS bind today" sentence and its anchors.
2. **Fix the Risk section (plan:281-285) and Subticket 4 (plan:314-315)** so they
   name `https_in` and current line ranges, matching Requirement 11. Right now
   the plan instructs the implementer twice, contradictorily.
3. **Correct the Triggered-by basic-auth claim (plan:26-28, 41-45).** Userlist is
   at `haproxy.hcl:88-89`; auth is on phoenix (`:143`) and mlflow (`:153`) only.
   Drop bifrost from the claim and from the Non-goal at plan:77-78 (B1 removed
   it).
4. **De-inline the F2 secret path (plan:344-350, 380-382, 162-166).** Move
   `secret/data/default/oauth2-proxy/oidc` back to an Open Question, or state it
   as a *proposal to F2* and reconcile with F2's per-service client
   architecture (`dash`/`mlflow`/`phoenix`, F2 plan:397-402). Thread the path as
   a Terraform variable so the value is not baked into the template.
5. **Settle the flat-access contract with F2 (P8).** State explicitly whether
   F2's `dash` client uses the built-in `allow_all` assignment or gates on
   `dashboard-users`. "Any authenticated user" is only true under the former.
6. **Rewrite evals 2-4 and eval-file rows 2, 3 and 5** against oauth2-proxy's
   actual flow: either follow redirects (`curl -sIL`) and assert the eventual
   Vault authorize URL, or probe `/oauth2/start` directly; assert the CSRF
   cookie (not `_oauth2_proxy`) on the pre-auth request and check
   `Secure`/`HttpOnly` on whatever cookie is actually emitted. Replace
   `$VAULT_ADDR` with F2's issuer host and use the `/ui/vault/identity/oidc/
   provider/<name>/authorize` path the live discovery document advertises.
7. **Resolve the L1/L2 upstream circularity (P14).** Either give L1 a
   self-contained upstream for its own DoD (the Q1 placeholder that was
   overridden) and move the "200 from Homepage" row to L2, or invert the
   dependency. Also reconcile L2's forward-auth language, which L1 flagged and
   nobody changed.
8. **Re-resolve Q6 with the live numbers.** firebat has 100 MHz of reservable
   CPU left (3100/3200) and is `amd64`, the only amd64 node. Pick the host and
   the image arch together, state the `resources` budget, and fix Requirement 1
   and Risk mode 4 so the arch constraint is "multi-arch, must include the
   chosen host's arch", not "arm64 because Orange Pi".
9. **Fix the shifted Terraform anchors:** HAProxy `nomad_job` is
   `services.tf:318-326`, Grafana is `services.tf:346-368`. Correct the Context
   provider claim (`providers.tf` also has `null` and `google`).

## Notes (observations, not findings)

- Stale `.localstack` hostnames: none remain in this plan; Requirement 11 and
  the Code-surface bullets already carry the `lab.orangecluster.nl` names. Per
  the dispatch scope note, no rename is proposed.
- The plan's front-matter `depends_on` correctly retargeted F3 to T3, but the
  body still hard-blocks on F3 in four places (plan:220-227, 288-292, 361-365,
  and the eval-file DoD). F3 is `done`, so this is cosmetic staleness rather
  than a fault; folding it into fix 1 would be cheap.
- Live Vault already carries an `identity/oidc/provider/default` and a `test`
  client. Any close-out check must name F2's provider explicitly so it cannot
  accidentally validate against the pre-existing default.

## Cluster commands run (all read-only)

`vault auth list`, `vault list identity/oidc/{provider,client,key,assignment}`,
`vault read identity/oidc/provider/default`, `curl` on the Vault discovery
document, `nomad job status`, `nomad node status [-verbose]`, `curl -sI` against
`dash.` and `grafana.lab.orangecluster.nl`, `getent hosts` / `nslookup`. No
mutating Vault, Nomad, Terraform, or git command was issued.
