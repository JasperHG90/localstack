verdict: pass
tree: 80884e2e73346a07d18904a07e9a254c3ddcfc95

# Adversarial review: fingerprint-binds-loop-config

Scope reviewed: `src/loop_harness/stamp.py`, `tests/test_stamp.py`,
`MANIFESTO.md`, `docs/onboarding.md`,
`docs/tutorials/custom-reviews-and-actions.md`. `.loop/ledger.json` is
harness state, not reviewed. `DECISIONS.md` section F is already committed
at HEAD (verified), so R7 is satisfied in-repo though absent from this diff.

## Gates (re-run independently)

- `git add --intent-to-add -A . && uv run pytest` -> 234 passed.
- `uvx prek run --all-files` -> ruff-lint, ruff-format, mypy all Passed.
- `tree_fingerprint` over the current tree =
  `80884e2e73346a07d18904a07e9a254c3ddcfc95`, matching the bound stamp and
  the briefing fingerprint.

## Premise: sound

The vulnerability is real. Pre-fix `tree_fingerprint` strips all of
`.loop/` before `git write-tree`, so `.loop/config.json` (the `gates` and
`fingerprint_ignore` that DEFINE "green") sat outside the certified tree. I
empirically confirmed against HEAD's pre-fix `tree_fingerprint`: editing
`gates` from `["uv run pytest"]` to `["uv run pytest || true"]` left the
fingerprint UNCHANGED (`old_before == old_after`), so a weakening edit did
not stale a green stamp. The change closes this.

## Requirements

- R1 (bind config): PASS. Post-fix, the same gate-weakening edit changes the
  fingerprint (`new_before != new_after`); `verify_stamp` reads STALE. Proven
  empirically and by `test_config_edit_stales_the_stamp`.
- R2 (bind ONLY config.json): PASS. The re-bind adds exactly `CONFIG_FILE`
  (`stamp.py:127-128`), nothing else under `.loop/`. `test_churny_loop_state_
  still_never_stales_with_config_bound` writes `ledger.json`, `HALT`,
  `reflections/x.md`, and `handoff.log` after a green stamp and it stays OK.
  No leak into other loop state.
- R3 (single-sourced): PASS. The include/exclude policy stays inside the one
  `tree_fingerprint` function (`stamp.py:63-129`); all callers route through
  it. No second definition.
- R4 (undefeatable by `fingerprint_ignore`): PASS. The re-bind runs AFTER the
  `.loop` strip AND after the ignore loop (`if` at `stamp.py:127` is outside
  the `for pattern in ignore` loop at `stamp.py:118-121`). I empirically
  drove `fingerprint_ignore=[".loop/"]` through the current
  `tree_fingerprint` and a config `gates` edit still changed the hash;
  `test_fingerprint_ignore_cannot_exclude_config` parametrizes
  `.loop/config.json`, `.loop/`, and `.loop`. No ignore pattern subtracts the
  contract. I could not construct a way to weaken `gates`, `fingerprint_
  ignore`, or `review_passes` without changing config.json bytes, and any
  byte change stales (whole-file binding, Q1).
- R5 (fail-safe on absence): PASS. The existence guard
  `if (repo / CONFIG_FILE).exists():` skips the re-bind when config is
  absent; empirically no crash, and a real code change still stales
  (`test_config_binding_backward_compatible_when_absent`). Crucially, the
  `-f` is load-bearing here too: I verified a bare `git add -- .loop/config.
  json` in a repo that gitignores `.loop/` exits 1 (fatal under
  `check=True`), which the commit hook's fail-open (`hooks.py:425-427`) would
  swallow and silently disable the gate. With `-f` the binding works even
  when `.loop/` is gitignored (config edit still stales). The `-f` is correct
  and necessary, not gratuitous.
- R6 (manifesto honest): PASS. I6 prose and its enforcer citation
  (`MANIFESTO.md:126-135`) match the code verbatim: the strip
  `git("rm", "-r", "--cached", "--ignore-unmatch", "-q", ".loop")` and the
  re-bind `git("add", "-f", "--", CONFIG_FILE.as_posix())` are both accurate.
  The §2 exclusion note ("All of `.loop/` ... EXCEPT `config.json`") is
  accurate. onboarding mermaid + prose qualified; the tutorial note added.
  The I3 enforcer signature citation is corrected to the real signature
  `def tree_fingerprint(repo: Path, ignore: tuple[str, ...] = ()) -> str:`
  (matches `stamp.py:61`). No em-dashes, no curly quotes, no `--` prose in
  added doc lines.
- R7 (record decision): PASS. `DECISIONS.md` section F (F1-F4) is committed
  at HEAD, covering the whole-file fork (Q1), no config.py validation (Q2),
  the allowlist-of-one rationale, and the rejected edit-forbidding hook.

Repo restrictions: stdlib-only (no new deps); docstring on `tree_fingerprint`
updated to match new behavior (`stamp.py:66-78`); tests use real temp git
repos via the `repo` fixture, no git mocking.

## Test quality

Non-tautological. The reproducer and the R4 tests genuinely fail against
pre-fix code (I loaded HEAD's `tree_fingerprint` and confirmed a config edit
does NOT change the fingerprint there, so the `is StampStatus.STALE`
assertions would fail). R2 and R5 tests are green-witness fences (they pass
pre- and post-fix by design), which is the correct shape for over-binding /
regression guards. The R4 parametrization covers the exact adversarial
pathspecs.

## Non-blocking observations (no fix required)

1. README.md:94-95 ("The list only ever subtracts, so any change outside it
   stales") no longer mentions the `config.json` carve-out: a consumer who
   lists `.loop/config.json` in `fingerprint_ignore` is silently neutralized
   (DECISIONS F3's chosen behavior) rather than warned. The ticket (§7)
   explicitly scoped README out and this does not misdescribe the core
   mechanism, so it is informational only.
2. The I3 enforcer-signature correction is technically outside R6's named
   targets (I6 + §2), but the old citation was already stale at HEAD (it
   omitted the pre-existing `ignore` param), so this is a legitimate
   pre-existing-accuracy fix in a file the ticket edits, and the
   architectural pass reviews signatures against MANIFESTO. Defensible, not
   scope creep.

## Verdict

PASS. Premise sound, all R1-R13 requirements met, gates green, fingerprint
matches the bound tree, tests exercise the real vulnerability and fail on
pre-fix code, MANIFESTO/doc edits are accurate to the code, and no scope
leak beyond the ticket. The `-f` + existence-guard combination correctly
prevents a fail-open-swallowed fatal git.
