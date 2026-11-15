---
type: verdict
title: 'Verdict: okf-design-spikes plan-reviewer round 2'
description: 'plan-reviewer verdict for round 2 of okf-design-spikes: pass.'
tags:
- verdict
- plan
generated:
  by: claude-opus/5.5
  at: '2026-11-15T20:01:15+00:00'
slug: okf-design-spikes
pass: plan-reviewer
round: 2
body_schema: verdict/1
---

## Summary

Both round 1 findings are fixed and I found no new risk that could break the
plan. Pass.

## Checked

- spike:ov-sync-consumer/4 (production args, listener in another container:
  0 delivered, `dial tcp 127.0.0.1:0->...: connect: invalid argument`) and /5
  (variant A, same-namespace loopback listener: create, folder create, update,
  delete delivered with the bearer header). The plan's three variants and
  expected results match these.
- `deployments/infrastructure/services/seaweedfs.hcl:96-97` still carries
  `-ip=127.0.0.1` and `-ip.bind=127.0.0.1`.
- The handoff's NATS and webhook spike records match the plan's settings and
  expected outcomes (about 10 messages, nothing for `loki`).
- `.okf/prototypes/` does not exist yet, so the first `kmctl new prototype`
  creating the section is consistent with the plan.

## Findings

- p1: resolved. Three webhook variants, production args included, match spikes 4 and 5.
- p2: resolved. decide.sh has a case for each of the 400, 401 and 403 outcomes.

## Notes

- Whether Bifrost checks the payload shape before the virtual key decides if
  `decide.sh bare-strings` with no key returns 400 or 401. The building step
  shows this at once, and the script appends raw responses either way, so the
  plan holds. If it returns 401, the bare-strings case needs the key.
