---
type: verdict
title: 'Verdict: docs-howto reviewer round 2'
description: 'reviewer verdict for round 2 of docs-howto: pass.'
tags:
- verdict
- review
generated:
  by: claude-opus/5.5
  at: '2026-10-19T20:01:22+00:00'
slug: docs-howto
pass: reviewer
round: 2
body_schema: verdict/1
---

## Summary

All three findings sent back are fixed and match the code. The how-to
skeleton still holds on the three pages, and the stamp is green. Verdict:
pass.

## Checked

- `loopctl gate stamp` in the worktree: pass on gate pre_commit, gate
  cli_tests and rows r1, r2, r3, r4 and r6, ending "stamp green:
  0e77631e64aa22f893abcb572572c245583ea1b596317b8878e85dc1c757ca90".
- Headings on the three pages: title `# How to`, four H2 sections in order,
  and `### Step N:` numbered from 1 with no gaps.
- f2 against embark.hcl: both tasks use `driver = "podman"` with
  `network_mode = "host"`. The paragraph no longer names phoenix. Tempo is
  the only 4317 holder it names.
- f3 against acme.hcl: the job has a `periodic` block, so a forced run makes
  an `acme/periodic-<id>` child, and the allocation is read from that child.

## Findings

- f1: resolved. Step 2 now says to run `just mfa_status` from the repository
  root (line 48).
- f2: resolved. Line 46 reads "the podman driver's `network_mode = "host"`,
  as embark uses".
- f3: resolved. Lines 64-67 force the run, list the children with
  `nomad job status acme`, read the allocation from
  `nomad job status acme/periodic-<id>`, then read the `issue` logs.

## Notes

Two prose lines in test-acme-job-changes-on-staging.md go past 80 columns:
line 77 (120 characters, in Step 3) and line 65 (81 characters, a code
comment). The 80-column wrap rule is not a gate, and line 77 is not part of
the f3 fix, so I am not asking for a change.
