eval: loopctl-install-and-derived-version

Definition of Done: `loopctl` has a documented `uv tool install` path
(README + `just` recipe) and `pyproject.toml` derives its version from
`.claude-plugin/plugin.json`, so the single number the
`release-claude-code-plugin` skill bumps is authoritative for both the
plugin and the installable package. The zero-install plugin path and
`marketplace.json` are untouched.

| Behavior | Input | Expected | Scorer | Threshold |
|----------|-------|----------|--------|-----------|
| The package version is derived from `plugin.json`, not restated | `pyproject.toml` `[project]` and `[tool.hatch.version]` | `dynamic` contains `"version"`, no static `version` key, and `[tool.hatch.version]` `path` = `.claude-plugin/plugin.json` with a named-group `pattern` | Deterministic (`test_manifest.test_pyproject_version_derives_from_plugin_json`, `tomllib`) | 100% |
| The regex source resolves (single-sourcing makes divergence structurally impossible) | apply the configured `pattern` to the pointed-at file | `pattern` matches and captures exactly one `version` group; no static `version` key reappears | Deterministic (same test, reproduces hatchling's regex source) | 100% |
| A build reads the version from `plugin.json` end to end | `uv build` at `0.1.0`, then `plugin.json` bumped to `0.1.1`, rebuild, revert | artifacts are `loop_harness-0.1.0-*` then `loop_harness-0.1.1-*` | Deterministic (artifact filename) | 100% |
| `loopctl` is installable and documented as a standalone tool | `just install` recipe + README Install section | `just install` runs `uv tool install --force .` and puts `loopctl` on `PATH`; README shows the local and `git+https://…` forms | Deterministic (`loopctl --help` after install; grep README) | 100% |
| Guardrail: the zero-install plugin path stays honest | the README "no install step" claim (`README.md:155`) and the new Install prose | the claim survives; the new text frames `uv tool install` as optional/additive for standalone CLI use only | Human (adversarial + architectural review) | Must hold |
| Guardrail: `marketplace.json` gains no version field | `.claude-plugin/marketplace.json` after the change | unchanged; no `version` key added | Deterministic (git diff empty for the file) | 100% |
| Guardrail: no runtime code changes; surgical diff | `git diff` scope | only `pyproject.toml`, `justfile`, `README.md`, and `tests/test_manifest.py` change; nothing under `src/loop_harness/` | Deterministic (diff paths) | 100% |
| Guardrail: repo gates and doc slop-scan stay green | `uv run pytest`, `uvx prek run --all-files`, `.claude/rules/slop-scan-for-docs.md` on the README edit | all green; README edit passes the P0/economy/sentence layers | Deterministic (gates) + Human (slop-scan) | 100% |
