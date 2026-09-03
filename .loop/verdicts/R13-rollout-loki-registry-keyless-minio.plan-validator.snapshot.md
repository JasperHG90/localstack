---
epic = "rollout"
depends_on = ["R9-rollout-tempo-keyless-minio"]
priority = 18
summary = "Move loki and registry off their static MinIO keys in one change, using an AWS credential_process helper that performs the STS exchange itself. Supersedes R10 and R11: one mechanism serves both, and loki keeps its existing storage client."
premise = { Q1 = "Both images ship /bin/sh and wget and run as root, and both services build their S3 session with session.NewSession, so an AWS credential_process helper reached through AWS_SDK_LOAD_CONFIG serves both" }
measured_against = { Q1 = { kind = "package", version = "loki v3.4.2 / distribution v3.1.1 / aws-sdk-go v1.55.x", ref = "live nomad alloc exec on both allocs, 2026-09-03; s3_storage_client.go L227-231,282; s3-aws/s3.go L461,492" } }
---

# Ticket: R13-rollout-loki-registry-keyless-minio

## 1. Title

Move loki and registry off their static MinIO keys with one shared
credential_process helper, so the last two service consumers hold no key.

## 2. Size / Effort

**Medium.** Two jobs, one new mechanism, no code and no image rebuild. The
effort is the helper script and its two wirings, not the per-service work:
once the helper exists, each job is an identity block, three env vars, two
templates and two deletions.

## 3. Triggered by

R9 made tempo keyless and proved the mechanism. loki and registry are the
remaining service consumers of a static MinIO key. The operator asked for
both in one change.

## 4. Context

Both jobs render a long-lived MinIO key from Vault today:

- `deployments/applications/services/loki.hcl:65-74` — a `template` writing
  `MINIO_ACCESS_KEY` / `MINIO_SECRET_KEY` to `secrets/minio.env`, consumed
  at `loki.hcl:121-122` as `access_key_id` / `secret_access_key`.
- `deployments/applications/services/loki.hcl:32` — `vault {}`. The MinIO
  secret is loki's ONLY Vault use, so the block goes with it.
- `deployments/applications/services/registry.hcl:78-81` — the same shape,
  rendered inline into `secrets/config.yml` as `accesskey` / `secretkey`.
- `deployments/applications/services/registry.hcl:113-120` — registry has a
  SECOND Vault use, `registry_auth_secret` for its htpasswd, so registry
  KEEPS `vault {}` where loki loses it.
- `deployments/applications/services.tf:229-234` and `:260-...` — the two
  `nomad_job` resources passing those secret paths.

R9's mechanism is already live: MinIO's `NOMAD` OIDC target runs in claim
mode, applying the policy NAMED by the JWT's `nomad_job_id` claim. Policies
named `loki` and `registry` do not exist; `loki_read_write` and
`registry_read_write` are different strings and do not match.

**Why this is not R9 repeated.** Tempo reaches MinIO through minio-go,
which has a web-identity provider with a settable STS endpoint. Neither of
these does. Both use aws-sdk-go v1, which has no environment variable for
pointing STS at a non-AWS endpoint. The route that does work for both is
`credential_process`: the SDK invokes an external command, the command
performs the exchange itself, and the SDK re-invokes it when the returned
credentials expire.

This supersedes R10 and R11, which assumed two different mechanisms. It
also retires R10's central risk: R10 proposed switching loki to
`use_thanos_objstore`, which would swap loki's entire storage client and
put existing log data in question. The helper leaves loki's client alone.

## 5. Non-goals / out of scope

- Removing either static key. Both MinIO users, their access keys and their
  Vault KV entries STAY as the rollback path, exactly as R9 left tempo's.
- memex. Dropped by the operator (R12); its fix needs application changes
  in another repo.
- Changing MinIO's OIDC configuration. R9 and M1 own it; it needs no edit.
- Promoting the per-job policy convention into
  `deployments/applications/modules/bucket/`. Three consumers may justify
  it later; this ticket does not do it.
- Registry's htpasswd path. Untouched, and registry keeps `vault {}` for it.

## 6. Requirements & restrictions

- R1. Each job obtains MinIO credentials by exchanging its Workload Identity
  JWT, holding no static key. Named identity block per
  `docs/workload-identity.md:169-176`: `name`, `aud`, `file`, pinned
  `filepath`, `ttl`, and `change_mode = "noop"`.
- R2. `aud = ["minio"]` for both, matching
  `MINIO_IDENTITY_OPENID_CLIENT_ID_NOMAD`. No new audience: the registry at
  `docs/workload-identity.md:216` already assigns `minio` to this verifier,
  and the rule above it forbids a per-job audience.
- R3. A `minio_iam_policy` named exactly `loki` and one named exactly
  `registry`, each scoped to its own bucket by plain string, mirroring
  `minio_iam_policy.tempo_wi` in `deployments/applications/storage.tf`.
- R4. **Every static credential source removed per job, and NINE names must
  be absent, not eight.** `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, the
  legacy `AWS_ACCESS_KEY` / `AWS_SECRET_KEY`, `MINIO_ROOT_USER`,
  `MINIO_ROOT_PASSWORD`, `MINIO_ACCESS_KEY`, `MINIO_SECRET_KEY`, and
  `AWS_WEB_IDENTITY_TOKEN_FILE`.
  The ninth is the dangerous one, because it is the variable the implementer
  is most likely to copy: tempo sets it at
  `deployments/applications/services/tempo.hcl:72`, and
  `credentials.go` lines 50-53 checks it BEFORE the shared-config profile. Probe:
  with `credential_process` otherwise wired correctly, setting it fails
  session creation outright with `WebIdentityErr: role ARN is not set`, and
  adding `AWS_ROLE_ARN` fails differently rather than working. tempo's
  wiring must NOT be copied into these two jobs.
  The reasons differ by group and the distinction matters. The four `AWS_*`
  names pre-empt `credential_process` because aws-sdk-go resolves the
  environment first. The four `MINIO_*` names are not read by aws-sdk-go at
  all: `MINIO_ACCESS_KEY` matters because loki interpolates it into its own
  config under `-config.expand-env=true`
  (`deployments/applications/services/loki.hcl:121`), and `MINIO_ROOT_*`
  goes for hygiene.
  Registry's static credential is NOT an env var at all. It is the two YAML
  lines at `deployments/applications/services/registry.hcl:79-80`, so
  checking only the nine names would pass a registry that never changed.
- R5. **Three env vars per task, all required, named here rather than
  counted:** `AWS_SDK_LOAD_CONFIG=1`, `AWS_CONFIG_FILE=/local/aws-config`,
  and `AWS_REGION=us-east-1`.
  `AWS_SDK_LOAD_CONFIG` does NOT make `credential_process` work;
  `shared_config.go` line 453 parses that key outside the extended-options
  guard, so it is read from whatever files are in the list. What the env
  var decides is whether the CONFIG file joins the CREDENTIALS file in that
  list (`session.go` lines 476-481). Because this ticket puts the directive in a
  config file, the var is required for THIS placement.
  `AWS_CONFIG_FILE` is required and is the fix that makes the difference
  between working and dead: unset, the SDK reads `$HOME/.aws/config`, and
  `HOME=/root` in both containers with no such file. Probe: with the file
  at `/local/aws-config` and only `AWS_SDK_LOAD_CONFIG=1` the SDK returns
  `NoCredentialProviders`; adding `AWS_CONFIG_FILE=/local/aws-config`
  returns `ProcessProvider`.
  The failure when this is wrong is LOUD, not silent: the SDK installs a
  chain that errors with `NoCredentialProviders` rather than an anonymous
  signer (`session.go` line 815). Do not look for anonymous requests.
- R6. **The helper's contract, which the SDK imposes and the author does not
  get to choose.** It writes ONLY the credential JSON to stdout and keeps no
  state; the document MUST carry `"Version":1` or the SDK rejects it with
  `ProcessProviderVersionError`; stdout is capped at 8 KiB and the run at
  60 s (`processcreds/provider.go` lines 146-149); it is invoked through `sh -c`
  (`provider.go` line 316), which resolves because both task PATHs carry `/bin`;
  and a non-zero exit surfaces as `ProcessProviderExecutionError`, so it
  must exit non-zero only when it means to fail. It must also handle
  busybox `wget` DISCARDING the response body on any non-2xx from STS while
  printing it on 200, so an STS rejection arrives as an empty body plus a
  non-zero return rather than as a parseable error document.
- R7. Existing consumers stay untouched (CLAUDE.md section 3). tempo keeps
  its R9 wiring; memex keeps its key.

## 7. Code surface

- `deployments/applications/services/loki.hcl:28-32` — add the named
  `identity` block (R1, R2) and an `env` block carrying exactly
  `AWS_SDK_LOAD_CONFIG=1`, `AWS_CONFIG_FILE=/local/aws-config` and
  `AWS_REGION=us-east-1` (R5), and NOT `AWS_WEB_IDENTITY_TOKEN_FILE` (R4);
  DELETE `vault {}` (line 32), dead once the template goes.
- `deployments/applications/services/loki.hcl:65-74` — DELETE the
  `secrets/minio.env` template (R4).
- `deployments/applications/services/loki.hcl:118-123` — DELETE
  `access_key_id` and `secret_access_key` from the s3 config. Loki sets
  static credentials only when BOTH are non-empty
  (`s3_storage_client.go` lines 227-231), so removing both is what reaches
  the chain.
- `deployments/applications/services/loki.hcl` — add two templates: the
  helper at `local/minio-creds.sh` with `perms = "0755"` honoring R6's
  contract, and `local/aws-config` naming it as `credential_process` under
  a `[default]` profile. The path in `AWS_CONFIG_FILE` and the template's
  destination must match exactly.
- `deployments/applications/services/registry.hcl:30-34` — add the named
  `identity` block (R1, R2) and the same three-variable `env` block as loki
  (R5), again without `AWS_WEB_IDENTITY_TOKEN_FILE` (R4). KEEP `vault {}`:
  the htpasswd at `:113-120` still needs it.
- `deployments/applications/services/registry.hcl:78-81` — DELETE the
  `accesskey` / `secretkey` lines from the rendered config (R4).
- `deployments/applications/services/registry.hcl` — the same two
  templates as loki.
- `deployments/applications/services.tf:229-234` — drop `loki_minio_secret`
  from `nomad_job.loki` and add `depends_on` on the new loki policy (R3).
- `deployments/applications/services.tf` — the `nomad_job.registry`
  resource: drop `registry_minio_secret`, keep `registry_auth_secret`, add
  `depends_on` on the new registry policy.
- `deployments/applications/storage.tf` — two `minio_iam_policy` resources
  named `loki` and `registry` (R3), beside `minio_iam_policy.tempo_wi`.
- `docs/workload-identity.md` — the "Keyless MinIO access" section. Its
  worked example covers only the minio-go route; this ticket adds a second
  supported route, and the "still keyed" enumeration changes again. R9's
  documentation review required this file be declared, and the same reason
  applies here.
- `.loop/evals/R13-rollout-loki-registry-keyless-minio.md` — the eval
  marker, home of every scored check in section 8. R1, R2, R5 and R6 are
  each asserted by a row there: R1 and R2 by E1, R5 and R6 by E3, and R7 by
  E7.

## 8. Tests & validation gates

### Repo gate (loop-enforced)

`just pre_commit` (`.loop/config.json` `gates`): `nomad-fmt`,
`terraform fmt -check -recursive`, and `scripts/tf_validate.sh` across all
three roots. No unit-test harness and no CI, so this plus the live evals
below are the whole check surface.

**Worktree precondition.** `just worktree_setup <path>` first, or terraform
has no `prod.tfvars` in either root.

### Evals (live cluster)

Scored rows live in `.loop/evals/R13-rollout-loki-registry-keyless-minio.md`.

- E1 — both jobs run with a rendered WI JWT. `nomad job status` healthy for
  each, and `nomad alloc fs <alloc> <task>/secrets` lists
  `nomad_minio.jwt`.
- E2 — no static credential reachable, per job. `nomad job inspect` contains
  none of R4's eight names, and no `minio.env` is rendered. This is the row
  that catches the silent-fallback failure.
- E3 — the helper actually runs and returns credentials. Executed inside
  each container (both ship `/bin/sh` and `wget`), the helper prints JSON
  carrying `AccessKeyId`, `SecretAccessKey`, `SessionToken` and an
  `Expiration` about an hour out.
- E4 — each service reaches its bucket through the helper. loki: a fresh
  object appears under the `loki` bucket after the cutover, and its logs
  carry no `AccessDenied`. registry: an image pull or `mc ls` against the
  `registry` bucket succeeds, and its logs carry no S3 auth error.
- E5 — per-job scoping enforced. A throwaway MinIO user bound to only the
  `loki` policy lists `loki` and is denied `tempo` and `registry`; the same
  for the `registry` policy, denied on `loki`. Deleted afterwards. This is
  R9's E4 method, which proved MinIO enforces the document.
- E6 — guardrail, rollback paths intact. Both MinIO users, both access keys
  and both Vault KV entries still exist.
- E7 — guardrail, no collateral damage. tempo still runs keyless and its
  bucket still receives writes; memex still runs on its static key.

## 9. Risk assessment

- Blast radius, and it is the highest of this epic. Loki holds every
  service's logs, and a broken registry blocks any image pull not already
  cached, including the recovery path. Neither is on a request path for
  user traffic, but losing the registry mid-incident would hurt.
- Reversibility: high and deliberately preserved. Both static keys stay
  provisioned (non-goal 1), so restoring the deleted template, the config
  keys and the templatefile variable returns either job to its key with one
  apply. **Loki's rollback must also restore its `vault {}` block**, which
  this ticket deletes and without which the restored template cannot read
  the secret. Leaving `AWS_SDK_LOAD_CONFIG` set does not interfere: the SDK
  skips resolution entirely when the caller supplies credentials
  (`session.go` line 815).
- Sequence the two jobs, do not apply both at once. Registry second, so a
  mistake on loki does not also cost the ability to pull images.
- Likeliest failure modes, all quiet: (a) a credential env var left set, so
  the SDK resolves it before the shared config and nothing changed (R4,
  caught by E2); (b) `AWS_CONFIG_FILE` unset or pointing elsewhere, or
  `AWS_SDK_LOAD_CONFIG` unset, so the config file is never read and the
  helper never runs. This does NOT go anonymous: the SDK returns
  `NoCredentialProviders` and the request fails loudly (R5);
  (c) no job-id-named policy, which through a client library surfaces as a
  plain `AccessDenied` rather than a policy error, per
  `docs/workload-identity.md`'s two-symptom warning; (d) the helper failing
  at runtime, which the SDK reports as a credential error rather than
  naming the script.

## 10. Subtickets

1. **Add both policies** (`storage.tf`) and apply. Safe first: a policy
   nothing references grants nothing.
2. **Cut loki over** and apply. Verify E1-E4 for loki before touching
   registry.
3. **Cut registry over** and apply. Verify E1-E4 for registry.
4. **Verify E5-E7** and record outcomes.

## 11. Open questions

- Q1. **Which mechanism — resolved.** `credential_process` for both, not
  thanos for loki and something else for registry. Verified live: both
  containers ship `/bin/sh` and `wget` and run as uid 0, so both can run
  the helper and read their JWT. This keeps loki's storage client
  untouched, which is why R10's thanos route is abandoned rather than
  deferred.
- Q2. **Whether to supersede R10 and R11 — resolved: yes.** They assumed
  two mechanisms and one of them carried a data-loss risk this approach
  removes. Drop both with a reason naming this ticket.
- Q3. **One ticket or two.** The operator asked for both in one change, and
  the helper is shared, so one ticket. The subticket order still applies
  the two jobs separately, so a failure on loki stops before registry.
- Q5. **How the STS XML is parsed with busybox tooling.** The response is a
  single unindented line, so the helper anchors on tag names with `sed`
  rather than on line structure. Recommendation: verify the extraction
  inside each container before relying on it, since busybox `sed` is not
  GNU `sed`; a parse that silently yields an empty field would reach the SDK
  as valid JSON with blank credentials.
- Q6. **What `DurationSeconds` to request.** The identity `ttl` is `1h` and
  MinIO bounds the session by the JWT's remaining life, so a longer request
  cannot extend it and a shorter one only increases helper invocations.
  Recommendation: request nothing and take MinIO's default, which R9 showed
  is bounded by the token; revisit only if the SDK re-invokes more often
  than expected.
- Q7. **A sidecar alternative, surfaced not chosen.**
  `AWS_CONTAINER_CREDENTIALS_FULL_URI` would move the exchange to a sidecar
  and need no shell in either image, which would also survive a future
  distroless image losing busybox. Recommendation: stay with
  `credential_process` for this ticket, since both images demonstrably have
  a shell today, and record this as the fallback if that stops being true.
- Q4. **Where the helper lives.** A Nomad `template` rendering it into
  `local/` per job, rather than baking it into an image. No image rebuild,
  and it stays readable in the jobspec. The cost is the script existing
  twice; if a third consumer appears, promote it to a shared file read by
  `templatefile`.

## Premises / assumptions

- **P1 — Both containers can run a shell helper and read their JWT.**
  Probe: `nomad alloc exec` against both live allocations, 2026-09-03. Loki
  returned `sh:ok`, `/busybox/wget`, `uid=0(root)`; registry returned
  `sh:ok`, `/usr/bin/wget`, `uid=0(root)`. The images probed are the ones
  pinned at `deployments/applications/services/loki.hcl:51` and
  `deployments/applications/services/registry.hcl:53`. Loki's is
  `gcr.io/distroless/static:debug`, whose busybox supplies both. Loki also
  sets `user = "root"` at `deployments/applications/services/loki.hcl:30`,
  so the documented non-root JWT hazard does not apply.
- **P2 — aws-sdk-go v1.55.x supports `credential_process`.** Probe: an
  HTTP fetch of `aws/credentials/processcreds/provider.go` at tag `v1.55.5`
  returned 200, so the package exists. Both services vendor that major
  version (loki `v1.55.6`, distribution `v1.55.5`, each from its `go.mod`),
  at the image pins cited in P1
  (`deployments/applications/services/loki.hcl:51`,
  `deployments/applications/services/registry.hcl:53`).
- **P3 — Both fall through to the credential chain when static keys are
  omitted.** Probe: source fetched at each pinned tag. Loki calls
  `WithCredentials` only inside a both-non-empty branch
  (`s3_storage_client.go` lines 227-231) and otherwise never sets
  credentials; registry builds static credentials only in the same shape
  (`s3-aws/s3.go` line 461) and its driver documents omitting the keys to
  use IAM credentials. The keys this ticket deletes are the ones at
  `deployments/applications/services/loki.hcl:121-122` and
  `deployments/applications/services/registry.hcl:79-80`.
- **P4 — `AWS_SDK_LOAD_CONFIG` is required, not optional.** Probe: source
  fetched at each pinned tag shows both building the session with plain
  `session.NewSession` (`s3_storage_client.go` line 282, `s3-aws/s3.go`
  line 492), which performs no shared-CONFIG profile resolution on its own,
  and `credential_process` is a shared-config key. Applies to the jobs at
  `deployments/applications/services/loki.hcl:51` and
  `deployments/applications/services/registry.hcl:53`.
- **P5 — MinIO's `NOMAD` target is in claim mode and expects a policy named
  for the job id.** Anchor:
  `deployments/infrastructure/services/minio.hcl:90` sets
  `MINIO_IDENTITY_OPENID_CLAIM_NAME_NOMAD="nomad_job_id"`. R9 proved the
  whole path end to end for tempo; see
  `.loop/reflections/R9-rollout-tempo-keyless-minio.md`.
- **P6 — Neither policy name exists yet.** The bucket module emits only
  `<bucket>_read_write` and `_read_only`
  (`deployments/applications/modules/bucket/main.tf:12`), and `mc admin
  policy ls` shows `tempo` as the only job-id-named policy.
- **P7 — registry keeps Vault, loki does not.** `registry.hcl:113-120`
  renders an htpasswd from `registry_auth_secret`, a second Vault use;
  grep of `loki.hcl` shows the MinIO secret as its only one.
