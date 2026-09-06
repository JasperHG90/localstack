---
verdict: pass
tree: e93b785de6317a53444963f577fb653507be41f2
---

# Adversarial review, cycle 2 — OV2-openviking-user-scoped-resources

## Scope binding

This verdict carries no `bound_paths:` / `scope:` / `citations:` lines. My
briefing supplied the tree fingerprint but no scope digest, and I may only
write a digest I was given, never one I computed. The verdict therefore falls
back to whole-tree binding, which is stricter. For the record, the reviewed
diff touches exactly three paths:

    deployments/applications/secrets.tf
    deployments/applications/services.tf
    docs/openviking.md

## Deterministic floor

`loopctl verify --expect-tree e93b785de6317a53444963f577fb653507be41f2` exits 0
in this checkout, so I am standing where I was asked to stand.

`loopctl verify-eval-substance OV2-openviking-user-scoped-resources` returns
`valid` with one `warn:` — the plan-drift advisory. No HARD-FAIL. Proceeded to
the semantic pass.

Gate re-run by me at this tree, not trusted from the hand-off: `just pre_commit`
→ 27 hooks, all `Passed`, exit 0. The cycle-1 trust stamp was keyed to
`b700cbc0`, so it did not apply; I re-ran and re-stamped
`.loop/scratch/OV2-openviking-user-scoped-resources.adversarial/trust-stamp.json`
to `e93b785d`.

## Re-attack on cycle-1 settled findings

**OV2-ADV-M1 (the one required fix) — FIXED, and the description is correct.**

`deployments/applications/services.tf:481 = ### Creates one OpenViking account per person through the Admin API.`
replaces "Registers the account and its humans", and
`deployments/applications/services.tf:488 = ### One POST per person and that is the whole registration: POST /accounts`
replaces the paragraph that named the deleted user POST.

I checked every clause of the new text against upstream v0.4.17.1 — the same
version the job pins at `deployments/applications/services.tf:455`
(`openviking_image = "ghcr.io/jasperhg90/openviking:v0.4.17.1-1"`):

- "creates the account, makes admin_user_id its first user with role admin":
  `openviking/server/api_keys/new.py` builds
  `user_info = {"role": "admin", ...}` and a `UserKeyEntry(..., role=Role.ADMIN)`
  for `admin_user_id`, then writes both JSON stores.
- "and initializes both directory trees": `openviking/server/routers/admin.py`
  `create_account` calls `initialize_account_directories(account_ctx)` and
  `initialize_user_directories(account_ctx)` back to back.
- "409s on an existing account WITHOUT touching any key": the existence check
  (`raise AlreadyExistsError(account_id, "account")`) precedes every mutation
  in `new.py`; only the local `generate_api_key` runs before it, and that stores
  nothing.

**One nuance, an observation rather than a finding.**
`deployments/applications/services.tf:497 = ### 409 as success, because the account existing is the desired state. The key`
through
`deployments/applications/services.tf:500 = ### server. The trigger is the account map plus the seed, so adding a person or`
attributes "it still runs after a 409" to the key step being "a SEPARATE list
element, not chained to that case guard". The structural fact is true —
`concat()` emits it as its own string, so `remote-exec` puts it on its own line.
But the mechanism that actually carries the behavior is that the `409` arm of
the `case` is an empty `;;` returning 0, so `set -e` never fires; a call chained
into the same element with `;` would run too. The preceding sentence ("treats a
409 as success") supplies that half, so the paragraph read whole is correct. No
fix asked for.

**OV2-ADV-L1 — FIXED.** "viking://resources stays shared either way" is gone.
The replacement at `deployments/applications/secrets.tf:383-389` is accurate:
Hermes reads and writes inside jasper's own account, and a separate line in
`openviking_people` would give it an account whose `viking://resources` is
shared with nobody. The fix did introduce one new low, L6 below.

**OV2-ADV-L2 — FIXED.** `deployments/applications/services.tf:555 =       ],`
is immediately followed by
`deployments/applications/services.tf:556 =       [`. The stray blank line
inside `concat()` is gone. Cycle-1's
`.loop/scratch/.../render/main.tf:26-27` preserves the old shape for comparison.

**OV2-ADV-L3 — PARTIALLY FIXED. The second half did not land.** The "leaked,"
wrap is fixed; `docs/openviking.md:150-153` now wraps normally. The other one
does not:

    docs/openviking.md:429 (58 chars) = its principal's data at all. What may hold one is the open
    docs/openviking.md:430 ( 9 chars) = question.

Folding "question." up gives a 68-character line, well inside the 80 the rest of
the file keeps. The hand-off said this was fixed; it was not. Severity is
unchanged from cycle 1 — cosmetic, no gate covers prose wrapping — so this does
not block. I name it because a claimed fix that did not land is worth one line
in the record.

**OV2-ADV-L4 — FIXED and accurate.**
`docs/openviking.md:46 = | Root | the job, from Vault | none | ROOT | accounts, and re-minting any user's key |`.
Verified: `create_account`, `list_accounts` and `delete_account` all carry
`@require_auth_root` in `routers/admin.py`, while `regenerate_key` carries
`@require_auth_root_or_admin` and its `_check_account_access` helper only fences
`Role.ADMIN` (`if ctx.role == Role.ADMIN and ctx.account_id != account_id`), so
root does reach any user's key. Both halves of the new cell are true.

**OV2-ADV-L5 — FIXED.** `docs/openviking.md:106-107` reads "The derivation is /
`secret = sha256(user_id + NUL + seed)`." No dangling "It is".

**OV2-ADV-A1 (plan-drift advisory) — UNCHANGED, and the cycle-1 bound still
holds.** The marker still records `plan: 48bf33716dc2…` and the plan file still
hashes to `adb12eafa7ab4153857c8cf2c53e8a58a948045211b38179329d4e5ac462925d` —
byte-identical to what I measured in cycle 1, so the plan did not move again
between cycles and no row can have drifted further. I re-read the marker's nine
rows against the current plan: row 9's premise (Q1, re-mint over delete) matches
plan line 13's `premise = { Q1 = "…re-minting its keys from a discarded seed,
preserving the content and staying reversible, over deleting the account
outright" }`, and the runbook the doc now carries is exactly that. This is an
advisory, not a defect; I cannot clear it, because `loopctl eval-rebind` refuses
inside a linked worktree by design. **Operator action: clear it from the primary
checkout with `loopctl eval-rebind --counter-signer` before the commit.**

One small thing the check cannot see: the eval's row-9 prose cites
`docs/openviking.md:155` for the "`ov config add` writes it to disk in the
clear" sentence. That anchor resolved at sign-off time (it is line 155 at HEAD)
and this diff pushed the sentence to line 164. Prose context, not a `Fails-when`
cell, so nothing to fix.

**OV2-ADV-V1 — no change in scope, still holds.** Escaping, 409 idempotency plus
the unconditional key reconcile, key derivation with no secret rotation, the
rewritten offboarding call, the fifteen-value count and scope discipline were
all demonstrated in cycle 1. I did not take that on trust: I extracted the two
`code=$(curl …)` strings from
`deployments/applications/services.tf:558` and `:573` and diffed them
mechanically against the ones cycle 1 rendered and dry-ran in
`.loop/scratch/.../render/main.tf`. The diff is empty. The evidence carries
forward intact.

## New work verified this cycle

**RF-2, the `lab` close-out runbook — correct and safe. Verified by running
it.** I extracted `docs/openviking.md:171-180` verbatim, stripped the `$`
prompts, and executed it under `bash` with a recording `curl` shim on PATH, an
ambient `umask 022`, and no network. Artifacts are in
`.loop/scratch/OV2-openviking-user-scoped-resources.adversarial/runbook/`.

- **Nothing leaks.** stdout was exactly `jasper 200` / `veerle 200`. The shim
  returned a body containing `"user_key":"SUPERSECRETNEWKEY"` and `-o /dev/null`
  swallowed it.
- **The seed never enters argv.** The shim recorded
  `--data-binary @/tmp/ov-remint.json` for both calls. The seed also stays out of
  shell history, because the command line carries the unexpanded
  `"$(openssl rand -hex 24)"`.
- **The file is created before the loop, at mode 600, and removed after.** The
  shim stat'd it as `mode=600` on both calls despite my `umask 022`, which
  confirms the `umask 077 && printf … > file` ordering is right: the redirection
  is performed when `printf` runs, after the umask took effect. `/tmp/ov-remint.json`
  was absent after the block.
- **`%{http_code}` is the right form here.**
  `docs/openviking.md:175 =     curl -sS -o /dev/null -w "$u %{http_code}\n" -X POST \`
  is a plain console block, so the single `%` is correct; the Terraform-escaped
  `%%{http_code}` that `services.tf:558`/`:573` need is correctly not used.
  `$u` interpolates and curl converts the literal `\n`.
- **The stated reason is the real reason.** `regenerate_key` in
  `openviking/server/routers/admin.py` ends
  `return Response(status="ok", result={"user_key": new_key})` with **no**
  `_should_expose_user_key` guard, unlike `create_account`, which does gate its
  `user_key` on that helper. So the endpoint returns the new key unconditionally
  and `-o /dev/null` is load-bearing, exactly as
  `docs/openviking.md:183-185` says. The Argon2id claim at `docs/openviking.md:190`
  also checks out (`PasswordHasher` in `api_keys/legacy.py`, and
  `regenerate_key`'s own docstring: "Old key is immediately invalidated").

Two low observations on that block, neither worth a fix: `umask 077` runs in the
operator's interactive shell and persists for the session, where the
provisioner's copy runs in a throwaway script; and if a curl fails partway the
operator may stop before the separate `rm -f` line, leaving the 0600 seed file
behind. The block is copy-pasted whole in practice, so both are marginal.

**The profile rename — clean.** `docs/openviking.md:230` is the only `--name` in
the file and now reads `orangecluster`. I grepped the whole repo for `ov config`
and for profile names: nothing outside `.loop/` artifacts names an `ov` CLI
profile at all, so the collision with the `lab` account the same doc tells you
to close is gone with no loose ends.

**Scope — every changed line traces.** All three paths and every hunk map to the
plan's §7 code-surface table or to eval row 9's demand for the Q1 runbook. No
reference to the deleted `openviking_account`, `openviking_users` map or
`openviking_admin_user` locals survives anywhere outside `.loop/` plan and
verdict text, which describe the pre-state and are correct to. The one surviving
`openviking_users` token is the resource NAME at
`deployments/applications/services.tf:502 = resource "null_resource" "openviking_users" {`,
left alone deliberately so the Terraform address does not churn — the right
call, and the header comment above it now describes what it does.

**Doc gates.** One em dash in the whole file and it is on an untouched line. The
two ` -- ` prose hits (`docs/openviking.md:239`, `:382`) are both pre-existing
and outside the diff. No tier-1 slop in any added line.

## Findings

| id | severity | anchor | status |
|---|---|---|---|
| OV2-ADV-M1 | was required | `deployments/applications/services.tf:481,488` | fixed, verified against upstream |
| OV2-ADV-L1 | low | `deployments/applications/secrets.tf:383-389` | fixed |
| OV2-ADV-L2 | low | `deployments/applications/services.tf:555-556` | fixed |
| OV2-ADV-L3 | low | `docs/openviking.md:429-430` | **partially fixed — "question." still orphaned** |
| OV2-ADV-L4 | low | `docs/openviking.md:46` | fixed |
| OV2-ADV-L5 | low | `docs/openviking.md:106-107` | fixed |
| OV2-ADV-L6 | low, new | `deployments/applications/secrets.tf:387` | 93-char comment line, the only `###` line over 80 in the file; the L1 fix packed text without re-wrapping |
| OV2-ADV-A1 | advisory | `.loop/evals/OV2-openviking-user-scoped-resources.md` | plan-drift, unchanged, bounded; operator clears with `eval-rebind` from the primary checkout |

Nothing blocking. The required fix landed and its new text is true against the
pinned upstream. The runbook rewrite is correct and I proved it by running it.
Two cosmetic lows remain (L3's leftover, L6's long line); fix them or don't.

**verdict: pass**
