---
epic = "rollout"
depends_on = ["F2-foundation-vault-oidc-provider"]
priority = 25
summary = "Give the Nomad web UI and `nomad login` a sign-in button backed by Vault's OIDC provider, so a developer reaches Nomad with the same identity they use everywhere else instead of pasting an ACL token. Binds to the `developer` Nomad policy that Ansible already owns, authoring none of it."
tags = ["nomad", "oidc", "vault", "terraform", "sso"]
---

# G2 — Sign in to the Nomad UI with Vault OIDC

## Title

Register Nomad as an OIDC client of Vault's `lab` provider and create the
Nomad auth method and binding rule behind it, so the web UI gains a sign-in
button and `nomad login` works from a terminal. Both paths hand back an ACL
token carrying the `developer` policy, gated on Vault group membership.

## Size / Effort

**M.** The resource graph is small and every piece is verified to exist. The
weight is in three places: the `groups` claim can go missing silently, so the
gates have to decode a token rather than trust that one came back; the
`developer` policy is owned by Ansible, so this ticket must consume it rather
than re-author it; and a redirect URI that does not match
exactly fails at the last hop of a browser flow, which is tedious to debug.

## Triggered by

Operator question, 2026-07-31: a developer authenticates once with
`localstack login` and the CLI shims hand tokens to `nomad`, `consul` and
`vault`. That covers the terminal. It cannot cover a browser, because a
browser cannot read a token file on the developer's laptop. The Nomad UI is
reachable today and its only login is pasting a Secret ID.

This is the case OIDC federation exists for, and it is the one surface where
the brokering design in `D2-cli-login-broker-tokens` has nothing to offer.

## Context (today's state)

### What already exists

Verified live on 2026-07-31 unless noted.

- **The edge already routes the UI.** `acl is_nomad` at
  `deployments/infrastructure/services/haproxy.hcl:101`, routed by `:112` to
  `backend nomad` at `:136-137`, which is `192.168.2.30:4646`.
  `https://nomad.lab.orangecluster.nl/` returns 307 to its UI path.
- **Vault is a working OIDC provider.** F2 is `done`, merged and applied. The
  `lab` provider issues at
  `https://vault.lab.orangecluster.nl/v1/identity/oidc/provider/lab`, its
  JWKS serves keys, and a real login through it returns an `id_token` whose
  `groups` claim is a JSON array. That was proven end to end in F2's close-out,
  not assumed.
- **The provider file has a marked extension point.**
  `local.oidc_provider_client_ids` at `oidc.tf:63-67` is the one line a
  consumer ticket edits. The key needs no edit: register through
  `vault_identity_oidc_key_allowed_client_id`, copying the smoke-test block at
  `oidc.tf:118-121`.
- **Nomad supports OIDC in Community Edition.** The cluster runs 2.0.4 and the
  CLI reports `Supported types are 'OIDC' and 'JWT'`. Unlike Consul, whose
  OIDC auth method is Enterprise-only, nothing here is license-gated.
- **The pinned Terraform provider has everything needed.**
  `hashicorp/nomad ~>2.5.0` (`providers.tf:3-6`), resolved to 2.5.2. It
  carries `nomad_acl_auth_method`, `nomad_acl_binding_rule` and
  `nomad_acl_role`, and the schema fields `oidc_discovery_url`,
  `oidc_client_id`, `oidc_client_secret`, `oidc_scopes`, `oidc_enable_pkce`,
  `bound_audiences`, `allowed_redirect_uris`, `claim_mappings`,
  `list_claim_mappings` (these ten sit inside the auth method's nested
  `config` block, not on the resource, see §Code surface), plus
  `bind_type`/`bind_name`/`selector` on the
  binding rule. No provider bump, no new dependency.

### The cluster's ACL state

```
nomad acl auth-method list   ->  none
nomad acl role list          ->  none
nomad acl policy list        ->  deploy, developer
```

`deploy` is Terraform-managed at `nomad_deploy_role.tf:13-30` and is
deliberately narrow: `submit-job`, `read-job` and the host-volume
capabilities, with no `list-jobs`, no `read-logs`, no `alloc-exec` and no
node, agent or operator access. **It is a deployer policy and is wrong for a
human.**

### The finding that shapes this ticket

**`developer` already exists, and ANSIBLE owns it.** Corrected 2026-07-31: an
earlier version of this section said it was "not in Terraform" and concluded it
was unmanaged. That was a bad inference from a `grep` over `.tf` files only.
`bootstrap/roles/nomad_server/tasks/main.yml:182-187` applies it with the
bootstrap token from the checked-in source
`bootstrap/roles/nomad_server/files/nomad_developer_policy.hcl`.

It grants exactly what a person at a keyboard needs:

```
namespace "default": write + submit-job, read-job, list-jobs, dispatch-job,
                     read-logs, read-fs, alloc-exec, alloc-lifecycle,
                     alloc-node-exec
host_volume "*":     write
node / agent / operator: read
```

So the policy this ticket wants to hand out is already written, already live,
and **already owned**. This ticket consumes it by name and authors nothing.
It is NOT the same shape as the drifting `test` OIDC client F2 found: that
one genuinely had no owner. See Q1, whose original framing rested on the
mistaken reading and is corrected there.

### Why this matters beyond the browser

`D3-cli-read-commands` scoped its command surface down because the brokered
`deploy` token returns 403 on `nomad job status` and sees only 2 of 25 Consul
services. That constraint comes from the **role**, not from Nomad. Once a
human can obtain a `developer`-scoped token, D3's justification for the
narrow surface weakens. G2 does not fix D3, and must not silently widen it,
but D3 should be re-read after this lands.

## Non-goals / out of scope

- **No Consul UI SSO.** Consul's OIDC auth method is Enterprise-only. The
  first-party doc banners it:
  `consul/docs/secure/acl/auth-method/oidc` reads "This feature requires
  version 1.8.0+ of self-managed Consul **Enterprise**", and its nav entry is
  tagged `OIDC (ENT)`. That banner is the citation and it is the whole
  argument. **Do not re-add a cluster probe here.** An earlier version of this
  bullet claimed `/v1/agent/self` reports `Edition: n/a`. It reports no
  `Edition` field at all (`grep -i edition` over the full response returns
  nothing), and `consul version` prints no Edition line either, so no probe on
  this cluster establishes edition directly. The CE `jwt` method is
  programmatic with no browser redirect, so the UI cannot drive it either.
  `D2` §12 owns the paste-a-token path for Consul. Do not attempt it here.
- **No change to `vault_identity_oidc_client.smoke`** or its group and
  assignment. F2's smoke client stays until a later ticket retires it.
- **No workload identity work.** `F1-foundation-nomad-wi-jwt-trust` owns the
  `jwt-nomad` mount that machines use. This ticket is humans only, and the two
  must not be confused: one is a Nomad auth method trusting Vault, the other
  is a Vault auth method trusting Nomad.
- **No Vault policy changes.** Whether the operator entity can read
  `nomad/creds/*` is `F11`'s question (F7 is retired) and is unrelated here:
  OIDC login to Nomad bypasses brokering entirely.
- **No group taxonomy.** `F14-foundation-role-taxonomy` owns the group naming
  convention and the OIDC assignment wiring that decides who may authorize
  against a client. G2 consumes a group name; it does not define one. The
  group this ticket binds is **F11's `developer`**, which is applied and live
  (`developer_group.tf`) with the operator entity as a member. This ticket
  creates no `vault_identity_group` — see the code surface for why a duplicate
  collides and a differently-named one admits nobody.
- **No oauth2-proxy.** Nomad speaks OIDC natively. `L1` is a different
  mechanism for services that do not.

## Requirements & restrictions

- **R1. Request the `groups` scope explicitly.** Write
  `oidc_scopes = ["groups"]`, matching HashiCorp's Vault-to-Nomad guide, whose
  worked config is `"OIDCScopes": ["groups"]`. Vault also requires `openid`,
  and the guide's example does not list it. **Settled 2026-08-01, measured:** with
  `OIDCScopes = ["groups"]`, Nomad's `/v1/acl/oidc/auth-url` emits
  `scope=openid groups` and `code_challenge_method=S256` — Nomad adds `openid`
  itself, so `["groups"]` is correct as written and needs no `"openid"` entry.
  Still decode the issued token in subticket 4 to confirm the claim arrives. A request that omits `groups`
  returns a correctly signed token with **no groups claim**, however perfect
  the scope template is. F2's close-out records this as the trap that hid a
  real defect: apply succeeded, claim absent. The binding rule then matches
  nothing and **the login fails** — `400 no role or policy bindings matched`,
  measured on Nomad 2.0.4. No token is issued; a green login with an empty
  policy list is unreachable.
- **R2. Enable PKCE.** `oidc_enable_pkce = true`, as defense in depth. It
  works here because Vault does its half: the live `lab` provider's discovery
  document advertises `"code_challenge_methods_supported": ["plain","S256"]`,
  and the cluster is on 2.0.4, past the 1.10.0 that added PKCE on the Nomad
  side. The setting is optional, not mandatory:
  `nomad/docs/secure/authentication/sso-pkce-jwt` reads "Beginning with Nomad
  v1.10.0, Nomad **supports** PKCE", the 1.10.0 changelog says Nomad
  "**enables** PKCE for OIDC logins", and the provider schema types
  `oidc_enable_pkce` as optional, defaulting off. **Rationale corrected
  2026-07-31:** an earlier version of this line cited the Vault-to-Nomad guide
  (`nomad/docs/secure/authentication/sso-vault`) as making PKCE required from
  1.10. That guide never mentions PKCE, and its worked auth-method config
  carries no `OIDCEnablePKCE`. The setting stays. The justification does not.
- **R3. Both redirect URIs, exactly.** The UI callback
  `https://nomad.lab.orangecluster.nl/ui/settings/tokens` **and** the CLI
  callback `http://localhost:4649/oidc/callback`, which is where
  `nomad login` listens by default (`-oidc-callback-addr`, default
  `localhost:4649`). They must appear in both `allowed_redirect_uris` on the
  Nomad auth method and `redirect_uris` on the Vault client. Omitting the CLI
  one breaks terminal login while the UI keeps working — **loudly, not
  silently**: measured 2026-08-01, an unlisted redirect URI fails at auth-url
  generation with `unauthorized redirect_uri`. That is a good failure; the
  point stands that the two URIs are separate and both are needed.
- **R4. Point at the `lab` provider, never `default`.** Vault's built-in
  `default` provider advertises `allowed_client_ids = ["*"]` and an issuer of
  `http://192.168.2.30:8200/v1/identity/oidc/provider/default`. A consumer
  aimed at it **works**, over plaintext against a raw IP, while bypassing
  every scoping decision F2 made. Set `bound_issuer` to the `lab` issuer so a
  misaimed discovery URL fails loudly. It is typed as a list of strings, so
  write it as a one-element list (see §Code surface).
- **R5. Append the client to `local.oidc_provider_client_ids`**
  (`oidc.tf:63-67`). Vault gates the provider on that list and ships no
  standalone resource for it. Omit it and Vault refuses the authorization
  request. Register against the key with a standalone
  `vault_identity_oidc_key_allowed_client_id`; do not add an inline
  `allowed_client_ids` to the key resource, which creates a Terraform cycle.
- **R6. No client secret in the diff, and none on disk.** The Vault client
  secret is generated by Vault — measured 2026-08-01, `vault read
  identity/oidc/client/<name>` returns `client_id` and a 75-char
  `client_secret` carrying the `hvo_secret_` prefix. It moves from
  `vault_identity_oidc_client` to `nomad_acl_auth_method` as a Terraform
  reference, so it never appears in the diff, a template, a variable file or a
  file on any host. It does live in state, which is already true of every
  other secret in this root. This replaces the earlier "persist to KV2 and
  pass by reference" shape, which existed only to hand the value to a
  playbook.
  Do not score this with `detect-private-key`: that hook matches a fixed
  blocklist of PEM headers and cannot match a Vault client secret. F2's
  marker records that false green.
- **R6b. Terraform brokers its own management token.** The auth method and
  binding rule are management-only writes (measured: a maximal *client* policy
  403s on both). `nomad/role/deploy` is `type = "client"`
  (`nomad_deploy_role.tf:39`), so this ticket adds
  `vault_nomad_secret_role.manage` with `type = "management"`, reads
  `nomad/creds/manage` through a `vault_nomad_access_token` data source, and
  configures a **second `nomad` provider alias** with it. The default provider
  is left exactly as it is, so nothing else in this root changes credential.
  (It does **not** hold a brokered client token today — it is bare and reads
  `NOMAD_TOKEN`, currently the bootstrap token. See the code surface for what
  that means and why R6b is forward-looking for F8.)
  Add `nomad/creds/manage` to F11's `developer` policy in `developer_group.tf`
  next to the existing `nomad/creds/deploy`. Measured working end to end on
  2026-08-02; both probe artifacts were torn down in the same command.
- **R6c. `README.md:44-59` needs no new step.** That is the canonical
  three-step rebuild sequence — bootstrap, infrastructure, applications — and
  everything this ticket adds lands inside the infrastructure `terraform
  apply`. An earlier draft added a fourth step for a standalone recipe; there
  is no recipe and no playbook, so there is nothing to add and nothing a
  rebuild can silently skip.
- **R7. Do NOT author or import the `developer` policy.** Ansible owns it
  (`nomad_server/tasks/main.yml:182-187`). Bind the binding rule to it by
  name. A Terraform copy, whether imported or freshly written, creates two
  owners: the next `just bootstrap` re-applies Ansible's version, Terraform
  reports drift on the following plan, and the two fight indefinitely. If the
  grants need changing, change
  `bootstrap/roles/nomad_server/files/nomad_developer_policy.hcl`.

## Code surface

New file, `deployments/infrastructure/nomad_oidc.tf`:

- `vault_identity_oidc_client` for Nomad, `client_type = "confidential"`,
  both redirect URIs from R3.
- `vault_identity_oidc_assignment` listing **F11's existing `developer`
  group** — `vault_identity_group.developer` in `developer_group.tf`, applied
  and live. **Do not create a group here.** A second one named `developer`
  collides on Vault's unique name; a differently-named one admits nobody,
  because the assignment gates on membership and the operator entity is in
  F11's. Reference `vault_identity_group.developer` directly — it is in this
  same root, so no data source is needed.
- `vault_identity_oidc_key_allowed_client_id`, copying `oidc.tf:118-121`.
**The Nomad half is TERRAFORM, in the same file.** `nomad acl auth-method
create` and `binding-rule create` do require a Nomad **management** token —
measured against a client token with a deliberately maximal policy (`namespace
"*" write` plus node/agent/operator/quota/plugin write): 403 on both. An
earlier draft concluded from this that Ansible had to own them. **That
conclusion was wrong**, and it rested on treating our one existing Vault Nomad
role as a ceiling.

`vault_nomad_secret_role` carries a `type` field. `nomad/role/deploy` is
`type = "client"` (`nomad_deploy_role.tf:39`), which is why the brokered token
403s. A second role with `type = "management"` mints a token that does the job.
Measured end to end on the live cluster, 2026-08-02:

```
$ vault write nomad/role/probe-mgmt type=management global=true
$ vault read -field=secret_id nomad/creds/probe-mgmt
$ NOMAD_TOKEN=<that> nomad acl token self
Type    = management
Global  = true
$ NOMAD_TOKEN=<that> nomad acl auth-method create -name=probe-delete-me ...
Name     = probe-delete-me
Type     = OIDC
Locality = global
```

Both the probe role and the probe auth method were deleted in the same command;
`vault list nomad/role` is back to `["deploy"]` and `nomad acl auth-method list`
to "No ACL auth methods found".

**Read is NOT management-only** — an earlier draft said it was, and it is false:
`GET /v1/acl/auth-methods` returns `[]` with HTTP 200 and no token at all,
measured against the live edge. Only `auth-method info` requires management.

So this ticket adds, in `nomad_oidc.tf`:

- `vault_nomad_secret_role.manage`, `type = "management"`, `global = true`.
- A `vault_nomad_access_token` data source reading `nomad/creds/manage`, and a
  second `nomad` provider alias configured with it. The default `nomad`
  provider is untouched, so the 11 `nomad_job` and 9
  `nomad_dynamic_host_volume` resources in this root are unaffected. (17
  `nomad_job` spans both roots; this root holds 11.)

  **Be precise about what the default provider holds today: not a brokered
  token.** `providers.tf:26` is a bare `provider "nomad" {}`, so it reads
  `NOMAD_TOKEN` from the environment, and that is currently the Nomad
  **bootstrap** token (`Type = management`, `Global = true`); `VAULT_TOKEN` is
  `root`. So today's credential could create both ACL resources on the default
  provider with no new role at all. **R6b is forward-looking**: F8 is the
  ticket that moves this root to a brokered token, it is `blocked` in the
  ledger, and once it lands the default provider becomes a *client* token that
  403s on these two writes. The cost of doing it now is that the Medium
  widening in the risk section lands immediately for a payoff that arrives
  with F8. Doing it later means F8 lands and Nomad UI login breaks. Worth
  telling F8 either way: its recorded blocker is that a brokered token cannot
  manage the Nomad ACL policy defining its own grants, and a `type =
  "management"` role is the answer to it.

  **`depends_on = [vault_policy.developer]` on the data source.** The
  `nomad/creds/manage` grant goes into `vault_policy.developer` beside
  `developer_group.tf:123-125`, and nothing otherwise orders that write before
  the creds read. Without it the read can fire against a policy that does not
  yet carry the grant. Harmless today, since the run is root; a 403 the moment
  F8 lands.

  **Every plan and apply mints a fresh global management token.** Once
  `nomad/role/manage` exists the data source is no longer deferred, so it reads
  on every run. Bounded by the mount lease — `vault read nomad/config/lease`
  reports `ttl 30m`, `max_ttl 1h` — but it is new for this root, whose `nomad`
  provider has always been env-driven.
- `path "nomad/creds/manage" { capabilities = ["read"] }` added to F11's
  `developer` policy in `developer_group.tf`, alongside the existing
  `nomad/creds/deploy`.

**No Ansible playbook, and no new `just` recipe.** This lands in the
infrastructure root and ships with `just apply`, like every other change here.
An earlier draft put the work in a playbook, which then could not join the
`bootstrap:` sequence — it needed `client_id` and `client_secret` from a
Terraform-layer resource, so listing it there would abort `just bootstrap`
before `configure_podman`, `configure_tailscale` and `configure_network` ran,
and it grew a standalone recipe to work around that. With Terraform owning
both halves the problem disappears: the client and the auth method are created
in one `apply`, in dependency order, with no second command and nothing new
for an operator to learn.

**The client secret never lands on disk or in a host file.** It moves
`vault_identity_oidc_client` to the `nomad_acl_auth_method` resource inside
Terraform, so it never reaches a host filesystem. No marking is needed:
`vault_identity_oidc_client.client_secret` and `config.oidc_client_secret` are
both already `sensitive: true` in the installed providers, so it stays out of
plan output. It does live in state, which is already true of every other secret
in this root.

**This does not reintroduce what F8 removes.** F8 moves this root off the root
token to a brokered credential; a second brokered credential, scoped to a
distinct role, is the same pattern rather than a regression. What it does mean
is that `developer` can read a Nomad management token — see Risk, below.

Contents:

- **`nomad_acl_auth_method`**, `type = "OIDC"`, `token_locality = "global"`,
  `max_token_ttl = "8h"` per Q2. Every OIDC field lives in a nested `config`
  block: `oidc_discovery_url`, `oidc_client_id`, `oidc_client_secret`,
  `oidc_scopes`, `oidc_enable_pkce`, `bound_audiences`, `bound_issuer`
  (typed `["list","string"]`), `allowed_redirect_uris`, `claim_mappings` and
  `list_claim_mappings`. Schema verified against the installed 2.5.2 binary.
- **`nomad_acl_binding_rule`**, with `auth_method` (**Required** in the 2.5.2
  schema — name the method resource), `bind_type = "policy"`, `bind_name =
  "developer"` (the policy Ansible already owns), and a `selector` on the
  mapped groups list.

  **The selector and `list_claim_mappings` are one decision, not two.** The
  selector reads the *mapped* name, not the claim name. HashiCorp's guide maps
  `{"groups": "roles"}` and selects on `list.roles`; this plan maps
  `{"groups": "groups"}` and selects on `list.groups`. Mix them and the
  selector matches nothing.

  **It fails loudly, not silently** — measured on Nomad 2.0.4, the version
  this cluster runs: `Error performing login: 400 (no role or policy bindings
  matched)`, and no token is issued. `nomad/acl_endpoint.go` carries the guard
  in both the OIDC and JWT paths. An earlier draft of this plan claimed a
  silent green login with an empty policy list; **that state is unreachable**.
  Nothing validates the pair at *create* time, though, so a mismatch applies
  clean and only surfaces at first login. Pin both together and assert the pair
  in review.

**Terraform is what makes this idempotent, and that is not a small detail.**
`nomad acl binding-rule create` is **not** idempotent — measured, two identical
runs produced two live rules on the same method with the same selector, and
`binding-rule update` takes an **ID**, not a name. Worse, a guard cannot be
written against it cleanly: `binding-rule list` returns only `ID`,
`Description`, `AuthMethod`, `CreateIndex` and `ModifyIndex` — measured, in
both table and `-json` form:

```
$ nomad acl binding-rule list -t '{{range .}}{{.Selector}}{{end}}'
Error formatting the data: can't evaluate field Selector in type
*api.ACLBindingRuleListStub
```

so "list and match on selector" is unwriteable, and `list` has no
`-auth-method` flag either. An imperative implementation grows one rule per
run and a stale wide rule survives every later narrowing. `nomad_acl_binding_rule`
holds the ID in state and updates in place, which removes the whole class.
(`auth-method create` **is** an upsert by name, so that half was never the
problem.)

Both resources ship in the installed provider (2.5.2, `hashicorp/nomad`,
pinned `~> 2.5.0` in `.terraform.lock.hcl:25-27`) — confirmed by name in the
binary, along with `oidc_enable_pkce`, `oidc_client_assertion` and
`oidc_disable_userinfo`. On the resource sit `type`, `token_locality`,
`max_token_ttl`, `token_name_format` and `default`; everything OIDC is nested
under `config`.

**Deliberately NOT created, per Q1 (read this before adding a file):**

- **No `nomad_acl_policy "developer"` resource**, in `nomad_oidc.tf`, in
  `nomad_deploy_role.tf`, or anywhere else.
- **No `import` block** for that policy. An earlier draft of Q1 recommended
  importing it, and that recommendation is rejected: an import gives one
  policy two owners, so the next `just bootstrap` re-applies Ansible's copy,
  the following `terraform plan` reports drift, and the two fight on every
  run. `bind_name = "developer"` is a string; Terraform never reads or writes
  the policy body.
- Consequence for scope: this ticket does **not touch the `developer` policy
  body** — Ansible keeps sole ownership of it. It does add a grant to F11's
  Vault `developer` policy (`nomad/creds/manage`), which is a different file
  and a different thing. If the grants
  themselves need changing, that is a separate ticket against
  `bootstrap/roles/nomad_server/files/nomad_developer_policy.hcl`.

Edited:

- `deployments/infrastructure/oidc.tf:63-67`, one line appended to
  `local.oidc_provider_client_ids`. Nothing else in that file changes.
- `deployments/infrastructure/developer_group.tf`, one stanza appended to
  `vault_policy.developer`: `path "nomad/creds/manage" { capabilities =
  ["read"] }` (R6b).
- **No KV2 write.** An earlier draft copied the client credentials into KV2
  the way F2 does. Dropped: the secret passes as a Terraform reference from
  the client resource to the auth method (R6), so nothing would consume the
  copy, and a second copy of a live client secret earns nothing.
- **No `README.md` change**, no new `just` recipe, and no
  `bootstrap/justfile` entry. Everything ships in the infrastructure
  `terraform apply` (R6c).
- `docs/vault-human-auth.md`, "Adding a service", to record Nomad as the
  first real consumer **and to scope one instruction**: its "Write your client
  secret to KV2" paragraph. G2 passes the secret as a Terraform reference from
  the client resource straight to the auth method instead, because its consumer
  is a Terraform resource rather than a job reading through a `template`
  stanza. Cite that paragraph **by name, not line** — three separate line
  citations into this file went stale within one night.

  **The group rule is `F14`'s, not G2's**, and so is the matching header
  comment at `oidc.tf:7-10`. See the ownership note above; do not write either
  here.

## Tests & validation gates

Repo gate: `just pre_commit`, which runs `terraform fmt -check` and
`terraform validate` per root. The eval marker
`.loop/evals/G2-nomad-ui-oidc-login.md` carries the scored rows.

Post-apply checks are the operator's, since the loop never runs
`terraform apply`. The load-bearing one decodes the issued token rather than
accepting that a token came back, for the reason in R1.

**Idempotency still needs its own gate**: `terraform apply` twice and confirm
the second run is a no-op — specifically that `nomad acl binding-rule list`
holds exactly one rule for the method. The imperative CLI grows a rule per run
(measured); the resource holds the ID in state and should not. Assert **exactly
one**, not presence: a presence check passes against an already-duplicated
state, which is the failure it exists to catch.

## Risk assessment

- **Medium: `developer` can now broker a Nomad management token.** R6b adds
  `nomad/creds/manage` to F11's policy, so anyone who runs `localstack login`
  can mint a token that does anything in Nomad, including minting more Nomad
  tokens. Two things bound how much this changes. First, it is not a new
  ceiling: `developer` already holds `nomad/role/*` in F11's policy, so a
  holder could always have written this role themselves — this makes an
  existing capability convenient rather than granting a new one, and F11's
  own header says plainly it is not a containment boundary. Second, the
  brokered token is short-lived and per-person, which is the property the
  root token lacked. What it does add is a **second path to full Nomad
  control that does not pass through Vault self-elevation**, so it is worth
  stating rather than burying. If that trade is unwanted, the alternative is
  a separate credential held only by whoever runs `apply` — at the cost of
  `just apply` no longer working from a plain `localstack login`, which is
  the property this cluster is being rebuilt around.
- **Medium: a new authentication path into the orchestrator.** Anyone in the
  bound Vault group gets `alloc-exec` on the default namespace, which is
  shell access inside running containers. The assignment and the group are
  the whole control. Scope them before applying, not after.
- **Low: breaking existing access.** Purely additive. `deploy`, the existing
  management tokens and the workload `jwt-nomad` path are untouched. Rollback
  is deleting the auth method, after which the UI returns to token paste.
- **Low: a claim that never arrives.** It is not silent — the login returns
  `400 no role or policy bindings matched` and issues no token. Mitigated by
  R1 and the decode-the-token gate. F2's version of this defect WAS silent
  (Vault issued a token with the claim dropped); Nomad's is not, and the two
  should not be described the same way.
- **Low, but it is where the DoD hangs: the browser is redirected to Vault's
  UI.** The `lab` provider's `authorization_endpoint` is a Vault **UI** path,
  `https://vault.lab.orangecluster.nl/ui/vault/identity/oidc/provider/lab/authorize`,
  not an API path. So the developer's browser must reach the Vault UI through
  the edge and log in there (`userpass`) before Nomad ever sees a code. That
  is reachable today (`https://vault.lab.orangecluster.nl/ui/` returns 200,
  `vault auth list` shows `userpass/`), and F2's marker already flagged the
  UI-path surprise, so this is a prerequisite to state rather than a risk to
  mitigate. A developer with no Vault UI access cannot complete the flow.
- **Watch: `alloc-node-exec` in the `developer` policy** grants exec on the
  node itself, not just an allocation. That is a bigger grant than the rest
  of the policy and predates this ticket. Q1 deliberately does not settle it:
  the policy is Ansible's, so changing the grant is a different ticket against
  `bootstrap/roles/nomad_server/files/nomad_developer_policy.hcl`. What this
  ticket owes is a **stated** inheritance, not a silent one. The close-out
  must say plainly that everyone in the bound group gets it. The eval scores
  this twice: one row **proves** the capability by exec'ing into a live
  allocation and on the node, and a second row ("The widening is written down
  where a reader will meet it") checks the docs say so.

## Subtickets (ordered)

0. **Verify the callback paths against the running Nomad UI first** (Q4).
   Subticket 1 writes them into the Vault client's `redirect_uris` and
   applies, so checking afterwards means re-applying to correct them.

   **Use a fresh `ClientNonce` on every probe.** Nomad caches auth URLs per
   nonce: reusing one with a changed, unlisted `redirect_uri` returns **HTTP
   200 carrying the previous request's `redirect_uri`** and an identical
   `code_challenge`, which reads as a pass. A fresh nonce returns 500
   `unauthorized redirect_uri`. Measured. This bites the hand-rolled
   `auth-url` probe here and nowhere else — `nomad login` generates its own
   nonce, so the eval's login row cannot hit it.
1. **Terraform.** Vault client, assignment listing F11's live `developer`
   group, key registration, and the one-line append to
   `local.oidc_provider_client_ids`. **No `vault_identity_group`** — F11 owns
   it. Apply and confirm the client appears in `vault list identity/oidc/client`.
2. **Terraform.** `vault_nomad_secret_role.manage` (`type = "management"`,
   `global = true`), the `vault_nomad_access_token` data source on
   `nomad/creds/manage`, the aliased `nomad` provider configured with it, and
   the `nomad/creds/manage` grant appended to `vault_policy.developer` in
   `developer_group.tf`. Apply, then confirm `nomad acl token self` under the
   brokered token reports `Type = management`. **`nomad acl token self` has
   no `-t` and no `-json` flag** — measured, `flag provided but not defined`
   — and the bare form prints the Secret ID in full, so filter it:
   `nomad acl token self | grep -E '^(Type|Global)'`. The default `nomad` provider
   must be left alone — check this root's 11 `nomad_job` and 9
   `nomad_dynamic_host_volume` resources still plan clean.
3. **Terraform.** `nomad_acl_auth_method` on the aliased provider, with the
   client secret passed by reference from subticket 1's client, and
   `nomad_acl_binding_rule` with `bind_type = "policy"`, `bind_name =
   "developer"`. The selector and `list_claim_mappings` are one decision (see
   the Nomad half) — pin them together. No policy resource, no import block.
4. `terraform apply` **twice** and confirm the second run is a no-op, with
   exactly one binding rule on the method. Then the gate and the operator's
   post-apply rows.
5. Docs.

## Open questions (operator must settle)

> **All questions in this section were resolved on 2026-07-31 in
> `## Forks resolved, 2026-07-31` at the end of this plan.** Q2, Q3 and Q4
> followed the recommendation recorded below. **Q1 did not**: its premise was
> false, so its answer overrides the recommendation printed here. These read
> as history rather than as pending decisions.


**Q1 — the `developer` policy: import, replace, or reference?**
*(Premise below is wrong and kept only as history, see the corrected answer
in `## Forks resolved`. Ansible owns this policy; the option this question
recommends is rejected.)*
It is live, grants `alloc-exec` and `alloc-node-exec`, and no `.tf` file
mentions it. Three options. *Import* it into Terraform and bind to it, which
puts an existing grant under management without changing behavior. *Replace*
it with a Terraform-authored policy under a new name and delete the original,
which is cleaner but changes what any existing token carrying `developer`
can do. *Reference it by name only*, leaving it unmanaged, which is the least
work and leaves the drift.
*Recommendation:* import. It matches what F2 did with the `test` client in
spirit (resolve drift rather than build beside it) while avoiding a
behavior change in the same ticket that introduces a login path. Revisit
`alloc-node-exec` separately.

**Q2 — token TTL and locality for UI sessions.** `max_token_ttl` on the auth
method governs how long a browser session lasts, and `token_locality`
(`local` or `global`) governs whether the token works in one region.
*Recommendation:* `global` (single region, so the distinction is moot and
`global` avoids a surprise later) and a `max_token_ttl` of 8 hours, matching a
working day. Note this is a **different** decision from D2 Q6: that one
concerns the long-lived Vault token a human holds on disk, this one a browser
session with no refresh mechanism behind it.

**Q3 — which Vault group does the binding rule select on?**
*Settled: `developer`, the group `F11` creates.* An earlier draft invented
`nomad-developers`, which matches neither `F11`'s group nor `F14`'s
`app-<service>-<level>` convention, and the plan never said which source it
took.

`F11` is applied and live: the `operator` entity is a member of `developer`,
and `F11`'s own requirement 2 records that *"the group name also rides the
OIDC `groups` claim, which is how F14 and the per-app tickets consume it."*
That is exactly this ticket's consumption path, so inventing a parallel group
would mean two names for one role.

**The per-consumer gate is the OIDC assignment, not the group.** Who may use
Nomad's client is decided by `vault_identity_oidc_assignment`, which this
ticket creates and which lists only the groups it admits. So a shared group
does not imply shared access, and the objection the earlier draft raised does
not apply.

**Q4 — does the UI callback need the trailing path exactly as documented?**
HashiCorp documents `http://{host:port}/ui/settings/tokens` for the UI and
`http://{host:port}/oidc/callback` for the CLI. This ticket assumes the edge
hostname over HTTPS for the former and `localhost:4649` for the latter.
*Settled: verify in subticket 0, before the Vault client is written.* A
mismatch fails with `unauthorized redirect_uri` at auth-url generation
(measured), so it is loud — but it still costs an apply cycle to correct if
the URIs go in wrong. See the subticket list for what is and is not checkable
before the auth method exists.

## Forks resolved, 2026-07-31

- **Q1 → CORRECTED 2026-07-31. Reference it by name. Ansible owns it, and the
  question's own premise was wrong.**

  This plan said the `developer` policy was "live, unmanaged and owned by
  nobody", inferred from `grep` finding it in no `.tf` file. That inference was
  bad: not-in-Terraform is not the same as unmanaged. **Ansible owns it.**
  `bootstrap/roles/nomad_server/tasks/main.yml:182-187` runs
  `nomad acl policy apply ... developer /opt/nomad/policies/nomad_developer_policy.hcl`
  with the bootstrap token, from the checked-in source at
  `bootstrap/roles/nomad_server/files/nomad_developer_policy.hcl`.

  So the earlier answer, "import it into Terraform", is now **rejected**: it
  would create two owners for one policy. The next `just bootstrap` would
  re-apply Ansible's copy over Terraform's, Terraform would see drift on the
  following plan, and the two would fight indefinitely. That is a worse state
  than the one the question was trying to fix.

  **Bind the auth method's binding rule to the policy by name.** Ansible keeps
  authoring it; this ticket consumes it. If the grants need changing, change
  `files/nomad_developer_policy.hcl`, which is where they already live.

  `alloc-node-exec` still deserves its own decision later. It grants exec on
  the node, not just an allocation, and this ticket hands it to everyone in the
  bound Vault group. Say so in the close-out rather than inheriting it
  silently.
- **Q2 → `token_locality = "global"`, `max_token_ttl = 8h`.** One region, so
  locality is moot and `global` avoids a surprise if that ever changes. Eight
  hours matches a working day. This is a browser session with no refresh
  mechanism behind it, so it is a genuinely different decision from D2 Q6,
  which concerns the long-lived Vault token a human holds on disk.
- **Q3 → `F11`'s `developer` group.** It is applied and live, the operator
  entity is already a member, and its name is what the `groups` claim carries.
  Access stays per-consumer because the OIDC **assignment** is the gate, not
  the group.
- **Q4 → verify the callback paths in subticket 0, before the Vault client is
  written and applied.** Note the check is only partly possible that early:
  the Nomad UI builds its sign-in button from the auth-method list, which does
  not exist until subticket 3. The cheap check works at 0; a faithful one needs
  a scratch auth method, which `auth-method create` will accept against the
  real discovery URL with a placeholder client id — at the cost of a broken
  public sign-in button while it lives. HashiCorp documents
  `/ui/settings/tokens` for the UI and `/oidc/callback` for the CLI. This
  ticket assumes the edge hostname over HTTPS for the first and
  `localhost:4649` for the second. A mismatch fails at the last hop of a
  browser redirect and reads like a Vault problem rather than a URI typo, so
  confirm rather than trust the plan.
