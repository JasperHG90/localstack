verdict: pass
tree: 060db5cc0f75a2aacb4360088bf2be90df394900

# Adversarial review: implement-ticket-prek-before-stamp

Scope reviewed: single documentation edit to step 3 ("Gate") of
`skills/implement-ticket/SKILL.md` (working-tree diff). No Python changed.
The change since the prior passing round is the one-word precision fix
"commit any rewrites" -> "let any rewrites land in the tree".

## Verdict: PASS

Every eval row (Definition of Done) holds against the diff, both repo
gates re-run green, and the doc-quality layers pass. No confirmed
findings.

## Premise soundness

The ticket premise holds. `.loop/config.json:2-5` runs
`git add --intent-to-add -A . && uv run pytest` first, then
`uvx prek run --all-files`, so a lint/format/type-only defect fails the
stamp only after the pytest cost, and `loopctl stamp` is all-or-nothing.
`.pre-commit-config.yaml` confirms mypy runs `pass_filenames: false`
(project-wide regardless of file filter). A pre-stamp fast pass is a
coherent fix. Verified both facts directly.

## Eval rows, judged against the diff

1. Clears fast hooks before the stamp — HOLDS. Step 3 now opens "First
   clear the cheap, deterministic checks... Run the repo's configured
   lint/format/type hooks over the changed files... let any rewrites land
   in the tree, and fix any failure rather than silence it. ... Then run
   `loopctl stamp`" (`skills/implement-ticket/SKILL.md:59-66`). Order is
   pre-stamp, clear rewrites/failures, then stamp.

2. Never weakens the stamp (guardrail) — HOLDS. "This pass is a
   convenience, not a substitute for the stamp: the type hook still runs
   over its whole configured target inside it, and `loopctl stamp`
   re-runs every gate" (`SKILL.md:63-66`). pytest is not mentioned,
   moved, or reordered; `.loop/config.json` gate ordering is untouched.

3. No silencing/skipping language — HOLDS (deterministic). Grepped the
   added lines for `type: ignore`, `--force-exclude`, "skip mypy",
   "no-verify": zero matches. `--force-exclude` exists in
   `.pre-commit-config.yaml` but is NOT introduced by this diff. The only
   occurrence of "silence" is the anti-silencing instruction "fix any
   failure rather than silence it".

4. Stays generic, prek only as example — HOLDS. Targets "the repo's
   configured lint/format/type hooks... through the blessed invocation
   (here, `uvx prek run --files <changed>`)" (`SKILL.md:60-62`). The
   "here," frames prek as this repo's example, not the rule; consistent
   with `SKILL.md:12-15` and `.claude/rules/prek-code-quality.md`.

5. No hallucinated command/path — HOLDS (Layer 0). Backticked commands in
   the edit: `uvx prek run --files <changed>` (verified: prek is the real
   tool the config already invokes; `--files` is a real flag per
   `uvx prek run --help`), `loopctl stamp`, `loopctl advance <slug>
   gates` — all real forms used elsewhere in the SKILL. No `path:line`
   references in the edit.

6. Doc-quality Layers 0-2 — HOLDS. All added lines wrap at <= 80 chars
   (measured max 79). Zero em-dashes in the diff. No identity leaks, no
   tier-1 slop, no throat-clearing, no participial tails, no semicolon
   splices. The two contrastive-negation constructions ("convenience, not
   a substitute"; "fix... rather than silence it") are load-bearing
   guardrails mandated verbatim by ticket section 6 and eval row 2 — kept
   per the slop rule's load-bearing exception.

7. Surgical, gates green — HOLDS. Diff touches only step 3; step 4 and
   the frontmatter are unchanged, no renumbering. Re-ran both gates
   independently: `uv run pytest` = 180 passed; `uvx prek run --all-files`
   = ruff-lint, ruff-format, mypy all Passed. Working-tree also shows a
   modified `.loop/ledger.json` and untracked `.loop/verdicts/*.md` files;
   these are harness bookkeeping artifacts, not part of the ticket's diff.

## Skeptical checks that passed

- The precision fix is correct. At step 3 the code is not yet committed
  (commit is a later protocol stage), so "commit any rewrites" was
  inaccurate; "let any rewrites land in the tree" correctly describes
  ruff `--fix`/`format` mutating the working tree for the stamp to gate.
  Mirrors the action-stages precedent at `SKILL.md:54-58`.
- The `--files <changed>` / mypy `pass_filenames: false` trap flagged in
  ticket section 11 fork 1 is handled: "the type hook still runs over its
  whole configured target inside it" accurately states mypy runs
  project-wide regardless of the file filter. Not misleading; a strength.

No required fixes.
