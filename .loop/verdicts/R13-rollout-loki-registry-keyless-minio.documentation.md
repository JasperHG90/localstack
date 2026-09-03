---
verdict: pass
tree: 4b57a536b3a2fc3d51b683a632e7f7ae1697743b
---

# Documentation freshness: R13 loki and registry keyless, cycle 3 (final)

No scope-binding lines. This briefing carried a tree fingerprint but no
64-hex scope digest, and the rule is to write only the digest I was given,
so the verdict falls back to the whole-tree binding, which is stricter.
The reviewed path set is the full diff against HEAD:
`.loop/ledger.json`, `deployments/applications/services.tf`,
`deployments/applications/services/loki.hcl`,
`deployments/applications/services/registry.hcl`,
`deployments/applications/storage.tf` and `docs/workload-identity.md`.

**Nothing blocks. Commit it.** Both required fixes are real fixes, not
rewordings, and both hold under independent checks against the jobspecs,
the Terraform and, for two claims, the pinned upstream sources. Three
advisories remain, all one-clause edits, none of which makes an operator
act wrongly. One of them is the heading clause your briefing reports as
dropped: it is still in the tree.

I verified the tree myself before reading anything: `git add -A` into a
throwaway `GIT_INDEX_FILE`, strip `.loop`, re-bind `.loop/config.json`,
`git write-tree` gives `4b57a536b3a2fc3d51b683a632e7f7ae1697743b`. The
real index was not touched.

## The two required fixes

**DOC-9 (image pin), resolved.** The doc now separates the pin from the
base for both jobs, and both pins match the tree.

- `docs/workload-identity.md:455` = "(`docker.io/grafana/loki:3.4.2`, built on `gcr.io/distroless/static:debug`,"
- `docs/workload-identity.md:456` = "whose busybox supplies both) and registry (`docker.io/library/registry:3.1.1`,"
- `deployments/applications/services/loki.hcl:84` = `        image = "docker.io/grafana/loki:3.4.2"`
- `deployments/applications/services/registry.hcl:81` = `        image        = "docker.io/library/registry:3.1.1"`

I went past the ledger's ask and settled the base claim upstream instead
of inheriting it from the plan. `grafana/loki` v3.4.2's `cmd/loki/Dockerfile`
ends with `FROM gcr.io/distroless/static:debug` and sets
`SHELL [ "/busybox/sh", "-c" ]`, so both halves of the sentence are true
and the busybox aside is the reason the shell exists. Registry being
Alpine-based matches the live probe recorded by the plan reviewer
(BusyBox v1.37.0, Alpine 3.23.5).

"Both run as root" also holds, for two different reasons worth knowing:
loki's image would drop to uid 10001 (the Dockerfile adds a `loki` user),
and `deployments/applications/services/loki.hcl:30` = `      user   = "root"`
is what overrides it. Registry runs as root by image default. The doc's
sentence is about the runtime, and the runtime is root in both.

**DOC-10 (only-consumer over-reach), resolved, and true under both
readings.**

- `docs/workload-identity.md:269` = "and each keeps its key provisioned as a rollback path. memex is the only one"
- `docs/workload-identity.md:270` = "of those four still using one. Other holders exist outside this set: the"

Narrow reading (the four keyed service jobs): memex still renders a static
key, at `deployments/applications/services/memex.hcl:125` =
`MEMEX_SERVER__FILE_STORE__ACCESS_KEY_ID={{ .Data.data.access_key }}`.
Tempo, loki and registry no longer do.

Plain reading (every MinIO consumer): the follow-on sentence now closes
the gap and is exact. `backup-minio` really is on the root credential, not
merely on some other key. See
`deployments/infrastructure/services/backup-minio.hcl:35`, which renders
`access_key_id` from the KV entry whose
`deployments/infrastructure/backup.tf:69` = `    access_key = "minio"` and
whose secret is `random_password.minio_secret_key.result`, the same value
`deployments/infrastructure/services/minio.hcl:85` feeds to
`MINIO_ROOT_USER`. The unconsumed keys are real too: `storage.tf` mints
them for `ducklake_reader`/`writer`, `models_reader`/`writer`, `mlflow`
and `openviking`, and no jobspec under `deployments/*/services/` names any
of those buckets.

I checked the pair is now exhaustive rather than merely better. Sweeping
every jobspec for MinIO or S3 credential use returns loki, registry,
memex, tempo, backup-minio and minio itself. Grafana, Prometheus and
HAProxy mention MinIO only as a scrape target, a dashboard or a backend.
`docs/gcs-backups.md:44` = "- `backup_minio_s3_credentials` -> `default/backup-minio/minio` (copies root MinIO creds)"
says the same thing from the other side, so the two docs agree.

The rollback-path clause holds as well:
`deployments/applications/secrets.tf:42` =
`resource "vault_kv_secret_v2" "loki_minio_credentials" {` and its tempo
and registry siblings at lines 53 and 104 are all still there, and
`deployments/applications/storage.tf:19` still carries
`{ "name" = "loki", generate_access_key = true }`.

## Did the five edits break anything

No. I re-read the whole rewritten passage rather than the diff hunks,
since the file has now been rewritten by R9 and twice by R13.

The `silently` removal is the right call and now agrees with the rest of
the file. `docs/workload-identity.md:419` = "loudly:" matches item 2's own
failure mode fourteen lines down (`NoCredentialProviders` when
`AWS_CONFIG_FILE` is omitted) and matches the route split at 326-330.
Item 4 also fails loudly, so the superlative "the one that breaks
everything" is emphasis rather than an exclusive claim, and it does not
contradict anything.

The path fix at `docs/workload-identity.md:437` = "   destination is
alloc-relative and `AWS_CONFIG_FILE` is the in-container" is correct and
matches both jobspecs.

Every backticked identifier, env var, path and error string in the changed
regions resolves. The three env vars and their values match the `env`
blocks in both jobspecs exactly; `local/minio-creds.sh` with
`perms = "0755"` and `local/aws-config` under `[default]` match both
template stanzas; the six minio-go names and the three added AWS names are
the real provider names; `ProcessProviderExecutionError`,
`NoCredentialProviders` and `WebIdentityErr: role ARN is not set` are real
SDK strings; `AWS_WEB_IDENTITY_TOKEN_FILE` is indeed what
`deployments/applications/services/tempo.hcl:72` sets, which is what makes
the copy-from-tempo trap real; the policy names `loki` and `registry` in
`storage.tf` match the job ids in the two jobspecs, which is what claim
mode needs.

Repo doc rules on the changed lines are clean: no line over 80 columns
(the only long lines in the file are pre-existing command lines), zero em
dashes in the changed regions (the file's one em dash is at line 194, from
an earlier ticket), no smart quotes, no semicolon splices, no tier 1 slop,
no British spellings. `.pre-commit-config.yaml` defines no markdown hook,
so no gate covers this surface. `nomad fmt -check -recursive` and
`terraform -chdir=deployments/applications fmt -check -recursive` both
exit 0, and all five changed files end in a newline, so the two mutating
hooks have nothing to mutate.

No other doc goes stale. loki dropping its `vault {}` block stales
nothing, because no doc documented loki as a Vault consumer:
`docs/monitoring.md`, `docs/haproxy_reverse_proxy.md`,
`docs/observability-python.md` and `docs/vault-human-auth.md` mention loki
only as an endpoint, a datasource or a host volume.
`docs/credential-rotation.md` names no MinIO credential.
`docs/notes/audit/plan-premise-sweep-2026-07.md` is a dated historical
audit, which the repo's own rules say not to rewrite.

## Advisories, none blocking

**A1, the heading clause is still there.** Your briefing says "and the two
are opposites" was dropped. It was not:
`docs/workload-identity.md:318` = "   the two symptoms are opposites.** Exchanging by hand with `curl`, the".
The passage it introduces now covers three routes and four error strings,
and the `credential_process` symptom is loud like the curl one rather than
its opposite. I am holding the severity I gave it in cycle 2: the bold
paragraph three lines down at 322-330 gives the correct breakdown, so no
operator acts wrongly, and re-attacking my own finding does not mean
escalating an unchanged line just because it went unfixed. The fix is to
end that sentence at "depends on how you reach MinIO."

**A2, the same false wording survives in the two jobspec comments the doc
sentence came from.**
`deployments/applications/services/loki.hcl:133` = `      ### must stay identical.`
and `deployments/applications/services/registry.hcl:122` = `      ### must stay identical.`
The destination is `local/aws-config` and `AWS_CONFIG_FILE` is
`/local/aws-config`. The correct literals sit three lines either side, so a
copying reader is fine. Worth folding into the same follow-up as A1.

**A3, the section intro still names one route.**
`docs/workload-identity.md:296` = "**To give a new job keyless access**, two things must line up. A job whose"
introduces tempo as the only elaboration, and a reader meets the second
route 100 lines later. Nothing there is false, and the diff added forward
pointers at 326-330 and 395-396, so this is a signpost, not a correction.
Sibling of the cycle-2 advisory about the two four-item lists (DOC-12),
which is unchanged and still non-blocking.

**Carried, unchanged:** DOC-7 (no blank line between the two templates,
now `loki.hcl:140-141`, `nomad fmt -check` does not care) and DOC-6
(duplicated SDK comment block, still declined: the blocks differ in their
last lines and a jobspec comment is read where the jobspec is edited).

## Your question about the third advisory

Follow-up, not this cycle. But it is now settled rather than asserted, so
the follow-up is cheap. At loki's own pinned SDK version, aws-sdk-go
v1.55.6, `aws/credentials/processcreds/provider.go` rejects an empty
`AccessKeyID` (line 272) and an empty `SecretAccessKey` (line 279) with
`ProcessProviderRequiredError`, and applies no check at all to
`SessionToken` or `Expiration`. So `docs/workload-identity.md:450` =
"loudly rather than emitting a half-document: an empty field would
otherwise" is right for two of the four fields and wrong for the other
two.

The interesting half is the one the doc misses. When `Expiration` is
absent the provider sets `staticCreds = true` (line 287) and the SDK never
re-runs the helper, so the hour-long credential simply stops working and
is never refreshed. That is a worse failure than blank credentials and it
is exactly what the helper's guard on `ex` prevents. A better rationale
for that sentence: the SDK rejects an empty `AccessKeyId` or
`SecretAccessKey` itself, but an empty `SessionToken` passes straight
through, and a missing `Expiration` makes the SDK treat the credential as
static and never refresh it.

The guard in both jobspecs already covers all four fields, so no code
changes. Only the stated reason would.

## Ledger

Updated at
`.loop/scratch/R13-rollout-loki-registry-keyless-minio.documentation/findings.json`:
DOC-9, DOC-10 and DOC-11 closed as resolved with this cycle's evidence,
DOC-13 refined with the SDK line numbers, DOC-6, DOC-7, DOC-12 and DOC-15
carried with absence claims, and DOC-16 (A1), DOC-17 (A2) and DOC-18 (A3)
added.
