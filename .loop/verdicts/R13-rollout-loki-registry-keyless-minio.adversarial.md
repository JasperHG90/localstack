---
verdict: pass
tree: 4b57a536b3a2fc3d51b683a632e7f7ae1697743b
---

# Adversarial review, cycle 3 (final) — R13-rollout-loki-registry-keyless-minio

**Verdict: pass. Nothing blocks. Commit it.**

Both cycle-2 items are closed on evidence: the required fix (R13-A6) is
taken and the recommendation (R13-A7) is taken and now correct in both
readings. The open refresh item (R13-A3) is closed this cycle on live
post-expiry evidence. Three advisories remain, none of them blocking, and
one of them corrects the hand-off summary.

## Binding

This verdict declares no `bound_paths:` / `scope:` / `citations:` lines. I
was given a tree fingerprint but no 64-hex scope digest, and writing a
digest I computed myself for a set I chose would bind the gate to the wrong
thing. Omitting the three lines falls back to the whole-tree binding, which
is stricter than any path set I could declare, so the commit gate loses
nothing. Same choice as the R9 verdict in this repo.

For the record, the artifact I reviewed is these five paths plus the
harness's own `.loop/ledger.json`:

    deployments/applications/services.tf
    deployments/applications/services/loki.hcl
    deployments/applications/services/registry.hcl
    deployments/applications/storage.tf
    docs/workload-identity.md

That is exactly the code surface plan section 7 declares (lines 147-188).
Nothing outside it changed. Scope is clean.

## Deterministic floor

`loopctl verify-eval-substance R13-rollout-loki-registry-keyless-minio`
returns `valid`, with no `warn:` lines. No hard fail, no advisory, so the
deep pass proceeded.

## Gate, re-run independently

`just pre_commit` from the worktree root: 18 hooks, all Passed, including
Terraform Validate (per root), Nomad Format, Terraform Format, Ruff, Mypy
and both pytest suites. I ran it myself rather than reading the stamp.

## The five edits, attacked one by one

### 1. "loudly" (was "silently") — correct, no new inaccuracy

`docs/workload-identity.md:418` = `Four things per job, and the second is the one that breaks everything,`
`docs/workload-identity.md:419` = `loudly:`

`silently` now appears nowhere in the file. The replacement is right for
this route rather than merely different: with `AWS_CONFIG_FILE` or
`AWS_SDK_LOAD_CONFIG` unset, aws-sdk-go v1 leaves a `ChainProvider` in
place, which errors with `NoCredentialProviders`; it never installs an
anonymous signer. That is what `:330-333` and `:435` already said, and the
heading no longer contradicts them.

I attacked the emphasis too: item 4 (`AWS_WEB_IDENTITY_TOKEN_FILE`) also
breaks everything. But item 2 is singled out for how easy it is to omit, not
for being uniquely fatal, and the jobspec comments say the same
(`loki.hcl:52`). Not a defect.

### 2. The "still keyed" rewrite — true in the narrow AND the plain reading

`docs/workload-identity.md:269` = `and each keeps its key provisioned as a rollback path. memex is the only one`

All three claims check out:

- **"the only one of those four."** `nomad job inspect memex` still carries
  `MEMEX_SERVER__FILE_STORE__ACCESS_KEY` (source: `memex.hcl:124` renders
  `${memex_minio_secret}`). `nomad job inspect` on loki and registry returns
  zero matches for all nine env names plus `accesskey`, `secretkey` and
  `minio.env`. tempo is on the minio-go route and still sets
  `AWS_WEB_IDENTITY_TOKEN_FILE`.
- **`backup-minio` on the root credential.** `backup.tf:65-70` stores
  `access_key = "minio"` with `random_password.minio_secret_key.result`.
  `secrets.tf:15-20` stores that same pair at `default/minio/localstack`,
  and `minio.hcl:85-86` reads that entry into `MINIO_ROOT_USER` /
  `MINIO_ROOT_PASSWORD`. Same key, so "the root credential" is literal, not
  loose.
- **`storage.tf` mints keys no job consumes.** `generate_access_key = true`
  for datalake, models, mlflow-artifacts and openviking. The file says so
  itself: `storage.tf:53-56` records that mlflow the service is gone, and
  `:33-35` that datalake, openviking and mlflow-artifacts have no Vault
  entry because nothing consumes them.

The old sentence was false under the plain reading. This one is true under
both. Closed.

### 3. The leading-slash sentence — right about which side is which

`docs/workload-identity.md:438` = `   path, so they differ by a leading slash and must otherwise agree.`

Checked against the code, not the prose. `loki.hcl:139` and
`registry.hcl:128` are `destination = "local/aws-config"`, no leading slash,
resolved by Nomad under the task directory. `loki.hcl:63` and
`registry.hcl:60` are `AWS_CONFIG_FILE = "/local/aws-config"`, with the
slash, because the Docker driver mounts the task's `local/` at `/local`
inside the container. The sentence assigns the alloc-relative half to the
destination and the in-container half to the env var. That is the right way
round. The old sentence ("must match exactly") was false; this one is true.

One nit, not a finding: Nomad resolves `destination` against the *task*
directory, which sits inside the allocation directory, so "alloc-relative"
is loose. It carries the meaning that matters (relative, not absolute), and
I would not spend a cycle on it.

### 4. The image pins — verified at runtime, not from the jobspec alone

`docs/workload-identity.md:455-456` names
`docker.io/grafana/loki:3.4.2` on `gcr.io/distroless/static:debug` and
`docker.io/library/registry:3.1.1`, Alpine-based. Both pins match the
jobspecs (`loki.hcl:84`, `registry.hcl:81`). I did not stop there, because
the *base* claim is the load-bearing one and no gate touches it:

- loki alloc `cbcf925a`: `/etc/os-release` says `PRETTY_NAME="Distroless"`,
  Debian 12 bookworm; no `libc.so.6` anywhere under `/lib`, which is what
  distinguishes distroless `static` from `base`; `/busybox/sh` and
  `/busybox/wget` present; `/bin/sh -> /busybox/sh`, so the SDK's `sh -c`
  resolves; `uid=0(root)`.
- registry alloc `7acd9c43`: `/etc/alpine-release` = `3.23.5`;
  `/bin/sh -> /bin/busybox`; `/usr/bin/wget`; `uid=0(root)`.

So "whose busybox supplies both", "Alpine-based" and "both run as root" are
all confirmed. The previous text named loki's *base* as its image, which was
wrong; the fix is right and the correction did not introduce a new error.

### 5. The heading edit — NOT MADE. The hand-off is wrong here.

This is the one place the summary I was given does not match the tree.

`docs/workload-identity.md:318` = `   the two symptoms are opposites.** Exchanging by hand with `curl`, the`

The hand-off says: *"Your cycle-2 note on the heading: 'and the two are
opposites' is dropped."* It was not dropped.
`git diff -U0 -- docs/workload-identity.md | grep -E '^[-+].*opposites'`
returns nothing — the line was never touched by this diff. The phrase in the
file is "the two symptoms are opposites", not "and the two are opposites",
which may be how the mismatch went unnoticed.

The finding it was supposed to close (R13-A8) therefore stands: the passage
below that heading now describes three symptoms, not two — the curl-by-hand
`None of the given policies (...) are defined`, minio-go's quiet anonymous
fallback, and aws-sdk-go's loud chain error — and the first and third are
not opposites, they are both explicit failures.

**This is advisory, not blocking**, on the same reasoning I used in cycle 2:
it is a bold lead-in, the three paragraphs under it are individually correct
and explicit, and no gate or eval row depends on it. I am recording it so
the ledger reflects the tree rather than the summary.

## New this cycle

### R13-A10 (low, advisory) — the corrected claim survives in both jobspecs

`deployments/applications/services/loki.hcl:132` = `      ### Points the SDK at the helper. The path here and AWS_CONFIG_FILE above`
`deployments/applications/services/loki.hcl:133` = `      ### must stay identical.`
`deployments/applications/services/registry.hcl:121` = `      ### Points the SDK at the helper. The path here and AWS_CONFIG_FILE above`
`deployments/applications/services/registry.hcl:122` = `      ### must stay identical.`

The documentation pass fixed this claim in the docs and left it standing in
the two jobspecs, so the repo now contradicts itself: `:438` says the two
paths differ by a leading slash, these four lines say they must be
identical. Taken literally the comment is a small trap — an operator who
made the destination identical to `AWS_CONFIG_FILE` would write
`destination = "/local/aws-config"`, an absolute path Nomad rejects at
submit time.

The root is the plan's own wording (`.loop/plans/...:163`, "destination must
match exactly"), which is frozen and out of scope. This is my own cycle-2
miss, not a regression.

**Not blocking:** it is a comment, it changes no behavior, the correct code
sits six lines below it, and no gate or eval row reads it. A one-line
follow-up when someone next opens these files.

### R13-A11 (info) — split endpoint sourcing inside each jobspec

`loki.hcl:113` and `registry.hcl:102` build the STS URL from
`${minio_host}` (Consul `node_address`), while `loki.hcl:183` and
`registry.hcl:145` keep the pre-existing literal `192.168.2.29`. They agree
today: `consul catalog nodes -service=minio` reports `192.168.2.29`. If
MinIO moved, the helper would follow discovery and the storage config would
not, and the symptom would read as a credential fault rather than an address
one. The new half is the better-sourced one and `memex.hcl:122` already uses
`${minio_host}`, so this is a note, not a defect.

## R13-A3, the refresh item: CLOSED, and not by the error scan

You asked whether a clean credential-error scan after 09:16 UTC closes this.
**On its own, no — I would have recorded it as carried.** As it happens I
gathered the missing evidence directly, so it is closed. Both halves matter,
so here is the reasoning separate from the result.

**Why a clean scan alone is not enough.** Absence of errors only proves
something if a request was attempted after the expiry boundary. registry
makes zero S3 requests when nobody pushes or pulls: its log ran silent from
`09:08:40Z` to `09:20:15Z`. A clean registry scan at 09:16 would have proved
only that registry was idle. What closes the item is *positive* post-expiry
work per service, on a credential that cannot be the original one.

**What I actually observed** (job start 08:08:07Z for loki, 08:09:34Z for
registry; identity `ttl = "1h"`, so the first credentials expired around
09:08 and 09:09):

- **loki:** 4 new objects in the `loki` bucket after 09:10:00Z —
  `09:14:52Z`, `09:18:18Z`, `09:18:24Z` and `09:18:24Z`. Writes succeeding
  past the boundary mean the SDK re-invoked the helper and got a fresh
  credential.
- **registry:** an authenticated `GET /v2/_catalog` and
  `GET /v2/embeddinggemma-q8/tags/list` both returned `200` at `09:20:15Z`,
  in 227 ms and 137 ms. Both walk S3 prefixes through the storage driver;
  distribution does not cache the catalog. Real S3 work, well past expiry.
- **Renewal on the Nomad side:** registry's `secrets/nomad_minio.jwt` mtime
  was `09:13:24Z` at read time, a second renewal after the 08:41 one cycle 2
  recorded. So the re-invoke read a renewed token, which is the composition
  that was unproven.
- **Error scan, for completeness:** zero matches for
  `NoCredentialProviders|ProcessProviderExecutionError|ExpiredToken|InvalidAccessKeyId|AccessDenied|SignatureDoesNotMatch|MissingRegion|minio-creds:`
  across both whole logs, stdout and stderr.

Record it as **closed**, citing the loki object timestamps and the registry
200s rather than the clean scan. If your scan reports only error counts, add
those two positive checks to it before you rely on it next time.

## Eval rows, checked independently

Every row I could verify read-only, I did. All hold.

| Row | Result |
|---|---|
| JWT rendered per job | `nomad alloc fs` lists `nomad_minio.jwt` in both: loki `0600` (task runs as root), registry `0644` (no `user` set). Matches the two jobspec comments. |
| No static credential reachable | `nomad job inspect` on both: zero matches for the nine env names, `accesskey`, `secretkey`, `minio.env`. |
| Helper returns usable credentials | Not re-run. The rendered helper is byte-identical to the one exercised live in cycle 2 (md5 `e9ad117978ab4a4805c4532f26e19451` in both tasks, same as cycle 2), so re-running would add nothing. |
| SDK invokes the helper, no anonymous fallback | Zero auth errors in both whole logs. |
| Real S3 work | loki: object count 10576 to 10578 during the review, 4 objects after 09:10Z. registry: two `200`s off the S3 driver at 09:20:15Z. |
| Policy grants own bucket, denies others | `mc admin policy info` for `loki` and `registry`: each is `s3:*` on `arn:aws:s3:::<own>` and `<own>/*` and nothing else. Created 08:05:18Z, three minutes before the jobs were submitted, so the `depends_on` ordering held. I did not re-create throwaway users; that is a mutating check and cycle 2 covered it. |
| Rollback paths survive | MinIO users `loki`, `registry`, `tempo` all enabled on their `_read_write` policies; `secret/default/{loki,registry,tempo}/minio` all still carry `access_key` and `secret_key`. |
| No collateral damage | tempo running and still on the minio-go route; memex running and still on its static key; nothing outside plan section 7's code surface changed. |

Also re-verified the two comment claims no gate covers: `registry.hcl:177`
is the literal `path: /secrets/htpasswd` and the only Vault render in the
file is the separate template at `:184-193`, so the rewritten config.yml
comment (R13-A2) is true; and `services.tf`'s "restoring loki means
restoring the template, the two YAML keys AND the `vault {}` block" matches
what the diff actually removed.

## Findings ledger

`.loop/scratch/R13-rollout-loki-registry-keyless-minio.adversarial/findings.json`

| id | severity | status |
|---|---|---|
| R13-A1 | medium | resolved |
| R13-A2 | low | resolved |
| R13-A3 | info | resolved — closed this cycle on post-expiry evidence |
| R13-A4 | info | accepted |
| R13-A5 | info | accepted |
| R13-A6 | low | resolved — required fix taken |
| R13-A7 | low | resolved — recommendation taken |
| R13-A8 | info | advisory, still open; the hand-off wrongly reports it fixed |
| R13-A9 | info | note, outside this diff, operator's call |
| R13-A10 | low | advisory, new — jobspec comments contradict the corrected doc |
| R13-A11 | info | note, new — split endpoint sourcing |

Nothing on that list blocks. Commit it.
