---
type: verdict
title: 'Verdict: devcontainer-ovsync plan-reviewer round 1'
description: 'plan-reviewer verdict for round 1 of devcontainer-ovsync: fail.'
tags:
- verdict
- plan
generated:
  by: claude-opus/5.5
  at: '2026-10-28T09:23:52+00:00'
slug: devcontainer-ovsync
pass: plan-reviewer
round: 1
body_schema: verdict/1
---

## Summary

The plan holds apart from one false premise (p1): a read-only ~/.openviking
breaks in-container `ovx -L` once a binding exists, so token refresh and
binding must happen on the host. Revise, do not split.

## Checked

- Risk 1, writes under a read-only ~/.openviking: settled by
  spike:devcontainer-ovsync/1. strace found no write, create, rename or
  unlink there from `ov status`, `ov ls`, `ovsync status` or `ovsync run`,
  and each failed only on the connection. The spike also found that
  ovcli.settings.conf is needed, and step 3 now requires it. Its limit
  stands: there was no server, so code that runs only after a successful
  connection was not exercised. The outcome check (ovsync's root check
  against the lab) covers that.
- Dockerfile installs openviking and ovx but not ovsync. devcontainer.json
  bind-mounts ~/.ovx writable and does not mount ~/.openviking. Both match
  the plan.
- ovx `write_private` replaces the file with mkstemp and rename, so
  mounting the directory rather than the file is correct.
- The bound URL comes from the profile's $OV_URL
  (openviking-api.lab.orangecluster.nl in the docs), not localhost, so the
  container can reach it. The current bound token lasts about 14 days.

## Findings

- p1 (premise, blocking): in-container `ovx -L` auto re-binds to the
  read-only ~/.openviking/ovcli.conf and exits with an error. A token
  refreshed in the container never reaches ovsync. The plan should state
  that in-container login uses `--no-bind` and that bind and refresh happen
  on the host, and the docs step should say so.
