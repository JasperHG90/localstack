---
type: verdict
title: 'Verdict: docs-reference reviewer round 1'
description: 'reviewer verdict for round 1 of docs-reference: fix.'
tags:
- verdict
- review
generated:
  by: claude-opus/5.5
  at: '2026-10-19T19:38:27+00:00'
slug: docs-reference
pass: reviewer
round: 1
body_schema: verdict/1
---

## Summary

The change does what the plan asks. All 19 reference pages carry the three
front matter keys, every build-history line spike:docs-reconcile/1 listed for
docs/reference is rewritten as a current fact, and the claims I checked
against the code hold, including the new ones (operators assignment, TOTP MFA,
Alloy OTLP relay, OpenViking firewall callers, the gemini summary model, the
reflection pass, the unhooked oauth2-proxy guard). Three non-blocking fixes
remain: one missing source, one row that reads as more complete than it is,
and long lines.

## Checked

- `loopctl gate stamp` from the worktree: "stamp green:
  bb603ee847b48a3b00957b929b29bee14ba7101884119a9248d8238a022bf706", with
  gate cli_tests and eval rows r1 to r4 all `pass`.
- Rows r1 to r4: read each command. r1 parses the front matter and fails on a
  missing key, empty sources or an extra key. r2 fails on any notice. r3 fails
  on a nonzero exit or a warning naming docs/reference/. r4 fails on a
  backticked token that is a suffix of a tracked path. Each asserts its
  fails_when.
- r5, judgment. Read the diff of all 19 pages and checked claims against code
  on cli-login, cluster-roles, dash, vault-human-auth, openviking, monitoring,
  registry-ui, bootstrap-secrets, cli-breakglass, edge-routes, nats,
  python-observability, vault-login-mfa, gcs-backups and tls-certificates:
  - oidc.tf: clients are smoke, nomad, memex, oauth2-proxy, grafana, ov-dash
    and hermes-dashboard. `operators` names developer and admin and is used
    by oauth2-proxy, grafana and hermes-dashboard. No client uses allow_all,
    and oauth2-proxy carries both the dash and registry-ui redirect URIs.
  - identity.tf: TOTP method and userpass enforcement, OpenViking consumers,
    the openviking-user group, the jwt-lab mount. secrets.tf writes
    default/vault/<username> for each consumer.
  - login.py and auth/vault.py: the `TOTP passcode for <addr>:` prompt,
    "Using the first" when there are several methods, the three-cause error,
    save before revoke, the ~/.vault-token write. .devcontainer/devcontainer.json
    passes --env-file.
  - alloy.hcl: OTLP on 127.0.0.1:4319 and 4320, exporting to
    192.168.2.47:4317. embark's otlp_endpoint is 127.0.0.1:4319.
    infrastructure/services.tf admits .47 and .30 on 9090.
    configure_network.yml still opens 4646, 8200 and 8500 to 192.168.0.0/16.
  - openviking.hcl and ov.conf.json: `-m ov_ext`, gemini/gemini-3.5-flash-lite,
    OV_REFLECT_MODEL ollama/deepseek-v4.1-flash, interval 3600, lab/jasper,
    liveness grace 60m. The virtual key carries embark, gemini and ollama.
    Port 1933 admits .50, .30, .47 and .29.
  - registry-ui: .pre-commit-config.yaml has no hook for
    check_oauth2_proxy_guard.py or for the registry-ui backend. The guard runs
    with no arguments and exits 0.
  - bootstrap playbooks: init.json stat with an env fallback, and the podman
    auth files skipped when the user is empty. haproxy.hcl serves /metrics on
    8404. The breakglass runbook opens with a connectivity check, and the
    command always exits 0. nats.hcl has the exporter on 7777, which only .47
    may reach. prometheus.hcl reads the `metrics_path` meta and has no
    `metrics_port`.
  - dash tiles.json: six groups, with openviking and ov-dash as two tiles and
    registry covering registry-ui.
- CLI claims: ran `uv run --directory cli localstack <cmd> --help` for login,
  breakglass, deps, vault grants, env, token, whoami, config, logout, status,
  service, secret and monitor. --insecure, --no-probe and --with-shims exist.
  The justfile has mfa_status, mfa_enroll and mfa_reset.
- Sources: every entry I sampled is code the page describes. f1 is the one
  gap I found.
- Slop: no em dashes and no ` -- ` left in docs/reference. Ticket codes are
  gone (the one regex hit is a numbered list). Semicolon splices became two
  sentences. The long lines are f3.

## Findings

- f1: cli-login.md describes the ~/.vault-token write, and the file that does
  it, auth/vault_token_file.py, is not in sources. Add it.
- f2: the secrets.tf row in vault-human-auth.md leaves out the OIDC client
  secret writes in the same file. Name them, or scope the row to human
  credentials.
- f3: long lines from the repo-root path rewrites. Rewrap them to 80.

## Notes

A few "now" and "no longer" phrasings remain outside the spike's list
(openviking.md:41-45 "now also runs", edge-routes.md:40 "no longer gates it").
They describe how the service differs from stock or from HAProxy, not ticket
history, so I left them out of the findings. The oauth2-proxy guard and the
registry-ui backend suite have no pre-commit hook. The page now says so
correctly, and the missing hook may be worth a ticket under plan step 7.
