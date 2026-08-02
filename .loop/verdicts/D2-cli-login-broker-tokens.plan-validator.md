---
verdict: pass
plan: cba65704fdad2c7dd27f334227c03d7d5cf65705eefad8a97e2d2db607798775
---

# Premise verdict: SOUND

Narrow re-bind pass. Fingerprint confirmed by `sha256sum` against
`.loop/plans/D2-cli-login-broker-tokens.md` before binding. Per the briefing I
did not re-walk the previous pass's fixes 1 and 2, the `cli-login.md`
garden-path, the test-23 reallocation, or the eleven live-cluster assumptions
confirmed two passes ago.

All seven claimed edits are applied and, where they assert a fact, the fact
holds. The one I was asked to check rather than assume — the `vault token
revoke -self` hazard — is accurate, and stronger than the author claims.

## Per assumption

**P1 — the comma splice at `:282-283` is now one sentence. HOLDS.**
`.loop/plans/D2-cli-login-broker-tokens.md:278-287`. The clause reads "The
operator's locked surface for D2 is `login|logout|whoami|env|token|config`
(…), and `ui consul` was folded into D3's `service consul --open`." That is a
comma plus the coordinating conjunction "and" joining two independent clauses,
which is one grammatical sentence, not a splice. The next sentence starts
cleanly at "An earlier draft shipped it here…". No dangling fragment survives.

**P2 — the dangling comma at `:1116-1117` is now a period. HOLDS.**
`:1117` reads "R13: addresses with no secrets. Test 22. Depends on 4 and 8."
The comma is gone and "Test 22" is its own sentence, matching the shape of
items 4, 5, 6 and 8 in the same list.

**P3 — the orphaned "That inversion" paragraph is rewritten. HOLDS.**
`grep "That inversion"` returns nothing in the plan. `:982-987` now opens
**"Why the accessor revoke outranks the composite."** and states the ranking
positively: the composite needs a Nomad management token *and* a Consul
management token, the accessor revoke needs only the Vault password (R7), so
for the victim this section addresses the composite is the remedy they cannot
run. No reference to a superseded draft.

**No contradiction with `:857-863`.** That block ranks 1. `localstack logout`,
2. accessor revoke, 3. composite. `:986-987` closes "So after `logout`, this is
the first thing to reach for" — rank 2, exactly. `:865-866` puts the composite
at 3, and `:912-914` independently says "This is not *the* non-root closer; the
accessor revoke is also non-root and needs no management tokens at all."
Three statements, one ranking.

One thing I checked for and did not find: `:862-863` gates the accessor revoke
behind "read the escalation warning before doing it", and `:986-987` does not
repeat that gate. It does not need to — the rewritten paragraph sits at `:982`,
*after* the policy block (`:925-931`), the throwaway-entity warning
(`:933-950`) and all four responder residuals (`:952-980`). A reader arriving
at it in document order has already passed every warning.

**P4 — the carve-out gained the `main`-is-wrong clause. HOLDS, and the claim
is true.** `:670-676`: "Worse than absent: the version on `main` still carries
a bullet this section's measurements falsify, so a worktree shows the **wrong**
claim rather than no claim. Commit the doc alongside this ticket."

I verified the falsified bullet exists rather than trusting the plan.
`git show HEAD:docs/vault-human-auth.md` line 104 reads:

    - It is per-person, and revoked by removing you from the group.

§9 falsifies the second half at `:878-884`: group removal only *demotes* the
Vault token to `default` on its next call, and `default` grants
`sys/leases/renew`, so the holder keeps renewing both brokered leases to their
`max_ttl` of 3600. The working-tree `:104` has been cut back to "It is
per-person." The carve-out describes a real hazard, not a hypothetical one.

**P5 — the `-self` hazard. HOLDS, and the warning is accurate.**
`docs/vault-human-auth.md:111-119`. The fenced block is

    VAULT_TOKEN=<the lost session's token> vault token revoke -self

followed by "**Set `VAULT_TOKEN` on that line and nowhere else.** `-self`
revokes whatever `VAULT_TOKEN` currently holds, and in this devcontainer that
is the **root token** — running it bare would revoke root and take the
cluster's admin credential with it."

I confirmed the factual claim with a read-only lookup (no revoke of any kind
was run). `env | grep -c '^VAULT_TOKEN='` returns 1, and `vault token lookup
-format=json` on the ambient token reports:

    display_name: root
    policies: ['root']
    identity_policies: None
    ttl: 0
    entity_id: ''

So the ambient `VAULT_TOKEN` in this devcontainer is the root token, it is
non-expiring (`ttl: 0`), and it is not entity-backed, which means no group
demotion or entity disable would soften a revoke of it. The warning's
consequence clause — "take the cluster's admin credential with it" — is exact.
`entity_id: ''` also independently confirms the doc's own pre-existing claim at
`:31`.

**On "impossible to skim past": stronger than claimed.** The block is fail-safe
against the failure mode that produced the original hazard, which is a
verbatim copy-paste. Pasted into bash, `VAULT_TOKEN=<the` parses the `<` as an
input redirect (the metacharacter terminates the assignment word), and
`session's` opens a single quote that never closes. Bash errors out before it
ever reaches `vault`. A skimmer who copies the block gets a shell complaint,
not a revoked root token. Combined with the bolded lead sentence directly
beneath it and **root token** bolded inside it, this clears the bar.

Low-severity, untested, not a required fix: a reader who deletes the
placeholder and leaves `VAULT_TOKEN= vault token revoke -self` sets the
variable to empty, and the Vault CLI's fallback to `~/.vault-token` in that
case is a behavior I did not probe, because probing it means running a revoke.
I mention it for completeness; the doc's instruction ("set it on that line")
does not invite that edit.

**P6 — the Consul bridge is restored and matches the plan. HOLDS.**
`docs/vault-human-auth.md:181-188` carries
`CONSUL_HTTP_TOKEN="$CONSUL_TOKEN" consul acl token delete -accessor-id
<accessor>` with "**The Consul bridge is not optional**: the CLI reads
`CONSUL_HTTP_TOKEN` and ignores `CONSUL_TOKEN`, so without it the delete fails
with an error that reads like a wrong accessor."

Against plan `:896-905`: same command byte-for-byte at `:898`, and `:902-905`
gives the same reason ("`.devcontainer/.env` sets `CONSUL_TOKEN` and the
`consul` binary reads only `CONSUL_HTTP_TOKEN` (§4), so without it the call
runs as the agent token and fails with a permission error that reads like a
wrong accessor"). The doc drops "runs as the agent token" and the word
"permission"; neither omission changes what the reader does. Ordering matches
too: both put cut-the-mint-path before the deletes, and both say management
token, not root (doc `:186-188`, plan `:901`, `:910-912`).

**P7 — British spellings normalized. HOLDS.** `grep -n "honour\|Honour"` across
the plan, the doc and `ROADMAP.md` returns zero. Five "honoring" remain, all
American: `docs/vault-human-auth.md:132,192,193` and
`.loop/plans/D2-cli-login-broker-tokens.md:1023,1024`. The briefing said one in
the plan; there are two. Both are correct, so this is a counting nit, not a
finding.

**P8 — `ROADMAP.md` credits F8 with retiring the root token. HOLDS.**
`ROADMAP.md:107-113` now reads:

    F11 ->  D2 -> D6                  per-person sessions, then the shims
    F11 ->  F8                        retires the root token: providers off the
                                      static tokens

The contradicting `F11 -> D2 -> D6  retires the root token` is gone. Checked
against the two anchors I was given and one more:

- `.loop/plans/D6-cli-deps-and-shims.md:106-107` — "F8 would remove the
  injected token and make the shim redundant, but F8 is blocked, so the shim is
  what works today." Consistent: D6 owns the shim, F8 owns the retirement.
- `ROADMAP.md:103` — F8's row, "Points Terraform's providers at brokered
  tokens, drops the static ones." Consistent with the critical-path gloss.
- I did not take the D6-to-F8 attribution on trust, because ROADMAP `:103`
  scopes F8 to Terraform *providers* while the injected root `VAULT_TOKEN` is a
  devcontainer surface. `.loop/plans/F8-foundation-deployer-provider-cutover.md`
  settles it: `:280-281` has F8 remove root `VAULT_TOKEN` from
  `.devcontainer/.env.example` line 10 outright, repeated at `:199`, `:407` and
  `:477`. F8 really does retire it.

## Most dangerous assumption

P5, the `-self` hazard. It is the only edit where being wrong puts a reader one
paste away from destroying a non-expiring root token on a cluster with no audit
device (`:969-972`) and no cheap recovery. It is also the one the briefing
flagged as the author's own error. I measured it rather than reading it: the
ambient token is root, so the warning's premise is true, and the fenced form
cannot fire on a verbatim paste. This is the strongest of the seven.

## Sweep for collateral

- Doc line wrap: `docs/vault-human-auth.md:41,42,43,68` exceed 80 chars, but
  `git diff -U0` shows only two hunks (`:104` changed, 88 lines inserted after
  `:106`), so those four are pre-existing and untouched. Every inserted line
  wraps at 80 or less.
- No pre-commit hook scans markdown prose. `.pre-commit-config.yaml` lists
  check-json, check-ast, check-merge-conflict, check-yaml, debug-statements,
  detect-private-key, end-of-file-fixer, nomad-fmt, terraform-fmt,
  terraform-validate. So fix 4's "commit the doc alongside this ticket" adds no
  new gate risk.
- The doc's newly inserted `:107-109` claim is verbatim-accurate. `which
  localstack` resolves to `/home/vscode/.local/bin/localstack`, `--help` shows
  a command table with no subcommands (D1's skeleton), and `localstack logout`
  prints exactly `No such command 'logout'.`
- `:278`'s "see §12" resolves: §12 is at `:1319`, and both halves of the `ui
  consul` claim live there — the no-credential catalog read at `:1426-1427` and
  the 25-to-2 cut at `:1421`. The same measurement appears at `:530-533`.
- The doc's revocation block does not contradict §9's ranking anywhere: `:121`
  puts `logout` first, `:143-180` puts the accessor revoke ahead of
  cut-then-delete at `:181-188`, matching plan `:858-866`. Counts agree too —
  five live userpass accessors (doc `:164-165`, plan `:959-961`) and 14 workload
  tokens (doc `:152`, plan `:945-947`).
- Nothing else the seven edits touch is broken.

## The two you did not act on

Neither blocks. Plainly:

**The "does buy" / "does not buy" pair, now 93 lines apart** (`:102` and
`:195`; the 88-line insert widened it from 5). This is real and the insert
caused it: by `:195`, "What it does **not** buy" has lost its antecedent, and
the nearest subject a reader is holding is the revocation runbook, not the
`developer` credential. It is the same class of referent break as the "That
inversion" paragraph. But the difference matters: that one told an implementer
the plan was wrong, this one costs a re-read. The sentence is self-carrying —
"audit attribution… no audit device is enabled on this cluster" is true under
either antecedent. Structurally the runbook is now wedged inside a
compare-to-root section it does not belong to, and moving it after `:197` would
close both issues in one cut. Worth doing when someone next touches the file.
Not worth holding the ticket for.

**9 em dashes in 1818 words** (4.9 per 1000, against the 0-2 target in
`.claude/rules/slop-scan-for-docs.md`). Ignore it here. That rule's Layer 2 is
a scanner for docs you generate, and the plan scopes the slop scan to
`docs/cli-login.md`, the doc D2 creates (`:649-650`). `vault-human-auth.md` is
a pre-existing doc receiving an edit, no hook enforces the count, and em dashes
are not a premise defect. Fixing it would be busywork against a page whose
value is that its measurements are right.

## Required fixes

None.
