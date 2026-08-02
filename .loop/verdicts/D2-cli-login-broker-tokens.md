---
verdict: pass
tree: 1e32a12139e2e4c07ae0c9e63cb5f53f6aad789f
---

# D2-cli-login-broker-tokens — adversarial review, round 4 (fix confirmation)

Both required fixes landed correctly. The three findings from round 2 remain
closed, and the two I raised in round 3 are now closed too. Nothing new. Pass.

## Fingerprint

`1e32a1213` is the worktree index tree (`1c34314e`) with `.loop/` stripped
and `.loop/config.json` retained, the same derivation that produced
`7dedeaa6` last round. I rebuilt it to confirm rather than take it on trust.
I extracted it with `git archive` into `/tmp/d2b` and ran every experiment
there; `diff -r` against the worktree `cli/` is clean and `git write-tree`
still reports `1c34314e`, so the repo was never written to.

## Gates

`just pre_commit` from the worktree root: **14/14 Passed**, including Ruff
lint, Ruff format, Mypy (strict, cli/) and Pytest (cli/). Against the
extracted tree: **172 passed, 7 deselected**. The counts match the hand-off.

## Delta since the tree I passed with fixes

4 files, +26/-5. `auth/session.py`, `auth/vault_token_file.py`,
`tests/auth/test_session.py`, `tests/auth/test_vault_token_file.py`. Nothing
else moved. Every line traces to REQUIRED-1 or REQUIRED-2.

## REQUIRED-1 (dead `FILE_MODE`) — closed

`grep -rn FILE_MODE cli/src cli/tests` matches nothing but stale `.pyc`
bytecode, and no bytecode is tracked (`git ls-files | grep -c __pycache__`
is 0). The constant is gone from both modules and had no other referent.

The docstring rewrite at `auth/vault_token_file.py:41-46` is an improvement,
not just churn. The old text promised 0600 without naming what enforced it,
which is exactly the trap the dead constant set. The new text names `mkstemp`
and gives both reasons for the temp-file-plus-rename. Accurate: `mkstemp`
does open at 0600, and both the chmod window and the name collision are real.

The property is still guarded independently.
`test_write_sets_the_mode_at_creation_not_afterwards` and
`test_save_sets_the_mode_at_creation_not_afterwards` still record the `mode`
argument to `os.open` and still assert `modes == [0o600]`. Removing the
constant did not remove the check.

## REQUIRED-2 (the surviving mutant) — closed

I replanted the mutant myself rather than reading the report, and in both
writers rather than one. Reverting `session.py` and `vault_token_file.py` to
`path.with_name(f".<name>.{os.getpid()}")` plus
`os.open(..., O_CREAT | O_WRONLY | O_EXCL, 0o600)`:

```
FAILED tests/auth/test_session.py::test_a_leftover_temp_file_does_not_block_a_later_save
       - FileExistsError: [Errno 17] File exists
FAILED tests/auth/test_vault_token_file.py::test_a_leftover_temp_file_does_not_block_a_later_write
       - FileExistsError: [Errno 17] File exists
2 failed, 170 passed, 7 deselected
```

Two mutations, two failures, one per writer, each with the exact exception
the round-2 finding described. The mutant that survived last round is dead.
Sources restored from a fresh `git archive` afterwards and verified identical.

Both tests are honest about what they check. Each drops a `.<name>.<pid>`
file using the live pid, which is the precise name the old code would have
picked, then writes and asserts the result is readable. Neither touches a
real home: `test_session.py`'s row uses `tmp_path`, and the token-file row
relies on the suite-wide `isolated_environment` fixture that redirects
`HOME`, the same way `test_the_token_path_is_under_home` beside it does.
The function-local `import os` in the session row follows the convention
already set by two tests above it in the same file.

## Round 2's three findings, still closed

Verified against `7dedeaa6` last round and untouched by this delta:

1. **The crash window in `login`.** `commands/login.py:91` captures the
   previous session before the prompt, `:132-133` persist, `:138` revokes.
   The `ENOSPC` replant leaves zero revoke calls and the old, still-valid
   token in the cache. Moving `_revoke_previous` back above `save` fails
   `test_the_new_session_is_persisted_before_the_old_one_is_revoked`.
2. **The `O_EXCL` collision.** Fixed by `mkstemp` in both writers, and now
   regression-tested. See above.
3. **The live suite.** `uv run localstack` reaches the CLI where
   `python -m localstack_cli.main` was a silent `rc=0`. The corrected
   `vault write auth/token/lookup-accessor accessor=X` returns 0 for a live
   accessor and 2 for a dead one, and `nomad acl token info X` returns 0 and
   1, so both revocation asserts now discriminate. I ran the suite against
   the real cluster: 7 passed in 29s, accessors 25 before and 25 after.

## Noted, not blocking

Unchanged from round 3 and deliberately left:

- When `save` raises, the new Vault token and both leases are orphaned and
  the `OSError` escapes as a raw traceback rather than through `fail()`. The
  old session survives and a retry fixes it, and the self-inflicted trigger
  is gone now that the collision is.
- `mkstemp` litters where the old form reused a name. Never blocking beats
  never littering, and it is not a new leakage class.
- `test_live_login.py:6` documents `uv run pytest -m cluster` without saying
  it only works from `cli/`. `just -f cli/justfile test_cluster` encodes it.

Carried forward for the documentation pass or a later ticket, all outside
this fingerprint or outside the ticket's scope:
`.loop/evals/D2-manual-eval-results.md:3` test count and its line 95 claim;
`cli/tests/fixtures/cluster.py:106` using `field(default_factory=list)` on a
non-dataclass; `commands/env.py:46` emitting unquoted `export`;
`commands/whoami.py` omitting `lease_id` from the text form;
`docs/cli-login.md:114-117` covering only the with-session `logout`.

## Bottom line

Both fixes are correct and both are now enforced by a test that fails without
them. Four rounds in, every finding I raised is closed and independently
re-verified. Ship it.
