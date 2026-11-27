---
description: What `localstack login` brokers, where it keeps the session, and how `env`, `token`, `whoami`, `config` and `logout` use it.
stale_after: 2027-01-19
sources:
  - resource: cli/src/localstack_cli/commands/login.py
  - resource: cli/src/localstack_cli/commands/logout.py
  - resource: cli/src/localstack_cli/commands/env.py
  - resource: cli/src/localstack_cli/commands/token.py
  - resource: cli/src/localstack_cli/auth/sts.py
  - resource: cli/src/localstack_cli/commands/whoami.py
  - resource: cli/src/localstack_cli/commands/config.py
  - resource: cli/src/localstack_cli/auth/vault.py
  - resource: cli/src/localstack_cli/auth/broker.py
  - resource: cli/src/localstack_cli/auth/vault_token_file.py
  - resource: cli/src/localstack_cli/auth/session.py
  - resource: deployments/infrastructure/identity.tf
  - resource: deployments/infrastructure/machine_roles.tf
---

# `localstack login`

One command authenticates you to Vault and brokers your Nomad and Consul
tokens from that session. No per-service login, and no static god-mode token
in a file.

```sh
localstack login --vault-addr https://vault.lab.orangecluster.nl
eval "$(localstack env)"
```

The second line is not optional. `login` brokers the credentials, and
`eval "$(localstack env)"` is what puts them in your shell.

The PATH shims from `localstack deps --with-shims` cover a bare `nomad`,
`consul` or `vault` only. Everything else that reads these variables, the
`just` recipes around Terraform above all, still needs the `eval`. See
[cli-deps.md](cli-deps.md).

**`--vault-addr` is not optional yet either.** The default `VAULT_ADDR` in
this devcontainer is `http://192.168.2.30:8200`, and Vault's own listener runs
with `tls_disable: true`, so a password sent there crosses the network in the
clear. `login` refuses that address before it prompts, and names the TLS edge:

```
error: refusing to send a password to http://192.168.2.30:8200 in the clear.
Use the TLS edge: --vault-addr https://vault.lab.orangecluster.nl
Or pass --insecure if you really mean to.
```

`--insecure` is the only way past and it warns on stderr. Loopback `http://`
is allowed, since nothing leaves the host. Once `VAULT_ADDR` in
`.devcontainer/.env` names the edge hostname, a bare `localstack login` works
and the flag is no longer needed.

## Getting the password, once

See [How to get the operator password](../how-to/get-the-operator-password.md).

## The second factor

The `userpass` backend enforces TOTP login MFA. After the password, `login`
asks for `TOTP passcode for <addr>:`, hidden like the password prompt. If Vault
offers more than one MFA method, `login` says so and uses the first.

A login that returns neither a token nor an MFA challenge fails with a message
naming three causes: a wrong username, a disabled `userpass` backend, or an
MFA enforcement covering an entity with no second factor enrolled. Vault
answers all three the same way. See [Vault login MFA](vault-login-mfa.md).

A failed login leaves your existing session alone. A successful one saves the
new session first and then revokes the one it replaced.

## What you get

Four credentials in one `0600` file at
`${XDG_CONFIG_HOME:-$HOME/.config}/localstack/session.json`. `login` also
writes the Vault token to `~/.vault-token`, the file the stock `vault` CLI
reads.

| Credential | Lives for | Refresh |
| --- | --- | --- |
| Vault session token | weeks | renewed in place |
| Nomad `deploy` token | 30 minutes, capped at 1 hour | re-brokered |
| Nomad `manage` token | 30 minutes, capped at 1 hour | re-brokered |
| Consul `deploy` token | 30 minutes, capped at 1 hour | re-brokered |

`deploy` is scoped for Terraform's own job submission. `manage` is a full
Nomad management token, brokered only so `status`, `service` and `monitor`
can read `list-jobs` and node state that `deploy` withholds. It is never
exported to your shell: `eval "$(localstack env)"` and `localstack token`
only ever hand out `deploy`.

The three brokered leases are re-brokered rather than renewed, because they
cap at `max_ttl 3600`: renewing one buys a single extra window and then fails
anyway. Any command needing them refreshes them first, so you do not manage
this.

`localstack whoami` reports who you are, the accessors, and how long each has
left. It never prints a token value. The policies it shows are the union
Vault resolves, so a policy granted through an identity group (which is how
`developer` reaches you) appears there rather than being hidden behind
`default`.

`localstack config` prints the resolved addresses, the edge domain and the
session's non-secret fields. It is the command to paste into an issue: no
token, no accessor, no password in either `--format text` or `--format json`.

## You are probably still root, and the CLI will say so

The devcontainer injects `VAULT_TOKEN` into every shell
(`.devcontainer/devcontainer.json`, `.devcontainer/.env`), and that variable
**outranks** `~/.vault-token`. So after `localstack login`, a bare `vault`
command still runs as the injected root token, not as you.

`login`, `whoami` and `logout` all print a warning to stderr when that is the
case, naming the policies the environment's token carries. Two ways out:

- `eval "$(localstack env)"` in this shell, which overwrites `VAULT_TOKEN`
  with the session token, or
- the `vault` shim on PATH, which `localstack deps --with-shims` installs
  and the devcontainer installs for you.

The CLI does not remove the injected token. It comes from `VAULT_TOKEN` in
`.devcontainer/.env`, which the devcontainer loads with `--env-file`.

## `env` emits both Consul spellings

`localstack env` sets `CONSUL_HTTP_TOKEN` **and** `CONSUL_TOKEN` to the same
value. The `consul` binary reads only the first. The second matters because
this repo's terraform recipes bridge `CONSUL_HTTP_TOKEN=${CONSUL_TOKEN}` by
hand, so a stale `CONSUL_TOKEN` left in your shell would silently overwrite a
fresh token inside every `just` recipe.

## `token` is for scripts

```sh
localstack token nomad
```

Prints the token and nothing else, refreshing it first if stale. On any
failure it exits non-zero with **empty** stdout. That contract is what makes
the PATH shims safe: they fall through to the unmodified binary when this
command fails, and a failure that printed an error message on stdout would
be exported as the token.

```sh
eval "$(localstack token s3 local-ov-sync)"
```

`s3 ROLE` is the one service the shims never call. It reads
`identity/oidc/token/ROLE` with the session's Vault token, swaps it at
SeaweedFS's STS for `arn:aws:iam::role/ROLE`, and prints three `export` lines:
`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` and `AWS_SESSION_TOKEN`. The
credentials last 15 minutes, and stderr says when they expire. Vault's ACL
decides which roles your login may mint. `--endpoint` overrides the STS
address, `https://s3.lab.orangecluster.nl` by default. A failure, or no role,
exits non-zero with empty stdout, as for the other services.

## `logout` revokes, it does not just forget

```sh
localstack logout
```

Calls `auth/token/revoke-self` first, then deletes the session file and
`~/.vault-token`. Revoking the Vault token revokes the leases it created, so
every credential dies together. Deleting the file alone would leave live
tokens on the cluster for up to an hour.

If revocation fails, the files still go and the accessors print to stderr so
you can revoke them by hand.

## If a session is stolen

Follow [How to revoke a lost or stolen session](../how-to/revoke-a-lost-or-stolen-session.md).

## Preconditions

The `userpass` backend and the `operator` entity are defined in
`deployments/infrastructure/identity.tf`. The `developer` policy, in the same
file, lets your session read `nomad/creds/deploy`, `nomad/creds/manage` and
`consul/creds/deploy`. It reaches you through the `developer` identity group.
The roles it reads are in `deployments/infrastructure/machine_roles.tf`.

If brokering fails with a 403, the message names the path that was denied and
the policies your token actually carries. It reads `identity_policies`, not
`policies`. A group-granted policy lands in the former, and a message
reporting the latter would tell you that you have no grants when you do.
