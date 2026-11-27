---
type: verdict
title: 'Verdict: bifrost-update-2-6 plan-reviewer round 3'
description: 'plan-reviewer verdict for round 3 of bifrost-update-2-6: fail.'
tags:
- verdict
- plan
generated:
  by: claude-opus/5.5
  at: '2026-11-27T12:29:23+00:00'
slug: bifrost-update-2-6
pass: plan-reviewer
round: 3
body_schema: verdict/1
---

## Summary

The three risks are re-settled for 2.7.0 by spikes 4, 5 and 6, and their
evidence holds. The approach works. But the plan's claim that 2.6.0 to 2.7.0
adds only two reversible migrations is false by the 2.7.0 release notes:
there are eight, two of them one-way. That makes the record O2 and eval row
r2 ask for wrong, and it removes the reason the plan gives for skipping a
dump of the live 2.6.0 store. Fail, to revise; nothing here needs a rethink.

## Checked

- Spike 4: exit 0. On 2.7.0 and 2.6.0, bare-string and object rerank through
  a virtual key returned 200, forwarded bodies to `/v1/rerank` were identical
  `{"text": ...}` documents accepted by embark v0.2.4's models, and embeddings
  reported `routing_info.provider = embark`. Settles risk 3. Limits (sqlite,
  fresh key) are covered by spike 5 for the key path.
- Spike 5: exit 0. Provider 0.1.1 made the four `services.tf` keys on 2.3.1
  with Postgres 16; the store then ran 2.6.0 then 2.7.0. Same id/value hash
  on all three, `provider_configs` alphabetical, plan exit 0 on each, 200 for
  hermes/memex/openviking, 403 `provider_blocked` for router, 401
  `access_not_found` for a bogus key (matches the smoke script's expectation
  in r1), in-place update applied and planned clean. Settles risk 1 and the
  2.3.1, 2.6.0, 2.7.0 path matches what the live store went through.
- Spike 6: exit 0. 2.7.0 and 2.6.0 got Gemini 400, typesafe 401 and ollama
  502 `upstream_credentials_exhausted` after TLS, and the untrusted-root
  control surfaced `x509: certificate signed by unknown authority` on both.
  Settles risk 2.
- `gh release view transports/v2.7.0 -R maximhq/bifrost`: the Database
  Migrations section lists eight migrations, two non-reversible. This is
  where p4 and p5 come from.
- Problems, Goals, Outcomes against the prose: O1 behaviour needs O3 (pin and
  pin test must move together), O2 and O3 are support and cannot ship value
  alone, touches match the files the prose names. O1 no longer needs O2,
  which is right now that O2 is a page note rather than a pre-apply dump.
  The only mismatch is the migration fact behind P3/O2, raised as p4.
- Code: `deployments/applications/services.tf` line 902 and
  `cli/tests/test_bifrost_version.py` on main still say 2.3.1 (the 2.6.0
  apply is on the ticket branch), consistent with the plan's touches.

## Findings

- p1, p2, p3: resolved, as in the front matter.
- p4: the plan and r2 state "two reversible migrations" for 2.6.0 to 2.7.0;
  upstream lists eight, two one-way. The page would record a false rollback
  story, and P3/O2 should also say there is no way back to 2.6.0.
- p5: the plan's rationale for no dump rested on 2.7.0 being reversible. It
  is not, so a dump now is a real restore point to the live 2.6.0. The
  operator should confirm the waiver with that fact, or a dump is taken.

## Notes

Spike 6 reads go1.27.4 from the 2.6.0 image, where spike 3 recorded go1.27.3,
which hints the upstream tag was rebuilt. The plan pins a tag, not a digest.
Not a finding for this ticket; the TLS evidence covers the image as pulled
today.
