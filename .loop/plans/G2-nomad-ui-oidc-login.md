---
epic = "rollout"
depends_on = ["F2-foundation-vault-oidc-provider"]
priority = 25
summary = "Give the Nomad web UI and `nomad login` a sign-in button backed by Vault's OIDC provider, so a developer reaches Nomad with the same identity they use everywhere else instead of pasting an ACL token. Also resolves the unmanaged `developer` policy the cluster already carries."
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
`developer` policy is live but unmanaged, so this ticket has to decide its
fate rather than build beside it; and a redirect URI that does not match
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
  `list_claim_mappings`, plus `bind_type`/`bind_name`/`selector` on the
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

**`developer` already exists and is not in Terraform.** `grep` over
`deployments/**/*.tf` returns nothing for it. It grants exactly what a person
at a keyboard needs:

```
namespace "default": write + submit-job, read-job, list-jobs, dispatch-job,
                     read-logs, read-fs, alloc-exec, alloc-lifecycle,
                     alloc-node-exec
host_volume "*":     write
node / agent / operator: read
```

So the policy this ticket wants to hand out is already written, already live,
and owned by nobody. That is the same shape as the drifting `test` OIDC client
F2 found, and it needs the same explicit decision rather than being built
around. See Q1.

### Why this matters beyond the browser

`D3-cli-read-commands` scoped its command surface down because the brokered
`deploy` token returns 403 on `nomad job status` and sees only 2 of 25 Consul
services. That constraint comes from the **role**, not from Nomad. Once a
human can obtain a `developer`-scoped token, D3's justification for the
narrow surface weakens. G2 does not fix D3, and must not silently widen it,
but D3 should be re-read after this lands.

## Non-goals / out of scope

- **No Consul UI SSO.** Consul's OIDC auth method is Enterprise-only and this
  cluster is Community Edition, verified: `consul version` carries no `+ent`
  and `/v1/agent/self` reports `Edition: n/a`. The CE `jwt` method is
  programmatic with no browser redirect, so the UI cannot drive it either.
  `D2` §12 owns the paste-a-token path for Consul. Do not attempt it here.
- **No change to `vault_identity_oidc_client.smoke`** or its group and
  assignment. F2's smoke client stays until a later ticket retires it.
- **No workload identity work.** `F1-foundation-nomad-wi-jwt-trust` owns the
  `jwt-nomad` mount that machines use. This ticket is humans only, and the two
  must not be confused: one is a Nomad auth method trusting Vault, the other
  is a Vault auth method trusting Nomad.
- **No Vault policy changes.** Whether the operator entity can read
  `nomad/creds/*` is `F7`'s question and is unrelated: OIDC login to Nomad
  bypasses brokering entirely.
- **No oauth2-proxy.** Nomad speaks OIDC natively. `L1` is a different
  mechanism for services that do not.

## Requirements & restrictions

- **R1. Request the `groups` scope explicitly.** Set `oidc_scopes` to include
  `groups`. Vault requires `openid`, and a request that omits `groups`
  returns a correctly signed token with **no groups claim**, however perfect
  the scope template is. F2's close-out records this as the trap that hid a
  real defect: apply succeeded, tokens issued, claim absent. The binding rule
  then matches nothing and every login yields a token with no policy.
- **R2. Enable PKCE.** `oidc_enable_pkce = true`. HashiCorp's own
  Vault-to-Nomad guide states PKCE is required from Nomad 1.10 onward, and
  this cluster is on 2.0.4.
- **R3. Both redirect URIs, exactly.** The UI callback
  `https://nomad.lab.orangecluster.nl/ui/settings/tokens` **and** the CLI
  callback `http://localhost:4649/oidc/callback`, which is where
  `nomad login` listens by default (`-oidc-callback-addr`, default
  `localhost:4649`). They must appear in both `allowed_redirect_uris` on the
  Nomad auth method and `redirect_uris` on the Vault client. Omitting the CLI
  one silently breaks terminal login while the UI keeps working.
- **R4. Point at the `lab` provider, never `default`.** Vault's built-in
  `default` provider advertises `allowed_client_ids = ["*"]` and an issuer of
  `http://192.168.2.30:8200/v1/identity/oidc/provider/default`. A consumer
  aimed at it **works**, over plaintext against a raw IP, while bypassing
  every scoping decision F2 made. Set `bound_issuer` to the `lab` issuer so a
  misaimed discovery URL fails loudly.
- **R5. Append the client to `local.oidc_provider_client_ids`**
  (`oidc.tf:63-67`). Vault gates the provider on that list and ships no
  standalone resource for it. Omit it and Vault refuses the authorization
  request. Register against the key with a standalone
  `vault_identity_oidc_key_allowed_client_id`; do not add an inline
  `allowed_client_ids` to the key resource, which creates a Terraform cycle.
- **R6. No client secret in the diff.** The Vault client secret is generated
  by Vault. Persist it to KV2 the way F2 does at `secrets.tf`, and pass it to
  the Nomad auth method by reference. Do not score this with
  `detect-private-key`: that hook matches a fixed blocklist of PEM headers and
  cannot match a Vault client secret. F2's marker records that false green.
- **R7. Resolve the `developer` policy, do not duplicate it.** Per Q1.
  Creating a second, Terraform-managed policy with the same grants beside the
  unmanaged original leaves two sources of truth for who can `alloc-exec`.

## Code surface

New file, `deployments/infrastructure/nomad_oidc.tf`:

- `vault_identity_oidc_client` for Nomad, `client_type = "confidential"`,
  both redirect URIs from R3.
- `vault_identity_group` and `vault_identity_oidc_assignment` gating who may
  use it.
- `vault_identity_oidc_key_allowed_client_id`, copying `oidc.tf:118-121`.
- `nomad_acl_auth_method`, type `OIDC`, `token_locality` and `max_token_ttl`
  set deliberately (see Q2).
- `nomad_acl_binding_rule` with a `selector` on the mapped groups list,
  binding to the `developer` policy or a role wrapping it, per Q1.

Edited:

- `deployments/infrastructure/oidc.tf:63-67`, one line appended to
  `local.oidc_provider_client_ids`. Nothing else in that file changes.
- `deployments/infrastructure/secrets.tf`, one KV2 write for the client
  credentials, matching F2's pattern.
- `docs/vault-human-auth.md`, "Adding a service", to record Nomad as the
  first real consumer.

## Tests & validation gates

Repo gate: `just pre_commit`, which runs `terraform fmt -check` and
`terraform validate` per root. The eval marker
`.loop/evals/G2-nomad-ui-oidc-login.md` carries the scored rows.

Post-apply checks are the operator's, since the loop never runs
`terraform apply`. The load-bearing one decodes the issued token rather than
accepting that a token came back, for the reason in R1.

## Risk assessment

- **Medium: a new authentication path into the orchestrator.** Anyone in the
  bound Vault group gets `alloc-exec` on the default namespace, which is
  shell access inside running containers. The assignment and the group are
  the whole control. Scope them before applying, not after.
- **Low: breaking existing access.** Purely additive. `deploy`, the existing
  management tokens and the workload `jwt-nomad` path are untouched. Rollback
  is deleting the auth method, after which the UI returns to token paste.
- **Low: silent claim failure.** Mitigated by R1 and the decode-the-token
  gate, which is exactly the defect this pattern produced in F2.
- **Watch: `alloc-node-exec` in the `developer` policy** grants exec on the
  node itself, not just an allocation. That is a bigger grant than the rest
  of the policy and predates this ticket. Q1's answer should say whether it
  stays.

## Subtickets (ordered)

1. Vault client, group, assignment, key registration, and the one-line
   append to `local.oidc_provider_client_ids`. Apply and confirm the client
   appears in `vault list identity/oidc/client`.
2. KV2 write for the client credentials.
3. `nomad_acl_auth_method` with R1 to R4 applied.
4. Resolve `developer` per Q1, then `nomad_acl_binding_rule`.
5. Gate, then the operator's post-apply rows.
6. Docs.

## Open questions (operator must settle)

> **All questions in this section were resolved on 2026-07-31 in
> `## Forks resolved, 2026-07-31` at the end of this plan.** Each followed the
> recommendation recorded below, so these read as history rather than as
> pending decisions.


**Q1 — the unmanaged `developer` policy: import, replace, or reference?**
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

**Q3 — one Vault group for Nomad, or reuse a general operators group?**
F2 created `oidc-smoke` as a throwaway. This ticket needs a real group.
*Recommendation:* a dedicated `nomad-developers` group. A shared "operators"
group means every future consumer grants the same people access by default,
which is the opposite of what per-consumer assignments are for.

**Q4 — does the UI callback need the trailing path exactly as documented?**
HashiCorp documents `http://{host:port}/ui/settings/tokens` for the UI and
`http://{host:port}/oidc/callback` for the CLI. This ticket assumes the edge
hostname over HTTPS for the former and `localhost:4649` for the latter.
*Recommendation:* verify against the running UI during subticket 3 before
writing the Vault client's `redirect_uris`, since a mismatch fails at the
last hop and reads like a Vault problem rather than a URI typo.

## Forks resolved, 2026-07-31

- **Q1 → import the `developer` policy into Terraform.** It is live, unmanaged
  and grants `alloc-exec` and `alloc-node-exec`. Importing puts an existing
  grant under management without changing what any current token can do, which
  keeps the behavior change out of the same ticket that introduces a login
  path. Replacing it would do both at once; referencing it by name leaves the
  drift that made this a question.
  Two consequences the implementer must carry: the import must be verified to
  leave the live rules **byte-identical**, and `alloc-node-exec` stays for now
  and gets its own decision later. Narrowing it here would be a behavior
  change smuggled in under an import.
- **Q2 → `token_locality = "global"`, `max_token_ttl = 8h`.** One region, so
  locality is moot and `global` avoids a surprise if that ever changes. Eight
  hours matches a working day. This is a browser session with no refresh
  mechanism behind it, so it is a genuinely different decision from D2 Q6,
  which concerns the long-lived Vault token a human holds on disk.
- **Q3 → a dedicated `nomad-developers` Vault group.** A shared operators
  group means every future consumer admits the same people by default, which
  is the opposite of what per-consumer assignments are for. F2 set the pattern
  with `oidc-smoke`; this is the first real one.
- **Q4 → verify the callback paths against the running UI in subticket 3,
  before writing them into the Vault client.** HashiCorp documents
  `/ui/settings/tokens` for the UI and `/oidc/callback` for the CLI. This
  ticket assumes the edge hostname over HTTPS for the first and
  `localhost:4649` for the second. A mismatch fails at the last hop of a
  browser redirect and reads like a Vault problem rather than a URI typo, so
  confirm rather than trust the plan.
