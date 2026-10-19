---
type: verdict
title: 'Verdict: docs-explanation reviewer round 1'
description: 'reviewer verdict for round 1 of docs-explanation: pass.'
tags:
- verdict
- review
generated:
  by: claude-opus/5.5
  at: '2026-10-19T19:49:28+00:00'
slug: docs-explanation
pass: reviewer
round: 1
body_schema: verdict/1
---

## Summary

The change repairs all 11 explanation pages in place. It adds front matter, rewrites the listed build-history lines as current facts, and brings the hermes-dashboard and leo-consumer additions in line with the code. I found no claim the code contradicts, no build-history line left as it was, and no slop pattern the rules name. Pass.

## Checked

- Stamp, re-run by me from the worktree: `loopctl gate stamp` printed "stamp green: b5e181ff39451d600939364981f717816e331a481d72c54112d3a0d7b8c2b384", with the cli_tests gate and rows r1 to r4 passing.
- Rows r1 to r4 run inline checks that test their fails_when directly: front matter keys, kmctl review due notices, kmctl check warnings, and shorthand paths against git ls-files. None of them is a stub.
- r5, build history: spike:docs-reconcile/1 lists workload-identity.md :71 (As of F9), :217 (M1 owner cell), :240 (M1 landed this) and cluster-roles.md :34 (different ticket). All four are rewritten. The page no longer holds any other ticket code (F1, R5, R9, R13, F10, OV1, OV2, D5, branch 2), which I checked with a grep for `[A-Z][0-9]` codes.
- r5, claims against code:
  - The oidc.tf clients number seven, hermes_dashboard included.
  - hermes-dashboard has id_token_ttl 604800 on its own key. Per the oidc.tf comments, no JWT role accepts its audience, the dashboard caches keys for an hour and -replace is the full lever. This matches vault-login-mfa.md and vault-oidc-tokens.md.
  - var.vault_openviking_workloads holds hermes and leo-consumer, both lab/jasper, which matches the openviking-identity.md rewrite.
  - local.openviking_people is still in deployments/applications/secrets.tf as the seed, so the removed "one line in local.openviking_people" sentence was rightly dropped.
  - hermes.hcl sets `vault { role = "hermes" }`.
  - The audience table's "Defined in" cells point at real definitions: bound_audiences vault.io, memex auth_oidc.json audience, MINIO_IDENTITY_OPENID_CLIENT_ID_NOMAD/_POC2 in minio.hcl.
  - nomad_oidc_config_url is filled in services.tf, and oidc_issuer is in nomad.hcl.j2.
  - The dash upstreams are filled in services.tf.
  - loki, tempo and registry carry aud minio, and memex still templates a static access key.
  - The registry-ui 1+R+T expansion matches registry_client.py (catalog, tags/list, HEAD).
  - The backup KV paths in deployments/infrastructure/secrets.tf hold per-job GCS copies.
  - `localstack breakglass` exists in cli/src/localstack_cli/commands/breakglass.py.
  - app_user_groups holds only the memex tiers, so "first service with its own tier" holds.
  - oidc.tf has no MinIO client, so "MinIO has no human login through Vault yet" holds.
- Removed text: the cluster-roles.md lines and the public-lab-dns.md last section that were dropped repeated content still on those pages (the developer reach paragraph, and the CT-log and RFC1918 bullets under "What this exposes"). Nothing in the repo links an anchor of public-lab-dns.md, and the inbound links name only the page.
- Sources: every `sources` entry is a file the page describes, and r2 shows that each one resolves.
- Slop scan on each changed page: no em dashes, no ` -- `, no prose semicolon splices, and none of the tier-1 or spatial-copula words, except "serves as an OIDC issuer", which is literal there.
- docs/README.md and .okf are untouched, which is right because no title or path changed. docs/explanation/README.md is the kmctl-generated index.

## Findings

None.
