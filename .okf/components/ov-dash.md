---
type: component
title: ov-dash, OpenViking's browser face
description: "How ov-dash signs a person in through a three-hop chain (Vault's lab provider, the jwt-lab mount, an OpenViking identity token) and why that chain keeps Login MFA on the userpass mount. Lists the four lifetimes involved, the resources in each root, apply order, and the single-alloc constraint."
tags: [ov-dash, openviking, vault, oidc, mfa, jwt-lab]
status: stable
generated:
  by: claude-opus/5.5
  at: 2026-09-27
sources:
  - id: ov-dash-jobspec
    resource: git:3ec5d1e:deployments/applications/services/ov-dash.hcl
  - id: app-services
    resource: git:3ec5d1e:deployments/applications/services.tf
  - id: app-secrets
    resource: git:3ec5d1e:deployments/applications/secrets.tf
  - id: infra-oidc
    resource: git:3ec5d1e:deployments/infrastructure/oidc.tf
  - id: infra-identity
    resource: git:3ec5d1e:deployments/infrastructure/identity.tf
  - id: infra-secrets
    resource: git:3ec5d1e:deployments/infrastructure/secrets.tf
  - id: haproxy
    resource: git:3ec5d1e:deployments/infrastructure/services/haproxy.hcl
  - id: ov-dash-deploy
    resource: git:30292e2
  - id: ov-dash-vault-chain
    resource: git:bafb562
---

# ov-dash, OpenViking's browser face

ov-dash serves `https://openviking.lab.orangecluster.nl`, the browser view of
OpenViking. OpenViking's own edge route is `openviking-api.lab`, and it has no
browser surface of its own
([ADR 0009](/decisions/0009-openviking-has-no-browser-surface.md)). The source
is not in this repository. The image is built and released from
`JasperHG90/openviking_extensions` and pinned as `ov_dash_image` in
`nomad_job.ov_dash` (`deployments/applications/services.tf`), today
`ghcr.io/jasperhg90/ov-dash:0.5.0`.

## Sign-in is three hops

1. The browser goes to Vault's `lab` provider and returns to `/auth/callback`
   with an ID token. Vault asks for the password and the second factor on
   its own page.
2. ov-dash posts that ID token to `auth/jwt-lab/login` (role `ov-dash`) and
   gets a Vault token for the person's entity.
3. With that token it reads `identity/oidc/token/openviking`, then revokes
   the login token. The minted identity token is what every later request to
   OpenViking carries.

Hop 3 exists because OpenViking pins one issuer and one audience
(`services/openviking/ov.conf.json`), and both belong to the identity-token
role. A provider ID token carries neither, so OpenViking would refuse it.
The trade leaves ov-dash holding a token shape the cluster already accepts,
and Hermes's path is untouched. Release 0.5.0 is the first that performs hop
2. 0.4.0 knew the `vault-oidc` mode but sent the ID token straight to
OpenViking.

## The pieces

**Infrastructure root** (`deployments/infrastructure/`), the chain:

- `oidc.tf`: `vault_identity_oidc_scope.openviking` (templates `ov_account`
  and `ov_user` into the provider token), `vault_identity_oidc_assignment.ov_dash`
  (the `openviking-user` and `developer` groups), `vault_identity_oidc_client.ov_dash`
  (confidential, on the shared `lab` key), its key registration, and its
  entry in `local.oidc_provider_client_ids`.
- `identity.tf`: `vault_jwt_auth_backend.lab` (mount `jwt-lab`),
  `vault_jwt_auth_backend_role.ov_dash`, and one entity alias per person
  (`ov_dash_operator`, `ov_dash_consumer`).
- `oidc.tf`: `vault_identity_oidc_role.openviking`, the role hop 3 mints from.
- `secrets.tf`: `vault_kv_secret_v2.ov_dash_oidc_client` at
  `default/ov-dash/oidc`, the client id and secret.
- `services/haproxy.hcl`: `backend ovdash` to 192.168.2.29:4182, with no
  `http-request auth`.

**Applications root** (`deployments/applications/`):

- `services/ov-dash.hcl`, `nomad_job.ov_dash` in `services.tf`.
- `secrets.tf`: `vault_kv_secret_v2.ov_dash_config`, the session-cookie key.
- `local.firewall_rules.ov_dash` in `services.tf`: 4182 from HAProxy only.
  OpenViking's own entry admits .29, so ov-dash reaches it on 1933 directly.

ov-dash needs no Vault role of its own. `vault {}` gets the default
`nomad-workloads` grant, which covers its two KV paths under
`default/ov-dash/`. The identity token is minted with the person's token, not
the workload's.

## Apply order

Infrastructure first, and the chain in ONE apply: the mount, the role, the
aliases, the client, the scope and the KV secret. A login against the mount
before its aliases exist makes Vault invent an entity and alias, and the
next apply then fails with "already exists". The applications job boots with
an empty `OIDC_CLIENT_ID` if the KV secret is missing. The step list is
`docs/how-to/roll-out-vault-login-mfa.md`, steps 3 and 4.

Values linked only by agreeing: `ov_dash_public_origin` in `services.tf` and
`local.ov_dash_redirect_url` in `oidc.tf`, and the literals `jwt-lab`,
`ov-dash` and `openviking` passed as `vault_jwt_mount`, `vault_jwt_role` and
`vault_oidc_role`.

## Four lifetimes

| Token | Lifetime | Set by |
|---|---|---|
| Provider ID token | 10 minutes | `id_token_ttl` on `vault_identity_oidc_client.ov_dash` |
| `jwt-lab` Vault token | 5 minutes, spent at once | `token_ttl` on `vault_jwt_auth_backend_role.ov_dash` |
| ov-dash session | 8 hours | `SESSION_TTL_SECONDS` in `ov-dash.hcl` |
| Minted OpenViking token | 30 days | `ttl` on `vault_identity_oidc_role.openviking` |

The ID token is short because the trade takes it alone, with no client secret
and no second factor, and for the operator the resulting token carries
`developer`. Ten minutes covers a slow redirect. The session should outlive
the ID token. `oidc.tf` calls that "EXPECTED, not measured" and says rollout
step 4 tests it by leaving a session idle past ten minutes. If sessions die
at ten minutes, `id_token_ttl` has to rise to the session length.

## MFA interplay

The TOTP enforcement names the userpass mount's accessor,
`vault_identity_mfa_login_enforcement.userpass` in `identity.tf`. The
password login behind Vault's provider page lands on userpass, so a person
meets the challenge once, at Vault. `jwt-lab` must stay outside the
enforcement: ov-dash cannot answer a challenge, and a challenge there would
break hop 2. Naming the operator entity instead challenged the `jwt-lab`
login too and stranded the operator there. That is why the enforcement
names the mount
([ADR 0011](/decisions/0011-login-mfa-enforcement-names-the-userpass-mount.md)).
The password form ov-dash used to have (`AUTH_MODE=vault-userpass`) cannot
coexist with Login MFA, which is why it was removed. Enrollment is an admin
step per person
([ADR 0010](/decisions/0010-vault-generates-each-totp-qr.md)) and has no page
on dash ([ADR 0012](/decisions/0012-no-mfa-enrollment-app-on-dash.md)). The
rollout handoff is [Two-factor auth on Vault logins](/proposals/vault-login-mfa.md).

## Constraints that shaped the job

- **One alloc.** Sessions live in process memory, so a second replica signs
  a person out whenever HAProxy switches instances, and a restart signs
  everyone out. Scaling needs a shared session store.
- **On orangepi4a, not beside OpenViking.** radxa had 598 MB free, and its
  stateful neighbors (driftwatch's baseline volume, OpenViking's workspace)
  are pinned there by single-node-writer volumes. ov-dash holds nothing on
  disk, so it moved. The cost is a LAN hop to 1933.
- **`memory = 512`, no `memory_max`.** Oversubscription is off, so `memory`
  is the cap. A folder download is zipped in process with fflate, and an
  OOM kill signs every session out.
- **`VAULT_ADDR` is the edge hostname.** The trade and the mint carry
  credentials, so they go over TLS even inside the cluster.
- **Two env templates, two files.** Two templates writing one destination
  leave the last one's variables and silently drop the other's.
- **`/health` answers without a credential**, so the Consul check reports
  the process, not whether Vault or OpenViking are reachable.

## History

`30292e2` deployed ov-dash with `AUTH_MODE=vault-userpass`: a password form
that signed the person into Vault itself. `bafb562` moved it to the Vault
chain. It is the dashboard the deprecated proposal
[Building our own OpenViking dashboard](/proposals/openviking-dashboard.md)
described, minus the server-side key that Vault identity tokens made
unnecessary.

## Related

- [The OpenViking service](/components/openviking-service.md)
- [Vault human identity](/components/vault-identity.md)
- [Vault's OIDC provider and its clients](/components/vault-oidc-provider.md)

- `docs/explanation/openviking-identity.md`
- `docs/reference/vault-login-mfa.md`
- `docs/how-to/verify-an-openviking-deployment.md`, step 4
