---
verdict: pass-with-required-fixes
plan: fe6c207bbf8e803cd5c0c7629bf4bf068b94580d37245ec2b016e8dfc7a3dddc
---

# Plan verdict — F14-foundation-role-taxonomy (pass `plan-validator`, third review)

Fingerprint verified locally: `sha256sum .loop/plans/F14-foundation-role-taxonomy.md`
returns `fe6c207bbf8e803cd5c0c7629bf4bf068b94580d37245ec2b016e8dfc7a3dddc`,
matching the briefing.

Method: a throwaway `vault server -dev` on Vault 2.0.3 at `127.0.0.1:8299`,
driven by the repo's pinned `hashicorp/vault 5.3.0` provider binary through a
scratchpad filesystem mirror. No live cluster call. All scratch resources
destroyed (`Destroy complete! Resources: 4 destroyed`), the dev server is down
(`/v1/sys/health` on 8299 no longer answers), and both F14 files are untouched
by me (`git status` shows them still `??`). No token value appears in this file.

**`~/.vault-token` was overwritten twice, as you expected.** Once by
`vault server -dev` on start, then again by two `vault login -method=userpass`
calls I made against that dev server to measure whether row 1's probe needs a
group member. It now holds a 95-byte token for a server that no longer exists.
No live credential was involved and nothing leaked, but any `vault` CLI call
relying on that file will now fail.

## Premise verdict: PARTIALLY SOUND — the plan file is clean, the eval is not

I cannot say it is clean. **The plan itself now is**: every load-bearing claim
in `.loop/plans/F14-foundation-role-taxonomy.md` holds under measurement, all
three framings you corrected are right, and the fingerprint needs no change.
The remaining defects are all in `.loop/evals/F14-foundation-role-taxonomy.md`,
and the worst of them is that **row 10's removal command does not work**. Run
verbatim it returns HTTP 500 and leaves the member in place, so the one step
guarding the failure this plan ranks second-worst is the step that fails.

Answering your four questions in order.

### 1. Is `null` versus `[]` stated correctly and consistently? YES

And the distinction is a genuine discriminator, which I had not proven last
pass. I built the pristine case for both group kinds on the same server:

| Group, freshly applied, never hand-written | `member_entity_ids` |
|---|---|
| flagged (`external_member_entity_ids = true`) | `null` |
| unflagged scaffold group (`policies = []`, no member attribute) | `[]` |

Raw API confirms it is not CLI formatting: `GET /v1/identity/group/name/...`
returns the key present with value `[]` for the unflagged group. So row 3's
sentence "An unflagged group returns `[]`, so a scorer asserting `[]` fails a
correct build and passes a broken one" is exactly right, and the substance of
fix 1 is sound.

Consistency across the other membership sites also holds. Plan line 34's
"the next apply reverts it to `[]`" is about the unflagged default and is
correct: I hand-added a member to the `for_each` scaffold group and the apply
returned it to `[]`. Row 10's scorer hedges to "empty or null", which is the
right hedge. Requirement 8's `~ member_entity_ids / 1 to change` is the literal
tool output.

One stale spot: the eval's own Definition of Done (eval line 3) still says
"`admin` exists as a policy and **an empty group**", the wording you replaced in
the plan's DoD. Minor, but it is the last place carrying the old framing.

### 2. Row 10's hand-removal: the command shape is WRONG

Measured verbatim against a Terraform-declared flagged group:

```
$ vault write identity/group/name/admin member_entity_ids='[]'
Code: 500. Errors:
* 1 error occurred:
	* invalid entity ID "[]"
exit=2
   -> members: ["be8bb2c5-..."]   # still there
```

The Vault CLI does not JSON-parse a `k=v` value. `'[]'` arrives as the literal
two-character string, Vault reads it as one entity ID, and rejects it. The
member survives. "or equivalent" does not rescue this: the named form is the one
an implementer pastes and a deterministic scorer encodes.

**Three forms that do work**, all measured on the same group, all clearing to
`[]` and all leaving `policies ['admin']` and `name` intact:

```
vault write identity/group/name/admin member_entity_ids=
vault write identity/group/name/admin member_entity_ids=""
echo '{"member_entity_ids": []}' | vault write identity/group/name/admin -
```

The `identity/group/id/<gid>` endpoint takes the same bare-empty form. Use the
first; it is the shortest and does not depend on shell quoting. `terraform plan`
after the clear reports "no differences", so the hand-removal creates no drift.

### 3. "A habit, not a gate": holds in the plan, one gap in the eval

The plan is right everywhere I checked. The risk section (lines 158-163) now
says nothing enforces it and nothing can, the DoD (179-182) says the state is
left by hand rather than maintained by an apply, Requirement 2 says an apply
does not revert it, and Requirement 10 pushes the same sentence into
`docs/cluster-roles.md`. Nothing implies Terraform guards it.

The gap is that **Requirement 10 grew a clause the eval does not score**.
Requirement 10 now demands the doc say `admin` membership is invisible to every
plan. Eval row 12's rubric lists what the doc must contain (four roles, what
each grants, the defining ticket, the naming convention, that a group needs an
assignment, that neither role is a containment boundary) and does not mention
it. The one sentence you added to stop the doc misleading a reader is the one
sentence no row checks.

### 4. New contradictions from this pass: two, both in row 3

**a. The `null` read is one-shot and the eval's own row 10 destroys it.** Once
any hand-write touches the field it reads `[]` forever. A plain apply does not
restore `null`; only destroying and recreating the group does:

| Step | `admin` members |
|---|---|
| fresh apply | `null` |
| hand-add, then row 10's clear | `[]` |
| `terraform apply` (0 changed) | `[]` |
| `terraform apply -replace` on the group | `null` |

So the eval is not re-runnable: row 10 leaves the state that makes row 3 fail
next time. Worse, **row 1 collides with row 3 on the first run.** Row 1 says
"Mint a token in the `admin` group" and then probes "update the token's **own**
entity", which exercises `identity/entity/id/{{identity.entity.id}}`. A token
made with `vault token create -policy=admin` carries `entity_id: ''` (measured),
so it cannot exercise that path at all. Row 1 needs an entity-backed login by a
group member, which means a hand-add. If row 1 runs before row 3, row 3's
`null` read returns a populated list and the row fails on a correct build. This
is the sharp edge fix 1 introduced: the old `[]` assertion at least came back
after a cleanup, whereas `null` does not.

**b. Row 3 still does not name the entity, and now that matters more.** Row 6
puts the scratch entity in `app-probe-reader` "**and nothing else**", and row 8
asserts that entity's session is denied four probes. If an implementer reuses
the scratch entity for row 3's hand-add, it is also in `admin`, row 6's "and
nothing else" is false, and row 8's four probes succeed instead of failing. I
flagged the unnamed entity last pass; the removal half of that fix landed and
the naming half did not.

## Assumptions attacked

| # | Assumption | Verdict | Evidence |
|---|---|---|---|
| P1 | `external_member_entity_ids = true` stops the revert, including on a real group update | **HOLDS** | re-measured: plan clean with member present; forced `metadata` change gave `0 added, 1 changed` and the member survived |
| P2 | `null` distinguishes a flagged group from an unflagged one | **HOLDS** | pristine flagged `null`, pristine unflagged `[]`, confirmed on the raw API |
| P3 | Row 10's command clears membership | **BREAKS** | HTTP 500, `invalid entity ID "[]"`, member intact |
| P4 | Row 3's `null` read is stable across the eval run | **BREAKS** | one-shot; row 1 needs a prior member, row 10 leaves `[]`, only `-replace` restores `null` |
| P5 | Row 3's entity does not collide with rows 6 and 8 | **UNCERTAIN** | entity still unnamed; row 6's "and nothing else" and row 8's denials break if it is the scratch entity |
| P6 | The "habit, not gate" framing holds everywhere | **HOLDS in the plan** | risk 158-163, DoD 179-182, Requirement 2, Requirement 10; eval row 12's rubric and eval line 3 lag |
| P7 | Unflagged groups revert a hand-added member to `[]` | **HOLDS** | `~ member_entity_ids`, `Plan: 0 to add, 1 to change`, then `[]` |
| P8 | Plan anchors resolve | **HOLDS** | `oidc.tf:36-38`, `oidc.tf:64`, `oidc.tf:110`, `modules/bucket/main.tf:12`, `docs/vault-human-auth.md:71-87`, `.loop/config.json:2-4`, `M2:128-132` all exact; `roles.tf` and `docs/cluster-roles.md` correctly absent |
| P9 | A `developer` can self-join in one write | **HOLDS** | `F11:105` grants `path "identity/*"` with update; `F11:147` states it outright. F11's line numbers have shifted since my last pass, but this plan cites no F11 line, so nothing here breaks |
| P10 | Requirement 5's `concat` keeps the smoke client alive | **HOLDS** | `oidc.tf:100-104` is the assignment, `group_ids = [vault_identity_group.smoke.id]`; `values({})` on an empty map does not error |

Live-cluster claims stay **UNCERTAIN**: I could not read the live `default`
policy or the live `bootstrap` mount. Requirement 1 already tells the
implementer to read `default` live, which is the right hedge.

## Most dangerous assumption

**P3 — that row 10's command removes the member.** Everything else is a wording
repair or an ordering note. This one means the proof run ends with a standing
`admin` member that no future `terraform plan` will ever report, which is the
exact failure the plan ranks second-worst and the thing that makes `F11`'s
narrow policy stop meaning anything. It fails at the end of a long manual run,
with a 500 that is easy to wave off as cleanup noise, and the flag guarantees
nothing downstream will catch it.

## Required fixes

All four land in `.loop/evals/F14-foundation-role-taxonomy.md`. **None touches
the plan file, so the fingerprint above stands** and the ticket does not need
re-planning.

1. **Row 10: replace the command.** `member_entity_ids='[]'` returns HTTP 500
   (`invalid entity ID "[]"`) and leaves the member. Use
   `vault write identity/group/name/admin member_entity_ids=` (measured: clears
   to `[]`, keeps `policies ['admin']` and `name`, and `terraform plan` stays
   clean). The `""` and JSON-stdin forms also work if you prefer one of those.
2. **Row 3: pin the `null` read to the pristine state and fix the ordering.**
   Say it must be read straight after the first apply, before any membership
   write anywhere in the eval, and note that the signal is one-shot: after row
   10 the group reads `[]` forever, so re-running row 3 needs a
   `terraform apply -replace` on the group. Either move row 3's read ahead of
   row 1 or say row 1's member must be cleared first, because row 1 needs an
   entity-backed member (a `-policy=admin` token has no `entity_id`, measured,
   so it cannot exercise row 1's self-entity probe).
3. **Row 3: name the entity, and make it not the scratch entity.** Row 6 says
   the scratch entity is in `app-probe-reader` "and nothing else" and row 8
   asserts its session is denied; reusing it for row 3 breaks both. The operator
   entity works, and row 10's clear sweeps it either way.
4. **Row 12: score Requirement 10's new clause.** Add "and that `admin`
   membership is not managed by Terraform, so a standing member is invisible to
   every plan" to the rubric. Right now the sentence you added to Requirement 10
   is the one doc claim no row checks. While you are in the eval, bring its
   Definition of Done (eval line 3, "an empty group") in line with the plan's
   reworded DoD.

## Carried, not blocking

Same list as last time, minus what you fixed. I am not re-raising my previous
fix 3 as a blocker: Requirement 8 is buildable both ways (I measured both), so
it is under-specification rather than a false premise, and it should not hold
the ticket a third time.

- **Requirement 8 has no eval row**, and Requirement 3 still gives the locals
  map no value shape, so "adding a person is a Terraform edit" does not say
  which edit. Decide it during implementation.
- **Row 1's `bootstrap` probe exits 2 on an empty mount** ("No value found at
  bootstrap/metadata", re-measured), while row 1's scorer demands all probes
  exit 0. Score "not permission denied" instead, or seed a value first.
- **Requirement 5's second consequence**: the smoke assignment now reads the
  whole taxonomy, so every future map entry silently gains login rights on the
  smoke client.
- **Naming convention reach**: `G1` and `M2` already assume `minio-admins`,
  `minio-readers`, `minio-writers`, `dashboard-users`, which the
  `app-<service>-<level>` convention does not cover. One sentence in
  `docs/cluster-roles.md` keeps it from stating a rule the next two tickets
  break. Worth noting too that the `groups` claim only appears when the client
  requests `scope=openid groups`, which rows 7 and 11 depend on.
- **`D5:28-32`** starts one line late; the sentence begins at line 27.
