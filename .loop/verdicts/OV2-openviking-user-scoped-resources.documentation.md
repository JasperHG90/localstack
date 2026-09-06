---
verdict: pass
tree: e93b785de6317a53444963f577fb653507be41f2
---

# Documentation-freshness review — cycle 2

Scope binding omitted deliberately. The briefing carried no 64-hex scope
digest, and the harness this pass runs under
(`loop-harness/1.9.0/scripts/loopctl.py`) computes none: `grep -n
"scope\|bound_paths"` over its scripts and hooks returns nothing. Per the
brief, the three lines are omitted and the verdict falls back to the
stricter whole-tree binding. The reviewed path set was
`docs/openviking.md`, `deployments/applications/secrets.tf`,
`deployments/applications/services.tf`, `.loop/ledger.json`.

Both required fixes are applied and correct. Every documented surface this
change touches was updated in the same diff. Four advisories below, none
of which leaves a reader wrong about a behavior this change altered.

## RF-1 — verified

`deployments/applications/secrets.tf:385` = `### openviking_people would give it its own ACCOUNT, whose viking://resources is`
`deployments/applications/secrets.tf:386` = `### shared with nobody -- which is the same isolation stated above, arriving by`

The false claim is gone and the replacement is true. `openviking_people`
is a `toset` and `openviking_accounts` maps `user => user`, so a line added
for an agent mints an account whose `viking://resources` resolves to
`/local/<agent>/resources` and is shared with nobody. Consistent with both
places I cited at cycle 1:

- `docs/openviking.md:268` = ``viking://resources` is still shared by every identity in an account, but an`
- `docs/openviking.md:427` = `in `local.openviking_people`, which would also give it its own account. That is`

Comment, code and doc now say one thing.

## RF-2 — verified, shell correct, nothing else leaks in the section

`docs/openviking.md:175` = `    curl -sS -o /dev/null -w "$u %{http_code}\n" -X POST \`
`docs/openviking.md:177` = `      --data-binary @/tmp/ov-remint.json \`
`docs/openviking.md:180` = `$ rm -f /tmp/ov-remint.json`

`-o /dev/null` is load-bearing, not decoration: against openviking 0.4.17.1,
`server/routers/admin.py:640` returns
`Response(status="ok", result={"user_key": new_key})` unconditionally, and
`-o /dev/null` discards the body on every status, so no key can reach the
terminal.

The shell is correct. `umask 077` completes before the redirect in the `&&`
list, so `/tmp/ov-remint.json` is created 0600. `printf` is a shell builtin
and `openssl rand` writes to stdout, so the seed enters no process argv and
no shell-history line carries a literal seed. `--data-binary @file` matches
`RegenerateKeyRequest(seed: str | None = None)` at `admin.py:80-81`. `-w`
takes `$u` from the shell and `%{http_code}` from curl, so the loop prints
`jasper 200` and nothing else. The backslash continuations join into a
valid `for ... do ... done`.

The supporting claims hold. `docs/openviking.md:190` = `The old keys stop working immediately: the server stores an Argon2id hash of`
matches the route docstring "Old key is immediately invalidated" and
`legacy.py:607`, which replaces the stored hash. The reversibility claim
holds too: `new.py:415` mints via `generate_api_key(account_id, user_id,
seed)`, which is deterministic, so re-minting with a kept seed restores
access.

Nothing else in the section prints a secret. No `echo`, no `cat`, no
unredirected body.

## Advisories

### A1 (low) — the provisioner cross-reference is half true

`docs/openviking.md:187` = `an argv secret is readable from `ps` for the life of the call. The provisioner`
`docs/openviking.md:188` = `beside this does both for the same reasons.`

The provisioner does the `-o /dev/null` half. It does not do the argv half.
It stages the seed in a 0600 file (`services.tf:533`) and sources it
(`services.tf:535` = `        ". /tmp/ov-prov.env",`), then expands
`$OV_SEED` straight into curl's `-d` argument at `services.tf:558` and
`services.tf:573`, where the shell puts it in argv before `execve` and `ps`
can read it. The runbook's `--data-binary @file` is strictly stronger than
the model it cites.

Not a required fix: the sentence faithfully restates the provisioner's own
comment, `services.tf:528` = `        # Credentials go in a 0600 file rather than on the command line: an`,
so the doc is consistent with the repo it documents and the inaccuracy is
pre-existing in that comment. It is worth naming because a reader who
follows the pointer sees the argv form and concludes the inline shape is
house style, which is the exact "improvement" the paragraph exists to
block. One clause fixes it: the provisioner stages both credentials in a
0600 file but still expands them into curl's argv.

### A2 (low) — the root key is still in argv in the same command

`docs/openviking.md:176` = `      -H "X-API-Key: $ROOT_KEY" -H 'Content-Type: application/json' \`

The block moves the throwaway seed out of argv and leaves the most
privileged credential in the system in it, under a paragraph that says argv
secrets are readable from `ps`. Pre-existing idiom, used identically in the
offboarding block at `docs/openviking.md:146`, and curl has no clean
header-from-file equivalent. Worth a scoping clause, not a rewrite.

### A3 (low) — one of the three wraps is not fixed, and RF-1 added a fourth

`docs/openviking.md:429` = `its principal's data at all. What may hold one is the open`
`docs/openviking.md:430` = `question.`

58 + 1 + 9 = 68, under 80, so `question.` belongs on the line above. The
other two are genuinely fixed: `docs/openviking.md:152` is now a full 78
chars, and `docs/openviking.md:106` = `without rotating any secret. The derivation is`
at 46 chars is a legitimate greedy wrap, because the next token is a
39-character inline code span that would push it to 86.

RF-1 introduced one new instance of the same class:
`deployments/applications/secrets.tf:387` = `### a second route. The cost is real and accepted: Hermes's writes are indistinguishable from`
is 93 characters where every other comment line in that block sits at
78-79. The inserted sentence was not re-wrapped. No gate covers this; the
stamped `just pre_commit` passed at this tree.

### A4 (low) — prose scan residues

Clean on em dashes (the single hit, `docs/openviking.md:419`, is
pre-existing context), ` -- ` in markdown prose (both hits pre-existing),
smart quotes, tier-1 slop, British spellings, self-narration, "not
only/not just", the significance cluster, spatial copulas, emphasis
crutches, three-fragment bursts, and 80-char wrap outside code fences and
table rows.

Two residues. Contrastive negation appears seven times in the added set
(`secrets.tf:273`, `secrets.tf:287`, `docs/openviking.md:52`, `:137`,
`:140`, `:183`, `:274`). Most are load-bearing, since the ticket itself is
"account, not user". The one that is decorative is
`docs/openviking.md:183` = `Two details in that block are the point of it, not decoration. `-o /dev/null``.
And `deployments/applications/secrets.tf:279` = `  # URI as a literal in server Python; neither consults`
is a semicolon splice, where the parallel sentence in the doc,
`docs/openviking.md:64`, correctly uses a period. Both are
surface-do-not-auto-rewrite categories.

## Settled findings not touched by this cycle's edits

- DOC-6 — no change in scope, still holds. Re-checked cheaply anyway:
  `scripts/check_openviking_config.py` still has exactly 15 `found.append`
  calls, `docs/openviking.md:315-321` still enumerates 15 values, and the
  checker's "twelve settings" docstring lists exactly 12 setting entries,
  three of which assert two values each. Two units, both correct.
- DOC-7 — no change in scope, still holds. Repo-wide grep across `.tf`,
  `.hcl` and `.md` for `openviking_account`, `openviking_admin_user` and
  `openviking_users` finds only `resource "null_resource"
  "openviking_users"` at `services.tf:502`, a resource name that is
  correctly unchanged.
- DOC-8 — no change in scope, still holds. `docs/openviking.md:137-153`
  was not edited this cycle; the offboarding reasoning is not re-derived.

## Also confirmed from the briefing

The `lab` CLI profile rename is complete. `docs/openviking.md:230` = `$ printf '%s' "$OV_KEY" | ov config add custom --name orangecluster \`,
and a repo-wide grep for `--name lab` returns nothing. Every surviving bare
`lab` is the Vault OIDC provider, the DNS zone, or the OpenViking account
under discussion.

The key table's Root row is accurate. `docs/openviking.md:46` = `| Root | the job, from Vault | none | ROOT | accounts, and re-minting any user's key |`.
`regenerate_key` is `@require_auth_root_or_admin` and calls
`_check_account_access`, which root passes for any account, so root does
re-mint any user's key. The row claims no exclusivity, which is right:
an ADMIN re-mints within their own account, and that is covered by
"everything in their own account" on the two person rows.

No other doc in the repo went stale. `deployments/applications/services/openviking/README.md`
carries no account or user content, and the Hermes skills reference
`viking://user/jasper/...`, a path this change does not move.
