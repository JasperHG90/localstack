---
type: decision
title: "ADR 0008: OpenViking's rerank goes through Bifrost, not straight to embark"
description: OpenViking reranks through Bifrost like every other model call, which meant upgrading Bifrost to 2.0.0 so it accepts bare-string documents. Pointing rerank at embark directly would have worked without the upgrade and was rejected.
generated:
  by: claude-opus/5.5
  at: 2026-09-26
tags: [adr, decision, openviking, bifrost, embark, rerank]
status: stable
decision_status: Accepted
decided_on: 2026-09-05
sources:
  - id: openviking
    resource: git:3ec5d1e:docs/openviking.md
    last_modified: 2026-09-12
---

# ADR 0008: OpenViking's rerank goes through Bifrost, not straight to embark

- Status: Accepted
- Date: 2026-09-05

> Written retrospectively from docs/openviking.md, dated 2026-09-12.

## Context

OpenViking's OpenAI-compatible rerank clients send `documents` as a list of
bare strings. Bifrost accepted only the object form through 1.6.11 and rejected
strings with a flat `400 Invalid request payload` at its own edge, before the
request reached embark.

## Decision

Rerank goes through Bifrost, which required upgrading it.
`U7-upgrade-bifrost-2x` bumped the gateway to 2.0.0, which normalizes both
forms.

Pointing rerank straight at embark would have worked without that upgrade, and
was rejected: it would lose Bifrost's logging, governance and virtual-key
accounting for one call type.

## Consequences

Rerank depends on a Bifrost that accepts bare strings. `scripts/embark_rerank.py`
checks that shape, see `docs/how-to/verify-an-openviking-deployment.md`.
