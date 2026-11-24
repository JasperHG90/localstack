# Update Log

## 2026-09-26

- **Bundle created** (`index.md`): Adopted the Open Knowledge Format so decisions, lessons and unbuilt plans stop sitting in `docs/` beside user guides, where a reader could not tell a current instruction from a record of intent. Recorded as [ADR 0001](/decisions/0001-durable-knowledge-lives-in-an-okf-bundle.md).
- **docs/ sorted by reader intent** (`decisions/0002-docs-are-sorted-by-reader-intent.md`): Split the 29 flat pages in `docs/` into how-to, reference and explanation, keeping their wording, and moved everything aimed at people working on the repository into this bundle.
- **Decisions carved out of docs** (`decisions/0003` to `0012`): Wrote retrospective records for the choices the old pages already argued with a named rejected alternative: public lab DNS, no `.consul` forwarding, Vault-minted Postgres users and per-job JWT roles, OpenViking's static MinIO key, Bifrost rerank and missing browser surface, and three Login MFA choices. Numbered in the order the choices were made.
- **Proposals kept, not deleted** (`proposals/`): The credential-rotation and RISC-V plans, the Postgres-to-NATS bridge and the Postgres dynamic-credentials follow-up were never built, and the OpenViking dashboard was superseded. Each says what state it is in, so a reader does not mistake it for current behavior.
- **Monitoring build plan** (`components/monitoring-stack.md`): Kept the original build plan as history and recorded that git shows the stack on `ubuntu` from its first commit, which contradicts the plan's claim that it moved there from firebat.

## 2026-09-27

- **Components filled in** (`components/`): Added 31 concepts, one per subsystem, covering how each part of the cluster is put together across both Terraform roots, the jobspecs, Ansible and the CLI, and the traps that shaped it. Written from the code, its `###` comment blocks and the archived loop tickets, because that is where this repository's build reasoning was kept and `docs/` never held it.
- **Nodes section added** (`nodes/`): One page per device, so a reader can see what a node carries, why each job is pinned there and what breaks when it goes down, without assembling it from five jobspecs and two Terraform roots. The cross-node placement rules moved here from `components/cluster-nodes.md`, now [Node placement](/nodes/placement.md).
- **Deployment layers** (`architecture/deployment-layers.md`): Wrote down what Ansible, the infrastructure root and the applications root each own, because the rule for the infrastructure-applications line was stated nowhere, and the written Ansible rule ("no management token in Terraform") has been false since G2 brokered one into the infrastructure root.

## 2026-10-19

- **Devcontainer shares caches with loop-harness** (`components/devcontainer.md`, `decisions/0013-devcontainer-shares-caches-with-loop-harness.md`): Recorded that the uv and prek caches are the loop-harness container's named volumes, so a rename on either side silently ends the sharing, and that `just setup` needs `prek install --overwrite` or the old pre-commit hook survives and fails every commit. Dropped the page's "uncommitted edits" framing, because those edits are committed.
- Added `summary` with `kmctl init`.
- Added `manifesto` with `kmctl init`.
- Added `decisions/0014-keep-project-knowledge-in-an-okf-bundle` with `kmctl init`.
- Added `decisions/0015-loopctl-owns-the-pre-commit-hook-and-chains-prek-behind-it` with `kmctl new decision`.
- **loopctl owns the commit hook** (`components/devcontainer`, `decisions/0015-loopctl-owns-the-pre-commit-hook-and-chains-prek-behind-it`): Recorded that the image installs a pinned loopctl and that `just setup` chains prek's hook behind loopctl's commit gate as `pre-commit.local`, so the gate survives a container rebuild. Dropped aim from the agent tools, because the Dockerfile no longer installs it.
- Superseded `decisions/0014-keep-project-knowledge-in-an-okf-bundle` with `decisions/0001-durable-knowledge-lives-in-an-okf-bundle`.
- `architecture/deployment-layers`: Added a diagram of the three layers, the keyless MinIO workload-identity handoff (each `*_wi` policy name equals its job id; the job identity's `aud` matches MinIO's OpenID client id), sources for the files that hold that boundary, and a Depicts section listing its entry points, files and the manifesto invariants.
- `nodes/firebat`: Recorded that MinIO reads Nomad's OIDC discovery through firebat's edge, so loki, tempo and the registry lose keyless S3 credentials when firebat is down.
- `components/monitoring-stack`: Pointed sources at the Prometheus, Grafana and node-exporter jobspecs, and corrected the history: `663663a` added Loki and Promtail with Prometheus and Grafana on ubuntu, and `9a84f24` later added Tempo and replaced Promtail with Alloy.
- `components/nomad-oidc-discovery`: Pointed sources at the Nomad server template, its playbook and MinIO's jobspec, and recorded that MinIO reads the issuer as `MINIO_IDENTITY_OPENID_CONFIG_URL_NOMAD`.
- `components/observability-pipeline`: Recorded that the OpenViking alerts landed in `a055dcf`, replacing a note that called them uncommitted.
- `components/openviking-database`: Pointed sources at `deployments/applications/database.tf` and `ov.conf.json`, and recorded that `623abf8` created the database, role and vector extension while the `openviking` schema is not a Terraform resource.
- `components/openviking-service`: Recorded that the two-check health design, the config hook, the five keyword fields and the alerts landed in `a055dcf`, replacing notes that called them working-tree edits.
- `components/acme-certificate-job`: Dropped two duplicate sources, added `.openviking_workload` to the JWT roles that copy acme's shape, and recorded that T5 was never built and left the loop at reinit `5b2ed1b`.
- `components/bifrost`: Recorded that B2 and SY1 were never built and left the loop at reinit `5b2ed1b`, replacing their old ready and planning states.
- `components/container-registry`: Added `deployments/applications/storage.tf` as a source, recorded that the static MinIO key stays as the rollback path, and that R13 superseded the R11 stub.
- `components/dash`: Completed the module list (`config.py`, the copied `_http.py`), corrected the loop gates (cli's tests also run, dash's suite still runs by hand) and recorded the suite's 75 passing on 2026-10-19.
- `components/deployer-credentials`: Recorded that the applications justfile evals `localstack env` and so needs `localstack` on PATH, and that F8 was never built and no ticket owns its work.
- `components/devcontainer`: Added `cli/tests/test_devcontainer_volumes.py` as a source, and recorded the `mc` alias `bootstrap.sh` sets from the `AWS_*` variables `.env.example` does not list.
- `components/driftwatch`: Dropped a stale note that called the alert-rule edits uncommitted, since they landed in `a055dcf`.
- `decisions/0002-docs-are-sorted-by-reader-intent`, `decisions/0003-lab-names-resolve-from-public-dns`, `decisions/0004-consul-names-are-not-forwarded`, `decisions/0007-openviking-static-key-has-no-claim-policy`, `decisions/0008-openviking-rerank-goes-through-bifrost`, `decisions/0009-openviking-has-no-browser-surface`, `decisions/0010-vault-generates-each-totp-qr`, `decisions/0012-no-mfa-enrollment-app-on-dash`, `decisions/0013-devcontainer-shares-caches-with-loop-harness`: Pointed each record's sources at the code and pages it governs. Each body still holds against HEAD and is unchanged.
- `decisions/0005-postgres-credentials-come-from-vaults-database-engine`: Appended a correction: the admin password is at `secrets.tf:77-97`, the old ledger is gone from HEAD, and Postgres still uses static passwords with Redis as the only database engine.
- `decisions/0006-each-converted-job-gets-its-own-vault-jwt-role`: Appended a correction: mlflow and phoenix no longer run, the jobs left to convert are memex `db-migrate`, bifrost and openviking, and the Redis JWT roles are in `machine_roles.tf`.
- `decisions/0011-login-mfa-enforcement-names-the-userpass-mount`: Appended a correction: the `lab` provider has seven clients since `hermes_dashboard` was added in `fd5134d`, and `oauth2_proxy` also fronts registry-ui.
- `components/minio`: Recorded the R10 to R12 gap as it happened: R13 superseded the R10 and R11 stubs, the operator dropped R12 in `a7aa595`, and none of the three was built before the `5b2ed1b` reset. Added the planned SeaweedFS replacement tickets.
- `components/memex`: Recorded that memex keeps its static MinIO key because R12 was dropped, and that R7 was never built.
- `components/hermes`: Recorded that the `memory_max` removal landed in `a055dcf`, and marked hermes-veerle-profile and U6 as tickets from before the reset.
- `components/edge-proxy`: Marked T5 and N4 as tickets from before the reset, recorded that `alert-rules.yaml` has no certificate-expiry rule, and dropped a duplicate source.
- `components/gcs-backups`: Corrected the gate claim (the loop's gates run the cli tests, so the drift test runs), dropped a pointer to a `just test` recipe that does not exist, and added the planned `backup-durable-buckets` widening.
- `components/host-firewall`: Marked N3 and N4 as tickets from before the reset, and dropped a dead verdict path, a stale ledger sentence and a duplicate source.
- `components/localstack-cli`: Added `config.py` to the layout and `test_devcontainer_volumes.py` to the guarding tests, and marked D9 and D11 as never built.
- `components/registry-ui`: Recorded that L5 and B2 left the loop at the `5b2ed1b` reset, and re-ran the guard script and the backend suite (55 passed) on 2026-10-19.
- `components/tailscale-subnet-router`: Recorded that its three tickets stopped at the `5b2ed1b` reset, and corrected the Evidence path to `.loop/plans/` and `.loop/verdicts/` at `48f52e2`.
- `components/terraform-roots`: Recorded that F8 was blocked when `5b2ed1b` reset the loop and that no deployer ticket is in the current loop.
- `components/vault-oidc-provider`: Pointed its source at `bootstrap/roles/nomad_server/tasks/main.yml`, the code that owns the Nomad `developer` policy.
- `components/vault-secrets-engines`: Corrected the claim that no Nomad management token reaches Terraform: every infrastructure run mints one through `data.vault_nomad_access_token.manage` and keeps it in state. Marked R3 as blocked at the reset, and recorded that firebat is missing from the Redis firewall rule.
- `components/workload-identity-chain`: Added MinIO as a verifier: loki, tempo and the registry trade a `minio` identity for keys through `AssumeRoleWithWebIdentity`, while memex still reads a static key.
- `practices/edge-certificate-names`: Pointed sources at `acme.hcl`, `variables.tf` and `haproxy.hcl`, and named the code site that asks for nothing deeper than one label.
- `practices/jetson-orin-nano-flashing`: Added sources, stated that no count or measurement backs these notes, linked the jetson node, and fixed a garbled line.
- `practices/openviking-vision-models`: Recorded that the VLM is now `gemini/gemini-3.5-flash-lite` (`66bed3c`) and that `VISION_MODELS` caught its own gap, pointed sources at the config check and `ov.conf.json`, and set `stale_after`.
- `practices/plan-premise-sweep`: Added sources and a section on what changed since: the old `.loop/` paths are gone, F10 set Nomad's `oidc_issuer`, memex now verifies Nomad workload JWTs, and F9's policy is in the repo.
- `practices/terraform-write-only-credentials`: Recorded that the measured chain was deleted in `19c1696`, and named a current site with the warned-against shape: the Redis engine's admin password in `database.tf` is in state.
- `practices/ufw-rules-outside-user-rules`: Recorded that since `fef7eee` the infrastructure root re-asserts its rules on every apply while the applications root does not, and that neither root has a destroy provisioner.
- `practices/vault-totp-enrollment`: Added sources, the PNG magic-byte check and the CLI's lookup order, and set `stale_after` with a note to re-measure after a Vault upgrade.
- `proposals/bootstrap-credential-rotation`: Re-confirmed it is not built, corrected where the tailscale `BackendState` guard is, and added sources.
- `proposals/openviking-dashboard`: Pointed at the `ov-dash` concept and recorded the moved anchors, the current image provenance and that OV2 closed done.
- `proposals/postgres-dynamic-credentials`: Recorded that the PoC file is gone, memex still uses a static password and Redis is the only database engine, and added sources.
- `proposals/postgres-nats-cdc-bridge`: Recorded three jobspec errors (datacenter `localstack`, the registry that now exists, and who can read memex's password), and added sources.
- `proposals/riscv-worker-node`: Added sources and fixed two premises: the cluster has five nodes, and Prometheus and Grafana run on `ubuntu`.
- `proposals/vault-login-mfa`: Added sources and a Built banner, since every resource and tool it lists is in the code, and updated its description.
- `components/minio`, `components/postgres`, `components/nats`: Marked M2, R3, R7, R8 and R2 as tickets that stopped at the `5b2ed1b` loop reset instead of live ones.
- `decisions/0014-keep-project-knowledge-in-an-okf-bundle`, `decisions/0001-durable-knowledge-lives-in-an-okf-bundle`: The operator chose to keep 0001, the written record, so 0014, the template `kmctl init` wrote, is superseded by it.
- `manifesto`: Wrote what the cluster is for, eleven invariants (ten enforced, each naming the passing test that pins it, and one planned) and a draft of values for the operator to approve.
- **Sources repointed** (every concept this change touches; the audit found these accurate against the code and changed nothing else: `components/bootstrap`, `components/embark`, `components/host-volumes`, `components/ov-dash`, `components/redis`, `components/vault-identity`, `nodes/jetson-orin-nano`, `nodes/orangepi4a`, `nodes/placement`, `nodes/radxa-dragon-q6a`, `nodes/ubuntu`): okf-reconcile step 1 pointed each `git:SHA:PATH` source at the plain path git tracks at HEAD, or at the file it was renamed to, and moved sources that cannot resolve (deleted paths, bare commits, `loop:` tickets) into an appended Evidence section.
- `summary`: Replaced the kmctl template with a distillation of the whole bundle in 457 words: the layers, the settled principles with their records, and what is open (the SeaweedFS replacement, Postgres dynamic credentials, the manifesto values awaiting the operator).
- Evidence wording (every concept named above with an Evidence line for a loop ticket): an old ticket's plan and any verdicts are under `.loop/` at commit `48f52e2`, not always under `.loop/archive/`. `components/minio`: R12 was dropped, not left a stub.
- Evidence wording (the same concepts): dropped the claim that `48f52e2` is the last commit before the reset, since three stamp commits follow it.

## 2026-10-20 (hermes-update)

- **Hermes runs hermes-agent v0.22.2** (`components/hermes`, `decisions/0019-hermes-openviking-plugin-built-into-the-image`): the OpenViking memory provider left the base image, so the image now copies the catalog plugin in at build time, pinned by commit, rather than fetching it at first start. `sessions.auto_prune: false` keeps ended sessions as 0.21 did. The staged (commented-out) memex job now names `ollama/deepseek-v4.1-flash`, since Bifrost 2.3.1 refuses the retired `deepseek-v4-flash:0731`; it takes effect only when memex is uncommented and applied.

## 2026-10-20 (minio-volume-destroy)

- **MinIO's data is deleted** (`components/minio`, `components/host-volumes`, `components/seaweedfs`, `components/container-registry`, `components/memex`, `nodes/orangepi4a`, `nodes/placement`, `summary`): with the operator's approval, `nomad_dynamic_host_volume.minio_data` was removed from `deployments/infrastructure/services.tf` and applied, deleting volume `cb07eebf` and MinIO's last data on orangepi4a. Everything durable was already in SeaweedFS and backed up in GCS. Loki's and Tempo's 30 days from before the cutover, which the operator chose not to migrate, and the frozen copies of the other buckets went with it. Every old MinIO key in Vault (`default/minio/*` and `default/<job>/minio`) was purged with all its versions. Nothing of MinIO remains on the cluster, and only the GCS prefix `minio/` keeps the name. ADR 0018 stays as written. The user doc `reference/monitoring` says the old logs and traces are gone.

## 2026-10-20 (minio-removal)

- **MinIO is removed** (`decisions/0018-remove-minio`, `components/minio`, `components/seaweedfs`, `components/terraform-roots`, `components/deployer-credentials`, `components/workload-identity-chain`, `components/nomad-oidc-discovery`, `components/edge-proxy`, `components/host-firewall`, `components/host-volumes`, `components/observability-pipeline`, `components/container-registry`, `architecture/deployment-layers`, `nodes/orangepi4a`, `nodes/placement`, `nodes/firebat`, `summary`): the `minio` job, its firewall entry, root key, dashboard, alert, scrape job, `minio.lab` route and Consul `service "minio"` grant are gone, and the applications root dropped every `minio_*` resource and `module.buckets` from state with `destroy = false`, then deleted the `aminueza/minio` provider and `modules/bucket`. The 9000 and 9001 ufw rules were deleted on orangepi4a by hand. Only the `minio_data` volume and its data remain, until the operator promotes `minio-volume-destroy`. `components/minio` is deprecated and kept as history. ADR 0018 records why the volume was not destroyed in the same step.
- **The backup job is `backup-s3`** (`components/gcs-backups`, `components/openviking-service`, `nodes/radxa-dragon-q6a`, `nodes/placement`, `manifesto`): renamed from `backup-minio`, with its keys at `default/backup-s3/seaweedfs` and `default/backup-s3/gcs`, and its GCS prefix still `minio/` so the history carries on. Its first run exited 0. The manifesto's I10 and I11 now name the renamed tests `test_s3_backup_syncs_declared_buckets` and `test_s3_backup_syncs_the_durable_buckets`.
- **ov-dash runs again** (`components/ov-dash`, `components/seaweedfs`, `nodes/orangepi4a`): started with `nomad job start ov-dash` once MinIO's memory was free.
- **memex needs a SeaweedFS bucket** (`components/memex`): its MinIO bucket and key went with MinIO, so bringing it back now needs a `memex` entry in `local.buckets` and a key first.
- User docs follow: the three MinIO keyless how-tos are replaced by `how-to/give-a-job-keyless-seaweedfs-access`, `how-to/give-an-aws-sdk-go-service-keyless-seaweedfs-access` and `how-to/exchange-a-workload-jwt-for-seaweedfs-credentials`, and `explanation/workload-identity` describes SeaweedFS as the S3 verifier, with MinIO as history.

## 2026-10-20 (seaweedfs-cutover)

- **Everything users touch points at SeaweedFS** (`components/gcs-backups`, `components/seaweedfs`, `components/minio`, `components/container-registry`, `components/openviking-service`, `components/edge-proxy`, `components/devcontainer`, `components/host-volumes`, `nodes/orangepi4a`, `summary`): `backup-minio` now syncs the four durable buckets from SeaweedFS with the read-only `backup` user's key at `default/backup-minio/seaweedfs`, into the same `minio/<bucket>/` GCS prefixes, and its first run exited 0. That closes the gap where new OpenViking and registry blobs had no off-site copy. The `s3` Consul tag moved from `minio` to `seaweedfs`, so the CLI's `s3` route resolves to SeaweedFS, and HAProxy's `s3.lab.orangecluster.nl` backend points at `192.168.2.29:8333`. The dash tile is `seaweedfs`, and the devcontainer's `mc` alias is `s3`, which `.env.example` documents with the SeaweedFS admin key. MinIO still runs with its data and the `minio.lab` console route, but nothing reads or writes it, until `minio-removal`. The user docs `reference/gcs-backups`, `reference/edge-routes`, `reference/cli-read-commands`, `how-to/run-a-backup-job-on-demand`, `explanation/backup-job-credentials` and `explanation/workload-identity` say the same.

## 2026-10-20 (seaweedfs-cutover-registry)

- **The registry stores in SeaweedFS** (`components/container-registry`, `components/seaweedfs`, `components/minio`, `components/workload-identity-chain`, `components/gcs-backups`, `components/edge-proxy`, `architecture/deployment-layers`, `nodes/orangepi4a`, `nodes/ubuntu`, `nodes/firebat`, `summary`): the OCI registry now keeps its blobs in SeaweedFS's `registry` bucket and logs in with a `seaweedfs` identity through `local/s3-creds.sh`, which names the `registry` role. Both the helper and `regionendpoint` take the address from Consul, so the literal `192.168.2.29:9000` is gone. No workload uses MinIO now: only `backup-minio` reads it, until `seaweedfs-cutover`. The bucket came back through `restore-s3`, and the 725 zero-byte `dir/` markers the restore wrote were deleted, since the registry never had them. All 33 tags read back unchanged and a new push worked.

## 2026-10-20 (seaweedfs-cutover-openviking)

- **OpenViking moved to SeaweedFS** (`components/openviking-service`, `components/seaweedfs`, `components/minio`, `components/host-volumes`, `nodes/orangepi4a`): OpenViking's blobs are now in SeaweedFS's `openviking` bucket, reached through Consul service `seaweedfs` with a static key from `default/openviking/seaweedfs`, because its AGFS `s3fs` client carries no session token. Its MinIO key is still minted and no longer used.
- **Bucket restore is built and proven** (`components/gcs-backups`, `components/terraform-roots`, `nodes/radxa-dragon-q6a`, `nodes/placement`, `summary`): Recorded the parameterized `restore-s3` job, its keys in both roots, its exit codes, the `dispatch-job` capability the Nomad `deploy` policy gained for it, and that it restored `openviking` with identical tree and file hashes. Replaced the "restore is unproven" trap, which now holds only for the Postgres dump, and recorded that the nightly backup still reads MinIO, so OpenViking's new blobs have no off-site copy until `seaweedfs-cutover`.

## 2026-10-20 (seaweedfs-cutover-observability)

- **Loki and Tempo store in SeaweedFS** (`components/seaweedfs`, `components/observability-pipeline`, `components/workload-identity-chain`, `components/minio`, `components/host-volumes`, `architecture/deployment-layers`, `nodes/orangepi4a`, `nodes/firebat`, `summary`): both jobs now write to empty `loki` and `tempo` buckets on SeaweedFS and log in with a `seaweedfs` identity, tempo through `AWS_ROLE_ARN` and loki through `local/s3-creds.sh`. Old logs and traces stay in MinIO, unmigrated by operator decision. Grafana gained a SeaweedFS dashboard, the `SeaweedFSDown` and `SeaweedFSDiskError` alerts, and `seaweedfs` in `ScrapeJobMissing`. The registry still uses MinIO.

## 2026-10-20 (seaweedfs-workload-identity)

- **SeaweedFS takes workload identities** (`components/seaweedfs`, `components/workload-identity-chain`, `decisions/0017-seaweedfs-keyless-roles-bound-per-job`): tempo, loki and registry each get a SeaweedFS role bound to their own job id and sub, with audience `seaweedfs`. Claim mode is ruled out because SeaweedFS splits the claim on commas. Proven live with throwaway probe jobs, which were then purged.

## 2026-10-19 (seaweedfs-service)

- **SeaweedFS stands beside MinIO** (`components/seaweedfs`, `decisions/0016-seaweedfs-replaces-minio`): MinIO's pinned image no longer downloads, so the cluster's S3 store moves to SeaweedFS. This change runs the server only, with the flags its spikes proved, and records why SeaweedFS was chosen over Garage and over building MinIO from source.
- **Hermes recall outwaits OpenViking search** (`components/hermes`): plugin 2.1.1's recall defaults (3s per request, 4s total) are shorter than our search/find, so recall timed out on most turns; the config now sets 10s and 12s.
- **Hermes recall budget fits under its 8s limit** (`components/hermes`): the 12s/10s budget from the previous entry could never take effect, because Hermes drops recall at 8s; now 7.5s with abstracts only.

## 2026-10-20

- Added `decisions/0020-agents-use-openviking-through-tools-only` with `kmctl new decision`.
- **Hermes and Claude Code use OpenViking through tools only** (`components/hermes`, `decisions/0020-agents-use-openviking-through-tools-only`, `summary`): Hermes now runs the `openviking_tools` wrapper, which keeps the six `viking_*` tools and turns off recall, turn sync, session commits, startup recovery and memory mirroring, and `SOUL.md` lost its Session Bootstrap and Auto-Capture Protocol. The recall-budget trap is gone with recall. Claude Code's memory plugin comes out, per the rewritten how-to. The summary still holds and was acked.
- Added `decisions/0021-openviking-starts-over-on-a-v2-store` with `kmctl new decision` (numbered 0021 because 0020 went to the tools-only decision).
- **OpenViking starts over on a v2 store** (`decisions/0021-openviking-starts-over-on-a-v2-store`, `components/openviking-service`, `components/openviking-database`, `summary`): OpenViking now runs on bucket `openviking-v2`, schema `openviking_v2` and volume `openviking_data_v2` as `lab`/`jasper`. The `openviking` storage user's policy moved to the new bucket, so its key cannot reach the old one, and the old bucket, schema and volume stay as a read-only backup. Schema `openviking_v2` is created by hand before the first boot, and no account is created. veerle's consumer entry is gone.
- **Both OpenViking buckets are backed up** (`components/gcs-backups`, `components/seaweedfs`): `openviking-v2` joins the durable buckets with its own sync line to `minio/openviking-v2/` and an entry in the restore allowlist, and a test checks no other bucket writes that prefix.
- **The workspace volume is new** (`components/host-volumes`, `nodes/radxa-dragon-q6a`, `nodes/placement`): `openviking_data_v2` on radxa holds OpenViking's workspace, and `openviking_data` stays unmounted as part of the backup. The user docs `reference/openviking`, `explanation/openviking-identity` and `how-to/roll-out-vault-login-mfa` drop veerle as a live consumer, and `reference/gcs-backups` and `how-to/run-a-backup-job-on-demand` list five durable buckets.
- **I11 names five durable buckets** (`manifesto`): `openviking-v2` joins the list the invariant names, matching the test that pins it.
- **Review fixes for ov-fresh-instance** (`components/openviking-database`): the schema note says `ov.conf.json` now names `openviking_v2`.
- Added `decisions/0023-hermes-saves-from-a-skill-owned-map-of-roots` with `kmctl new decision`.
- **Hermes saves through a skill and a map** (`components/hermes`, `decisions/0023-hermes-saves-from-a-skill-owned-map-of-roots`, `decisions/0019-hermes-openviking-plugin-built-into-the-image`): the `save-to-openviking` skill files links, files, notes and voice transcripts under `viking://user/jasper/resources/` from a map of roots it owns, and asks when no place is given. The `openviking_tools` wrapper gains `viking_write` and sends `create_parent` on saves that name a parent. The image (`0.22.2-3`) bakes in faster-whisper, and ADR 0019 gets a correction saying so. The summary still holds and was acked.
- **Review fixes for ov-save-skill** (`components/hermes`): the skill paragraph now cites what spike 9 measured with the `SOUL.md` line, not an unmeasured claim about running without it.
- Added `decisions/0022-openviking-carry-over-copies-storage-and-re-indexes` with `kmctl new decision`.
- **The kept OpenViking trees carry over by a storage copy and a re-index** (`decisions/0022-openviking-carry-over-copies-storage-and-re-indexes`, `components/openviking-service`, `components/seaweedfs`, `summary`): the dispatched `ov-carry-over` job copies clips, blogs, leo and blog-scraper (into `blogs/`) from `openviking` to `openviking-v2` with a key that cannot write the old bucket, and `scripts/ov_carry_over.py` regenerates the merged blog directories, runs `vectors_only`, copies the old image rows and checks the result. Pack export was rejected because it needs the old instance running. The user docs `how-to/carry-the-kept-trees-over-to-the-new-openviking` and `reference/openviking` cover running it.
- **Review fixes for ov-carry-over** (`decisions/0022-openviking-carry-over-copies-storage-and-re-indexes`, `components/openviking-service`, `summary`): the script regenerates only the eight blog directories that hold files from both trees, not ten, since an overview has nothing to say about an empty folder. To stay under 500 words, the summary's SeaweedFS bullet dropped two MinIO details that `components/seaweedfs` and `decisions/0018-remove-minio` still hold: which data read back intact, and that `minio_data` was deleted.

## 2026-10-21

- Added `handoffs/openviking-reset-aim-to-apm-migration-ci-tailnet-access` with `kmctl new handoff`.

## 2026-10-28

- Added `decisions/0024-the-devcontainer-reads-the-host-openviking-login-through-a-read-only-mount` with `kmctl new decision`.
- Added `decisions/0025-the-agent-guidelines-stay-in-agents-md` with `kmctl new decision`.

## 2026-11-15

- Added `decisions/0026-repo-docs-reach-openviking-through-a-webhook-receiver-a-jetstream-queue-and-a-consumer` with `kmctl new decision`.
- **Repo docs sync from the ov-sync bucket into OpenViking** (`decisions/0026-repo-docs-reach-openviking-through-a-webhook-receiver-a-jetstream-queue-and-a-consumer`, `components/ov-sync-consumer`, `components/seaweedfs`, `components/nats`, `nodes/placement`, `nodes/orangepi4a`, `nodes/radxa-dragon-q6a`, `summary`): the `ov-sync-consumer` ticket adds a Go receiver as a prestart sidecar that owns the seaweedfs group's network namespace, the `OV_SYNC` JetStream stream, and a consumer on radxa that applies each file's current state to OpenViking. ADR 0026 records the rejected `gocdk_pub_sub` notifier, the rejected listener outside SeaweedFS's namespace, and the rejected receiver-joins-SeaweedFS layout. The SeaweedFS page gains the receiver and the eighth bucket, the NATS page its first user, the node pages the two jobs. To stay under 500 words the summary dropped its line on loop tickets dropped at the `5b2ed1b` reset.
- **ov-sync-consumer review round 1** (`components/ov-sync-consumer`): the OpenViking client now holds one shared limit of `POOL_SIZE` per request, so catch-up no longer adds a request beyond the pool, and catch-up lists OpenViking one folder at a time, following `has_more`, instead of one recursive `fs/ls` that stops at three levels and 1000 entries.
- Added `decisions/0027-ci-reaches-the-lab-through-a-public-lab-auth-action-and-per-caller-vault-roles` with `kmctl new decision`.
- **GitHub Actions reach the lab through lab-auth** (`decisions/0027-ci-reaches-the-lab-through-a-public-lab-auth-action-and-per-caller-vault-roles`, `components/tailscale-subnet-router`, `components/vault-identity`, `architecture/deployment-layers`, `summary`): the `ci-tailscale-access` ticket adds the composite action `.github/actions/lab-auth`, the `jwt-github` Vault mount with one role per `var.vault_ci_callers` entry, and the manual `lab-auth-check` workflow. ADR 0027 records the rejected separate actions repository, glob role on `repository_owner`, self-hosted runner and stored secrets. The subnet router page gains the `tag:ci` grant, the federated identity and a read-only copy of the saved tailnet policy, the Vault identity page the new mount, the deployment layers page the mount in the infrastructure root. To stay under 500 words the summary shortened its MinIO, Postgres, practices and open-gaps lines.
- Added `decisions/0028-ci-syncs-repo-folders-to-a-shared-ov-sync-bucket-with-a-manifest-and-a-vault-identity-token-swapped-at-seaweedfs-sts` with `kmctl new decision`.
- Moved `decisions/0028-ci-syncs-repo-folders-to-a-shared-ov-sync-bucket-with-a-manifest-and-a-vault-identity-token-swapped-at-seaweedfs-sts` to `decisions/0028-ci-syncs-repo-folders-to-ov-sync-with-a-manifest-and-a-vault-identity-token` with `kmctl mv`, rewriting links to it in `decisions/index`.
- **CI syncs repo folders to ov-sync** (`decisions/0028-ci-syncs-repo-folders-to-ov-sync-with-a-manifest-and-a-vault-identity-token`, `components/seaweedfs`, `components/vault-identity`, `architecture/deployment-layers`, `summary`): the `ci-openviking-sync` ticket adds the `openviking-sync` action and workflow, an optional `ov_sync` flag on `var.vault_ci_callers`, one Vault identity-token role and token policy per such caller, and SeaweedFS's `vault` OIDC provider with one prefix-scoped role and policy per caller. ADR 0028 records the manifest, the token-to-STS credential and the rejected static key per caller, SeaweedFS trusting GitHub directly, and cache or artifact state. The SeaweedFS page gains the CI roles, the Vault identity page the token policy, the deployment layers page the per-caller policy, and the summary's ov-sync line names the CI half; to stay under 500 words the summary shortened its project, CLI, practices and status lines.
- Added `handoffs/bifrost-decision-models-ci-lab-auth-and-openviking-doc-sync-design` with `kmctl new handoff`.
- Updated `handoffs/bifrost-decision-models-ci-lab-auth-and-openviking-doc-sync-design` with `kmctl new handoff --key`.

## 2026-11-16

- Updated `handoffs/bifrost-decision-models-ci-lab-auth-and-openviking-doc-sync-design` with `kmctl new handoff --key`.
- Added `decisions/0029-bifrost-routes-by-complexity-for-one-virtual-key-and-adds-jev` with `kmctl new decision`.
- Added `decisions/0030-ov-sync-stores-images-in-openviking-per-file-folders` with `kmctl new decision`.
- Corrected `decisions/0029-bifrost-routes-by-complexity-for-one-virtual-key-and-adds-jev` and updated `components/bifrost`: router routing rules at priorities 10 to 13, after the hand-made Claude Code rules at 0 to 3.

## 2026-11-18

- Added `decisions/0031-the-lab-auth-action-picks-the-tailscale-identity-from-the-oidc-subject-format` with `kmctl new decision`.
- Updated `components/ov-dash`: the pinned image is now 0.7.0, which folds front matter away and loads the Files tree one folder at a time (openviking_extensions PR #22).

## 2026-11-19

- Added `handoffs/passwordless-postgres-ticket-planning` with `kmctl new handoff`.

## 2026-11-23

- Added `decisions/0032-summarize-openviking-content-with-inkling-2-small` with `kmctl new decision`.
- Added `prototypes/openviking-summary-model` with `kmctl new prototype`.
- Updated `practices/openviking-vision-models`: the vlm block now names `ollama/inkling-2-small`, measured 2026-11-23, and accepting an image is not reading it (gemma4:31b misread identifiers). Wrote `decisions/0032-summarize-openviking-content-with-inkling-2-small` and `prototypes/openviking-summary-model` with the evidence.
- Added `decisions/0033-networkmanager-nodes-get-public-fallback-resolvers` with `kmctl new decision`.
- Corrected `decisions/0033-networkmanager-nodes-get-public-fallback-resolvers`: the DNS play moved to `bootstrap/playbooks/configure_dns.yml`. Updated `nodes/radxa-dragon-q6a`, `nodes/orangepi4a`, `components/bootstrap` and `components/host-firewall` to match.
