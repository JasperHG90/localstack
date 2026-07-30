---
verdict: pass
tree: 7fc8dbb58e3ea45a79f7f13450a7c0bdc2eddc74
---

# Adversarial implementation review — A1-audit-plan-premise-sweep (cycle 4, final)

**Nothing blocks. All three cycle-3 blockers are resolved, verified against the
repo rather than the hand-off.** Two minor findings are recorded below; neither
falsifies a claim, changes a triage verdict, or affects an action.

## Tree freshness (cycle-3 B1)

Verified myself, twice, at the start and end of this review:

```
tree_fingerprint(repo, ignore=()) -> 7fc8dbb58e3ea45a79f7f13450a7c0bdc2eddc74
.loop/stamp.json                  -> 7fc8dbb5..., "just pre_commit" exit 0
```

The fingerprint was identical before and after the whole pass, so the tree was
frozen for its duration. The stamp binds the same tree the briefing gave me.
`.loop/` is excluded from the fingerprint by design (`stamp.py:67-105`), which
is why writing this verdict does not stale it.

I re-ran the gate independently: `just pre_commit` -> all ten hooks
`Passed`/`Skipped`, nothing modified. `loopctl reconcile` -> `ledger consistent
with git`. `loopctl graph` -> exit 0, every `depends_on` resolves.

## Cycle-3 B2 — doc versus repo: RESOLVED

Every claim the fix rests on, checked against the live repo and ledger:

- **All thirteen blocked, with the stated codes.** `loopctl next` lists twelve
  under `unresolved-design-fork` and `F9-...: eval-missing`. Matches
  `plan-premise-sweep-2026-07.md:333-342` exactly.
- **`loopctl next` offers none of the thirteen.** Actionable set printed by the
  harness is C1, F1, N3, S2, T5 — byte-for-byte the doc's claim at `:344-345`.
  G1 sits under "blocked on dependencies" behind F2, correctly not listed.
- **All thirteen pointer sections exist**, one per plan, 18 lines each, each
  headed `## Plan review, 2026-07-30 (A1 premise sweep)` and each stating in
  its own text that it is a pointer, not the record. Matches `:305-312`.
- **Substance versus pointer is now honest.** `:298` reads "No other plan's
  *substance* was touched", and the diff bears it out: the ten
  needs-deep-review plans show `18 insertions` and nothing else.
- **Fork 1 is retitled RESOLVED, records both codes with the F9 reasoning, and
  quotes the superseded recommendation verbatim** (`:325-352`). The lead-in at
  `:24-27` and Fork 2's rewording at `:354-360` are consistent with it. No
  contradiction survives anywhere in the file.

## Cycle-3 B3 — stale verdict fingerprints: RESOLVED, and stronger than claimed

Recorded at `:315-318` as correct behavior with a re-dispatch instruction. I
went further and checked whether the bindings were honest in the first place.
They are, provably:

| Comparison | Result |
|---|---|
| Verdict fingerprint vs **current** plan | 13/13 STALE |
| Verdict fingerprint vs **HEAD** plan content | **13/13 exact match** |

Every one of the thirteen fingerprints reproduces the byte-for-byte sha256 of
the plan as it stood at the branch point. No hash was fabricated, guessed, or
copied. The staleness is caused entirely and only by A1's own
operator-directed pointer edits, landing after the reviews.

## Eval marker — all thirteen rows scored

| # | Row | Result |
|---|---|---|
| 1 | Thirteen verdict rows, one per slug | **PASS.** 13 rows, exactly the named slugs, each `fixed` or `needs deep review`. M2 and F9 read `fixed (mechanical) plus …`, which is more precise, not less |
| 2 | M1's discovery-endpoint gap confirmed | **PASS.** `curl` returns `OIDC Discovery endpoint disabled` live; M1's row `:242` names the removal of `jwks_url` and the disabled endpoint; Fork 3 records the `oidc_issuer` ownership gap |
| 3 | Grounded in the running system | **5/5** (needs 4/5). I re-ran every ground-truth read: the policy renders six `path` blocks with the five grants as described; `vault list auth/jwt-nomad/role` returns exactly `acme` and `nomad-workloads`; `jwks_url` set and `oidc_discovery_url` unset; nineteen jobs, and spot-inspected `haproxy` (`Role: ""`), `acme` (`Role: acme`), `nats` (no vault block), `talat-shim` (`Role: ""`) |
| 4 | No plan rewritten wholesale | **PASS.** Largest in-scope plan diff is 34 lines on a 426-line file |
| 5 | Every correction marked and dated | **PASS.** F9, L2, M2 and A1's own plan each carry a dated note quoting the exact superseded text, inline at the point of the claim |
| 6 | Nothing T3 owns is touched | **PASS.** Checked on the *unfiltered* diff: the only added lines containing `.localstack` are verbatim re-quotes inside the L2/M2 correction notes. No rename |
| 7 | No fork silently resolved | **PASS.** Five open with recommendations; Fork 1 decided by the operator, marked as such, superseded text preserved |
| 8 | The doc states its own limits | **5/5** (needs 4/5). `:8-27` states a `SOUND` verdict is not a correctness guarantee and not a design review, and that `needs deep review` means NOT fixed. The marker's own rescope note anticipated that the "clean" caveat is superseded by the mechanism change; the doc answers the superseding form |
| 9 | Ledger survives | **PASS.** `reconcile` clean, `graph` exit 0, no edge names a dropped ticket |
| 10 | Touched markers still valid | **PASS.** Only A1's marker was modified; `loopctl eval` -> `valid` |
| 11 | Shape-check evals named | **5/5** (needs 4/5). `:276-282` names F2, F8, R1, L2, S1, and separately the wrong-expectation class in L1, R4, M2 |
| 12 | Verdicts real and bound | **See below** |
| 13 | Doc neither overstates nor understates | **5/5.** I extracted the premise and gate verdict from all thirteen files and compared them to the table cell by cell: perfect match. Eight `BROKEN`, five `PARTIALLY SOUND`, twelve `fail`, one `pass-with-required-fixes` — the doc's counts at `:252-256` are exact. Spot-checked five headline defects (F2's four client counts, M1's `RELEASE.2025-09-07`, R1's `#10922` `not_planned`, R2's `#5692`, S1's `docs/notes`) against the verdict bodies; each traces |

### Row 12: passes on intent, and I rule it non-blocking

The row has two halves and they now point opposite ways.

- **Evidence half: PASSES outright.** Thirteen `plan-validator` files exist,
  one per in-scope slug, each written by `loop-plan-reviewer`, each naming a
  sha256 it verified. No triage row is unevidenced. The failure mode the row
  was written to catch — a fabricated verdict behind a table cell — is absent,
  and I proved it positively: all thirteen hashes reproduce the HEAD plan
  content exactly.
- **Freshness half: cannot pass, by construction.** The operator's later
  instruction to append pointer sections changed all thirteen reviewed
  artifacts. The row was added earlier the same day by the same rescope.

I judge the row **satisfied**. The literal freshness clause was superseded by a
later operator decision, exactly as Fork 1's recommendation was, and the
consequence is disclosed at the point of the claim
(`plan-premise-sweep-2026-07.md:315-318`) with the right remedy: re-dispatch
before treating a verdict as fresh. Nothing can act on a stale verdict in the
meantime, because all thirteen tickets are `blocked` in the ledger and require
an operator unblock first. A verdict that authorizes only the content it read
is the harness behaving correctly; calling that a failure would punish the doc
for reporting it honestly.

## Findings

### Minor 1 — R3's citation count is 7 under the rule that produces the other six

`docs/notes/audit/plan-premise-sweep-2026-07.md:191` and
`.loop/plans/A1-audit-plan-premise-sweep.md:110` both say R3 carries 9
citations of the three bifrost `.tf` files. Counting prefix-qualified
references (`applications/{providers,secrets,services}.tf`) I get:

```
F7=1  F8=13  M1=2  M2=3  R1=5  R4=2   <- all six match the doc exactly
R3=7                                  <- doc says 9
```

The six matches pin the counting rule, so R3 should read 7. The load-bearing
claim — that *seven* in-scope plans cite those files — is correct and
unaffected. Cosmetic; fold into a later touch of the file.

### Minor 2 — the plan's provenance section is one operator decision short

`.loop/plans/A1-audit-plan-premise-sweep.md:211-229` is headed "Operator
decisions of 2026-07-30 (provenance)" and opens "Three decisions were put to
the operator". A fourth — perform the thirteen `loopctl block` calls and append
the thirteen pointer sections — produced the largest diff in this ticket and is
recorded only in the audit doc (`:305-312`, `:333-334`). Since that section
exists precisely because the repo holds no other evidence of operator
direction, it should carry all four. Non-blocking: the decision *is* recorded,
dated, at its point of effect.

## Verified independently, beyond the eval rows

- `memex.hcl:138-140` resolves exactly as described: `AUTH__ENABLED=true` plus
  a static `AUTH__KEYS` list, no JWKS, no OIDC issuer. The epic-brief finding
  holds.
- Fork 4 is now correct in every particular: branch point is `64f4adb`,
  `AGENTS.md:74` and `:114` carry the private-registry claim at HEAD, `27dd367`
  landed on `main` after the branch point, `main:AGENTS.md:120` reads "Private
  docker registry: we use the GitHub registry", and `CLAUDE.md` is a symlink to
  `AGENTS.md` (`777 CLAUDE.md -> AGENTS.md`).
- Systemic finding 1 is TRUE and the documentation pass's objection to it was
  wrong. `loopctl eval` returns `absent` for F9 and `unsigned` for the other
  twelve; `evals.py:48` defines `UNSIGNED`, `_has_signoff` gates it, the
  `verify_eval` docstring says "Only ``VALID`` clears the ``require_eval``
  gate", and `ctl.py:185-186` wires it into the advance. "Content-blind" in
  that docstring refers to the eval's substance never being graded, not to the
  sign-off being ignored — the doc's reading is right.
- Bifrost commit arithmetic checks out: 76 / 67 / 9 insertions, per-file splits
  correct, `git log -S'"bifrost"' -- database.tf` names only `e17d8d0`, and
  `ac3267b` does not touch that file.
- `database.tf:88-96` is the body of `postgresql_extension`; the reader grants
  start at `:97`. The reviewer's "cited 4x" is exact — four occurrences in the
  plan as reviewed.
- Fork 6: `docs/notes/` count at HEAD is 0, `cc22050` exists, `docs/rfcs/` does
  not.
- The L2/M2 DNS corrections verify live: `getent hosts
  dash.lab.orangecluster.nl` -> 192.168.2.30, `dig +short
  minio.lab.orangecluster.nl @1.1.1.1` -> 192.168.2.30, zero `orangecluster`
  entries in `/etc/hosts`.
- Method-note count is now right: nine record what they ran (F2, L1, L2, M1,
  M2, R1, R2, R3, S1), three record nothing (F7, F8, R4), and F9 asserts
  read-only by listing what it did *not* run.

## Scope

Every changed path traces to the ticket's declared code surface: `.loop/plans/`
(fourteen files), `.loop/evals/A1-…`, thirteen `*.plan-validator.md` verdicts,
`docs/notes/audit/plan-premise-sweep-2026-07.md`, and `.loop/ledger.json` from
the `loopctl block` calls. No source, no infrastructure, no Terraform, no HCL.

No mutating cluster or git command was issued during this review; all cluster
access was `curl` GETs, `vault list`/`read`/`policy read`/`secrets list`, and
`nomad job status`/`inspect`.
