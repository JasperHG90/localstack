verdict: pass
tree: f07318510134bcbf3f5b0d8bee9bba9c24528de3

# Adversarial review — stamp-fingerprint-ignore-list (re-run after fixes)

## Verdict: PASS

Both prior findings (F1, F2) are genuinely resolved, all gates re-run
green independently, the tree fingerprint binds, and no caller drift
remains. The deliberate non-rejection of over-broad patterns beyond
empty-string is a defensible resolution of the human-scored eval row.

## Gate re-run (independent)

- `git add --intent-to-add -A . && uv run pytest` → 193 passed.
- `uvx prek run --all-files` → ruff-lint, ruff-format, mypy all Passed.
- Harness `tree_fingerprint(Path('.'))` recomputed to
  `f07318510134bcbf3f5b0d8bee9bba9c24528de3`, exactly the bound tree.

## Prior findings — verification

### F2 (empty-pattern fail-open) — FIXED, sufficient

`load_config` rejects empty/whitespace-only patterns at
`src/loop_harness/config.py:235-240`:
`if not all(p.strip() for p in raw_ignore)`. `""` → `strip()` is falsy;
`"   "` → `strip()` == `""` is falsy — both raise `ConfigError` matching
`"empty pattern"`. Confirmed from the code, not just the test.

Ordering is correct and safe:
- The type check (`config.py:230`) runs BEFORE the empty check
  (`config.py:235`), so a non-string element (e.g. `123`) raises the
  type error rather than an `AttributeError` on `.strip()`.
- The check lives entirely in `load_config`, which makes NO git call.
  In every flow config is loaded before `tree_fingerprint`, so the
  raise precedes any `git rm -- ''`. In the fail-open hook,
  `fingerprint_ignore_failsafe` (`hooks.py:204-214`) catches
  `ConfigError` and returns `()` — the STRICT empty list — so a
  malformed config never RELAXES the fingerprint. Correct direction.

Test `test_empty_fingerprint_ignore_pattern_raises`
(`tests/test_config.py:453-460`) pins `""`. Whitespace-only is not
separately tested but is provably handled by the same predicate; not a
gap worth a finding.

### F1 (over-claim + undocumented shadowing) — FIXED, sufficient

- `tree_fingerprint` docstring (`stamp.py:61-96`) no longer claims real
  code can never commit ungated. It now warns that an over-broad
  pathspec (`.`, `src`) "shadows real source, so a change under it would
  NOT stale the stamp and could commit ungated" and that "honest
  patterns are the operator's responsibility." The false absolute is
  gone.
- `LoopConfig.fingerprint_ignore` docstring (`config.py:178-186`)
  carries the same warning ("shadows real source and silently defeats
  the whole-tree guarantee").
- README (`README.md:83-98`) — the operator-facing surface F1 said was
  missing — now documents `fingerprint_ignore`: git pathspec semantics
  vs `.gitignore` globs (`*` crosses directory boundaries; `*.lock`
  does not match `aim.lock.toml`), subtract-only, the `.`/`src`
  shadowing danger, and empty-pattern rejection.

Eval row G ("git pathspec semantics are documented so an operator
cannot shadow source unknowingly") is now satisfied across three
surfaces, including the operator-facing README.

## Human-scored row G — is documentation-only defensible?

Yes. Static rejection of `.`/`*` is NOT required.

The eval author scored this row on documentation + reviewer flagging,
not rejection, because a complete static denylist is impossible: the
harness cannot distinguish a generated path from source (`docs/`,
`build/`, `lib` are source in some repos), and a plausible-looking
`*.py` or `src` shadows source. A partial denylist (`.`, `*`, `**`)
would create false confidence while `src`, `lib`, clever globs, and
pathspec equivalents (`:/`, `./`, `[a-z]*`) still pass. The empty-string
case is rejected only because it is a distinct failure mode
(`git rm -- ''` is fatal and would be swallowed by the fail-open hook),
not because it is over-broad.

Observation (not required, low severity): the degenerate whole-tree
patterns `.`, `*`, `**` differ from merely-broad-but-plausible ones —
they have zero legitimate use and unconditionally neuter the gate. A
guard rejecting exactly those three would close a footgun with no false
positives. I am NOT requiring it: it is outside the ticket, the eval
endorses the documentation route, and a partial guard risks the
false-confidence failure above. Surfaced for the operator to decide.

## Caller-drift audit — clean

`grep tree_fingerprint(/verify_stamp(/write_stamp(` across `src/`
confirms every production caller threads the resolved ignore-list:
- `stamp.py:167` (`write_stamp`), `stamp.py:202` (`verify_stamp`),
  `stamp.py:217` (`main` via `load_config(repo).fingerprint_ignore`).
- `hooks.py:235,240` via `ignore = fingerprint_ignore_failsafe(repo)`.
- `ctl.py:70,72` via `config.fingerprint_ignore`.
- `cli.py:44,46` via `config.fingerprint_ignore`.
Single-definition invariant holds: all resolve from the same config key
into the one `tree_fingerprint`.

## Eval rows — all pass

- A (real edit still stales): `test_ignore_list_never_hides_a_real_source_change`,
  `test_verify_stale_when_non_ignored_file_moves_despite_ignore_list`.
- B (generated churn no longer stales): `test_fingerprint_ignores_configured_paths`,
  `test_verify_ok_when_only_ignored_file_added_after_stamp`.
- C (absent key preserves whole-tree): `test_absent_ignore_list_is_backward_compatible`,
  `test_absent_fingerprint_ignore_is_empty`.
- D (callers fingerprint identically): `test_all_callers_fingerprint_identically_via_config`
  plus the grep audit above.
- E (malformed fails loud): `test_bare_string_fingerprint_ignore_raises`,
  `test_non_string_fingerprint_ignore_elements_raise`.
- F (under-ignores, never over): `test_ignore_pattern_uses_git_pathspec_not_gitignore`
  (empirically confirms `*.lock` does not match `aim.lock.toml`).
- G (human): satisfied per the documentation assessment above.

Every new stamp test passes the `ignore=` argument the old signature
could not accept (`TypeError` against pre-change code) and every new
config test reads `fingerprint_ignore` (`AttributeError` against old
code), so none are vacuous — they fail against the old tree.

## Scope

Every changed line traces to the ticket. The one addition beyond bare
thread-through — `fingerprint_ignore_failsafe` in `hooks.py` — is
justified and correct: the hook fails open, so a `ConfigError` there
must not silently disable the gate; the failsafe returns the STRICT
`()` on a broken config, preserving the whole-tree guarantee. In scope.
