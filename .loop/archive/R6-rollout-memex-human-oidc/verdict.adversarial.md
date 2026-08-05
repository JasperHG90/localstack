---
verdict: pass
tree: 61ee8563babbf5b7f3c3d7b15dfd974db0157a15
---

# Adversarial review, cycle 3: R6-rollout-memex-human-oidc (pass id: adversarial)

Bound to `61ee8563babbf5b7f3c3d7b15dfd974db0157a15`. This supersedes the
`ab6a6950…` verdict.

Deterministic floor: `loopctl verify-eval-substance R6-rollout-memex-human-oidc`
returns `valid`. Proceeded to the semantic pass.

Gates re-run independently in this worktree:

- `just pre_commit` — all 14 hooks pass, including `Terraform Validate (per
  root)`, `Terraform Format` and `Nomad Format`.
- `loopctl verify` — `ok`. `.loop/stamp.json` records tree
  `61ee8563babbf5b7f3c3d7b15dfd974db0157a15`, matching the fingerprint I was
  given.
- `loopctl eval R6-rollout-memex-human-oidc` — `valid`.

## The four required fixes: all landed, all correct

**1. W1's eval row is whole.** Splitting every row on unescaped pipes only,
all sixteen rows plus the header and separator carry exactly five cells.
W1 now reads `Deterministic (HTTP status + dict key equality)` / `100%`
(`.loop/evals/R6-rollout-memex-human-oidc.md:19`). The one row with an
escaped `\|` inside a code span (`:17`) still splits to five.

**2. V5's polarity is right, and I checked it against the server, not the
prose.** The eval row (`:24`) now expects NOT `403`, names `404`/`422` from
the handler as the pass, and adds the `groups`-carries-both-tiers assertion.
The runbook matches (`docs/memex-oidc-verification.md:339-358`).

I verified the mechanism upstream rather than trusting the premise block:

- `PATCH /notes/{note_id}/title` declares
  `dependencies=[Depends(require_write)]`
  (`memex v1.2.0 packages/core/src/memex_core/server/notes.py:370`), and
  FastAPI solves route-level dependencies before it validates the body, so
  a `reader` gets `403` regardless of what the probe sends and an `admin`
  reaches the handler and fails on the fabricated uuid. Both directions
  hold.
- `_claims_to_context` iterates `provider.grant_rules` and `break`s on the
  first match (`…/server/oidc.py`), so listing `app-memex-admins` at index 0
  is what makes a dual member resolve to `admin`. R19 is real and V5 is its
  only detector.

**3. The supersession note's row numbers are right.** I enumerated R5's
table myself: rows are `.loop/archive/R5-rollout-memex-oidc-auth/eval.md:15`
through `:24`, so row 1 is S1 (`:15`), row 4 is D2 (`:18`), row 9 is G1
(`:23`), and row 10 is G2, the static-keys guardrail R6 preserves. The note
(`:36`, `:38`, `:43`) names 1, 4 and 9. `git diff` over that file shows 23
insertions and 0 deletions, so the signed rows and the sign-off are
untouched.

**4. V1's discriminator carries its precondition again.** The decode step
now also asserts `groups` does NOT contain `app-memex-admins`
(`docs/memex-oidc-verification.md:263`), with the paragraph at `:265-269`
explaining that the Q8 resting state puts the operator in both tiers, so a
later re-run resolves to `admin` and the write is not refused. The write
bullet is scoped "Given a reader-only token" and ends "If the token carries
`app-memex-admins`, this is V5, not V1" (`:275-279`). The eval row states
the same precondition in its Input column (`:20`).

## The `roles.tf` comment edit is comment-only

`deployments/infrastructure/roles.tf:140-142` replaces "SHIPS EMPTY, on
purpose" with "F2 built the extension point and shipped it empty; memex
(R6) is its first consumer." Every changed line in that hunk starts `###`.
No behavior moves.

## Tree delta since the last review

`git diff ab6a6950… 61ee8563…` reports exactly two files: `roles.tf` (+3/-2,
the comment above) and `docs/memex-oidc-verification.md` (+13/-6, the V1
precondition). Nothing else moved. Fixes 1, 2 and 3 live under `.loop/`,
which the stamped tree does not cover (only `.loop/config.json` is tracked),
so I checked those three by reading the files directly, as recorded above.

## Independent correctness pass

Beyond the fixes, I re-derived the load-bearing premises rather than reading
the plan's claim:

- **P13 holds.** `readOIDCClientCredsResource` in
  terraform-provider-vault v5.3.0 guards the secret read with
  `if clientType != "public"`, so `data
  "vault_identity_oidc_client_creds" "memex"` on a public client returns an
  empty `client_secret` instead of erroring. The
  `client_secret is not set in response` string does exist in the pinned
  binary, but only inside that branch.
- **P6 holds, byte for byte.** All four log strings the runbook and the eval
  assert on match v1.2.0 source: `OIDC bearer rejected: not a parseable JWT
  (%d dot-separated segments).`, `OIDC bearer rejected: no configured
  provider matches issuer %s.`, `OIDC token rejected for issuer %s: %s`, and
  `OIDC token verified for issuer %s but matched no grant_rule and the
  provider has no default_policy, so it authorizes nothing. Claims present
  on the token: %s.` The provider-count line is `logger.info('OIDC
  bearer-token authentication enabled (%d provider(s)).')`, so S1's `2` is
  the right assertion.
- **The documented laptop config validates.** `OidcClientConfig.grant`
  defaults to `interactive` and `credential="id_token"` requires exactly
  that plus the `openid` scope, so the snippet at
  `docs/vault-human-auth.md` and `docs/memex-oidc-verification.md:241-247`
  loads. V4's `scopes: ["openid"]` variant also loads, so V4 is runnable as
  written.
- **Tier names match in all five places.** `roles.tf:162-163` (map keys),
  `roles.tf:176` (members map), `memex_oidc.tf:45-46` (assignment lookups),
  `memex.hcl:167` (both `grant_rule` values), and the docs. That closes §9's
  mode 11.
- **R5's element is byte-unchanged.** Element 0 of
  `memex.hcl:167` is identical to the pre-change line; only the appended
  second object and the comment above it are new. G2 is satisfiable.
- **No Terraform cycle and no name collision.** The key is created without
  inline `allowed_client_ids`, per the warning at `oidc.tf:28-32`; the
  standalone `vault_identity_oidc_key_allowed_client_id.memex` registers the
  client instead. Vault names `memex` / `memex-human` collide with nothing
  in `nomad_oidc.tf` or `oidc.tf`.
- **TTL arithmetic passes Vault's two checks.** `verification_ttl 2592000`
  is 4.3x `rotation_period 604800` (limit 10x), and `id_token_ttl 2592000`
  equals the key's `verification_ttl` (the check is `>`, not `>=`).
- **Scope is clean.** The changed set is exactly §7's declared surface: one
  new Terraform file, three edits to `roles.tf`, the one-line `oidc.tf`
  append, four `services.tf` changes, the `memex.hcl` array and comment, and
  three docs plus the R5 supersession note. `hermes.hcl`,
  `docs/workload-identity.md`, `vault_identity_oidc_key.lab` and
  `vault_identity_group.admin` are untouched.

## Nits, none blocking

- **N1 (low).** `deployments/infrastructure/oidc.tf:21` and `:122` still say
  the app-user map "ships empty", which this ticket falsified — the same
  staleness the implementer fixed at `roles.tf:140`. §5 forbids editing that
  file beyond the append, so leaving it is the defensible call, and the
  operative instruction at `:122` ("CONCAT, never replace") is still
  correct. Worth a line in a later scaffold ticket.
- **N2 (low).** `docs/cluster-roles.md:1` reads "The application-user role is
  a per-application scaffold; memex is its first consumer." That semicolon
  joins two independent clauses, which the repo's slop rule asks to surface
  rather than auto-rewrite. Documentation reviewer's call.
- **N3 (low).** The eval's V6 row (`:25`) asserts only the cached
  `expires_at`, while §8 V6 also asserts the decoded id_token `exp`. Not a
  hole: `expires_at` is `min(now + expires_in, id_exp)`, so a short TTL on
  either side shows up in the one value. The row is just narrower than the
  plan.

## Verdict

`pass`. The four required fixes landed and are correct, and the two that
existed because an earlier version would have failed a healthy system (V5's
eval row, V1's precondition) have the polarity right in both the eval and
the runbook. The only tree change beyond those two fixes is a comment. Gates
are green and the scope traces to the ticket.
