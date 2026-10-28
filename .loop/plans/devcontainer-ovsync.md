---
type: plan
title: 'Plan: devcontainer-ovsync'
description: Install ovsync in the devcontainer image and mount the host's ~/.openviking read-only, so ovsync and ov authenticate inside the container with the credentials the host already has.
slug: devcontainer-ovsync
depends_on: []
tags:
- plan
generated:
  by: process:loopctl/2.2.2.dev1+gd84319696
  at: '2026-10-28T09:17:30+00:00'
---

# devcontainer-ovsync

Relayed from: none

## Intent

The operator wants to run `ovsync` inside this devcontainer without logging
in again there.

**Today.** `.devcontainer/Dockerfile` installs `openviking` (the `ov` CLI) and
`ovx` with `uv tool install`, but not `ovsync`. `.devcontainer/devcontainer.json`
bind-mounts the host's `~/.ovx` (ovx profiles and Vault-minted tokens) writable,
and does not mount `~/.openviking`.

**How ovsync authenticates.** `ov-sync` at `ov-sync-v0.3.0`
(packages/ov-sync/src/ov_sync/config.py in JasperHG90/openviking_extensions)
reads `url` and `api_key` from `$OPENVIKING_CLI_CONFIG_FILE`, falling back to
~/.openviking/ovcli.conf, then lets `OV_SYNC_*` variables override them. On
the host, `ovx -L --bind lab` (or `ovx --bind lab`) writes that file with the
token expanded. So the host's `~/.openviking` already carries everything
ovsync needs.

**Change.**

1. `.devcontainer/Dockerfile`: install ovsync next to `ovx`, pinned to the tag:
   `uv tool install ov-sync --from "git+https://github.com/JasperHG90/openviking_extensions@ov-sync-v0.3.0#subdirectory=packages/ov-sync"`.
2. `.devcontainer/devcontainer.json`: add
   `source=${localEnv:HOME}/.openviking,target=/home/vscode/.openviking,type=bind,readonly`.
   Mount the directory, not the file: `ovx --bind` replaces the file, and a
   file bind would keep showing the old inode. The `~/.ovx` mount stays
   writable so `ovx -L` still works inside the container.
3. Like the `gcloud` and `~/.ovx` mounts, the host folder must exist before the
   container is created (operator's choice, 2026-10-28). It must also hold
   `ovcli.settings.conf`, which `ov language en` writes on the host: ov 0.5.0
   refuses every command without it and reads it only from `~/.openviking`
   (spike:devcontainer-ovsync/1). The step that says so
   goes in the devcontainer docs page that covers the other host mounts, or a
   new how-to if none exists.

Operator's choices, 2026-10-28: mount `~/.openviking` only and read-only, pin
`ov-sync-v0.3.0` (the `ci-openviking-sync` plan pins `v0.2.0`; that plan moves
up on its own), require the host folder rather than create it.

**Outcome.** In a rebuilt container, `ovsync --help` runs, `~/.openviking` is
mounted read-only (`touch ~/.openviking/x` fails with "Read-only file
system"), and `ovsync` reaches the lab OpenViking with the host's credentials,
which `ovsync`'s root check against `viking://user/jasper/resources/` shows.

## Could invalidate this plan

- ov and ovsync write into `~/.openviking`. The plan assumes both only read
   `ovcli.conf` there. If either writes a sibling (`ovcli.conf.<name>`, a
   cache, state) under `~/.openviking`, a read-only mount breaks it, and the
   mount must become writable or point `OPENVIKING_CLI_CONFIG_FILE` at a
   read-only file elsewhere. Spike question: with `~/.openviking` made
   read-only and a stub `ovcli.conf` pointing at an unreachable URL, do
   `ovsync` at `ov-sync-v0.3.0` and the image's `ov` (openviking 0.5.0) fail
   only on the network, with no write error under `~/.openviking`?
   Settled by spike:devcontainer-ovsync/1: strace showed no write, create,
   rename or unlink under a read-only `~/.openviking` from `ov status`,
   `ov ls`, `ovsync status` or `ovsync run`, and each failed only on the
   connection. ovsync keeps its state in .ov-sync.db inside the synced folder. The catch,
   now in step 3: the mounted folder must already hold `ovcli.settings.conf`.
