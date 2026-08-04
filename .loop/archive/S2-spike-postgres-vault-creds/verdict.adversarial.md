---
verdict: pass
tree: 551204861aafed3299a47115c7f4be7fd6a4e4e9
---

# Adversarial review, cycle 3: S2-spike-postgres-vault-creds

Deterministic floor: `loopctl verify-eval-substance S2-spike-postgres-vault-creds`
returns `valid` (exit 0). `loopctl verify` returns `ok`, and
`.loop/stamp.json` carries `551204861aafed3299a47115c7f4be7fd6a4e4e9`, the
fingerprint I was given and reviewed against.

Gate re-run by me: `just pre_commit`, exit 0, all 14 hooks `Passed`.

**Scope, measured rather than taken on trust.** Both fingerprints are real git
tree objects, so I diffed them directly:

```
$ git diff --stat 1628ba9d453fa8e2ec4012873baf075fb5637393 551204861aafed3299a47115c7f4be7fd6a4e4e9
docs/postgres-vault-dynamic-creds-spike.md | 28 ++++++++++++++++++++--------
1 file changed, 20 insertions(+), 8 deletions(-)
```

One file, and the 28 changed lines are exactly the six edits the hand-off
claims. Nothing else moved: no Terraform, no jobspec, nothing under
`bootstrap/`, no adjacent static-credential code.

R1 is closed by measurement. Both nits are closed. Both documentation fixes and
the three low recommendations are applied and correct. Three low
recommendations remain, none blocking.

---

## 1. R1, the rebuild heading. CLOSED, and the new prose is true

`docs/postgres-vault-dynamic-creds-spike.md:322-326`:

> **Rebuild what is standing.** This does NOT include the Nomad job, its
> `vault_policy` or its `vault_jwt_auth_backend_role`. `-target` pulls in a
> resource's dependencies, never its dependents, and the job depends on the role
> rather than the reverse, so it is excluded by construction as well as on
> purpose. To opt back into it, add `-target=nomad_job.s2_poc_dynamic_creds`.

I re-ran both plans this cycle against live state, read-only, `-lock=false`:

```
$ terraform plan <the six targets exactly as printed at :329-336>
No changes. Your infrastructure matches the configuration.

$ terraform plan <the same six, plus -target=nomad_job.s2_poc_dynamic_creds>
  # nomad_job.s2_poc_dynamic_creds       will be created
  # vault_jwt_auth_backend_role.s2_poc   will be created
  # vault_policy.s2_poc_db_read          will be created
```

The first plan is the proof of the exclusion claim. All three resources are
currently absent from the cluster (`vault policy read s2-poc-db-read` and
`nomad job status s2-poc-dynamic-creds` both fail), so if the six-target command
reached them the plan would say "will be created". It says "No changes".

The second plan is the proof of the opt-in claim: one extra target restores all
three, so "add `-target=nomad_job.s2_poc_dynamic_creds`" is sufficient, not
merely necessary.

The dependency direction the prose asserts is also right in the code.
`nomad_job.s2_poc_dynamic_creds` references
`vault_jwt_auth_backend_role.s2_poc.role_name`
(`deployments/applications/database-secrets-poc.tf:263`) and carries
`depends_on = [vault_database_secret_backend_role.poc]` (`:274`); the JWT role
in turn references `vault_policy.s2_poc_db_read.name` (`:252`). The job is a
dependent of the six, never a dependency, which is exactly what the sentence
says.

**No overcorrection.** The heading now matches what the command does: the file's
own "left running" list (`:389-397`) is the mount, the connection, role
`s2-poc`, the `vault-dbengine-admin` role and its KV2 password, and the six
targets are precisely those five (the grant being part of the admin role). "on
purpose" is backed by `database-secrets-poc.tf:14-19`, which calls recreating
the job "not what anyone asked for". The doc does not overreach into telling the
reader never to rebuild it; it gives the one-flag opt-in.

## 2. N1, the revocation check. CLOSED

`:311-320` now says to run the `pg_roles` count as `localstack` rather than as
the just-revoked user, and adds "Zero means the revoke really took". The
instruction is correct in both branches: if the DROP failed, the revoked user
still authenticates and would give a false clean reading; if it succeeded, a
fresh connection with it is refused. Either way the check needs a different
identity. One imprecision remains, recorded as REC1 below, not a fix.

## 3. N2, the semicolon splice. CLOSED

`:400-402` is now two sentences. My splice scan over the doc, code fences and
inline code stripped, returns only two hits, both table cells at `:250-253`
whose semicolons separate fragment lists rather than independent clauses. Those
predate this cycle and I passed them twice.

## 4. Documentation fix, the lead. VERIFIED AGAINST BOTH JOBSPECS, and it does not underclaim

`:6-9`:

> That credential is minted on demand and dies with its lease, so it exists in no
> Terraform state and no KV2 entry. It does reach the task as a rendered file,
> `secrets/db.env`, exactly as today's static passwords do: what changes is the
> credential's lifetime, not the delivery.

Both halves check out against the code:

- `deployments/applications/services/poc-dynamic-creds.hcl:38-39` renders the
  minted credential to `destination = "secrets/db.env"` with `env = true`.
- `deployments/applications/services/memex.hcl:58` and `:180` render today's
  static KV2 password to `destination = "secrets/file.env"` with `env = true`.

Same mechanism, same place, same `env = true`. "exactly as today's static
passwords do" is accurate, and the previous claim ("exists in no file") was
genuinely wrong. The surviving "no Terraform state and no KV2 entry" half is
still true: nothing in the root reads `database/creds/*`, and I re-measured the
state below.

**Does it now underclaim?** Not materially. The sentence pair keeps the
state-and-KV2 claim intact and scopes the concession to delivery. What
"lifetime" flattens is recorded as REC2, a wording nit rather than a lost
result. The contrastive form ("what changes is X, not Y") is on the slop list,
but the contrast is load-bearing here (it exists to stop the exact misreading
that the delivery changes) and survives the exception in the rule.

## 5. The three low documentation recommendations. ALL CORRECT

- **`sql` tag and placement comment** (`:122-125`). The comment says the
  statement goes "in the Vault role's `creation_statements`, alongside the CREATE
  ROLE and GRANT". `database-secrets-poc.tf:201-205` has exactly those three
  statements in that order, and the live role confirms it:
  `vault read database/roles/s2-poc` prints
  `[CREATE ROLE "{{name}}" ...; GRANT "memex" TO "{{name}}"; ALTER ROLE "{{name}}" SET ROLE "memex";]`.
- **`<secret_mount>` resolved** (`:396-397`).
  `deployments/applications/vars/prod.tfvars:1` sets `secret_mount = "secret"`,
  and `vault kv get -mount=secret default/postgres/vault-dbengine-admin` returns
  a 32-character password. `secret/default/postgres/vault-dbengine-admin` is the
  right resolution for this cluster.
- **The splice**, covered above.

## Regression checks, re-confirmed this cycle

No code changed, so these are cheap re-measurements rather than a fresh suite.

- **Write-only chain intact.** `terraform state pull` is 240,057 bytes and the
  32-character KV2 admin password appears **0 times** in it.
  `postgresql_role.s2_poc_admin`: `password ""`, `password_wo null`,
  `password_wo_version "2"`, `roles ["memex"]`.
  `vault_kv_secret_v2.s2_poc_admin`: `data null`, `data_json null`,
  `data_json_wo null`, `data_json_wo_version 2`, `disable_read true`.
  `postgresql_grant_role.s2_poc_admin_owner`: `with_admin_option true`. The
  doc's "over 233 KB" is accurate (234.4 KiB).
- **`replace_triggered_by` unchanged.** `database-secrets-poc.tf:124-126` is
  byte-identical to the tree I proved it on in cycle 2 (the file did not appear
  in the tree diff). The scratch-copy experiment that showed it firing on a
  `s2_poc_admin_password_version` bump stands.
- **`bootstrap/` untouched.** `git diff --numstat bootstrap/`, `git status
  --porcelain bootstrap/` and `git diff --numstat <old-tree> <new-tree> --
  bootstrap/` all return zero lines. Eval row 5's hard condition holds.
- **All nine eval rows.** Rows 1 to 3 re-read live: `plugin_name
  postgresql-database-plugin`, `allowed_roles [s2-poc]`, connection `username
  vault-dbengine-admin` with `rotation_period 0s`, role `default_ttl 2m` /
  `max_ttl 5m`. Row 4's `ALTER ROLE ... SET ROLE` is present in the live role's
  `creation_statements`, so the finding the row turns on is current; the
  measured run at `:66-82` is untouched by this delta. Row 5's two halves hold
  (`bootstrap/` clean; the job and policy are destroyed exactly as `:404-407`
  says). Rows 6 to 9 are doc rows: the one-token section (`:180-194`), the pool
  characterization (`:145-178`), Path B with citations (`:234-270`) and the
  falsifier plus recommendation (`:16-27`, `:357-385`) are all outside the
  delta and unchanged.
- **Residue.** As `vault-dbengine-admin` against firebat: `pg_roles like 'v-%'`
  returns `NONE` and `pg_tables like 's2\_%'` returns `NONE`. The doc's
  teardown claim at `:404-407` holds, and my own cycle-2 probes left nothing
  behind. That query also re-exercises the runbook's docker `psql` path and the
  KV2 credential, both of which work as written.
- **Scope.** `git status --porcelain` shows the three ticket files, the harness
  ledger, and the two verdict files. Nothing else.

## Slop scan on the changed doc, passes

2,714 words. 0 em dashes, 0 ` -- ` substitutions, 0 tier-1 slop, 0
self-narration, 0 "not just / not only", 0 British spellings, 0 smart quotes, 0
TODO/FIXME/XXX/HACK. Layer 0: every path and identifier the new prose names
resolves, and I executed the commands. The nine lines over 80 characters are
Path B and Recommendation table rows, one bare URL, and one line inside a
captured Nomad event block, all unwrappable.

---

## Findings, all low, none blocking

### REC1 — LOW — the revoke check's justification sits in mild tension with the doc's own pool finding

`:313-314` explains the "run it as `localstack`" advice with "the user you just
revoked, whose connection the revoke is meant to have destroyed". The doc's own
rotation section (`:160-163`) establishes that PostgreSQL authenticates once at
connection time, so an *already open* session survives its role being dropped;
only a *new* connection is refused. "meant to" hedges it, and in the runbook's
own flow (`docker run --rm ... psql -c`) every invocation is a new connection,
so the advice is right. Two clauses would tighten it: say the fresh connection
is refused, and name where `localstack`'s password lives, since a reader
following the runbook holds a minted credential and not that one. The
`vault-dbengine-admin` identity, whose password the doc already names at
`secret/default/postgres/vault-dbengine-admin`, is the identity actually in
hand; it is what I used.

### REC2 — LOW — "the credential's lifetime" is narrower than the real delta

`:9`. Beyond lifetime, the credential is also unique per task rather than one
long-lived password shared by every consumer, and its source moves from a KV2
entry to the database engine. The neighbouring sentence carries the KV2 half, so
nothing is lost to a reader of the whole lead, but "lifetime" alone
under-describes the change if the sentence is quoted on its own.

### REC3 — LOW — "All six in ONE apply" reads slightly off after the opt-in

`:338`. A reader who takes the `-target=nomad_job.s2_poc_dynamic_creds` opt-in
at `:326` is running seven targets. The sentence clearly refers to the block as
printed, and the one-apply constraint it explains applies to the three
password-writing resources regardless. Cosmetic.

---

## Verdict

**pass.** The one required fix from cycle 2 is closed, and I closed it by
measurement rather than by reading: the six targets as printed plan to "No
changes" against a cluster where all three excluded resources are absent, which
is only possible if the command genuinely does not reach them, and adding the
single job target brings all three back, which is what the opt-in line promises.
The new prose is true in both directions and does not overcorrect.

The documentation pass's lead fix is the more interesting one, and it checks out
against the code on both sides: the PoC renders `secrets/db.env` and memex
renders `secrets/file.env`, both with `env = true`. The old "no file" claim was
wrong; the new one is right and does not give back the state-and-KV2 result.

Everything I passed by measurement across two cycles still holds: the admin
password appears zero times in a 240 KB state file, `bootstrap/` is untouched by
every measure, all nine eval rows stand, and the cluster carries no residue from
the spike or from my probes. The three remaining items are wording, and the
brief is right that they do not justify blocking a spike whose findings are
already measured. R3 can absorb REC1 when it writes the real runbook.

*Review notes: every terraform call this cycle was a plan with `-lock=false`,
never an apply. I minted no Vault credentials this cycle; the two Postgres
queries ran as `vault-dbengine-admin` and were read-only. I edited no repo file
and ran no mutating git command.*
