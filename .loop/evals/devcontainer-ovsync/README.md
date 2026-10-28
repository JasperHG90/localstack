---
type: eval
title: 'Eval: devcontainer-ovsync'
description: 'Definition of done for devcontainer-ovsync: 5 row(s).'
tags:
- eval
generated:
  by: process:loopctl/2.2.2.dev1+gd84319696
  at: '2026-10-28T10:18:36+00:00'
slug: devcontainer-ovsync
signoff:
  signer: delegated:jasperginn@gmail.com/agent
  hash: 13c7c172d1446b886edd34a86bf4b1a1d5f299b13642f98a62fb7096594f0b4d
  at: '2026-10-28T10:18:36+00:00'
verified: null
---

Rows: rows.json; the fields each row takes: loopctl schema eval-rows.

- r1: The devcontainer image installs ovsync from openviking_extensions pinned to the ov-sync-v0.3.0 tag.
  Fails when: the Dockerfile has no uv tool install of ov-sync, or installs it from a branch, another tag or no ref
- r2: devcontainer.json bind-mounts the host's ~/.openviking directory read-only at /home/vscode/.openviking.
  Fails when: no mount has source ${localEnv:HOME}/.openviking, target /home/vscode/.openviking, type bind and readonly, or the mount names the ovcli.conf file instead of the directory
- r3: The ~/.ovx bind mount stays writable, so ovx -L can store a token from inside the container.
  Fails when: the ~/.ovx mount is gone or carries readonly
- r4: A how-to in docs/how-to tells the reader to create ~/.openviking on the host with ovx --bind localstack and ov language en before building the container, to refresh the token on the host, and to log in inside the container only with ovx -L --no-bind; it passes the how-to skeleton test.
  Fails when: no docs/how-to page names all of ov language en, --bind localstack and ovx -L --no-bind, or uv run --directory cli pytest tests/test_how_to_skeleton.py fails
- r5 (judgment): After a rebuild on the operator's host, ovsync --help runs, touch ~/.openviking/x fails with a read-only error, and ovsync reaches the lab OpenViking with the host's credentials.
  Fails when: any of the three fails in the rebuilt container; judged after the operator rebuilds, since the build cannot rebuild its own container
