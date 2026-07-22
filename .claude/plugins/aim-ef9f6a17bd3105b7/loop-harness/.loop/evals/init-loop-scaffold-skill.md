eval: init-loop-scaffold-skill

Definition of Done: the `init-loop` skill takes an unconfigured repo to a
verified, green, ready-to-commit loop config without overwriting existing
state and without committing.

| Behavior | Input | Expected | Scorer | Threshold |
|----------|-------|----------|--------|-----------|
| Proposes real gates for a Python repo instead of the placeholders | A repo with `pyproject.toml` declaring pytest and ruff, and no `.loop/config.json` | Runs `loopctl init`, then proposes concrete gates (e.g. `uv run pytest`, `uvx prek run --all-files`) in place of the example placeholders, and asks the operator to confirm before writing them | Human or LLM judge, rubric | 4/5: gates are repo-appropriate and confirmation is requested |
| Falls back to a generic proposal for an unrecognized stack | A repo whose only task runner is a `Makefile` exposing `make verify`, with no `pyproject.toml` or `package.json` | Does not invent commands absent from the repo; proposes the repo's blessed invocation (`make verify`) via the generic "inspect the task runner" rule, and confirms with the operator | Human or LLM judge, rubric | 100%: no fabricated command that is absent from the repo |
| Leaves the mandatory adversarial review pass enabled | The fresh-repo run through to writing the config | The written `.loop/config.json` has the `adversarial` pass with `enabled: true`, and does not silently enable `architectural` or `documentation` | Deterministic check on the written config | 100% |
| Applies the prescribed gitignore and commit contract | The fresh-repo run | `.gitignore` gains `.loop/stamp.json`, `.loop/HALT`, and `.loop/handoff.log`; the skill states that `.loop/config.json` and `.loop/ledger.json` are committed, not ignored | Deterministic grep for the three entries; judge for the stated contract | 100% on the three entries |
| Verifies the config is green before handoff | The fresh-repo run after gates are chosen | Runs a dry `loopctl stamp` and confirms it is green; on a red stamp, reports the failing gate and does not declare the repo ready | Human or LLM judge, rubric | 4/5 |
| Stops at "ready to commit" and hands off | The fresh-repo run carried to completion | Final message says `.loop/config.json` + `.loop/ledger.json` are ready to commit and leaves the commit to the operator | Human or LLM judge, rubric | Pass |
| GUARDRAIL: refuses to overwrite an existing config | A repo that already has a `.loop/config.json` with custom gates | The skill stops, tells the operator to edit the existing config instead, and the config file's bytes are unchanged after the run | Deterministic: byte-for-byte compare of the config before and after | 100% |
| GUARDRAIL: never commits on the operator's behalf | Any full run of the skill | No `git commit` is invoked by the skill; the repo's `HEAD` is the same commit before and after the run | Deterministic: `HEAD` sha unchanged | 100% |
