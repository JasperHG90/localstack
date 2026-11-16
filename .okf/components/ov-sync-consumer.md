---
type: component
title: ov-sync-consumer, repo docs into OpenViking
description: "How repo docs in the ov-sync bucket reach OpenViking: one Go binary run as a receiver sidecar inside the seaweedfs job and as a consumer on radxa, joined by the JetStream stream OV_SYNC. The consumer applies each file's current state, paced by a pool and a rate limit, with retries, a dead-letter subject and a catch-up pass."
tags: [ov-sync-consumer, openviking, seaweedfs, nats, jetstream, go, component]
status: stable
generated:
  by: claude-opus/5.5
  at: 2026-11-15
sources:
  - id: main
    resource: applications/ov-sync-consumer/main.go
  - id: receiver
    resource: applications/ov-sync-consumer/internal/receiver/receiver.go
  - id: consumer
    resource: applications/ov-sync-consumer/internal/consumer/consumer.go
  - id: catchup
    resource: applications/ov-sync-consumer/internal/consumer/catchup.go
  - id: openviking-client
    resource: applications/ov-sync-consumer/internal/consumer/openviking.go
  - id: mapping
    resource: applications/ov-sync-consumer/internal/consumer/mapping.go
  - id: stream
    resource: applications/ov-sync-consumer/internal/stream/stream.go
  - id: justfile
    resource: applications/ov-sync-consumer/justfile
  - id: seaweedfs-jobspec
    resource: deployments/infrastructure/services/seaweedfs.hcl
  - id: consumer-jobspec
    resource: deployments/applications/services/ov-sync-consumer.hcl
  - id: infra-services
    resource: deployments/infrastructure/services.tf
  - id: infra-secrets
    resource: deployments/infrastructure/secrets.tf
  - id: infra-variables
    resource: deployments/infrastructure/variables.tf
  - id: app-services
    resource: deployments/applications/services.tf
  - id: app-storage
    resource: deployments/applications/storage.tf
  - id: jobspec-test
    resource: cli/tests/test_seaweedfs_jobspec.py
---

# ov-sync-consumer, repo docs into OpenViking

CI uploads each repo's `docs/` and `.okf/` to the SeaweedFS bucket `ov-sync`,
laid out as `<owner>/<repo>/...`, plus `<owner>/<repo>/_state/manifest.json`
for CI's own use. ov-sync-consumer makes
`viking://user/jasper/resources/projects/<repo>/` match that bucket. Why it is
split into a receiver, a queue and a consumer is
[ADR 0026](/decisions/0026-repo-docs-reach-openviking-through-a-webhook-receiver-a-jetstream-queue-and-a-consumer.md).
It was built by the loop ticket `ov-sync-consumer`. The CI upload is the
ticket `ci-openviking-sync`.

## The pieces

| Piece | Where |
|---|---|
| Source and tests (Go module) | `applications/ov-sync-consumer/` |
| Image build, `test-one` | its `Dockerfile` and `justfile`; the tag is `ov_sync_consumer_image` in both roots' `services.tf` |
| Go gates | the `ov-sync-consumer-go` hook in `.pre-commit-config.yaml` (prek fetches Go 1.27.4) |
| Receiver | task `receiver` in `deployments/infrastructure/services/seaweedfs.hcl` |
| Consumer | `deployments/applications/services/ov-sync-consumer.hcl`, `nomad_job.ov_sync_consumer` |
| Webhook bearer token | `default/seaweedfs/webhook` in `deployments/infrastructure/secrets.tf` |
| OpenViking identity (`lab`/`jasper`) | the `ov-sync-consumer` entry in `var.vault_openviking_workloads` |
| Bucket and its keyless role | `ov-sync` in `local.buckets` (applications `storage.tf`) and in `local.seaweedfs_keyless_jobs` (infrastructure `services.tf`) |
| Prefix map | `prefixes` in `nomad_job.ov_sync_consumer`, rendered to `local/prefixes.json` |

## Receiver

A prestart sidecar in the seaweedfs group, listening on `127.0.0.1:20500`.
SeaweedFS's `notification.toml` sends filer events under
`/buckets/ov-sync/` there with the bearer token. The receiver checks the
token, then publishes the raw event to `ovsync.events` with a `Msg-Id` that
is the SHA-256 of the event's canonical JSON, so a redelivered webhook is
dropped inside the stream's two-minute dedupe window. It holds no OpenViking
or S3 credential.

It owns the group's network namespace and both static ports, and the
seaweedfs task joins with `network_mode = "task:receiver"`. Its exit fails
the whole alloc, so it is written never to exit on an outside fault:

- It starts with NATS unreachable and reconnects forever.
- While it cannot publish it answers 503 at once (no publish buffering), and
  the webhook retries.
- It never creates the stream. Until the consumer has created it, every
  event gets 503.
- It reads the token file on every request, so the template is
  `change_mode = "noop"` and a rotated token still takes effect.
- 96 MB memory limit with `GOMEMLIMIT=40MiB`.

## Consumer

On radxa, host network, no port. Each of `POOL_SIZE` (4) workers fetches one
message at a time. The OpenViking client takes one of `POOL_SIZE` slots for
each request, workers and catch-up alike, so at most four OpenViking requests
are in flight. A slot is held for one request, never while waiting on the
folder-delete lock, so the two cannot deadlock. Two events for one file are
handled one after the other: a worker takes a lock on the file's OpenViking
URI before it reads the object and keeps it until OpenViking has the result,
so an older read never lands after a newer one. It takes that lock before the
folder-delete lock and never while holding it. A shared limiter starts at
most `RATE_PER_SECOND` (2) events a second, which bounds the VLM calls each
write triggers.

For each event it strips `/buckets/ov-sync/` from the key, skips folder
events, and maps the key through the prefix map. Keys under `_state/` and
unmapped prefixes are skipped. Then it reads the object's current state,
because the webhook delivers out of order:

- The object exists: `POST /api/v1/content/write` with `wait: true`, one
  file per call. Never `content/batch-write`, which 404s under missing
  folders (spike:ov-sync-consumer/7). An object that is not valid UTF-8 and
  is not an image is skipped with an INFO `binary file skipped` line naming
  the key, because the JSON write would turn its bytes into U+FFFD.
- The object is an image (extension `.png`, `.jpg`, `.jpeg`, `.gif` or
  `.webp`, any case; the extension alone decides): it is uploaded the way
  OpenViking ingests a file, into its own folder
  ([ADR 0030](/decisions/0030-ov-sync-stores-images-in-openviking-per-file-folders.md)).
  A key that maps to `D/name`
  lands at `D/name/name`: `POST /api/v1/resources/temp_upload` (multipart
  field `file`) gives a `temp_file_id`, then `POST /api/v1/resources` with
  `to: D/name`, `source_name: name`, `wait: true` stores it, creates missing
  parents and replaces what that folder held
  (spike:ov-sync-consumer-binary-upload/1, /4). Before the add, a plain file
  at `D/name` (the damaged copy an old text write left) is deleted, but only
  when `ls D` lists it with `isDir` false: a non-recursive delete of an image
  folder is refused with 412 (spike:ov-sync-consumer-binary-upload/8). The
  per-key lock, deletes and catch-up all use `D/name/name`.
- The object is gone: `DELETE /api/v1/fs` on the file, then each folder
  above it up to the mapped root is removed with `recursive=true`, but only
  when `fs/ls` with hidden files shows nothing in it but `.abstract.md` and
  `.overview.md`. Removal is checked by listing the parent, never by
  `fs/stat`, which answers 200 for a removed folder. A recursive delete holds
  a lock that keeps every write out until it is done. An image's folder
  `D/name` is the exception: after its delete it stays listed in `ls D` for
  good as an empty folder (spike:ov-sync-consumer-binary-upload/6), so it
  counts as removed when `ls D/name` is empty. That ghost folder stays
  visible in ov-dash and keeps `D` and every folder above it from being
  removed. A later upload to the same URI still works.

It acks only after OpenViking accepts. A failure is retried with a delay
doubling from 2 s to 30 s. After 20 tries (about eight minutes, longer than
a five-minute OpenViking outage) the event is copied to `ovsync.dead` with
an `Ov-Sync-Error` header and terminated. A body that is not JSON goes there
at once.

OpenViking answers a write or delete with 409 `lock acquire timed out` when it
gives up waiting for a folder lock, and that lock can stay held for minutes,
probably by its own folder summary. The consumer retries such an event on the
same schedule but logs it at INFO as `folder busy`, and catch-up skips the
file until its next pass. The first 189-file sync hit it dozens of times and
took over 20 minutes; what holds the lock is the stub
`ov-sync-consumer-lock-scope`.

The catch-up pass runs at start and every 15 minutes. For each mapped prefix
it lists the bucket and the OpenViking folder, writes what is missing and
deletes what has no object. It compares which files exist, not content. It
lists OpenViking one folder at a time and follows `has_more`, because a
recursive `fs/ls` stops three levels down and at 1000 entries. It never
deletes a file at `U` while `U/base(U)` is wanted: that is an image's old
plain copy, which the image's upload deletes.

The OpenViking token is a Vault identity token minted from
`identity/oidc/token/openviking-ov-sync-consumer`, as hermes mints its own,
with `change_mode = "noop"` and read on every request. The S3 credential
comes from minio-go's web identity exchange under role
`arn:aws:iam::role/ov-sync-consumer`, as tempo does it.

## Apply order

Infrastructure first: it creates the webhook token, the keyless role, the
OpenViking identity role and the receiver. Then applications: the bucket and
the consumer. Push the image before either, with
`just -f applications/ov-sync-consumer/justfile release`.

## Invariants and what enforces them

| Must stay true | Enforced by |
|---|---|
| Receiver stays up without NATS and answers non-2xx on a failed publish | `TestReceiverStartsWithoutNATS`, `TestReceiverPublishFailureReturnsNon2xx` |
| Bad token publishes nothing | `TestReceiverRejectsBadToken` |
| Redelivered event dedupes | `TestReceiverPublishesWithMsgID` |
| Current state wins, no batch-write | `TestConsumerAppliesCurrentState` |
| Prefix map, `_state/` skipped | `TestConsumerMapsPrefixes` |
| Ack after success, bounded retries, dead letter | `TestConsumerRetriesThenDeadLetters` |
| A folder lock 409 retries as `folder busy`, not a failure | `TestLockConflictLogsBusy`, `TestOtherConflictFails`, `TestCatchUpLockConflictIsBusy` |
| In-flight requests bounded by the pool | `TestConsumerPoolBound` |
| Recursive delete only on an emptied folder, judged by ls | `TestConsumerFolderDeleteGuard` |
| Catch-up repairs both directions | `TestCatchUpRepairs` |
| Catch-up sees past the recursive ls caps | `TestCatchUpListsWholeTree` |
| An image is uploaded byte for byte to `D/name/name`, siblings untouched | `TestImageUploaded` |
| A changed image replaces the old one, and a plain copy at `D/name` goes first | `TestImageReplacesOldCopies` |
| Another binary is skipped with an INFO line, nothing written | `TestOtherBinarySkipped` |
| Text still goes through `content/write` byte for byte | `TestUTF8ObjectWrittenExactly` |
| Catch-up finds images at `D/name/name`, spares the old plain copy, and accepts the ghost folder | `TestCatchUpImages` |
| Both roots deploy the same image | the justfile's tag check |
| The receiver owns the namespace and the service, restart attempts at least three, its template is noop | `cli/tests/test_seaweedfs_jobspec.py` |

The tests use an in-process NATS server and httptest fakes of S3 and
OpenViking, so they need no network.

## Related

- [SeaweedFS](/components/seaweedfs.md)
- [NATS](/components/nats.md)
- [The OpenViking service](/components/openviking-service.md)
- [Node placement](/nodes/placement.md)
