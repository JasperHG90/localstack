---
type: verdict
title: 'Verdict: ci-openviking-sync reviewer round 1'
description: 'reviewer verdict for round 1 of ci-openviking-sync: fix.'
tags:
- verdict
- review
generated:
  by: claude-opus/5.5
  at: '2026-11-15T23:01:35+00:00'
slug: ci-openviking-sync
pass: reviewer
round: 1
body_schema: verdict/1
---

## Summary

The change does what the plan and the eval rows say. sync.py follows r4's
partial-failure semantics exactly. The Terraform scopes each CI caller to its
own prefix and leaves the keyless Nomad roles untouched. The action's
credential handling is sound, and the docs match the code. One non-blocking
gap remains: the action.yml credential step has no test, unlike lab-auth's.
I confirmed the `meta.role` default live against Vault 2.0.3. The label is
fix.

## Checked

- Gates: I re-ran `loopctl gate stamp` from the worktree. All passed:
  pre_commit, cli_tests, r1 to r7. Result: "stamp green:
  37f2d491888c2b50bfc317423d1ce07d4e5679d12f3a9c25bab6ab0e2d29b643".
- sync.py, read in full:
  - It hashes only `git ls-files -z` output and skips submodules and
    deleted-but-tracked files.
  - Only `NoSuchKey` counts as an empty manifest. Any other read error exits
    before a put or delete, which test_unreadable_manifest_stops_the_run
    covers. spike:ci-openviking-sync/1 check 7 showed that SeaweedFS returns
    NoSuchKey, not AccessDenied, for a missing key when the credential has no
    List.
  - Uploads run first, then deletes, through one pool. `state` changes only
    on the main thread. A failed upload keeps the old hash or no entry, and a
    failed delete keeps its entry.
  - The manifest is written whenever the state changed, a failed manifest
    write counts as a failure, and any failure exits 1. That matches r4.
  - Concurrency between runs relies on the workflow's queue
    (`cancel-in-progress: false`). The comment on how GitHub replaces a
    pending run is correct.
- Rows r1 to r6: I read each test against its `fails_when`.
  - r1 asserts the exact put lists across two runs, an untracked file left
    out, and the prefix on every key.
  - r2 asserts the exact delete list, that the kept file survives, and the
    exact manifest.
  - r3 asserts no put or delete on a rerun, and a first run on a NoSuchKey
    manifest that exits 0.
  - r4 checks every clause, including the retry that removes docs/c.md. An
    all-or-nothing manifest write would fail its `docs/b.md not in manifest`
    assert.
  - r5 asserts the triggers, environment, permissions, timeout and
    concurrency.
  - r6 renders the real IAM JSON with terraform console. It asserts Principal
    vault, a StringEquals condition only on ci_repository, exactly the three
    actions, and exactly `ov-sync/<repo>/*`. Nomad roles are pinned
    separately by test_one_role_per_keyless_job.
- Credential step:
  - The JWT is masked before the STS call. All three STS values are masked
    before python runs and are exported to that step's processes only. None
    go to $GITHUB_ENV.
  - The STS call matches the spike: `arn:aws:iam::role/<role>` and a
    RoleSessionName. The issuer in services.tf is
    `https://vault.lab.orangecluster.nl/v1/identity/oidc`, which matches
    `vault_identity_oidc.lab` (issuer `https://${var.vault_issuer_host}`).
- `meta.role`: I tested it live. I ran a dev Vault 2.0.3 with a jwt-github
  mount, logged in with a locally signed RS256 JWT
  (`user_claim=repository`), and called lookup-self. It returned
  `meta = {"role":"localstack-openviking-sync"}`. Reading
  `identity/oidc/token/ci-localstack-openviking-sync` with only the
  per-path policy returned a token with `aud: seaweedfs` and
  `ci_repository: JasperHG90/localstack`. The derived default is reliable
  and needs no explicit fallback.
- Terraform:
  - The keyless policy and role bodies are moved unchanged inside `concat`.
  - `seaweedfs` is in `allowed_client_ids`.
  - `vault_policy.ci_ov_sync` reads only its own token path.
  - token_policies uses a conditional index. HCL drops the diagnostics of the
    branch it does not take, and validate passes.
  - The variable's `optional(bool, false)` keeps the existing caller
    unchanged, and test_default_callers and the token_policies assert cover
    it.
- The pre-commit change: ruff, ruff-format and mypy now cover
  `.github/actions`. ruff uses default config there, the same as `scripts/`
  already does. mypy is given the action directory and uses strict via
  `--config-file`.
- r9 (judgment): I find no `secrets.` reference, stored key or token in the
  diff. The workflow needs none, because lab-auth uses the GitHub OIDC token
  and the S3 credential is minted per run. Pass.
- r10 (judgment): I read ADR 0028, the seaweedfs and vault-identity component
  pages, the workload-identity explanation, the reference page and the how-to
  against the code. Inputs, defaults, names (`ci-<key>`,
  `ci-ov-sync-<key>`), TTL 900 and the issuer all match. The how-to follows
  the skeleton, and its test passes. The `_state/` skip claim matches
  applications/ov-sync-consumer/internal/consumer/mapping.go:52. The
  `prefixes` example matches deployments/applications/services.tf:658.
  Pass.
- r8, last clause (a refused write under another repo's prefix): this can
  rest on spike:ci-openviking-sync/1 plus r6, and needs no new check in the
  build. The spike showed SeaweedFS 4.48 enforces prefix scope inside the
  shared bucket. r6 proves the deployed config has the same shape. At r8
  time the operator can show it live without code. With an entity-bearing
  admin Vault token, read `identity/oidc/token/ci-localstack-openviking-sync`
  (the claim is a literal, so it matches CI's), assume the role, and try a
  put under another prefix, for example `ov-sync/other/repo/x`. I recommend
  recording that in r8's evidence.

## Findings

- f1 (test-strength, non-blocking): sync.py is well tested, but nothing
  tests action.yml's credential step. The sibling lab-auth action has a
  shape test that pins masking order and keeps secrets out of $GITHUB_ENV.
  A static test that parses action.yml would cover four things:
  - each `::add-mask::` comes before the first use of its value;
  - no `GITHUB_ENV` or `GITHUB_OUTPUT` write and no `secrets.` reference;
  - the role ARN is `arn:aws:iam::role/$role`;
  - the default is `ci-` plus `meta.role`.
  That would keep this hardening in place.

## Notes

- The .okf/summary.md diff also trims unrelated sentences ("on one LAN",
  "Nomad and Consul tokens", "is a draft"), presumably to stay within 500
  words. These are acceptable, but "on one LAN" was a true fact the trim
  removed.
- In action.yml, a failed lookup-self uses `curl -sSf` and gives only curl's
  error, with no `::error::` hint like the identity-token read has. This is
  cosmetic.
