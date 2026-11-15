---
type: verdict
title: 'Verdict: ci-openviking-sync plan-reviewer round 1'
description: 'plan-reviewer verdict for round 1 of ci-openviking-sync: pass.'
tags:
- verdict
- plan
generated:
  by: claude-opus/5.5
  at: '2026-11-15T20:19:04+00:00'
slug: ci-openviking-sync
pass: plan-reviewer
round: 1
body_schema: verdict/1
---

## Summary

No open risk could break this plan. Spike ci-openviking-sync/1 answers the plan's one listed risk directly. The repo claims the plan rests on hold. The two dependencies are already declared in `depends_on`. One of them, ci-tailscale-access, is blocked on its federated subject, so this plan's live Outcome cannot run until that ticket lands. That is a scheduling fact, not a flaw in this plan.

## Checked

- Spike ci-openviking-sync/1 (README, stdout, run.json; exit 0, 17/17 required checks). On SeaweedFS 4.48 and Vault 2.0.3, STS accepted Vault's identity issuer beside a `nomad` provider. It refused an `aud: openviking` token. It bound `ci-a-x` to the `StringEquals oidc:ci_repository` literal, with a `b/y` control proving the refusal came from the condition. Prefix scope held: put, get and delete worked under `a/x/` (including `.okf/`) and were AccessDenied under `b/y/`, `a/xx/`, `a/` and the bucket root. ListObjectsV2 was denied, and a missing manifest returned NoSuchKey, not AccessDenied, so step 3's "missing is empty" works without List. This is exactly the plan's spike question. The remaining gap (http issuer on Docker, not https; userpass entity, not a jwt-github login) is named in the plan and gets exercised by the first production run.
- `deployments/infrastructure/services.tf` `local.seaweedfs_iam`: providers is a list with one `nomad` OIDC entry, and roles use `StringEquals` with the comma note, so adding a second provider and per-caller roles fits the existing shape.
- `deployments/infrastructure/oidc.tf`: `vault_identity_oidc.lab` sets issuer `https://${var.vault_issuer_host}` (default `vault.lab.orangecluster.nl`), so tokens carry `iss = https://vault.lab.orangecluster.nl/v1/identity/oidc`, which matches the provider the plan configures. `vault_identity_oidc_key.identity_tokens` sets `allowed_client_ids` inline, so adding `seaweedfs` there is the edit the plan names. `vault_identity_oidc_role.openviking_workload` is the per-workload literal-claim pattern the plan copies.
- Reachability: `haproxy.hcl` routes host `s3.lab.orangecluster.nl` to `192.168.2.29:8333` with no path restriction, so STS (`/?Action=AssumeRoleWithWebIdentity`) and S3 both work through the one `tag:ci` grant (`192.168.2.30:443`). Existing keyless jobs call `:8333` directly, but nothing in the edge blocks the CI path.
- ov-sync-consumer plan: it uses the same `<owner>/<repo>/{docs,.okf}` layout and says the consumer ignores `<owner>/<repo>/_state/manifest.json`, so the manifest does not leak into OpenViking.
- ci-tailscale-access: `var.vault_ci_callers` and the `jwt-github` mount come from that ticket and do not exist yet. That matches `depends_on`. Its roles bind `workflow_ref`, and this plan adds a separate caller entry for the sync workflow, which is consistent with that binding.

## Findings

None.

## Notes

- Sequencing: spike:ci-tailscale-access/3 shows the Tailscale join failing on the federated-subject format (GitHub immutable-ID `sub`). Until that ticket lands, nothing in this plan's Outcome can be shown live. Build order should stay ci-tailscale-access, then ov-sync-consumer (bucket and webhook), then this ticket.
- This plan and ov-sync-consumer both change the seaweedfs job (this one through `iam_members`, that one by adding the receiver to the group). That means merge order and a SeaweedFS restart on each apply. It is not a design conflict.
- An edge case for the build, not a plan risk: if a run uploads a new file and then fails, the manifest is not written. If that file is deleted before the next successful run, the old manifest never listed it, so it stays orphaned in the bucket. Writing the manifest as the union of the old entries and the successful uploads on failure would close this. It is cheap to handle in `sync.py` and its test.
- GitHub concurrency without cancel-in-progress keeps only the newest pending run. Since each run syncs HEAD against the manifest, dropping an intermediate pending run loses nothing.
