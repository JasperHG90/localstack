---
type: verdict
title: 'Verdict: seaweedfs-service plan-reviewer round 2'
description: 'plan-reviewer verdict for round 2 of seaweedfs-service: pass.'
tags:
- verdict
- plan
generated:
  by: claude-opus/5.5
  at: '2026-10-19T20:52:14+00:00'
slug: seaweedfs-service
pass: plan-reviewer
round: 2
body_schema: verdict/1
---

## Summary

Pass. Both round 1 findings are fixed. The plan now asks for volume limits
sized to the store, and only S3 and metrics leave the host. Spike 3 backs
both: with the flag set and `master.toml` `copy_1 = 2`, six buckets each
took a write and 300 MiB fit, and master, volume and filer listened on
loopback only. I found no new risk that could break the plan.

## Checked

- Spike 3 (README, stdout, slots.sh, run.json, exit 0). Under defaults
  only 4 of 6 buckets wrote (7 volumes grown per collection). With the
  candidate set all 6 wrote and read back, with 2 slots per bucket. The
  listeners show 127.0.0.1 for 9333/19333, 8080/18080 and 8888/18888, and
  `:::` only for 8333, 18333 and 9327. A second container reached only those
  three.
- Unmapped ports under podman. In bridge mode (the podman driver default,
  and what minio.hcl uses with static ports), the driver publishes only the
  ports listed in `config.ports`. An unmapped port such as 18333 sits on the
  podman bridge, which the LAN cannot reach. If the build picks
  `network_mode = "host"` instead (embark, loki, bifrost do), loopback binds
  stay on host loopback. 18333 then binds the host, and ufw's default deny
  closes it, because 18333 is outside the worker base rule's 20000:32000
  and outside every other base port in
  bootstrap/playbooks/configure_network.yml. Both modes hold the plan's
  claim, so the build can pick either.
- master.toml delivery. The podman plugin has `volumes { enabled = true }`
  (bootstrap/roles/nomad_client/templates/nomad.hcl.j2). Jobs already
  bind-mount a rendered template onto an absolute path, for example
  `local/config.json:/app/data/config.json` in
  deployments/applications/services/bifrost.hcl. So a template rendered to
  `local/master.toml` and mounted at `/etc/seaweedfs/master.toml` follows
  existing practice. SeaweedFS's `WEED_`-prefixed env vars are a fallback.
- Port collisions. Nothing in deployments/ or bootstrap/ uses 8333, 9327 or
  18333.
- `-volume.max=0` sizes slots from free disk at 1 GB per volume. The spike
  measured this on a 27 GB host. orangepi4a holds MinIO's 1 to 3.5 TiB
  host volume (services.tf), so the slot count there is larger, not
  smaller.

## Findings

- p1 (resolved): the plan requires volume limits sized to the store, and
  spike 3 shows a flag set and `copy_1 = 2` that let six buckets write.
- p2 (resolved): the plan now keeps every port except S3 and metrics off
  Nomad ports and off non-loopback binds, and leaves the S3 gRPC port
  closed. The firewall rule is no longer the guard.

## Notes

The spike ran on docker, not podman. The bind and publish behavior checked
above does not depend on the runtime. The node's free memory is still left
to the build, which the plan states (about 580 MB by the round 1 count,
against a 220 MB peak). Each volume adds index memory, so with 1 GB volumes
the build should watch RSS as data grows. That limits capacity later and
does not break this ticket.
