---
verdict: pass-with-required-fixes
plan: fb2eb449a218132ffc9b9a13774d631e6bc0e5e6827dcefbdaafa403b98f2d67
bound_paths: front-matter, 5, 6, 7, 8, 9, 10, premises
scope: c9def7d624802b68588c00c38641bd544f77cfc1e235a1410366c819c8a4c12d
fix_sections: 6, 7, 8, 9, premises
citations: deployments/applications/services/tempo.hcl:39 =       user   = "root"
  deployments/applications/services/tempo.hcl:41 =       vault {}
  deployments/applications/services/tempo.hcl:60 =         image = "docker.io/grafana/tempo:2.10.8"
  deployments/applications/services/tempo.hcl:77 =         MINIO_ACCESS_KEY="{{ .Data.data.access_key }}"
  deployments/applications/services/tempo.hcl:78 =         MINIO_SECRET_KEY="{{ .Data.data.secret_key }}"
  deployments/applications/services/tempo.hcl:82 =         destination = "secrets/minio.env"
  deployments/applications/services/tempo.hcl:105 =           max_block_duration: 30m
  deployments/applications/services/tempo.hcl:118 =               endpoint: 192.168.2.29:9000
  deployments/applications/services/tempo.hcl:119 =               access_key: $${MINIO_ACCESS_KEY}
  deployments/applications/services/tempo.hcl:120 =               secret_key: $${MINIO_SECRET_KEY}
  deployments/applications/services.tf:242 =     { tempo_minio_secret = vault_kv_secret_v2.tempo_minio_credentials.path }
  deployments/applications/storage.tf:25 =         { "name" = "tempo", generate_access_key = true }
  deployments/applications/storage.tf:86 = resource "minio_iam_user" "users" {
  deployments/applications/storage.tf:91 = resource "minio_accesskey" "users" {
  deployments/applications/modules/bucket/main.tf:12 =   name   = "${local.name_underscore}_read_write"
  deployments/applications/modules/bucket/main.tf:30 =   name   = "${local.name_underscore}_read_only"
  deployments/applications/secrets.tf:53 = resource "vault_kv_secret_v2" "tempo_minio_credentials" {
  deployments/applications/secrets.tf:55 =   name  = "default/tempo/minio"
  deployments/infrastructure/services/minio.hcl:89 =         MINIO_IDENTITY_OPENID_CLIENT_ID_NOMAD="minio"
  deployments/infrastructure/services/minio.hcl:90 =         MINIO_IDENTITY_OPENID_CLAIM_NAME_NOMAD="nomad_job_id"
  docs/workload-identity.md:192 = Nomad skips the chown and leaves the JWT world-readable only when the task
  docs/workload-identity.md:193 = sets no `user`. Adding `user =` to a task whose process runs unprivileged
  docs/workload-identity.md:214 = | `vault.io` | Vault, via the `jwt-nomad` mount | F1 |
  docs/workload-identity.md:216 = | `minio` | MinIO STS, `NOMAD` target | M1 |
  docs/workload-identity.md:314 =    credential is minted, with `None of the given policies are defined`. It
  docs/workload-identity.md:347 = provider may run in claim mode. A token arriving with no `RoleArn` has to
  .loop/reflections/M1-minio-poc-service-account.md:22 = proof: the session token carries no `roleArn`, and MinIO cannot mint that
  .pre-commit-config.yaml:16 =       - id: nomad-fmt
  .pre-commit-config.yaml:22 =       - id: terraform-fmt
  .pre-commit-config.yaml:28 =       - id: terraform-validate
  justfile:45 =     ln -sfn "$(pwd)/.ssh" "{{ path }}/.ssh"
  github.com/grafana/tempo@v2.10.8 tempodb/backend/s3/s3.go:695 = 		wrapCredentialsProvider(&credentials.EnvMinio{}),
  github.com/grafana/tempo@v2.10.8 tempodb/backend/s3/s3.go:702 = 			Endpoint: os.Getenv("TEST_IAM_ENDPOINT"),
  github.com/grafana/tempo@v2.10.8 go.mod:31 = 	github.com/minio/minio-go/v7 v7.1.0
  github.com/minio/minio-go@v7.1.0 pkg/credentials/iam_aws.go:82 = 	DefaultSTSRoleEndpoint      = "https://sts.amazonaws.com"
  github.com/minio/minio-go@v7.1.0 pkg/credentials/iam_aws.go:154 = 	endpoint := m.Endpoint
  github.com/minio/minio-go@v7.1.0 pkg/credentials/iam_aws.go:166 = 				endpoint = DefaultSTSRoleEndpoint
  github.com/minio/minio-go@v7.1.0 pkg/credentials/env_minio.go:44 = 	id := os.Getenv("MINIO_ROOT_USER")
  github.com/minio/minio-go@v7.1.0 pkg/credentials/env_minio.go:49 = 		id = os.Getenv("MINIO_ACCESS_KEY")
  github.com/minio/minio-go@v7.1.0 pkg/credentials/chain.go:61 = 		creds, _ := p.RetrieveWithCredContext(cc)
  github.com/minio/minio-go@v7.1.0 pkg/credentials/chain.go:72 = 		SignerType: SignatureAnonymous,
  github.com/minio/minio-go@v7.1.0 pkg/credentials/sts_web_identity.go:150 = 	if len(roleARN) > 0 {
---

rebound-by: JasperHG90 2026-09-02T16:50:08Z (reason: applied all 7 required fixes from the plan-validator verdict; every change confined to the declared fix_sections (6, 7, 8, 9, premises))

# Plan review: R9-rollout-tempo-keyless-minio

## Deterministic floor

`loopctl verify-plan R9-rollout-tempo-keyless-minio` returns
`valid: warn: provenance: premise Q1 measured against package tempo v2.10.8 /
minio-go v7.1.0 at tempodb/backend/s3/s3.go L686-706; pkg/credentials/iam_aws.go
L123-186`. No hard fail, so the semantic pass ran. The reviewed bytes match the
snapshot (`diff` reports identical) and `sha256sum` on the plan returns the
briefed fingerprint.

## Premise verdict

**PARTIALLY SOUND.**

The engineering core is right, and I proved the two claims that carry the most
weight rather than reading them. Tempo v2.10.8 really does reach minio-go's IAM
provider, really does exchange a web-identity token against an operator-set
endpoint, and really does send no `RoleArn`. The plan's central safety
argument (R4) is correct and I reproduced the silent fallback live.

What breaks is the verification design and the risk narrative around that core:
the plan's own designated catcher for its most dangerous failure mode, eval row
E2, cannot execute against this image; the failure mode described in §9(b) is
not what an operator will actually see; and §7 leaves the one value most likely
to be typed wrong unstated, where getting it wrong fails silently. All of it is
confined to sections 6, 7, 8, 9 and Premises.

## Method note

Probes ran in `.loop/scratch/R9-rollout-tempo-keyless-minio.plan-validator/probe/`
against the real pinned image, pulled by digest
`sha256:f0561deb1c68ec44d6e6e7e4487f30106c4e5e768642077695b37958b105812a`, which
matches the Docker Hub digest for tag `2.10.8`. Each probe pointed tempo's s3
`endpoint` and `TEST_IAM_ENDPOINT` at a local listener that logs the request
line, the `Authorization` header and the POST body. Probes A and B were re-run
from a clean state and gave identical counts, so nothing below rests on a flaky
run. Scratch created at
`.loop/scratch/R9-rollout-tempo-keyless-minio.plan-validator/`.

## Per-assumption findings

### The plan's stated premises

- **P1 — HOLDS.** `github.com/grafana/tempo@v2.10.8 tempodb/backend/s3/s3.go:686-703`
  > 	chain := []credentials.Provider{
  > 		wrapCredentialsProvider(&credentials.Static{
  > 		wrapCredentialsProvider(&credentials.EnvAWS{}),
  > 		wrapCredentialsProvider(&credentials.EnvMinio{}),
  > 		wrapCredentialsProvider(&credentials.FileAWSCredentials{}),
  > 		wrapCredentialsProvider(&credentials.FileMinioClient{}),
  > 		wrapCredentialsProvider(&credentials.IAM{
  > 			Endpoint: os.Getenv("TEST_IAM_ENDPOINT"),

  The order and the endpoint source are exactly as claimed, at exactly the
  cited lines, at exactly the cited tag. The tag is real: the GitHub API returns
  `refs/tags/v2.10.8`, and the pin at `deployments/applications/services/tempo.hcl:60`
  > 	image = "docker.io/grafana/tempo:2.10.8"

  resolves to a live Docker Hub tag. This is the path that serves this repo's
  config: `fetchCreds` is called only by `createCore` (`s3.go:717`), and the
  jobspec's YAML keys map onto this package's `Config` struct
  (`tempodb/backend/s3/config.go:49-62` carries `yaml:"bucket"`,
  `yaml:"endpoint"`, `yaml:"insecure"`, `yaml:"forcepathstyle"`).

  Demonstrated, not inferred. Probe B ran the pinned image with no static key
  and captured, at the listener:
  ```
  === STS POST /
  BODY: Action=AssumeRoleWithWebIdentity&Version=2011-06-15&WebIdentityToken=FAKE.JWT.TOKEN-nomadjobid-tempo%0A
  ```
  and tempo logged `version="(version=v2.10.8, branch=HEAD, revision=f0f3ed591)"`.

- **P2 — HOLDS.** `github.com/grafana/tempo@v2.10.8 go.mod:31`
  > 	github.com/minio/minio-go/v7 v7.1.0

  The pin is what the plan says. At
  `github.com/minio/minio-go@v7.1.0 pkg/credentials/iam_aws.go:123,128,154,158,170-183,187`
  > 	identityFile := os.Getenv("AWS_WEB_IDENTITY_TOKEN_FILE")
  > 	roleArn := os.Getenv("AWS_ROLE_ARN")
  > 	endpoint := m.Endpoint
  > 		if len(endpoint) == 0 {
  > 		creds := &STSWebIdentity{
  > 			STSEndpoint: endpoint,
  > 			GetWebIDTokenExpiry: func() (*WebIdentityToken, error) {
  > 				token, err := os.ReadFile(identityFile)
  > 			m.SetExpiration(creds.Expiration(), DefaultExpiryWindow)

  Every element of the premise is on the cited lines: the token-file env var,
  the direct use of `m.Endpoint`, the fallback guarded behind `len(endpoint) == 0`
  so a non-empty endpoint skips it, `STSWebIdentity` built with `STSEndpoint`,
  the per-retrieve `os.ReadFile`, and `SetExpiration`. Probe B confirms the wire
  behavior: after the exchange, tempo signed its S3 calls with the returned
  session credential.
  ```
  AUTH: AWS4-HMAC-SHA256 Credential=STSFAKEACCESSKEY/20260902/us-east-1/s3/aws4_request, SignedHeaders=host;x-amz-content-sha256;x-amz-date;x-amz-security-token, ...
  ```

  One citation drift, cosmetic: the plan writes the fallback as "155-166"; the
  block is 158-168. The cited range overlaps the substance, so this is an
  observation, not a fix.

- **P3 — HOLDS on substance; one cited path does not exist.**
  `github.com/minio/minio-go@v7.1.0 pkg/credentials/sts_web_identity.go:150-157`
  > 	if len(roleARN) > 0 {
  > 		v.Set("RoleArn", roleARN)
  > 		v.Set("RoleSessionName", roleSessionName)

  `RoleArn` is set only when non-empty, so an unset `AWS_ROLE_ARN` sends none.
  Probe B's captured body is the demonstration: the POST carries `Action`,
  `Version` and `WebIdentityToken` and nothing else. The MinIO half is settled
  by this repo's own record of M1's live proof, `docs/workload-identity.md:347`
  > provider may run in claim mode. A token arriving with no `RoleArn` has to

  and `.loop/reflections/M1-minio-poc-service-account.md:22`
  > proof: the session token carries no `roleArn`, and MinIO cannot mint that

  This was the premise the author was least able to prove from source, and it
  stands. But its first cited evidence path,
  `.loop/archive/M1-minio-poc-service-account/`, **does not exist**. `.loop/archive/`
  holds 40 entries and none matches `M1` or `minio`. The deterministic floor did
  not catch it. The claim survives on its other two anchors; the dead pointer is
  a required fix.

- **P4 — HOLDS.** `deployments/infrastructure/services/minio.hcl:90`
  > 	MINIO_IDENTITY_OPENID_CLAIM_NAME_NOMAD="nomad_job_id"

  Claim mode on the `NOMAD` target, as stated. `minio.hcl:89`
  > 	MINIO_IDENTITY_OPENID_CLIENT_ID_NOMAD="minio"

  also confirms R2's `aud = ["minio"]`.

- **P5 — HOLDS, on the repo's recorded live finding rather than on my own.**
  `deployments/applications/services/tempo.hcl:39`
  > 	user   = "root"

  and `docs/workload-identity.md:192-194`
  > Nomad skips the chown and leaves the JWT world-readable only when the task
  > sets no `user`. Adding `user =` to a task whose process runs unprivileged
  > breaks its ability to read its own identity file — and the failure is

  The hazard is scoped to an unprivileged process, so a root task reads a
  root-owned file. Note the doc's rule is narrower than the plan's paraphrase:
  Nomad skips the chown only when the task sets **no** `user`, so tempo does get
  chowned. It gets chowned to root, which is why the conclusion holds. I could
  not demonstrate this without a live Nomad alloc; the anchor and quote settle
  it as a pure-intent premise.

- **P6 — HOLDS.** `deployments/applications/modules/bucket/main.tf:12` and `:30`
  > 	name   = "${local.name_underscore}_read_write"
  > 	name   = "${local.name_underscore}_read_only"

  A repo-wide grep for `minio_iam_policy` across `deployments/` returns only
  `modules/bucket/main.tf:11` and `:29`, so the module is the sole producer and
  the only name for this bucket is `tempo_read_write`. Caveat worth carrying:
  this is repo state, not live MinIO state. A hand-made policy named `tempo`
  left over from an operator session would collide on apply. Cheap to check with
  `mc admin policy list` before subticket 1.

### Implicit premises the plan left out

- **P7 — BREAKS. §9(b) describes a failure the operator will not see.** The plan
  says a missing policy makes the exchange "fail outright with `None of the
  given policies (...) are defined` rather than returning a credential that is
  then denied", citing `docs/workload-identity.md:314`
  >    credential is minted, with `None of the given policies are defined`. It

  MinIO's side is as documented. Tempo's side is not. At
  `github.com/minio/minio-go@v7.1.0 pkg/credentials/chain.go:61` and `:72`
  > 		creds, _ := p.RetrieveWithCredContext(cc)
  > 		SignerType: SignatureAnonymous,

  the chain **discards** the provider's error and, when every provider comes up
  empty, returns an anonymous credential. Probe D pointed tempo at an STS that
  returns HTTP 400 with that exact MinIO message. Captured:
  ```
  STS POST / BODY:Action=AssumeRoleWithWebIdentity&Version=2011-06-15&WebIdentityToken=...
  S3 GET /tempo/?location= AUTH:None
  ```
  ```
  level=error caller=main.go:110 msg="error running Tempo" err="failed to init module services: error initialising module: optional-store: failed to create store: unexpected error from ListObjects on tempo: Access Denied."
  ```
  The policy error never reaches tempo's logs. Tempo goes anonymous and dies on
  `Access Denied` — which reads exactly like "a credential that is then denied",
  the outcome §9(b) tells the reader to rule out. Good news buried in this: tempo
  does fail fast (exit 1) rather than crash-looping silently, so the §10 ordering
  holds and E1 catches it. But an operator debugging a failed cutover by grepping
  for the documented string will find nothing.

- **P8 — BREAKS. E2 is not runnable against this image, and E2 is the row the
  plan itself calls load-bearing.** §8 specifies "`nomad alloc exec` and
  `env | grep -E 'MINIO_(ACCESS|SECRET)|AWS_(ACCESS|SECRET)'` returns nothing.
  This is the check that catches R4's silent fallback; without it every other
  row passes on the old key."

  `docker.io/grafana/tempo:2.10.8` ships no shell and no coreutils. Exporting the
  image filesystem and listing top-level entries returns `bin/`, `sbin/`,
  `usr/bin/`, `usr/sbin/` as **empty directories**; the only executable is
  `/tempo` at the root. Direct probe:
  ```
  $ docker run --rm --entrypoint /bin/sh grafana/tempo:2.10.8 -c 'echo SHELL_OK'
  exec: "/bin/sh": stat /bin/sh: no such file or directory
  $ docker run --rm --entrypoint /bin/ls grafana/tempo:2.10.8 /
  exec: "/bin/ls": stat /bin/ls: no such file or directory
  ```
  `nomad alloc exec` needs a binary inside the container; there is none but the
  tempo server itself. So the plan's designated catcher for its most dangerous
  failure mode cannot be executed as written, and the ticket would be scored
  without it.

- **P9 — BREAKS. §7 leaves `TEST_IAM_ENDPOINT`'s value unstated, and the wrong
  form fails silently.** §7 says only "add an `env` block to the task setting
  `AWS_WEB_IDENTITY_TOKEN_FILE` and `TEST_IAM_ENDPOINT`". minio-go feeds the
  value to `url.Parse` then `http.NewRequest`, so it needs a scheme. The
  adjacent line in the same file models the schemeless form:
  `deployments/applications/services/tempo.hcl:118`
  > 	      endpoint: 192.168.2.29:9000

  An implementer who copies that style breaks the ticket without a trace. Probe
  E set `TEST_IAM_ENDPOINT=192.168.2.29:9000` and captured, over a full run:
  ```
  lines: 10
  === S3 GET /tempo/?location=
  AUTH: None
  ```
  Zero STS requests, every S3 call anonymous, and no log line naming the
  endpoint. `http://192.168.2.29:9000` is the value that works (probe B).

- **P10 — UNCERTAIN. E3 is runnable, but not on the timescale the row implies.**
  §8 E3 asks that "New objects appear under the `tempo` bucket after the cutover
  (`mc ls --recursive m1lab/tempo` count rises)". Probe C ran the pinned image
  with `blocklist_poll: 10s` and captured **zero PUTs in 25 s with no traces
  flowing** — tempo writes no tenant index on an empty tenant, only list and
  location GETs. After one OTLP span was pushed and with `max_block_duration:
  15s`, four objects appeared:
  ```
  1 ('S3', 'PUT', '/tempo/single-tenant/3e422788-.../data.parquet')
  1 ('S3', 'PUT', '/tempo/single-tenant/3e422788-.../bloom-0')
  1 ('S3', 'PUT', '/tempo/single-tenant/3e422788-.../index')
  1 ('S3', 'PUT', '/tempo/single-tenant/3e422788-.../meta.json')
  ```
  So the count does rise, but only once a block is cut, and production sets
  `deployments/applications/services/tempo.hcl:105`
  > 	    max_block_duration: 30m

  A scorer running E3 a few minutes after the cutover sees no new objects and
  would wrongly read that as a failed cutover. E3 needs a stated precondition
  (traces are being ingested) and a stated wait (> `max_block_duration`), or a
  cheaper substitute observable. Minor and separable: `m1lab` is an operator-local
  `mc` alias that appears nowhere in the repo.

- **P11 — HOLDS (the contradiction you asked me to look for is not there).** Your
  reading is right. R4 removes what is *rendered into the job*; non-goal 1 keeps
  what is *provisioned in MinIO and Vault*. Those are independent resources.
  `deployments/applications/secrets.tf:53` and `:55`
  > resource "vault_kv_secret_v2" "tempo_minio_credentials" {
  >   name  = "default/tempo/minio"

  is a standalone resource, not gated on the templatefile reference at
  `deployments/applications/services.tf:242`
  > 	  { tempo_minio_secret = vault_kv_secret_v2.tempo_minio_credentials.path }

  Dropping that variable removes a read of `.path`, not the resource. Likewise
  `deployments/applications/storage.tf:91`
  > resource "minio_accesskey" "users" {

  is driven by `local.access_key_users`, which derives from
  `deployments/applications/storage.tf:25`
  > 	    { "name" = "tempo", generate_access_key = true }

  which §7 does not touch. The rollback path survives, so E5 is satisfiable and
  non-goal 1 stands.

### The claim you most wanted attacked: R4

- **R4 — HOLDS, and it is the strongest part of the plan.**
  `github.com/minio/minio-go@v7.1.0 pkg/credentials/env_minio.go:49`
  > 		id = os.Getenv("MINIO_ACCESS_KEY")

  and `github.com/grafana/tempo@v2.10.8 tempodb/backend/s3/s3.go:695`
  > 		wrapCredentialsProvider(&credentials.EnvMinio{}),

  with `chain.go:60-68` taking the first provider returning a non-empty key.
  Probe A ran the pinned image with the YAML keys deleted and
  `MINIO_ACCESS_KEY`/`MINIO_SECRET_KEY` still in the environment, exactly the
  half-done cutover R4 warns about:
  ```
  STS request count: 0
  S3 request count:  5
  Static-key signed: 5
  STS-key signed:    0
  === S3 GET /tempo/?location=
  AUTH: AWS4-HMAC-SHA256 Credential=STATICLEFTOVERAK/20260902/us-east-1/s3/aws4_request, ...
  ```
  Clean rerun: `A2: STS=0  static-signed=5  sts-signed=0`. Not one STS call was
  attempted; every request went out on the static key. R4 and E2's rationale are
  both correct. The problem is not the argument, it is that E2 cannot run (P8).

## Most dangerous assumption

**P8 — that E2 can be executed.** R4 is right, which means the half-done cutover
it describes produces a job that looks completely healthy: alloc running, health
check green, traces flowing, no error in the logs, and a static credential still
in use. The plan knows this and appoints E2 as the only row that can tell the two
states apart. E2 cannot run against a distroless image. If the ticket ships with
E2 unfixed, the most likely failure mode of this cutover is also the one nothing
in the plan detects.

## Required fixes

1. **§8, E2: replace the exec-based check.** `grafana/tempo:2.10.8` has no shell.
   Two substitutes need no in-container binary: `nomad alloc fs <alloc> tempo/secrets/`
   asserting `minio.env` is absent, and `nomad job inspect tempo` asserting the
   `Templates` and `Env` blocks carry no MinIO key. Pick one and write the exact
   command, since this row is the plan's own safety net.
2. **§8, E2: widen the credential-source check.** `env_minio.go:44`
   > 	id := os.Getenv("MINIO_ROOT_USER")

   EnvMinio checks `MINIO_ROOT_USER`/`MINIO_ROOT_PASSWORD` *before*
   `MINIO_ACCESS_KEY`/`MINIO_SECRET_KEY`. E2's regex matches neither. Nothing in
   this jobspec sets them today, but E2 claims "no static credential remains
   reachable", and R4 enumerates the whole chain, so the check should too.
3. **§9(b): correct the observable.** State that minio-go swallows the STS error
   and falls to anonymous, so a missing policy shows up in tempo's log as
   `ListObjects on tempo: Access Denied` and the MinIO-side message
   `None of the given policies ... are defined` appears only in MinIO's log.
   Evidence: `chain.go:61`, `chain.go:72`, and probe D above.
4. **§7: state `TEST_IAM_ENDPOINT`'s value with its scheme**, and
   `AWS_WEB_IDENTITY_TOKEN_FILE`'s with its leading slash. The schemeless form
   silently disables the exchange (probe E), and the line directly above in the
   same file uses the schemeless form.
5. **§9(c): fix the fallback constant.** The plan names
   `https://sts.<region>.amazonaws.com`. Tempo passes no `Region` to the IAM
   provider (`s3.go:698-703` sets only `Client` and `Endpoint`) and `AWS_REGION`
   is unset, so the branch that applies is
   `iam_aws.go:166`
   > 				endpoint = DefaultSTSRoleEndpoint

   with `iam_aws.go:82`
   > 	DefaultSTSRoleEndpoint      = "https://sts.amazonaws.com"

   The conclusion ("every call leaves the LAN") is unchanged; the constant is
   wrong.
6. **§6, R2: fix the anchor.** The plan cites `docs/workload-identity.md:214`.
   That line is
   > | `vault.io` | Vault, via the `jwt-nomad` mount | F1 |

   The row that assigns `minio` is line 216:
   > | `minio` | MinIO STS, `NOMAD` target | M1 |

   The anchor resolves but does not support the claim attached to it.
7. **Premises, P3: remove or replace the dead path.**
   `.loop/archive/M1-minio-poc-service-account/` does not exist; `.loop/archive/`
   has 40 entries and none matches. `.loop/reflections/M1-minio-poc-service-account.md:19-24`
   carries the live proof and is the anchor that survives.
8. **§8, E3: state the precondition and the wait**, or name a faster observable.
   No objects are written until a block is cut, and production sets
   `max_block_duration: 30m` (`tempo.hcl:105`). As written, a scorer checking
   soon after the cutover reads a working config as broken. Also define or drop
   the `m1lab` alias, which the repo never establishes.

## Contract hygiene

- **Anchors.** Every `path:line` in §4, §6 and §7 resolves and says what the plan
  claims, with the one exception in fix 6 (`docs/workload-identity.md:214`) and
  the dead `.loop/archive/` path in fix 7. `tempo.hcl:37-41`, `:74-84`,
  `:113-122`, `:119-120`, `:41`, `:60`; `services.tf:239-244`; `storage.tf:23-28`,
  `:86`; `modules/bucket/main.tf:11-27`, `:12`; `secrets.tf:53-58` all check out.
  `modules/bucket/outputs.tf` is genuinely 0 bytes, so R3's "exports nothing"
  argument stands.
- **Gates, discovered not assumed.** `.loop/config.json` carries
  `"gates": ["just pre_commit"]`, `justfile:18` defines `pre_commit`, and the
  three hooks the plan names are at `.pre-commit-config.yaml:16`, `:22`, `:28`
  as cited. `justfile:44-48` is the `worktree_setup` recipe, so the worktree
  precondition is real.
- **Requirements reachable by a measurement.** R1, R2, R3 and R5 each name an
  observable with a producer in §7 and a scoring row in §8. R4's producer exists
  (`tempo.hcl:74-84` and `:113-122`) but its measurement (E2) does not execute:
  that is the hygiene failure driving fix 1, and it is why this is not a clean
  pass. Operator options as usual: `widen-surface`, `split-ticket`,
  `drop-requirement`, `declared-proxy`. I do not pick one.
- **Non-goals, tests homed, forks surfaced.** All present. §5 is explicit, every
  eval row is homed in `.loop/evals/R9-rollout-tempo-keyless-minio.md` (listed in
  §7; the file does not exist yet, which is correct for a plan), and Q1/Q2/Q3
  each carry a recommendation.
- **Observation, advisory only.** §4 says a grep for `secret` in `tempo.hcl`
  "returns lines 76, 78, 120 and nothing else". It also returns line 82:
  > 	destination = "secrets/minio.env"

  Line 82 sits inside the template block §7 deletes, so the conclusion that
  `vault {}` is dead afterward is unaffected. §4 is outside `bound_paths`, so
  this is not a required fix.

## On `TEST_IAM_ENDPOINT` as a production dependency

You asked whether the name alone should block. It should not. The variable is
read in the shipped release path, not behind a build tag or a test helper: it is
the sole source of the IAM provider's `Endpoint` at
`tempodb/backend/s3/s3.go:702`, in `fetchCreds`, which every s3-backend startup
calls through `createCore`. There is no alternative knob in this version, so
depending on it is not a choice between a supported and an unsupported path; it
is the only path. Q1's handling (proceed, keep the image pinned, re-check on
upgrade) is the right call, and the pin is real at `tempo.hcl:60`. Strengthen the
watch by naming the concrete upgrade check: after any tempo bump, grep the new
tag's `s3.go` for `TEST_IAM_ENDPOINT` before deploying.

## Scratch

Scratch created at `.loop/scratch/R9-rollout-tempo-keyless-minio.plan-validator/`.
Probe artifacts and fetched upstream sources removed at end of pass; the findings
ledger at `.loop/scratch/R9-rollout-tempo-keyless-minio.plan-validator/findings.json`
is retained for the next cycle, per the reviewer brief.
