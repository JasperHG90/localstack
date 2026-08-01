---
verdict: fail
---

# G2-nomad-ui-oidc-login — plan premise review (pass `plan-validator`)

## Why this is recorded as `fail` rather than `pass-with-required-fixes`

Read this first, because the header understates the review.

**The premise review landed at PARTIALLY SOUND, and on premise severity alone
the gate verdict would be `pass-with-required-fixes`.** The core mechanism is
verified working end to end against the live cluster and the pinned provider.
Two things force the `fail` header instead:

1. **My briefing supplied no plan fingerprint.** The dispatcher gave the repo
   root, the plan path, the slug, the pass id and the verdict path, but no
   64-hex sha256 to bind. My contract is explicit: report the gap, never
   invent one, never write a fingerprint I was not given. A verdict with no
   authorizing `plan:` line cannot flip `PLANNING -> READY`, which is the
   correct and safe outcome.
   For the operator's convenience only, and **not** as an authorizing binding:
   `sha256(.loop/plans/G2-nomad-ui-oidc-login.md)` at review time was
   `9c74ccddcf2b70e45c5175a94bbd637eb43e63c55e11232e744ea770ac052e59`.
2. **The required fixes below change the plan and the eval marker anyway**, so
   any fingerprint bound now would be stale on arrival. Apply RF1–RF5, then
   re-run this pass with the fingerprint supplied.

Nothing here is a "the approach is wrong" fail. The approach is sound.

---

## Premise verdict

**PARTIALLY SOUND.**

The load-bearing capability claims that this repo's history says to distrust —
Nomad OIDC in Community Edition, the pinned provider's schema, the redirect
URI paths, Consul OIDC being Enterprise-only, the unmanaged `developer` policy,
and the achievability of Q1's import — **all hold, verified against the live
cluster, the provider binary and first-party docs.** One third-party capability
claim is false (PKCE), and three scoring/scope defects would let a broken
ticket report green.

## Per assumption

### P1 — Nomad supports the OIDC auth method in Community Edition; the cluster runs 2.0.4 — **HOLDS**

Four independent lines of evidence, all confirming CE and confirming OIDC is
not license-gated:

- `nomad license get` on this cluster returns `Error getting license: Nomad
  Enterprise only endpoint`. The binary is CE.
- `nomad server members` reports leader `firebat.global`, `Build 2.0.4`;
  `/v1/agent/self` reports `"Version": "2.0.4"`. Plan §Context is exact.
- The CE binary's `nomad acl auth-method create -help` prints, verbatim:
  `Sets the type of the auth method. Supported types are 'OIDC' and 'JWT'.`
  Plan §Context quotes this correctly.
- `developer.hashicorp.com/nomad/docs/secure/authentication/oidc` carries no
  Enterprise badge and no Enterprise prose in its body, and its nav entry reads
  plain "Configure OIDC". Contrast the Consul equivalent below, which the same
  doc system tags `OIDC (ENT)`.

### P2 — pinned `hashicorp/nomad` 2.5.2 carries the named resources and fields — **HOLDS**

Verified against the actual provider binary, not the registry docs. I built a
throwaway root, `terraform init -plugin-dir=` against the repo's own provider
cache, and dumped `terraform providers schema -json`. Lockfile in that root
resolves `registry.terraform.io/hashicorp/nomad version = "2.5.2"`, matching
`deployments/infrastructure/.terraform.lock.hcl`.

- Resources present: `nomad_acl_auth_method`, `nomad_acl_binding_rule`,
  `nomad_acl_role`, plus `nomad_acl_policy` (needed for Q1).
- `nomad_acl_auth_method` `config` block attributes present: `oidc_discovery_url`,
  `oidc_client_id`, `oidc_client_secret`, `oidc_scopes`, `oidc_enable_pkce`,
  `bound_audiences`, `bound_issuer`, `allowed_redirect_uris`, `claim_mappings`,
  `list_claim_mappings`. Top-level: `token_locality`, `max_token_ttl`,
  `token_name_format`, `type`, `default`.
- `nomad_acl_binding_rule` carries `auth_method`, `bind_name`, `bind_type`,
  `selector`, `description`.
- Provenance: `terraform-provider-nomad` CHANGELOG 2.5.0 (April 16, 2025) adds
  `oidc_enable_pkce` (PR #523). The `~>2.5.0` pin at `providers.tf:3-6` is the
  first line that carries it. "No provider bump" is correct.

Two accuracy nits, neither a break:

- The plan lists the OIDC fields as if they sit on the resource. They are
  inside the nested `config` block. Cosmetic for a reader, but the implementer
  should know.
- `bound_issuer` is typed `["list","string"]`, not a string. R4 says "Set
  `bound_issuer` to the `lab` issuer"; it takes a one-element list.

Bonus check, since it would have been a nasty surprise: Nomad redacts the OIDC
client secret from API responses (CVE-2025-1296, changelog line 935), which
would normally give Terraform a perpetual diff. Provider 2.5.2 handles it —
`resource_acl_auth_method.go:438-471` defines `unredactACLAuthMethodResource`,
"mutates fetchedAuthMethod with real secrets ... redacted in Nomad API
responses". No drift. (Note 2.6.0 adds `oidc_client_secret_wo`; at 2.5.2 the
secret does land in Terraform state, consistent with the repo's existing
`random_password` resources.)

### P3 — "PKCE is required from Nomad 1.10 onward, per HashiCorp's Vault-to-Nomad guide" (R2) — **BREAKS**

This is the false third-party capability claim. Three sources contradict it:

- The guide the plan names,
  `developer.hashicorp.com/nomad/docs/secure/authentication/sso-vault`,
  **never mentions PKCE**. The string "pkce" occurs exactly once in the whole
  rendered page, in the left sidebar nav link to a different document. Its
  worked auth-method config is
  `{"OIDCDiscoveryURL":…,"OIDCClientID":…,"OIDCClientSecret":…,"BoundAudiences":…,"OIDCScopes":["groups"],"AllowedRedirectURIs":[…],"ListClaimMappings":{"groups":"roles"}}`
  — no `OIDCEnablePKCE` at all.
- The document that does cover it,
  `…/secure/authentication/sso-pkce-jwt`, states: "Beginning with Nomad
  v1.10.0, Nomad **supports** PKCE. To take advantage of the additional
  security of PKCE, you must enable it in Keycloak." Supports, not requires.
- Nomad CHANGELOG 1.10.0 (April 09, 2025), FEATURES: "**OIDC Login:** Nomad now
  **enables** PKCE for OIDC logins…" A feature, not a requirement.
- Schema confirms: `oidc_enable_pkce` is `optional`, default off.

**The action R2 prescribes is still right, and safe.** I checked the one thing
that could have made it actively harmful: the live `lab` provider's discovery
document at
`https://vault.lab.orangecluster.nl/v1/identity/oidc/provider/lab/.well-known/openid-configuration`
advertises `"code_challenge_methods_supported": ["plain","S256"]`. Vault
supports PKCE, so enabling it works and eval row 7 is achievable. Only the
stated justification is fabricated. Fix the rationale, keep the setting.

### P4 — redirect URIs `/ui/settings/tokens` and `http://localhost:4649/oidc/callback` — **HOLDS**

Verbatim from the Nomad OIDC docs: "Logging in via the UI requires the redirect
URI `http://{host:port}/ui/settings/tokens`. Logging in via the CLI requires
the redirect URI `http://{host:port}/oidc/callback`." And: "If the
`-oidc-callback-addr` flag is not specified, it will default to
`localhost:4649`." Corroborated by the local CLI: `nomad login -help` documents
`-oidc-callback-addr … defaults to "localhost:4649"`. The sso-vault guide's own
example lists both:
`["http://localhost:4649/oidc/callback","http://localhost:4646/ui/settings/tokens"]`.

The UI host is right too: `https://nomad.lab.orangecluster.nl/` returns 307 to
`https://nomad.lab.orangecluster.nl/ui/`, and the docs warn "URIs need to match
exactly. Check http/https, 127.0.0.1/localhost, port numbers, and whether
trailing slashes are present" — which is exactly why R3 and Q4 exist. Good
plan.

One prerequisite the plan never states, verified favorably: the `lab`
provider's `authorization_endpoint` is a **Vault UI** path
(`https://vault.lab.orangecluster.nl/ui/vault/identity/oidc/provider/lab/authorize`),
which F2's own marker flagged. So the browser flow requires the developer's
browser to reach the Vault UI through the edge and log in there. It does:
`https://vault.lab.orangecluster.nl/ui/` returns 200, and `vault auth list`
shows `userpass/`. Not a break, but see RF5.

### P5 — Consul's OIDC auth method is Enterprise-only — conclusion **HOLDS**, cited evidence **BREAKS**

The conclusion is right, and better sourced than the plan claims.
`developer.hashicorp.com/consul/docs/secure/acl/auth-method/oidc` says:
"**Enterprise** — This feature requires version 1.8.0+ of self-managed Consul
Enterprise", and "Browser interaction is required. This is only available in
Consul Enterprise." Its nav tags the page `OIDC (ENT)`. The non-goal stands.

But the plan's stated verification does not resolve. It claims
"`/v1/agent/self` reports `Edition: n/a`". On this cluster `/v1/agent/self`
has **no `Edition` field at all** — `.Config` returns `{"Version":"2.0.2",
"VersionMetadata":null}` — and `consul version` prints only
`Consul v2.0.1 / Revision / Build Date / Protocol`, with no Edition line.
`grep -i edition` across both outputs is empty. CE is still established (no
`+ent` suffix, `VersionMetadata: null`), but the citation as written is not
reproducible. In a repo with this history, a fabricated-looking verification
string next to a correct conclusion is worth correcting.

### P6 — a live unmanaged `developer` policy granting alloc-exec and alloc-node-exec — **HOLDS, exactly**

- `nomad acl policy list` returns `deploy` and `developer` only.
- `nomad acl policy info developer` returns rules matching the plan's §Context
  block grant for grant: namespace "default" policy=write with `submit-job,
  read-job, list-jobs, dispatch-job, read-logs, read-fs, alloc-exec,
  alloc-lifecycle, alloc-node-exec`; `host_volume "*"` write; `node`, `agent`,
  `operator` read.
- `grep -rn 'developer' deployments --include=*.tf` returns nothing. Unowned,
  confirmed.
- `nomad acl auth-method list` → "No ACL auth methods found";
  `nomad acl role list` → "No ACL roles found". The §Context ACL-state block is
  accurate, so eval row 1's attribution argument holds.
- The `deploy` contrast is accurate: `nomad_deploy_role.tf:13-30` grants only
  `submit-job`, `read-job` and the five `host-volume-*` capabilities, with no
  `list-jobs`, no `read-logs`, no `alloc-exec` and no node/agent/operator
  block. That also substantiates the D3 aside without needing to mint a token:
  `nomad job status` needs `list-jobs`, which `deploy` does not have.

### P7 — Q1's "import the policy" is achievable with the pinned provider — **HOLDS** (probed)

I ran a real import probe in a throwaway root against the live cluster with
`-lock=false` (plan only, no mutation):

```
resource "nomad_acl_policy" "developer" { name = "developer" … }
import { to = nomad_acl_policy.developer, id = "developer" }
```

`terraform plan` returned `Plan: 1 to import, 0 to add, 1 to change, 0 to
destroy`, and rendered the live rules in the diff — the import reads the
policy body, so Q1's "verify the import leaves the live rules byte-identical"
is mechanically checkable by matching `rules_hcl`. Import is supported.
Eval row 10 can also fail today (grep returns nothing right now), so it is a
real check.

The binding half works too: `nomad acl binding-rule create -help` gives
`-bind-type … Valid options are "role", "policy", or "management"`, so binding
straight to the imported policy is legal. And the claim mapping works:
the OIDC docs' attribute table gives `list.groups` the operations
`In, Not In, Is Empty, Is Not Empty` (not interpolatable), which is exactly
what a `"nomad-developers" in list.groups` selector with a static `bind_name`
needs.

### P8 — Vault's `lab` provider is live at the HTTPS issuer with a `groups` scope — **HOLDS**

Live discovery document returns
`"issuer": "https://vault.lab.orangecluster.nl/v1/identity/oidc/provider/lab"`,
`"scopes_supported": ["groups","openid"]`, `"response_types_supported":["code"]`,
`"grant_types_supported":["authorization_code"]`, and a working `jwks_uri`.
F2 is applied. `oidc.tf:63-67` is the `locals { oidc_provider_client_ids = [...] }`
block the plan says it is, and `oidc.tf:118-121` is the standalone
`vault_identity_oidc_key_allowed_client_id "smoke"` the plan says to copy.
R5's "no inline `allowed_client_ids` on the key" is true of the live file
(`oidc.tf:26-31`), so eval row 8's third assertion is meaningful.

### P9 — Vault's built-in `default` provider is the trap R4 describes — **HOLDS, exactly**

`vault read identity/oidc/provider/default` returns
`allowed_client_ids: ["*"]` and
`issuer: http://192.168.2.30:8200/v1/identity/oidc/provider/default`.
Plaintext, raw IP, wildcard. R4 and eval row 6 are well founded.

### P10 — repo anchors — **HOLDS**

- `haproxy.hcl:101` is `acl is_nomad hdr(host) -i nomad.lab.orangecluster.nl`;
  `:112` is `use_backend nomad if is_nomad`; `:136-137` is
  `backend nomad / server nomad1 192.168.2.30:4646 check`. All three resolve.
- `providers.tf:3-6` is the `nomad = { source = "hashicorp/nomad", version =
  "~>2.5.0" }` block.
- `nomad_deploy_role.tf:13-30` is `resource "nomad_acl_policy" "deploy"`.
- `secrets.tf` carries the `vault_kv_secret_v2` + `custom_metadata` pattern the
  plan says to match (e.g. `secrets.tf:15-29`).
- `docs/vault-human-auth.md:71` is `## Adding a service that logs people in
  through Vault`.
- The F2 close-out claims the plan leans on are real:
  `.loop/evals/F2-foundation-vault-oidc-provider.md:37` records the
  `scope=openid groups` trap ("`openid` alone returns a token with NO groups
  claim however correct the template"), and `:25`/`:39` record the
  `detect-private-key` false green.

### P11 — the gates are this repo's real gates — **HOLDS**

`justfile:18-19` `pre_commit: pre-commit run --all-files`.
`.pre-commit-config.yaml:22-33` defines `terraform-fmt`
(`terraform fmt -check -recursive`) and `terraform-validate`
(`scripts/tf_validate.sh`, per root). `justfile:30-32` defines
`worktree_setup path`, which eval row 12 invokes. Discovered, not assumed.

### P12 — R6's replacement secret guardrail "can fail" — **BREAKS**  ← most dangerous

R6 and eval row 9 correctly reject `detect-private-key` (it is at
`.pre-commit-config.yaml:12` and matches a fixed PEM blocklist). But the
replacement pattern, copied from F2's marker verbatim, **cannot fail either**.

The scored command is
`grep -nE 'client_secret[[:space:]]*=[[:space:]]*"\|hvo_secret_'`.
In ERE, `\|` is an escaped literal pipe, not alternation, so the pattern
searches for the single literal string `client_secret = "|hvo_secret_`, which
will never appear. Tested on this host against a file containing a real leak
shape:

```
$ printf 'oidc_client_secret = "hvo_abc"\nfoo hvo_secret_x\n' > g.txt
$ /usr/bin/grep -nE 'client_secret[[:space:]]*=[[:space:]]*"\|hvo_secret_' g.txt ; echo $?
1                       # no match — GNU grep 3.11
$ grep -nE 'client_secret[[:space:]]*=[[:space:]]*"\|hvo_secret_' g.txt ; echo $?
1                       # no match — ugrep 7.5.0, what `grep` resolves to here
$ grep -nE 'client_secret[[:space:]]*=[[:space:]]*"|hvo_secret_' g.txt
1:oidc_client_secret = "hvo_abc"
2:foo hvo_secret_x        # unescaped pipe matches both
```

So the row whose entire stated purpose is "scored by something that can fail"
returns green against a literal client secret committed to a `.tf` file. This
is the same false-green class the marker's own prose claims to have fixed, one
layer down. It is the most dangerous finding here: being wrong about it means
a real credential ships with a green board.

### P13 — eval row 11's workload-path guardrail observes what it claims — **BREAKS**

Row 11's input is "`nomad acl auth-method list` for the workload path" and its
expectation is "The `jwt-nomad` Vault mount that workloads use is untouched."
`nomad acl auth-method list` lists **Nomad** auth methods and can never show a
Vault mount. `jwt-nomad` is a Vault auth mount: `vault auth list` returns
`jwt-nomad/  jwt`, alongside `token/` and `userpass/`. Worse, after this ticket
that command returns exactly the new OIDC method, which a scorer could read as
a green signal about something it never looked at. The plan's own non-goal
states the distinction correctly ("one is a Nomad auth method trusting Vault,
the other is a Vault auth method trusting Nomad"); the marker then scores it
with the wrong tool.

The other half of row 11 is fine: `vault_nomad_secret_role.deploy` exists at
`nomad_deploy_role.tf:36-41` and `vault secrets list` shows the `nomad/` mount.

### P14 — §Code surface covers the resolved Q1 — **BREAKS**

Q1 resolved to **import** the `developer` policy (§Forks resolved), and
subticket 4 says "Resolve `developer` per Q1". But §Code surface lists no
`nomad_acl_policy "developer"` resource and no `import` block, and names no
file for either. §7 is the scope contract the create-ticket skill checks
"every changed line traces to the ticket" against, and needing a file not
listed there is the `out-of-scope-fix-needed` blocker. As written, the
implementer must guess whether the import lands in the new `nomad_oidc.tf`,
in `nomad_deploy_role.tf`, or in a new file — mid-loop, on the one resource
that grants `alloc-node-exec`.

### P15 — R1's scope handling — **HOLDS**, with one ambiguity

The trap is real and correctly stated (F2 eval row at
`.loop/evals/F2-foundation-vault-oidc-provider.md:37`). Minor ambiguity: R1
says "Set `oidc_scopes` to include `groups`. Vault requires `openid`", which
leaves open whether to write `["groups"]` or `["openid","groups"]`. The
sso-vault guide uses `"OIDCScopes": ["groups"]` (Nomad's OIDC library adds
`openid` itself). Not a break; worth one clarifying clause.

## Most dangerous assumption

**P12 — that R6 and eval row 9 give this ticket a secret-leak guardrail that
can actually fail.** Every other finding costs rework; this one lets a real
Vault client secret land in a committed `.tf` file with the whole board green,
which is the exact defect F2's marker exists to prevent. P3 is the headline
false capability claim and must be fixed, but the plan still ships correctly
with it, because PKCE genuinely works against this Vault provider.

## Required fixes

**RF1 (P3).** Rewrite R2's justification and the eval row 7 rationale. PKCE is
*supported* from Nomad 1.10.0, not required, and the Vault-to-Nomad guide never
mentions it. Keep `oidc_enable_pkce = true`; justify it as defense in depth,
citing `…/secure/authentication/sso-pkce-jwt` ("Beginning with Nomad v1.10.0,
Nomad supports PKCE") and the live discovery document's
`code_challenge_methods_supported: ["plain","S256"]`, which is what makes it
work here.

**RF2 (P12).** Fix the guardrail pattern in eval row 9 so it can fail: drop the
backslash, `grep -nE 'client_secret[[:space:]]*=[[:space:]]*"|hvo_secret_'`.
Verify it by running it against a line containing
`oidc_client_secret = "hvo_abc"` and confirming a match before trusting it.
F2's marker carries the same broken pattern and should be corrected too.

**RF3 (P13).** Fix eval row 11's workload-path input. `nomad acl auth-method
list` cannot observe the `jwt-nomad` Vault mount. Use `vault auth list` (or
`vault read sys/auth/jwt-nomad`) and assert the mount and its config are
unchanged.

**RF4 (P14).** Add the Q1 import to §Code surface: name the `nomad_acl_policy
"developer"` resource, name the `import` block, and name the file each lands
in. State that `rules_hcl` must reproduce the live policy byte for byte, and
that the check is a clean `terraform plan` after import (my probe shows the
diff renders the live rules, so this is verifiable).

**RF5 (P5, P2, P4 — small, group them).**
 (a) Replace the Consul non-goal's unreproducible citation: `/v1/agent/self`
     has no `Edition` field on this cluster and `consul version` prints no
     Edition line. Cite instead the Consul OIDC doc's own banner ("This feature
     requires version 1.8.0+ of self-managed Consul Enterprise") plus
     `VersionMetadata: null` / no `+ent` suffix.
 (b) Note in §Code surface that the OIDC fields sit inside the auth method's
     nested `config` block, and that `bound_issuer` takes a list of strings.
 (c) Add one line to §Context or §Risk: the browser flow redirects to Vault's
     **UI** authorize path
     (`https://vault.lab.orangecluster.nl/ui/vault/identity/oidc/provider/lab/authorize`),
     so the developer's browser must reach the Vault UI through the edge and
     log in there (userpass). Verified reachable (HTTP 200), but the DoD hangs
     on it and F2's marker already flagged the UI-path surprise.
 (d) Optional, one clause on R1: write `oidc_scopes = ["groups"]`, matching
     HashiCorp's guide; the OIDC library adds `openid` itself.

## Contract hygiene

All eleven create-ticket sections are present. Anchors resolve (P10). Gates are
discovered from `justfile` and `.pre-commit-config.yaml`, not assumed (P11).
Non-goals are explicit and, apart from RF5(a)'s citation, correct. Forks are
surfaced with recommendations and then resolved in a dated block. §8 names no
unit tests, which is genuinely empty for a Terraform-only change and is stated
as such ("Post-apply checks are the operator's"), so §7's "every named test has
a file" requirement is vacuous here rather than violated. The one contract
break is §7's omission of the Q1 import (RF4).

## What I could not verify

- The end-to-end browser login itself. It cannot be driven without applying the
  change, and I am read-only. Eval rows 2 to 5 are the right shape to catch it.
- The D3 aside ("2 of 25 Consul services") was not probed; minting a brokered
  token has side effects. The 403 half is substantiated by reading the `deploy`
  policy at `nomad_deploy_role.tf:18-28`, which lacks `list-jobs`. Either way
  it is motivation, not a load-bearing premise.

---

**Recommendation to the operator:** apply RF1–RF5, then re-dispatch this pass
**with the plan fingerprint in the briefing**. On premise severity the plan is
close to ready — its verified core is unusually well evidenced — and the fixes
are all text.
