# How to revoke a lost or stolen session

## Introduction

End a `localstack` session you no longer control, for example after a laptop
is lost or stolen. A session holds a Vault token and three brokered leases
(Nomad `deploy`, Nomad `manage`, Consul `deploy`), and this ends all four:
you have [four credentials](../reference/cli-login.md#what-you-get) out there
and revoking the Vault token cascades to the other three.

Try step 1 first. Steps 3 to 5 are for when you no longer have the session
file or its token. Removing the holder from a group or disabling their entity
does not end the session, and
[Cluster roles](../explanation/cluster-roles.md#why-removing-someone-does-not-end-their-session)
says why. The other route, cutting the mint path and deleting the brokered
tokens directly, is
[How to delete a lost session's Nomad and Consul tokens](delete-a-lost-sessions-brokered-tokens.md).

## Prerequisites

- Your Vault password, and a working `localstack login` session or another
  Vault token, see [`localstack login`](../reference/cli-login.md).
- For steps 3 to 5, rights to write `identity/group/name/admin`, which
  `developer` grants through `identity/*`.

## Directions

### Step 1: Run `localstack logout`

**If a session is lost, do this first: `localstack logout`.** It calls
`auth/token/revoke-self`, which `default` grants, and revoking the parent
cascades to all three brokered leases (Nomad `deploy`, Nomad `manage`, Consul
`deploy`). It ends all four credentials in one command, needs no root, and
works only while you still have the file — so it is the first thing to try
and the first thing to lose.

**`localstack logout` ships with `D2` and is the way to do this.** It revokes
the Vault token, and with it the three brokered leases (Nomad `deploy`,
Nomad `manage`, Consul `deploy`), then deletes the session file and
`~/.vault-token`. See [`localstack login`](../reference/cli-login.md). If this
worked, go to step 6.

### Step 2: Revoke the token by hand, if you have it but not the session file

If you have the lost session's token but not its session file, the equivalent
is:

```sh
VAULT_TOKEN=<the lost session's token> vault token revoke -self
```

**Set `VAULT_TOKEN` on that line and nowhere else.** `-self` revokes whatever
`VAULT_TOKEN` currently holds, and in this devcontainer that is the **root
token** — running it bare would revoke root and take the cluster's admin
credential with it. Deleting the placeholder instead of filling it is safe:
an empty `VAULT_TOKEN` returns 403 rather than falling back to
`~/.vault-token` (measured). Same endpoint and same cascade as `logout` once the token
is right.

### Step 3: Get the right to revoke by accessor

**Revoke by accessor**, if you do not have the session. Revoking the parent
cascades to the child leases — one action, all four credentials, and it
needs only your Vault password. But it needs `auth/token/revoke-accessor`,
which `developer` does not grant.

**Join `admin`** — it exists for exactly this. It carries `path "*"` with
`sudo`, so it covers all three accessor paths with no policy to write and
none to clean up, and its membership survives a `terraform apply` running
mid-incident, because `identity.tf` sets `external_member_entity_ids = true`
on the group. Both the join and leave commands, including the empty-group
case, are also in
[How to join and leave the admin group](join-and-leave-the-admin-group.md).

```sh
# READ the membership first: the write REPLACES the list, it does not append.
# On a fresh cluster `admin` is empty and this prints nothing. Then pass
# your id alone below, with no leading comma.
vault read -field=member_entity_ids -format=json identity/group/name/admin \
  | python3 -c 'import sys,json; print(",".join(json.load(sys.stdin)))'

# your own entity id
vault read -field=entity_id auth/token/lookup-self

# join
vault write identity/group/name/admin member_entity_ids="<current>,<you>"
```

**Fallback if you cannot join `admin`:** grant yourself the accessor policy
by hand. It works without root, since `developer` grants
`sys/policies/acl/*` and `identity/*`, but it is six more commands, its
teardown order matters, and it leaves an orphan near-root policy nothing
cleans up. **Do that on a throwaway entity, never on the `developer`
group.** Group policies resolve per request and the thief is also a
`developer`: granting it to the group hands them `revoke-accessor` over
every token in the cluster, including every workload token on the cluster.
That turns a stolen laptop into an outage.

The policy needs `sudo` on the list path, or its first command fails:

```hcl
path "auth/token/accessors"       { capabilities = ["list", "sudo"] }
path "auth/token/lookup-accessor" { capabilities = ["update"] }
path "auth/token/revoke-accessor" { capabilities = ["update"] }
```

Clean up the throwaway policy yourself, because Terraform will not: a policy
attached to a throwaway entity is invisible to it, so nothing removes the
orphan when the incident ends. An earlier version of this page said the
opposite — that a `terraform apply` would strip the grant mid-incident,
citing the `developer` policy in `identity.tf`. That is true only if you attach it
to the `developer` **group**, which the paragraph above forbids.

### Step 4: Revoke every accessor at the operator path except yours

You cannot pick the target by path. Every live session at
`auth/userpass/login/operator` shares the same display name, entity and
policy list, and they differ only on `creation_time` — which does not
identify which one was lost, since sessions minted seconds apart are common
and no audit device records when the lost one started. Each carries
`developer` for another month. **So revoke every accessor at that path
except the one you are using now**, then log in again. `localstack whoami`
prints your own accessor.

Do not trust a count of them written here: it drifts within a day, because
every login adds one. Read it when you need it:

```sh
# find the stolen session and revoke it
vault list auth/token/accessors
vault token revoke -accessor <accessor>
```

### Step 5: Leave admin, or tear down the throwaway

```sh
# leave. `member_entity_ids=""` empties the group outright, which is only
# correct if you were its last member.
vault write identity/group/name/admin member_entity_ids="<current-without-you>"
```

**Leaving `admin` is a habit, not a gate.** Joining it is invisible to every
`terraform plan`, so nothing will remind you. See
[Cluster roles](../reference/cluster-roles.md).

**Tearing the throwaway down: revoke its token by accessor FIRST, then
delete the entity, the alias, the user and the policy.** Deleting the user
and entity does not revoke what they minted. Measured on this cluster: a
scratch `userpass` token survived its own user and entity by 30.6 days. It
had decayed to `default` because the entity was gone, so it was litter — but
a throwaway torn down the same way while its token still carried the
escalation policy would have left that policy live and unattached to
anything you could find by listing users.

### Step 6: Treat what the session could reach as exposed

**Revoking is not instant, and during an outage it may not happen at all.**
Nomad runs `ACL.TokenTTL: 30s` and Consul `ACLTokenTTL: 30s`, both defaults,
both read off the live agents. An agent honors a deleted token until its
cache expires. Consul also runs `ACLDownPolicy: extend-cache`, so while the
ACL servers are unreachable it keeps honoring that token for as long as that
lasts. That is exactly the condition an incident tends to create.

**Revocation does not un-disclose what was read.** Treat anything the session
could reach as exposed.

## Additional resources

- [`localstack login` reference](../reference/cli-login.md), including what
  `logout` revokes
- [Cluster roles (explanation)](../explanation/cluster-roles.md): why the
  roles are not a boundary, and why group removal does not end a session.
- [How to delete a lost session's Nomad and Consul tokens](delete-a-lost-sessions-brokered-tokens.md)
- [How to join and leave the admin group](join-and-leave-the-admin-group.md)
