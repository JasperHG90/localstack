---
type: plan
title: 'Plan: hermes-file-toolset'
description: Give Hermes on Telegram and email the file tools, by naming the toolset `file` in platform_toolsets instead of the non-existent `files`.
tags:
- plan
generated:
  by: process:loopctl/2.4.0
  at: '2026-11-26T13:45:00+00:00'
slug: hermes-file-toolset
epic: null
depends_on: []
priority: null
schema_version: '2.0'
---

# hermes-file-toolset

Relayed from: none

## Intent

Both `platform_toolsets` lists (email and telegram) in the `config.yaml`
that `deployments/applications/services/hermes.hcl` renders name `files`.
Upstream hermes-agent names that toolset `file` in `toolsets.py`, in v0.22.2
and v0.23.4 alike. Hermes skips unknown toolset names, and only a warning in
the log shows it, so Telegram and email have run without file tools.
Found while checking the hermes-agent v0.23.4 upgrade (`hermes-update-0-23`).

Rename both entries to `file`. Add a test in `cli/tests/test_hermes_version.py`
that every `platform_toolsets` entry is a name upstream defines, so a typo
fails the gate instead of a log line.

Outcome: after the apply, the gateway log has no "references unknown toolset"
warning, and a Telegram request to read a file on the data volume gets an
answer that used a file tool. `just pre_commit` and
`uv run --directory cli pytest` pass.

## Problems

- P1: Both `platform_toolsets` lists name `files` instead of `file`, so Telegram and email have no file tools.

## Goals

- G1: Give the Telegram and email platforms the toolsets the config means them to have.

## Outcomes

### O1: Telegram and email get the file toolset
- kind: behaviour
- goal: G1
- fixes: P1
- needs: none
- touches: `deployments/applications/services/hermes.hcl`, `cli/tests/test_hermes_version.py`
- checked by: a test that every `platform_toolsets` entry is a known toolset name, no "references unknown toolset" warning in the gateway log, and a Telegram request answered with a file tool
- seen by: operator

## Could invalidate this plan

- none
