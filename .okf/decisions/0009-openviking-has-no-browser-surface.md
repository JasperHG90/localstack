---
type: decision
title: "ADR 0009: OpenViking has no browser surface; Web Studio is unmounted and its proxy removed"
description: "oauth2-proxy-openviking and Web Studio are gone because Studio cannot collect a credential under oidc. Studio is unmounted rather than left up without its proxy, and the hostname now serves ov-dash."
generated:
  by: claude-opus/5.5
  at: 2026-09-26
tags: [adr, decision, openviking, web-studio, oauth2-proxy, ov-dash]
status: stable
decision_status: Accepted
decided_on: 2026-09-08
sources:
  - id: openviking
    resource: git:3ec5d1e:docs/openviking.md
    last_modified: 2026-09-12
---

# ADR 0009: OpenViking has no browser surface; Web Studio is unmounted and its proxy removed

- Status: Accepted
- Date: 2026-09-08

> Written retrospectively from docs/openviking.md, dated 2026-09-12.

## Context

`openviking.lab.orangecluster.nl` used to reach the same service through
`oauth2-proxy-openviking` on port 4182, and the only thing on it was upstream's
Web Studio. Studio cannot collect a credential under `oidc`, so the proxy gated
a UI nobody could finish logging into.

## Decision

Both are gone: the job, its Vault OIDC client, its two KV entries, and the
HAProxy backend.

Studio is unmounted with `OPENVIKING_WEB_STUDIO_DIR` pointing at a path that
does not exist. There is no config-file switch for it, and the variable takes
`/` down with it, because the root redirect is registered inside the same block
that mounts the bundle. Leaving it mounted with the proxy gone would have
served the UI to anyone reaching the edge: Studio answers without a token.

Rejected alternatives: keeping the proxy in front of a UI nobody could log
into, and leaving Studio mounted once the proxy was gone.

## Consequences

The name resolved to a 503 for a while, since the HAProxy frontend declares no
`default_backend`. It now reaches ov-dash, the dashboard it was held for:
a Node service on orangepi4a, routed by the `ovdash` backend, deployed by
`nomad_job.ov_dash` from `deployments/applications/services/ov-dash.hcl`. It
sends a person to Vault's own login page, trades the ID token that comes back
for a Vault token on the `jwt-lab` mount, mints their identity token
server-side and never hands the browser one, which is why nothing gates it at
the edge.

`scripts/check_openviking_config.py` asserts the value is `/nonexistent`,
see `docs/reference/openviking.md`.
