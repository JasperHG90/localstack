---
type: plan
title: 'Plan: ov-sync-consumer'
description: A Go receiver beside SeaweedFS and a consumer on radxa that turn filer webhook events on the ov-sync bucket into rate-limited, retried OpenViking writes and deletes through NATS JetStream, plus their Nomad, Vault and SeaweedFS wiring.
tags:
- plan
generated:
  by: process:loopctl/2.2.2.dev1+gd84319696
  at: '2026-11-15T19:49:52+00:00'
slug: ov-sync-consumer
epic: ci-lab-access
depends_on: []
priority: null
---

# ov-sync-consumer

Relayed from: none

## Intent

Docs land in the SeaweedFS bucket `ov-sync`, laid out as
<owner>/<repo>/{docs,.okf}/... plus <owner>/<repo>/_state/manifest.json,
which CI writes and the consumer ignores. This ticket builds everything from
the bucket to OpenViking. CI uploads are `ci-openviking-sync`, which will
depend on this ticket. The design is section 3b of the handoff
bifrost-decision-models-ci-lab-auth-and-openviking-doc-sync-design, not yet
committed.

**The Go app** is a module in `new:applications/ov-sync-consumer/go.mod`,
with its entry point in `new:applications/ov-sync-consumer/main.go`. It
lives under the top-level `applications/`, beside `applications/migrations/`,
and not inside the Terraform root, so it can later move to its own repo the
way `JasperHG90/leo-webhook-exporter` did. One binary in one image has two
subcommands:

- `receiver` runs next to SeaweedFS, because the filer webhook only reaches
  a loopback listener in the SeaweedFS task's network namespace (risk 2). It
  listens on 127.0.0.1, checks the bearer token, and publishes each event
  into a JetStream stream on NATS at `192.168.2.50:4222`
  (`docs/reference/nats.md`) with a `Msg-Id` for dedupe. It holds no
  OpenViking or S3 credential.
- `consumer` runs on radxa and reads the stream. It treats each event as
  "look at this file now", because the webhook delivers out of order: it
  reads the object's current state from the bucket, then writes or deletes
  the file in OpenViking. Its config maps each `<owner>/<repo>/` prefix to
  `viking://user/jasper/resources/projects/<repo>/`. It runs a fixed worker
  pool behind a rate limit, acks only after OpenViking accepts, retries with
  backoff, and moves a message to a dead-letter subject after N tries. A
  periodic catch-up pass compares the bucket with OpenViking and repairs lost
  events. Per spike:ov-sync-consumer/7 it writes one file at a time with
  `content/write` and `wait: true`, never `content/batch-write`. It deletes
  an emptied folder with `recursive=true` only after `ls` with hidden files
  shows nothing but `.abstract.md` and `.overview.md`, and judges removal by
  `ls`, not `fs/stat`.

The consumer has one OpenViking identity, `lab`/`jasper`, as a Vault identity
token minted the way hermes and leo-consumer mint theirs. OpenViking indexes
in its default mode, so each write regenerates folder summaries with one VLM
call. The rate limit is what bounds that cost. Bucket access is keyless
through minio-go web identity, as tempo does
(`docs/how-to/give-a-job-keyless-seaweedfs-access.md`).

**Build and gates.** `new:applications/ov-sync-consumer/Dockerfile` builds a
static arm64 binary. `new:applications/ov-sync-consumer/justfile` has
`build`/`push`/`release` recipes that push to ghcr, as
`deployments/applications/services/driftwatch/justfile` does. The receiver
deploys with the infrastructure root and the consumer with the applications
root, so the image tag sits on one line in each root's `services.tf`. The
justfile reads the tag from `deployments/applications/services.tf` and fails
when `deployments/infrastructure/services.tf` pins a different one. `go vet`
and `go test` join `.pre-commit-config.yaml` as local `language: golang`
hooks scoped to `^applications/ov-sync-consumer/`, with a pinned
`language_version` (risk 3).

**Wiring, per `.claude/rules/terraform-file-layout.md`:**

- `deployments/applications/storage.tf`: bucket `ov-sync` in `local.buckets`,
  with no static users. CI keys belong to `ci-openviking-sync`.
- `deployments/infrastructure/services/seaweedfs.hcl`: a `receiver` task in
  the `seaweedfs` group that owns the network namespace: a prestart sidecar
  that takes over the group's two static ports (S3 and metrics) from the
  seaweedfs task. The seaweedfs task joins it with the podman driver's
  `network_mode = "task:receiver"` (driver 0.6.4,
  `bootstrap/inventory/group_vars/all.yml`) and declares no ports. This way
  SeaweedFS restarts alone and keeps the alloc running
  (spike:ov-sync-consumer/11); the reverse, the receiver joining SeaweedFS,
  fails the alloc on every SeaweedFS restart (spike:ov-sync-consumer/9). A
  receiver restart still fails the alloc and Nomad reschedules both, so the
  receiver stays small. The group's `restart` block allows at least three
  attempts, because an in-place SeaweedFS restart costs one failed start
  first (spike 11). The group's `network` block keeps its two static ports.
  The seaweedfs task gains a
  `notification.toml` template with `[notification.webhook]` pointing at the
  receiver's loopback port, `path_prefixes = ["/buckets/ov-sync/"]` and the
  bearer token, on the standard chrislusf/seaweedfs 4.48 image.
- `deployments/infrastructure/services.tf`: the receiver image tag passed to
  `seaweedfs.hcl`, and `ov-sync-consumer = "ov-sync"` in
  `local.seaweedfs_keyless_jobs`.
- `deployments/infrastructure/secrets.tf`: one random bearer token, written to
  KV under the seaweedfs job's path only. Both tasks that read it are in that
  job.
- `deployments/infrastructure/variables.tf`: an `ov-sync-consumer` entry
  (`lab`/`jasper`) in `var.vault_openviking_workloads`.
  `deployments/infrastructure/oidc.tf` and
  `deployments/infrastructure/machine_roles.tf` already loop over that
  variable, so they need no edit.
- `new:deployments/applications/services/ov-sync-consumer.hcl` and its
  `nomad_job` in `deployments/applications/services.tf`. It runs on radxa
  beside NATS and OpenViking (`.okf/nodes/placement.md`). It listens on no
  port, so it needs no static port and no firewall rule.
- Knowledge: a decision record for the receiver-to-queue-to-consumer design,
  naming the rejected `gocdk_pub_sub` backend (spike:ov-sync-consumer/8) and
  the rejected listener on radxa (spike:ov-sync-consumer/4). An
  `.okf/components/` page for the service. Updates to
  `.okf/nodes/placement.md` and `docs/reference/nats.md` for the new jobs and
  stream.

**Outcome:** with both jobs running, `mc cp` of a `.md` file to
`ov-sync/JasperHG90/localstack/docs/` can be read at
`viking://user/jasper/resources/projects/localstack/docs/` within 60 s, and
`mc rm` removes it within 60 s. This holds when OpenViking is stopped during
the copy and started again five minutes later. A burst of 200 files never
has more OpenViking requests in flight than the configured pool size.

## Could invalidate this plan

- **OpenViking may refuse the writes and deletes the consumer needs, made
  with a Vault identity token as a USER.** Settled by
  spike:ov-sync-consumer/7: on a local v0.4.17.1-9 under oidc with a
  lab/jasper USER token, `content/write` with `wait: true` created every
  missing parent, `DELETE /api/v1/fs` removed the file, and the emptied
  folder needed `recursive=true` because OpenViking keeps its own
  `.abstract.md` and `.overview.md` there (412 without it).
  `content/batch-write` returned 404 under missing folders. The consumer's
  write and delete rules above follow from this.
- **The filer webhook may not reach a listener in this job's shape.**
  spike:ov-sync-consumer/4 ran the job's exact args: the webhook queued the
  filtered `ov-sync` events but delivered none to a listener in another
  container (`dial tcp 127.0.0.1:0->...: connect: invalid argument`),
  because `-ip=127.0.0.1` in `deployments/infrastructure/services/seaweedfs.hcl`
  pins the client's source address. In spike:ov-sync-consumer/5 a loopback
  listener in the same network namespace got all four events as JSON with
  the bearer header, and nothing from other buckets. The design change
  answers this risk: the receiver listens on loopback in the SeaweedFS
  task's namespace. The rejected filer path, `gocdk_pub_sub` into NATS,
  sends every filer write as a gob envelope and needs the `_full` image
  (spike:ov-sync-consumer/8). What remains is risk 4, and that the receiver
  reaches NATS from that namespace, which the seaweedfs container's outbound
  LAN calls suggest (spike:seaweedfs-workload-identity/6) and the build
  checks.
- **The Go gates may need a toolchain the devcontainer lacks.** Settled by
  spike:ov-sync-consumer/1: prek 0.5.6 fetched Go itself with no system
  `go`, ran `go vet` and `go test` in a module under `applications/`, failed
  on a failing test, and passed in a fresh worktree on the shared cache.
- **Nomad's podman driver may not let the receiver share the seaweedfs
  task's network namespace.** Spike 5 shared the namespace by hand with
  podman, not through Nomad. If `network_mode = "task:seaweedfs"` fails under
  driver 0.6.4, or the receiver loses the namespace when the seaweedfs task
  restarts alone, the fallback is group `network { mode = "bridge" }`, which
  moves the S3 and metrics ports behind Nomad's CNI bridge and changes how
  every client reaches SeaweedFS. That is a different, larger ticket.
  Half real, per spike:ov-sync-consumer/9 (local Nomad 2.0.4, driver 0.6.4,
  podman 3.4.4 on jammy, busybox for SeaweedFS): the sidecar with
  `task:<main>` shared the main task's namespace, reached it on loopback and
  reached an address outside it. But restarting the main task alone failed
  the whole alloc, because the driver cannot delete a container another
  container still depends on, and Nomad rescheduled both tasks. For
  SeaweedFS that turns every in-place restart into a reschedule, under the
  service default of an exponential delay. Settled by
  spike:ov-sync-consumer/11, with the owner reversed: the receiver (a
  prestart sidecar) owns the namespace and holds the static port, the main
  task joins with `task:<receiver>`. The main task was reachable through the
  host port, on loopback and outbound, and `nomad alloc restart` of it alone
  left the alloc running with every check passing again, after one failed
  start and a 16 s restart delay. A receiver restart still fails the alloc.
  The design above follows this. Busybox stood in for both tasks, so the
  first deploy shows the real SeaweedFS and receiver.
