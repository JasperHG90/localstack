---
verdict: pass-with-required-fixes
plan: 0cd29a84ba48ca7c72b001ea54e59f9e62998fa82df414e4388c7a5d08645e11
bound_paths: front-matter, 5, 6, 7, 8, 9, 10, premises
scope: 7cfeca871f8e87974f50a990e2b50a05ce1fcd0d232ad7208ac65e1965e17d1d
fix_sections: front-matter, 6, 7, 8, 9, premises
citations:
deployments/applications/services/loki.hcl:30 =       user   = "root"
deployments/applications/services/loki.hcl:32 =       vault {}
deployments/applications/services/loki.hcl:51 =         image = "docker.io/grafana/loki:3.4.2"
deployments/applications/services/loki.hcl:68 =         MINIO_ACCESS_KEY="{{ .Data.data.access_key }}"
deployments/applications/services/loki.hcl:121 =             access_key_id: $${MINIO_ACCESS_KEY}
deployments/applications/services/loki.hcl:122 =             secret_access_key: $${MINIO_SECRET_KEY}
deployments/applications/services/registry.hcl:34 =       vault {}
deployments/applications/services/registry.hcl:53 =         image        = "docker.io/library/registry:3.1.1"
deployments/applications/services/registry.hcl:79 =             accesskey: {{ .Data.data.access_key }}
deployments/applications/services/registry.hcl:80 =             secretkey: {{ .Data.data.secret_key }}
deployments/applications/services/registry.hcl:115 =         {{- with secret "${registry_auth_secret}" }}
deployments/applications/services/tempo.hcl:72 =         AWS_WEB_IDENTITY_TOKEN_FILE = "/secrets/nomad_minio.jwt"
deployments/applications/services.tf:229 = resource "nomad_job" "loki" {
deployments/applications/services.tf:232 =     { loki_minio_secret = vault_kv_secret_v2.loki_minio_credentials.path }
deployments/applications/services.tf:271 = resource "nomad_job" "registry" {
deployments/applications/storage.tf:104 = resource "minio_iam_policy" "tempo_wi" {
deployments/applications/modules/bucket/main.tf:12 =   name   = "${local.name_underscore}_read_write"
deployments/infrastructure/services/minio.hcl:90 =         MINIO_IDENTITY_OPENID_CLAIM_NAME_NOMAD="nomad_job_id"
docs/workload-identity.md:169 = identity {
docs/workload-identity.md:216 = | `minio` | MinIO STS, `NOMAD` target | M1 |
scripts/tf_validate.sh:8 = roots=(
scripts/tf_validate.sh:12 = )
.loop/config.json:3 =     "just pre_commit"
.pre-commit-config.yaml:66 =       - id: pytest
---

rebound-by: JasperHG90 2026-09-03T08:01:14Z (reason: applied all six required fixes from the plan-validator verdict: AWS_CONFIG_FILE required and named, AWS_WEB_IDENTITY_TOKEN_FILE added to the forbidden list with corrected rationale, registry's YAML keys covered, the helper contract stated, the anonymous-fallback symptom corrected to NoCredentialProviders, and loki's vault block added to the rollback recipe)

# Plan review: R13-rollout-loki-registry-keyless-minio

## Deterministic floor

`loopctl verify-plan R13-rollout-loki-registry-keyless-minio` returned
`valid` with one provenance warning, no hard-fail. Proceeded to
falsification.

## Premise verdict

**PARTIALLY SOUND.**

The mechanism works. I demonstrated `credential_process` resolving under
aws-sdk-go v1.55.5 against a real build, and both live containers can run
the helper. But the plan's requirement set is not the requirement set that
makes it work: as literally written, §6 and §7 produce a job that resolves
no credentials at all. Four premises hold outright, one holds with a
correction, one breaks as written, and the plan's stated failure symptom is
wrong in three places.

## Per-assumption findings

### P1 — HOLDS. Both containers can run a shell helper and read their JWT.

`deployments/applications/services/loki.hcl:51`
> `        image = "docker.io/grafana/loki:3.4.2"`

`deployments/applications/services/registry.hcl:53`
> `        image        = "docker.io/library/registry:3.1.1"`

`deployments/applications/services/loki.hcl:30`
> `      user   = "root"`

Live `nomad alloc exec` against alloc `31577689` (loki) and `5e7f40cb`
(registry), 2026-09-03, re-running the author's probe:

```
loki:     uid=0(root) gid=0(root)   HOME=/root   /bin/sh   /busybox/wget
          BusyBox v1.36.1 ... --post-data STR  Send STR using POST method
          sed=/busybox/sed grep=/busybox/grep awk=/busybox/awk
registry: uid=0(root) gid=0(root)   HOME=/root   /bin/sh   /usr/bin/wget
          BusyBox v1.37.0   Alpine 3.23.5
          sed=/bin/sed grep=/bin/grep awk=/usr/bin/awk
```

The operator's specific worry is answered: loki's busybox wget DOES carry
`--post-data`, and it reached MinIO's STS endpoint from inside the
container. Posting a dummy token to `http://192.168.2.29:9000/` returned
`HTTP/1.1 400 Bad Request`, so the network path and the POST both work.

Two additions the plan does not record, both load-bearing for the helper.
First, `sh` must be found by `exec.LookPath` in the SERVICE process, not in
the exec session; from `/proc/1/environ` inside each container:

```
loki:     PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:/busybox
registry: PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
```

Both carry `/bin`, so `sh -c` resolves. Second, busybox wget DISCARDS the
response body on a non-2xx status: the 400 above printed nothing on stdout
and exited 1, while `wget -q -O - http://127.0.0.1:3100/ready` printed
`ready` and exited 0. The helper gets the body on success and nothing at
all on an STS error.

One correction to the premise's wording, immaterial to the conclusion: the
plan calls loki's image `gcr.io/distroless/static:debug`. The jobspec pins
`docker.io/grafana/loki:3.4.2`; distroless is its base, not the pin.

### P2 — HOLDS. aws-sdk-go v1.55.x supports `credential_process`.

Confirmed at both pinned tags rather than by a 200 on a file fetch.
`https://raw.githubusercontent.com/grafana/loki/v3.4.2/go.mod:23`
> `	github.com/aws/aws-sdk-go v1.55.6`

`https://raw.githubusercontent.com/distribution/distribution/v3.1.1/go.mod:12`
> `	github.com/aws/aws-sdk-go v1.55.5`

Demonstrated, not inferred. Scratch at
`.loop/scratch/R13-rollout-loki-registry-keyless-minio.plan-validator/p4/`
built a Go program against `aws-sdk-go v1.55.5` calling plain
`session.NewSession` and printing the resolved provider, run in
`golang:1.23` under docker. Captured stdout:

```
### CASE B: credential_process in AWS_CONFIG_FILE, AWS_SDK_LOAD_CONFIG=1
CREDS_OK provider="ProcessProvider" ak="PROCKEY" token="PROCTOKEN"
```

### P3 — HOLDS. Both fall through when static keys are omitted.

Loki, `https://raw.githubusercontent.com/grafana/loki/v3.4.2/pkg/storage/chunk/client/aws/s3_storage_client.go:227-230`
> ```
> 	if cfg.AccessKeyID != "" && cfg.SecretAccessKey.String() != "" {
> 		creds := credentials.NewStaticCredentials(cfg.AccessKeyID, cfg.SecretAccessKey.String(), cfg.SessionToken.String())
> 		s3Config = s3Config.WithCredentials(creds)
> 	}
> ```

`grep -n "credentials\.\|WithCredentials\|SharedConfig\|session\." ` over
that whole file returns only lines 228, 229 and 282, so there is no second
credential path. `cfg.S3.URL` is nil for this config (the jobspec uses
`endpoint:`), so the URL-userinfo branch at line 194 never runs.

Registry, `https://raw.githubusercontent.com/distribution/distribution/v3.1.1/registry/storage/driver/s3-aws/s3.go:460-467`
> ```
> 	if params.AccessKey != "" && params.SecretKey != "" {
> 		creds := credentials.NewStaticCredentials(
> 			params.AccessKey,
> 			params.SecretKey,
> 			params.SessionToken,
> 		)
> 		awsConfig.WithCredentials(creds)
> 	}
> ```

Same file, lines 189-191, confirms the plan's "the driver documents
omitting the keys":
> ```
> 	// Providing no values for these is valid in case the user is authenticating
> 	// with an IAM on an ec2 instance (in which case the instance credentials will
> 	// be summoned when GetAuth is called)
> ```

The keys the ticket deletes are the right ones:

`deployments/applications/services/loki.hcl:121`
> `            access_key_id: $${MINIO_ACCESS_KEY}`

`deployments/applications/services/registry.hcl:79`
> `            accesskey: {{ .Data.data.access_key }}`

Note for the implementer, from the same loki file at lines 222-224:
supplying ONE of the pair is a hard error (`must supply both an Access Key
ID and Secret Access Key or neither`), so §7's "delete both" is not
optional.

### P4 — BREAKS as written. `AWS_SDK_LOAD_CONFIG` is not unconditionally required.

`https://raw.githubusercontent.com/aws/aws-sdk-go/v1.55.5/aws/session/session.go:476-481`
> ```
> 		cfgFiles = []string{envCfg.SharedConfigFile, envCfg.SharedCredentialsFile}
> 		if !envCfg.EnableSharedConfig {
> 			// The shared config file (~/.aws/config) is only loaded if instructed
> 			// to load via the envConfig.EnableSharedConfig (AWS_SDK_LOAD_CONFIG).
> 			cfgFiles = cfgFiles[1:]
> 		}
> ```

`.../aws/session/shared_config.go:453`, which sits OUTSIDE the `if exOpts`
block that ends at line 451:
> `	updateString(&cfg.CredentialProcess, section, credentialProcessKey)`

So `credential_process` is parsed from whatever files are in `cfgFiles`
regardless of `AWS_SDK_LOAD_CONFIG`, and the env var only decides whether
the CONFIG file joins the CREDENTIALS file in that list. Demonstrated:

```
### CASE A: credential_process in AWS_CONFIG_FILE, AWS_SDK_LOAD_CONFIG unset
CREDS_ERR: NoCredentialProviders: no valid providers in chain. Deprecated.

### CASE B: credential_process in AWS_CONFIG_FILE, AWS_SDK_LOAD_CONFIG=1
CREDS_OK provider="ProcessProvider" ak="PROCKEY" token="PROCTOKEN"

### CASE C: credential_process in AWS_SHARED_CREDENTIALS_FILE, AWS_SDK_LOAD_CONFIG unset
CREDS_OK provider="ProcessProvider" ak="PROCKEY" token="PROCTOKEN"
```

The operator's own framing settles the severity: CASE C is the "R5 is
over-strict but harmless" branch, not the "whole ticket is broken" branch.
The plan's chosen placement is the config file, and for that placement R5
is exactly right. The premise sentence, however, is false as stated, and a
reader who trusts it will believe the env var is what makes
`credential_process` work at all. Reword rather than drop.

### P4a — BREAKS, and this is the one that stops the plan working. `AWS_CONFIG_FILE` is required and unstated.

§7 says loki and registry each gain "`local/aws-config` naming it as
`credential_process`". Nothing in §6 or §7 points the SDK at that file.
Unpointed, the SDK reads `$HOME/.aws/config`, and `HOME=/root` in both live
containers (P1 probe), where no such file exists. Demonstrated:

```
### CASE H: plan as literally written -- file rendered at /local/aws-config,
###         only AWS_SDK_LOAD_CONFIG=1, no AWS_CONFIG_FILE
CREDS_ERR: NoCredentialProviders: no valid providers in chain. Deprecated.

### CASE I: same file, plus AWS_CONFIG_FILE=/local/aws-config
CREDS_OK provider="ProcessProvider" ak="PROCKEY" token="PROCTOKEN"
```

§2 says "three env vars" per job but never names them, so the shortfall is
plausibly a drafting omission rather than a design error. It is still the
difference between a working ticket and a dead one, and §6 is the section
an implementer builds from.

### P5 — HOLDS. MinIO's `NOMAD` target is in claim mode on the job id.

`deployments/infrastructure/services/minio.hcl:90`
> `        MINIO_IDENTITY_OPENID_CLAIM_NAME_NOMAD="nomad_job_id"`

Live corroboration that R9's path is running: `nomad alloc fs 0240b708
tempo/secrets/` lists `nomad_minio.jwt`, 886 B, mode `-rw-------`,
modified `2026-09-03T09:00:35+02:00`, so the JWT is being rendered and
rotated on tempo now.

### P6 — HOLDS. Neither policy name exists yet.

`deployments/applications/modules/bucket/main.tf:12`
> `  name   = "${local.name_underscore}_read_write"`

Live `mc admin policy ls m1lab`: `loki_read_write`, `loki_read_only`,
`registry_read_write`, `registry_read_only` are present; `loki` and
`registry` are absent; `tempo` is the only job-id-named policy in the list.

### P7 — HOLDS. registry keeps Vault, loki does not.

`deployments/applications/services/registry.hcl:115`
> `        {{- with secret "${registry_auth_secret}" }}`

`grep -n 'secret "\|vault {' ` returns three hits for registry.hcl (34, 78,
115) and two for loki.hcl (32, 67), so removing loki's MinIO template does
leave `vault {}` at `deployments/applications/services/loki.hcl:32` with
nothing to serve.

### P8 (added) — BREAKS. R4's eight-name list misses the one env var the sibling job sets.

`deployments/applications/services/tempo.hcl:72`
> `        AWS_WEB_IDENTITY_TOKEN_FILE = "/secrets/nomad_minio.jwt"`

tempo is the worked example the implementer copies from, and that variable
is checked BEFORE the shared-config profile.
`.../aws/session/credentials.go:50-53`
> ```
> 	case len(envCfg.WebIdentityTokenFilePath) != 0:
> 		// Web identity token from environment, RoleARN required to also be
> 		// set.
> 		return assumeWebIdentity(cfg, handlers,
> ```

Demonstrated, with the helper wired correctly in every other respect:

```
### CASE N: credential_process wired correctly BUT AWS_WEB_IDENTITY_TOKEN_FILE
###         also set (tempo's R9 env var, no AWS_ROLE_ARN)
SESSION_ERR: WebIdentityErr: role ARN is not set

### CASE O: same, plus AWS_ROLE_ARN
CREDS_ERR: WebIdentityErr: failed to retrieve credentials
caused by: InvalidIdentityToken: The ID Token provided is not a valid JWT.
```

R4 exists to stop exactly this class of silent pre-emption, and it lists
the eight names that cannot cause it while omitting the one that can.

The eight it does list are otherwise correct. Env credentials beating
`credential_process` is real, including the legacy pair:

```
### CASE E: credential_process in config file BUT AWS_ACCESS_KEY_ID env also set
CREDS_OK provider="EnvConfigCredentials" ak="ENVKEY" token=""

### CASE G: legacy AWS_ACCESS_KEY / AWS_SECRET_KEY only
CREDS_OK provider="EnvConfigCredentials" ak="LEGACYKEY" token=""
```

R4's RATIONALE is wrong for four of the eight, though. aws-sdk-go reads no
`MINIO_*` variable; `MINIO_ACCESS_KEY` matters because loki's config
interpolates it under `-config.expand-env=true`
(`deployments/applications/services/loki.hcl:121`), and `MINIO_ROOT_*`
matters for hygiene, not for SDK precedence. The requirement is right; the
reason given for half of it is not.

### P9 (added) — BREAKS. The stated failure symptom is wrong in three places.

R5 says "the SDK falls through to anonymous"; §9(b) repeats it; the eval
marker's row 4 scores on it. It does not happen.
`.../aws/session/session.go:815`
> `	if cfg.Credentials == credentials.AnonymousCredentials && userCfg.Credentials == nil {`

Resolution runs whenever the caller set no credentials, and when it finds
nothing it installs a chain that ERRORS rather than an anonymous signer:

```
### CASE F: no config at all (baseline: what 'nothing wired' looks like)
CREDS_ERR: NoCredentialProviders: no valid providers in chain. Deprecated.
```

Good news operationally, since the failure is loud, but the eval row is
watching for a string that will not appear.

### P10 (added) — BREAKS. The helper's contract is unstated, and it is not free-form.

§7 names `local/minio-creds.sh`; the plan contains no script and no
contract for one. The operator asks whether that is an acceptable plan-level
gap. Not writing the script is fine. Not stating its contract is not, because
the SDK imposes hard constraints the author has not recorded, and §6 carries
only R6 ("stdout only, keeps no state"), which is the least of them.

`.../aws/credentials/processcreds/provider.go:265`
> `	if resp.Version != 1 {`

```
### CASE L: helper prints JSON without Version field
CREDS_ERR: ProcessProviderVersionError: wrong version in process output (not 1)

### CASE K: helper exits non-zero
CREDS_ERR: ProcessProviderExecutionError: error in credential_process
caused by: exit status 1
```

Same file, lines 146-149:
> ```
> 	DefaultBufSize = int(8 * sdkio.KibiByte)
>
> 	// DefaultTimeout default limit on time a process can run.
> 	DefaultTimeout = time.Duration(1) * time.Minute
> ```

And line 316:
> `		cmdArgs = []string{"sh", "-c"}`

So: `"Version":1` is mandatory, stdout is capped at 8 KiB, the run is capped
at 60 s, and the command goes through `sh -c` found on the service process's
PATH. Add the busybox non-2xx body loss from P1 and the XML-to-JSON
conversion the operator flags, and this is where the ticket will actually
break.

## Most dangerous assumption

**P4a: that rendering `local/aws-config` is enough to make the SDK read it.**
Everything else in this ticket is either correct or a wording repair. This
one is the difference between a cutover that works and two services that
fail to resolve credentials at once, and it is invisible in review because
§2's "three env vars" implies the author knows about `AWS_CONFIG_FILE`
while §6 and §7, the sections an implementer builds from, never say it.

## Contract hygiene

- **Code surface anchors.** All resolve and support their claims. Spot
  checks: `deployments/applications/services.tf:229` is
  `resource "nomad_job" "loki" {`, and `:232` is the `loki_minio_secret`
  line §7 says to drop. `deployments/applications/storage.tf:104` is
  `resource "minio_iam_policy" "tempo_wi" {`, the model R3 mirrors.
  `docs/workload-identity.md:169` opens the `identity {` example R1 cites,
  and `:216` is the `| `minio` | MinIO STS, `NOMAD` target | M1 |` row R2
  cites. The eval marker §7 declares exists on disk.
- **Gates discovered, not assumed.** `.loop/config.json:3` is
  `"just pre_commit"`; the justfile runs `pre-commit run --all-files`; the
  hooks are `nomad-fmt`, `terraform-fmt` (`terraform fmt -check
  -recursive`) and `terraform-validate` (`scripts/tf_validate.sh`), whose
  `roots=(` at line 8 closes at line 12 with three entries. §8's gate
  description is accurate. Its aside "No unit-test harness and no CI" is
  not: `.pre-commit-config.yaml:66` is `- id: pytest`, and there is a
  `dash-backend-pytest` too. Neither is reachable from this ticket's files,
  so this is a wording fix, not a gate gap.
- **Non-goals.** Explicit and specific. Fine.
- **Forks surfaced.** Q1-Q4 carry recommendations. On superseding R10 and
  R11: defensible. R10 is a stub, and its own text says
  `use_thanos_objstore` "swaps Loki's entire storage client ... Getting this
  wrong loses logs", so R13's characterization is fair rather than a straw
  man. The honest trade is that thanos offers a supported `sts_endpoint`
  config field against a hand-rolled shell helper, and the plan's Q1 sells
  only the "client untouched" side. Recording the trade would be better; it
  is surfaced, so it is not a refusal. One fork is NOT surfaced: aws-sdk-go
  v1 also carries the container-credentials provider
  (`AWS_CONTAINER_CREDENTIALS_FULL_URI` plus
  `AWS_CONTAINER_AUTHORIZATION_TOKEN`, `aws/defaults/defaults.go:118-121`),
  which would move the exchange into a sidecar and need no shell in either
  image. Observation, not a required fix.
- **Requirements reachable by a measurement.** R1, R2, R3, R4, R6 and R7
  each have a producer in §7 and a scored row. **R5 does not.** §7 claims
  "R5 and R6 by E3", but E3 runs the helper by hand inside the container,
  which prints JSON whether or not `AWS_SDK_LOAD_CONFIG` is set, so it
  cannot fail on R5. The row aimed at R5 is the eval marker's row 4, which
  scores on the "anonymous" symptom P9 shows will not occur. R5 therefore
  has no measurement. This is a hygiene failure and it is why the verdict is
  not a clean pass. Your four options are `widen-surface`, `split-ticket`,
  `drop-requirement` and `declared-proxy`; the reviewer does not pick.
- **Advisory, reverse direction.** Every file in §7 is reached by some
  requirement. No orphans.

## Required fixes

1. **§6 and §7, and the front-matter premise: require `AWS_CONFIG_FILE`.**
   Add it to R5 (or a new requirement) and to the `env` block §7 adds to
   each job, pointing at the rendered `local/aws-config`. Evidence: CASE H
   fails, CASE I succeeds, `HOME=/root` in both live containers. Name the
   three env vars §2 already promises instead of counting them.

2. **§6 R4: add `AWS_WEB_IDENTITY_TOKEN_FILE` to the forbidden list, and
   §8 E2 with it.** Evidence: `deployments/applications/services/tempo.hcl:72`
   sets it, and CASE N shows it kills session creation outright when
   `credential_process` is otherwise correct. While there, fix R4's
   rationale: the `MINIO_*` four are removed because loki interpolates them
   under `-config.expand-env=true`, not because aws-sdk-go reads them.

3. **§8 E2: cover registry's actual credential shape.** R4's eight names do
   not include `accesskey`/`secretkey`, and registry's static key is those
   two YAML lines (`deployments/applications/services/registry.hcl:79-80`).
   Live check: `nomad job inspect registry | grep -c accesskey` returns `1`
   today, so E2 as written would pass a registry that still carries them.
   Assert their absence per job.

4. **§6: state the helper's contract as a requirement.** Not the script,
   the contract: `"Version":1` mandatory, stdout under 8 KiB, completes
   under 60 s, invoked via `sh -c`, exits non-zero only when it means to
   fail, and handles busybox wget returning 1 with an empty body on any
   non-2xx from STS. Add the two open items this exposes to §11 rather than
   leaving them to discovery: how the XML `Credentials` block is parsed with
   busybox `sed`/`awk`, and what `DurationSeconds` to request given the
   identity `ttl` is `1h` and MinIO bounds the session by the JWT's
   remaining life.

5. **§6 R5, §9(b) and Premises: drop the "anonymous" symptom.** The real
   failure is `NoCredentialProviders` and a failed request, per CASE F.
   Rewrite P4 too: `AWS_SDK_LOAD_CONFIG` is required for the CONFIG-file
   placement this plan chose, not for `credential_process` as such
   (CASE C).

6. **§9: complete loki's rollback recipe.** It lists the template, the
   config keys and the templatefile variable. §7 also deletes
   `deployments/applications/services/loki.hcl:32` (`      vault {}`), and
   the restored template cannot read Vault without it. Add it.

## On sequencing and rollback

Sequencing is right as written. Loki first, registry second, applied
separately: a broken registry blocks the image pulls you would need to
recover, and `nomad alloc logs` still works when loki is down, so cutting
loki first costs you no diagnostics. Keep it.

Rollback is genuinely sufficient, and I checked the one thing that could
have spoiled it. Re-adding the static keys works even with
`AWS_SDK_LOAD_CONFIG=1` left in place, because credential resolution is
skipped whenever the caller set credentials on the config
(`.../aws/session/session.go:815`). So the revert does not have to unwind
the env block, only restore the template, the config keys, the templatefile
variable and, per required fix 6, loki's `vault {}`.

## Scratch

Scratch created at
`.loop/scratch/R13-rollout-loki-registry-keyless-minio.plan-validator/`;
findings ledger written to `findings.json` in that directory; the probe
artifacts under `p4/` and the fetched upstream sources removed at end of
pass. No trust stamp: every gate re-run was cheap.
