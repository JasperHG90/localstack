# F14 eval results

Everything the plan asked to be proven was proven, on the live cluster, with no
browser. An earlier revision of this file claimed two clauses were impossible
to test headlessly. That was false and a reviewer said so; the correction is
recorded at the bottom because the mistake is more instructive than the result.

All probe artifacts were removed. Final state: groups are `admin`, `developer`
and `oidc-smoke`; OIDC clients are `nomad` and `oidc-smoke`; the smoke
assignment carries exactly F2's original group id.

## Requirement 1 — the `admin` policy beats `default`

The claim under test is a **capability** claim, not a transcription one:
restating a path in a second policy unions capabilities, so `path "*"` stops
being shadowed. Measured with a negative control, since `default` grants
`update` on `sys/leases/lookup` but not `list`:

```
default only -> Error listing sys/leases/lookup
admin        -> Keys
                ----
                auth/
```

Both probe tokens were revoked. The transcription holds too: `vault policy read
admin` returns 19 `path` blocks, the `*` glob plus all 18 paths the live
`default` policy names. Three are not literal strings and survived the heredoc
verbatim: `{{identity.entity.id}}`, `{{identity.entity.name}}`, and
`identity/oidc/provider/+/authorize`, where `+` is a single-segment wildcard.

## Requirement 1 — the templated restatement also works

`sys/leases/lookup` proves the plain-path case. The two `{{identity.*}}` paths
go through a different Vault code path, so they were measured separately.
`default` grants `read` only on `identity/entity/id/{{identity.entity.id}}`, so
an update is the discriminating call. With an entity-backed token carrying
`identity_policies ['admin', 'developer']`:

```
POST /v1/identity/entity/id/351f302a-...  -> HTTP 200
```

The templated restatement is therefore live, not just syntactically present.

**That probe cost two applies to clean up, and the reason is worth recording.**
A Vault entity metadata write **replaces the whole map**, exactly as a group
membership write does. `auth_userpass.tf:38-44` declares
`metadata = { managed_by = "terraform", kind = "human" }` on this entity, so the
probe evicted both keys, and clearing the probe key afterwards evicted them
again. Two evictions, and they ended differently. The first was repaired by the
very next apply, which is where the unexplained "2 changed" in Requirement 2's
write-path test below came from. The second sat as live drift until a reviewer
ran a plan and found it, and it took a further apply (`0 added, 1 changed`) to
repair. **Terraform healing the first one is what made the second easy to
miss.** `terraform plan` now reports no changes.

The lesson is narrower than "writes clobber things", and this file measures
both halves. Fields omitted from a write **are** preserved: writing only
`member_entity_ids` left `policies` and `type` intact, recorded below. What is
not preserved is the rest of a **map-valued field**: setting one key of
`metadata` drops every other key, because the map is replaced wholesale. Fields
merge; maps do not. Membership is the same shape, which is why the runbook says
joining means naming the existing members too.

## Requirement 2 — `external_member_entity_ids` behaves as claimed

```
member added by hand       -> [351f302a-...]
terraform plan             -> No changes. Your infrastructure matches...
terraform apply            -> 0 added, 0 changed, 0 destroyed
member re-read after apply -> [351f302a-...]
```

**That apply was a no-op, which is the weaker test**, and a reviewer was right
to say so: it proves the provider's *diff* ignores the field, not that the
write path preserves it. Re-run with a real change to the group — adding a
`metadata` description, so Terraform actually writes it — while a hand-added
member was present:

```
member before apply -> [351f302a-...]
terraform apply     -> 0 added, 2 changed, 0 destroyed
                       (the second resource was the operator entity, unrelated
                        to this test: the templated-restatement probe above had
                        clobbered its metadata and this apply repaired it)
member after apply  -> [351f302a-...]
```

Terraform owns the group, not its membership, through a write and not merely
through a skipped diff. The test member was removed; `admin` is empty.

## Requirement 8 — the app-user tiers do the opposite, deliberately

Same test against a tier that does **not** set the flag:

```
member added by hand -> [351f302a-...]
terraform plan       -> ~ member_entity_ids ... Plan: 0 to add, 1 to change
terraform apply      -> 0 added, 1 changed, 0 destroyed
member after apply   -> []
```

A hand-added tier member shows as a diff and is reverted. That is the right
default for a list that should be reviewable, and `admin` is the exception.

## Requirements 3-6 — the scaffold wires end to end and is reversible

One map entry created the group, its id flowed into the smoke assignment, and
removing the entry destroyed the group and restored the assignment exactly:

```
after adding   -> group_ids [a41fc0a5-... e86ec229-...]
after removing -> group_ids [e86ec229-...]
```

The throwaway group carried `policies: []` and `member_entity_ids: []`.

**The concat is safe with an empty map.** The first plan reported `2 to add, 0
to change`: the two `admin` resources, and no change to the smoke assignment,
because `concat([smoke.id], [])` equals what is live. A replacement would have
written `group_ids = []` and broken F2's client.

## Requirement 9 — the decode

Run headlessly. `vault login -method=userpass` gives an entity-backed token,
and `identity/oidc/provider/lab/authorize` is an ordinary API endpoint that
takes that token and returns the code in the response body, so no redirect_uri
has to be served.

With a throwaway tier created through the scaffold and the operator entity in
it, the decoded `id_token` payload carried:

```
groups: ['app-probe-readers', 'oidc-smoke', 'developer']
is a list: True
```

A real JSON array, not the string `"null"` a malformed scope template renders
while still issuing a valid token, and the scaffold-created tier is in it.

## Requirement 9 — branch 3, that `allow_all` admits a non-member

Proven, with a control that isolates the variable. A scratch entity in **no**
group, one authorize request, two clients differing only in their assignment:

```
smoke client (assignment names a group the entity is not in)
  -> {"error":"access_denied",
      "error_description":"identity entity not authorized by client assignment"}

throwaway client with assignments = ["allow_all"]
  -> {"code":"lL5xJGnyuLHnzjMIvQN7utERGk69W2Dz"}
```

So `allow_all` is doing the admitting, not something incidental. The scratch
identity's token was revoked before its entity and user were deleted, and the
throwaway client, its key registration and its provider entry were removed.

## Found while implementing, and documented

**`identity/group-member-entity-ids` does not exist on this Vault.** It returns
`unsupported path`, which reads like a permissions problem. Membership is
written through `identity/group/name/<name>`.

**Fields omitted from a group write are preserved.** An earlier revision of
`docs/cluster-roles.md` told operators to restate `policies` and `type` "or the
write clears them". Measured and false: writing only `member_entity_ids` left
`policies ['admin']` and `type internal` intact. What *is* replaced is the
membership list itself, so joining means naming the existing members too. The
runbook now says that.

## The correction worth keeping

This file previously filed Requirement 9's decode and the branch-3 clause under
"Not proven here: needs a browser". Both were then proven headlessly in about
ten minutes. The premise was never tested — the authorize endpoint was assumed
to be browser-only because it is reached through a browser in normal use, and
the assumption was written down as a constraint. An admission of ignorance
reads as honest, which is exactly what makes it dangerous when it is standing
in for a measurement nobody attempted.
