---
verdict: pass
tree: 551204861aafed3299a47115c7f4be7fd6a4e4e9
---

# Documentation-freshness review: S2-spike-postgres-vault-creds (cycle 3)

Pass id: documentation. Scope: the delta since cycle 2, which is one file,
`docs/postgres-vault-dynamic-creds-spike.md`. Both required fixes are
applied and both new claims check out against the code they describe.
Three of the four recommendations are taken. The fourth was answered by
execution rather than by an edit, which is the right call. Nothing in the
change leaves a reader of any repo doc wrong. Two cosmetic nits below,
neither worth a cycle.

## Required fix 1: the rebuild heading. Resolved, and the new claim is true.

`docs/postgres-vault-dynamic-creds-spike.md:322-326` now reads:

> **Rebuild what is standing.** This does NOT include the Nomad job, its
> `vault_policy` or its `vault_jwt_auth_backend_role`. `-target` pulls in a
> resource's dependencies, never its dependents, and the job depends on the
> role rather than the reverse, so it is excluded by construction as well as
> on purpose. To opt back into it, add
> `-target=nomad_job.s2_poc_dynamic_creds`.

Three separate claims, all correct.

The heading matches the command. The six targets at `:329-335` are exactly
the six live resources: `postgresql_role.s2_poc_admin`
(`database-secrets-poc.tf:95`), `postgresql_grant_role.s2_poc_admin_owner`
(`:119`), `vault_kv_secret_v2.s2_poc_admin` (`:133`), `vault_mount.database`
(`:145`), `vault_database_secret_backend_connection.postgres_poc` (`:155`),
`vault_database_secret_backend_role.poc` (`:196`). Five of them are the .tf
header's standing list (`:6-12`); the sixth, the grant, is the admin option
on the standing admin role, so "what is standing" covers all six. "All six
in ONE apply" at `:338` still counts right.

The dependency direction is right. `nomad_job.s2_poc_dynamic_creds` carries
`depends_on = [vault_database_secret_backend_role.poc]`
(`database-secrets-poc.tf:274`) and reads
`vault_jwt_auth_backend_role.s2_poc.role_name` (`:263`), which in turn reads
`vault_policy.s2_poc_db_read.name` (`:252`). Targeting the database role
therefore cannot pull the job in, exactly as the doc says.

The opt-in is minimal and complete. One `-target=nomad_job.s2_poc_dynamic_creds`
pulls the JWT role and the policy along with it, through the two references
above. The doc names one target and needs only one.

## Required fix 2: the "no file" clause. Resolved, without underselling.

`docs/postgres-vault-dynamic-creds-spike.md:6-9`:

> That credential is minted on demand and dies with its lease, so it exists
> in no Terraform state and no KV2 entry. It does reach the task as a
> rendered file, `secrets/db.env`, exactly as today's static passwords do:
> what changes is the credential's lifetime, not the delivery.

Checked against both anchors. `poc-dynamic-creds.hcl:37` is
`destination = "secrets/db.env"` with `env = true`, and `:99` is the same
for the pool task. `memex.hcl:44-60` is the static pattern: a `vault {}`
block and a `template { destination = "secrets/file.env", env = true }`
rendering `.Data.data.username` and `.Data.data.password`. Same delivery
mechanism, different lifetime. The sentence now says that.

It does not undersell. The two claims it keeps are the ones the diff
supports: nothing durable holds the minted credential, and the file that
does hold it dies with the alloc. Dropping the third differentiator costs
the paragraph nothing, because the lifetime claim was always the load-bearing
one.

## Recommendations taken

**SQL fencing and placement.** The `ALTER ROLE` block is now ```sql at
`:122-125` and carries `-- in the Vault role's creation_statements,
alongside the CREATE ROLE and GRANT`, which matches
`database-secrets-poc.tf:201-205` (CREATE ROLE, GRANT, ALTER ROLE, in that
order). The revoke check at `:316-318` is also tagged `sql`, `:313-314` names
who runs it ("as `localstack`, not as the user you just revoked"), and `:320`
states the expected answer ("Zero means the revoke really took"). That is more
than I asked for and all three additions are correct.

**`<secret_mount>` resolved.** `:396-397` gives both the placeholder and
`secret/default/postgres/vault-dbengine-admin` for this cluster.
`deployments/applications/vars/prod.tfvars:1` sets `secret_mount = "secret"`
and `database-secrets-poc.tf:134-135` composes the rest, so the concrete path
is right and the placeholder is still there for anyone on a different mount.

**Semicolon splice gone.** `:400-402` is now two sentences. A scan of the
whole file for prose semicolons outside fences returns only the two Path B
table cells, which stay.

## Recommendation not taken, correctly

The `docker run --rm -e PGPASSWORD=<password> postgres:18 psql ...`
workaround at `:291-293` is unchanged. My cycle-2 objection was that it was
the doc's one unmeasured command; the adversarial pass then ran it. Executing
it answers the objection better than a hedge in the doc would have, and adding
"untested" after someone tested it would have been false. Leaving the line as
a plain instruction is right. It is a devcontainer aside, not a finding, so it
does not need the date stamps the findings carry.

## Slop scan, all three layers, re-run over the changed prose

Layer 0: no identity leaks, no `TODO`/`FIXME`/`XXX`/`HACK`. Every backticked
identifier in the new lead and the new runbook paragraph resolves:
`secrets/db.env` (`poc-dynamic-creds.hcl:37,99`),
`nomad_job.s2_poc_dynamic_creds` / `vault_policy` /
`vault_jwt_auth_backend_role` (`database-secrets-poc.tf:259,216,231`),
`secret/default/postgres/vault-dbengine-admin` (`prod.tfvars:1` plus
`database-secrets-poc.tf:135`), `pg_roles`, `localstack`, `-target`.

Layer 1 (economy): 6/6, unchanged. The lead still states the takeaway in its
first sentence. The added delivery sentence instances the thesis rather than
repeating it, and the runbook paragraph replaces a wrong heading with a
correct one plus the reason, at a cost of three lines.

Layer 2 (sentences), whole file at 2714 words: zero em dashes, zero ` -- `,
zero smart quotes, zero tier-1 slop, zero British spellings, no
self-narration, no spatial copula, no significance cluster, no throat-clearing
opener, no participial tail, trailing newline present. Prose wraps at 80. The
nine over-length lines are seven table rows, one URL and one line inside a
captured-output fence (`:90`, `:250-253`, `:257`, `:366-368`), none of which
can wrap.

## Re-confirmed

**No other repo doc drifted.** Only one file changed since cycle 2. I
re-swept the doc tree for anything that would now be wrong: `docs/` has no
index that enumerates pages, `README.md:30` points at `docs/` in prose
without a list, `README.md:36` ("everything lives in Vault KV2") stays true
of the one long-lived password this spike leaves behind, and
`docs/credential-rotation.md` is scoped to `TAILSCALE_AUTH_KEY` and
`GITHUB_PAT` and says nothing about database credentials.

**The honesty admissions are still real.** "What this does not settle" at
`:136-143` still names the untested half of failure mode 4 and still matches
what the job asserts (`poc-dynamic-creds.hcl:45-57`: a `SELECT` on a
memex-owned table plus a create/insert/select/drop round-trip on a scratch
table, no `UPDATE`, `DELETE` or `ALTER TABLE` on an app-owned object). "Not
established within the time box" at `:267-270` is untouched. The new lead
softened neither.

**The .tf header still documents the config-vs-live drift.**
`database-secrets-poc.tf:6-12` names the five standing resources including
the KV2 entry, `:14-19` names the three destroyed-but-declared resources and
the consequence, `:21-30` gives the undo command with its `CONSUL_HTTP_TOKEN`
prefix and the exact error you get without it, `:32` names the end state. The
doc's runbook and this header now agree on which set is which, which is the
thing cycle 2 broke.

**The `replace_triggered_by` comment is still accurate.**
`database-secrets-poc.tf:111-118` is unchanged and my cycle-2 analysis stands:
`depends_on` orders the role and the grant only when both are in the plan,
`replace_triggered_by` forces the grant's re-creation when a later apply
touches the role alone, and bumping `s2_poc_admin_password_version` (`:53`) is
exactly that case.

## Cosmetic nits (no action needed)

1. **`secrets/db.env` reads as if it were shared** (`:8`). The PoC renders to
   `secrets/db.env` (`poc-dynamic-creds.hcl:37`); memex renders to
   `secrets/file.env` (`memex.hcl:58`). "exactly as today's static passwords
   do" modifies the mechanism, not the filename, and the sentence is true as
   written. A reader skimming could take the path as common to both.
2. **"what changes is the credential's lifetime, not the delivery"** (`:9`)
   is a trailing contrastive negation. Here the contrast is load-bearing: it
   exists to block the misreading the previous version invited. Keep it.
