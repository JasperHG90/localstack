---
type: decision
title: "ADR 0024: The devcontainer reads the host OpenViking login through a read-only mount"
description: "The devcontainer bind-mounts the host ~/.openviking read-only, so ovsync and ov authenticate with the host login and the token is renewed on the host."
tags: [decision]
generated:
  by: process:kmctl/0.12.1
  at: 2026-10-28T10:20:45Z
status: stable
sources:
  - resource: ".devcontainer/devcontainer.json"
---

# ADR 0024: The devcontainer reads the host OpenViking login through a read-only mount

## Context

The operator wants `ovsync` in the devcontainer without logging in again
there. `ovsync` and `ov` read their URL and token from
`~/.openviking/ovcli.conf`, which `ovx --bind` writes on the host. The
container already bind-mounts the host's `~/.ovx` writable. Spike
devcontainer-ovsync/1 showed neither tool writes under `~/.openviking`, but
`ov` 0.5.0 refuses every command unless `ovcli.settings.conf` is there too.

## Decision

`.devcontainer/devcontainer.json` bind-mounts the host's `~/.openviking`
directory read-only. It mounts the directory, not the file, because
`ovx --bind` replaces `ovcli.conf` by rename and a file bind would keep the
old copy. The token is renewed on the host with `ovx -L --bind localstack`.
Inside the container, `ovx -L --no-bind` still works because `~/.ovx` stays
writable.

Rejected: a writable mount. It would let an agent in the container rewrite
or delete the host's login, and nothing in the container needs to write
there. Also rejected: passing `OV_SYNC_URL` and `OV_SYNC_API_KEY` through
`.devcontainer/.env`. That copies a token with a 30-day life into a second
file that goes stale on its own, and `ov` would still have no config.

## Consequences

The host must have `~/.openviking` with both `ovcli.conf` and
`ovcli.settings.conf` before the container is built, or the bind fails. Plain
`ovx -L` in the container re-binds onto the read-only mount and exits with an
error, so the how-to tells the reader to use `--no-bind` there. The how-to is
`docs/how-to/sync-a-folder-to-openviking-from-the-devcontainer.md`.
