---
verdict: pass-with-required-fixes
plan: d0f5b90fd7ecf97bfa402a844b00dab20cb865545a12f747a078108a8e3fa75c
---

# Plan review — R7-rollout-postgres-consumer-cutover (`plan-validator`, cycle 2)

`sha256sum .loop/plans/R7-rollout-postgres-consumer-cutover.md` returns
`d0f5b90fd7ecf97bfa402a844b00dab20cb865545a12f747a078108a8e3fa75c`, matching the
briefing. `loopctl verify-plan R7-rollout-postgres-consumer-cutover` returns
`valid` (exit 0). The `plan:` line is written, so this verdict authorizes the
`PLANNING -> READY` flip.

## Premise verdict: SOUND

Gate verdict: **pass-with-required-fixes**.

The ground has indeed stopped moving. `a21da6f` is committed,
`deployments/applications/database-secrets-poc.tf` is 330 lines and clean in
`git status`, and the premise that flipped under me in cycle 1 is now stated as
an invariant rather than a snapshot. Every cycle-1 required fix was attempted
and three of the four premise fixes (A1, A3, A4) landed correctly. The fourth
(A2) landed halfway. The anchor fix (B1) landed for every citation written as
`database-secrets-poc.tf:NNN` and missed all eight written as a bare `:NNN`
inside §7 — which is the code surface, the section an implementer navigates by.

I am passing rather than failing because no premise is false, the required fixes
are text edits with no design consequence, and the ticket cannot be implemented
until R3 lands anyway. The fixes below are binding on the implementation.

---

## Cycle-1 required fixes, verified one by one

**A1 — minting-admin invariant. FIXED.** Requirement 3
(`.loop/plans/R7-rollout-postgres-consumer-cutover.md:206-244`) now states the
invariant, routes the membership check into requirement 1's discovery, and
carries a correct `pg_auth_members` query. I checked the query's semantics
rather than its shape: `pg_auth_members.roleid` is the granted group and
`member` is the grantee, so filtering `g.rolname = '<admin>'` on the `member`
join and selecting `r.rolname` from the `roleid` join returns exactly the owner
roles the admin belongs to, with `admin_option`. Correct. The hand-add
instruction is gone from the requirement, subticket 2 (`:600-607`) checks first
and says it may be a no-op, failure mode 2 (`:554-562`) explains the delay by
design, P10 (`:802-818`) is the invariant plus a probe, and P10a (`:819-826`)
records the `noinherit` measurement. The derivation itself checks out:
`database-secrets-poc.tf:75` is
`s2_poc_grantable_owners = distinct([for db in local.databases : db.owner])`,
consumed at `:149` and `:173`, and `deployments/applications/database.tf:10-40`
yields exactly five distinct owners (`ducklake_owner`, `memex`, `phoenix`,
`mlflow`, `bifrost`), matching the live probe the plan records.

**A2 — §5 / Q8 root-consumer contradiction. HALF FIXED.** The stub is real:
`.loop/plans/R8-rollout-postgres-root-consumers.md` exists, carries
`stub = true` and `depends_on = ["R7-rollout-postgres-consumer-cutover"]`, and
`loopctl ledger` shows `R8-rollout-postgres-root-consumers: stub [epic: rollout]
[priority: 3] deps: R7-... (1 unmet)`. Downstream, not upstream, exactly as Q8
asks. §5 (`:144-147`) names it correctly.

But **Q8 was not updated and now contradicts §5 in the other direction.**
`:722-724` still reads "which ticket owns the `localstack` root consumers? **No
ticket does today.** *Recommendation:* file one (suggested slug
`R8-rollout-postgres-root-consumers`)". §5 ends with "See Q8", so the plan points
the reader at a paragraph that denies what §5 just asserted. The hallucination
risk I flagged is gone (subticket 8 now has a real slug to name), so this is a
one-sentence text fix, not a design hole. See F1.

**A3 — ducklake ownership. FIXED, and not moved elsewhere.** §5 (`:148-162`) now
says plainly that no ticket owns the roles, that this plan does not hand them to
one, and why the previous S1 citation was wrong. `deployments/applications/
database.tf:3-4` is `"ducklake_owner"` and `"ducklake_reader"`, as cited. I
checked the problem was not relocated: `grep -n ducklake` on the plan shows the
roles appear only in §5, the code surface's "leave them alone" instruction
(`:363-366`), Q7's `for_each` note (`:715-721`), and P4. No new owner is claimed
anywhere.

**A4 — mlflow restart cost. FIXED, and the reasoning is honest.**
`deployments/applications/services/mlflow.hcl:38-41` is exactly
`args = [ "-c", "pip install --quiet --no-cache-dir psycopg2-binary boto3 &&
exec mlflow server ...", ]`. Anchor resolves to the line. Q2 (`:662-674`) prices
the daily PyPI fetch, offers three options, recommends the long `max_ttl`, and
declines to smuggle an image change into a credential ticket. That is the right
call and stated without hedging.

**B1 — re-anchoring `database-secrets-poc.tf`. PARTIALLY FIXED, and the miss is
systematic.** Every anchor written with the filename prefix is now correct
against the committed 330-line file. I opened each:

| Plan anchor | Claim | Verified |
|---|---|---|
| `:251-264` (`:105`) | applied `SET ROLE` form | `vault_database_secret_backend_role.poc`, `SET ROLE` at `:259` |
| `:286-310` (`:114`) | dedicated JWT role | `vault_jwt_auth_backend_role.s2_poc`, `token_policies` at `:307` |
| `:78-82` (`:143`) | localstack rotation breaks three | the "Deliberately NOT the `localstack` root" comment |
| `:262-263` (`:298`) | S2's 120s/300s TTLs | `default_ttl = 120` / `max_ttl = 300` |
| `:184-198` (`:309`) | `disable_read` KV2 secret | the comment plus `vault_kv_secret_v2.s2_poc_admin` |
| `:39-53` (`:311`) | ephemeral chain, one apply | the `locals` write-only-chain block |
| `:49-53` (`:314`, `:896`) | unchanged version is a no-op | verbatim |
| `:14-19` (`:585`) | PoC resources still declared | verbatim |
| `:216` (`:645`) | `connection_url` targets `/memex` | the `connection_url` line, `local.s2_poc_database = "memex"` at `:58` |
| `:75`, `:149`, `:173` (`:810`) | grantable set derived and consumed | verbatim |
| `:121-144` (`:824`) | `noinherit` measurement | the "DO NOT set `inherit = false`" block, ending "nowhere to inject one" |
| `:257-260` (`:831`, `:892`) | creation statements | verbatim |

**The eight anchors in §7 (`:346-351`) were all missed, and every one is
wrong.** They are written bare (`` `:95-103` ``) with no filename prefix, which
is why a filename grep does not find them and why `loopctl verify-plan` cannot
parse them either. Checked against the committed file:

| §7 says | It actually is | Correct anchor |
|---|---|---|
| the admin role (`:95-103`) | tail of `ephemeral "random_password"` plus comment prose | `:145-153` |
| the admin-option grant (`:119-127`) | the transient-drift and `inherit = false` comment | `:172-182` |
| the write-only KV2 secret (`:133-143`) | the `noinherit` revocation-failure table | `:188-198` |
| the mount (`:145-149`) | `postgresql_role.s2_poc_admin`'s opening lines | `:200-204` |
| the connection (`:155-169`) | the WITH ADMIN OPTION comment | `:210-224` |
| the DB role (`:196-209`) | KV2 tail, the mount, the `connection_url` comment | `:251-264` |
| the dedicated policy (`:216-224`) | the inside of the connection resource | `:271-279` |
| the dedicated JWT role (`:231-255`) | the TTL comment plus the DB role's head | `:286-310` |

This is bounded damage: every shape §7 mis-anchors is also anchored correctly
somewhere else in the plan (`:251-264` in §4, `:286-310` in §4, `:184-198` in
requirement 11, `:121-144` in P10a). But §7 is the map, and right now every
coordinate on it is off by roughly fifty lines. See F2.

**C1 — R3's stale blocker. FIXED, and understated in the plan's favor.**
`:636-641` notes it before the forks. `d394306` is `S2-spike-postgres-vault-
creds: prove keyless Postgres via Vault's database engine` and S2 is `done` in
the ledger. The plan addresses only the S2 half of R3's recorded headline; the
other half ("F9 owns the same policy and is narrowing it") is also stale, since
`F9-foundation-scope-nomad-workloads-policy` is `done`. R3's whole blocker is
stale, not just the part the plan names.

**C2 — P14 attribution. FIXED.** `:843-846` records that the spike passage
assigns the untested half to R3 and keeps eval 3 anyway, with the reason.

**C3 — golang-migrate attribution. FIXED.** §5 (`:167-170`) now owns the
decision. `.loop/plans/R3-rollout-postgres-vault-db-creds.md:490-494` is Q6, an
open fork with a *leaning* toward static, exactly as the correction says.

**C4 — Q5 carries the P26 evidence. FIXED.** `:697-708` states the real cost:
the shared admin must inherit every owner role's data privileges because
`noinherit` breaks revocation, so the question is one broad standing credential
against several narrow ones, and the narrow option cannot buy its narrowness
with `noinherit` either. That is the honest framing.

---

## Most dangerous assumption

**That §7's code surface is a usable map of the reference file.** It is not: all
eight of its anchors point at comment prose or the wrong resource, and both
automated checks that would normally catch this are blind to the bare-`:NNN`
form. Nothing downstream of it is wrong, which is why this is a fix rather than
a failure, but an implementer who trusts §7 opens the wrong lines eight times
out of eight.

Cycle 1's most dangerous assumption — that `database-secrets-poc.tf` is a stable
reference — is retired. The file is committed, unmodified in the working tree,
and the plan no longer depends on any snapshot of its live effect.

---

## Required fixes (binding on the implementation, no further planning cycle)

**F1. Rewrite Q8's first sentence.** `:722-724` says "No ticket does today"; §5
`:144-147` says `R8-rollout-postgres-root-consumers` owns it, and the stub and
ledger entry both exist. Make Q8 read that R8 owns it, filed 2026-08-04 as a
stub, downstream of R7 and deliberately not in `depends_on`.

**F2. Re-anchor §7's eight bare citations** to `:145-153`, `:172-182`,
`:188-198`, `:200-204`, `:210-224`, `:251-264`, `:271-279`, `:286-310`
respectively, per the table above. Write them with the filename prefix so the
next `verify-plan` and the next reviewer can see them.

**F3. Fix Q8's anchor.** `:727` cites `database-secrets-poc.tf:67-71` for "S2
measured that rotating `localstack` breaks all three at once". Those lines are
the grantable-owners ADMIN OPTION trap and say nothing about `localstack`. The
correct anchor is `:78-82`, which §5 `:143` already uses.

**F4. Align §7's minting-admin bullet with requirement 3.** `:357-358` still
instructs "extend the minting admin's `roles` list and add one
`postgresql_grant_role` with `with_admin_option` per new owner role" — the
hand-add shape requirement 3 now warns against. Make it conditional on the
discovery check ("if the invariant does not already hold"), matching subticket
2's no-op wording.

---

## Recommendations (not binding)

**R1. P15's anchor is off by a block.** `:850` cites
`database-secrets-poc.tf:262-263` for the assertion that Nomad renews a
renewable lease until `max_ttl`. Those two lines are the TTL *values*; the
assertion is the comment at `:226-230`. Cite both.

**R2. "S2 measured" overstates `:78-82`.** That comment argues that rotating
`localstack` would take the exporter, the pg_dumpall backup and the applications
provider down at once. It is reasoning from three named consumers, not a
recorded measurement. Say "S2 recorded" or drop the verb.

**R3. C1's note could go further.** R3's blocker is fully stale, not half:
F9-foundation-scope-nomad-workloads-policy is `done` too.

**R4. Q1 and Q3 still defer work the plan could finish, and I am not blocking on
it.** My cycle-1 position stands and it was explicit that this is not a contract
violation: both forks carry a recommendation, which is what `CLAUDE.md` section
1 asks for. Q1's decisive fact (`CREATE ROLE`, `GRANT` and `ALTER ROLE ... SET
ROLE` are cluster-wide) is supplied in the question itself and the recommendation
is correct; Q3's open half is a fact about memex's config surface, not a
preference, and the plan already routes it to subticket 1. Leaving both as forks
costs the operator two confirmations and nothing else. It does not block.

---

## Contract hygiene

- **Code surface.** Every anchor outside §7's eight bare ones resolves. I
  re-checked the ones the rewrite touched or could have disturbed:
  `mlflow.hcl:38-41`, `database.tf:3-4`, `database.tf:10-40`,
  `services.tf:116`, `:171-183`, `:205-210`, `:300`,
  `docs/postgres-vault-dynamic-creds-spike.md:216-220`,
  `.loop/plans/R3-rollout-postgres-vault-db-creds.md:490-494`, plus the whole
  `database-secrets-poc.tf` set above. The §7 block is the single defect, and it
  is decay from `a21da6f`, not fabrication.
- **Gates.** Unchanged from cycle 1 and still exact: `justfile:17-19`,
  `.pre-commit-config.yaml:16-33`, `scripts/tf_validate.sh:8-12`.
- **Non-goals.** Explicit, and both ownership defects from cycle 1 are resolved
  in substance: R8 owns the root consumers and is real, ducklake is honestly
  unowned.
- **Tests homed.** Unchanged; eval 3 still closes S2's open half before any
  jobspec moves, and eval 5 still counts `pg_roles` rather than trusting
  `vault lease revoke`.
- **Forks surfaced.** Eight, each with a recommendation. Q2 is materially better
  than in cycle 1.

The plan is ready. Land F1 through F4 with the implementation.
