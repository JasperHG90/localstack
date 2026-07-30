---
verdict: fail
---

# Plan verdict — M2-minio-poc-human-tiers (pass `plan-validator`)

Plan fingerprint verified locally: `sha256sum .loop/plans/M2-minio-poc-human-tiers.md`
returns `9487c738a8e997e2d1031decc14c297ba072a3eb8ed3b933144f44cbb4fa241f`,
matching the briefing. Per the contract a `fail` carries no `plan:` line, so this
verdict cannot authorize the `PLANNING -> READY` flip.

## Premise verdict: PARTIALLY SOUND

The load-bearing core holds. Vault really does serve an OIDC discovery document
(unlike Nomad — M1's trap does **not** transfer), MinIO's `identity_openid`
subsystem really does support multiple named targets with `role_policy`, and the
console really does still serve on this release. The approach is buildable.

What fails is the layer just above the approach: the plan's stated primary cost
driver is false, one required env var it names is deprecated (and the one that
replaces it is absent from the plan entirely), the close-out is gated on a
**dropped** ticket, and two of the eval file's deterministic 100%-threshold rows
would fail a *correct* implementation. Those last two are why this is a `fail`
rather than `pass-with-required-fixes`: the fixes have to land in
`.loop/evals/M2-minio-poc-human-tiers.md` as well as the plan, and a passing
verdict would flip the ticket to `ready` with an acceptance gate that cannot be
satisfied.

## Assumptions attacked

### P1 — The env template at `minio.hcl:32-40` is the only env injection point and holds exactly the three named variables. **HOLDS**
`deployments/infrastructure/services/minio.hcl:32-40` is the `template { env = true }`
block with `MINIO_ROOT_USER`, `MINIO_ROOT_PASSWORD`, `MINIO_PROMETHEUS_AUTH_TYPE`.
Confirmed against the *running* job: `nomad job inspect minio` shows `Env: null`
and exactly that one embedded template. Nothing else injects env.

### P2 — Console + OIDC survive on `RELEASE.2025-09-07T16-13-09Z`. **HOLDS**
Re-verified independently rather than trusting the relayed finding.
`http://192.168.2.29:9001/` returns HTTP 200; `https://minio.lab.orangecluster.nl/`
returns HTTP 200. `mc admin config get <alias> identity_openid` against the live
server returns the key set including `role_policy`. The relayed finding's
instruction not to re-litigate from release notes is correct.

### P3 — Three named `identity_openid:<tier>` providers, env-addressable as `MINIO_IDENTITY_OPENID_<KEY>_<tier>`, each rendering a console button. **HOLDS (mechanism) with a case defect**
- Multi-target is real: `cmd/config-current.go:129-132` declares
  `IdentityOpenIDSubSys` with `MultipleTargets: true`.
- Env naming is real: `internal/config/config.go:1128-1147` derives targets by
  stripping the prefix `MINIO_IDENTITY_OPENID_<PARAM>_`, and
  `internal/config/config.go:1157-1164` (`getEnvVarName`) reconstructs the env
  name with the target appended **verbatim, with no case folding**.
- Live probe: `mc admin config get lab identity_openid:admin` returns
  ``there is no target `admin` for subsystem `identity_openid` `` — the error is
  about the *target* not existing, which itself proves named targets are parsed.
- Per-tier role ARNs are distinct because the ARN resource id is a SHA-1 of the
  **client id**, not of the issuer domain
  (`internal/config/identity/openid/openid.go:352-366`). Three clients on one
  Vault issuer therefore yield three distinct ARNs. The design works.
- **Defect:** Code surface says "`<tier>` uppercased as the provider suffix",
  which produces targets `ADMIN`/`WRITER`/`READER`. Every eval command in the
  plan and in the eval file queries lowercase `identity_openid:admin`. Given the
  no-case-folding evidence above, those queries return
  ``there is no target `admin` `` against a correct implementation.

### P4 — `MINIO_IDENTITY_OPENID_REDIRECT_URI_<tier>` is a valid per-tier setting. **BREAKS**
`internal/config/identity/openid/help.go:107-108` for this exact release tag:

    Key:         RedirectURI,
    Description: `[DEPRECATED use env 'MINIO_BROWSER_REDIRECT_URL'] Configure custom redirect_uri for OpenID login flow callback`

The replacement is **server-global**, not per-provider:
`cmd/common-main.go:715-725` reads `config.EnvBrowserRedirectURL` once into
`globalBrowserRedirectURL` (`cmd/globals.go:196`), `logger.Fatal` on a bad value.
The key is also `HiddenIfEmpty: true`
(`internal/config/identity/openid/openid.go:112-116`), which is why the live
`mc admin config get` output omits it — the plan's relayed finding read that
omission as "the key list", and its Code surface then named a key that release
documents as deprecated.

Three consequences the plan does not carry:
1. All three tiers necessarily share **one** redirect URI. Eval step 4's
   `<reader-redirect-uri>` / `<admin-redirect-uri>` implies per-tier URIs.
2. `MINIO_BROWSER_REDIRECT_URL` must be added to the `minio.hcl` env template.
   The plan never mentions it.
3. HAProxy terminates TLS and sets **no** `X-Forwarded-Proto` / `forwardfor`
   (`deployments/infrastructure/services/haproxy.hcl` — grep for
   `X-Forwarded|forwardfor|option http` returns nothing). Without
   `MINIO_BROWSER_REDIRECT_URL`, MinIO derives the callback from the Host header
   and will build an `http://` redirect that cannot match F2's `https://`
   registration. This is the concrete mechanism by which the browser flow
   silently fails, and it is exactly the caveat the plan flagged but left open.

### P5 — "MinIO validates each `role_policy` name at startup; the policies must be applied first." **BREAKS**
This is the plan's stated effort driver ("Size / Effort": *"Effort is driven by
the cross-layer ordering constraint"*), its "likeliest failure" risk, and the
entire justification for subticket 3. The source says otherwise:
- `internal/config/identity/openid/openid.go:336-338` comments
  *"RolePolicy is validated by IAM System during its initialization"* and does
  no check itself.
- `cmd/iam.go:369-376` is that initialization. It is
  `sys.rolesMap = make(...)` followed by `maps.Copy(sys.rolesMap, sys.OpenIDConfig.GetRoleInfo())`
  and `sys.printIAMRoles()`. There is **no** lookup of the policy name against
  the policy store, and no error path. Policy resolution happens per-request via
  `GetRolePolicy` (`cmd/iam.go:578-588`).

So a missing tier policy denies access at login time; it does not reject the
config and does not crash-loop the job. The plan's own "Resolved fork Q2"
already asserts the opposite of its Risk section ("server-up-then-policies is
the natural, existing order"), and neither side cites evidence. The source
settles it in Q2's favor — which means subticket 3 ("Wire the ordering") has no
work in it and the Size/Effort rationale is wrong.

### P6 — Vault's OIDC provider exposes a usable discovery document (the M1 trap). **HOLDS**
`curl http://192.168.2.30:8200/v1/identity/oidc/provider/default/.well-known/openid-configuration`
returns HTTP 200 with `issuer`, `jwks_uri`, `authorization_endpoint`,
`token_endpoint`, `response_types_supported: ["code"]`. This is categorically
unlike Nomad's `OIDC Discovery endpoint disabled`. M1's broken edge does not
transfer to M2. `vault list identity/oidc/provider` → `default`;
`vault list identity/oidc/key` → `default`; Vault 1.21.4, unsealed.

Two riders the plan should carry:
- MinIO fetches the discovery doc **at config load**
  (`internal/config/identity/openid/openid.go:296`, `parseDiscoveryDoc`, whose
  error is returned straight out of `LookupConfig`). An issuer unreachable at
  MinIO boot fails the whole `identity_openid` subsystem. That is a larger
  blast-radius risk than the ordering risk the plan does name, and it is absent.
- The live provider's issuer is `http://192.168.2.30:8200/v1/identity/oidc/provider/default`,
  not the `https://vault.lab.orangecluster.nl` F2 promises. F2 must set
  `issuer_host` + `https_enabled`; M2's config URL is only as good as that.
  `https://vault.lab.orangecluster.nl/v1/identity/oidc/provider/default/.well-known/openid-configuration`
  returns 200 today, so the path exists once F2 sets the issuer.

### P7 — F2 writes each tier's client id/secret to KV `default/minio/oidc/<tier>`. **BREAKS (inlined conclusion)**
M2's "Resolved forks" states this as settled and adds "Flag as an F2 interface
requirement". It was never flagged. `grep -n "minio/oidc|default/minio"
.loop/plans/F2-foundation-vault-oidc-provider.md` returns **no match**. F2's own
Code surface (§7) says only *"add `vault_kv_secret_v2` entries writing each
client's `client_id` / `client_secret` to `vault_mount.kvv2.path`"* with no path
convention, and F2 is `ready`, never run. Subticket 2 tells the implementer to
reference "the F2 Vault paths" that no artifact defines.

### P8 — F2 produces clients readable at `identity/oidc/client/<tier>` and assignments `<tier-assignment>`. **UNCERTAIN**
Live Vault has one client (`test`) and two assignments (`allow_all`, `test`) —
`vault list identity/oidc/client`, `vault list identity/oidc/assignment`. F2's
plan names neither the client names nor the assignment names. Eval row 3 and
plan step 3 hard-code a naming convention that no upstream artifact commits to.
I cannot settle whether F2 will produce these names; that is the point.

### P9 — Q4's redirect `https://minio.lab.orangecluster.nl/oauth_callback` reaches the console. **HOLDS, with a scheme mismatch against F2**
`deployments/infrastructure/services/haproxy.hcl:98` (`acl is_minio`), `:109`
(`use_backend minio`), and `:127-128` (`backend minio` / `server minio1
192.168.2.29:9001 check`) route the hostname to the **console** port, not the S3
port (`s3.lab.orangecluster.nl` → `:9000`). HTTPS to that host returns 200.
Note for the fix list: F2's Q4 placeholder is
`http://minio.lab.orangecluster.nl/oauth_callback` (F2 plan line 345) while M2
resolves to `https://`. M2 itself says these "must match exactly"; MinIO enforces
exact match (`invalid_redirect_uri`, observed live — see P13).

### P10 — "M2 must not be marked done until F4 lands, so the MinIO console resolves from non-Mac LAN devices, not just via the operator's `/etc/hosts`." **BREAKS (stale premise + broken dependency edge)**
Every clause is now false:
- **F4 is dropped.** `.loop/ledger.json` entry `F4-foundation-dnsmasq-localstack-dns`
  has `"dropped": true`. It will never land, so the plan's close-out condition
  can never be met as written.
- **`.localstack` is retired.** T3 (`stage: done`, commit `a6cc9c6`, 2026-07-26)
  renamed all twelve hostnames; its own message states *"After this applies, no
  .localstack name is served."* N2 (`stage: done`) then removed dnsmasq entirely
  in favor of public DNS.
- **The `/etc/hosts` premise is dead.** `grep -c orangecluster /etc/hosts` → `0`,
  and `dig +short minio.lab.orangecluster.nl @1.1.1.1` → `192.168.2.30`. The name
  resolves from public DNS, for every LAN device, with no local resolver.

This is the residue the T3 commit warned about in its own message ("left three
downstream plans describing resources this apply destroys"). T3 surgically
rewrote only M2's Q4 line (`git show a6cc9c6 -- .loop/plans/M2-...md` is a
one-line diff) and left the closing Dependencies paragraph untouched. The ledger
edge for M2 is only `[F2, A1]`, so the harness will not block — but an
implementer following the plan text will.

### P11 — Every `path:line` anchor resolves to the thing described. **BREAKS (three of them)**
| Plan claim | Actual | Status |
|---|---|---|
| `services.tf:301-306` — the `nomad_job "minio"` resource | `nomad_job "minio"` is at **306-311**; 301-306 is the tail of `nomad_job "postgres"` plus the `### Minio` comment | shifted +5 |
| `services.tf:333-355` — "input-map convention used by the `grafana` job" | 333-343 is `nomad_job "prometheus"`; grafana starts at **346** | shifted +13 |
| `deployments/applications/providers.tf:40-44` — the `minio` provider | provider is at **44-48**; 40-44 is the tail of `provider "consul"` | shifted +4 |
| `minio.hcl:32-40`, `:34-35`, `:42-46`, `:66` | all exact | holds |
| `modules/bucket/main.tf:11-45` | exact (11 = `policy_read_write`, 45 = close of `policy_read_only`) | holds |
| `deployments/applications/services.tf:11-14` | exact (`ephemeral "vault_kv_secret_v2" "minio_admin"`) | holds |

The three shifts trace to `services.tf` and `providers.tf` gaining the HAProxy
job and provider blocks after M2 was authored (`git log` on those files:
`a6cc9c6` T3 2026-07-26, `ac3267b` B1 2026-07-29).

### P12 — `just pre_commit` is the gate and covers HCL fmt + Terraform fmt/validate over three roots. **HOLDS**
`justfile:18-19` (`pre_commit: pre-commit run --all-files`);
`.pre-commit-config.yaml:16-21` `nomad-fmt`, `:22-27` `terraform-fmt`,
`:28-33` `terraform-validate` → `scripts/tf_validate.sh`, whose `roots=()` array
is exactly `deployments/infrastructure`, `deployments/applications`,
`deployments/applications/modules/bucket`. `detect-private-key` at `:12`.
The plan's gate section is discovered, not assumed. No CI workflow exists —
also correct.

### P13 — Eval step 4 / eval row 5 can observe `access_denied` via `vault read .../authorize`. **BREAKS**
Probed read-only against the live `test` client with a deliberately invalid
redirect so nothing could be issued:
- `vault read identity/oidc/provider/default/authorize client_id=... redirect_uri=https://invalid.example/none ...`
  prints `Code: 400. Errors:` — **with the error list empty**. The CLI drops the
  OIDC error body.
- The same request via `curl` returns
  `{"error":"invalid_redirect_uri","error_description":"redirect_uri is not allowed for the client","state":"abc123xyz"}`.

So the deterministic scorer as written ("`vault read .../authorize` returns
`access_denied`") observes nothing to match against. It must use `curl` and parse
the JSON body. This also incidentally confirms MinIO/Vault enforce exact
redirect-URI matching, which sharpens P9.

### P14 — Eval row 1's `redirect_uri` expectation is satisfiable. **BREAKS**
Row 1 and plan step 1 require each tier block to show "non-empty `config_url`,
`client_id`, and `redirect_uri`", scorer `deterministic`, threshold `100%`. Per
P4, `redirect_uri` is deprecated and `HiddenIfEmpty`; a correct implementation
using `MINIO_BROWSER_REDIRECT_URL` leaves it empty and `mc admin config get`
will not print it. A deterministic 100% row that fails correct work is worse than
no row.

### Shape-check eval (required surface item 4)
`.loop/evals/M2-minio-poc-human-tiers.md` has six rows. **No row uses `ls`,
`grep`, or file-existence as its scorer** — the deterministic rows are
`mc admin config get`, `mc admin policy info`, and `vault read`, all content-
checking, and the two judgment rows are `model + rubric` and `human + rubric` at
4/5. On shape the eval is sound. It fails on content: rows 1 and 5 (P14, P13)
cannot pass a correct implementation, and row 1's lowercase `identity_openid:admin`
contradicts the plan's uppercase-suffix instruction (P3).

## Most dangerous assumption

**P4** — that the redirect URI is a per-tier `identity_openid` setting.

P10 is the loudest stale finding and P5 falsifies the most plan text, but both
fail *visibly*: a dropped dependency gets noticed, and a non-existent ordering
problem simply costs nothing. P4 fails *silently and late*. The implementer sets
`MINIO_IDENTITY_OPENID_REDIRECT_URI_ADMIN`, MinIO accepts it as a config key,
`terraform apply` succeeds, the job starts, the buttons render — and the browser
flow dies at the callback with a scheme or URI mismatch that surfaces only in
step 5, the one step that cannot be scripted. The per-tier-redirect assumption is
also baked into F2's client registrations, so discovering it late means
re-planning F2's `redirect_uris` variables too. Everything upstream of it looks
green.

## Required fixes before this plan can leave PLANNING

1. **Redirect URI (P4).** Drop `MINIO_IDENTITY_OPENID_REDIRECT_URI_<tier>` from
   Code surface. Add the global `MINIO_BROWSER_REDIRECT_URL` to the `minio.hcl`
   env template and state that all three tiers share one callback. Record that
   HAProxy sets no `X-Forwarded-Proto`, so this variable is what makes the
   `https://` callback correct.
2. **Ordering (P5).** Delete the "MinIO validates `role_policy` at startup"
   claim, rewrite the Size/Effort rationale (the cross-layer ordering is not the
   cost), and drop or repurpose subticket 3. Cite `cmd/iam.go:369-376`. Resolve
   the standing contradiction with Resolved-Q2 in Q2's favor.
3. **F4 (P10).** Delete the closing Dependencies paragraph. F4 is dropped,
   `.localstack` is retired, and `minio.lab.orangecluster.nl` resolves from
   public DNS. Nothing about DNS gates M2's close-out.
4. **Eval row 1 (P14, P3).** Remove the `redirect_uri` expectation; assert
   `role_policy`, `config_url`, `client_id` only. Settle the target-name case
   and make the plan's Code surface and every eval command agree.
5. **Eval row 5 (P13).** Re-express the cross-tier-deny check as a `curl`
   against `/v1/identity/oidc/provider/<provider>/authorize` parsing
   `.error == "access_denied"`. `vault read` swallows the body.
6. **F2 interface (P7, P8).** Either land `default/minio/oidc/<tier>` and the
   client/assignment naming in F2's plan, or restate them in M2 as Open
   Questions rather than Resolved forks. Reconcile F2's `http://` redirect
   placeholder with M2's `https://`.
7. **Anchors (P11).** Repoint `services.tf:301-306` → `:306-311`,
   `services.tf:333-355` → the grafana map at `:346-...`, and
   `providers.tf:40-44` → `:44-48`.
8. **Boot-time discovery risk (P6).** Add to Risk assessment: MinIO parses the
   OIDC discovery document during config load
   (`internal/config/identity/openid/openid.go:296`), so an unreachable Vault
   issuer at MinIO start fails the `identity_openid` subsystem. This is a larger
   blast radius than the ordering risk currently named.

## Method note

Read-only throughout. Cluster interaction was limited to `vault status`,
`vault list`, `vault read`, `curl` GETs, `nomad job inspect`, and
`mc admin config get` / `admin info` via `MC_HOST_*` with `--config-dir` pointed
at a scratch directory (no alias written to the user's `~/.mc`). MinIO behavior
was verified against the exact release the job runs
(`RELEASE.2025-09-07T16-13-09Z`) by reading that tag's source from
`raw.githubusercontent.com`, not from intuition or release notes. No mutating
command was run and no repo file was modified; the only write is this verdict.
