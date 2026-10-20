---
type: decision
title: "ADR 0019: Hermes's OpenViking provider is built into the image"
description: "From hermes-agent v0.22 the OpenViking memory provider is a catalog plugin, so the Hermes image copies it in at build time, pinned by commit, over letting Hermes install it from GitHub at first start."
tags: [adr, decision, hermes, openviking, memory, docker]
generated:
  by: claude-opus/5.5
  at: 2026-10-20T00:00:00Z
status: stable
sources:
  - resource: "deployments/applications/services/hermes/Dockerfile"
  - resource: "cli/tests/test_hermes_version.py"
---

# ADR 0019: Hermes's OpenViking provider is built into the image

## Context

hermes-agent v0.22.0 moved the OpenViking memory provider out of the base
image into Volcengine's plugin catalog. With `memory.provider: openviking`,
Hermes installs the plugin from GitHub on its first agent turn and keeps it on
the `hermes_data` volume (`spike:hermes-update/2`). Hermes's memory is
OpenViking, so a start without the plugin starts without memory.

## Decision

The Hermes Dockerfile copies the catalog plugin's `examples/hermes-plugin`
directory, pinned at OpenViking commit `9f150ece` (plugin 2.1.1), into the
bundled provider directory `/opt/hermes/plugins/memory/openviking`, and checks
its version during the build. The image carries the provider, and no start
depends on GitHub (`spike:hermes-update/3`).

Rejected: the lazy install at first start. It needs GitHub reachable from the
node on the first turn after a fresh volume, backs off for an hour or more if
that fails, and installs whatever the catalog serves at that moment rather
than a pinned version. Also rejected: `pip install` of the plugin, which does
not build (flat layout, and it declares no memory-provider entry point).

## Consequences

- Upgrading the plugin means changing `OPENVIKING_PLUGIN_SHA` and the checked
  version in the Dockerfile, then rebuilding with `just rebuild_hermes`.
- `cli/tests/test_hermes_version.py` pins the base, the commit and the copy
  destination.
- Decided as the operator's default while they were away (2026-10-20), and
  confirmed when they said to go ahead with the Hermes upgrade.

## Correction, 2026-10-20

The image now also carries faster-whisper 1.2.1, for local transcription of
Telegram voice notes, for the same reason the plugin is built in: no voice note
depends on an install at run time. The base image ships no speech engine and
the gateway never installs one (spike:ov-save-skill/1, /3). The install is
constrained by the base's own `uv.lock` export, because an unpinned install
pulls PyAV 19.0.1 and breaks every transcription (spike:ov-save-skill/8). The
`base` model downloads on first use to the data volume. `config.yaml` pins
`stt.provider: local` and `stt.local.model: base`, and
`cli/tests/test_hermes_version.py` pins the line and the keys.
