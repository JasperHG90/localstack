verdict: pass
tree: 08b71a1ac37d50df8aa2501e904fdda774ae7c6f
pass: adversarial
slug: loopctl-install-and-derived-version

# Adversarial review — loopctl-install-and-derived-version

Independent skeptical review of the diff (`git diff HEAD`) against the ticket
contract. Gates and the version-derivation claim were re-run, not trusted.

## Tree binding

- `.loop/stamp.json` binds tree `08b71a1ac37d50df8aa2501e904fdda774ae7c6f`,
  both gates green. `loopctl verify` returns `ok`: the working tree fingerprints
  to the bound tree.

## Claims verified

- **Derivation.** `uv build` produces `loop_harness-0.1.0-*` with the version
  pulled from `.claude-plugin/plugin.json`; bumping the manifest to `0.1.1` and
  rebuilding yields `loop_harness-0.1.1` (reverted). The regex has a single
  capture site in `plugin.json`, so it cannot mis-capture. The sdist ships the
  version-source file, so rebuild-from-sdist and `git+https://` installs resolve
  the version too.
- **Gates.** `uv run pytest` → 274 passed; `uvx prek run --all-files` →
  ruff-lint, ruff-format, mypy all pass. The new
  `test_pyproject_version_derives_from_plugin_json` passes.
- **Surgical.** Nothing under `src/loop_harness/` changed; the zero-install
  plugin path (`scripts/loopctl.py`, SessionStart hook) is untouched;
  `marketplace.json` gained no version field.
- **Zero-install claim honest.** The README's "consumers need no install step"
  survives; the new install text is framed as optional/additive.
- **Install URL resolves.** `git ls-remote` against the README's git URL returns
  refs (matches `origin`).

## Findings

- **F1 (nit, FIXED).** The new "Releasing" prose carried one em dash, against the
  doc slop-scan prevention-mode target of zero. Replaced with a colon; the new
  README regions now contain zero em dashes (`git diff` confirmed).

## Verdict

PASS. The `[tool.hatch.version]` wiring is hatchling's documented regex source,
the named group is correct, and the guard test reproduces that resolution rather
than asserting a constant. The one nit is resolved at this tree.
