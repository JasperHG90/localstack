---
type: verdict
title: 'Verdict: ov-sync-consumer plan-reviewer round 1'
description: 'plan-reviewer verdict for round 1 of ov-sync-consumer: fail.'
tags:
- verdict
- plan
generated:
  by: claude-opus/5.5
  at: '2026-11-15T20:44:40+00:00'
slug: ov-sync-consumer
pass: plan-reviewer
round: 1
body_schema: verdict/1
---

## Summary

Each listed risk is settled by spike evidence that answers it. Spike 7 covers
OpenViking writes and deletes, spikes 4 and 5 cover webhook reach, spike 1
covers the Go gates, and spikes 9 and 11 cover sharing the namespace with the
receiver as owner. The design follows from these. One risk is missing. The
receiver now owns the network namespace, so every exit it makes takes SeaweedFS
down with it, and the receiver depends on NATS on another node. The plan sets
no rule for how the receiver acts when NATS is down. Revise the plan; it does
not need a rethink.

## Checked

- Spikes 4, 5, 9 and 11: read the README outcomes and the spike 11 script. Spike
  11 used busybox and no `service` block. Its three checks were the spike's own
  curl probes, not Consul checks.
- `deployments/infrastructure/services/seaweedfs.hcl`: the `-ip=127.0.0.1` and
  `-ip.bind` binds stay valid inside the shared namespace, because loopback is
  shared and spike 5 delivered to a loopback listener with these exact args. S3
  binds 0.0.0.0 and metrics binds 0.0.0.0:9327, so the receiver's published static
  ports reach them. The Prometheus scrape is the static target
  `192.168.2.29:9327` (`services/prometheus.hcl:116`), and that does not change.
  The seaweedfs task's outbound calls (the STS/JWKS fetch to
  nomad.lab.orangecluster.nl) go through the owner's namespace, which spike 11
  showed can reach off-node addresses by IP.
- nomad-driver-podman 0.6.4 source (spike-ovc4/src/driver.go:1008) and Nomad
  2.0.4 `client/serviceregistration/address.go`: see Notes on the service block.
- `docs/reference/nats.md`: NATS has no auth, so the receiver holds no secret
  beyond the bearer token, as the plan says. Podman on jammy comes from apt
  (3.4.4), which matches the spikes.
- `.loop/plans/ci-openviking-sync.md`: it says this ticket owns the bucket and
  the webhook, and the plan agrees. The two plans split `services.tf` IAM locals
  and `storage.tf` the same way. No conflict.
- `local.seaweedfs_keyless_jobs` grants `s3:*` on the job's whole bucket, which
  is enough for the consumer's reads and the catch-up listing.

## Findings

- p1: when NATS is down, the receiver's failure behavior must be part of the
  plan, because any receiver exit fails and reschedules the whole SeaweedFS
  alloc (spikes 9 and 11).

## Notes

- Not a finding, but it needs a decision during the build. Today the `service`
  and its HTTP check sit in the seaweedfs task with the default `address_mode`.
  The podman driver always returns `AutoAdvertise: true` with the container's
  inspected IP. A container started with `container:<receiver>` reports an empty
  IP, so Nomad resolves the service to address "" with port `To`, and the check
  URL to `http://:8333/healthz`. Move the `service` block to the receiver task,
  which has the IP and whose namespace serves SeaweedFS on 8333, or set
  `address_mode = "host"`. Nothing restarts on this check (no `check_restart`),
  and clients use 192.168.2.29 directly. A wrong check is noise, not an outage.
- Spike 11 tested outbound by IP only. Name resolution from the joined container
  (JWKS by hostname) is untested, but podman gives a `container:` joiner the
  owner's resolv.conf. The first deploy will show it.
- The eval has no rows yet. That is outside this review, but the Outcome
  paragraph is ready to become rows.
