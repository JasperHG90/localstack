---
type: spike
title: Spike seaweedfs-cutover-registry/2
description: after the backup, restore, marker removal and switch, does every pre-switch image serve unchanged by tag and digest, does a new push land on SeaweedFS, and does MinIO stay fixed?
tags:
- spike
generated:
  by: process:loopctl/2.2.2.dev1+gd84319696
  at: '2026-10-20T07:54:20+00:00'
slug: seaweedfs-cutover-registry
n: 2
outcome_written: true
---

# Spike seaweedfs-cutover-registry/2

after the backup, restore, marker removal and switch, does every pre-switch image serve unchanged by tag and digest, does a new push land on SeaweedFS, and does MinIO stay fixed?

The command exited 0:

```
/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/reg/verify.sh
```

## Outcome

Yes. The sequence on 2026-10-20 (UTC):

- 07:40: baseline through the registry API (files/snapshot.py, files/before.json), covering 33 tags, each tag's manifest digest, the manifest re-read by digest, the config blob's sha256, and the digest and size of all 192 layers (9.1 GB counted per tag). Layers were checked with HEAD through the registry's redirect to a presigned S3 URL, so no layer body was downloaded.
- 07:47: `nomad job stop registry`. The forced `backup-minio` run (periodic-1792482443, alloc e12ec616) exited 0 at 07:48:17. `restore-s3` for registry (dispatch-1792482509-16fcb201, alloc 72fa47f2) exited 0 at 07:50:54, so its copy, `rclone check` and directory check passed.
- files/drop_markers.py found MinIO's registry bucket with 399 keys and no directory keys, and SeaweedFS's with 1,124 keys, of them 725 zero-byte `dir/` markers the restore had written (`spike:backup-durable-buckets/3` predicted 725). It deleted exactly those 725. SeaweedFS then held the same 399 keys at the same sizes as MinIO.
- 07:51: the applications root updated `nomad_job.registry` to the `seaweedfs` identity, its role and `regionendpoint` on 8333. The deployment is successful.

This run (stdout.txt): every one of the 33 tags reads back with the same manifest digest, by tag and by digest, the same config hashes, and the same layer digests and sizes, now served through SeaweedFS presigned URLs signed with the role's STS credentials. A new OCI image pushed to `seaweedfs-cutover-check` (manifest 201) read back by tag and by digest, its layer matched, and its manifest was then deleted (202). SeaweedFS's registry bucket went from 399 to 404 objects, while MinIO's stayed at 399. The five leftover objects are the test image's blobs and links, which registry garbage collection reclaims.

## Files

- `run.json`: the command, when it ran, its exit, the commit and tree it ran on, and where its output went
- `stdout.txt`: its standard output
- `stderr.txt`: its standard error
- `files/verify.sh`: a copy of `/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/reg/verify.sh`, which the command used
- `files/snapshot.py`: a copy of `/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/reg/snapshot.py`, which the command used
- `files/push_check.py`: a copy of `/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/reg/push_check.py`, which the command used
- `files/drop_markers.py`: a copy of `/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/reg/drop_markers.py`, which the command used
- `files/before.json`: a copy of `/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/reg/before.json`, which the command used
