---
type: verdict
title: 'Verdict: docs-howto reviewer round 1'
description: 'reviewer verdict for round 1 of docs-howto: fix.'
tags:
- verdict
- review
generated:
  by: claude-opus/5.5
  at: '2026-10-19T19:54:04+00:00'
slug: docs-howto
pass: reviewer
round: 1
body_schema: verdict/1
---

## Summary

The audit holds up. Every procedural fix I checked against the code is right,
and several fix real errors in the old pages: the driftwatch baseline is on a
dynamic host volume, so the old SSH path was wrong; the Consul client agents
run `down_policy = "deny"`, so the old extend-cache claim was false; and
deleting the MFA blocks with `vault delete` while Terraform still declares them
would have caused a lockout. Three small doc errors remain, and none needs
another review round, so the verdict is fix.

## Checked

- `loopctl gate stamp` from the worktree: pass on gate pre_commit, gate
  cli_tests and rows r1, r2, r3, r4 and r6, ending "stamp green:
  88e7ac632875fbd7f24e838ea5aae7ada7d05a8b2d3cd52c22f6424dbe577b47".
- Rows r1-r4 and r6: read each command. Each one checks its `fails_when` directly
  (front matter keys, review-due notices, check warnings that name docs/how-to,
  shorthand tokens against `git ls-files`, and that the note-sync files do not
  exist).
- r5 (judgment), checked against code:
  - remove/turn-off/roll-out MFA: checked against the `vault_identity_mfa_totp.lab`
    and `vault_identity_mfa_login_enforcement.userpass` blocks in identity.tf,
    the root justfile's mfa_* recipes, the infrastructure justfile (apply only),
    and the `(none)` output in scripts/vault_mfa.sh.
  - reseed-driftwatch: checked against driftwatch.hcl (job, task and volume
    names, mount at /var/lib/driftwatch, DRIFTWATCH_BASELINE_PATH, an interval
    of 86400) and `nomad_dynamic_host_volume.driftwatch_data`.
  - delete-lost-session tokens: checked against consul.hcl.j2 `down_policy =
    "deny"` and the developer policy's grants on the three creds paths.
  - rotate-operator-password: `random_password.operator`,
    `vault_generic_endpoint.operator`, `vault_kv_secret_v2.vault_operator_credentials`
    at default/vault/operator, and that `localstack env` exports both Consul
    variables.
  - revoke-memex-human-tokens: the client line in `local.oidc_provider_client_ids`,
    the memex-human `verification_ttl` of 30d, and that `nomad_job.memex` is
    commented out.
  - test-acme-on-staging: the acme_server variable, `nomad_job.acme`, the
    issue and store tasks, the store task writing default/haproxy/tls, and
    HAProxy's `change_mode = "restart"`.
  - narrow-firewall: `always_run = timestamp()` in the infrastructure root and
    the rules-only trigger in the applications root. There are four entries for
    the .47 host.
  - check-jetstream: `max_file_store: 10GB`.
  - set-up-nats-cli: nats.hcl has no accounts block, and the monitor is on 8222.
  - send-traces: alloy 4319/4320 on loopback, and tempo and phoenix hold 4317.
  - verify-memex-oidc: auth_oidc.json grant_rules, `app_user_group_members`
    (the operator is in admins only), and the hermes job no longer naming memex.
  - expose-metrics: the HCL check blocks are now valid multi-line HCL.
  - revoke-lost-session: the logout.py success message and exit 1.
  - verify-workload-identity: the developer policy covers sys/auth,
    auth/jwt-nomad/role and secret/data/default.
  - Sampled get-the-operator-password, log-in-to-vault,
    sign-in-to-grafana-without-vault, give-a-job-keyless-minio-access and
    check-the-edge-certificate.
- Build history: all five RESIDUE lines from spike docs-reconcile/1 for
  how-to pages are gone. Old G5 and the "follow-up" are removed. F11, D2 and
  "at the time of writing" are rewritten. The remaining dated lines ("Verified
  live on 2026-07-31", "Observed 2026-08-02") are dated measurements, which the
  spike classed as acceptable.
- Invented commands: every `just` and `localstack` call the diff adds matches
  `just --list`, the deployment justfiles (applications `apply refresh
  target`) or `localstack --help`.
- Slop scan on the added lines: 0 em dashes (0 left in docs/how-to), no
  ` -- `, no prose semicolon splices, no tier-1 words.
- Plan step 7: docs/note-sync.toml and docs/.gitignore are deleted and
  docs/notes is absent. No live reference to them remains outside historical
  .okf text.

## Findings

- f1: `just mfa_status` is unreachable from deployments/infrastructure (checked
  with `just --dry-run mfa_status` there). Add "from the repository root", as
  turn-off-vault-login-mfa.md does.
- f2: replace "Docker's" with "podman's" or drop the driver name.
- f3: point the step at `nomad job status acme/periodic-<id>` to get the
  allocation, as check-the-edge-certificate.md does.

## Notes

rotate-the-vault-operator-password.md says "state lives in the Consul
backend". That is a mild spatial-copula phrase, and I am not asking for a
change.
