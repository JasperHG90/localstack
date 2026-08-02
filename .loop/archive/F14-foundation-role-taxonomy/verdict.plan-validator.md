---
verdict: pass
plan: ab134b20c93025560d8cb5bfd7442a8e8a096dc4d5fe7579278b144f4a9f2137
---

# Plan verdict — F14-foundation-role-taxonomy (pass `plan-validator`, seventh review)

Fingerprint verified locally: `sha256sum .loop/plans/F14-foundation-role-taxonomy.md`
returns `ab134b20c93025560d8cb5bfd7442a8e8a096dc4d5fe7579278b144f4a9f2137`,
matching the briefing. Eval at
`44e4803c767bec08d0629fa7307e0a7237d99d85f44dd2eb2baf31b6d5b8abd7`.

Method: read-only. All three sixth-pass required fixes and the carried anchor
nit re-checked against the files they touch, the two texts F14 rewrites reopened
verbatim, all six consumer plans reopened at their cited lines, and seven
read-only Vault probes (`vault status`, `vault list identity/oidc/assignment`,
`vault read identity/oidc/assignment/{allow_all,oidc-smoke}`, `vault list
identity/group/name`, `vault read identity/oidc/provider/lab`, `vault policy
read default`, `vault path-help identity/oidc/assignment/allow_all`). No
mutating command, no `terraform`, no write outside this file.

## Premise verdict: SOUND

All three required fixes landed, and each makes a claim that is true. The
carried `R1` anchor is corrected and the new anchor genuinely supports its
claim. The eval row now passes a correct build and still fails both the
three-branch build and the unconditional-clause build. Requirements 1..13 and
branches 1..4 are complete with no gap or duplicate, and all cross-references
resolve — the first pass in three where that survives a hand edit. The four
branches cover all six known consumers.

Nothing left is load-bearing. Four advisories are listed at the end; none of
them changes what gets built or lets a wrong build through, so they are not
required fixes and the fingerprint is bound.

## Fix 1 — Requirement 12 now scopes both clauses. VERIFIED

`plan:177-188` reads: "**Both clauses are now conditional, not just the group
one.** Under branches 1, 2 and 4 a consumer creates its own assignment — `G2`
does (`G2:242-250`), and it stays the worked example. Under branch 3 it creates
**neither**". The old "leave the assignment clause alone" is gone, and
`plan:185-187` says so explicitly ("An earlier draft … was written before
branch 3 existed and is now false").

The claim is true against the text being rewritten. `oidc.tf:8-10` verbatim:

```
### NOT created here. Each consumer ticket creates its own
### vault_identity_oidc_client, its own group and assignment, and its own
### vault_identity_oidc_key_allowed_client_id entry pointing at this key.
```

Both "group" and "assignment" sit in one clause, and both are false for a
branch-3 consumer.

**Nothing else in the plan still asserts a consumer always creates an
assignment.** All 17 occurrences of "assignment" in the plan checked. The only
other unconditional-sounding one is `plan:199` in Code surface, and it is a
quotation of the comment being rewritten ("which tells every consumer 'each
consumer ticket creates its own group and assignment'"), identical in role to
`plan:178`. Requirement 10's "a group needs an OIDC assignment to grant
anything" (`plan:136`) stays true under branch 3: `allow_all` is an assignment
and `group_ids [*]` covers every group, so the sentence does not contradict the
new branch.

## Fix 2 — Requirement 11 now covers three things. VERIFIED

`plan:147-154`: "**Three things in that section change, not one.**" Both new
targets are named, quoted, and correct against `docs/vault-human-auth.md`:

- the lead, quoted as "**Four resources**, then one line in a shared list" —
  `docs/vault-human-auth.md:169` verbatim: "Four resources, then one line in a
  shared list. Copy the smoke-test block in `oidc.tf` as the template."
- step 3, quoted as "`vault_identity_oidc_assignment`, which binds **that
  group** to the client" — `:175` verbatim: "3. `vault_identity_oidc_assignment`,
  which binds that group to the client."

Step 2 is `:174` verbatim, "2. `vault_identity_group`, who is allowed in.",
which is the string Requirement 11's header cites. Citation is by name
throughout: the requirement quotes text and says "step 2", "step 3", "the
section's lead", and repeats the by-name rule at `plan:153-154`. No line number
into that file appears anywhere in the requirement.

## Fix 3 — the eval row. VERIFIED, and it now discriminates the right way

`eval:32` behavior cell: "**Both copies of the consumer rule carry all four
branches, and nothing still claims an assignment is always created**". The
"unchanged" clause is gone. Scorer: "deterministic check (both texts name all
four branches; neither states unconditionally that a consumer creates its own
group or its own assignment)".

Discrimination, checked case by case:

- **A build that does fixes 1 and 2 correctly PASSES.** Both texts name four
  branches; neither states the group or assignment clause unconditionally. The
  row no longer pins the text the new branch falsifies.
- **A build naming only three branches FAILS.** Both the Expected cell ("Both
  name four branches") and the scorer's first clause require four.
- **A build leaving either clause unconditional FAILS.** The scorer names group
  *and* assignment, so a header comment keeping "its own group and assignment"
  fails, and a step list keeping step 3 as an unconditional item fails.
- **A doc-only edit FAILS.** The Input cell reads both texts.

Shape: `awk -F'|'` over `.loop/evals/F14-foundation-role-taxonomy.md` reports
all 16 table lines at 7 fields, i.e. 5 columns (Behavior, Input, Expected,
Scorer, Threshold). Row 32 matches the header and the other 14 rows exactly.

One narrow seam, advisory not blocking: the scorer's parenthetical does not
mention the lead's "Four resources" count, which the Expected cell does require
("the doc's lead must no longer say a flat consumer writes four resources"). A
scorer built from the parenthetical alone would pass a doc that fixes steps 2
and 3 but leaves the lead. The Expected cell is part of the row and carries it,
and the resulting doc would be visibly self-contradicting, so this cannot ship a
wrong taxonomy — it can only miss one stale sentence.

## Fix 4 — Requirement 9's branch-3 proof. VERIFIED, with a cost caveat

`plan:125-134` adds: "**Prove branch 3 on the same run, since the scratch entity
already exists.** Point a throwaway client's `assignments` at `["allow_all"]`
and complete an authorization with that entity while it is in **no** relevant
group." It then names exactly the gap the sixth pass named — "that it therefore
admits a non-member at authorization time is inferred from those values and
nothing here has run it" — invokes Requirement 2's own standard, and gives an
honest escape hatch: skip it and write "Vault-documented, unverified on this
cluster" into branch 3 rather than letting the reader assume it was tested.

The clause closes the gap it was asked to close. A completed authorization by an
entity that no assignment enumerates is exactly the missing measurement.

**It is cheaper than a separate proof run, but it is not one free clause.** The
throwaway client also needs registering against the key and, per `oidc.tf:60-62`
("Omitting your client means Vault refuses the authorization request against
this provider"), an entry in `local.oidc_provider_client_ids`. Confirmed live:
`vault read identity/oidc/provider/lab` returns `allowed_client_ids
[zsJxdNqN7vIBQXhGmlgkwVIHigjhweGF]`, one id. Miss either and the authorization
is refused for a reason unrelated to `allow_all`, which reads as branch 3
failing. It reuses the scratch entity, the userpass alias, the key, the provider
and `var.oidc_smoke_redirect_uris` (which has a default,
`variables.tf:64-67`), so the marginal cost is one client plus two registrations
plus one flow. The escape hatch means the implementer is never trapped by that
cost. Advisory 2 below.

## Carried nit — the `R1` anchor. CLEARED

`plan:172` now reads `R1` (`R1:99-102`). Verified: `R1:99-102` is the non-goal
"**No fine-grained MLflow authorization.** MLflow's built-in auth plugin is
thin; the proxy gates *access* (authn) but does not give per-experiment or
per-model authz. This limit MUST be documented". That supports "R1 declares flat
access" as directly as R1 allows: `grep -in 'flat|identity_group|assignment'`
over the whole R1 plan returns **zero** hits, so no better anchor exists in that
file. The old `R1:122-127` no longer appears anywhere in the plan.

## Attack: requirement and branch integrity after four hand edits

Clean, and this is the check that broke twice before.

- Requirements read **1..13**, no gap, no duplicate (`plan:78, 86, 91, 93, 95,
  103, 104, 112, 119, 135, 141, 177, 190`).
- Branches inside Requirement 11 read **1, 2, 3, 4** (`plan:156, 158, 164, 176`).
  Branch 4's "only when none of the three fits" is arithmetically right.
- Every branch-count mention is correct: `plan:146` ("needs **four** branches,
  not two"), `plan:161` ("with only two branches", a correct reference to the
  superseded state), `plan:184` (Req 12 to "Requirement 11's four branches"),
  `plan:249` (DoD, "the same four branches"), `eval:32` ("four branches"). No
  "three branches" survives.
- Cross-references resolve, all of them: `plan:38` (Req 2 = the
  `external_member_entity_ids` group, and "eval row 3" is the membership row
  `eval:22`), `plan:99` ("the header comment covered by Requirement 12" →
  `plan:177` is the header-comment requirement), `plan:117` (Req 2),
  `plan:160` (Req 6 = "The map ships empty", `plan:103`), `plan:184` (Req 11 =
  `plan:141`), `plan:197` (Req 5 = the `oidc.tf` line), `plan:200` (req 11 = the
  doc edit), `plan:213` (Req 5), `plan:217` (Req 9 = "Prove it end to end").

## Attack: does the four-branch rule cover all six known consumers?

**Yes, six of six.** Re-read at the cited lines:

| Consumer | Evidence at the cited anchor | Branch |
|---|---|---|
| `G2` | `G2:147-149` "The group this ticket binds is **F11's `developer`** … creates no `vault_identity_group`" | 1 |
| `M2` | `M2:112-116` three Vault groups `minio-admins`/`-readers`/`-writers`, consumed not created | 2 |
| `G1` | `G1:141-143` "start flat, with every authenticated user an Editor" | 3 |
| `R4` | `R4:296-298` "start flat … matching G1's Q2" | 3 |
| `L1` | `L1:66-67` "Access is FLAT: anyone who completes Vault login is allowed through" | 3 |
| `R1` | `R1:99-102` no per-experiment/per-model authz, plus L1's flat pattern | 3 |

One honest qualification, advisory 3 below: for `G1` and `R4` the flat posture
is a *recommendation inside an unresolved open question* (`G1:140` "Q2 — Map
OIDC groups to Grafana roles, or give everyone the same role?"; `R4:295` "Q3 —
Flat access, or map Vault groups to Phoenix roles?"), not a settled decision, so
`plan:172-175`'s "each declare flat access" is a shade strong for two of the
four. It does not touch coverage: if either resolves the other way it lands in
branch 2 or 4, both of which exist.

## Attack: multi-assignment semantics — is a clause needed now?

**No.** Branch 3 prescribes `allow_all` alone in the same sentence that
introduces it (`plan:168`: "`assignments = ["allow_all"]`: no group, no map
entry, no Terraform group resource"), and the branch list is a set of exclusive
answers to one question. Whether Vault unions or intersects multiple
assignments, `allow_all` on its own admits everyone, so the plan's prescription
is correct under either semantics and the plan never depends on the answer. I
still could not settle union-versus-intersection read-only — `vault path-help
identity/oidc/assignment/allow_all` documents only the two slice parameters and
says nothing about combination, and testing it needs a client write. A "do not
combine `allow_all` with another assignment" clause would be defensive polish
for a reader who improvises past the branch, not premise repair. Advisory 4.

## Attack: are the plan's own Vault claims still true live?

Re-measured, because Requirement 1 and eval row 1 both rest on them:

- `vault policy read default` shows `path "sys/leases/lookup"` with
  `capabilities = ["update"]` only — so `vault list sys/leases/lookup` is denied
  for a policy that does not re-grant it, exactly as `plan:59-63` and `eval:20`
  claim.
- `default` grants `identity/entity/id/{{identity.entity.id}}` **read only**,
  confirming Requirement 1's templated-path argument (`plan:80-85`) and the
  self-entity-update probe in eval row 1.
- `vault read identity/oidc/assignment/allow_all` returns `entity_ids [*]`,
  `group_ids [*]`; `oidc-smoke` returns `entity_ids []`, `group_ids
  [e86ec229-…]`. `plan:169-171` is accurate.
- `vault list identity/group/name` returns `developer`, `oidc-smoke` only — no
  `admin`, no `app-*`. Eval rows 4 and 5 start from a clean baseline, and
  `developer_group.tf:141` `resource "vault_identity_group" "developer"` is the
  live group branch 1 points at.
- Vault 2.0.3, unsealed, active.

## Attack: every other cited anchor

All resolve. `oidc.tf:7-10` (header comment), `:36-38` ("M2 tiers MinIO on
`role_policy`, which bypasses the claim entirely and gates on the per-client
assignment instead" — exactly Requirement 7's claim), `:64`
(`oidc_provider_client_ids = [`), `:110` (`assignments =
[vault_identity_oidc_assignment.smoke.name]`, confirming the list-of-names
claim). `.loop/config.json:2-4` is `"gates": ["just pre_commit"]`.
`deployments/applications/modules/bucket/main.tf:12` is
`name = "${local.name_underscore}_read_write"`. `roles.tf` and
`docs/cluster-roles.md` do not exist, matching their **(new)** marks.

## Assumptions attacked

| # | Assumption | Verdict | Evidence |
|---|---|---|---|
| P1 | `allow_all` is live with `entity_ids [*]`, `group_ids [*]` | **HOLDS** | probed live against Vault 2.0.3 |
| P2 | `assignments` is a list of names, so `["allow_all"]` needs no Terraform resource | **HOLDS** | `oidc.tf:110`; `path-help` documents `assignments (slice)` |
| P3 | Requirement 12 now scopes both clauses of `oidc.tf:9` | **HOLDS** | `plan:177-188`; `oidc.tf:8-10` verbatim has both in one clause |
| P4 | Nothing else in the plan claims a consumer always creates an assignment | **HOLDS** | all 17 "assignment" hits checked; `plan:199` is a quotation of the text being rewritten |
| P5 | Requirement 11 covers the lead, step 2 and step 3, cited by name | **HOLDS** | `plan:147-154`; quotes match `docs/vault-human-auth.md:169, :174, :175` verbatim |
| P6 | The eval row passes a correct build and fails both wrong builds | **HOLDS** | `eval:32` case analysis above |
| P7 | The eval row's shape matches the other table lines | **HOLDS** | `awk -F'|'`: all 16 lines at 7 fields, 5 columns |
| P8 | Requirement 9's new clause closes the branch-3 runtime gap | **HOLDS** | `plan:125-134`; an authorization by an entity no assignment enumerates is the missing measurement |
| P9 | That proof is cheap on a run already happening | **HOLDS with caveat** | reuses entity, alias, key, provider, redirect default; but also needs a key registration and a `local.oidc_provider_client_ids` entry (`oidc.tf:60-62`; live `allowed_client_ids` has one id). Escape hatch at `plan:132-134` |
| P10 | `R1:99-102` supports the flat-access claim | **HOLDS** | non-goal verbatim; `grep` over R1 for flat/group/assignment returns zero hits, so it is the best anchor available |
| P11 | Requirements 1..13 and branches 1..4 are complete and cross-refs resolve | **HOLDS** | enumerated above; nine references, nine resolve |
| P12 | The four branches cover all six known consumers | **HOLDS** | table above, each at its cited anchor |
| P13 | `G2:242-250` supports "a branch-1/2/4 consumer creates its own assignment" | **HOLDS at the edge** | the supporting text starts at `G2:250` and runs to `:252`; `:242-247` is an unrelated note plus the Code surface heading |
| P14 | Multi-assignment semantics do not affect the plan | **HOLDS** | branch 3 prescribes `allow_all` alone (`plan:168`); safe under union or intersection. Semantics themselves **UNCERTAIN**, unprovable read-only |
| P15 | The tests-and-gates section names commands that work here | **PARTIAL** | `just pre_commit` correct (`.loop/config.json:2-4`); bare `terraform plan` fails — `secret_mount`, `gcp_project`, `gcs_backup_bucket` have no defaults (`variables.tf:1-14`) and the blessed form is `CONSUL_HTTP_TOKEN=… terraform … -var-file=./vars/prod.tfvars` (`deployments/infrastructure/justfile`) |
| P16 | The plan's live Vault claims are still true | **HOLDS** | `default` policy, assignments, group list, provider all re-measured |

## Most dangerous assumption

**P8/P9 — that branch 3's runtime behavior gets proven rather than assumed.**
Branch 3 is canonical guidance four of six consumers will follow without
re-deriving it, and it is the one branch whose payoff (a service that admits
anyone who can log in) is invisible until a real user with no groups tries to
log in months later. Requirement 9 now demands the proof and, if the
implementer declines, demands they write the words "unverified on this cluster"
into the branch itself. That is the right shape: either it is measured or the
reader is told it is not. What keeps this from being a blocker is that the
failure mode is now honest rather than silent. What keeps it on the danger list
is that no eval row scores either half, so the escape hatch is unpoliced —
advisory 1.

## Advisories (none blocking, none requiring a re-bind)

1. **No eval row scores the branch-3 runtime proof or its caveat.** Requirement
   9's other clauses are covered by eval rows 6 and 7; the `allow_all`
   authorization and the "say so in branch 3" fallback are covered by nothing.
   An implementer can skip both silently. If you touch the eval again, a clause
   on row 6 costs one sentence.
2. **The throwaway client in Requirement 9 needs two registrations the plan does
   not mention** — a `vault_identity_oidc_key_allowed_client_id` and an entry in
   `local.oidc_provider_client_ids`. Without them Vault refuses the
   authorization for a reason unrelated to `allow_all` (`oidc.tf:60-62`; live
   provider carries exactly one allowed client id), and the implementer may read
   that as branch 3 failing.
3. **`G1` and `R4` recommend flat access inside an open question** (`G1:140`
   Q2, `R4:295` Q3) rather than declaring it. `plan:172-175`'s "each declare
   flat access" is a shade strong for those two. Coverage is unaffected.
4. **One clause would fence off `allow_all` beside another assignment.** The
   plan is safe because branch 3 says `allow_all` alone, but the combined case
   is undefined here and I could not settle Vault's union-versus-intersection
   behavior read-only.
5. **`terraform validate` and `terraform plan` are named without their
   invocation** (`plan:207`). Bare `terraform plan` errors on three
   default-less variables; the working form is in
   `deployments/infrastructure/justfile`.
6. **`oidc.tf:7-10` is cited by line in four places** (Req 12, Code surface,
   DoD, `eval:32` Input) while this ticket rewrites and lengthens that comment,
   so the range goes stale during the ticket. Requirement 11 argues for citing
   by name for exactly this reason. It resolves today.
7. **`G2:242-250` starts eight lines early** (`plan:180`); the supporting text
   is `G2:250-252`. **`D5:28-32`** (`plan:53`) starts one line late; the
   sentence begins at `D5:27`.
8. **`M2` names its groups `minio-admins`/`-readers`/`-writers`**
   (`M2:112-116`), not `app-minio-<level>`. Requirement 7 makes naming
   advisory, so this is M2's to reconcile.
