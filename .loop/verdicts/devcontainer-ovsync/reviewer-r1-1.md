---
type: verdict
title: 'Verdict: devcontainer-ovsync reviewer round 1'
description: 'reviewer verdict for round 1 of devcontainer-ovsync: fix.'
tags:
- verdict
- review
generated:
  by: claude-opus/5.5
  at: '2026-10-28T10:27:05+00:00'
slug: devcontainer-ovsync
pass: reviewer
round: 1
body_schema: verdict/1
---

## Summary

The change does what the plan asks. The Dockerfile installs ov-sync from the
ov-sync-v0.3.0 tag. devcontainer.json bind-mounts the host's ~/.openviking
directory read-only, and the ~/.ovx mount is unchanged and still writable.
The new how-to and ADR 0024 match the plan and the tools' real behavior. One
docs finding that does not block: a prerequisite links to a page that does
not give the reader what the bullet promises.

## Checked

- Gates: `loopctl gate stamp` from the worktree came back green
  (2b28115609be50aa478b3f6caa4233d8bcd40b0a159d05f167fd54f475c022cd). It passed
  pre_commit, cli_tests and eval rows r1 to r4.
- r1: the test asserts the exact `RUN uv tool install ov-sync --from ...@ov-sync-v0.3.0#subdirectory=packages/ov-sync"`
  line. It fails with a branch, another tag or no ref.
- r2: exact membership of the full mount string, with type=bind and readonly.
  It fails if the mount targets ovcli.conf or drops readonly.
- r3: exact membership of the ~/.ovx mount string. Adding `,readonly` or
  removing the mount makes it fail.
- r4: the grep chain matches the new page, and test_how_to_skeleton passes.
  The page has the four sections in order and Step 1 to Step 5.
- r5: a judgment row deferred until the operator rebuilds, as the briefing
  says. Not judged in this round.
- CLI claims, checked against the spike ovsync v0.3.0 install and the image's
  ovx: `ovsync init <folder>` and `ovsync run <folder> --create-root` exist.
  init writes ov-sync.toml and asks for root_uri under [sync]. `ovx -L --bind`
  and `--no-bind` exist. ovx writes through a temp file and `os.replace`, so
  mounting the directory rather than the file is right. Plain `ovx -L`
  re-binds when bound.json exists (`_offer_to_bind`), which matches the
  warning in Step 5. ovx needs `$VAULT_ADDR`.
- Consistency: no existing docs page covers the devcontainer's host mounts, so
  a new how-to fits plan step 3. The index entries in docs/README.md and
  docs/how-to/README.md are right. `kmctl check` passes. The summary was
  re-acked against ADR 0024 with its body unchanged. The ADR names the
  alternatives it rejected.
- Slop scan of the new how-to and ADR: no em dashes, no ` -- ` in prose, no
  semicolon splices, no prose lines over 80 characters, no tier-1 words.

## Findings

- f1 (docs, not blocking): Prerequisites says "`ov` and `ovx` installed on the
  host, with an ovx profile `localstack`. See How to call OpenViking from the
  CLI." That page installs neither tool and never mentions ovx profiles. It
  mints a token with `vault read` and calls the API with curl. The
  `VAULT_ADDR` bullet has no link. Point both bullets at a page that covers
  them, such as the ovx README in openviking_extensions at the pinned tag. If
  no page covers them, drop the "See" so the bullet does not promise
  something the link does not give.

## Notes

Step 3 says "The build fails" when ~/.openviking is missing. Strictly,
container creation fails on the bind source, not the image build. A reader
running Rebuild Container sees the same failure either way, so I am not
raising it as a finding.
