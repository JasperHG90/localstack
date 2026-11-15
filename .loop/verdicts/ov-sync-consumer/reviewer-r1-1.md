---
type: verdict
title: 'Verdict: ov-sync-consumer reviewer round 1'
description: 'reviewer verdict for round 1 of ov-sync-consumer: fail.'
tags:
- verdict
- review
generated:
  by: claude-opus/5.5
  at: '2026-11-15T21:33:25+00:00'
slug: ov-sync-consumer
pass: reviewer
round: 1
body_schema: verdict/1
---

## Summary

The build matches the plan's shape, and the receiver holds up well: it cannot
exit on a NATS, token-file or publish fault, and the jobspec carries every
part of r13. One blocking defect remains. The catch-up pass sends OpenViking
requests outside the worker pool, so the pool does not bound requests in
flight the way the plan, r8 and two docs claim (f1). The fix touches the
tree lock, so I want to see it again. f2 (truncated ls in catch-up) and f3
(a per-key race that can keep stale content) do not block.

## Checked

- `loopctl gate stamp` from the worktree: green, stamp
  337b1b3c7b3885e4bc2f276f9345e4f6e4fef7661b9ffbb22ded2090e2347a60. Both gates
  (pre_commit, cli_tests) and rows r1 to r11 passed.
- Read every changed file in full: main.go, receiver, stream, consumer,
  mapping, catchup, openviking client, the tests and fakes, justfile,
  Dockerfile, both jobspecs, the tf diffs, the three changed cli tests, the
  ADR, the components page, and the nats, seaweedfs, node and summary edits.
- Rows r1 to r10: each test asserts its fails_when. r1 posts while NATS is
  down, checks for non-2xx and that the receiver did not exit, then brings
  NATS up on the same port and waits for a 2xx. r2 checks status, time
  against 10 s and that the receiver is still up, for both no stream and
  server gone. r3 tries five bad auth forms, checks the stream count stays
  0, then checks that a good request does publish. r4 checks the header
  exists, that a resend and a reordered body dedupe, and that a one-digit
  inode change gets a new id. r5 to r10 run against fakes that act like
  OpenViking does: 412 without recursive, summaries in every folder, a stat
  that lies. r7 checks the exact try count, flaky-then-success and a single
  dead letter. r8 measures the peak inside the fake. r9 records violations,
  checks that no stat is called, and catches a delete that leaves the folder
  behind (keepFolders). The gap in r8 is f1: the test does not cover the
  catch-up path.
- Receiver never exiting: Serve returns only on a bad NATS URL or a listener
  error. RetryOnFailedConnect, MaxReconnects(-1) and ReconnectBufSize(-1)
  are set. A missing token file gives 500 and the receiver stays up.
  net/http recovers a panic in a handler. Before the consumer has created
  OV_SYNC, a publish fails with no responders and the receiver answers 503.
  I think that is acceptable: the consumer's first catch-up pass runs at
  start and covers the gap, and the ADR records it.
- OpenViking assumptions checked against spike 7 and the installed source.
  `isDir` is the real ls field (`_tree_original`). ls and DELETE map
  AGFSNotFoundError to NOT_FOUND, which is HTTP 404 (`server/models.py`).
  ls entries carry no trailing slash and list folders as entries (spike 7
  stdout). The fake matches all of this.
- Folder-delete lock: the file delete runs under RLock and the emptiness
  check plus recursive delete under Lock, so no write lands between check
  and delete. Correct as written.
- Jobspec (r13, judged from the diff): the receiver is a prestart sidecar
  holding ports s3 and metrics and the seaweedfs service and /healthz check.
  seaweedfs has `network_mode = "task:receiver"` and no ports. The restart
  block has attempts = 3. The receiver template is noop. Memory is 96 MB
  with GOMEMLIMIT=40MiB. Prometheus scrapes 192.168.2.29:9327 statically,
  which is unchanged because the receiver container still maps it. Nothing
  else in the repo depends on the seaweedfs task owning the ports. The
  default Vault workload policy is scoped `secret/data/<ns>/<job>/*`, so
  both tasks can read `default/seaweedfs/webhook`. The heredoc and jobspec
  edits are intended: they add new templates, and the one existing
  template is unchanged. The live alloc restart cannot be shown before
  apply. Neither can r12. By code, 20 tries with a 30 s cap ride out a
  5-minute outage and land within about 30 s of recovery.
- The three changed cli tests still test what they did. They add the
  eighth bucket and the fourth keyless job. The iam regex narrowed to
  `[^\n]*` so it cannot start at the receiver's new `{{ with secret`
  template. Four new jobspec tests were added.
- minio-go 7.4.1 STSWebIdentity sends RoleSessionName whenever RoleARN is
  set, as the keyless how-to requires.
- r14: the ADR names gocdk_pub_sub (spike 8) and the radxa listener (spike
  4). The components page, placement, the node pages and the NATS reference
  match the build, except for the in-flight claim in f1.

## Findings

- f1 (bug, blocking): requests in flight can reach Pool+1 because catch-up
  is outside the pool. Bound catch-up's OpenViking calls by the same limit,
  extend TestConsumerPoolBound (or add a test) to run CatchUp during the
  burst, and correct the jobspec comment and the components page. Watch for
  deadlock: a remover holding tree.Lock must not wait for a slot held by a
  worker that is blocked on RLock.
- f2 (bug, non-blocking): catch-up's single recursive ls can be truncated
  by node_limit or level_limit, and has_more is ignored. Files missing from
  the listing are then rewritten on every pass.
- f3 (hardening, non-blocking): there is no per-key ordering between
  workers, so a stale read can overwrite a newer write, and catch-up does
  not repair content.

## Notes

The summary.md edit also drops "read back intact" and the bullet about older
loop tickets. Both cuts look like word-budget trims, not claims made false,
so I raise no finding.
