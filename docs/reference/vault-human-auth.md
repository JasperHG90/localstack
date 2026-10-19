---
description: Where human Vault credentials are, which OIDC issuer a service points at, what the developer group grants, and the claims a service can read.
stale_after: 2027-01-19
sources:
  - resource: deployments/infrastructure/identity.tf
  - resource: deployments/infrastructure/oidc.tf
  - resource: deployments/infrastructure/secrets.tf
  - resource: bootstrap/roles/nomad_server/files/nomad_developer_policy.hcl
---

# Human login to Vault, and the OIDC issuer it feeds

Vault is the OIDC provider for humans on this cluster. This page covers where
the credentials live, the issuer a service points at, what the `developer`
group grants, and the claims a service can read. Machine identity is a
separate system: Nomad issues Workload Identity JWTs and Vault trusts them
through the `jwt-nomad` auth mount. Nothing here touches that.

How to log in is [How to log in to Vault](../how-to/log-in-to-vault.md). How
to add a service that logs people in is
[How to add a service that logs people in through Vault](../how-to/add-a-vault-oidc-client.md).

## What Terraform creates

All of it is in `deployments/infrastructure/`:

| File | Contents |
| --- | --- |
| `deployments/infrastructure/identity.tf` | The `userpass` auth mount, the operator user, the identity entity and alias that bind a login to an identity, the TOTP login MFA, the OpenViking consumer users and their `openviking-user` group, the `jwt-lab` mount ov-dash signs people in through, and the `developer`, `admin` and app-user groups. The entity's `email` metadata is what the `email` scope reads |
| `deployments/infrastructure/oidc.tf` | The OIDC signing key, the shared `groups`, `email` and `openviking` scopes, the provider, one throwaway smoke-test client, the consumer clients (nomad, memex, oauth2-proxy, grafana, ov-dash, hermes-dashboard), and the identity-token roles OpenViking verifies |
| `deployments/infrastructure/secrets.tf` | Among its KV2 writes, the human-login ones: the operator password, each OpenViking consumer's password, the smoke client's credentials, and the OIDC client secrets for Grafana, oauth2-proxy (and its registry-ui copy) and ov-dash |

These secrets land in KV2:

- `secret/default/vault/operator`: the operator's username and password.
- `secret/default/vault/<username>`: each OpenViking consumer's username and
  password.
- `secret/default/vault/oidc-smoke`: the smoke-test client's `client_id`,
  `client_secret`, and the issuer URL.

## The issuer, and which one to point at

The provider advertises:

```
https://vault.lab.orangecluster.nl/v1/identity/oidc/provider/lab
```

**Point services at that provider, named `lab`. Not at `default`.** Vault
ships a built-in provider called `default` whose `allowed_client_ids` is
`["*"]` and whose issuer is the raw backend address over plain HTTP. A service
aimed at `default` will appear to work while bypassing every scoping decision
made here, which makes it a quiet way to lose the gate.

Discovery and keys, if you need to check them by hand:

```
curl -s https://vault.lab.orangecluster.nl/v1/identity/oidc/provider/lab/.well-known/openid-configuration
```

## What the operator can do: the `developer` group

Logging in gives you the `developer` policy, carried by the
`developer` identity group (`deployments/infrastructure/identity.tf`).
It covers everything a person does here: both Terraform roots, brokered Nomad
and Consul tokens, creating users and groups, and every secret under
`default/`.

**Two of those are bigger than they sound. Read this before adding anyone to
the group.**

**"Brokered Nomad tokens" includes a full management token.** Besides the
deliberately narrow `deploy` role, the policy grants `nomad/creds/manage`,
which mints a global Nomad **management** token: anything in Nomad, including
minting more Nomad tokens. `localstack login` brokers it for
`localstack monitor`. It raises no ceiling. A holder could already overwrite
`nomad/role/deploy` to `type = "management"` and read the creds they had, but
that route clobbers a Terraform-managed role and shows as drift on the next
plan. Reading `manage` leaves no trace, so the difference is detectability,
not privilege.

**Signing in to the Nomad UI gives you root over the cluster's data.** The
binding rule maps this group to Nomad's `developer` ACL policy, which grants
`alloc-exec` and `alloc-node-exec` on the `default` namespace **and**
`host_volume "*" { policy = "write" }`. Combined with `submit-job`, that means
a signed-in developer can attach any host volume read-write and exec into it as
root. Measured: `nomad alloc exec` into a running container returns
`uid=0(root)`, and every host volume in the cluster is attachable:
`postgres`, `minio_data` and `acme_lego_state` among them, which hold the
Postgres data directory, the MinIO object store and the ACME account key.

The policy is Ansible's
(`bootstrap/roles/nomad_server/files/nomad_developer_policy.hcl`), and the
Nomad UI's sign-in button is only a shorter route to it: logging in is enough,
where before someone had to hand you a token. Narrowing it is a change in
Ansible, not here.

**Check `identity_policies`, not `policies`.** The group carries the policy, so
a fresh login reports:

```
token_policies     ["default"]
identity_policies  ["developer"]
```

Anything asserting `developer` in `policies` will report that you have no
grants when you do.

Why the group is not a security boundary, and what ending a lost session
takes, is [Cluster roles](../explanation/cluster-roles.md). Ending one is
[How to revoke a lost or stolen session](../how-to/revoke-a-lost-or-stolen-session.md).

## The claims, and which one your service reads

The shared `groups` scope emits the entity's Vault group names. oauth2-proxy
consumes that through `--oidc-groups-claim`.

The `email` scope emits the entity's `email` metadata key. Grafana requires
it: its generic OAuth client refuses a login whose resolved email is empty and
offers no setting to turn that off. An entity with no `email` key yields an
empty string, not an error, and the login fails at the callback. **Every human
entity needs that metadata key**, or its owner cannot sign in to Grafana. The
operator's is set from `vault_operator_email`
(`deployments/infrastructure/identity.tf`,
`deployments/infrastructure/variables.tf`).

Whether your service needs it depends on the service, not on a rule. Grafana
does. oauth2-proxy does not: it identifies a user from `sub`
(`OAUTH2_PROXY_OIDC_EMAIL_CLAIM="sub"`), so dash logs people in with no
`email` scope at all.

Not every service reads the `groups` claim either. A client's assignment
decides who may log in at all, before any claim is read: the `oauth2-proxy`,
`grafana` and `hermes-dashboard` clients carry the `operators` assignment, so
Vault refuses anyone outside `developer` and `admin`. Decide which mechanism
your service uses rather than assuming the claim is read everywhere.
