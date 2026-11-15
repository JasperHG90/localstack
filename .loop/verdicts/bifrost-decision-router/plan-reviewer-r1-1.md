---
type: verdict
title: 'Verdict: bifrost-decision-router plan-reviewer round 1'
description: 'plan-reviewer verdict for round 1 of bifrost-decision-router: fail.'
tags:
- verdict
- plan
generated:
  by: claude-opus/5.5
  at: '2026-11-15T20:54:58+00:00'
slug: bifrost-decision-router
pass: plan-reviewer
round: 1
body_schema: verdict/1
---

## Summary

The router design holds up. Spikes 2 and 4 show config.json loads the
analyzer and the rules in split mode with Postgres, that matching on
`virtual_key_name` scopes the reroute without a key ID, and that the
priority-0 passthrough removes the classifier cost for the other keys.
Spike 1 shows the classifier call skips governance and the catalog. Two
things would still break the outcome. The Jev base_url doubles the request
path (p1). The live classifier latency against the 1500 ms default has never
been measured, and when the classifier times out the router stops routing
without any error (p2). Both are revisions, not a rethink. Two risks do not
call for a split.

## Checked

- Read the plan, the empty eval, and spikes 1 to 4 (README, files, configs).
  Their outcomes answer risks 1 and 2 as the plan states, with the
  mock-upstream limit the plan does not address (p2).
- Upstream at transports/v2.3.1:
  - `core/providers/typesafe/utils.go:12-20` and `typesafe.go:52-58,
    131-143, 181, 241`: base URL plus path, and the pinned catalog only
    applies with the default base URL (p1).
  - `plugins/routing/decisionclassify.go:56-111` and
    `framework/configstore/complexityconfig.go:409, 594-602`: 1500 ms
    default, a timeout or error gives MechanismSkipped, and `timeout` can be
    configured (p2).
  - `plugins/routing/main.go:403-440, 486-560`: a passthrough match with no
    provider, model or fallbacks leaves the request's provider, model and
    fallbacks alone, and the virtual key's load balancing still runs. So
    Hermes, Memex and OpenViking keep their behavior, embeddings and rerank
    included.
  - `plugins/routing/utils.go:23-42`: rules read the virtual key name from
    the governance context, so a Terraform-created key named `router`
    matches the same way the spike's config.json key did.
- Repo: `deployments/applications/services/bifrost.hcl` and `services.tf`.
  The existing keys already carry `key_ids = ["*"]`. Provider names in
  `bifrost_virtual_key` are free-form (embark already works), so a
  `typesafe` entry fits.

## Findings

- p1: the Jev `base_url` includes the path the provider adds itself, so
  every typesafe call misses and the outcome's Jev 200 cannot pass.
- p2: the clef:cloud classifier is untested against ollama.com, and its
  1500 ms default timeout fails silently. A live latency and model-name
  spike should settle it before the build.

## Notes

The other points the briefing raised are not findings:

- The passthrough rule matching requests with no virtual key does not
  matter, because `enforce_auth_on_inference` is true, so such requests are
  refused anyway.
- config.json not being authoritative for deletions affects later removal
  of these rules and the analyzer block, not this change, which only adds.
  It is worth one line in the component page.
- The router key having no consumer is an operator decision the plan
  records.
- The Jev provider being untested live is covered by p1 for the part that
  is certain to fail. The rest (the TYPESAFE_API_KEY value, account access)
  is answered by building.
