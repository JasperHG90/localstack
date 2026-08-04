---
verdict: pass
plan: 13cac3f463ba3788888052f297cbad09ac9f9b0c2ab35153c2430bc13c6cdaca
---

# Plan review — R7-rollout-postgres-consumer-cutover (`plan-validator`, cycle 3)

`sha256sum .loop/plans/R7-rollout-postgres-consumer-cutover.md` returns
`13cac3f463ba3788888052f297cbad09ac9f9b0c2ab35153c2430bc13c6cdaca`, matching the
briefing. `loopctl verify-plan R7-rollout-postgres-consumer-cutover` returns
`valid` (exit 0). `deployments/applications/database-secrets-poc.tf` is still
`a21da6f`, 330 lines, clean in `git status`, as the briefing states.

## Premise verdict: SOUND

Gate verdict: **pass**.

Scoped pass, per the briefing: cycle 2's SOUND premise is not re-derived. All
four required fixes landed. I re-checked F2 independently rather than taking the
author's word, since that was the fix most likely to be subtly wrong. It is
right.

---

## Required fixes from cycle 2, verified

**F1 — Q8 contradicted §5. FIXED.** Q8 (`:725-735`) now reads "RESOLVED
2026-08-04 — `R8-rollout-postgres-root-consumers` owns the `localstack` root
consumers", names the stub path, and states it `depends_on` R7 and is not in
R7's own `depends_on`. All three claims check out:
`.loop/plans/R8-rollout-postgres-root-consumers.md` front-matter carries
`depends_on = ["R7-rollout-postgres-consumer-cutover"]` and `stub = true`, and
`loopctl ledger` shows `R8-rollout-postgres-root-consumers: stub [epic: rollout]
[priority: 3] deps: R7-... (1 unmet)` while R7's own deps line names only R3.
§5 (`:144-147`) and Q8 now agree, and the parenthetical records which side was
wrong.

**F2 — eight §7 anchors on pre-`a21da6f` numbering. FIXED, all eight verified.**
I printed the first and last lines of each range against the committed file:

| §7 claim | Opens at | Closes at |
|---|---|---|
| the admin role (`:145-153`) | `resource "postgresql_role" "s2_poc_admin" {` | `}` at `:153` |
| the admin-option grant (`:172-182`) | `resource "postgresql_grant_role" "s2_poc_admin_owner" {` | `}` at `:182` |
| the write-only KV2 secret (`:188-198`) | `resource "vault_kv_secret_v2" "s2_poc_admin" {` (`disable_read = true` at `:191`) | `}` at `:198` |
| the mount (`:200-204`) | `resource "vault_mount" "database" {` | `}` at `:204` |
| the connection (`:210-224`) | `resource "vault_database_secret_backend_connection" "postgres_poc" {` | `}` at `:224` |
| the DB role (`:251-264`) | `resource "vault_database_secret_backend_role" "poc" {` | `}` at `:264` |
| the dedicated policy (`:271-279`) | `resource "vault_policy" "s2_poc_db_read" {` | `}` at `:279` |
| the dedicated JWT role (`:286-310`) | `resource "vault_jwt_auth_backend_role" "s2_poc" {` | `}` at `:310` |

Every range brackets its resource exactly, and every resource is the shape §7
names it. No second miss.

**F3 — §7's hand-extend clause. FIXED.** `:356-361` now reads "ONLY IF
requirement 3's discovery shows the minting admin does not already cover the
owner role, extend its grantable set", cites
`deployments/applications/database-secrets-poc.tf:75` (verified:
`s2_poc_grantable_owners = distinct([for db in local.databases : db.owner])`),
says the likely correct edit is none, and warns against hand-adding names to a
computed list. That matches requirement 3 (`:205-244`) and subticket 2
(`:603-610`).

**F4 — Q8's anchor. FIXED.** `:731` now cites
`deployments/applications/database-secrets-poc.tf:78-82`, which is the comment
naming the exporter, `backup-postgres`'s pg_dumpall and the root's own
`postgresql` provider as the three consumers rotation would take down. Correct,
and consistent with §5 `:143`.

## New edits introduced nothing

The author's own sweep found `(`:94-151`)` in the bifrost bullet (`:392`) and
left it. Confirmed correct: `bifrost.hcl` is 159 lines, `:94` is `template {`,
`:151` its closing `}`, `:134` is `"host": "env.PG_HOST"` and `:137` is
`"password": "env.PG_PASSWORD"`.

I also re-checked the remaining bare anchors in §7's jobspec bullets, since bare
forms were the cycle-2 failure pattern: `memex.hcl:44` and `:114` are both
`vault {}`; `:52`/`:55` and `:132`/`:135` bracket the two
`${memex_postgres_secret}` blocks; `:124-127`, `:139-141` and `:156` are the
MinIO, auth-key and Bifrost-key blocks §7 says to leave alone. All resolve.

## Most dangerous assumption

Unchanged from cycle 2 in kind but no longer live: §7 is now a usable map of
`database-secrets-poc.tf`. What remains most dangerous is R3's output, which
does not exist yet — the plan handles that correctly by making requirement 1
discovery rather than a hardcoded list (`:190-198`).

## Recommendations for the implementer (not binding, no fourth cycle)

1. **The anchors are still written bare.** Correct, but without the filename
   prefix, so `verify-plan` still cannot parse them and the next reviewer must
   read the bullet's lead to know the file. Add the prefix if you touch §7.
2. **P15's anchor is still off by a block.** `:857` cites
   `database-secrets-poc.tf:262-263` for the renewal claim; those two lines are
   `default_ttl = 120` / `max_ttl = 300`. The claim's support is the comment
   above the resource. P15 already labels itself partly UNCERTAIN, so this is
   cosmetic.
3. **"S2 measured" still overstates `:78-82`** at `:140` and `:730`. That
   comment reasons from three named consumers; it records no measurement. Say
   "S2 recorded".
4. **R3's blocker is fully stale, not half.** `loopctl ledger` shows R3 blocked
   on both "S2 never ran" and "F9 owns the same policy"; both halves are stale.
   The note at `:639-644` names only the first.
5. **Q1 and Q3 stay forks and still do not block.** Settled twice; unchanged.

## Contract hygiene

Every anchor I opened this pass resolves. Gates, non-goals, homed tests and
surfaced forks are unchanged from cycle 2 and were clean there. The plan is
ready.
