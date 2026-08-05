---
verdict: pass
tree: 61ee8563babbf5b7f3c3d7b15dfd974db0157a15
---

# Documentation freshness — R6-rollout-memex-human-oidc (review cycle 3)

Supersedes the `ab6a6950…` verdict. The one required fix from cycle 2 (RF1,
the supersession note's wrong row ordinals) landed and is correct. The four
changes the adversarial pass made are correct and none of them introduced a
new stale claim. Every documented surface this diff touches was updated in
step. **pass.**

## Binding

`61ee8563babbf5b7f3c3d7b15dfd974db0157a15` resolves to a real tree in this
repo. `git diff --name-only 61ee8563… -- docs deployments cli bootstrap
scripts` is **empty**: every file I reviewed under `docs/` and
`deployments/` matches the given fingerprint byte for byte
(`docs/memex-oidc-verification.md` = `1c52e9cf…`, `docs/vault-human-auth.md`
= `8ac81b10…`, `docs/cluster-roles.md` = `e729056e…`).

Scope note, so the record is honest: the fingerprinted tree carries only
`.loop/config.json` under `.loop/`. The two artifacts this cycle asked me to
check hardest — the R5 supersession note and the R6 eval — are **outside**
the fingerprint. I reviewed them at their working-tree content:

- `.loop/archive/R5-rollout-memex-oidc-auth/eval.md` = `b3858c8d…`
- `.loop/evals/R6-rollout-memex-human-oidc.md` = `38be1993…`

## RF1 is fixed, and fixed correctly

**Evidence:** `.loop/archive/R5-rollout-memex-oidc-auth/eval.md:36`, `:38`,
`:43`.

I re-enumerated the signed table independently rather than trusting the
correction. The table is `:13` header, `:14` separator, `:15`-`:24` ten data
rows: 1 S1, 2 W1(hermes token accepted), 3 D1, 4 D2, 5 H1, 6 H2, 7 H3, 8 S2,
9 G1, 10 G2.

- `:36` **Row 1 (S1)** — `:15`, asserts `(1 provider(s))`. Correct.
- `:38` **Row 4 (D2)** — `:18`, "the server log emits NOTHING for this
  request. A silent 403 is the pass". Correct, and this is the row whose
  polarity v1.2.0 inverts.
- `:43` **Row 9 (G1)** — `:23`, "exactly ONE element" and "no
  `vault_identity_oidc_client`". Correct.

Row 10 (`:24`, G2 "static API keys survive") is **not** named, which is the
outcome that mattered: R6 preserves that invariant on purpose (§5; runbook
G1 at `docs/memex-oidc-verification.md:372-373`; eval row at
`.loop/evals/R6-rollout-memex-human-oidc.md:28`), and the old pointer sent a
reader there under the heading "now false about the live system".

The signed rows are byte-unchanged: the diff on this file is 23 insertions
and zero deletions, all below the sign-off at `:26`.

**Nothing else in the note misleads a mid-incident reader.** Each bullet
still carries its label in parentheses and quotes the row's content, so the
pointer and the quote now agree instead of contradicting. The closing at
`:46-49` routes the reader to `.loop/evals/R6-rollout-memex-human-oidc.md`
and `docs/memex-oidc-verification.md` and forbids fixing the runbook
backwards, which is the right instruction now that the pointers are right.

One timing seam I checked and am not flagging: `:36-37` says "the live count
is `2`", which is true after R6 applies, not at this commit. The whole doc
set is written in that tense (runbook S1 at `:33-38` asserts `2` as well),
the note is dated in its own header, and it points at the R6 runbook before
asserting anything. Consistent, so a reader is not sent in two directions.

## V1's precondition: clear, correctly placed, and impossible to skim past

**Evidence:** `docs/memex-oidc-verification.md:260-279`.

The decode step at `:260-263` now ends with "**`groups` does NOT contain
`app-memex-admins`**" in bold, as the last of four assertions, so the
discriminator is inside the step that produces the token rather than
appended after the result.

The paragraph at `:265-269` explains why, and it explains the right thing:
the resting state after this ticket puts the operator in both tiers, so a
later re-run resolves to `admin` and the write is not refused. I checked
both halves of that claim:

- Q8 is settled to END 1, both tiers
  (`.loop/plans/R6-rollout-memex-human-oidc.md:1256`, `:1264-1267`,
  `:1273-1274`), so "the resting state … puts the operator in BOTH tiers" is
  accurate rather than aspirational.
- "as this runbook's header tells you to after any memex auth deploy" is a
  true self-reference: `:6-8` says run these after a deploy touching the
  memex auth config, the hermes `identity` stanza, the hermes image, or the
  Vault OIDC client.

The write bullet at `:272-279` is scoped rather than absolute: "**Given a
reader-only token**, anything else means the tier resolved ABOVE `reader`",
and it closes "If the token carries `app-memex-admins`, this is V5, not V1."
That is the sentence that stops the misread in the other direction, and it
sits at the end of the bullet the reader is acting on.

The check is safe in both states of `local.app_user_group_members`. At the
shipped state (`deployments/infrastructure/roles.tf:175-177`, readers only)
V1 passes as written; after V5's edit the precondition fails first and names
V5 as the right check. That is what a precondition is supposed to do.

**Placement holds up to a skim.** Reading only the bold in V1 gives: log
into the Vault UI first / `groups` does NOT contain `app-memex-admins` /
Given a reader-only token, anything else means the tier resolved above
reader. Those are the three things that make the `403` readable.

## The other three adversarial fixes

- **V5's eval row now matches the runbook's polarity.**
  `.loop/evals/R6-rollout-memex-human-oidc.md:24` expects **NOT** `403`, with
  "A `404`/`422` from the handler is the PASS: the write gate let the request
  through, and the uuid is fabricated so nothing mutates." That agrees with
  the runbook (`docs/memex-oidc-verification.md:349-353`) and with plan §8 V5
  (`:731-737`). The earlier "Succeeds" would have failed a correct system,
  since the runbook's own probe uses a fabricated uuid.
- **W1's eval row is complete.** `:19` now carries `| Deterministic (HTTP
  status + dict key equality) | 100% |`. Machine-counted: every data row has
  five cells (`:17`'s sixth is the escaped `\|` inside the `grep` command,
  which renders as five). "Sixteen rows" at `:7` matches `:17`-`:32`.
- **`roles.tf:140-142` no longer claims the map ships empty.** Now "F2 built
  the extension point and shipped it empty; memex (R6) is its first
  consumer." True against `:162-163`. The downstream comment at `:159-161`
  was updated in the same breath to point at `app_user_group_members`
  "below", and the map is in fact below it (`:174-178`).

## No new stale claim, and the four surfaces you named still hold

- **D2 polarity.** `docs/memex-oidc-verification.md:150-175` states the flip,
  names v1.2.0, gives the two discriminator lines (D1 vs D2) explicitly, and
  says silence is now a FAILURE. Matches the eval row (`:27`) and the
  supersession note (`:38-42`). No contradiction between the three.
- **Revocation.** `docs/memex-oidc-verification.md:391-412` and
  `docs/vault-human-auth.md:397-432` still lead with the condition before the
  lever, and both match the resource comment at
  `deployments/infrastructure/memex_oidc.tf:25-30`. The runbook states the
  lever unqualified because it is memex-specific and memex owns a dedicated
  key (`memex_oidc.tf:31-36`); the general doc carries the "only for a client
  on its OWN key" qualifier for future consumers. That split is correct, not
  drift.
- **The config snippet.** Byte-identical in both homes
  (`docs/memex-oidc-verification.md:241-247`,
  `docs/vault-human-auth.md:439-445`), and its `issuer` matches
  `local.vault_oidc_issuer` at `deployments/applications/services.tf`
  character for character, which is the value that must not drift or provider
  selection by `iss` fails.
- **Mandatory `scopes`.** Present in both snippets, enforced in prose at
  `docs/vault-human-auth.md:446-448` ("`scopes` MUST include `groups`"), and
  exercised live at `docs/memex-oidc-verification.md:323-337` (V4) and
  `.loop/evals/R6-rollout-memex-human-oidc.md:23`.

Also re-checked and clean: every Terraform identifier the docs name resolves
(`vault_identity_oidc_key.memex_human` / `memex-human` at 7d/30d,
`memex_oidc.tf:31-36`; `local.app_user_group_members`, `roles.tf:174-178`;
`member_entity_ids = lookup(...)`, `roles.tf:189`). `docs/cluster-roles.md`
`:140-158` matches the code it now documents, including the "authoritative,
not additive" sentence against the resource comment at `roles.tf:187-188`.
`docs/workload-identity.md:213-218` describes the Nomad audience registry
only, untouched by R6 as §5 requires. Nothing else under `docs/` documents a
surface this diff moves. Zero em dashes added across the docs diff.

## Standing advisories: none has become a defect

1. **`deployments/infrastructure/oidc.tf:122`** still says "The map ships
   empty" above a two-entry map, and `:21` says the same. Both are now false
   as stated. Still **not** a defect: the instruction each supports survives
   the new state. `:122`'s imperative ("CONCAT, never replace") stays
   correct, because a replacement now drops the smoke group id rather than
   writing `[]` — same broken client, different mechanism — and the
   DO-NOT-COPY comment at `:126-129` blocks the wrong action independently.
   §5 confines this file to the one-line append at `:79-84`, so raising it to
   a required fix would collide with the ticket's own non-goal. Follow-up.
2. **`oidc.tf:118`** calls the smoke assignment the "First consumer of the
   app-user extension point" while `docs/cluster-roles.md:3-4` now says memex
   is its first consumer. Two senses of "consumer" (proving the mechanism vs.
   owning a tier). Same §5 scope. Follow-up with nit 1, one edit.
3. **`docs/memex-oidc-verification.md:42` is 82 columns**, two over the prose
   wrap. Still the only prose line over the limit in the changed set.
4. **The D2 tail** (`:168-170`) attributes silence to "a signature or issuer
   problem", which is also reachable via the unparseable-JWT path. Unchanged
   and still not a defect: the fix in every case is "read which line DID
   fire", which the discriminator list directly above already instructs.
5. **`docs/vault-human-auth.md:277`**, the "so" that carries a causal link it
   does not quite earn. Cosmetic.
6. **New, lowest priority:** `.loop/evals/R6-rollout-memex-human-oidc.md:12-13`
   states the Q8 resting membership (both tiers) in the preamble, while row
   `:20` correctly scopes V1 to "entity in `app-memex-readers` only". Both are
   right at their own point in the sequence, and the runbook now spells the
   ordering out at `:265-269`, so this reads as sequence rather than
   contradiction. No fix wanted.
7. **Also new, optional:** no doc links `docs/memex-oidc-verification.md`.
   `docs/vault-human-auth.md`'s new memex section would be its natural
   inbound. Pre-existing (nothing linked it before R6 either), so it is not
   drift this diff caused and I am not requiring it.

## Verdict

**pass.** RF1 is fixed and the corrected pointers survive an independent
re-enumeration of the signed table. V1's precondition is accurate, placed
inside the step that produces the token, bold, and paired with a scoped write
bullet that names V5 by name. V5's and W1's eval rows now match the runbook.
No new stale claim was introduced, and every documented surface this diff
touches was updated in step.
