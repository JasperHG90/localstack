eval: loopctl-typer-pydantic-toml

Definition of Done: the harness runs on typer+rich, pydantic, and TOML config under the plugin's synced uv project env, with config still failing loud, the launcher still failing open, and the docs no longer claiming to be dependency-free — the substrate changes, the behavior does not.

| Behavior | Input | Expected | Scorer | Threshold |
|----------|-------|----------|--------|-----------|
| A bare-string `gates` value is refused, not silently coerced | `.loop/config.toml` with `gates = "pytest"` (a string where a list is required) | `load_config` raises `ConfigError` naming the list requirement; it never returns a config whose gates were char-split into single characters | Deterministic (test) | 100% |
| `require_review` with no enabled review pass is a hard error | `.loop/config.toml` with `require_review = true` and every `review_passes` entry `enabled = false` | `ConfigError` carrying the specific "require_review but no enabled pass" message | Deterministic (test) | 100% |
| An empty `fingerprint_ignore` pattern is rejected | `.loop/config.toml` with `fingerprint_ignore = [""]` | `ConfigError` naming the empty-pattern guard | Deterministic (test) | 100% |
| A duplicate review-pass / action-stage id is rejected | `.loop/config.toml` with two `review_passes` sharing one `id` | `ConfigError` about id uniqueness across passes and stages | Deterministic (test) | 100% |
| An action stage whose `after` anchor is unknown is rejected | `.loop/config.toml` with an action stage `after = "no-such-stage"` | `ConfigError` naming the missing anchor | Deterministic (test) | 100% |
| With `uv` absent from PATH, the hook shim fails OPEN, loudly | run `scripts/run_hook.py session-start` under a PATH that omits `uv` | exit 0, stderr reads `loop NOT active: uv not found; run init-loop`, no traceback, nothing blocked | Deterministic (real process) | 100% |
| With `uv` absent from PATH, the git-backstop shim fails OPEN, loudly (the commit proceeds) | run `scripts/run_git_hook.py` under a PATH that omits `uv` | exit 0, loud stderr message, the commit is not blocked | Deterministic (real process) | 100% |
| The docs no longer claim "dependency-free / stdlib-only" | grep `MANIFESTO.md` and `README.md` for `stdlib-only`, `dependency-free`, `zero-install` | zero live matches in body prose | Deterministic (grep) | 100% |
| No live `.loop/config.json` reference survives in the skill/doc/agent surface | `grep -rn "config.json" skills docs agents` | zero matches in instructional text (DECISIONS / historical mentions excluded) | Deterministic (grep) | 100% |
| All 19 `loopctl` subcommands keep their behavior and constraints | run each of the 19 subcommands in a temp repo; also `advance <slug> bogus-stage` and `block <slug> bogus-code` | each returns its pre-change exit code; the invalid stage and invalid code are rejected by the `choices` constraint | Deterministic (parametrized test) | 100% |
| rich formatting does not corrupt machine-parsed output | run `loopctl ledger` (delegates to `hooks.main`) and the `reconcile` / `verify` delegations | the machine-readable lines downstream code parses carry no ANSI / rich decoration; their structure is byte-stable | Deterministic (test) | 100% |
| `loopctl init` writes a TOML config that round-trips to the documented defaults | run `loopctl init` in an empty repo | a `.loop/config.toml` is written via `tomli-w`; `load_config` re-parses it into the documented default `LoopConfig` | Deterministic (test) | 100% |
| A missing config yields safe defaults with zero gates, not a crash | a repo with no `.loop/config.toml` | `load_config` returns defaults with empty gates; the loop runs ungated and does not raise | Deterministic (test) | 100% |
| The SessionStart context advertises the new invocation | run the session-start hook | the `[loop] ctl:` line prints `uv run --project "…" loopctl`, not `python3 …/scripts/loopctl.py` | Deterministic (test) | 100% |
