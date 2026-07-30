---
verdict: fail
---

# Premise verdict: BROKEN

M1's mechanism does not exist. The plan's central move is "point MinIO's
`identity_openid` at Nomad's OIDC discovery / JWKS (from F1)". Verified
against the deployed MinIO's own source and the live cluster: MinIO
`RELEASE.2025-09-07T16-13-09Z` accepts **only** `config_url` (a real OIDC
discovery document); `jwks_url` is an explicitly **removed** parameter.
Nomad's discovery endpoint is **disabled** cluster-wide and `oidc_issuer`
appears nowhere in the repo. F1 — M1's declared dependency — is still
`ready` (unrun) and its own requirement 5 plus its Q7 state in writing that
F1 delivers JWKS only and leaves the discovery-document work unassigned.
No ticket owns the one change M1 cannot start without.

A second, independent break: M1's R2/E2/E3 specify `identity { aud =
["minio"] }`. Probed live against Nomad 1.11.3 `/v1/jobs/parse`: the
unnamed form configures the task's **default Nomad-API** identity with
`File: false` and leaves `Identities: []`, so no JWT is written to the
alloc and `cat secrets/nomad_minio.jwt` has nothing to read. F1's Q5 was
corrected on 2026-07-25 to say precisely this, naming M1's R2/E2 as the
casualty. M1 was touched on 2026-07-26 and never absorbed the correction.

Confirming the dispatch hypothesis: every `path:line` anchor in the MinIO
job, the bucket module, and `storage.tf` still resolves exactly as
described. The anchors are not where this plan is wrong.

## Per-assumption findings

### P1 — MinIO's `identity_openid` can consume Nomad's JWKS (no discovery document needed). BREAKS

The single load-bearing claim. R1 and code surface treat "OIDC discovery /
JWKS" as interchangeable (`plan:129-131`, `plan:174-176`). They are not, on
this release.

Evidence, from MinIO `RELEASE.2025-09-07T16-13-09Z`
`internal/config/identity/openid/openid.go` (fetched at the deployed tag):

- `// Removed params` / `JwksURL = "jwks_url"` (`openid.go:66-69`), and
  `deprecatedKeys := []string{JwksURL}` with `CheckValidKeys` rejecting it
  (`openid.go:220-231`).
- `func Enabled(kvs config.KVS) bool { return kvs.Get(ConfigURL) != "" }`
  (`openid.go:502-504`). A provider with no `config_url` is simply off.
- `p.URL, _ = xnet.ParseHTTPURL(configURL)` then `p.DiscoveryDoc, err =
  parseDiscoveryDoc(p.URL, ...); if err != nil { return c, err }`
  (`openid.go:293-300`). An unfetchable `config_url` aborts the whole OIDC
  config load.
- `jwksURL := p.DiscoveryDoc.JwksURI; if jwksURL == "" { return c,
  config.Errorf("no JWKS URI found in your provider's discovery doc
  (config_url=%s)", configURL) }` (`openid.go:327-330`). The JWKS URI is
  derived from the discovery document; it cannot be supplied directly.

Corroborated live, read-only against `192.168.2.29:9000` with the root
creds from `secret/default/minio/localstack`:

    mc admin config get <alias> identity_openid
    identity_openid enable= display_name= config_url= client_id=
    client_secret= claim_name=policy claim_userinfo= role_policy=
    redirect_uri_dynamic=off scopes= vendor= keycloak_realm=
    keycloak_admin_url= user_readable_claim= user_id_claim=

No `jwks_url` key exists on the running server.

### P2 — F1 delivers a reachable Nomad OIDC discovery URL for M1 to consume. BREAKS

M1 declares `depends_on = ["F1-foundation-nomad-wi-jwt-trust", ...]`
(`plan:3`) and asserts the discovery URL is an F1 output
(`plan:364-367`, subticket 1 at `plan:335-337`).

Live cluster (read-only):

    curl -s -w "HTTP:%{http_code}" http://192.168.2.30:4646/.well-known/openid-configuration
    HTTP:404
    OIDC Discovery endpoint disabled

    /v1/agent/self -> {"OIDCIssuer": ""}   (Nomad 1.11.3)
    /.well-known/jwks.json -> 200, keys present

Repo: `grep -rn oidc_issuer bootstrap/ deployments/` returns nothing;
`bootstrap/roles/nomad_server/templates/nomad.hcl.j2:11-13` has a bare
`server { ... bootstrap_expect = 1 }` with no `oidc_issuer`.

F1's own plan says this outright:
`.loop/plans/F1-foundation-nomad-wi-jwt-trust.md:119-125` ("Nomad's OIDC
discovery endpoint is DISABLED ... MinIO's `identity_openid` consumes a
discovery document, not a bare JWKS"), requirement 5 at `F1:205-208` ("It
delivers the JWKS URL. It does NOT deliver an OIDC discovery document"),
and Q7 at `F1:569-590` — a section titled "Open question added 2026-07-25
(operator must settle before pickup)", still unresolved: F1's "Resolved
forks" block covers Q1-Q6 only (`F1:509-567`).

Ledger: `F1-foundation-nomad-wi-jwt-trust` stage = `ready`, not `done`
(`.loop/ledger.json`). So the fork is open, F1 has not run, and M1 carries
no subticket to enable `oidc_issuer` either. Enabling it means editing
`nomad.hcl.j2` and restarting the cluster's single Nomad server — real work
in neither ticket's scope.

**This is the confirmed broken dependency edge.** M1 depends on something
F1, as planned, cannot deliver.

### P3 — `identity { aud = ["minio"] }` renders a WI JWT the task can read. BREAKS

R2 (`plan:132-135`), E2 (`plan:252-256`), E3 (`plan:258-264`,
`"$(cat secrets/nomad_minio.jwt)"`), subticket 3 (`plan:343-346`) and eval
rows 2-3 all use the unnamed form.

Probed live, read-only, via `POST $NOMAD_ADDR/v1/jobs/parse`:

- `identity { aud = ["minio"] }` parses to task `Identity` =
  `{"Name":"","Audience":["minio"],"File":false,...}` with
  `Identities: []`. That is the task's **default Nomad-API** identity
  retargeted, and no JWT is written to the alloc.
- `identity { name = "minio" aud = ["minio"] file = true change_mode =
  "restart" }` parses to `Identities: [{"Name":"minio","Audience":
  ["minio"],"File":true,...}]`.

The live `minio` job confirms the shape: `nomad job inspect minio` shows
`Identity.Name = "default"` (aud `nomadproject.io`) alongside
`Identities[0].Name = "vault_default"` (aud `vault.io`).

`F1:537-563` (Q5, "Corrected 2026-07-25") states the same conclusion and
names M1: "It would also have handed M1 a template that cannot work — M1's
own R2/E2 depend on the named form". M1 was last committed 2026-07-26
(`cc22050`) without absorbing it. **Stale premise.**

### P4 — The deployed MinIO release still supports OIDC and STS. HOLDS

M1's relayed finding (`plan:75-107`) is correct and I re-verified it
independently rather than trusting the relay.

- `mc admin config get <alias> identity_openid` returns the full key set
  including `role_policy` and `claim_name=policy` (output in P1).
- Unauthenticated STS probe against `http://192.168.2.29:9000/`:
  `Action=AssumeRoleWithWebIdentity&...&RoleArn=arn:minio:iam:::role/dummy-internal`
  returns `InvalidParameterValue: RoleARN arn:minio:iam:::role/dummy-internal
  is not defined.` — a live, role-aware handler, not a removed feature.
- `mc admin info` reports server version `2025-09-07T16:13:09Z`, matching
  `deployments/infrastructure/services/minio.hcl:66`.

### P5 — Two-phase design (role-policy first, then claim mode with `role_policy` removed) is mechanically sound. HOLDS

R3 at `plan:136-140`, E3/E5 at `plan:258-287`.

- `openid.go:317-322`: "Role Policy (=`%s`) and Claim Name (=`%s`) cannot
  both be set" — so the plan is right that the switch must *replace*, not
  add.
- `cmd/sts-handlers.go:419` `isRolePolicyProvider := roleArnStr != ""` —
  claim mode is exactly "no `--role-arn`", as E5 assumes.
- `sts-handlers.go:476-493`: `GetPoliciesFromClaims(claims,
  iamPolicyClaimNameOpenID())` then `CurrentPolicies(...)`; a single
  policy-name value resolves fine, so Q2's worry (`plan:368-374`) resolves
  favorably. Correctly surfaced as a fork rather than assumed.

### P6 — A named provider can be configured entirely from env vars in the existing `template { env = true }` block. HOLDS (with one naming caveat)

R1 at `plan:127-131`.

`internal/config/config.go:1107-1152` (`GetAvailableTargets`) enumerates
targets from the config store **and** from environment variables
(`env.List(envVarPrefix)`, target name = the env-var suffix). So
`MINIO_IDENTITY_OPENID_CONFIG_URL_NOMAD` does create a named target
without any `mc admin config set`.

Caveat: the target name is the literal env-var suffix, so the provider
will surface as `NOMAD`, not the lowercase `nomad` that E1 (`plan:249`)
and eval row 1 expect. Cosmetic, but it will make a literal-match eval
read as a failure.

### P7 — Nomad WI JWTs carry only the fixed claims; no custom claims. HOLDS

R4's justification at `plan:141-148`.

Live `/v1/jobs/parse` with `identity { ... extra_claims = { foo = "bar" } }`
returns HTTP 400: `Failed to parse job: input.hcl:9,9-21: Unsupported
argument; An argument named "extra_claims" is not expected here.` Keying
the convention on `nomad_job_id` is therefore forced, as the plan says.

### P8 — MinIO may ignore `aud` in role-policy mode (Q5's hedge). BREAKS (low severity)

Q5 at `plan:386-391` hedges "if MinIO ignores `aud` in role-policy mode,
note it for the claim-mode switch". It never ignores it:
`internal/config/identity/openid/jwt.go:189-217` — "Validate that matching
clientID appears in the aud or azp claims"; failure returns "STS JWT Token
has `aud` claim invalid, `aud` must match configured OpenID Client ID".

The plan's *recommendation* (client id `minio`, `aud = ["minio"]`) is
correct. Only the dead branch of the hedge is wrong. Note this also means
`client_id` must be non-empty in role-policy mode (`openid.go:~345`).

### P9 — A "placeholder second named `identity_openid` config" can coexist to prove the multi-IdP shape. BREAKS

R7/E7 (`plan:297-302`), subticket 6 (`plan:354-355`), eval row 7.

`LookupConfig` loops over **every** enabled target and calls
`parseDiscoveryDoc` on each, returning on the first error
(`openid.go:237-300`). A placeholder whose `config_url` is absent or
unreachable therefore does not sit inertly beside the `nomad` provider —
it aborts the entire OIDC config load, taking the `nomad` provider with
it. `seenClientIDs` (`openid.go:283-287`) additionally forbids duplicate
client IDs across providers. The second provider must be a *real*,
fetchable IdP, which M1's non-goals explicitly exclude (`plan:111-113`).

### P10 — `just pre_commit` is the whole gate and is runnable as described. PARTIALLY HOLDS

Correct: `.pre-commit-config.yaml:16-21` `nomad-fmt`, `:22-27`
`terraform-fmt`, `:28-33` `terraform-validate`; `scripts/tf_validate.sh:8-12`
validates exactly the three roots the plan names; `.loop/config.json`
`gates: ["just pre_commit"]` and `require_eval: true`. The plan's removal
of the old "Terraform is not validated" caveat is right.

Wrong / missing:

- `plan:203` cites the `pre_commit` recipe at "line 17-18". It is
  `justfile:18-19` (line 17 is a comment).
- The plan omits the worktree precondition. `terraform-validate` has
  `pass_filenames: false` (`.pre-commit-config.yaml:33`) so it runs on
  every invocation, and `deployments/infrastructure/services.tf:290`
  evaluates `file("${path.root}/../../.ssh/id_rsa")`, which is gitignored
  and absent from a fresh worktree. `just worktree_setup <path>`
  (`justfile:30-32`, added in `3c12c7a`, 2026-07-24) exists precisely for
  this and F1's plan documents it (`F1:290-296`). M1 does not. The loop
  runs tickets in worktrees, so the gate red-fails for a reason unrelated
  to M1.

### P11 — The `path:line` anchors resolve to what the plan claims. PARTIALLY HOLDS

Resolve exactly as described (checked individually):
`minio.hcl:18-25` ports, `:30` `vault {}`, `:32-40` template env=true,
`:34-35` root creds, `:66` image tag; `modules/bucket/main.tf:2` hyphen
replace, `:11-27` `policy_read_write`, `:29-45` `policy_read_only`,
`:47-59` user attachments; `modules/bucket/providers.tf:1-8`
`aminueza/minio ~>3.8.0`; `storage.tf:2-29` `local.buckets`, `:11-16`
memex, `:51-55` `minio_accesskey`, `:57-68` `module "buckets"`;
`memex.hcl:116-127` the MinIO key-pair template.

Drifted:

- `plan:46-48` and `plan:179-181`: "the job is instantiated in
  `deployments/infrastructure/services.tf:301-305`". Line 301 is
  `postgres_secret`; the `nomad_job "minio"` block is `:305-311`. This was
  already wrong when the plan was last committed (`git show
  cc22050:deployments/infrastructure/services.tf`) and is still wrong.
- `plan:160-161`: `services.tf:304` for `minio_secret`. Actual line 309.
- `plan:194-196`: "modeled on the memex block
  (`services.tf:147-163`)" in `deployments/applications/services.tf`.
  Line 147 is the hermes `depends_on`; the memex `nomad_job` is `:159-177`.
  B1 (`ac3267b`, 2026-07-29) pushed it down further after the plan was
  written.

Each drifted anchor still lands within a few lines of the right block, so
severity is moderate, not fatal — but three of the plan's edit points are
mis-cited.

### P12 — MinIO auth today is entirely static-key; no `identity` stanza exists in the repo. HOLDS

`grep -rn "identity" --include=*.hcl deployments/` returns nothing, exactly
as `plan:70-73` claims. `nomad job inspect minio` shows only the implicit
`default` and `vault_default` identities, no `MINIO_IDENTITY_OPENID_*` env,
and a template rendering only `MINIO_ROOT_USER` / `MINIO_ROOT_PASSWORD` /
`MINIO_PROMETHEUS_AUTH_TYPE`. `storage.tf:51-55` and `memex.hcl:116-127`
confirm the static-key path.

## Most dangerous assumption

**P1 — that MinIO's `identity_openid` can be pointed at Nomad's JWKS.** It
cannot; `jwks_url` is a removed parameter and `config_url` must resolve to
a real discovery document. Every M1 subticket from 2 onward, and evals
E1-E7 in full, are unexecutable until Nomad's `oidc_issuer` is set and the
server restarted — work that neither M1 nor F1 currently owns. P2 is the
same defect seen from the dependency side.

## Required attack surface — findings

1. **Stale premise (claim true at authoring, false now).** Two.
   - P3: F1's Q5 correction of 2026-07-25 invalidated M1's `identity { aud
     = ["minio"] }` form. M1 was recommitted 2026-07-26 without absorbing
     it (`F1:537-563`).
   - P10: `just worktree_setup` (`justfile:30-32`, `3c12c7a`) became the
     gate's precondition and M1's gate section never mentions it.
   - Also anchor drift from B1 (`ac3267b`, 2026-07-29) in
     `deployments/applications/services.tf` — see P11.

2. **Inlined conclusion (fact asserted as settled that an unrun ticket was
   to establish).** One, and it is the headline. `plan:129-131` and
   `plan:364-367` treat "Nomad's OIDC discovery URL" as an F1 deliverable.
   F1 is stage `ready`, its Q7 is an unresolved open question added
   2026-07-25, and its requirement 5 disclaims the deliverable outright.
   M1's Q1 partially mitigates by recommending "block subticket 2 on F1
   providing a concrete, reachable URL" — but F1 as planned will never
   provide one, so that recommendation deadlocks rather than resolves.

3. **Broken dependency edge.** CONFIRMED, not refuted. See P1 + P2. MinIO
   genuinely requires `config_url`; it does not accept a JWKS URL on this
   release. F1 delivers JWKS only. F1's Q7 records the fork and it is
   still open.

4. **Shape-check eval.** `.loop/evals/M1-minio-poc-service-account.md`
   exists. **No row uses an `ls`, `grep`, or file-existence scorer** — five
   rows are `deterministic check (<command>)` and two are `model + rubric`.
   No instance of the flagged shape found. Three separate problems do
   apply, though:
   - Row 1 requires `config_url` = "Nomad OIDC discovery URL". That URL
     does not exist (P2), so the row is unsatisfiable as written.
   - Row 7 requires "a placeholder second named config", which aborts
     MinIO's OIDC config load (P9). Unimplementable as written.
   - Row 2 asserts "the `identity` stanza has rendered the WI JWT (e.g. to
     `secrets/nomad_minio.jwt`)" from the unnamed stanza, which writes no
     file (P3).
   - Every deterministic row carries unresolved placeholders (`<alias>`,
     `<alloc>`, `<minio>`, `<other-bucket>`, `<RoleArn-from-E1>`), so no
     row is runnable without operator substitution.

5. **Unresolvable anchor.** Three, all in P11:
   `deployments/infrastructure/services.tf:301-305` (postgres, not minio),
   `services.tf:304` (should be 309), and
   `deployments/applications/services.tf:147-163` (memex is 159-177). Plus
   `justfile` "line 17-18" (should be 18-19).

## Contract hygiene (secondary; recorded, not the headline)

- **Fork surfaced then silently decided the other way.** Q3
  (`plan:376-380`) recommends putting the per-job policy in `storage.tf`
  and keeping `modules/bucket/` stable. Subticket 4 (`plan:347-350`) and
  R5 (`plan:149-153`) both direct the implementer to extend
  `modules/bucket/main.tf` + `variables.tf`. Pick one.
- **Undeclared repo constraint.** T4 (`5262abc`, done 2026-07-26)
  established that the Nomad podman driver rejects
  `name:tag@sha256:digest`. The new `m1-poc.hcl` image reference must be
  digest-only or tag-only. Not mentioned.
- Non-goals (`plan:109-121`) are explicit and good. Tests are homed in the
  code surface. The relayed MinIO finding is honestly scoped and, unusually,
  turned out to be entirely correct.

## Required fixes before this plan can leave PLANNING

1. **Resolve F1's Q7 and assign the `oidc_issuer` work to a ticket.** Until
   Nomad's `/.well-known/openid-configuration` returns a document with a
   `jwks_uri`, M1's subtickets 2-7 cannot start. Either F1 gains a subticket
   that adds `server { oidc_issuer = "<url>" }` to
   `bootstrap/roles/nomad_server/templates/nomad.hcl.j2` and restarts the
   server, or M1 gains that subticket, takes the restart's blast radius into
   its own risk section, and drops F1's discovery-URL claim. Silence is not
   an option; today neither ticket owns it.
2. **Delete the "OIDC discovery / JWKS" equivalence.** Rewrite R1
   (`plan:127-131`) and the code surface (`plan:174-176`) to say
   `MINIO_IDENTITY_OPENID_CONFIG_URL_NOMAD` must point at a discovery
   document, citing `openid.go:66-69` (`jwks_url` removed) and
   `openid.go:502-504` (`Enabled` == `config_url != ""`). Record that a
   JWKS URL will not work.
3. **Fix R2/E2/E3 and eval rows 2-3 to the named identity form:**
   `identity { name = "minio" aud = ["minio"] file = true change_mode =
   "restart" }`. The unnamed form writes no JWT and silently retargets the
   task's Nomad-API identity.
4. **Rewrite or drop E7 / subticket 6 / eval row 7.** A placeholder second
   provider aborts MinIO's whole OIDC config load. Either prove the
   multi-IdP shape from source and config-key evidence without deploying a
   second provider, or defer the check to the sibling Vault-as-IdP ticket
   that will supply a real discovery document.
5. **Add the gate precondition:** `just worktree_setup <path>`
   (`justfile:30-32`) before the first `just pre_commit`, because
   `terraform-validate` (`pass_filenames: false`) evaluates
   `services.tf:290`'s gitignored SSH key. Correct the `justfile` citation
   to `18-19`.
6. **Repair the three drifted anchors:** infra `services.tf:305-311` for
   the minio `nomad_job` and `:309` for `minio_secret`; apps
   `services.tf:159-177` for the memex block.
7. **Resolve the Q3-vs-subticket-4 contradiction** (module extension versus
   a `storage.tf`-local resource) so the implementer is not handed both.
8. **Correct Q5's dead branch:** MinIO always validates `aud` against
   `client_id` (`jwt.go:189-217`), in role-policy mode included. Drop "if
   MinIO ignores `aud`". Note that E1's expected provider name will be the
   env-var suffix `NOMAD`, not lowercase `nomad` (`config.go:1128-1147`).

## Method note

Plan fingerprint verified locally with `sha256sum`:
`52ef286ad6cfd14ca7439066f49b91e7fef0929a0bb60cb233da5850e6a45bdb`. Omitted
from the header because this verdict is a `fail` and must not authorize the
flip to `ready`.

All cluster interaction was read-only: `curl` GETs against Nomad, `vault kv
get`, `nomad job inspect` / `node status`, `mc admin config get` / `admin
info` (credentials passed via a transient `MC_HOST_*` env var, no `mc alias
set`, no config written), `POST /v1/jobs/parse` (parse-only, creates no
job), and two unauthenticated STS calls with a junk token that failed
validation. No `vault write/delete/patch`, no `nomad job run/stop`, no `mc
admin` mutation, no `terraform apply`, no mutating git command. MinIO source
was read from the `RELEASE.2025-09-07T16-13-09Z` tag on
`raw.githubusercontent.com/minio/minio`, matching the version `mc admin
info` reports for the running server.
