---
verdict: pass
tree: 395322fe9bc7fb75b06eff43aae2bc152a04a6d8
---

# Adversarial review, cycle 3 (final): D3-cli-read-commands

## Deterministic floor

`loopctl verify-eval-substance D3-cli-read-commands` returns `valid` (exit 0).
No mechanical eval defect, so I ran the full semantic pass.

## Gates, re-run

| Gate | Result |
|---|---|
| `just pre_commit` | exit 0, all 14 hooks Passed (Ruff lint, Ruff format, Mypy strict, Pytest all report files checked) |
| `loopctl verify` | `ok`; `.loop/stamp.json` carries `395322fe...`, matching the fingerprint I was given |
| `uv run pytest` (cli/) | 473 passed, 17 deselected, 7 snapshots passed |
| `uv run pytest -m cluster` (cli/) | 17 passed, 473 deselected |
| `loopctl verify-plan D3-cli-read-commands` | `valid` (two pre-existing line-anchor warnings, unchanged) |

---

## Cycle-2 findings, verified against this tree

### N1 — FIXED, and both new tests are non-vacuous. Verified by measurement.

I reconstructed the cycle-2 code in a scratch copy of `cli/src` (restored
`nomad_list_denied` returning `False` on any `ClusterError`, restored
`known_job=service` in `secret.py`), shadowed the package with `PYTHONPATH`
and ran the two new rows. Both fail against cycle-2 and pass here:

    test_a_nomad_denial_is_never_reported_as_a_dead_session
      AssertionError: assert 'does not authenticate' not in
        'error: nomad: the token does not authenticate. Run `localstack login`.'

    test_the_probe_does_not_re_issue_the_call_that_just_failed
      AssertionError: assert 2 == 1
        where 2 = <Route ... Path eq '/v1/job/hermes'>.call_count

`commands/_session.py:100-115` now returns `True` or `None` and never `False`,
and the docstring states the asymmetry and its reason. The reasoning holds:
Nomad's dead-token case is classified upstream at `api/_http.py` by the body,
so a failed job probe cannot distinguish a dead token from a second policy
gap. The `live is False` branch (`_session.py:55-62`) is now reachable only
for Vault, where `lookup-self` is a different endpoint any live token can
call, and it is still exercised by
`test_a_dead_token_that_looks_like_a_policy_gap_still_says_log_in`, so it is
not dead code.

`commands/secret.py:48-54` no longer passes `known_job`, so the probe goes to
`haproxy` rather than the job that just 403'd.

### N3 — ADDRESSED. The plan now records the divergence.

`.loop/plans/D3-cli-read-commands.md:415-422` carries the
"Amended during implementation, 2026-08-03" note directly under
requirement 3's table, naming `/v1/jobs/statuses`, D4's measured reasons and
D4's guardrail. Leaving the original rows in place with an amendment under
them is a better audit trail than a silent rewrite. `loopctl verify-plan`
still returns `valid`.

### N5 — FIXED. The three `ROADMAP.md` one-liners are correct.

Heading now reads "Shipped since the last re-review round"; N4's row states
"No plan-validator verdict has ever run" instead of the dangling "Same."; the
D3/G2 note (`ROADMAP.md:340-345`) records that G2 landed and D3 shipped, and
the reason it gives is true (`nomad_deploy_role.tf:4` grants neither
`list-jobs` nor node read, so `status` and `service` stay partial).

### N2 — STILL OPEN. Reproduced on this tree.

`api/vault.py:87-98`: `token_is_live` catches `NotAuthenticated` and
`MissingCapability` only. Measured with respx against the shipped tree, Vault
403ing the policy read and refusing the connection on `lookup-self`:

    exit_code: 1
    stdout: ''
    exception: Unreachable('vault: unreachable at
              https://vault.test.invalid/v1/auth/token/lookup-self')

The developer gets a traceback and no message. Requirement 13 asks for a
single line naming the service. This was LOW at cycle 2 and stays LOW: the
probe only runs after Vault has already answered 403, so Vault is reachable
by construction and only a timeout on the second call gets here. It was not
fixed and was not mentioned in the hand-off. One `except ClusterError: return
None` closes it. Not a blocker.

### N4 — I agree with the disposition. Not a blocker.

The eval is unamended (`.loop/evals/D3-cli-read-commands.md:76`, still
`signed-off-by: JasperHG90 2026-07-31`). All four rows still contradict the
shipped code, re-checked here:

- Row 6 (`:57`), `--open`: demands the brokered token be printed "for
  `consul` ... even when the OSC 52 clipboard write reports success". There
  is no `consul` command. The operator cut it, D2 cut `ui consul` on measured
  evidence (`.loop/plans/D3-cli-read-commands.md:510-523`), and
  `cli/tests/commands/test_read_commands.py:210-219` pins the refusal.
- Row 13 (`:64`): scorer wants a footer that "names the filtering token".
  `commands/render.py:27-32` says no token is sent, which is what the code
  does (`api/consul.py` passes none) and what I verified live at cycle 2.
  The honest footer cannot satisfy the row.
- Row 10 (`:61`): `grep -rnE "subprocess|os\.system|shutil\.which"` over
  `cli/src/localstack_cli/` matches `install.py:22,86,92` and
  `commands/breakglass.py:12`. D1's code, not D3's.
- Row 14 (`:65`): `grep -rn "auth_jwt_649fd6cc" cli/` matches
  `cli/tests/api/test_grants.py:88`, the guardrail test that enforces the
  row. The scorer's scope includes the test that implements it.

Not re-signing is right. An implementing agent that edits its own acceptance
criteria has removed the only independent check on its work, and every one of
these four divergences was a deliberate, evidence-backed decision made
downstream of the signature (the operator's surface cut, the F2 footer
correction, D1's pre-existing code, the guardrail test itself). None of them
is the code being wrong. Two of them (rows 10 and 14) are scorer scoping
bugs, not substance.

The one condition: the four rows must be named in the reflection so the
amendment is not lost. `.loop/reflections/D3-cli-read-commands.md` does not
exist at this tree, so I cannot verify it. The harness writes it after this
pass, which is the normal order, so I am not blocking on it. If it lands
without the four rows named, the record is incomplete.

---

## New findings, all LOW, none a blocker

### N6 — LOW. The read-job denial does not name the grant.

`_session.py:25-30`: `GRANTED_BY` maps `nomad.LIST_JOBS` and `nomad.NODE_READ`
but not `nomad.READ_JOB`, which is defined right beside them at
`api/nomad.py:30` and is the capability `job_templates` requests
(`api/nomad.py:174`). Measured on this tree, `localstack service` with every
Nomad job read 403ing:

    error: nomad: denied read-job. That comes from a policy grant.

Requirement 13 asks the message to "name the denied path and the ticket that
grants it". It names the path and falls back to the generic phrase for the
ticket. The N1 fix is what made this path reachable, so the omission is newly
visible rather than newly introduced. Narrow: `nomad_deploy_role.tf:21` grants
`read-job`, so the everyday brokered token never lands here; only a token
narrower than `deploy`, or a job in another namespace, does. One dict entry
closes it.

### N7 — LOW. `service` still re-issues the call that just failed.

Fixed for `secret`, not for `service`. `explain`'s `known_job` defaults to
`"haproxy"` (`_session.py:39`) and `_collect`'s first Nomad call is
`job_templates(..., EDGE_JOB)` with `EDGE_JOB = "haproxy"`
(`commands/service.py:24,81`). Measured: `/v1/job/haproxy` call_count is 2 on
a denial. The consequence is now only a wasted duplicate request and a probe
that can never return `True` on that path, because the N1 asymmetry makes a
failed probe produce the neutral message rather than wrong advice. Output is
correct.

The related test cost: `test_a_denied_nomad_read_probes_a_known_job_before_
blaming_the_session` (`test_read_commands.py:452-472`) drives this with a
403-then-200 `side_effect` on the same URL and asserts `call_count == 2`. Real
Nomad does not deny a job read and then allow it a millisecond later, so that
row pins the re-issue rather than testing a reachable state. The behavior it
claims to cover is genuinely reached by `secret` and by `service` when the
failure is on `job_statuses` rather than on `haproxy`, and
`test_the_probe_does_not_re_issue_the_call_that_just_failed` covers that
honestly.

### N8 — LOW, cosmetic. The plan amendment breaks requirement 3's list.

`.loop/plans/D3-cli-read-commands.md:415` starts at column 0 inside the
numbered list, so under CommonMark it ends the list. Requirement 3's own
trailing paragraph about the diagnostic calls (`:424-428`, indented three
spaces) then renders as a loose paragraph, and requirement 4 starts a fresh
list. Indenting the note four spaces fixes it. Content is right; only the
rendering is off.

---

## What I attacked and could not break

- **The N1 asymmetry, from the other side.** `explain`'s `live is False`
  branch is not orphaned by the change: Vault still reaches it, and the
  cycle-1 regression test still guards it.
- **The loosened D4 guardrail.** `test_monitor_guardrails.py:78-108` narrowed
  its pattern from `auth/token|VAULT_TOKEN` to acquisition-only forms. I ran
  the old pattern over `api/` and `tui/` on this tree: the only hits are
  `api/vault.py:18` (`X-Vault-Token`, a header name), `:86`
  (`auth/token/lookup-self`) and three uses of the header constant. Nothing
  that obtains a token hides behind the loosening, and a broad sweep for
  `login|environ|getenv|\.token =` over both directories finds only docstring
  prose in `api/errors.py`. The comprehension fix at the same site (offenders
  now name the file, not the directory) is a correction, not creep.
- **The everyday Nomad denial.** Under the brokered `deploy` token,
  `service` fails on `job_statuses` (`list-jobs`), the probe reads `haproxy`
  (`read-job`, granted at `nomad_deploy_role.tf:21`) and succeeds, and the
  message names `list-jobs` and D2. That is requirement 13's case (b),
  correct.
- **Scope.** Every tracked change traces to the ticket: `main.py` registers
  the four commands and pins `pretty_exceptions_show_locals=False`;
  `conftest.py` exempts `cluster`-marked rows from the temp-`HOME` fixture;
  `test_live_login.py` adds `--no-sync` with a reason; `README.md` lists the
  four new commands. Nothing under `deployments/` or `bootstrap/` is touched.

---

## Disposition

Nothing remaining is a blocker in the shipped tree. Gates are green including
`-m cluster`, the two cycle-2 required fixes are verified by measurement
against reconstructed old code, and every path I exercised produces correct
output with no wrong advice and no credential exposure.

For the record, carried forward rather than blocking:

1. **N2** — an unreachable `lookup-self` escapes `vault grants` as a
   traceback. One `except ClusterError: return None` in `api/vault.py`.
2. **N4** — four signed eval rows contradict shipped code. Operator's call.
   Name all four in the reflection.
3. **N6** — add `nomad.READ_JOB` to `GRANTED_BY`.
4. **N7** — give `service` a probe job that is not `haproxy`, and retire the
   403-then-200 mock that pins the re-issue.
5. **N8** — indent the plan's amendment note into requirement 3's list.
