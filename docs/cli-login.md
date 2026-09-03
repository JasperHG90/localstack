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
[cli-deps.md](./cli-deps.md).

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
is allowed, since nothing leaves the host. Once N4 moves `.devcontainer/.env`
to the edge hostnames, the bare `localstack login` will work and this flag
becomes unnecessary.

## Getting the password, once

The `operator` password lives in Vault at `secret/default/vault/operator`,
and reading it needs a Vault token, which is what login produces. So the CLI
cannot fetch the password it needs to log in. Get it out of band, once, with
a token that already works:

```sh
vault kv get -field=password secret/default/vault/operator
```

Keep it in your password manager. `localstack login` prompts for it and never
stores it.

## What you get

Four credentials in one `0600` file at
`${XDG_CONFIG_HOME:-$HOME/.config}/localstack/session.json`:

| Credential | Lives for | Refresh |
| --- | --- | --- |
| Vault session token | weeks | renewed in place |
| Nomad `deploy` token | 30 minutes, capped at 1 hour | re-brokered |
| Nomad `manage` token | 30 minutes, capped at 1 hour | re-brokered |
| Consul `deploy` token | 30 minutes, capped at 1 hour | re-brokered |

`deploy` is scoped for Terraform's own job submission; `manage` is a full
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

Removing the injected token entirely is F8's job, not this CLI's.

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

You have four credentials out there and revoking the Vault token cascades to
the other three. In order of preference:

**1. `localstack logout`**, if you still have the session. One command, ends
all four.

**2. Revoke by accessor**, if you do not. This needs
`auth/token/revoke-accessor`, which `developer` does not grant. **Join
`admin`** — it exists for exactly this, and membership survives a
`terraform apply` running mid-incident, because `identity.tf` sets
`external_member_entity_ids = true` on the group.

```sh
# 1. READ the membership first: the write REPLACES the list, it does not append.
#    On a fresh cluster `admin` is empty and this prints nothing. Then pass
#    your id alone below, with no leading comma.
vault read -field=member_entity_ids -format=json identity/group/name/admin \
  | python3 -c 'import sys,json; print(",".join(json.load(sys.stdin)))'

# your own entity id
vault read -field=entity_id auth/token/lookup-self

# 2. join
vault write identity/group/name/admin member_entity_ids="<current>,<you>"

# 3. find the stolen session and revoke it
vault list auth/token/accessors
vault token revoke -accessor <accessor>

# 4. leave. `member_entity_ids=""` empties the group outright, which is only
#    correct if you were its last member.
vault write identity/group/name/admin member_entity_ids="<current-without-you>"
```

**Every live session at `auth/userpass/login/operator` looks identical** —
same display name, same entity, same policies. They differ only on
`creation_time`, which does not identify which one was lost. There is no
audit device recording when a session started. So revoke every accessor at
that path except the one you are using, then log in again.

**Leaving `admin` is a habit, not a gate.** Joining it is invisible to every
`terraform plan`, so nothing will remind you. See `docs/cluster-roles.md`.

**Fallback if you cannot join `admin`:** write yourself the accessor policy by
hand and attach it to a throwaway entity, never to the `developer` group. It
works without root, since `developer` grants `sys/policies/acl/*` and
`identity/*`, but it is six more commands, its teardown order matters, and it
leaves an orphan near-root policy nothing cleans up. `docs/vault-human-auth.md`
has the full procedure.

**Revoking is not instant, and during an outage it may not happen at all.**
Nomad runs `ACL.TokenTTL: 30s` and Consul `ACLTokenTTL: 30s`, both defaults,
both read off the live agents. An agent honors a deleted token until its
cache expires. Consul also runs `ACLDownPolicy: extend-cache`, so while the
ACL servers are unreachable it keeps honoring that token for as long as that
lasts. That is exactly the condition an incident tends to create.

**Revocation does not un-disclose what was read.** Treat anything the session
could reach as exposed.

This page covers the fast path. `docs/vault-human-auth.md` has the rest: the
composite closer for when you hold the Nomad and Consul management tokens, the
teardown order for a throwaway entity, and why rotating the `operator`
password does not end a live session.

## Preconditions

The `userpass` backend and the `operator` entity come from F2. The policy that
lets your session read `nomad/creds/deploy`, `nomad/creds/manage` and
`consul/creds/deploy` comes from F11, which binds `developer` through an
identity group. Both are applied.

If brokering fails with a 403, the message names the path that was denied and
the policies your token actually carries. It reads `identity_policies`, not
`policies` — a group-granted policy lands in the former, and a message
reporting the latter would tell you that you have no grants when you do.
