---
name: init-loop
description: Bootstrap the loop harness into a fresh consumer repo, collaborating with the operator: scaffold .loop/config.json via loopctl init, propose real gate commands from the repo's own manifests, apply the prescribed .gitignore entries, verify with a dry loopctl stamp, and stop at ready-to-commit. Use whenever an operator wants to set up, initialize, install, or configure the loop harness in a repo for the first time, when a repo has no .loop/config.json yet, or when someone asks how to get the loop running here.
---

# init-loop

Bootstrapping the harness by hand is a scattered checklist: run
`loopctl init`, then remember to replace the placeholder gates with the
repo's real ones, then hand-recall the gitignore rules from the README,
then check the config actually goes green. This skill turns that into
one guided flow that leaves the repo verified and ready to commit,
without ever committing on the operator's behalf.

The harness owns the mechanics: `loopctl init` writes the starter
config, and `loopctl stamp` proves it runs green. Your job is the two
decisions the harness cannot make for the operator: which gate commands
are this repo's blessed invocations, and confirming the operator is
ready. The operator owns the substance; you propose and confirm.

## The seven steps

Follow them in order. Each one has a reason, not just a rule.

1. **Refuse cleanly when the repo is already configured.** If
   `.loop/config.json` exists, stop and tell the operator to edit that
   file instead. This mirrors `write_example_config`, which raises
   `ConfigError` with `already exists; edit it instead` rather than
   overwrite. Re-running init on a configured repo would clobber the
   operator's real gates with placeholders, so the refusal protects
   work already done. Do not delete or overwrite the existing config to
   proceed.

2. **Scaffold the config with `loopctl init`.** Run the harness CLI to
   write a starter `.loop/config.json` from its bundled `EXAMPLE_CONFIG`.
   The SessionStart hook prints the exact CLI path as `[loop] ctl: ...`;
   use that invocation. The starter ships placeholder gates and the
   mandatory `adversarial` review pass already enabled, which the next
   steps refine.

3. **Propose real gates from the repo's manifests, then confirm.** The
   starter gates (`uv run pytest`, `uvx prek run --all-files`) are
   placeholders. Inspect the repo's manifests and task runner and
   propose the commands that actually verify this repo:

   - A `pyproject.toml` with pytest and ruff: `uv run pytest` and
     `uvx prek run --all-files`.
   - A Rust crate (`Cargo.toml`): `cargo test`.
   - A `package.json` with a test script: `npm test`.

   For any other stack, do not invent commands. Inspect the repo's task
   runner (a `justfile`, a `Makefile`, or the manifest's script block)
   and propose its blessed invocation, for example `make verify` when
   that is the recipe the repo exposes. A gate you cannot find in the
   repo is a gate you must not write.

   The gates decide what "green" means for every future ticket, so the
   operator owns them. Put the proposed gate list to the operator with
   `AskUserQuestion` (recommended option: accept the proposed gates;
   alternatives: edit them, or start with a single gate), and write them
   into the config only once the operator agrees. An empty gate list
   never stamps green, so the config must carry at least one real gate
   before handoff.

4. **Keep the `adversarial` review pass enabled.** It is the harness's
   mandatory default: review stays on, gated by an independent
   adversarial verdict. Leave it enabled and do not silently switch on
   the `architectural` or `documentation` passes, which ship disabled.
   Enable those only if the operator asks, so the repo starts with the
   smallest honest gate.

5. **Apply the gitignore and commit contract.** Add these three entries
   to the repo's `.gitignore`, because they are per-run local state that
   must not be shared:

   - `.loop/stamp.json`
   - `.loop/HALT`
   - `.loop/handoff.log`

   Then tell the operator the other half of the contract: commit
   `.loop/config.json` and `.loop/ledger.json`. The config defines the
   gates and the ledger records lifecycle state, so both are shared
   truth, not ignored.

6. **Verify with a dry `loopctl stamp`.** Run the stamp so the config
   parses and the chosen gates run green before handoff. A green stamp
   proves the gates are real commands that pass on the current tree. On
   a red stamp, report the failing gate and do not declare the repo
   ready: a red gate now is a misconfigured gate, not a verified repo.

7. **Stop at ready to commit.** Tell the operator that
   `.loop/config.json` and `.loop/ledger.json` are ready to commit, and
   leave the commit to them. The operator owns the first commit of the
   harness into their history, so hand off there rather than committing
   for them.

## Discipline

- **Propose, do not decide.** Gate selection is a collaboration. Draft
  concrete commands proactively, but write them only once the operator
  confirms they are this repo's real gates.
- **Never fabricate a gate.** Every proposed command must come from the
  repo's manifests or task runner. A command absent from the repo is a
  guess, and a guessed gate certifies nothing.
- **Never overwrite, never commit.** The two hard edges of this skill:
  refuse when a config already exists, and stop before the commit.
  Everything durable the operator gains here, they can review before it
  enters their history.
