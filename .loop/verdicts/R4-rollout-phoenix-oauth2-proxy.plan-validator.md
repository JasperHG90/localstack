---
verdict: pass
plan: 197712ffb6a1b96f9b60f52114bbb32d08ed9d07819bb3df239b76a6dd4cda01
---

# R4-rollout-phoenix-oauth2-proxy — seventh pass (confirmation)

**Premise verdict: SOUND.**

Narrow pass, as briefed. The sixth pass returned SOUND with three one-line
fixes, all in §2. This pass checks that those three edits are factually right,
that no other section still carries the fact they corrected, and that the §2
rewrite does not fight its own "Small" opening. It opens no new line of attack
on settled substance.

## Deterministic floor

`loopctl verify-plan R4-rollout-phoenix-oauth2-proxy` returns `valid`, with
only the pre-existing `warn: ambiguous file basename 'secrets.tf' /
'services.tf'` notices carried from earlier passes. Plan sha256 on disk matches
the briefed fingerprint `197712f…4cda01`.

## Per-check findings

- **C1 — "two secrets in KV2" is the right count. HOLDS.** §2:33-35 now reads
  "**two** secrets in KV2 (`PHOENIX_SECRET` and `PHOENIX_ADMIN_SECRET` …)".
  This agrees with every other site that names the provisioned set: §7:325-329
  (`applications/secrets.tf:11-16` — "`random_password` + `vault_kv_secret_v2`
  for `PHOENIX_SECRET` and `PHOENIX_ADMIN_SECRET` only"), §10 step 4:484-488
  ("**Not the OIDC client secret**"), and §6 requirement 4:244-251 (both
  values, both `random_password`, both with the complexity floor). Nothing else
  in the plan provisions a KV2 value: §10 step 5's memex header reuses "the
  same Vault secret Phoenix reads" (§7:391-395), and `CLIENT_ID` arrives by the
  cross-root `data` lookup (§7:387-390), not KV2. The parenthetical's second
  clause is also correct on the merits: on the public-client route Vault issues
  no secret (§7:330-357), matching Q5:544-558.
- **C2 — the anchor behind the HAProxy edit resolves, and §2 now agrees with
  §6 and §9. HOLDS.** `deployments/infrastructure/services/haproxy.hcl:143` is
  literally `http-request auth unless { http_auth(openfang_users) }` under
  `backend phoenix` at `:142`, with `server phoenix1 192.168.2.29:6006 check`
  at `:144`; mlflow's twin is at `:153`; `backend memex` (`:146-147`) and
  `backend bifrost` (`:156-157`) are bare `server` lines. So §2:35-36's "one
  deleted HAProxy line (`haproxy.hcl:143`, per requirement 3 and §10 step 8)"
  is right, and both pointers resolve: §6 requirement 3 is at :241-243 and §10
  step 8 at :510-511. §9:448 ("no HAProxy path-splitting") is not a
  contradiction — it denies the old proxy design's path split, not the auth
  line — and §9:446 ("restore the basic-auth line and the edge gate returns")
  presumes the deletion.
- **C3 — the P15 wording is now accurate at both sites. HOLDS.** §2:41-43 and
  §4:91-93 both say verified against the deployed container on 2026-08-04 with
  §10 step 1 re-checking it, matching P15:729-734 (`VERIFIED 2026-08-04` …
  "§10 step 1 still re-checks it, since the image tag can move") and §10 step
  1:453-459, which does order that container check. The stale §4 sentence
  ("Treat the capability as unverified against the deployed build") is gone:
  the only surviving `unverified` in the plan is Q4:541, about minting a scoped
  system key, which is a different and correctly-open question.
- **C4 — full-plan sweep for the three facts. CLEAN.** Every `three` in the
  file (:64, :159-160, :256, :311, :362, :408, :670, :731, plus the dated
  review history) refers to something else: the three email-claim gaps, the
  three further `oidc.tf` edits, the three dead-end secret routes, the three
  Terraform roots. No live site asserts three secrets. Every HAProxy mention
  (:110-118, :224-226, :241-243, :396-398, :496, :510-511, P8:689-693) says the
  same thing: delete `:143`, leave `:153`. No live site asserts an uncertain
  P15; the only remaining `UNCERTAIN` premise is P14:722-727, which is honestly
  open and checked by §10 step 7.
- **C5 — "Small" survives the rewrite. HOLDS.** Both items the rewrite added
  are configuration: a one-line deletion in `haproxy.hcl` and Terraform
  resources in `oidc.tf`. §2 still opens "Configuration only on both sides" and
  closes "No new job, no proxy, no application code", all of which remain true.
  Naming the HAProxy deletion makes the sizing more honest, not less: the work
  was already binding via requirement 3 and step 8, it was simply absent from
  the paragraph an implementer sizes from.
- **C6 — the edits introduced nothing. HOLDS.** The cumulative diff of §2
  against `HEAD` contains exactly the three described changes and no other edit
  to that section, which is consistent with the sixth pass's finding that §2
  was otherwise byte-identical to the pre-review 2026-07-26 draft.

## Most dangerous assumption

C1, the secret count. It is the one edit that could re-seed the failure §7
spends a paragraph preventing: an implementer hunting for a client secret that
does not exist on the recommended route. It is confirmed correct against
§7:325-329 and §10 step 4:484-488, and the parenthetical names the route
explicitly rather than leaving the reader to infer it.

## Non-blocking note (no fix required)

`:783`, inside the dated `### 2026-08-04 — required fixes applied` changelog
entry, still reads "now an explicit UNCERTAIN (P15) verified at step 1". That
is a record of what that pass did, and the two later dated entries (`:836`,
`:925`) walk it forward to verified, so the history is self-consistent as
history and no live section is affected. Left alone deliberately: dated
changelog entries are a record, not a standing claim.

## Required fixes

None. The three edits are correct, they agree with §6 requirement 3, §7, §9,
and §10 steps 4 and 8, and no other section carries the stale form of any of
the three facts. The plan is ready to leave `PLANNING`.
