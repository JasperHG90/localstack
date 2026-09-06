---
verdict: pass-with-required-fixes
plan: fadb380c243b9f3c6072e5e1d999a15223ad02e53e93eb9d19ded3586077a3b9
bound_paths: front-matter, 5, 6, 7, 8, 9, 10, premises
scope: eb5ebffc4a22b25926589e1a82cb95b38d379400de53d4802a8f32dac513b0fc
fix_sections: front-matter, 7, premises
citations: .cache/uv/archive-v0/eeJ44k62p_14x8mw/lib/python3.12/site-packages/openviking/server/api_keys/legacy.py:440 =     async def begin_user_deletion(
  .cache/uv/archive-v0/eeJ44k62p_14x8mw/lib/python3.12/site-packages/openviking/server/api_keys/legacy.py:462 =             if user_info.get("role") == Role.ADMIN:
  .cache/uv/archive-v0/eeJ44k62p_14x8mw/lib/python3.12/site-packages/openviking/server/api_keys/legacy.py:467 =                 if active_admins <= 1:
  .cache/uv/archive-v0/eeJ44k62p_14x8mw/lib/python3.12/site-packages/openviking/server/api_keys/legacy.py:468 =                     raise FailedPreconditionError("Cannot delete the last active account admin")
  .cache/uv/archive-v0/eeJ44k62p_14x8mw/lib/python3.12/site-packages/openviking/server/api_keys/legacy.py:267 =     def resolve(self, api_key: str) -> ResolvedIdentity:
  .cache/uv/archive-v0/eeJ44k62p_14x8mw/lib/python3.12/site-packages/openviking/server/api_keys/legacy.py:318 =             raise AlreadyExistsError(account_id, "account")
  .cache/uv/archive-v0/eeJ44k62p_14x8mw/lib/python3.12/site-packages/openviking/service/user_deletion.py:136 =         if actor.role == Role.ROOT or (
  .cache/uv/archive-v0/eeJ44k62p_14x8mw/lib/python3.12/site-packages/openviking/service/user_deletion.py:147 =             deletion, created = await self._manager.begin_user_deletion(
  .cache/uv/archive-v0/eeJ44k62p_14x8mw/lib/python3.12/site-packages/openviking/server/routers/admin.py:159 =     if ctx.role == Role.ADMIN and ctx.account_id != account_id:
  .cache/uv/archive-v0/eeJ44k62p_14x8mw/lib/python3.12/site-packages/openviking/server/routers/admin.py:297 =     user_key = await manager.create_account(
  .cache/uv/archive-v0/eeJ44k62p_14x8mw/lib/python3.12/site-packages/openviking/server/routers/admin.py:302 =     await service.initialize_account_directories(account_ctx)
  .cache/uv/archive-v0/eeJ44k62p_14x8mw/lib/python3.12/site-packages/openviking/server/routers/admin.py:303 =     await service.initialize_user_directories(account_ctx)
  .cache/uv/archive-v0/eeJ44k62p_14x8mw/lib/python3.12/site-packages/openviking/server/routers/admin.py:379 = @router.delete("/accounts/{account_id}")
  .cache/uv/archive-v0/eeJ44k62p_14x8mw/lib/python3.12/site-packages/openviking/server/routers/admin.py:380 = @require_auth_root
  .cache/uv/archive-v0/eeJ44k62p_14x8mw/lib/python3.12/site-packages/openviking/server/routers/admin.py:394 =         await viking_fs._async_agfs.rm(f"/local/{account_id}", recursive=True)
  .cache/uv/archive-v0/eeJ44k62p_14x8mw/lib/python3.12/site-packages/openviking/server/routers/admin.py:623 = @router.post("/accounts/{account_id}/users/{user_id}/key")
  .cache/uv/archive-v0/eeJ44k62p_14x8mw/lib/python3.12/site-packages/openviking/server/routers/admin.py:632 =     """Regenerate a user's API key. Old key is immediately invalidated."""
  .cache/uv/archive-v0/eeJ44k62p_14x8mw/lib/python3.12/site-packages/openviking/server/api_keys/new.py:70 = def generate_api_key(account_id: str, user_id: str, seed: Optional[str] = None) -> str:
  .cache/uv/archive-v0/eeJ44k62p_14x8mw/lib/python3.12/site-packages/openviking/server/api_keys/new.py:198 =         # Generate new format key
  .cache/uv/archive-v0/eeJ44k62p_14x8mw/lib/python3.12/site-packages/openviking/server/api_keys/new.py:415 =         new_key = generate_api_key(account_id, user_id, seed)
  .cache/uv/archive-v0/eeJ44k62p_14x8mw/lib/python3.12/site-packages/openviking/server/api_keys/new.py:427 =         account.users[user_id]["key"] = new_stored_key
  .cache/uv/archive-v0/eeJ44k62p_14x8mw/lib/python3.12/site-packages/openviking/core/namespace.py:332 =     if target.scope in {"", "resources", "temp", "queue"}:
  .cache/uv/archive-v0/eeJ44k62p_14x8mw/lib/python3.12/site-packages/openviking/storage/viking_fs/_access.py:430 =     def _uri_to_path(self, uri: str, ctx: Optional[RequestContext] = None) -> str:
  .cache/uv/archive-v0/eeJ44k62p_14x8mw/lib/python3.12/site-packages/openviking/storage/viking_fs/_access.py:433 =         Pure prefix replacement: viking://{remainder} -> /local/{account_id}/{remainder}.
  .cache/uv/archive-v0/eeJ44k62p_14x8mw/lib/python3.12/site-packages/openviking/storage/viking_vector_index_backend.py:535 =                 account_filter = Eq("account_id", self._bound_account_id)
  .cache/uv/archive-v0/eeJ44k62p_14x8mw/lib/python3.12/site-packages/openviking/storage/viking_vector_index_backend.py:236 =             payload["account_id"] = self._bound_account_id
  docs/openviking.md:24 = ## Authentication: OpenViking's own users, behind a Vault gate
  docs/openviking.md:99 = **Taking a person away is not.** Deleting their line destroys their Vault entry
  docs/openviking.md:105 = ```console
  docs/openviking.md:109 =     "$OV_URL/api/v1/admin/accounts/lab/users/veerle"
  docs/openviking.md:112 = That call also starts durable cleanup of everything they own, which is why no
  docs/openviking.md:126 = revoked only by regenerating it.
  docs/openviking.md:155 = **Every flag writes the key to disk in the clear.** `--api-key-env` does not
  docs/openviking.md:185 = So Hermes holds jasper's key and writes into `viking://user/jasper`. Its
  docs/openviking.md:187 = the seed, which rotates jasper too. `viking://resources` is account-shared and
  docs/openviking.md:229 = `scripts/check_openviking_config.py` runs in pre-commit and asserts the nine
  docs/openviking.md:339 = every caller today borrows a person's key. Giving an agent its own is two lines
  deployments/applications/services.tf:566 =       [
  deployments/applications/services.tf:572 =         "code=$(curl -sS -o /dev/null -w '%%{http_code}' -X POST http://127.0.0.1:1933/api/v1/admin/accounts/${local.openviking_account}/users/${user}/key -H \"X-API-Key: $OV_ROOT_KEY\" ... )"
  deployments/applications/secrets.tf:273 =   openviking_account = "lab"
  deployments/applications/services/hermes.hcl:244 =   provider: "openviking"
  deployments/applications/services/openviking/ov.conf.json:61 =       "enabled": true
  .pre-commit-config.yaml:24 =         entry: terraform fmt -check -recursive
  scripts/check_openviking_config.py:5 = healthy-looking service would hide:
---

rebound-by: JasperHG90 2026-09-06 (reason: Cycle-4 required fixes RF-A/RF-B/RF-C applied inside the verdict's own fix_sections (front-matter, 7, premises): corrected the hallucinated symbol _request_user_deletion to begin_user_deletion in P10, added the offboarding-runbook and Hermes-memory rows the R6 deliverables were missing from section 7, and stopped the front-matter summary presupposing Q1 option (a). Recorded P13, the now-verified re-mint premise. Operator settled Q1 in favour of option (b).)

# Plan review — OV2-openviking-user-scoped-resources, cycle 4 (FULL)

Deterministic floor: `loopctl verify-plan OV2-openviking-user-scoped-resources`
returns `valid` with two provenance warnings only (Q1/Q2 measured against
package 0.4.17.1). No hard fail, so the semantic pass ran.

## Premise verdict

**PARTIALLY SOUND.** Every substantive claim in the bound sections is now
confirmed against the installed 0.4.17.1, including the three the briefing
singled out. One premise (P10) carries a hallucinated symbol name in its
evidence prose, which is the same defect class cycle 2 forced P4 to correct.
Two hygiene gaps remain in the bound sections. None of the three sinks the
plan.

## Per-assumption findings

- **P1 — HOLDS, no change in scope.** Not touched by this cycle's edits.
  Settled at cycle 1 (ledger OV2-F1) from the shipped Studio bundle:
  `useState("viking://resources/")` in `add-resource-page-*.js`. The
  wheel-versus-ghcr-image caveat stands and the plan's own
  `measured_against.Q1` records it.

- **P2 — HOLDS, no change in scope.** Settled at cycle 2 (OV2-F2);
  `webdav.py:73` and `app.py:630` re-read then and unchanged since.

- **P3 — HOLDS, no change in scope.** Settled at cycle 3 (OV2-F20) by
  `.loop/scratch/OV2-openviking-user-scoped-resources.plan-validator/p3_derive.py`.
  Re-confirmed incidentally this cycle:
  `.../openviking/server/api_keys/new.py:70`
  > def generate_api_key(account_id: str, user_id: str, seed: Optional[str] = None) -> str:
  The account is a base64 segment prepended to a secret that
  `derive_seeded_api_key_secret(user_id, seed)` computes without it, so only
  segment 1 moves.

- **P4 — HOLDS.** `.../openviking/storage/viking_fs/_access.py:430` and `:433`
  > def _uri_to_path(self, uri: str, ctx: Optional[RequestContext] = None) -> str:
  > Pure prefix replacement: viking://{remainder} -> /local/{account_id}/{remainder}.
  The symbol name is right this cycle (P4 records the earlier
  `_uri_to_agfs_path` error itself) and the docstring states the mapping on the
  cited line.

- **P5 — HOLDS, and now confirmed at the route rather than only in the
  manager.** `.../openviking/server/routers/admin.py:297`, `:302`, `:303`
  > user_key = await manager.create_account(
  > await service.initialize_account_directories(account_ctx)
  > await service.initialize_user_directories(account_ctx)
  and `.../openviking/server/api_keys/new.py:198`
  > # Generate new format key
  `NewAPIKeyManager.create_account` mints `generate_api_key(account_id,
  admin_user_id, seed)` — the NEW format, so the key the account-create call
  returns already carries the account segment R2 depends on. One call gives the
  account, its first ADMIN and both directory trees.

- **P6 — HOLDS, no change in scope.** `deployments/applications/secrets.tf:273`
  >   openviking_account = "lab"
  with the user map on the next line; no other declaration of who exists.

- **P7 — UNCERTAIN, correctly and deliberately.** `scripts/check_openviking_config.py:25`
  > This is the STATIC half. It does not measure whether the service accepts a key,
  No gate here runs a deployed OpenViking. The plan does not claim otherwise.
  Left UNCERTAIN; do not force a probe the author already disclaimed.

- **P8 — HOLDS, no change in scope.** Settled at cycle 2 (OV2-F9), anchors
  re-opened this cycle:
  `.../openviking/storage/viking_vector_index_backend.py:535`
  > account_filter = Eq("account_id", self._bound_account_id)
  and `:236`
  > payload["account_id"] = self._bound_account_id
  `:230-234` rejects a record whose `account_id` disagrees with the bound one,
  and `:56` declares `account_id` in the field list. Isolation by predicate,
  exactly as P8 says.

- **P9 — HOLDS; the RF-4 anchor fix landed but the new anchor is thin.**
  `deployments/applications/services.tf:566`
  >       [
  Line 566 is the opening bracket of the reconcile block; the substance is at
  `:567` ("THE RECONCILE STEP") and `:572` (the actual
  `POST .../users/${user}/key` curl). That is better than the blank `:576` this
  anchor used to carry, and it is inside the block it names rather than tens of
  lines away, so it supports. P9's real weight rests on `:550` ("Nothing here
  DELETES") and the two Vault paths at `secrets.tf:316`/`:335`, all of which
  resolve. Nothing here revokes a `lab` key. HOLDS.

- **P10 — BREAKS on its named symbol; the mechanism it claims is confirmed.**
  The claim is right and I re-demonstrated it through the whole call chain.
  The evidence line names a function that does not exist.
  `.../openviking/server/api_keys/legacy.py:440`
  > async def begin_user_deletion(
  P10's prose says "`_request_user_deletion` in `server/api_keys/legacy.py`".
  Probe:
  ```console
  $ uv run --with "openviking==0.4.17.1" python -c "..."
  has _request_user_deletion: False
  has begin_user_deletion   : True
  module-level _request_user_deletion: False
  substring "_request_user_deletion" in legacy.py source: False
  ```
  `grep -rn "_request_user_deletion"` over the whole wheel exits 1. This is the
  identical defect cycle 2 caught in P4 (`_uri_to_agfs_path`, ledger OV2-F6) and
  made P4 record; repeating it in P10 sends the implementer to grep a name that
  is not there. The quoted block at `:462-468` is verbatim correct, so only the
  symbol name is wrong. Required fix RF-A.

- **P11 (implicit, added) — HOLDS. The fence is unconditional on the caller
  across the whole chain, not just in the branch P10 shows.** This is the
  briefing's attack 2 and it is the one that could have overturned P10.
  `.../openviking/server/api_keys/legacy.py:462`
  > if user_info.get("role") == Role.ADMIN:
  `:467`
  > if active_admins <= 1:
  `:468`
  > raise FailedPreconditionError("Cannot delete the last active account admin")
  `begin_user_deletion` takes `owner_account_id` / `owner_user_id` and uses them
  only to populate the deletion record; there is no `force` parameter and no
  caller-role branch. One step up,
  `.../openviking/service/user_deletion.py:136`
  > if actor.role == Role.ROOT or (
  is the ONLY place ROOT is special-cased, and `:147`
  > deletion, created = await self._manager.begin_user_deletion(
  runs unconditionally afterwards: the ROOT branch picks the task-owner ids and
  does not skip the fence. `NewAPIKeyManager.begin_user_deletion` (new.py:325)
  is a pass-through to the legacy one, and `grep -rn begin_user_deletion` over
  the wheel finds exactly those four sites. So root gets no bypass. P10's
  "holding the root key does not get past it" is confirmed.

- **P12 (implicit, added) — HOLDS with one caveat worth a doc sentence.
  `DELETE /accounts/{account_id}` really does remove `/local/{account_id}`
  including `viking://resources`.** §5's replacement offboarding call is real.
  `.../openviking/server/routers/admin.py:379` and `:380`
  > @router.delete("/accounts/{account_id}")
  > @require_auth_root
  `:394`
  > await viking_fs._async_agfs.rm(f"/local/{account_id}", recursive=True)
  Combined with P4's `viking://{rest}` to `/local/{account_id}/{rest}` mapping,
  the recursive rm covers `viking://resources`, and the vector side is cascaded
  by `delete_account_data(account_id)` a few lines below. Caveat: that `rm` sits
  inside `try/except Exception` that only logs a warning, so the endpoint
  returns `{"deleted": True}` even when blob cleanup failed. §5's claim ("removes
  the whole account tree") is accurate for the happy path; R6's runbook prose
  should not promise the operator a confirmation the response does not give.
  Observation, not a required fix.

- **P13 (implicit, added) — HOLDS. Q1 option (b) works: a re-mint invalidates
  the previously issued key with `encryption.api_key_hashing` enabled.** This is
  the briefing's attack 1, and the plan marks it UNVERIFIED. It is now settled in
  favour of the plan's recommendation.
  `deployments/applications/services/openviking/ov.conf.json:61`
  >       "enabled": true
  (the `encryption.api_key_hashing` block at `:59-62`), so the stored value is an
  Argon2id hash.
  `.../openviking/server/routers/admin.py:623` and `:632`
  > @router.post("/accounts/{account_id}/users/{user_id}/key")
  > """Regenerate a user's API key. Old key is immediately invalidated."""
  `.../openviking/server/api_keys/new.py:415` and `:427`
  > new_key = generate_api_key(account_id, user_id, seed)
  > account.users[user_id]["key"] = new_stored_key
  The docstring is a claim, so I demonstrated it rather than trusting it. Scratch
  at `.loop/scratch/OV2-openviking-user-scoped-resources.plan-validator/p_remint_invalidates.py`,
  identical output on two clean runs:
  ```console
  hashing enabled            : True
  stored value is an argon2 hash: True
  old key prefix             : 'bGFi.dmV'
  BEFORE re-mint: old key resolves -> user lab veerle
  re-mint returned a different key: True
  new key prefix identical to old : True
  AFTER re-mint: old key REJECTED -> UnauthenticatedError: Invalid API Key
  AFTER re-mint: new key resolves -> user lab veerle
  re-mint is deterministic on the seed: True
  stored key after re-mint is the NEW hash: True | old key verifies against it: False
  ```
  Both resolution paths were checked, not just the fast one.
  `NewAPIKeyManager.resolve` decodes account/user from the key and verifies
  against `users[user_id]["key"]`, which now holds the new hash; on failure it
  falls through to `.../openviking/server/api_keys/legacy.py:267`
  > def resolve(self, api_key: str) -> ResolvedIdentity:
  whose prefix index had the old entry filtered out and the new one appended
  under the same prefix (the prefix is the first 8 chars, which are
  account+user-derived and therefore unchanged). No cache exists anywhere in
  that path: `auth/plugins/api_key.py` calls `resolve` directly with no
  memoization. The OAuth fast path returns immediately because `ov.conf.json`
  carries no oauth block (top keys are storage, embedding, rerank, vlm,
  query_planner, encryption, server) and `auth_mode` is `api_key`. `reload()`
  rebuilds from the persisted new hash with `allow_migration=False`, so a
  reload cannot resurrect the old key. The jobspec declares no `count`, so
  there is one allocation and no second in-memory index to lag. **Q1's
  recommendation (b) is correct and no longer needs the fallback to (a).**
  One wording gap, in §11 and therefore outside my bound: the recommendation
  says "keeping the result nowhere", but the key is deterministic in the SEED
  (`re-mint is deterministic on the seed: True` above), so the operator must
  discard the seed too, not only the returned key string. Corroborated by
  `docs/openviking.md:126`
  > revoked only by regenerating it.

- **P14 (implicit, added) — HOLDS. Creating account `jasper` while a user
  `jasper` already exists inside `lab` does not collide.** Load-bearing for R3
  and P5, and never checked before.
  `.../openviking/server/api_keys/legacy.py:318`
  > raise AlreadyExistsError(account_id, "account")
  The only uniqueness check is on the ACCOUNT id against `self._accounts`; users
  live nested in `AccountInfo.users`, so user ids are scoped per account. The
  provisioner reshape cannot 409 on a name that already exists under `lab`.

- **P15 (implicit, added) — HOLDS. `viking://resources` is unconditionally
  shared within an account, which is the premise the whole ticket rests on.**
  §5's "the hardcoded `return True` is not being fought" is accurate.
  `.../openviking/core/namespace.py:332`
  > if target.scope in {"", "resources", "temp", "queue"}:
  followed by `return True` on `:333`, before any owner comparison. The `user`
  scope below it at `:336-338` is the branch that DOES compare owner ids.

## Most dangerous assumption

**P13** — that Q1's recommended remedy actually closes the exposure. §5, §6 R6
and §9 all defer the whole residual-exposure problem to Q1 ("Q1 carries that
step"), so if a re-mint had left the old `lab` keys working, the ticket would
ship with its stated exposure uncontained and its docs telling the operator a
procedure that does nothing. It was the plan's only self-declared UNVERIFIED
claim. It is now demonstrated true, so the plan's most dangerous assumption is
the one that got settled this cycle.

## Contract hygiene

- **Code surface, anchors.** Every `path:line` in the bound sections resolves
  and supports. `docs/openviking.md:155` (RF-6) is right: it is the
  "**Every flag writes the key to disk in the clear.**" line, not the MinIO
  fork's `:213`. `secrets.tf:273/274/285/293/304/349/388` all land on the named
  local or resource. `services.tf:495/519/527/550/560` all support.
  `hermes.hcl:244` is `provider: "openviking"` under `memory:`.
- **Gates, discovered.** Confirmed against the repo, not habit.
  `.pre-commit-config.yaml:24`
  > entry: terraform fmt -check -recursive
  so §8 gate 1's added `-recursive` (RF-3) matches the hook verbatim.
  `scripts/tf_validate.sh:10` lists `deployments/applications`.
  `.pre-commit-config.yaml:100` is `openviking-config-guard-self-test`, and its
  `files:` regex matches an existing repo file, so `pre-commit run --all-files`
  really runs it. §8 gate 3's contradiction with §6 R7 (ledger OV2-F17) is gone.
- **Non-goals.** Explicit and now internally consistent; the §6 R6 "stranded"
  wording (OV2-F16) is gone.
- **Tests homed.** §8 names no new tests, only gates, and says so. No orphan.
- **Requirements reachable.** Every §6 requirement has a producer in §7. R6's
  offboarding clause is produced by the `docs/openviking.md:24` row, since the
  `## Authentication` section spans 24-132 and the runbook sits at 99-114; R6's
  Hermes clause is produced by the `docs/openviking.md:187` row, since that
  anchor sits inside the Hermes paragraph at 185-188. No
  `unmeasurable-requirement` fork is owed. But see RF-B: the two row NOTES do
  not mention either clause.
- **Forks surfaced.** Q1, Q2, Q3 each carry a recommendation. Q1's
  ledger-OV2-F22 defects are gone.
- **Reverse direction (advisory).** No §7 row is unreached by a §6 requirement.

## Required fixes

**RF-A — Premises, P10.** Replace `_request_user_deletion` with the real name
`begin_user_deletion`. `.../openviking/server/api_keys/legacy.py:440`
> async def begin_user_deletion(

The quoted `:462-468` block and the line numbers are correct and need no change;
only the sentence naming the function is wrong. Probe above shows
`hasattr(LegacyAPIKeyManager, "_request_user_deletion")` is `False` and the
string does not occur anywhere in the wheel.

**RF-B — §7, two docs rows.** R6 requires five things of `docs/openviking.md`;
§7's four row notes name four different things, and neither the offboarding
rewrite nor the Hermes-memory line is among them. Since the "every changed line
traces to the ticket" rule is checked against §7, a diff rewriting
`docs/openviking.md:99-114` is authorized by nothing an implementation reviewer
can read off the table. Extend the notes:
- `docs/openviking.md:24` — add the offboarding runbook. The block is at
  `docs/openviking.md:105`
  > ```console
  with the call itself at `:109`
  >     "$OV_URL/api/v1/admin/accounts/lab/users/veerle"
  and note that the rewrite reaches past the fenced block: `:99`
  > **Taking a person away is not.** Deleting their line destroys their Vault entry
  and `:112`
  > That call also starts durable cleanup of everything they own, which is why no
  both go stale with it, so the region is 99-114, not just the 105-110 fence.
- `docs/openviking.md:187` — add the Hermes empty-memory consequence R4 and R6
  both demand. `:185`
  > So Hermes holds jasper's key and writes into `viking://user/jasper`. Its
  is the paragraph that hosts it and the `:187` anchor is already inside it.

**RF-C — front-matter, `summary`.** The last clause presupposes Q1 option (a):

    Existing content in the lab account stays shared until an operator deletes it.

P13 settles Q1 in favour of option (b), which invalidates the keys and keeps the
content, so "deletes it" states one of three options as if it were the only one.
§9 already has the neutral phrasing ("until an operator step removes it", of the
exposure rather than the content). Match it. This is the same front-matter-lags-
the-body pattern RF-5 fixed last cycle (ledger OV2-F18).

## Observations, no fix required

1. **§2 "M" is still honest, but its clause undercounts the docs.** The added
   scope since cycle 3 is prose inside files §2 already names: the offboarding
   runbook is in the same `## Authentication` section §2 counts, the Hermes
   consequence is one sentence plus a Vault field already inside "three Vault
   writes", and Q1's block is contingent on an unanswered fork so it is not a
   deliverable. What §2 does undercount is breadth: it says "the docs section"
   (singular) while §7's four anchors fall in four different top-level sections
   (`## Authentication` at 24, `## Using it from the CLI` at 133,
   `## Verifying a deployment` at 227, `## What is not configured` at 336).
   Two Terraform files plus four doc regions is still M, not L. No fix.
2. **Q1's UNVERIFIED note can be discharged.** §11 is outside `bound_paths`, so
   this is not a required fix, but P13 settles it and the operator may want the
   caveat replaced with the probe result — plus the "discard the seed, not just
   the key" clause.
3. **`DELETE /accounts/{account_id}` swallows a failed blob cleanup** (P12).
   Worth one sentence in whatever runbook R6 writes for Q1 option (a).
4. **P9's `:566` anchor is the block's opening bracket.** Accepted, since the
   comment at `:567` and the curl at `:572` are inside the block it names.
   `:567` or `:572` would read better.

## Scratch

- scratch created at `.loop/scratch/OV2-openviking-user-scoped-resources.plan-validator/p_remint_invalidates.py`
- WARN — scratch artifact left at `.loop/scratch/OV2-openviking-user-scoped-resources.plan-validator/p_remint_invalidates.py`,
  retained deliberately beside the cycle-1..3 probe scripts so a later cycle can
  re-run the P13 demonstration. Diagnostic only.
- findings ledger updated at `.loop/scratch/OV2-openviking-user-scoped-resources.plan-validator/findings.json`.
