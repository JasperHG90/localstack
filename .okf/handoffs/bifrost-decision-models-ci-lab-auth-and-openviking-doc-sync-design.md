---
type: handoff
title: "Bifrost decision models, CI lab-auth and OpenViking doc sync design"
description: "CI lab-auth and OpenViking doc sync are live and proven on main; bifrost-decision-router is next, at plan review round 2."
tags: [handoff]
generated:
  by: process:kmctl/0.12.1
  at: 2026-11-16T07:51:26Z
stale_after: 2026-11-30T07:51:26Z
handoff_key: "39954680-d360-4c77-9baf-bede6c6eafa0"
---

# Bifrost decision models, CI lab-auth and OpenViking doc sync design

## Summary

## Where it stands

Done and live on `main` (pushed 2026-11-16): ov-sync-consumer,
ci-tailscale-access, ci-openviking-sync, and a follow-up,
`lab-auth-check-errexit` (merge `fc62a8eb`). The operator published
`ghcr.io/jasperhg90/ov-sync-consumer:v0.1.0` and applied both roots.
SeaweedFS runs version 4 with the receiver sidecar, no restarts, and S3
answers. The consumer runs on radxa with no restarts.

Proven by runs:

- `lab-auth-check` on main, run 43826429945: token, the vault, openviking and
  s3 edges, and all five closed ports (firebat over the tailnet included)
  PASS. A dispatch from a throwaway branch (run 43818378784, branch since
  deleted) was refused at Vault: `claim "ref" does not match`.
- `openviking-sync`, run 43818142026 (rerun after the apply): 189 uploaded,
  0 failed. The operator confirmed the pages reached OpenViking.

The first live lab-auth-check run found a bug: GitHub runs `shell: bash` as
`bash -e -o pipefail`, so the closed-port probe's expected exit 124 killed
the step. `lab-auth-check-errexit` sets `set +e -u` in that step, and
`test_check_step_survives_errexit` runs the step under the same flags.

Not yet shown: a second `openviking-sync` run that uploads only what changed
(the next push touching `docs/` or `.okf/` does it). The live judgment eval
rows (ov-sync-consumer r12/r13, ci-tailscale-access r6, ci-openviking-sync r8,
lab-auth-check-errexit r3) are shown by the runs above; loopctl has no verb to
record them after landing. The agent's Nomad token cannot read alloc logs.

`bifrost-decision-router` is in planning: every risk is settled by spikes
1 to 7, lint is clean, and plan review round 2 is next. Tiers: classifier
`ollama/clef:27b`, simple `ollama/gpt-oss:120b`, medium
`ollama/deepseek-v4.1-flash`, hard `ollama/mistral-large-4`, with no cloud
suffix on any name. The Jev secret is `secret/default/bifrost/typesafe`,
field `TYPESAFE_API_KEY`, written by the operator.

The operator pasted the Bifrost virtual key `jasper-laptop-cc` into the chat
during spike 7. It should be rotated.

## Next steps

1. Rotate the Bifrost key `jasper-laptop-cc`.
2. `loopctl review start bifrost-decision-router` (plan review round 2), then
   sign its eval and build it.
3. Watch the next `openviking-sync` run upload only the changed files.
4. Pick up the deferred stubs when wanted: `ov-sync-consumer-reviewer-f3` (two
   events for one key on two workers), `ci-tailscale-access-reviewer-f3` (OIDC
   response without a value), `ov-carry-over-cleanup`.
5. Pushing, publishing images and applying Terraform are blocked for the agent
   by Claude Code's auto-mode classifier. The operator runs them.

## Key references
