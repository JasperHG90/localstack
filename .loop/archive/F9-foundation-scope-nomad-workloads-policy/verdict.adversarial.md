---
verdict: pass
tree: 917fa74d0e395554e063ca37319d47396dfef0ca
---

# F9 adversarial review, cycle 4 (final cycle, `review_cycles` at cap)

**Nothing blocks. Merge it.** Three notes below. All are cosmetic or
defence-in-depth; none changes what the committed template renders, what the
operator applies, or what the cluster ends up with.

Re-run independently, read-only: `just pre_commit`, `vault policy read
nomad-workloads` against `192.168.2.30:8200`, a Jinja render of the committed
template with the live accessor, `nomad job inspect` over all 19 live jobs, and
byte-level simulation of the runbook's step-2 assertions against four apply
outcomes. No mutating command ran. The live policy still has six `path` blocks
and the `# Bootstrap secrets (for rotation jobs)` comment — the correct
pre-apply state, untouched.

## Premise: sound

Independently confirmed the deletion premise rather than trusting the ticket.
`nomad job inspect` over every live job returns **zero** references to the
`bootstrap` mount, and `docs/credential-rotation.md:34-40` ("Why Ansible (Not
Nomad Periodic Jobs)") states both credentials are host-level and rotated over
SSH. The cites at `docs/credential-rotation.md:20` (`bootstrap/tailscale`) and
`:29` (`bootstrap/github`) resolve exactly. Nothing consumes the grant, so
deletion — not a dedicated role — is the right fix.

## The new assertion block: all four correct

`.loop/plans/F9-foundation-scope-nomad-workloads-policy.md:257-262`. I built
the post-apply text from the live policy and ran all four against a correct
apply and against each failure mode the plan claims they catch.

| Outcome | `^path` | `path "bootstrap` | `-ci bootstrap` | `secret/metadata/{{` | Caught? |
|---|---|---|---|---|---|
| Correct apply (3 blocks, comment gone) | 3 | 0 | 0 | 1 | pass, as specified |
| Live pre-apply (no-op / operator forgot) | 6 | 2 | 3 | 1 | yes (A1, A2, A3) |
| 3 blocks deleted, comment left behind | 3 | 0 | **1** | 1 | yes (A3) |
| Scoped metadata deleted instead of unscoped | 3 | 0 | 0 | **0** | yes (A4) |

**N-1 and N-2 from cycle 3 are genuinely closed.** A3's `-ci` catches the
orphaned comment that a case-sensitive grep missed; A4 is the assertion that
distinguishes deleting the right `secret/metadata` block.

**`grep -c 'secret/metadata/{{'` is correct against the RENDERED file** — this
was the specific thing to attack, and it holds. `vault policy read
nomad-workloads` returns, verbatim:

```
path "secret/metadata/{{identity.entity.aliases.auth_jwt_649fd6cc.metadata.nomad_namespace}}/*" {
```

`secret/metadata/` is immediately followed by `{{`, so the literal substring is
present. Vault stores policy text verbatim and does not reformat it, and the
assertion runs against `vault policy read` output rather than the file on disk,
so it verifies what Vault actually holds. Count is 1 on a correct apply, 0 if
the wrong metadata block went. Not a false failure.

The plan's long-term caveat at `:270-273` is also right: I rendered the
committed template and `grep -ci bootstrap` returns 1 against it, because
`vault_nomad_workloads.hcl.j2:14` contains "the bootstrap mount". The plan
names that exact line. `grep -c 'path "bootstrap'` stays 0, as claimed.

## The template renders exactly what step 2 leaves behind

Rendered `vault_nomad_workloads.hcl.j2` with
`auth_method_accessor=auth_jwt_649fd6cc` (the live accessor from `vault policy
read`). Its three `path` blocks are **byte-identical** to lines 1-11 of the
current live policy. So the job-scoped `secret/data` reads and the
namespace-scoped `secret/metadata` list survive untouched, the next full
bootstrap run is a no-op for grants, and the runbook's "the template wins" line
is accurate. Eval row 8's guardrail is satisfied and scoreable now.

## The audit-doc paragraph is accurate

`docs/notes/audit/plan-premise-sweep-2026-07.md:78-86`. Every claim checks out:

- "the committed template is 21 lines with three `path` blocks" — `wc -l` is
  21, three `^path` lines. Correct.
- "grants 3, 4 and 5 are removed" — matches the numbered list at `:65-71`
  (unscoped `secret/metadata/*`, `bootstrap/data/*`, `bootstrap/metadata/*`).
  Correct.
- "only the two job-scoped `secret/data` reads and the namespace-scoped
  `secret/metadata` list remain" — confirmed by the render.
- "The LIVE policy still renders six blocks until an operator applies F9" —
  confirmed live, six blocks.
- "this paragraph stays accurate about the cluster and is already stale about
  the repo" — precise. The paragraph above says "The file is 24 lines", which
  is a repo claim and is what goes false at merge; the note says so plainly and
  leaves A1's dated snapshot standing rather than rewriting it. N-4 closed.

## Findings

### F-1 (minor, non-blocking) — the F1 relay's line count was NOT corrected

The hand-off states N-3 was "corrected to 21, verified by `wc -l`". It was not.

`.loop/plans/F1-foundation-nomad-wi-jwt-trust.md:186` still reads:

```
> template drops from 24 lines to 20, so every line cite into it shifts.
```

`wc -l bootstrap/roles/nomad_server/templates/vault_nomad_workloads.hcl.j2`
returns **21**. The audit doc got 21 right; the relay did not.

Why it does not block: the sentence containing the wrong number is the sentence
telling the reader **not** to use line numbers and to re-read the file instead.
The operative instruction is correct and F1 is now `stage: blocked` in the
ledger with an explicit `unresolved-design-fork` blocker, so nobody picks it up
on the stale premise. The number is decoration on a warning label. Flagging it
because a hand-off claim was false, not because the artifact misleads.

### F-2 (minor, non-blocking) — a fourth failure mode slips past all four assertions

The block counts `^path` and checks for `bootstrap` and the scoped metadata
line, but nothing asserts the **unscoped** `secret/metadata/*` is gone. Verified
concretely: an operator who deletes the two `bootstrap` blocks plus one
`secret/data` read (instead of the unscoped list) lands on

```
A1 3   A2 0   A3 0   A4 1
```

— all four green, while requirement 4 is silently unmet and the bare-path
`secret/data` read is lost. One line closes it:

```
echo "$P" | grep -c 'secret/metadata/\*'       # expect: 0
```

Non-blocking for three reasons. It requires deleting a block step 2 explicitly
says to keep (`:252-254`, "Leave the two job-scoped `secret/data` reads ...
untouched"). Eval row 9 reads the rendered policy for exactly this class of
defect, and eval row 7 runs `vault list secret/metadata` with a WI token, so the
unscoped list surviving is caught at verification. Eval row 3's fifteen-holder
sweep catches the lost read. The plan already names row 9 as the backstop for
the sibling case at `:266-268`.

### F-3 (nit) — plan Context still says "24 lines" in the present tense

`.loop/plans/F9-foundation-scope-nomad-workloads-policy.md:33`. Unlike the audit
doc, the plan's own Context did not get a superseded marker. The section is
headed "Context (today's state)" and dated `Verified live 2026-07-25`, so it
reads as a snapshot, and the plan archives alongside the change. Cosmetic.

## Scope: clean

Five files, every one traceable to the ticket or to a prior review pass's
required fix:

- `bootstrap/roles/nomad_server/templates/vault_nomad_workloads.hcl.j2` — the
  fix itself (`-12/+9`).
- `.loop/plans/F9-...md` — runbook, assertions, corrections.
- `.loop/plans/F1-...md` — the relay the ticket's risk section mandates.
- `.loop/ledger.json` — F1 blocked with a reason, F9 stage bookkeeping.
- `docs/notes/audit/plan-premise-sweep-2026-07.md` — the documentation pass's
  required fix.

No stray edits, no adjacent "improvements", no changes to `acme.tf`, any
jobspec, or `docs/credential-rotation.md` (which needs none — it carries zero
references to `nomad-workloads` or the removed grants, so subticket 4 is
correctly a no-op).

The nine-line comment replacing three grants is verbose for the deletion it
records, but it is load-bearing: it explains a security change and deliberately
avoids restating the revoked rules so a grep for them cannot match. The
`.loop/archive/<slug>/plan.md` path it cites is real (verified against
`.loop/archive/F3-foundation-haproxy-tls-vault-pki/`). Keep it.

## Gate

`just pre_commit` — re-run by me, all Passed:

```
check json ... Passed        check yaml ... Passed
check for merge conflicts ... Passed
fix end of files ... Passed  detect private key ... Passed
Nomad Format (fmt -recursive) ... Passed
Terraform Format (fmt -check -recursive) ... Passed
Terraform Validate (per root) ... Passed
```

## Eval marker, re-scored (11 rows, signed 2026-07-30)

| # | Row | Score |
|---|---|---|
| 1 | bootstrap write grant gone (403 on read and write) | **unscoreable** — post-apply. Live policy still grants it, correctly. |
| 2 | denial proven with a non-root token | **unscoreable** — post-apply. Prerequisite is correctly stated in the marker. |
| 3 | all fifteen holders still render templates | **unscoreable** — post-apply. |
| 4 | re-checked at T+10 min | **unscoreable** — post-apply. |
| 5 | haproxy still serves edge TLS | **unscoreable** — post-apply. |
| 6 | `acme` unaffected | **pass (repo half)** — no change to `acme.tf` or `services/acme.hcl` in the diff. Live half post-apply. |
| 7 | metadata-list decision recorded AND matches reality | **pass (recorded half)** — requirement 4 at `:115-122` states explicitly that the unscoped list is REMOVED and that the scoped one survives. Live half post-apply. |
| 8 | guardrail: policy file changed, only where intended | **pass** — render is byte-identical to live lines 1-11 for the surviving grants; only blocks 4, 5, 6 and the comment go. |
| 9 | guardrail: no new broad grant replaces the old one | **pass** — all three surviving blocks are namespace- and job-scoped; nothing widened. |
| 10 | repo gate passes | **pass** — re-run independently, all Passed. |
| 11 | rollback path written down before the run | **pass** — `:295-302` gives the exact command, the non-empty-backup guard from step 1, who runs it (root on 192.168.2.30), why no re-login is needed, and the reminder to re-add blocks to the template or the next bootstrap undoes the rollback. |

Six scoreable rows pass; five are post-apply and correctly marked unscoreable
rather than guessed.

## Verdict

**pass.** The premise holds under independent check, the frozen decision
(requirement 4) is honored, the four new assertions are each correct and each
catches the failure mode claimed of it — including the one I was asked to
attack, `grep -c 'secret/metadata/{{'`, which is right because the rendered file
does contain that literal — and the audit-doc paragraph is accurate line by
line. F-1 is a stale number inside a "do not use numbers" warning on a ticket
that is now blocked anyway. F-2 is a defence-in-depth gap the evals already
cover. Neither is worth holding the merge for, and there is no cycle left in
which to fix them.

Carry F-1 and F-2 forward as operator notes: correct the "20" to "21" whenever
F1 is re-planned, and consider adding
`echo "$P" | grep -c 'secret/metadata/\*'  # expect: 0` to the step-2 block
before the apply.
