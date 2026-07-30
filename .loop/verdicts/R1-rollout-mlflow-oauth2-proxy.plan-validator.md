---
verdict: fail
---

# Plan review: R1-rollout-mlflow-oauth2-proxy (pass `plan-validator`)

Plan fingerprint verified with `sha256sum` as
`c94a3f1acbafe85653ebe8b5f347f4deda7fb52a41fa96e0e30f1348f6027781`,
matching the briefing. The `plan:` line is deliberately omitted because
this is a `fail`: no authorizing hash may be written.

## Premise verdict

**BROKEN.** Seven of thirteen load-bearing assumptions break, including
the two that carry the ticket: the third-party-capability claim that
justifies the whole proxy approach, and the machine-identity claim that
carries a REQUIRED success criterion. The plan's own resolved fork Q4
already contradicts its Context section, and its acceptance file encodes
a world that no longer exists.

## Load-bearing assumptions

### P1 — "MLflow has no native OIDC; the upstream SSO request is open issue mlflow/mlflow#10922, confirmed by the S3 spike finding" (plan:5, plan:33-35) — BREAKS

Three separate failures in one sentence.

1. **The issue is closed and does not say what the plan claims.**
   `GET api.github.com/repos/mlflow/mlflow/issues/10922` returns
   `state = closed`, `state_reason = not_planned`,
   `closed_at = 2026-07-05`, label `stale`. Its title is
   "Authentication Using External IDP" and its body is a user asking
   "I'm wondering how to achieve authentication in MLflow using an
   external IDP via OIDC/OAuth." It is a question thread auto-closed by
   a stale bot, not "the upstream SSO request". It was already closed
   **19 days before R1 was authored on 2026-07-24**.
2. **"Confirmed by the S3 spike finding" is false.** S3 was dropped:
   `.loop/ledger.json` entry `S3-spike-oidc-version-claims` has
   `stage = ready, dropped = true`, and it produced no findings doc
   (`ls docs/` has no auth findings file; S3's own plan at
   `.loop/archive/S3-spike-oidc-version-claims/plan.md` scopes the
   MLflow thread it never ran). Nothing confirmed this. The plan inlined
   a spike conclusion, with a citation, before the spike existed.
3. **MLflow ships a documented SSO path.** MLflow's own docs carry a
   "SSO (Single Sign-On)" page at
   `https://mlflow.org/docs/latest/self-hosting/security/sso/` (HTTP
   200) which states: "The mlflow-oidc-auth plugin provides OIDC support
   for MLflow. Features: OIDC-based authentication for MLflow UI and
   API; User management through OIDC provider; User-level access
   control; Group-based access control; Permissions management based on
   regular expressions; Support for session, JWT, and basic
   authentication methods." That page was added by merged PRs
   mlflow/mlflow#20556 (merged 2026-02-05) and #20591 (merged
   2026-02-12). `mlflow-oidc-auth` is real and current on PyPI at
   version `7.6.0`. Issue mlflow/mlflow#18217 "[FR] MLFlow OIDC auth
   support" is closed as `completed`. A first-party native
   implementation is in flight as open PR #21423 / issue #21240.

The narrow literal reading, "no *built-in first-party* OIDC," survives.
The plan does not use the narrow reading: it uses the claim to skip
surveying the plugin entirely and to justify the whole proxy approach.
This is exactly the correction the sibling ticket already took. R4's
frontmatter now reads: "Turn on Phoenix's own authentication and point
its generic OIDC client at Vault, instead of fronting it with
oauth2-proxy... the extra proxy job, and the L1 dependency all
disappear" (`.loop/plans/R4-rollout-phoenix-oauth2-proxy.md:5`). R1
never ran that survey.

The genuine constraint, which R1 must state rather than assume away:
`mlflow-oidc-auth` 7.6.0 requires `mlflow<4,>=3.14.0` (PyPI
`requires_dist`), while this cluster runs 2.20.0 (verified live: `curl
http://192.168.2.50:5050/version` returns `2.20.0`; pinned at
`deployments/applications/services.tf:293`). MLflow's latest release is
`v3.14.0` (2026-06-17). So the plugin is a real alternative gated on an
MLflow major upgrade. That is a fork for the operator, not a settled
fact for the planner.

### P2 — "No fine-grained MLflow authorization... MLflow's built-in auth plugin is thin... This limit MUST be documented, not solved" (plan:99-102) — BREAKS

Falsified by the same MLflow SSO doc page: the plugin provides
"User-level access control", "Group-based access control", and
"Permissions management based on regular expressions (allows or denies
access to specific MLflow resources...)". The plan elevates an
unverified limitation into a mandatory non-goal (`MUST be documented`)
and into Requirement R6 (plan:149-151). A reviewer downstream will
inherit a documented "known limitation" that upstream does not have.

### P3 — "HAProxy has no TLS. The only bind is `bind *:80` (`haproxy.hcl:49`); there is no `bind :443`, no cert, no `ssl` keyword anywhere in the file" (plan:66-70) — BREAKS

F3 shipped. `deployments/infrastructure/services/haproxy.hcl:96` reads
`bind *:443 ssl crt /secrets/haproxy.pem`, line 93 reads `http-request
redirect scheme https code 301 unless { ssl_fc }`, and lines 62-72 are a
Vault-templated cert block. Live confirmation: `curl -sI
http://mlflow.lab.orangecluster.nl/` returns `HTTP/1.1 301` with
`location: https://mlflow.lab.orangecluster.nl/`; `curl -skI
https://mlflow.lab.orangecluster.nl/` returns `HTTP/2 401` with
`www-authenticate: Basic realm="mlflow"`. The `haproxy` Nomad job was
resubmitted `2026-07-29T22:32:28+02:00`.

This false claim is load-bearing in five places: the Context bullet
(plan:66-70), the non-goal "the edge is plain HTTP:80 today"
(plan:104-105), the eval preamble "Scheme is `http://` because the edge
is plain HTTP:80 today (`haproxy.hcl:49`, Q4)" (plan:253-254), risk 5
"OIDC over plain HTTP:80 means cookies/tokens cross the LAN
unencrypted" (plan:367-369), and Q4 itself (plan:423-428). The plan
already knows better in one place and not the others: the resolved fork
at plan:456-459 says "Q4 → TLS-consistent: depend on F3,
`--cookie-secure=true` (revised from the planner's HTTP-interim)... No
unencrypted-cookie interim." The body was never reconciled with the
operator's own resolution. An implementer reading top to bottom builds
against the wrong world.

### P4 — the cited `path:line` anchors resolve — BREAKS for eleven anchors

Contrary to the usual pattern in this sweep, R1's anchors do **not**
resolve. Every `haproxy.hcl` anchor is off by roughly 38 to 43 lines
(F3 inserted the TLS bind, the cert template, and its comment block):

| Plan cites | Plan claims | Actually at that line | Real location |
|---|---|---|---|
| `haproxy.hcl:45-46` (plan:58-59) | `openfang_users` userlist | comment text | 88-89 |
| `haproxy.hcl:49` (plan:67, 254, 424) | `bind *:80` | `bind *:443 ssl crt ...` | 92 (plus 96) |
| `haproxy.hcl:61` (plan:59, 145) | MLflow ACL | `acl is_mlflow` | 106 |
| `haproxy.hcl:74` (plan:60, 145) | MLflow route | `bind *:75`-region blank | 117 |
| `haproxy.hcl:115-117` (plan:60) | mlflow backend | `use_backend grafana/mlflow/bifrost` | 152-154 |
| `haproxy.hcl:116` (plan:62, 140, 203, 295) | `http-request auth unless {...}` | `use_backend grafana if is_grafana` | 153 |
| `haproxy.hcl:117` (plan:63, 141, 205) | `server ... 192.168.2.50:5050` | `use_backend mlflow if is_mlflow` | 154 |

`haproxy.hcl:116` is the single most-repeated anchor in the plan, named
in the Context, Requirement R4, the code surface, and eval 5, and it now
points at an unrelated Grafana routing line. Three Terraform anchors are
also wrong: `services.tf:187-200` (plan:54, 193) is claimed to be
`nomad_job.mlflow` but is `resource "nomad_job" "bifrost"` (real mlflow
job: `deployments/applications/services.tf:284-297`); `services.tf:191`
(plan:196) is claimed to pass `mlflow_postgres_secret` but is a Bifrost
comment line (real: 288); `services.tf:58-65` (plan:115, 430) is claimed
to be MLflow's ufw rule but is Loki's (real MLflow ufw rule: 66-73).

Anchors that DO resolve and are correct: all `mlflow.hcl` anchors
(6-9, 11-15, 27-32, 29, 36, 40, 42, 45, 47-60);
`bootstrap/roles/nomad_server/templates/nomad.hcl.j2:42-45`
(`default_identity { aud = ["vault.io"] ttl = "1h" }`);
`deployments/infrastructure/secrets.tf:32-44` (openfang
`random_password` + `vault_kv_secret_v2`);
`deployments/applications/secrets.tf:53-67` (MLflow KV resources);
`docs/haproxy_reverse_proxy.md` and its "Adding a New Service" section
(line 83).

### P5 — "the proxy must trust Nomad's JWKS/OIDC-discovery issuer... Neither exists yet" and Q3's fix is `--skip-jwt-bearer-tokens` plus Nomad's JWKS as an added trusted issuer (plan:77-83, 314-329, 414-422, 450-455) — BREAKS

This is the deepest failure. Verified live against the cluster:

```
$ curl -s $NOMAD_ADDR/.well-known/openid-configuration
OIDC Discovery endpoint disabled          # HTTP 404
$ curl -s $NOMAD_ADDR/.well-known/jwks.json
{"keys":[ ... 6 keys ... ]}               # HTTP 200
```

Nomad's OIDC discovery endpoint is **off**, because `oidc_issuer` is
unset. HashiCorp's server-config reference is explicit: "`oidc_issuer`
(string: "") - Specifies the Issuer URL for Workload Identity JWTs...
If set the `/.well-known/openid-configuration` HTTP endpoint is enabled
for third parties to discover Nomad's OIDC configuration. **Once set
`oidc_issuer` cannot be changed without invalidating Workload Identities
that have the old issuer claim.**"
(`https://developer.hashicorp.com/nomad/docs/configuration/server`).

The plan writes "JWKS/OIDC-discovery" as if the two were
interchangeable. They are not, and the difference decides whether R1's
machine path is buildable within its declared scope. Reading
oauth2-proxy's actual source, `newVerifierFromJwtIssuer` in
`pkg/validation/options.go:146-167` calls `NewProviderVerifier` with
`IssuerURL = jwtIssuer.issuerURI`, and on discovery failure retries with
`JWKsURL = <issuerURI>/.well-known/jwks.json` and `SkipDiscovery =
true`. So the bare-JWKS fallback does exist. But the verifier still
binds `IssuerURL` to the token's `iss` claim, so the single string
passed to `--extra-jwt-issuers=<uri>=<aud>` must simultaneously equal
the JWT's `iss` claim AND be the base of a reachable JWKS URL. With
`oidc_issuer` unset those are not the same value, which is precisely
what F1's own Q7 records: "setting `oidc_issuer` -- which changes the
`iss` claim on newly minted WI JWTs" (`.loop/plans/F1-foundation-nomad-
wi-jwt-trust.md:586-588`). Corroborating live evidence that today's
`iss` is not treated as a resolvable URL: `vault read
auth/jwt-nomad/config` returns `bound_issuer: ""` with `jwks_url:
http://127.0.0.1:4646/.well-known/jwks.json`, i.e. the one existing
consumer validates by JWKS and deliberately does not check the issuer.

Consequence: R1's REQUIRED machine path (Requirement 3 at plan:133-138,
subticket 4 at plan:386-389, eval 3, eval 7, and the explicit "do not
narrow to humans-only" instruction at plan:454-455) depends on setting
`server { oidc_issuer = ... }` in
`bootstrap/roles/nomad_server/templates/nomad.hcl.j2` and restarting the
single Nomad server. R1 lists that file as read-only contrast, never as
an edit, and its code surface (plan:176-213) does not contain it.

### P6 — "It is not L because no new Ansible role or cluster bootstrap is required" (plan:27-29) — BREAKS

Direct consequence of P5. The machine path needs an Ansible-template
edit to `nomad.hcl.j2` plus a Nomad server restart on a
`bootstrap_expect = 1` cluster, and that setting is irreversible once
chosen. The sizing and the risk section both understate this.

### P7 — "R1 depends on L1 to establish the reusable pattern" and the dependency set is sufficient (plan:3, 74-76, 401-405, 474) — BREAKS

Two edges are wrong.

- **Missing F1 edge.** The `oidc_issuer` decision from P5 is owned by
  F1, whose Q7 is still open and unsettled: "Q7 — Does F1 enable Nomad's
  OIDC discovery endpoint, or does M1?... If the operator prefers to
  defer, amend F1's non-goals and M1's dependency edge to say explicitly
  that F1 delivers JWKS only" (`F1...md:571-600`). R1's `depends_on` is
  `["L1-landing-oauth2-proxy", "A1-audit-plan-premise-sweep"]` and L1's
  is `["F2...", "T3...", "A1..."]` (`.loop/ledger.json`), so F1 is not
  reachable transitively. R1 as written opens and discovers its machine
  path was never provisioned. This is the same template failure the
  briefing named for M1.
- **L1 cannot deliver the machine half.** L1's plan is human-login only:
  its summary says "gating the cluster landing page... with a flat
  any-authenticated-user policy", its non-goals say "No per-user RBAC or
  group/role mapping. Access is FLAT" and "L1 only establishes the
  reusable pattern", and its requirements 1-8 never mention bearer
  tokens or JWT validation (grep for `bearer|jwt` in
  `.loop/plans/L1-landing-oauth2-proxy.md` returns nothing). R1's Q3
  half-acknowledges this, but the Context bullet and Q1 both frame L1 as
  the pattern R1 "consumes" for the ticket as a whole. Layer mismatch
  too: L1 puts the proxy job under
  `deployments/infrastructure/services/` while R1's resolved Q2 puts a
  sidecar in `deployments/applications/services/mlflow.hcl`.

L1 has never run (`.loop/ledger.json`: `stage = ready`), and no
oauth2-proxy exists in the repo (tree-wide grep of `*.hcl`/`*.tf` for
`oauth2|forward-auth|oidc` returns nothing; `nomad job status` lists no
proxy job). That part of the plan's Context HOLDS.

### P8 — "Today MLflow is authenticated only by shared HTTP basic auth at the HAProxy edge, and MLflow itself is wide open on the LAN" (plan:41-42) — HOLDS

`haproxy.hcl:153` still carries `http-request auth unless {
http_auth(openfang_users) }` in `backend mlflow`, and live `curl -skI
https://mlflow.lab.orangecluster.nl/` returns `401` with
`www-authenticate: Basic realm="mlflow"`. Direct LAN access confirmed
open: `curl http://192.168.2.50:5050/health` returns `200`, and
`deployments/applications/services.tf:71` allows `192.168.0.0/16` to
port 5050.

### P9 — Nomad's default identity is Vault-audience only (plan:77-83) — HOLDS

`bootstrap/roles/nomad_server/templates/nomad.hcl.j2:42-45` is exactly
`default_identity { aud = ["vault.io"] ttl = "1h" }`, inside the
`vault {}` stanza. To answer the briefing's question directly: what this
buys R1 today is a JWKS endpoint and nothing else. There is no
audience R1 can accept, no discovery document, and no non-Vault
identity in any jobspec. See P5.

### P10 — the tests-and-gates section (plan:216-244) — HOLDS

Verified against the repo: `justfile:18-19` defines `pre_commit:` as
`pre-commit run --all-files`; `.pre-commit-config.yaml` line 1 is
`exclude: '^\.(claude|loop)/'` and contains exactly the listed hooks
including local `nomad-fmt`, `terraform-fmt` (`terraform fmt -check
-recursive`, `types: [terraform]`), and `terraform-validate` (`entry:
scripts/tf_validate.sh`); `scripts/tf_validate.sh` exists and is
executable. The "no Python test harness" reasoning is sound for this
repo. This section was clearly refreshed and is the plan's strongest
part.

### P11 — eval 3's API endpoint claim (plan:279-285) — PARTIALLY BREAKS

The parenthetical HOLDS: `curl
http://192.168.2.50:5050/api/2.0/mlflow/experiments/list` returns `404`
on the deployed 2.20.0. The expected result BREAKS. A bare GET to
`/api/2.0/mlflow/experiments/search` on this server returns **400**, not
200:

```
{"error_code": "INVALID_PARAMETER_VALUE", "message": "Invalid value 0
for parameter 'max_results' supplied. It must be a positive integer"}
```

A perfectly working proxy fails eval 3 as written. The command needs
`?max_results=1` (or a POST with a body).

### P12 — "Q6 → `docs/rfcs/` (revised from `docs/` root), consistent with the S1 doc location" (plan:465-466) — BREAKS

`docs/rfcs/` does not exist, and S1's doc location is not there: S1's
plan recommends `docs/notes/boundary-evaluation.md`
(`.loop/plans/S1-spike-boundary-evaluation.md:143, 193, 206`). The only
`docs/notes/` subdirectory that exists is `docs/notes/audit`. The
stated justification for the resolution is false.

### P13 — the eval file encodes a runnable Definition of Done — BREAKS

`.loop/evals/R1-rollout-mlflow-oauth2-proxy.md` is stale in the same way
as the plan body and contains one row that passes against wrong content.

- **Preamble is false.** "Scheme is `http://` because HAProxy binds only
  `*:80` today (`haproxy.hcl:49`, Q4)". See P3.
- **Row 2** (human redirect) expects `302`/`307` with a `Location:` to
  Vault. Live, `http://mlflow.lab.orangecluster.nl/` returns `301` to
  `https://...`. Fails regardless of implementation.
- **Row 3** (bearer) expects `200`. See P11: it gets `400`.
- **Row 5** (unauth blocked) expects `401` or `302`. It gets `301`. It
  fails in the safe direction, but for the wrong reason, so it no longer
  tests what it names.
- **Row 6 is the shape-check false pass and must be fixed.** Its
  deterministic scorer is `curl -sI http://mlflow.lab.orangecluster.nl/`
  checking for the absence of a `WWW-Authenticate: Basic` header. Run
  against today's unchanged cluster, that request returns a bare
  `HTTP/1.1 301` with no `www-authenticate` header at all, so **the
  check passes right now, with the basic-auth gate fully intact**. Only
  the second half of the row (`nomad alloc exec <haproxy-alloc> grep -A3
  'backend mlflow'`) discriminates, and the scorer cell names both, so
  whether the row is load-bearing depends on the runner honoring the
  second command. The row also cites `haproxy.hcl:116` for the auth
  line, which is now line 153.
- **Row 7** (`/health` unauthenticated 200) gets `301` over `http://`.
- **Count mismatch.** The DoD prose says "the six live evals below"
  while the table has seven rows and the plan says seven (plan:336-338).

No `ls`- or file-existence-scored rows are present; the false-pass risk
is the row 6 header check described above, and row 1 (`nomad job status
mlflow` checking for `running`) which is already true today for the
MLflow half.

## Required attack surface, reported explicitly

1. **Stale premise:** FOUND, twice. P3 (HAProxy TLS, falsified by F3
   shipping the evening of 2026-07-24) and P4 (all eleven anchors moved,
   also by F3 and by Bifrost landing in `services.tf`).
2. **Inlined conclusion:** CONFIRMED. P1. R1 cites mlflow/mlflow#10922
   as an open upstream SSO request "confirmed by the S3 spike finding".
   S3 was dropped and never ran; the issue was closed as `not_planned`
   on 2026-07-05, before R1 was authored; and its subject is a user
   question, not a feature request. P2 inherits the same defect.
3. **Broken dependency edge:** FOUND. P7. Missing F1 edge for the
   `oidc_issuer`/discovery prerequisite, plus L1 delivering only the
   human half of a two-half requirement.
4. **Shape-check eval:** FOUND. P13, row 6. Plus five stale-scheme rows
   and one unattainable expected value.
5. **Unresolvable anchor:** FOUND. P4, eleven anchors, including the
   plan's most-repeated one (`haproxy.hcl:116`).

**Scope-note observation only, per the briefing:** hostnames throughout
R1 already use `mlflow.lab.orangecluster.nl` and are current with T3.
The plan was partially refreshed for T3 and for the Terraform gate, but
not for F3. That partial refresh is what makes the TLS claim so easy to
miss.

## Most dangerous assumption

**P5.** If the bearer path cannot be built the way the plan assumes, R1
cannot deliver its own stated REQUIRED success criterion, and the fix
lives outside R1's declared scope: an irreversible `oidc_issuer` setting
in an Ansible template R1 marks read-only, a restart of a single-server
Nomad cluster, and a decision F1 has open as Q7. The plan's Q3
"prototype and see" framing hides this behind implementation time, and
its own fallback list ("a dedicated bearer-validation path, or Nomad WI
tokens minted with the Vault-OIDC audience") does not survive contact
either: minting WI tokens with the Vault-OIDC audience still needs a
non-default `identity` block whose `iss` the proxy can resolve.

P1 is the close runner-up, because it could change the shape of the
ticket entirely rather than just block one half of it, in the same way
R4 was already re-planned away from oauth2-proxy.

## Required fixes before this plan can leave PLANNING

1. **Delete or correct the mlflow/mlflow#10922 citation and the "S3
   spike finding" attribution** (plan:33-35, plan:5). S3 never ran.
   Either remove the attribution or replace it with a claim R1 verified
   itself.
2. **Survey `mlflow-oidc-auth` as a named fork in Open Questions**, with
   the real constraint stated: MLflow's own docs recommend it
   (`.../self-hosting/security/sso/`), it provides the per-experiment
   authz R1 declares unsolvable, and it requires `mlflow>=3.14.0` while
   the cluster runs 2.20.0. Give a recommendation. Do not decide it
   silently in either direction.
3. **Rewrite P2's non-goal** (plan:99-102) so it no longer asserts as
   fact that fine-grained MLflow authz cannot be had.
4. **Reconcile the whole plan with F3.** Replace the "HAProxy has no
   TLS" Context bullet, the HTTP:80 non-goal, the eval preamble, risk 5,
   and Q4's body with the state the resolved fork at plan:456-459
   already assumes. Switch every eval URL to `https://`.
5. **Re-resolve all eleven broken anchors**: the seven `haproxy.hcl`
   citations (userlist 88-89, bind 92/96, ACL 106, route 117, backend
   152-154, auth line 153, server line 154) and the three `services.tf`
   citations (mlflow job 284-297, postgres secret var 288, mlflow ufw
   rule 66-73).
6. **Resolve the Nomad issuer question before pickup, not during.**
   State plainly that `/.well-known/openid-configuration` returns 404
   today, name `oidc_issuer` as the prerequisite, record that it is
   irreversible once set, add the `depends_on` edge to F1 (or claim the
   `nomad.hcl.j2` edit and the server restart inside R1's code surface
   and re-size the ticket accordingly), and re-check the "no Ansible or
   bootstrap change" sizing claim at plan:27-29.
7. **State explicitly that L1 delivers the human flow only**, so the
   machine flow is R1-original work rather than a pattern R1 "consumes".
8. **Fix the eval file**: switch the scheme, add `?max_results=1` to the
   `experiments/search` calls, make row 6 discriminate on the live
   HAProxy config rather than on a header the 301 never carries, fix the
   `haproxy.hcl:116` citation, and reconcile "six" with the seven rows.
9. **Fix Q6's justification** (plan:465-466): `docs/rfcs/` does not
   exist and S1's location is `docs/notes/boundary-evaluation.md`.

## Method note

All repo reads and all cluster calls were read-only. Cluster commands
used: `nomad job status`, `nomad job status mlflow`, `vault auth list`,
`vault read auth/jwt-nomad/config`, and `curl` GETs against the HAProxy
edge, `192.168.2.50:5050`, `$NOMAD_ADDR/.well-known/*`. No mutating
command was issued. Upstream claims were checked against the GitHub API,
PyPI, `mlflow.org/docs`, `developer.hashicorp.com`, and oauth2-proxy's
source on `raw.githubusercontent.com`.
