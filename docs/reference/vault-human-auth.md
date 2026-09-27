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

All of it lives in `deployments/infrastructure/`:

| File | Contents |
| --- | --- |
| `identity.tf` | The `userpass` auth mount, the operator user, the identity entity and alias that bind a login to an identity, and the `developer`, `admin` and app-user groups. The entity's `email` metadata is what the `email` scope reads |
| `oidc.tf` | The OIDC signing key, the shared `groups`, `email` and `openviking` scopes, the provider, one throwaway smoke-test client, and the consumer clients added since (nomad, memex, oauth2-proxy, grafana, openviking, ov-dash) |
| `secrets.tf` | Two KV2 writes: the operator password, and the smoke client's credentials |

Two secrets land in KV2:

- `secret/default/vault/operator`: the operator's username and password.
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

**"Brokered Nomad tokens" now includes a full management token.** It used to
mean only the deliberately narrow `deploy` role. Since G2 the policy also
grants `nomad/creds/manage`, which mints a global Nomad **management** token:
anything in Nomad, including minting more Nomad tokens. This is not a new
ceiling — a holder could always overwrite `nomad/role/deploy` to
`type = "management"` and read the creds they already had — but that route
clobbers a Terraform-managed role and shows as drift on the next plan. This one
leaves no trace. What changed is detectability, not privilege.

**Signing in to the Nomad UI gives you root over the cluster's data.** The
binding rule maps this group to Nomad's `developer` ACL policy, which grants
`alloc-exec` and `alloc-node-exec` on the `default` namespace **and**
`host_volume "*" { policy = "write" }`. Combined with `submit-job`, that means
a signed-in developer can attach any host volume read-write and exec into it as
root. Measured: `nomad alloc exec` into a running container returns
`uid=0(root)`, and the attachable volumes include `postgres`, `minio_data`,
`grafana_data`, `loki_data`, `memex_data`, `hermes_data`, `nats_data`,
`prometheus_data` and `acme_lego_state` — the Postgres data directory, the
MinIO object store and the ACME account key among them.

None of that is new either; the policy predates the sign-in button and is
Ansible's (`bootstrap/roles/nomad_server/files/nomad_developer_policy.hcl`).
What G2 changed is the route: reaching it used to require someone handing you a
token, and now it requires logging in. Narrowing it is a change in Ansible, not
here.

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
operator's is set from `vault_operator_email` (`identity.tf`,
`variables.tf`).

Whether your service needs it depends on the service, not on a rule. Grafana
does. oauth2-proxy does not: it identifies a user from `sub`
(`OAUTH2_PROXY_OIDC_EMAIL_CLAIM="sub"`), so dash logs people in with no
`email` scope at all. Phoenix will need it, for the same reason Grafana does.

Not every service reads the `groups` claim either. MinIO tiers on
`role_policy`, which bypasses the claim and gates on the per-client assignment
instead. Decide which mechanism
your service uses and say so in its ticket, rather than assuming the claim is
read everywhere.
