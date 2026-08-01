---
verdict: pass
tree: 7fc8dbb58e3ea45a79f7f13450a7c0bdc2eddc74
---

# A1-audit-plan-premise-sweep — documentation (cycle 4)

Nothing blocks. My cycle-3 finding D1 is fixed and the fix is correct. The
Fork 4 correction I flagged as advisory is now in the doc and is itself
correct. The deliverable and the repo state it describes now agree.

Tree confirmed independently, not taken from the briefing: a throwaway index
(`GIT_INDEX_FILE`) built with `git add -A .`, `.loop` stripped, then
`.loop/config.json` re-bound — the recipe in `stamp.py:83-137` — yields
`7fc8dbb58e3ea45a79f7f13450a7c0bdc2eddc74` on the current working tree.
`.loop/stamp.json:2` carries the same value with `just pre_commit` exit 0.

## Documentation drift: none

The diff touches `.loop/plans/`, `.loop/evals/`, `.loop/ledger.json`, thirteen
new `plan-validator` verdicts, and one new page,
`docs/notes/audit/plan-premise-sweep-2026-07.md`. No public function, CLI flag,
config key, default, command, or error contract changed, so no existing doc
went stale. `README.md:29` points at `docs/` with an open "etc." and needs no
entry; `docs/` has no index file to update. `AGENTS.md` (and `CLAUDE.md`, its
symlink) needs no edit, for the reason the doc itself now gives.

## D1 (cycle 3) — fixed, verified

`plan-premise-sweep-2026-07.md:427-432` now says nine verdicts record what they
ran (F2, L1, L2, M1, M2, R1, R2, R3, S1), three record nothing (F7, F8, R4),
and F9 asserts read-only without saying what it ran. I recounted from the
files, not from the heading string:

- F2 `## Method note` (`:425`), L1 `## Cluster commands run (all read-only)`
  (`:332`), L2 `## Method and constraints observed` (`:368`), M1 `## Method
  note` (`:376`), M2 (`:280`), R1 (`:404`), R2 `## Read-only compliance`
  (`:340`), R3 (`:331`), S1 `## Method` (`:335`). Nine, each enumerating
  commands and asserting no mutation.
- F7, F8, R4 have no such section. F9's read-only claim is at
  `F9-...plan-validator.md:15-17` and lists only what it did NOT run.

The dated note at `:434-441` records both wrong counts and why the second one
was wrong. Honest and correct.

## Fork 4 — the correction is right

Verified against git, not the doc's own account:

- At this branch point (`64f4adb`), `AGENTS.md:74` and `:114` both assert a
  private Docker registry.
- `27dd367` on `main` (one commit after the branch point) removed both and
  added `AGENTS.md:120`, "Private docker registry: we use the GitHub
  registry." `git show main:AGENTS.md | grep -in registry` returns only `120`.
- `CLAUDE.md` is mode `120000` in both trees, so it is a symlink and a git-side
  grep over it reads the link target. The trap the doc names is real.

"No action; already correct on `main`" is the right call.

## Accuracy sweep (what I checked, and against what)

Live cluster, read-only:

- `GET /v1/jobs` returns nineteen jobs, exactly the nineteen listed. Per-job
  `Vault.Role` over the API: fifteen `""`, `acme` = `acme`, and `nats`,
  `node-exporter`, `promtail` carry no `Vault` block. The corrected paragraph
  at `:88-95` matches the cluster job for job.
- `/.well-known/openid-configuration` returns `OIDC Discovery endpoint
  disabled`; `/.well-known/jwks.json` returns a key with `kid`
  `00d87b20-6277-3854-b86f-4863c69ac826`, matching `:39-42`.
- Vault HTTP reads were refused by this environment's command classifier, so
  the Vault table at `:53-60` and the mount list at `:78-83` rest on the
  thirteen verdicts rather than on my own readback. I record that rather than
  implying I checked it. The policy claim I could check from the repo:
  `bootstrap/roles/nomad_server/templates/vault_nomad_workloads.hcl.j2` is 24
  lines with six `path` blocks and exactly the five grants described at
  `:65-71`, including the unscoped `secret/metadata/*` and `bootstrap/data/*`.

Ledger and harness:

- All thirteen are `blocked`: twelve `unresolved-design-fork`, F9
  `eval-missing`, each reason naming the headline defect and its verdict path.
  Fork 1 at `:325-352` describes this exactly.
- `loopctl next` offers C1, F1, N3, S2, T5 and none of the thirteen — the
  actionable set at `:344-345`, verbatim.
- `loopctl reconcile` prints `ledger consistent with git`. `loopctl eval` gives
  `absent` for F9 and `unsigned` for F2 and S1, so systemic finding 1 holds.
- The "challenged and upheld" note at `:151-169` checks out anchor by anchor
  in the out-of-repo `loop-harness`: `evals.py:48` is `UNSIGNED = "unsigned"`,
  `_SIGNOFF_PREFIX`/`_has_signoff` sit at `:88-99`, the `verify_eval` docstring
  says "Only ``VALID`` clears the ``require_eval`` gate", `eval_marker_present`
  returns `verify_eval(...).ok`, and `ctl.py:185-186` passes it in for
  `Stage.IMPLEMENTING`. The note's caveat that these will not resolve from the
  repo root is stated and true.
- Every `plan-validator` verdict's bound sha256 differs from its plan's current
  sha256 (checked F2, R3, F9). The doc says so at `:314-318` and calls it
  correct behavior. It is.

Repo claims:

- Bifrost table at `:180-182`: `ac3267b` 10+12+54 = 76, `e17d8d0` 8+23+36 = 67,
  `64f4adb` 9. Dates 2026-07-29, 07-30, 07-30. `git log -S'"bifrost"' --
  deployments/applications/database.tf` names only `e17d8d0`, and `ac3267b`
  does not touch that file. All four numbers and the attribution hold.
- `database.tf:88-96` is the tail of `postgresql_extension`; `postgresql_grant
  "reader"` starts at `:96`. R3's verdict (`:119`, `:299-301`) says the same,
  and the doc summarizes it faithfully.
- `docs/notes/` has 0 files at HEAD and `cc22050` (2026-07-26) deleted six of
  them; `docs/rfcs/` does not exist. Fork 6 holds.
- `grep -rl talat . --include=*.hcl` is empty; `grep -rln 'jwks\|openid\|oidc'
  deployments/ --include=*.hcl` is empty; `memex.hcl:138,140` are
  `MEMEX_SERVER__AUTH__ENABLED=true` and the static `__AUTH__KEYS` list, with
  no JWKS or issuer. Seventeen files under `.loop/plans` and `.loop/evals` match
  `localstack`.
- The archived S3 plan (`.loop/archive/S3-.../plan.md:282`) is the source for
  "the shared epic context", as the doc says.
- Triage table vs verdicts: premise findings match one for one — BROKEN for
  F7, F8, L2, M1, R1, R2, R3, S1; PARTIALLY SOUND for F2, F9, L1, M2, R4. Gate
  verdicts: twelve `fail`, F9 `pass-with-required-fixes`. F2's parenthetical
  (body 4, addendum 6, eval DoD 5, eval row 3 four) reproduces
  `F2-...plan-validator.md:197-206` exactly. M1's `RELEASE.2025-09-07` claim
  traces to that verdict's `openid.go:66-69` evidence.
- Plan edits: eighteen inserted lines per plan for the pointer, three
  substantive corrections (F9, L2, M2) each dated and quoting what it replaced,
  plus A1's own plan. No plan rewritten. `## Plan review, 2026-07-30 (A1
  premise sweep)` is the last section of all thirteen.

## Does it state its own limits (eval row 8)

Yes, in two places and honestly. `:8-27` says the verdict file, not the table,
is the authority; that `SOUND` is not a correctness guarantee and no design
question was asked; and in bold that `needs deep review` means NOT fixed.
`:443-453` adds that a reviewer can be wrong, that `UNCERTAIN` findings are
visible in the verdicts, and that the verdicts bind the plans as of 2026-07-30.
No plan came back clean, so the eval's literal "clean is not correct" caveat is
moot and the doc states the `SOUND` analogue instead, which is what the eval's
own rescope note asks for.

## Correction notes: honest record, not clutter

Six dated notes (`:104-109`, `:151-169`, `:193-197`, `:352`, `:393-397`,
`:434-441`), about 45 lines of 454. Each sits next to the claim it corrects,
quotes what it replaced, and names a distinct error. None contradicts another,
and I checked the two that could: the "challenged and upheld" note keeps a
disagreement open with evidence that I re-verified in the harness source, and
the Fork 1 note keeps the superseded recommendation quoted while the section
title says RESOLVED. The doc's framing (`:24-27`), the "No other plan's
substance was touched" paragraph (`:298`) and the pointer paragraph (`:305-312`)
now agree. I would keep all six.

## Slop scan (all three layers)

Layer 0 clean: no identity leak, no `TODO`/`FIXME`, and every backticked path,
command, commit and anchor I could reach resolves or is explicitly marked as
outside this repo. Layer 1: 5/6 minus nothing that blocks — the lead states the
purpose rather than the finding, and the finding ("Not one plan passed clean")
waits until `:253`; sentence weight and the repetition rule are fine for a
4,188-word audit record. Layer 2: zero em dashes, zero ` -- `, zero smart
quotes, zero British spellings, no tier-1 slop (the two `actionable` hits are
the harness's own term for a `loopctl next` state), no self-narration, no
"not only/not just", no participial tails, no three-fragment bursts. Prose
lines all wrap at 80; the only long lines are table rows.

## Non-blocking nits (no fix required, recorded for the writer)

1. `:429-430` — "**Three record nothing** (F7, F8, R4)" is a shade strong.
   None has a method record, which is the load-bearing point and is true, but
   each cites commands it ran inside its evidence (`F8-...:231-234` lists four
   `vault` reads and states "No creds endpoint was read"; `F7-...:55,108,131`;
   `R4-...:110,118`). "None records its method" would be exact. Not blocking:
   the phrasing understates the audit's own rigor, so no reader over-trusts it,
   and the sentence that follows is true as written.
2. `:428-430` — the three headings listed after "under varying headings:" read
   as exhaustive but omit L2's `## Method and constraints observed` and S1's
   `## Method`. Five headings, three shown.
3. `:190-191` — "R3 (9)" citations. Seven anchors are fully qualified
   `applications/{providers,secrets,services}.tf`; counting short-form anchors
   in the same context gives about ten. F8's 13 verifies exactly. The counting
   rule is unstated, so 9 is defensible but not reproducible.
4. Five prose semicolons join independent clauses (`:27`, `:160`, `:352`,
   `:388`, `:412`); the slop rule marks these low-confidence, for a human to
   judge. Four spatial-copula verbs: "rests on" (`:45`, `:432`), "sits above"
   (`:124`), "sits in" (`:407`), "lives under" (`:157`). All read naturally;
   surfaced, not demanded.
5. Outside the deliverable: `L1-landing-oauth2-proxy.md:401-402` appends the
   pointer heading with no blank line after the previous paragraph. Renders
   fine under CommonMark; cosmetic only.
