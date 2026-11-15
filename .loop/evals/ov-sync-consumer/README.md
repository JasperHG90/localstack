---
type: eval
title: 'Eval: ov-sync-consumer'
description: 'Definition of done for ov-sync-consumer: 14 row(s).'
tags:
- eval
generated:
  by: process:loopctl/2.2.2.dev1+gd84319696
  at: '2026-11-15T20:49:09+00:00'
slug: ov-sync-consumer
signoff:
  signer: delegated:jasperginn@gmail.com/claude-opus-5-5
  hash: 74e0c8374422d2fc40df59abe91825f6bdf9b44281ad78ea4eb8577f516dc9a3
  at: '2026-11-15T20:49:09+00:00'
verified: null
---

Rows: rows.json; the fields each row takes: loopctl schema eval-rows.

- r1: the receiver starts, serves the webhook endpoint and stays up when NATS is unreachable
  Fails when: the receiver exits, or does not answer on its port, while NATS cannot be reached
- r2: a publish failure makes the receiver answer the webhook with a non-2xx status at once and keep running
  Fails when: the answer is 2xx, takes longer than the webhook's 10 s timeout, or the receiver exits
- r3: the receiver refuses a request with a missing or wrong bearer token and publishes nothing for it
  Fails when: such a request gets 2xx or reaches JetStream
- r4: the receiver publishes each accepted event to the stream with a Msg-Id derived from the event, so a redelivered webhook dedupes
  Fails when: an event is published without a Msg-Id, or the same event gets two different ids
- r5: the consumer acts on the object's current state, not the event type: an existing object is written to OpenViking with content/write and wait true, a missing one is deleted
  Fails when: a delete event for an object that exists again causes a delete, a create event for a gone object causes a write, or batch-write is used
- r6: the consumer maps <owner>/<repo>/<path> to viking://user/jasper/resources/projects/<repo>/<path>, ignores _state/ keys and skips unmapped prefixes
  Fails when: a URI is wrong, a _state/ key reaches OpenViking, or an unmapped prefix is written
- r7: the consumer acks a message only after OpenViking accepts, retries with backoff, and moves it to the dead-letter subject after N failed tries
  Fails when: a message is acked before success, is retried without bound, or is dropped without reaching the dead-letter subject
- r8: under a burst of 200 events the consumer never has more OpenViking requests in flight than its pool size
  Fails when: the observed in-flight count exceeds the configured pool size
- r9: the consumer deletes an emptied OpenViking folder with recursive=true only when ls with hidden files shows nothing but .abstract.md and .overview.md, and judges removal by ls
  Fails when: a recursive delete runs on a folder holding any other entry, or removal is judged by fs/stat
- r10: the catch-up pass writes a bucket file missing from OpenViking and deletes an OpenViking file whose object is gone
  Fails when: either difference survives a catch-up pass
- r11: the repo gates pass, including the new go vet and go test hooks and Terraform fmt and validate
  Fails when: just pre_commit exits non-zero
- r12 (judgment): after apply, mc cp of a .md file to ov-sync/JasperHG90/localstack/docs/ is readable at viking://user/jasper/resources/projects/localstack/docs/ within 60 s and mc rm removes it within 60 s, also when OpenViking is stopped during the copy and started five minutes later
  Fails when: either takes 60 s or more, or the file is lost or left behind across the OpenViking outage
- r13 (judgment): in seaweedfs.hcl the receiver is a prestart sidecar that owns the static ports and the seaweedfs service and check, SeaweedFS joins it with network_mode task:receiver, the restart block allows at least three attempts, the receiver's token template is change_mode noop with a memory limit with headroom; after apply, nomad alloc restart of the seaweedfs task alone leaves the alloc running and S3 answering
  Fails when: any of these is missing in the jobspec, or the live restart fails the alloc
- r14 (judgment): the decision record (naming the rejected gocdk_pub_sub path and the rejected listener on radxa), the components page, placement and the NATS reference describe what was built
  Fails when: a page is missing or disagrees with the jobs and stream as built
