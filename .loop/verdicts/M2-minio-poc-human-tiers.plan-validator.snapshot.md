---
epic = "minio"
depends_on = ["F2-foundation-vault-oidc-provider", "A1-audit-plan-premise-sweep"]
priority = 10
summary = "Give humans tiered MinIO console access (Admin, Reader, Writer) via three Vault OIDC clients this ticket creates itself, one shared browser-redirect callback (MinIO's per-tier redirect_uri is deprecated and server-global instead), and matching MinIO role policies."
tags = ["minio", "vault", "oidc", "terraform"]
---

# Ticket: M2-minio-poc-human-tiers

## 1. Title

Give humans tiered MinIO console access (Admin / Reader / Writer) via
three Vault-gated OIDC providers on the MinIO job, each bound to a
matching MinIO role policy, sharing one browser-redirect callback.

## 2. Size / Effort

**Medium.** Two Terraform layers change, plus a Vault OIDC client set
this ticket creates itself — previously assumed to already exist from
F2. It does not (§5, §6.4).

The infrastructure layer gains: three `identity_openid:<TIER>`
provider env sets and ONE shared `MINIO_BROWSER_REDIRECT_URL` in the
MinIO job env template (`minio.hcl`); three
`vault_identity_oidc_client` + `vault_identity_oidc_assignment` +
`vault_identity_oidc_key_allowed_client_id` triples in `oidc.tf`, one
per tier, mirroring L1's oauth2-proxy pattern three times; three new
`app_user_groups` tier entries in `roles.tf`; and three KV2
client-credential writes in `secrets.tf`. The applications layer gains
three named MinIO policies, unchanged from the original scope.

None of this is architecturally novel — it is the L1/memex consumer
pattern (`docs/vault-human-auth.md`'s "Adding a service" procedure)
repeated three times. The effort is mechanical repetition plus getting
the ONE shared browser-redirect-URL wiring right (§6.3, §9), not a
genuine cross-layer ordering problem.

*(Rewritten 2026-08-22, plan-review rework. The previous version named
the cross-layer ordering constraint as the cost driver. That claim is
false — see the removed Risk bullet in §9 — and is no longer any part
of the estimate.)*

## 3. Triggered by

The localstack home-lab auth epic. Confirmed handoff: Vault is the
OIDC IdP for humans (Zitadel dropped). Humans need console access to
MinIO segmented by tier, gated so a reader cannot assume admin. This
ticket is the MinIO (relying-party) side of that design. F2 built the
shared OIDC provider/key/scope (`done`); this ticket, like L1 before
it, creates its own per-tier client registrations against that shared
infrastructure.

## 4. Context

Today MinIO runs as a Nomad job with only root credentials and no
OIDC:

- `deployments/infrastructure/services/minio.hcl:32-40` — the
  `template { env = true }` block that injects `MINIO_ROOT_USER`,
  `MINIO_ROOT_PASSWORD`, and `MINIO_PROMETHEUS_AUTH_TYPE`. This is the
  only place env is injected into the MinIO container, and it is where
  the three tier `MINIO_IDENTITY_OPENID_*_<TIER>` variable sets and
  the one shared `MINIO_BROWSER_REDIRECT_URL` go.
- `deployments/infrastructure/services.tf:328-333` — the
  `nomad_job "minio"` resource renders the job with
  `templatefile(..., { minio_secret = ... })`. Any new templatefile
  input the job needs (KV paths for the per-tier client credentials,
  the shared config URL, the shared browser redirect URL) is added to
  this map. *(Anchor corrected 2026-08-22: this resource is now at
  `:328-333`. It was `:301-306` in the original plan and `:306-311` at
  the 2026-07-30 review; `services.tf` gained the HAProxy and Redis
  jobs in between. Re-read the file before touching it — it has moved
  twice already.)*
- `deployments/infrastructure/services/minio.hcl:42-46` — the
  `minio-console` service on port 9001. The one shared OIDC callback
  targets this console.
- `deployments/infrastructure/oidc.tf:1-10` — F2's own header comment:
  it owns only the signing key, the shared `groups` scope, the
  provider, and one throwaway smoke client. "Consumer clients
  (dash/L1, mlflow/R1, phoenix/R4, the MinIO tiers/M2) are NOT created
  here. Each consumer ticket creates its own
  `vault_identity_oidc_client`." This ticket is that consumer.
- `deployments/infrastructure/oidc.tf:152-187` — the L1 (oauth2-proxy)
  block: the worked example this ticket copies three times. It shows a
  `locals` redirect-URL value referenced both by the Vault client's
  `redirect_uris` and by `services.tf`'s templatefile map, so the
  registration and the jobspec value can never drift apart
  independently.
- `deployments/infrastructure/services/oauth2-proxy.hcl:52` — L1's own
  jobspec: `OAUTH2_PROXY_REDIRECT_URL="${redirect_url}"`, a plain
  templatefile variable (not a Vault-templated secret, since a
  redirect URL is not a secret). `oauth2-proxy.hcl:19-21`'s header
  comment states the same reasoning this ticket relies on: "HAProxy
  sends no X-Forwarded-Proto/-Host, so the redirect URL is given
  explicitly ... instead of trusting headers nobody sends." Confirmed
  fresh for MinIO's own host: a grep for `X-Forwarded|forwardfor` over
  `deployments/infrastructure/services/haproxy.hcl` returns zero
  matches (probed 2026-08-22).
- `docs/vault-human-auth.md:262-298` — "Adding a service that logs
  people in through Vault", the four-answer "who is allowed in"
  checklist and the four-to-two resource list. This ticket is a
  branch-2 consumer (`local.app_user_groups`), like memex
  (`docs/vault-human-auth.md:361-366`) — real per-tier RBAC, not L1's
  flat `allow_all`.
- `deployments/infrastructure/roles.tf:153-165` — `local.app_user_groups`,
  the extension point memex already used. Its own comment already
  names the exact convention this ticket adopts:
  `"app-minio-readers" = "Read-only access to MinIO buckets"`
  (`roles.tf:157`).
- `deployments/infrastructure/secrets.tf:186-201` — the
  `oauth2_proxy_oidc_client` KV2 write: the fresh precedent for
  writing a Vault-issued `client_id`/`client_secret` pair to KV2 under
  a service's own prefix, never as a `.tf` literal.
- `deployments/applications/modules/bucket/main.tf:11-45` — the
  existing `minio_iam_policy` pattern (per-bucket read-write and
  read-only policies with `s3:*` and `s3:GetObject`/`s3:GetBucketLocation`
  statements). The three tier policies mirror this JSON shape but are
  cluster-wide, not scoped to one bucket.
- `deployments/applications/providers.tf:44-48` — the `minio` provider,
  authenticated with the root access/secret key pulled from the
  ephemeral Vault secret. This is the credential that lets the
  applications layer create the tier policies. *(Anchor corrected
  2026-08-22: `:44-48`, unchanged since the 2026-07-30 review; it was
  `:40-44` in the original plan.)*
- `deployments/applications/services.tf:11-14` — the ephemeral
  `vault_kv_secret_v2 "minio_admin"` at `default/minio/localstack`
  feeding the provider above. Unchanged, confirmed exact.

What is missing: no `identity_openid` provider is configured on the
job, no admin/writer/reader MinIO policies exist, and no MinIO-specific
Vault OIDC clients exist (`vault list identity/oidc/client` returns
`memex`, `nomad`, `oauth2-proxy`, `oidc-smoke` only — probed
2026-08-22).

### Relayed finding: console OIDC login is still available on this release

Verified live against the running server on 2026-07-26, re-confirmed
2026-08-22 (`curl -s -o /dev/null -w '%{http_code}' https://minio.lab.orangecluster.nl/`
returns `200`). This ticket is the one most exposed to MinIO's
`RELEASE.2025-05-24T17-08-30Z` notes, which say "Embedded UI Console is
now deprecated" and "External IDP logins via LDAP/OIDC are removed".
The job runs a release **after** that date
(`RELEASE.2025-09-07T16-13-09Z`, `minio.hcl:66`), so on the release
notes alone M2 reads as impossible. **The deployed server contradicts
it on both counts.** Do not re-litigate this from release notes.

Evidence, all read-only:

- **The console still serves.** `https://minio.lab.orangecluster.nl/`
  returns `200`.
- **The OIDC subsystem is present and multi-target.** The
  `IdentityOpenIDSubSys` declaration (`cmd/config-current.go`, pinned
  tag source, read directly) sets `MultipleTargets: true`.
- **Every key this ticket needs is settable**, including `role_policy`
  (the per-tier binding this ticket is built on).

One thing the relayed finding got wrong, corrected by the 2026-07-30
plan review and this rework: it assumed the three tiers would each
carry their own `redirect_uri`. They do not — see §6.3.

### One human identity exists on this cluster

`vault list auth/userpass/users` (probed 2026-08-22) returns exactly
one user, `operator`. `docs/vault-human-auth.md` states this plainly
for the `developer`/`admin` design: "there is one person." This shapes
how the cross-tier-denial acceptance in §8 can actually be exercised —
see the Open Question in §11.

## 5. Non-goals / out of scope

- **F2's shared singleton resources.** This ticket does not touch the
  OIDC provider (`vault_identity_oidc_provider.lab`), the signing key
  (`vault_identity_oidc_key.lab`), the shared `groups` scope, or F2's
  throwaway smoke client. Those are F2's, `done`, and this ticket only
  consumes them: registers three new clients against the same key,
  appends to the same `allowed_client_ids` list.
- **The Vault-side per-tier client/assignment/KV work IS this
  ticket's own** — *(corrected 2026-08-22)*. The previous version of
  this section wrongly assigned that work to F2, which never shipped
  it (`oidc.tf:1-10`; live `vault list identity/oidc/client` has no
  `minio-*` entry). Do not read the old boundary; §6.4 and §7 are the
  current one for this ticket's scope.
- The machine/service (STS `AssumeRoleWithWebIdentity` or access-key)
  path. This ticket is the human console-login path only.
- Any change to existing per-bucket policies in `modules/bucket/` or to
  the service-account users in `deployments/applications/storage.tf`.
- Per-bucket scoping of the tier policies. The POC grants cluster-wide
  tier access; bucket-scoped tiers are a later refinement.
- Backfilling `docs/vault-human-auth.md`'s "Nomad is the first real
  consumer" worked-example list with a MinIO entry. Useful follow-up,
  not required for this ticket.

## 6. Requirements & restrictions

Must achieve:

1. Three `identity_openid:<TIER>` providers on the MinIO job — targets
   `ADMIN`, `WRITER`, `READER`, **uppercased, and this casing is
   load-bearing.** MinIO's target-name parsing does no case folding on
   the target suffix (the `getEnvVarName` function in
   `internal/config/config.go`, pinned tag source, read directly), so
   every `mc admin config get` / `curl` command anywhere in this
   ticket or its eval file must query the SAME casing the env vars use. Each provider's `role_policy` is
   set to the matching MinIO policy name — lowercase
   (`minio-admin`/`minio-writer`/`minio-reader`), a **separate,
   unrelated casing convention** from the OIDC target suffix. Do not
   conflate the two.
2. Three named MinIO policies: admin = full access; writer =
   put/get/list + multipart + delete (Resolved fork Q5); reader =
   get/list.
3. **ONE shared `MINIO_BROWSER_REDIRECT_URL` env var on the job — no
   per-tier redirect URI.** All three tiers resolve to the SAME
   callback, because MinIO's per-provider `redirect_uri` key is
   deprecated in the pinned release
   (the `RedirectURI` `HelpKV` entry in
   `internal/config/identity/openid/help.go`, pinned tag source, read
   directly: `[DEPRECATED use env 'MINIO_BROWSER_REDIRECT_URL']`) and
   its replacement is read ONCE, globally, into
   `globalBrowserRedirectURL` (function `serverHandleEnvVars` in
   `cmd/common-main.go`), never per provider target.
   - Set `MINIO_BROWSER_REDIRECT_URL` to the bare console origin,
     `https://minio.lab.orangecluster.nl` — **no trailing slash, no
     `/oauth_callback` suffix.** MinIO's console appends
     `/oauth_callback` itself when it builds the callback it sends to
     the IdP: `callback := getConsoleEndpoints()[0] + "/oauth_callback"`
     (function `buildOpenIDConsoleConfig` in `cmd/common-main.go`,
     pinned tag source, read directly), and `getConsoleEndpoints()[0]`
     returns `globalBrowserRedirectURL.String()` when it is set
     (function `getConsoleEndpoints` in `cmd/net.go`).
   - Register `https://minio.lab.orangecluster.nl/oauth_callback`
     (WITH the suffix) as the single `redirect_uris` entry shared by
     all three Vault clients. HAProxy already routes that hostname to
     the console port, not the S3 port: `haproxy.hcl:98` (`acl
     is_minio`), `:109` (`use_backend minio`), `:127-128` (`backend
     minio` → `192.168.2.29:9001`) — confirmed live, `200` over HTTPS
     (probed 2026-08-22).
   - State this explicitly wherever the plan or eval names a
     per-tier redirect: there is no such thing on this release.
4. **This ticket creates its own Vault-side OIDC scaffolding for
   MinIO** — F2 did not (§5). Follow `docs/vault-human-auth.md`'s
   "Adding a service" procedure, mirroring L1's oauth2-proxy blocks in
   `oidc.tf` three times, branch 2 of the "who is allowed in" checklist
   (real per-tier RBAC, unlike L1's flat `allow_all`):
   - Three tier groups in `local.app_user_groups`
     (`roles.tf:153-165`): `app-minio-admins`, `app-minio-writers`,
     `app-minio-readers`.
   - Three `vault_identity_oidc_client` + `vault_identity_oidc_assignment`
     + `vault_identity_oidc_key_allowed_client_id` resources in
     `oidc.tf`, one triple per tier, each client's `redirect_uris`
     the one shared URL from requirement 3, each assignment bound to
     ONLY its own tier's group id.
   - Three `vault_kv_secret_v2` writes in `secrets.tf` under
     `default/minio/oidc/<tier>` (lowercase: `admin`/`writer`/`reader`
     — again, unrelated to the uppercase OIDC target casing), mirroring
     `secrets.tf:186-201`'s `oauth2_proxy_oidc_client` pattern.
   - Append all three client ids to `local.oidc_provider_client_ids`
     (`oidc.tf:79-86`). Vault gates the provider on this list and
     offers no standalone resource for it; an omitted client is
     refused at the authorize endpoint.
5. Bind each tier's `vault_identity_oidc_assignment` to ONLY its own
   group's id — `local.app_user_group_ids["app-minio-admins"]`, etc.
   `roles.tf:196-208`'s own comment names this exact mistake: binding
   every tier's id (as F2's throwaway smoke client deliberately does)
   silently admits every other tier's members.
6. The MinIO console shows one login button per provider (three
   buttons), and each client's own Vault assignment refuses cross-tier
   login. Verified mechanism: role ARNs are derived as
   `sha1(client_id)` (the role-ARN construction inside `LookupConfig`,
   `internal/config/identity/openid/openid.go`, pinned tag source), so
   three distinct clients on the SAME issuer
   still yield three independent role bindings even though they share
   one callback.

Restrictions the repo enforces:

- **Secrets in Vault, never hardcoded** (`README.md:36`, "Conventions":
  "everything lives in Vault KV2. Nothing in this repo should contain
  a real credential"). The OIDC client secrets this ticket creates
  must reach the container through the job's Vault `template` block,
  never as a `templatefile()` literal. *(Corrected 2026-08-22: the
  previous citation, "CLAUDE.md 'Key Conventions'", does not exist —
  the repo's `CLAUDE.md` has no such section. `README.md:36` is the
  real source.)*
- **Surgical changes** (CLAUDE.md section 3). Touch only: the MinIO
  job env template and its `templatefile()` inputs, the new
  applications-layer policies file, and the specific `oidc.tf` /
  `roles.tf` / `secrets.tf` additions named in §7. Do not restyle or
  refactor adjacent jobs, the other OIDC clients, or the bucket
  module.
- **Nomad HCL is formatted** by the `nomad-fmt` pre-commit hook
  (`.pre-commit-config.yaml:16-21`). New HCL in `minio.hcl` must pass
  `nomad fmt`.
- **Terraform is formatted and validated** by `terraform-fmt`
  (`.pre-commit-config.yaml:22-27`) and `terraform-validate`
  (`:28-33`).
- **Match existing style**: mirror `minio.hcl:34-35`'s Vault
  templating idiom (`{{ with secret "..." }}{{ .Data.data.X }}{{ end }}`)
  for the per-tier client id/secret (a real secret); mirror
  `oauth2-proxy.hcl:52`'s plain `templatefile()`-variable idiom
  (`OAUTH2_PROXY_REDIRECT_URL="${redirect_url}"`) for the NON-secret
  `MINIO_BROWSER_REDIRECT_URL` and the shared discovery `config_url` —
  neither is a secret, so neither needs a Vault template lookup.

## 7. Code surface

- `deployments/infrastructure/roles.tf:153-165` — add three entries to
  `local.app_user_groups`: `app-minio-admins`, `app-minio-writers`,
  `app-minio-readers`. The file's own comment already names the
  reader entry as the worked example (`roles.tf:157`).
- `deployments/infrastructure/roles.tf:174-178` — add ONE entry to
  `local.app_user_group_members`: `"app-minio-admins" =
  [vault_identity_entity.operator.id]`, mirroring the existing
  `"app-memex-admins"` entry at the same local. **Do not add an entry
  for `app-minio-writers` or `app-minio-readers`** — an unlisted key
  lands empty, which `roles.tf:173`'s own comment calls "a valid
  resting state," and it is this ticket's correct steady state:
  `operator` is a real admin, the other two tiers start with no
  members. *(Added 2026-08-22, fourth plan review: this local is the
  ONLY thing that actually grants group membership —
  `vault_identity_group.app_user`'s `member_entity_ids` reads
  `lookup(local.app_user_group_members, each.key, [])` and is
  Terraform-authoritative, so a tier this ticket never lists here
  admits nobody regardless of how correctly everything else is
  wired. Without this line, no eval row in §8 is runnable against a
  correct implementation.)*
- `deployments/infrastructure/oidc.tf:79-86` — append the three new
  clients' `client_id`s to `local.oidc_provider_client_ids`.
- `deployments/infrastructure/oidc.tf` — new section after the L1
  block (currently ends `:187`): three `locals` (the shared console
  origin, the shared oauth callback = origin + `/oauth_callback`, and
  the shared discovery `config_url` built the way
  `secrets.tf:171`/`:192` already build the issuer string:
  `"https://${var.vault_issuer_host}/v1/identity/oidc/provider/${vault_identity_oidc_provider.lab.name}/.well-known/openid-configuration"`);
  three `vault_identity_oidc_assignment` resources, each bound to one
  tier's group id only; three `vault_identity_oidc_client` resources
  (`key = vault_identity_oidc_key.lab.name`, `redirect_uris` the
  shared callback, `client_type = "confidential"` — MinIO holds a real
  secret, mirroring `oidc.tf:156-157`'s reasoning for L1); three
  `vault_identity_oidc_key_allowed_client_id` resources registering
  each client against `lab`. **Pin the Vault-side `name` of every
  client and assignment to `minio-admin` / `minio-writer` /
  `minio-reader`** — the same literal used for the MinIO `role_policy`
  string below, and the exact literal §8's eval row 3 reads back with
  `vault read identity/oidc/client/minio-admin` (and the `writer`/
  `reader` siblings, and the matching `identity/oidc/assignment/...`
  reads). Nothing else in this plan names these resources, so without
  this line an implementer could pick any Terraform resource label and
  Vault `name` and the eval's hard-coded reads would 404 against
  otherwise-correct work.
- `deployments/infrastructure/secrets.tf` — after the
  `oauth2_proxy_oidc_client` block (`:186-201`), add three
  `vault_kv_secret_v2` resources writing each tier's `client_id` /
  `client_secret` to `default/minio/oidc/<tier>` (`admin` / `writer` /
  `reader`), same shape as `:186-201`.
- `deployments/infrastructure/services/minio.hcl:32-40` — extend the
  `template { env = true }` block with three tier provider variable
  sets PLUS one shared `MINIO_BROWSER_REDIRECT_URL`. Per tier
  (`<TIER>` uppercased: `ADMIN`/`WRITER`/`READER`):
  `MINIO_IDENTITY_OPENID_CONFIG_URL_<TIER>` (the one shared discovery
  URL, same value three times),
  `MINIO_IDENTITY_OPENID_CLIENT_ID_<TIER>` and
  `MINIO_IDENTITY_OPENID_CLIENT_SECRET_<TIER>` (Vault-templated from
  that tier's `default/minio/oidc/<tier>` KV path),
  `MINIO_IDENTITY_OPENID_ROLE_POLICY_<TIER>` (the literal MinIO policy
  name — `minio-admin`/`minio-writer`/`minio-reader` — created in the
  applications layer; no cross-state reference is possible, so both
  sides must agree on this literal by convention),
  `MINIO_IDENTITY_OPENID_DISPLAY_NAME_<TIER>` (literal `"Admin"` /
  `"Writer"` / `"Reader"`),
  `MINIO_IDENTITY_OPENID_SCOPES_<TIER>` (literal `"openid"` — MinIO
  gates on `role_policy`/the per-client assignment, not the shared
  `groups` claim; `docs/vault-human-auth.md:452-459`). NOT present:
  any per-tier `REDIRECT_URI_<TIER>` key — dropped entirely, see §6.3.
- `deployments/infrastructure/services.tf:328-333` — add templatefile
  inputs: the three tiers' KV paths
  (`vault_kv_secret_v2.minio_oidc_admin.path`, etc.), the shared
  `config_url` local, and the shared `MINIO_BROWSER_REDIRECT_URL`
  local, so `minio.hcl` can interpolate them. *(Anchor corrected
  2026-08-22 — see §4.)*
- `deployments/applications/` — add a new file (suggest
  `minio_oidc_policies.tf`) defining three `minio_iam_policy` resources
  (admin/writer/reader) whose `name` values match the `role_policy`
  strings referenced by the job. Mirror the JSON statement shape in
  `deployments/applications/modules/bucket/main.tf:11-45`. Do not add
  these to `modules/bucket/`, which is per-bucket and instantiated with
  `for_each`; the tier policies are singletons.

## 8. Tests & validation gates

### Repo gate (automated, offline)

- `just pre_commit` — runs `pre-commit run --all-files`
  (`justfile:18-19`). This gate is Terraform-aware. Relevant hooks
  (`.pre-commit-config.yaml`): `check-yaml`, `check-json`,
  `end-of-file-fixer`, `detect-private-key` (`:12`), `nomad-fmt`
  (`nomad fmt -recursive` over `*.hcl`, `:16-21`), `terraform-fmt`
  (`terraform fmt -check -recursive`, `:22-27`), and `terraform-validate`
  (`scripts/tf_validate.sh`, `:28-33`), which validates all three roots
  offline (`deployments/infrastructure`, `deployments/applications`,
  `deployments/applications/modules/bucket`) via `init -backend=false`.
  New HCL in `minio.hcl` must be `nomad fmt` clean; new/edited `.tf`
  (`oidc.tf`, `roles.tf`, `secrets.tf`, `services.tf`, the new
  `minio_oidc_policies.tf`) must be `terraform fmt` clean and
  `validate`-clean; none may embed a private-key literal (note:
  `detect-private-key` does NOT catch a Vault client secret — it
  matches PEM headers only, and `hvo_secret_...` is not one; the hook
  staying green is not proof a secret stayed out of the repo). There is
  no CI workflow; `just pre_commit` is the blessed pre-merge gate.

### Evals (live cluster, run after this ticket's Terraform is applied and the job redeployed)

The live cluster is reachable: `VAULT_ADDR`, `VAULT_TOKEN`,
`NOMAD_ADDR`, `NOMAD_TOKEN`, and `CONSUL_HTTP_ADDR` are set in the
environment, and `mc`, `vault`, `nomad`, `terraform`, and `curl` are on
PATH. The acceptance below is therefore runnable, not hypothetical.

Set up the `mc` admin alias once from the root credentials in Vault
(`default/minio/localstack`), then run the checks. Substitute the
actual tier policy / client / assignment names from §7 if they differ
from `minio-admin` / `minio-writer` / `minio-reader` below.

1. **Three OIDC role providers exist on MinIO with the right
   `role_policy`, no `redirect_uri` expected.**
   Command (per tier): `mc admin config get minio identity_openid:ADMIN`
   (repeat for `:WRITER`, `:READER` — uppercase, §6.1).
   Expected: each returns a populated block whose `role_policy` equals
   the matching tier policy name (`minio-admin` / `minio-writer` /
   `minio-reader`), with a non-empty `config_url` and `client_id`.
   **Do not assert `redirect_uri`** — that key is deprecated and
   `HiddenIfEmpty` (the `RedirectURI` field tag in
   `internal/config/identity/openid/openid.go`, pinned tag source), so
   a correct implementation shows nothing there; the shared
   `MINIO_BROWSER_REDIRECT_URL` is not readable through this command at
   all.

2. **The three tier policies exist with the expected action sets.**
   Command (per tier): `mc admin policy info minio minio-admin`
   (repeat for `minio-writer`, `minio-reader`).
   Expected: `minio-admin` grants full access (`s3:*` / `admin:*` per
   the brief); `minio-writer` grants put/get/list plus the multipart
   and delete actions from Resolved fork Q5; `minio-reader` grants
   get/list only and no `s3:PutObject`. A non-zero exit or "policy
   does not exist" fails the step.

3. **The three Vault OIDC clients (created by THIS ticket, §6.4/§7 —
   not F2) and their per-tier assignments exist.**
   Command (per tier): `vault read identity/oidc/client/minio-admin`
   and `vault read identity/oidc/assignment/minio-admin` (repeat for
   `minio-writer`, `minio-reader` — this ticket's own naming
   convention).
   Expected: each `client` read returns a `client_id`, `redirect_uris`
   equal to `["https://minio.lab.orangecluster.nl/oauth_callback"]`
   (the ONE shared callback, identical across all three — §6.3), and
   an `assignments` entry naming its own tier's assignment; each
   `assignment` read lists ONLY that tier's group id in `group_ids`
   (never another tier's) and an empty `entity_ids`. A tier whose
   assignment includes another tier's group, or whose client's
   `redirect_uris` differs from the shared callback, fails the step.

4. **Scripted cross-tier denial (the part that can be scripted), via
   `curl`, not `vault read`.**
   `vault read identity/oidc/provider/<provider>/authorize` drops the
   OIDC error body: probed live 2026-08-22 against the existing
   `oidc-smoke` client with a deliberately invalid `redirect_uri`, it
   printed a bare `Code: 400. Errors:` with an empty list. The same
   request via `curl` returned the real JSON body,
   `{"error":"invalid_redirect_uri","error_description":"redirect_uri is not allowed for the client","state":"abc123xyz"}`.
   A valid request (registered `redirect_uri`, entity in the client's
   assignment) returned `{"code":"...","state":"..."}` (also probed
   live 2026-08-22). Use `curl` for both halves of this step:
   - Reader client, an entity in `app-minio-readers` only (should
     succeed):
     `curl -s -G "$VAULT_ADDR/v1/identity/oidc/provider/lab/authorize" -H "X-Vault-Token: $READER_TOKEN" --data-urlencode client_id=<reader-client-id> --data-urlencode redirect_uri=https://minio.lab.orangecluster.nl/oauth_callback --data-urlencode response_type=code --data-urlencode scope=openid --data-urlencode state=<s> --data-urlencode nonce=<n>`
     Expected: the JSON body carries a `code` field.
   - Admin client, the SAME reader-only entity (should be refused):
     the same command with `client_id=<admin-client-id>`.
     Expected: the JSON body's `.error == "access_denied"` (the reader
     entity is not in the admin client's assignment). The
     query-param/redirect form of this exact error is already
     documented live in this repo:
     `error=access_denied&error_description=identity entity not
     authorized by client assignment` (`docs/vault-human-auth.md:331-334`).
     Parse the body's `.error` field — never the CLI's exit code or its
     empty `Errors:` list.

5. **Residual manual browser check (close-out acceptance — cannot be
   scripted).**
   In a browser against the MinIO console (port 9001,
   `minio.hcl:42-46`, reached via `https://minio.lab.orangecluster.nl/`):
   - a `minio-readers` member clicks the **Reader** login button,
     authenticates, and has read-only S3 access (list/get succeed,
     put/upload is denied);
   - the same user clicks the **Admin** login button and is refused at
     the Vault consent/authorize step;
   - a `minio-admins` member clicks the **Admin** button and has full
     access.
   Expected: three login buttons render (all through the ONE shared
   callback), reader is read-only, reader is refused on admin, admin
   has full access. **Only one human identity exists on this cluster**
   (§4, §11), so this row SPANS both of §11's sequencing windows, the
   same way step 4 does — it is not a single post-promotion check.
   *(Corrected 2026-08-22, third plan review: an earlier version of
   this section deferred the whole row to §11 undivided, and §11's own
   text then mislabeled all three sub-parts as one "admin-tier check"
   run after promotion — which would run the reader/refused sub-parts
   while `operator` is no longer reader-only, proving nothing.)*
   Run the first two sub-parts (reader clicks Reader; same session
   clicks Admin, refused) in §11 step 1's window, while `operator` is
   `app-minio-readers`-only. Run the third sub-part (admin clicks
   Admin, full access) in §11 step 2's window, after `operator` is
   promoted to `app-minio-admins`. Record the result, and the exact
   window each sub-part ran in, in the ticket's acceptance notes.

Steps 1-4 are runnable now once this ticket's Terraform is applied and
the job redeployed; step 5 is the manual residual.

**Eval marker:** the scenarios above are encoded as a five-column eval
table at `.loop/evals/M2-minio-poc-human-tiers.md` (six rows: three
deterministic `mc`/`vault`/`curl` checks, the scripted reader
read-only judgment row, the `curl`-based cross-tier-deny guardrail,
and the human-scored manual browser close-out). Rows 1, 3, and 5 of
that table were edited in this rework to match §6.1/§6.3/§6.4/§8
above — the deprecated `redirect_uri` assertion is gone, the target
casing is uppercase throughout, the Vault client/assignment names
reflect this ticket's own naming convention, and the cross-tier-deny
row scores a `curl` JSON body instead of `vault read`'s dropped one.

## 9. Risk assessment

- **Blast radius:** the MinIO job restarts when the env template
  changes (`deployments/infrastructure/services/minio.hcl`), briefly
  interrupting S3 for every dependent service (Loki, MLflow, memex,
  DuckLake).
- **Boot-time OIDC discovery risk (the real likeliest failure,
  replacing the removed ordering claim below).** MinIO fetches Vault's
  `.well-known/openid-configuration` discovery document AT CONFIG LOAD
  for the `identity_openid` subsystem
  (the `parseDiscoveryDoc` call inside function `LookupConfig`,
  `internal/config/identity/openid/openid.go`, pinned tag source, read
  directly). That lookup runs inside a background retry loop (the
  OpenID/LDAP/AuthN/AuthZ loop inside method `IAMSys.Init`, `cmd/iam.go`)
  that blocks IAM initialization until OpenID (and LDAP/AuthN/AuthZ)
  all succeed — and, sequenced immediately after it in the SAME
  goroutine, blocks the **console** itself from starting:
  `initConsoleServer()` runs only once `globalIAMSys.Init()` returns
  (the anonymous goroutine in function `serverMain`, `cmd/server-main.go`,
  that calls `globalIAMSys.Init` then `initConsoleServer` in sequence).
  An unreachable Vault issuer at MinIO boot therefore does not just
  disable OIDC login — **the console (port 9001, all three login
  buttons) never starts serving at all**, retrying every ≤3s until
  Vault answers. The S3 API (port 9000) is unaffected: it binds in its
  own, earlier, independent goroutine (a separate anonymous goroutine
  in `serverMain` that starts `httpServer`, declared before the one
  above). This is a console-only outage, but a
  total one, not a degraded one, and it recurs on every MinIO restart
  where Vault happens to be unreachable — not just at first rollout.
- **Cross-layer ordering (low-stakes; previously mis-stated as the
  main risk).** *(Corrected 2026-08-22.)* The MinIO tier policies live
  in the applications Terraform state (needs a running MinIO); the
  OIDC provider config, which carries the policy name as a plain
  string, lives in the infrastructure state. The removed claim —
  "MinIO validates `role_policy` at startup, so the policies must be
  applied first" — is false: the IAM role-map initialization inside
  method `IAMSys.Init` (`cmd/iam.go`, right after its OpenID/LDAP/
  AuthN/AuthZ retry loop) performs no such lookup — it is
  `sys.rolesMap = make(...)` followed by a `maps.Copy`, no validation,
  no error path — and a missing policy denies logins at request time
  (method `IAMSys.GetRolePolicy`, `cmd/iam.go`) rather than
  rejecting config or crash-looping the job. Applying infrastructure
  before applications — the repo's existing practice, and already
  Resolved fork Q2's conclusion — is sufficient; there is no hard
  ordering requirement left.
- **Reversibility:** high. Removing the three env sets, the
  `templatefile()` inputs, and the Vault/policy resources restores the
  prior job. No data migration.
- **Secret handling:** if an OIDC client secret is threaded as a
  `templatefile()` literal instead of via the Vault template block, it
  lands in Nomad job JSON in plaintext, violating the secrets-in-Vault
  convention (`README.md:36`). `detect-private-key` will not catch
  this — it matches PEM headers, not `hvo_secret_...`.
- **Single point of human-identity testing.** Only one Vault userpass
  identity (`operator`) exists on this cluster (§4, §11). A membership
  mistake made while testing — e.g. leaving `operator` in two tiers at
  once — can mask a real cross-tier-denial bug rather than reveal it.

## 10. Subtickets

1. **Vault OIDC scaffolding for the three tiers** (infrastructure
   layer): three `app_user_groups` entries (`roles.tf`); three
   `vault_identity_oidc_client` + `vault_identity_oidc_assignment` +
   `vault_identity_oidc_key_allowed_client_id` triples plus the shared
   `locals` (`oidc.tf`); three `vault_kv_secret_v2` writes
   (`secrets.tf`); the `local.oidc_provider_client_ids` append.
   `terraform validate` and `just pre_commit` pass. No job dependency.
   (Depends on: nothing in this ticket.)
2. **Define the three MinIO tier policies** (applications layer). Add
   `minio_oidc_policies.tf` with admin/writer/reader `minio_iam_policy`
   resources; `terraform validate` and `just pre_commit` pass. No job
   dependency. (Depends on: nothing in this ticket. Parallel with 1.)
3. **Wire the MinIO job**: three `identity_openid` provider env sets
   plus the ONE shared `MINIO_BROWSER_REDIRECT_URL`, in `minio.hcl`
   and the matching `templatefile()` inputs in `services.tf`,
   referencing subticket 1's KV paths/client ids and subticket 2's
   policy names. `nomad fmt` clean. (Depends on: 1, 2.)
4. **Acceptance** against the live cluster: run the scripted evals
   (steps 1-4) and the manual browser check (step 5), and record the
   reader-refused-by-admin result. (Depends on: 1-3.)

*(Subticket 3 above replaces the previous plan's subticket 3, "Wire
the ordering" — dropped, per §9, since MinIO performs no such
validation. This ticket's genuinely new work, the Vault scaffolding,
takes its place as subticket 1.)*

## 11. Open questions

1. **How does the single-operator-identity constraint (§4) map onto a
   three-way cross-tier-denial acceptance run?** Only one Vault
   userpass identity, `operator`, exists on this cluster. Eval step 5
   (and, to exercise step 4's "should succeed" half, step 4 too)
   describes "a `minio-readers` member" and "a `minio-admins` member"
   as if they are different people. Two ways to make that concrete:
   - **(a) Sequential membership changes on the single `operator`
     entity.** Temporarily edit `local.app_user_group_members`
     (`roles.tf:174-178`) to move `operator` into `app-minio-readers`
     instead of `app-minio-admins`, apply, run the reader-tier checks,
     then edit again to move `operator` back to `app-minio-admins` and
     re-apply for the admin-tier check. *(Corrected 2026-08-22, fourth
     plan review: this is NOT "cheap, no new Terraform" as an earlier
     draft claimed — `member_entity_ids` is Terraform-authoritative
     [`roles.tf:187-189`'s own comment: a hand-added member "shows as a
     diff on the next plan and is reverted"], so this is two real,
     temporary edits and two real applies, not a live toggle. It is
     still cheap relative to option (b) below, just not free.)* The
     "cannot cross into Admin" refusal is proven only in the window
     where `operator` is NOT also in `app-minio-admins`.
   - **(b) A throwaway test entity per tier**, mirroring how F2's
     smoke client proves the issuer works end to end without using the
     operator's own identity. More resources, but proves all three
     tiers simultaneously and reversibly.
   **Recommendation: (a) for this POC, with the memberships kept
   MUTUALLY EXCLUSIVE.** *(Corrected 2026-08-22, second plan review:
   the first version of this recommendation kept `operator` in
   `app-minio-admins` permanently while only toggling
   `app-minio-readers`, which never actually removes admin access
   during the reader-tier window — the cross-tier-deny check
   (eval rows 5 and 6) would then return a success `code`, not
   `access_denied`, against a fully correct implementation. Vault's
   assignment check gates on group membership, a property of the
   entity, not of which client was used to authorize.)* This repo's
   own design already treats `operator` as the cluster's sole human
   actor (`docs/vault-human-auth.md`: "there is one person"), and
   creating throwaway per-tier entities is disproportionate to a
   proof-of-concept ticket. This ticket's own Terraform (§7) ships the
   steady state — `operator` in `app-minio-admins`, the other two
   tiers empty — so the sequence below is a temporary, two-apply
   detour from and back to that state, run by the operator at
   close-out, not by the loop:
   1. Edit `local.app_user_group_members` to move `operator` into
      `app-minio-readers` ONLY (remove the `app-minio-admins` entry
      for this step), apply. Run the reader-tier positive check (row 4),
      the cross-tier-deny check (row 5), AND row 6's first two
      sub-parts (reader clicks Reader; same session clicks Admin,
      refused) in this window — `operator` is genuinely reader-only
      here, so a refused admin-client authorize call is a real result,
      not a vacuous one. *(Corrected 2026-08-22, third plan review:
      row 6 is not a single post-promotion check — see §8 step 5. Two
      of its three sub-parts belong HERE, not in step 2.)*
   2. Revert `local.app_user_group_members` to this ticket's shipped
      state — `operator` back in `app-minio-admins`, no entry for
      `app-minio-readers` — and apply again. Run ONLY row 6's third
      sub-part here (admin clicks Admin, full access). This restores
      exactly the steady state §7 ships, not a new or different one.
   Document the exact sequence, the group membership at each step, and
   the two applies in the acceptance notes, since the two checks are
   not simultaneous and a reader re-running them later needs to see
   why. Confirm before
   running §8.

## Resolved forks (operator, 2026-07-23)

- **Q1 → SUPERSEDED 2026-08-22.** See the rework block below. The
  original resolution (F2 writes a KV path, flagged as an "F2
  interface requirement") never happened; this ticket now creates the
  KV writes itself.
- **Q2 → Rely on the existing infra→applications apply order
  (documented). Still current, and now doubly confirmed.** The three
  tier policies (`admin`/`writer`/`reader`) are MinIO IAM policies
  created by the MinIO provider in the applications layer; the MinIO
  server job is in the infrastructure layer. MinIO IAM policies can
  only be created against a running MinIO, and the repo already
  applies infrastructure before applications — so server-up-then-policies
  is the natural, existing order. *(2026-08-22: this is now confirmed
  by source, not just repo-practice inference — the IAM role-map
  initialization inside method `IAMSys.Init` (`cmd/iam.go`) performs no
  `role_policy` lookup at all, so there was never a
  crash-loop risk to order around; see §9.)* No cross-state
  `depends_on`, no moving policies, no duplicating the MinIO provider
  for the POC. Document the order in the runbook.
- **Q3 → SUPERSEDED 2026-08-22.** See the rework block below. The
  config/discovery URL is no longer "an F2-provided input" to confirm
  — this ticket builds it directly.
- **Q4 → SUPERSEDED 2026-08-22.** See the rework block below. There is
  no per-tier redirect URI host to choose between; MinIO's replacement
  key is server-global.
- **Q5 → writer = put/get/list + multipart + delete. Still current,
  unaffected by this rework.** Full write including
  `s3:DeleteObject`. (reader = get/list; admin = full.)

## Resolved forks (rework, 2026-08-22)

- **Redirect URI → ONE shared `https://minio.lab.orangecluster.nl/oauth_callback`
  for all three tiers**, fed by a single
  `MINIO_BROWSER_REDIRECT_URL=https://minio.lab.orangecluster.nl` (no
  per-tier `redirect_uri`, which is deprecated on this release). See
  §6.3. Supersedes Q4.
- **Ordering → no hard constraint.** MinIO does not validate
  `role_policy` at boot (method `IAMSys.Init`, `cmd/iam.go`); applying
  infra before applications (existing practice, Q2) is sufficient.
  See §9.
- **Vault-side OIDC scaffolding → this ticket's own**, not F2's. Three
  `vault_identity_oidc_client`/`assignment`/`key_allowed_client_id`
  triples in `oidc.tf`, three `app_user_groups` entries in `roles.tf`,
  three KV2 writes in `secrets.tf` under `default/minio/oidc/<tier>`.
  Mirrors L1's oauth2-proxy pattern, branch 2 of
  `docs/vault-human-auth.md`'s "who is allowed in" checklist. See
  §6.4, §7. Supersedes Q1.
- **Config/discovery URL → built directly by this ticket**, not an
  external F2 input:
  `"https://${var.vault_issuer_host}/v1/identity/oidc/provider/${vault_identity_oidc_provider.lab.name}/.well-known/openid-configuration"`,
  mirroring `secrets.tf:171`'s existing issuer-string construction.
  Supersedes Q3.
- **Target-name casing → uppercase** (`ADMIN`/`WRITER`/`READER`).
  Every eval command and every reference in this plan uses this
  casing; MinIO does no case folding on it (function `getEnvVarName`,
  `internal/config/config.go`).

**Dependencies:** M2 depends on **F2** (`done` — shared OIDC
provider/key/scope only; this ticket creates its own per-tier clients,
see §5/§6.4) and **A1** (`done` — the premise sweep that produced this
rework).

*(Corrected 2026-07-30 by A1's plan review. This previously added: "and on
**F4** (network-wide `.localstack` DNS) — M2 must not be marked done until F4
lands, so the MinIO console resolves from non-Mac LAN devices, not just via
the operator's `/etc/hosts`." False in all three clauses. F4 is dropped in the
ledger; T3's commit records that no `.localstack` name is served at all any
more; and public DNS already answers, verified by `dig +short
minio.lab.orangecluster.nl @1.1.1.1` returning 192.168.2.30 with zero
`orangecluster` entries in `/etc/hosts`. The block was prose only and never
appeared in front-matter, so `loopctl graph` could not see it and it survived
F4's drop. The front-matter `depends_on` is unchanged and correct.
Re-confirmed clean 2026-08-22: no further trace of F4/`.localstack` remains in
this section.)*

## Premises / assumptions

- **P1.** `minio.hcl:32-40` remains the sole env injection point for
  the MinIO container, currently holding exactly the three pre-OIDC
  vars. `Evidence:` direct read, 2026-08-22, of
  `deployments/infrastructure/services/minio.hcl:32-40`.

- **P2.** The console and the `identity_openid` subsystem still serve
  on the pinned release, `RELEASE.2025-09-07T16-13-09Z`
  (`minio.hcl:66`). `probe:` `curl -s -o /dev/null -w '%{http_code}'
  https://minio.lab.orangecluster.nl/` → `200`, 2026-08-22.

- **P3.** MinIO's per-provider `redirect_uri` env key is deprecated on
  this release, and its replacement (`MINIO_BROWSER_REDIRECT_URL`) is
  read once, globally, not per target. `Evidence:` the `RedirectURI`
  `HelpKV` entry in `internal/config/identity/openid/help.go` and
  function `serverHandleEnvVars` in `cmd/common-main.go`, fetched and
  read directly from the pinned tag's raw source, 2026-08-22 (upstream
  citations name symbols, not line numbers — see the note after P13).

- **P4.** MinIO does no case-folding on the `identity_openid` target
  suffix, so the provider name used in `mc admin config get` must
  match the env var suffix's casing exactly. `Evidence:` function
  `getEnvVarName` and the target-discovery code immediately above it
  in `internal/config/config.go`, pinned tag source, read directly
  2026-08-22.

- **P5.** MinIO does not validate `role_policy` names at IAM
  initialization; an unresolved policy denies logins at request time
  rather than rejecting config or crash-looping. `Evidence:` the
  comment beside the role-ARN construction inside function
  `LookupConfig` ("RolePolicy is validated by IAM System during its
  initialization" — no check follows it), and the IAM role-map
  initialization inside method `IAMSys.Init` (`sys.rolesMap`
  populated via `maps.Copy`, no lookup, no error path), both in
  `internal/config/identity/openid/openid.go` and `cmd/iam.go`
  respectively, pinned tag source, read directly 2026-08-22.

- **P6.** All three tiers' OIDC callback resolves to the SAME URL:
  `getConsoleEndpoints()[0] + "/oauth_callback"`, where
  `getConsoleEndpoints()[0]` is `globalBrowserRedirectURL` (the
  `MINIO_BROWSER_REDIRECT_URL` value) whenever it is set. `Evidence:`
  functions `buildOpenIDConsoleConfig` (`cmd/common-main.go`) and
  `getConsoleEndpoints` (`cmd/net.go`), pinned tag source, read
  directly 2026-08-22. This is the mechanism behind requirement 3;
  the 2026-07-30 review established that a shared callback was
  necessary but not this exact construction.

- **P7.** HAProxy routes `minio.lab.orangecluster.nl` to the console
  port (9001), and forwards no `X-Forwarded-Proto`/`forwardfor`
  header. `Evidence:`
  `deployments/infrastructure/services/haproxy.hcl:98,109,127-128`,
  read directly 2026-08-22. `probe:` a grep for
  `X-Forwarded|forwardfor` over that file returns 0 matches; `curl -s
  -o /dev/null -w '%{http_code}' https://minio.lab.orangecluster.nl/`
  → `200`.

- **P8.** Vault's `lab` OIDC provider is live and HTTPS, and F2 is
  `done`. `Evidence:` `.loop/ledger.json` entry
  `F2-foundation-vault-oidc-provider` has `stage: done`. `probe:`
  `curl https://vault.lab.orangecluster.nl/v1/identity/oidc/provider/lab/.well-known/openid-configuration`
  → `200` with a full discovery document, 2026-08-22.

- **P9.** F2 created no MinIO-specific Vault OIDC clients; this ticket
  must create its own. `Evidence:` `deployments/infrastructure/oidc.tf:1-10`
  states explicitly that consumer clients "including the MinIO
  tiers/M2" are not created by F2. `probe:` `vault list
  identity/oidc/client` (2026-08-22) returns `memex`, `nomad`,
  `oauth2-proxy`, `oidc-smoke` — no `minio-*` entry.

- **P10.** Vault's OIDC `/authorize` endpoint returns a real JSON
  error body via a direct HTTP call, but the `vault read` CLI drops
  that body. `probe:` 2026-08-22, against the existing `oidc-smoke`
  client with a deliberately invalid `redirect_uri`: `vault read` →
  `Code: 400. Errors:` (empty); `curl` with the same params and a
  valid Vault token → `{"error":"invalid_redirect_uri", ...}`. A valid
  request (registered redirect, entity in the client's assignment) →
  `{"code":"...","state":"..."}`, also probed live. The specific
  `access_denied` shape for an assignment mismatch was not
  reproduced live in this pass (no `minio-*` client exists yet to test
  against, and the only available identity, `operator`, is a member of
  every tested client's assignment); it is inferred from this same
  curl-vs-CLI mechanism plus the query-param form of the identical
  error already observed live and documented at
  `docs/vault-human-auth.md:331-334`. Flag this inference in the
  acceptance run (§8 step 4) rather than treat it as independently
  confirmed.

- **P11.** Only one human identity exists on this cluster. `probe:`
  `vault list auth/userpass/users` (2026-08-22) returns exactly one
  user, `operator`. `Evidence:` `docs/vault-human-auth.md` states "there
  is one person" for the `developer`/`admin` role design.

- **P12.** MinIO's OIDC discovery fetch runs inside a background
  goroutine that also gates the console's own startup, separately from
  the S3 API. `Evidence:` in `cmd/server-main.go`, the S3 API
  `httpServer` starts in its own, earlier, independent anonymous
  goroutine, while a SEPARATE, later anonymous goroutine runs
  `globalIAMSys.Init(...)` then `initConsoleServer()` sequentially; in
  `cmd/iam.go`, method `IAMSys.Init`'s retry loop blocks on
  `openidInit` with a ≤3s backoff; in
  `internal/config/identity/openid/openid.go`, function
  `LookupConfig` calls `parseDiscoveryDoc`, the actual failure point.
  All read directly from the pinned tag's raw source, 2026-08-22
  (symbols, not line numbers — see the note below).

- **P13.** `services.tf` and `providers.tf` anchors drift as other
  tickets land. `Evidence:` direct read, 2026-08-22 — `nomad_job
  "minio"` now at `services.tf:328-333` (was `:306-311` at the
  2026-07-30 review, `:301-306` in the original plan, due to the
  HAProxy and Redis jobs landing in between); `nomad_job "grafana"`
  now at `services.tf:368-390` (was `:346-...`); the `minio` provider
  is unchanged at `providers.tf:44-48` since the 2026-07-30 review.

- **P16.** The manual browser close-out (§8 step 5, eval row 6) has
  three sub-parts, and they do not all belong to the same §11
  sequencing window: two (reader clicks Reader; same session clicks
  Admin, refused) require `operator` to still be `app-minio-readers`-
  only, and one (admin clicks Admin, full access) requires `operator`
  already promoted to `app-minio-admins`. `Evidence:` Vault's
  `/authorize` assignment check (`pathOIDCAuthorize` /
  `entityHasAssignment`, confirmed live against the cluster's own
  `v2.0.3` source) calls `groupsByEntityID` fresh on every request —
  there is no cached or login-time-snapshotted membership — so a
  sub-part run in the wrong window observes the wrong group state
  and proves nothing. §8 step 5 and §11 step 2 now split the row's
  sub-parts across both windows explicitly, matching how §8 step 4
  and §11 step 1 already did for rows 4 and 5.

- **P17.** Tier group membership is granted ONLY through
  `local.app_user_group_members` (`roles.tf:174-178`), a separate
  local from `local.app_user_groups` (`roles.tf:153-165`, where §7's
  original text stopped). Without an entry there, a tier group exists
  but admits nobody. `Evidence:` `vault_identity_group.app_user`'s
  `member_entity_ids = lookup(local.app_user_group_members, each.key,
  [])` (`roles.tf:187-189`), whose own comment states membership is
  Terraform-authoritative — "a member added by hand shows as a diff on
  the next plan and is reverted" — and `roles.tf:173`'s comment that an
  unlisted key "lands empty, which is a valid resting state." §7 now
  commits `operator` to `app-minio-admins` there (mirroring the
  existing `app-memex-admins` entry) as this ticket's shipped steady
  state, and §11's acceptance sequence is corrected to describe the
  reader-tier detour as two real, temporary Terraform edits and
  applies, not a live toggle.

**Note on upstream citations.** Every premise above that cites MinIO's
own Go source (the ones naming `cmd/` or `internal/config/` files)
names a file and a function or struct symbol, never a line number,
mirroring `L1-landing-oauth2-proxy`'s convention (its requirement 16):
line numbers in a third-party repo drift against this repo's own
commits and reveal nothing this repo's reviewers can check without
also fetching that source. Every one of those symbols was fetched and
read directly from `raw.githubusercontent.com` at the pinned tag
`RELEASE.2025-09-07T16-13-09Z` on 2026-08-22, not inferred from
release notes or memory.

## Plan review history

### 2026-07-30 (A1 premise sweep) — PARTIALLY SOUND, `fail`

Reviewed by `loop-plan-reviewer` against the repo and the live cluster,
as part of `A1-audit-plan-premise-sweep`. Full verdict:
`.loop/verdicts/M2-minio-poc-human-tiers.plan-validator.md`. Headline
defect: the per-target `redirect_uri` is deprecated and its
replacement is server-global, so three tiers cannot register three
callbacks; the plan's stated ordering-constraint cost driver was also
false; two eval rows could not pass a correct implementation; and the
plan's Vault-side ownership assumption (F2 provides the clients) did
not match F2's actual, shipped scope.

### 2026-08-22 — rework addressing all eight required fixes

Every item in the 2026-07-30 verdict's required-fix list is addressed
in this revision: the deprecated per-tier redirect URI is dropped for
one shared `MINIO_BROWSER_REDIRECT_URL` (§6.3); the false
startup-validation ordering claim is removed from Size/Effort and Risk
(§2, §9); this ticket now creates its own Vault OIDC
clients/assignments/groups/KV writes rather than assuming F2 provides
them (§5, §6.4, §7); eval row 1 no longer asserts `redirect_uri` and
every target reference is uppercase (§8, `.loop/evals/M2-minio-poc-human-tiers.md`);
eval row 5 scores a `curl` JSON body instead of `vault read`'s dropped
one (§8, same eval file); the stale F4 dependency prose was already
clean and is reconfirmed so; all three drifted `path:line` anchors are
re-pointed at today's file state (§4, P13); and the boot-time OIDC
discovery risk is documented in §9 with its exact source-verified
mechanism. This revision also fixes a false citation found during the
rework (`README.md:36`, not a nonexistent "CLAUDE.md 'Key
Conventions'") and adds one new, previously unraised open question
(§11) about testing three-tier RBAC against a cluster with only one
human identity.

**This ticket remains `blocked` pending a fresh `loop-plan-reviewer`
pass.** Do not implement from this plan until that pass returns a
`plan:` line.
