verdict: pass
tree: 08b71a1ac37d50df8aa2501e904fdda774ae7c6f
pass: architectural
slug: loopctl-install-and-derived-version
baseline: MANIFESTO.md

# Architectural review — loopctl-install-and-derived-version

Reviewed `MANIFESTO.md` in full and the diff (`git diff HEAD`) against its
invariants and values. Enforcer anchors resolved in code.

## Tree binding

- `.loop/stamp.json` binds tree `08b71a1ac37d50df8aa2501e904fdda774ae7c6f`,
  both gates green. `loopctl verify` returns `ok`.

## Assessment

- **Coupling direction is correct.** The manifesto frames the Claude Code plugin
  as the primary artifact (§1–§2), so `.claude-plugin/plugin.json` holding the
  authoritative version and the Python build deriving from it points the
  dependency the right way. `pyproject.toml` never had version authority the
  manifesto assigned it, and nothing in `src/loop_harness/` reads the package
  version at runtime.
- **Stdlib-only core intact.** `dependencies = []` is unchanged; `hatchling`
  stays a build-backend requirement only, not a runtime dep. The §4 "consumers
  need no install step" value (runtime) is untouched — nothing under `src/`
  changed.
- **"Prompts may, code must" honored.** Single-sourcing is enforced by build
  config (`[tool.hatch.version]`) and guarded by a test
  (`tests/test_manifest.py`), not by a prose convention in a skill.
- **Zero-install intent preserved.** The new `uv tool install` path is framed as
  strictly optional/additive; the README re-asserts the zero-install commitment
  rather than eroding it.
- **No invariant enforcer touched.** `lifecycle.py`, `stamp.py`, `hooks.py`,
  `config.py`, `ctl.py`, `ledger.py`, `reconcile.py`, `evals.py`, `cli.py` are
  all absent from the diff. `tests/test_manifest.py` (the manifest-integrity
  suite) is extended in place.

## Findings

- **F1 (addressed).** The architect flagged that the guard test cannot catch
  "divergence" once the version is single-sourced (both sides read the same
  `plugin.json`). Correct. The ticket §10 subticket 2 and the eval row were
  corrected to state what the test genuinely guards: regex resolution and no
  reintroduced static `version`. No code change required.

## Verdict

PASS. The change is surgical, the coupling direction aligns with the manifesto,
and every invariant enforcer is untouched.
