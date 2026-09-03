---
epic = "cli"
depends_on = ["D3-cli-read-commands"]
priority = 25
summary = "Add `localstack vault admin status|join|leave` so joining and leaving the break-glass admin group is one safe command instead of a read-modify-write the operator does by hand. Automates the footgun the runbook warns about: the membership list is REPLACED, not appended to."
premise = { Q1 = "The operator's own session token can already write identity/group/name/admin, so this needs no root token and no new Vault policy" }
measured_against = { Q1 = { kind = "probe", version = "live cluster 2026-09-03", ref = "vault token capabilities identity/group/name/admin returned create, delete, list, read, update" } }
---

# Ticket: D11-cli-vault-admin-join-leave

## 1. Title

Add `localstack vault admin status|join|leave` so break-glass membership is
one safe command, not a hand-rolled read-modify-write.

## 2. Size / Effort

**Small.** Two functions in the existing Vault client and one command group.
No new dependency, no new auth path: the operator's own token already has
the capability.

## 3. Triggered by

The operator hit a 403 applying `deployments/infrastructure`: G1 added
`email` metadata to `vault_identity_entity.operator`, so the apply now
writes an identity entity, which the session token cannot do. The fix is to
join the `admin` group for the incident and leave after. Doing that by hand
means reading the current membership, appending yourself, writing the whole
list back, and remembering to reverse it.

## 4. Context

- `deployments/infrastructure/roles.tf:127-137` — `vault_identity_group.admin`
  sets `external_member_entity_ids = true`, so membership is deliberately
  NOT managed by Terraform. Its own metadata says "Join for the incident,
  leave after."
- `docs/cluster-roles.md:56-100` — the procedure, and the three traps it
  names: the membership list is REPLACED rather than appended to, so a join
  must restate every existing member; `member_entity_ids=""` empties the
  group outright and is correct only when you are its last member; and
  `identity/group-member-entity-ids` does not exist on this Vault, returning
  `unsupported path`, which reads like a permissions error.
- `docs/cluster-roles.md:56-58` — "Leaving yourself in `admin` after an
  incident is invisible to every `terraform plan`. Checking is a habit, not
  a gate." That habit is what this command makes cheap.
- `cli/src/localstack_cli/auth/vault.py:68-99` — `_request` already performs
  an authenticated POST with a JSON body, so the client needs two thin
  functions, not a new transport.
- `cli/src/localstack_cli/commands/vault.py:23` — the `vault` typer group
  already exists and its registration comment says it is a group "because it
  will hold more than one view". This is the second.
- `cli/src/localstack_cli/main.py:59` — the lazy subcommand registry the
  group is reached through.

**Why not `breakglass`.** `cli/src/localstack_cli/commands/breakglass.py:1-21`
declares a hard credential boundary as its load-bearing design: no read of
`VAULT_TOKEN` "for any purpose, including just to check", no subprocess, and
it always exits 0 because it is documentation you reach for when auth is
already broken. Join and leave need a token and perform a write, so they
would break that contract. They belong beside the other authenticated Vault
views instead.

## 5. Non-goals / out of scope

- Managing membership of any other group. `admin` is the documented
  exception; every other tier is Terraform-owned and must stay that way.
- Changing `vault_identity_group.admin`, its policy, or any Terraform.
- Adding, removing or renewing tokens. The command uses the session the
  operator already has.
- A justfile recipe. The operator asked for the CLI instead, and a recipe
  would be a second copy of the read-modify-write to keep correct.
- Auto-leaving on a timer, or any background daemon.

## 6. Requirements & restrictions

- R1. Three commands under the existing `vault` group: `admin status`,
  `admin join`, `admin leave`.
- R2. **Join and leave are read-modify-write, never a blind write.** Each
  reads the current `member_entity_ids`, changes only the caller's own id,
  and writes the full list back. This is the whole point: the raw API
  REPLACES the list, so a hand-written join silently evicts everyone else.
- R3. **The caller's entity id is read, never supplied or guessed.** Take it
  from `auth/token/lookup-self`, the way `docs/cluster-roles.md:77-79`
  instructs. A token with no entity (the root token has none) is a clear
  refusal, not an empty write.
- R4. Both commands are idempotent and say so: joining when already a member
  and leaving when not a member both succeed without a write, and report
  that nothing changed.
- R5. **`join` warns that the new policy is not live until the session is
  renewed.** Vault resolves group policies at token issuance, so the current
  token does not gain `admin` until re-login. Omitting this is the mistake
  the operator will otherwise make immediately after running it.
- R6. **`join` prints the matching `leave` invocation** and states that
  nothing will remind them, echoing `docs/cluster-roles.md:56-58`.
- R7. No credential is printed or logged, matching the boundary the rest of
  the CLI keeps (`cli/src/localstack_cli/commands/breakglass.py:8-13`). The
  entity id is an identifier, not a secret, and may be shown.
- R8. Failures are actionable: a 403 says the token cannot write the group
  and names the capability needed; an unreachable Vault says so. Reuse
  `VaultError` and the existing `fail` helper rather than raising a
  traceback.

## 7. Code surface

- `cli/src/localstack_cli/auth/vault.py` — add `read_identity_group(addr,
  token, name)` and `write_group_members(addr, token, name, member_ids)`,
  both thin wrappers over the existing `_request` (R2). Placed beside
  `read_creds`, which has the same shape.
- `cli/src/localstack_cli/commands/vault.py` — add an `admin` sub-group with
  `status`, `join` and `leave` (R1, R4, R5, R6), reusing `require_session`,
  `refreshed_session`, `fail` and `warn` already imported there (R8).
- `cli/tests/auth/test_vault.py` — respx cases for the two new client
  functions, including the empty-group and missing-entity shapes (R3).
- `cli/tests/commands/test_vault_admin.py` — new file: command-level tests
  for join, leave, the two idempotent paths (R4), the re-login warning (R5),
  the read-modify-write preserving other members (R2), and that no token
  value appears in any output (R7).

`main.py` needs no edit: the `vault` group is already registered and the new
commands hang off it.

## 8. Tests & validation gates

### Repo gate (loop-enforced)

`just pre_commit`, which for this ticket's files runs Ruff lint and format,
Mypy in strict mode, and pytest over `cli/`
(`.pre-commit-config.yaml`). Unlike the infrastructure tickets in this epic,
this change has a real unit-test harness and must use it.

Run the suite directly while iterating: `uv run pytest cli/tests -q` from
the repo root, per `.claude/rules/python-testing.md`.

### Tests to add

Mocked with respx against a fake Vault, never the live cluster, per
`.claude/rules/python-testing.md`'s boundary rule:

- T1 — join on an EMPTY group writes exactly the caller's id, and does not
  write an empty string.
- T2 — join on a group with other members writes those members PLUS the
  caller, preserving order. This is R2's regression test and the reason the
  ticket exists.
- T3 — join when already a member makes no write call at all and reports no
  change (R4). Assert on `respx` call count, not on output text alone.
- T4 — leave removes only the caller and preserves every other member.
- T5 — leave when the caller is the last member writes an empty list, which
  is the one case where emptying the group is correct.
- T6 — leave when not a member makes no write call and reports no change.
- T7 — a token with no entity id is refused with a clear message and no
  write (R3).
- T8 — join's output names the re-login requirement and the leave command
  (R5, R6).
- T9 — a 403 on the write surfaces an actionable message naming the
  capability, not a traceback (R8).

### Manual check (live, once)

`localstack vault admin status` against the live cluster reports the real
membership, which is currently empty. Not a scored row: the unit tests carry
the behavior, and this only confirms the wiring.

## 9. Risk assessment

- Blast radius: this command grants and revokes wildcard Vault access. A bug
  in the read-modify-write could evict other admins during an incident,
  which is exactly when that hurts most. T2 and T4 are the tests that matter.
- The opposite failure is quieter and likelier: a `leave` that silently does
  not write, leaving the operator with standing wildcard access they believe
  they dropped. T4, T5 and T6 pin it, and `status` exists so the claim can
  be checked rather than trusted.
- Reversibility: high. The command writes one field of one group, and
  `status` shows the result immediately. Nothing here is Terraform-managed,
  so no apply can conflict.
- Not a new privilege. The operator's token already has
  `create, delete, list, read, update` on this path (probe, premises), so
  this exposes no capability they lack today. It only makes the documented
  procedure hard to get wrong.

## 10. Subtickets

1. **Client functions plus their tests** (`auth/vault.py`,
   `tests/auth/test_vault.py`). Depends on nothing.
2. **The `admin` sub-group and its tests** (`commands/vault.py`,
   `tests/commands/test_vault_admin.py`). Depends on 1.
3. **Live `status` check** and record the outcome. Depends on 2.

## 11. Open questions

- Q1. **Command placement — resolved.** Under the existing `vault` group
  rather than `breakglass`, whose credential boundary forbids it (§4), and
  rather than a new top-level group, since this is a Vault operation and the
  group's own registration comment anticipates more than one view.
- Q2. **Should `join` prompt for confirmation?** It is a privilege
  escalation, but it is also reached during an incident when a prompt is
  friction. Recommendation: no prompt, because `status` makes the state
  cheap to check and R6's printed `leave` line is the safety net. Revisit if
  it is ever wired into something non-interactive.
- Q3. **Should `leave` run automatically on `localstack logout`?**
  Recommendation: no, and not in this ticket. Logging out does not end an
  incident, and a surprise revocation mid-incident is worse than a lingering
  membership the operator can see with `status`.

## Premises / assumptions

- **P1 — The operator's own token can already write the admin group, so no
  root token and no policy change is needed.** Probe, run live 2026-09-03:
  `vault token capabilities identity/group/name/admin` returned
  `create, delete, list, read, update`. Anchor for the group itself:
  `deployments/infrastructure/roles.tf:127`.
- **P2 — Membership is not Terraform-managed, so writing it cannot conflict
  with an apply.** Anchor:
  `deployments/infrastructure/roles.tf:127-137` sets
  `external_member_entity_ids = true`, and its metadata describes the
  join-then-leave workflow.
- **P3 — The group is currently empty, so the first join writes a single
  id.** Probe, run live 2026-09-03: `vault read -format=json
  identity/group/name/admin` returned a null `member_entity_ids` with
  `policies ['admin']` and group id `d40f1623-23ce-957b-1b81-afb921207923`.
  Anchor for the resource that created it:
  `deployments/infrastructure/roles.tf:127`. This is why T1 exists
  separately from T2.
- **P4 — The existing client can already make the calls.** Anchor:
  `cli/src/localstack_cli/auth/vault.py:68` takes a `method` and a JSON
  `body` and sets the token header, and `read_creds` at `:155` is the same
  shape as the two functions this adds.
- **P5 — `breakglass` must not host these commands.** Anchor:
  `cli/src/localstack_cli/commands/breakglass.py:8-13` states the boundary,
  including "No read of `VAULT_TOKEN` for any purpose" and "no subprocess",
  and `:19-21` explains the always-exit-0 contract.
- **P6 — Group policies apply at token issuance, so a fresh token is needed
  after joining.** Probe, run live 2026-09-03: `vault token lookup` on the
  operator's session reported `policies ['default']`, and
  `vault token capabilities identity/entity/id/351f302a-...` reported
  `read` only, which is the 403 the operator hit. Anchor for the group whose
  policy a new token would carry:
  `deployments/infrastructure/roles.tf:130`. R5 exists for this.
  UNCERTAIN in one respect, and the reason R5 is a warning rather than an
  automatic re-login: whether Vault re-resolves group membership for an
  already-issued token on its next request has not been probed here, only
  the failure that prompted the ticket.
