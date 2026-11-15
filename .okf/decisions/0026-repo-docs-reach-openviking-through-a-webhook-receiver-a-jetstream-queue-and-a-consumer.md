---
type: decision
title: "ADR 0026: Repo docs reach OpenViking through a webhook receiver, a JetStream queue and a consumer"
description: "Filer events on the ov-sync bucket go from a loopback receiver inside the seaweedfs job, through a JetStream stream, to a consumer on radxa that writes and deletes in OpenViking."
tags: [decision]
generated:
  by: process:kmctl/0.12.1
  at: 2026-11-15T21:13:51Z
status: stable
sources:
  - resource: "applications/ov-sync-consumer/main.go"
  - resource: "deployments/infrastructure/services/seaweedfs.hcl"
  - resource: "deployments/applications/services/ov-sync-consumer.hcl"
---

# ADR 0026: Repo docs reach OpenViking through a webhook receiver, a JetStream queue and a consumer

## Context

CI uploads each repo's `docs/` and `.okf/` to the SeaweedFS bucket `ov-sync`,
under `<owner>/<repo>/`. Those files have to reach OpenViking at
`viking://user/jasper/resources/projects/<repo>/`, and a removed file has to
leave it. Each OpenViking write regenerates folder summaries with one VLM
call, so the writes need a rate limit, and OpenViking can be down for
minutes, so they need retries that outlast it.

SeaweedFS can announce filer changes itself. Two of its notifiers were tried
under this job's exact arguments:

- The filer webhook works, but only toward a loopback listener in SeaweedFS's
  own network namespace. `-ip=127.0.0.1` pins the webhook client's source
  address, so a POST to another container failed with `connect: invalid
  argument` and nothing was delivered (spike:ov-sync-consumer/4). A listener
  on loopback in the same namespace got every `ov-sync` event as JSON with the
  bearer header, and nothing from other buckets (spike:ov-sync-consumer/5).
- `gocdk_pub_sub` into NATS works too, but it has no path filter, so every
  filer write on the cluster lands in the stream. Each body is a gob envelope
  around a protobuf, it needs the `_full` image, and it publishes core NATS,
  so the filer never learns whether JetStream stored an event
  (spike:ov-sync-consumer/8).

## Decision

One Go binary, `applications/ov-sync-consumer/`, runs as two jobs.

- `receiver` is a prestart sidecar in the seaweedfs job. It listens on
  `127.0.0.1:20500`, checks the bearer token, and publishes each event to the
  JetStream stream `OV_SYNC` with a `Msg-Id` hashed from the event, so a
  redelivered webhook dedupes. The receiver owns the group's network
  namespace and its two static ports, and SeaweedFS joins it with
  `network_mode = "task:receiver"`.
- `consumer` runs on radxa and reads the stream with a fixed worker pool
  behind a rate limit. It treats each event as "look at this file now": it
  reads the object's current state and writes or deletes the file in
  OpenViking to match, then acks. A failed event is retried with backoff and
  moves to a dead-letter subject after its last try. A catch-up pass every
  15 minutes repairs what lost events left behind.

Three alternatives were rejected:

- **The `gocdk_pub_sub` notifier straight into NATS.** It would remove the
  receiver, but it floods the stream with every filer write, sends gob, needs
  a different image, and cannot tell when JetStream refused an event
  (spike:ov-sync-consumer/8).
- **A webhook listener on radxa, or anywhere outside SeaweedFS's
  namespace.** The webhook cannot reach it under `-ip=127.0.0.1`
  (spike:ov-sync-consumer/4). Changing `-ip` would move the master, volume
  and filer off loopback, and their unauthenticated ports would land in the
  LAN-wide 20000:32000 range.
- **The receiver joining SeaweedFS's namespace.** The sharing works, but a
  restart of SeaweedFS alone then failed the whole alloc, because the podman
  driver cannot remove a container another still depends on
  (spike:ov-sync-consumer/9). With the owner reversed, SeaweedFS restarted
  alone and the alloc kept running (spike:ov-sync-consumer/11).

## Consequences

- A receiver restart fails the seaweedfs alloc and Nomad reschedules both
  tasks, so S3 goes down with it. The receiver therefore never exits on a
  fault outside it: it starts with NATS unreachable, reconnects forever,
  answers non-2xx while it cannot publish, runs under `GOMEMLIMIT` inside a
  larger memory limit, and its token template is `change_mode = "noop"`. It
  reads the token file on every request, so a rotated token still takes
  effect.
- An in-place SeaweedFS restart costs one failed start first, so the group's
  restart block allows three attempts instead of the default two.
- The seaweedfs service and its `/healthz` check moved to the receiver task,
  which holds the address. The check still probes SeaweedFS through the
  shared namespace.
- The receiver never creates the stream. Until the consumer has run once, the
  webhook gets non-2xx and the catch-up pass covers the gap.
- One image runs in both Terraform roots, so its tag is a line in each
  root's `services.tf`, and the justfile refuses to build when they differ.
- The catch-up pass compares which files exist, not their content. A lost
  update to a file both sides hold waits for the next event on that file.
