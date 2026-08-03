---
verdict: pass
tree: 19b0e9c1373ea62fda3e656a5476ea831ec47a4a
---

# Adversarial review, cycle 3 (final) — R5-rollout-memex-oidc-auth

Reviewed in `/home/vscode/workspace/.loop/worktrees/R5-rollout-memex-oidc-auth`
on branch `main`, bound to tree `19b0e9c1373ea62fda3e656a5476ea831ec47a4a`.
This overwrites my cycle-3 verdict bound to `2541057651a0052ab4e674d8f907313bfc84b514`.

Both items I raised are fixed and correct. I re-verified the `just` command
by dry-run and the fallback-semantics rewrites against the upstream source
they describe, not against the hand-off summary. Nothing new blocks. Four
nits below, none required.

## Deterministic floor

`loopctl verify-eval-substance R5-rollout-memex-oidc-auth` returns `valid`,
exit 0. No mechanical eval defect, so I ran the full semantic pass.

## Gates and fingerprint, re-run independently

`just pre_commit`: all 14 hooks pass, including `Nomad Format`, `Terraform
Format (fmt -check -recursive)` and `Terraform Validate (per root)`.

`loopctl verify`: `ok`.

I recomputed the fingerprint myself the way `loop_harness/stamp.py:110-137`
does it (throwaway `GIT_INDEX_FILE`, `git add -A`, `git rm -r --cached .loop`,
empty `fingerprint_ignore`, re-add `.loop/config.json`, `git write-tree`) and
got `19b0e9c1373ea62fda3e656a5476ea831ec47a4a`. Matches `.loop/stamp.json:2`
and the fingerprint I was given.

## The docs-only claim: verified true

```
$ git diff --stat 2541057 19b0e9c1373ea62fda3e656a5476ea831ec47a4a
docs/memex-oidc-verification.md | 25 ++++++++++++++++-------
```

One file, 18 insertions, 7 deletions. No `deployments/` file moved since the
tree I reviewed last cycle. Against the cycle-1 tree the picture is the same
shape:

```
$ git diff --stat 66ba508b 19b0e9c1373ea62fda3e656a5476ea831ec47a4a
docs/memex-oidc-verification.md | 95 ++++++++++++++++++++++++++---------
docs/workload-identity.md       |  7 ++-
```

I re-read the load-bearing infrastructure lines anyway rather than trusting
the stat: `deployments/applications/services/memex.hcl:148` (the provider
JSON, after the `{{- end }}` at `:141`, single-quoted, one element, one grant
rule, no `default_policy`), the `locals` block at
`deployments/applications/services.tf:21-26`, the identity stanza at
`deployments/applications/services/hermes.hcl:412-419`, the two
`env_passthrough` lists at `:257-268` and `:271-282`, the wheel pins at
`deployments/applications/services/hermes/Dockerfile:28-30`, and the image
tag `0.19.1-memex-v1.1.0` at `deployments/applications/services.tf:119`.
Unchanged from what I passed in cycle 1.

## REQUIRED FIX 1 (cycle 3) — CLEARED

`docs/memex-oidc-verification.md:83` now reads `just apply true
nomad_job.memex`. I did not take the hand-off's word for it; I ran both forms
through `just --dry-run` in `deployments/applications`:

```
$ just --dry-run apply true nomad_job.memex
    echo ">> Applying target: nomad_job.memex"
    terraform apply -var-file=./vars/prod.tfvars -refresh=true -target=nomad_job.memex

$ just --dry-run apply target=nomad_job.memex
    echo ">> No target specified, applying all resources"
    terraform apply -var-file=./vars/prod.tfvars -refresh=target=nomad_job.memex
```

The old form bound `target=...` to the first positional (`refresh`) and
targeted nothing; the new form is right. The recipe signature is `apply
refresh="true" target=""` (`deployments/applications/justfile:14`), so the
added parenthetical about positional order is accurate.
`grep -rn 'apply target=' docs/` returns nothing.

## MINOR (cycle 3) — CLEARED, and correct on the substance

I fetched `memex_common/auth_client.py` at tag `v1.1.0` and read the actual
resolution order rather than relying on P12:

```python
# resolve_client_headers, lines 196-201
bearer = await _resolve_bearer(config, client=client)
if bearer is not None:
    return {'Authorization': bearer}
if config.api_key is not None:
    return {'X-API-Key': config.api_key.get_secret_value()}
return {}
```

`_read_workload_token` (lines 240-271) returns `None` on a missing/unreadable
file (warning `Could not read workload token file %s: %s`, line 258), on an
empty source, and on an unset env var. So the API key is reachable only when
the bearer does not resolve. All three rewrites are correct against that:

- Intro, `docs/memex-oidc-verification.md:13-16` — "applies only when the
  bearer fails to resolve at all ... Once a bearer resolves, the client sends
  it and nothing else." Exact.
- W1, `:76-79` — "Once the bearer **resolves** ... (The fallback survives
  only where the bearer does NOT resolve at all, which is precisely what H2
  hunts for.)" Consistent with H2 at `:184-194`, whose two greps both target
  non-resolution faults.
- S2 close, `:212-216` — the misconfiguration/rejection split is right, and
  the passage no longer calls the static keys a safety net for the checks
  above.

No contradiction remains between the intro, W1, H2 and S2.

## Independent correctness checks I ran on the frozen infrastructure lines

Not required by the delta, but I would not sign off on a config I had only
read second-hand. All against upstream `v1.1.0`:

- Provider schema (`memex_common/config.py:1463-1545`): `issuer`, `audience`
  (`min_length=1`), `grant_rules[{claim,value,policy}]`, `default_policy`
  defaulting to `None`. The env line at `memex.hcl:148` uses exactly these
  names. `policy: admin` is valid (`POLICY_PERMISSIONS`, `:1326-1330`).
  `issuer` passes the `require_https` validator.
- `model_validator validate_has_authorization` (`:1536-1545`) requires at
  least one `grant_rule` **or** a `default_policy`. The line ships one grant
  rule, so it loads. Leaving `default_policy` unset is what makes D2's
  refusal real, and the comment at `memex.hcl:144-145` says so correctly.
- D1/D2 discriminator (`memex_core/server/oidc.py`): provider selection is by
  `iss` (`:167-170`), then `aud` is an essential claim option (`:203`); a
  failure logs `OIDC token rejected for issuer %s: %s` (`:209`). A verified
  token that matches no rule returns `None` from `_claims_to_context`
  (`:90-98`) with **no** log call. So D1 emits the line and D2 emits nothing,
  exactly as the runbook and the eval say.
- S1's expected string is verbatim: `'OIDC bearer-token authentication
  enabled (%d provider(s)).'` (`oidc.py:290`).
- `change_mode = "noop"` is justified by the same source the comment claims:
  `_read_workload_token`'s docstring says the token is read "fresh on each
  call", so no restart is needed to pick up a rotation.

## Scope

Every changed line traces to §7. `deployments/` touches are the four files
the ticket names and nothing else. `tests/wi-vault-probe.nomad.hcl:43` still
carries `change_mode = "restart"` — correctly left alone. No
`vault_identity_oidc_client`, no `deployments/infrastructure/` file, no edit
to `docs/vault-human-auth.md`: eval guardrail G1 holds by grep.
`MEMEX_SERVER__AUTH__KEYS` (`memex.hcl:140`) and `MEMEX_API_KEY`
(`hermes.hcl:201`, `:437`) are both untouched: G2 holds.

Doc hygiene on the two markdown files: 0 em dashes in the runbook, 1 in
`workload-identity.md` (inside budget), no ` -- `, no smart quotes, no tier-1
slop, no `TODO`/`FIXME`, all prose wraps at 80 except a pre-existing
89-column file path at `docs/workload-identity.md:68` that this diff did not
touch. Every cited path resolves: `deployments/applications/secrets.tf:79-86`
(the `memex_auth_keys` resource), `vars/prod.tfvars.example:1`
(`secret_mount = "secret"`), `/opt/hermes/.venv` (`Dockerfile:25`).

## Nits — not required, recorded so nobody "fixes" them later

1. **The eval's W1 precondition still says "BEFORE any `MEMEX_OIDC__*` var is
   set"**, which `docs/memex-oidc-verification.md:70-74` correctly proves is
   unreachable: the stanza and the vars render from one `templatefile` into
   one `nomad_job.hermes`. The eval is operator-signed and
   `verify-eval-substance` is clean; the substance of W1 (present the raw
   token, expect `200`, assert the three claims) is identical in both, so an
   implementer reading the runbook is not misled. Carried from cycle 2 by
   agreement. Same for the eval's `hermes.hcl:254-262` / `:265-273`
   `env_passthrough` anchors, which are pre-change line numbers (now `:257-268`
   and `:271-282`). Record both in the commit message as planned.

2. **H2's greps miss one non-resolution warning.** `_read_workload_token`
   also warns `Workload token source is empty (grant=%s)`
   (`auth_client.py:268`) when the file exists but is blank. Neither
   `grep -i 'workload token file'` nor `grep -i 'Falling back to X-API-Key'`
   matches it. H1 still catches that case (it would return `X-API-Key`), so
   the check set as a whole has no hole. Low likelihood; not worth a cycle.

3. **S1's stated cause is narrower than the symptom.**
   `docs/memex-oidc-verification.md:35-38` attributes a missing OIDC log line
   to "the JSON in `MEMEX_SERVER__AUTH__OIDC` failed to parse". Malformed JSON
   would actually fail pydantic validation and crash startup (loud). The
   genuinely silent case is `setup_oidc` seeing an empty `auth_config.oidc`
   (`oidc.py:283-286`), e.g. the env var never rendered. The operator action
   is the same either way, so the check works; only the diagnosis sentence is
   slightly off.

4. **The `locals` block is new rather than appended** to the existing one at
   `services.tf:28`. Q2's recommendation said "add to the existing `locals`
   block". Terraform merges multiple `locals` blocks, so this is equivalent,
   and the separate block reads better with its own comment. Cosmetic.

## Verdict

`pass`. The one required fix from cycle 3 is applied and dry-run verified;
the minor is applied and verified against the upstream code it describes; the
gates and the eval floor are clean; the fingerprint I recomputed matches the
one I was given; and no `deployments/` line moved since the tree I already
cleared.
