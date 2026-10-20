---
type: decision
title: "ADR 0022: OpenViking carry-over copies storage and re-indexes"
description: "The trees kept from the old OpenViking store are copied key for key into the new bucket and re-indexed there, blog-scraper merged into blogs, with no old instance running."
tags: [adr, decision, openviking, seaweedfs, postgres]
generated:
  by: process:kmctl/0.12.1
  at: 2026-10-20T16:30:08Z
status: stable
sources:
  - resource: "deployments/applications/services/ov-carry-over.hcl"
  - resource: "scripts/ov_carry_over.py"
  - resource: "deployments/applications/storage.tf"
---

# ADR 0022: OpenViking carry-over copies storage and re-indexes

## Context

OpenViking started over on a new bucket and schema
([ADR 0021](/decisions/0021-openviking-starts-over-on-a-v2-store.md)). The
operator keeps four trees from the old store, all under
`viking://user/jasper/resources/`: clips (280 objects), blog-scraper (2417),
blogs (166) and leo (449). Memories, peers, sessions, projects and handoffs
stay behind. blog-scraper and blogs hold the same eight sources, so the
operator wants them as one `blogs/<source>/` tree. The old instance is
stopped, and running it again would write its queue and vector state into the
backup.

## Decision

A dispatched Nomad job, `ov-carry-over`, copies the four trees in SeaweedFS
from `openviking` to `openviking-v2` with rclone, key for key, blog-scraper
into `blogs/`. Every copy skips keys the target holds, so a re-run only adds
what is missing. blog-scraper's sidecars get their URIs rewritten to `blogs/`
on the way. Its key reads the old bucket and cannot write it.

`scripts/ov_carry_over.py` then works through the new instance's API: it
regenerates the summaries of the eight directories where both blog trees
hold files, runs
`vectors_only` on clips, blogs and leo, which reuses the copied summaries and
makes no VLM call, and copies each image's level-2 row from the old schema
with SQL, because 0.4.17.1 cannot re-index an image from its overview
(spike:ov-carry-over/4). Spikes 1 and 3 of the same ticket showed the copy
and re-index index every file with no failures.

Rejected: OpenViking's pack export and import (`/api/v1/pack/*`). It needs
the old instance running, either before the cutover or as a temporary second
instance. Before the cutover it would have to land ahead of ADR 0021, and a
temporary instance writes into the backup. A storage copy needs no old
instance at all.

## Consequences

- Re-indexing costs embeddings for about 2900 files and about 300 VLM calls
  for the merged directories, not a new summary per file.
- 19 of the 71 images had no row in the old schema and stay unsearchable, as
  they were before.
- The `ov-carry-over` user, its key and the job stay until the operator signs
  off on the carry-over. Removing them is a follow-up.
- The blog-scraper skill saves under `blogs/<source>/` from now on, so no new
  `blog-scraper/` tree appears.
