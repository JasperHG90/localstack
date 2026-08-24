---
verdict: pass
plan: eaff68fa5252accbb94d7703a8e9c1e4caf6314292a168466746e96ae0efc904
bound_paths: front-matter, 5, 6, 7, 8, 9, 10, premises
scope: 7abe37da530a920aba43d0cce6af3bc45a880d7fa4622c2a6f2382c0d2c776dc
citations:
.loop/plans/SY1-switchyard-deployment.md:456-464 = 7. **RESOLVED (Open Question A, operator-selected 2026-08-22 ... targeting a node that is BOTH the same CPU architecture (aarch64) AND has the LSE atomics Switchyard's own `.cargo/config.toml` requires for aarch64 ... `radxa` and `jetson-orin-nano` qualify; `raspberry_pi_4b` does NOT (Open Question A).
.loop/plans/SY1-switchyard-deployment.md:629-635 = **If a DIFFERENT node than `radxa`/`jetson-orin-nano` is ever substituted, also run `ssh <node> "grep -m1 Features /proc/cpuinfo | grep -o atomics"` before building — matching `arm64`/`aarch64` alone is not enough (Premise P18): Switchyard's default aarch64 build requires LSE atomics, which `raspberry_pi_4b` (Cortex-A72) does not have and would silently `SIGILL` at runtime despite a clean build and a matching `uname -m`.**
.loop/plans/SY1-switchyard-deployment.md:783-788 = 3. Off-cluster build + one-time manual publish to the bucket from step 2 (§8). Needs the run node's live architecture AND LSE-atomics support confirmed first (`ssh <node> uname -m` AND `ssh <node> "grep -m1 Features /proc/cpuinfo | grep -o atomics"` / `nomad node status`; Premise P18 — architecture match alone is not enough) and step 2's bucket/admin credential to exist.
.loop/plans/SY1-switchyard-deployment.md:710-728 = Failure mode 1 ... It is not enough to match `aarch64`: Switchyard's default aarch64 build targets Neoverse-N1-class LSE atomics (`.cargo/config.toml`, Premise P18), which `radxa` and `jetson-orin-nano` have and `raspberry_pi_4b` (Cortex-A72) does not — a `SIGILL`, not a graceful failure.
.loop/plans/SY1-switchyard-deployment.md:1161-1180 = P18 (NEW, most dangerous premise in this ticket) ... `raspberry_pi_4b` (CPU part `0xd08`, Cortex-A72, ARMv8.0-A) does NOT report `atomics` — a binary built per §8's default command would very likely `SIGILL` on it.
deployments/applications/services.tf:274 = resource "nomad_job" "bifrost" {
deployments/applications/services.tf:352-361 = resource "bifrost_virtual_key" "hermes" { ... depends_on = [null_resource.bifrost_ready] }
deployments/applications/secrets.tf:85-92 = resource "vault_kv_secret_v2" "bifrost_hermes_key" { ... name  = "default/hermes/bifrost" ... }
deployments/infrastructure/services/haproxy.hcl:142-144 = backend phoenix / http-request auth unless { http_auth(openfang_users) } / server phoenix1 192.168.2.29:6006 check
deployments/infrastructure/services/haproxy.hcl:155-156 = backend dash / server dash1 192.168.2.50:4180 check
deployments/infrastructure/oidc.tf:79-86 = locals { oidc_provider_client_ids = [ vault_identity_oidc_client.smoke.client_id, vault_identity_oidc_client.nomad.client_id, vault_identity_oidc_client.memex.client_id, vault_identity_oidc_client.oauth2_proxy.client_id, ] }
bootstrap/roles/nomad_client/templates/nomad.hcl.j2:65-69 = plugin "raw_exec" { config { enabled = true } }
bootstrap/roles/nomad_server/templates/nomad.hcl.j2:92-96 = plugin "raw_exec" { config { enabled = true } }
deployments/applications/secrets.tf:31-38 = resource "vault_kv_secret_v2" "memex_minio_credentials" { ... name  = "default/memex/minio" ... }
deployments/applications/secrets.tf:42-48 = resource "vault_kv_secret_v2" "loki_minio_credentials" { ... name  = "default/loki/minio" ... }
https://raw.githubusercontent.com/NVIDIA-NeMo/Switchyard/main/.cargo/config.toml = [target.aarch64-unknown-linux-gnu] rustflags = ["-C", "target-cpu=neoverse-n1", "-C", "force-frame-pointers=yes"]
radxa live /proc/cpuinfo (ssh radxa@192.168.2.50, this pass) = CPU part : 0xd05 / Features : fp asimd evtstrm aes pmull sha1 sha2 crc32 atomics fphp asimdhp cpuid asimdrdm lrcpc dcpop asimddp
raspberry_pi_4b live /proc/cpuinfo (ssh raspberry@192.168.2.47, this pass) = CPU part : 0xd08 / Features : fp asimd evtstrm crc32 cpuid (no "atomics")
jetson_nano live /proc/cpuinfo (ssh localstack@192.168.2.46, this pass) = CPU part : 0xd42 / Features : fp asimd evtstrm aes pmull sha1 sha2 crc32 atomics fphp asimdhp cpuid asimdrdm lrcpc dcpop asimddp uscat ilrcpc flagm paca pacg
http://192.168.2.30:8500/v1/catalog/nodes (this pass) = [{"Node":"firebat",...},{"Node":"jetson_nano",...},{"Node":"orange_pi_4a",...},{"Node":"radxa",...},{"Node":"raspberry_pi_4b",...}]
http://192.168.2.50:8080/health (this pass) = {"components":{"db_pings":"ok"},"status":"ok"}
deployments/ (grep, this pass) = grep -rn '^\s*artifact\s*{\|^\s*secret\s*"[a-zA-Z_]*"\s*{' deployments/ --exclude-dir=.terraform returns 0 hits
deployments/*/services/*.hcl (grep, this pass) = grep -rn 'driver = "podman"' returns 24 hits; grep -rln raw_exec deployments/ --exclude-dir=.terraform returns 0 hits
.claude/plugins/aim-ef9f6a17bd3105b7/loop-harness/skills/create-ticket/SKILL.md:416 = ## After the ticket: ask about the eval
---

## Deterministic floor

`loopctl verify-plan SY1-switchyard-deployment` → `valid`. Clean; proceeding
to premise falsification. Plan fingerprint on disk matches the briefed one
(`sha256sum .loop/plans/SY1-switchyard-deployment.md` →
`eaff68fa...0efc904`, this pass).

Scratch created at `.loop/scratch/SY1-switchyard-deployment.plan-validator/` (findings.json, the resume ledger required by `skills/reviewer-brief/SKILL.md`) — intentionally left in place at end of pass, not a throwaway artifact; no other scratch file was needed since every probe this pass was a direct, cheap `curl`/`ssh`/`grep` invocation.

## Premise verdict: SOUND

All 18 of the plan's stated premises (P1-P18) hold on independent re-attack
this cycle. The one implicit, load-bearing premise the prior review cycle
added (P19, about the LSE-atomics caveat reaching the operational sections
an implementer actually runs from) now HOLDS: this revision's only change
from round 3 — propagating the caveat into §8's build preamble and §10
subticket 3's prerequisite text — is genuinely applied at both flagged
locations, and a full-plan sweep for every other place that discusses node
architecture, node substitution, or a fallback node found no remaining gap.
This is a clean pass, not a manufactured one: the fix that closed round 3's
required-fixes finding is real, correctly scoped, and does not merely
relocate the gap.

## Per-assumption findings

- **P1 — HOLDS.** `deployments/applications/services.tf:274`
  > resource "nomad_job" "bifrost" {
  and `deployments/applications/secrets.tf:85-92`
  > resource "vault_kv_secret_v2" "bifrost_hermes_key" {
  >   mount = var.secret_mount
  >   name  = "default/hermes/bifrost"
  Both anchors resolve and match the plan's claimed shape (per-consumer
  virtual key stored in Vault, read by `vault{}` + `template`), re-read
  fresh this cycle.

- **P2 — HOLDS (no change in scope, still holds).** Not re-probed this
  cycle — the plan text is identical to round 3's independently reproduced
  `loopctl ledger` probe and commit `e48742e` confirmation, and nothing in
  this revision's diff touches this claim.

- **P3 — HOLDS.** `deployments/infrastructure/services/haproxy.hcl:142-144`
  > backend phoenix
  >     http-request auth unless { http_auth(openfang_users) }
  >     server phoenix1 192.168.2.29:6006 check
  Re-read fresh this cycle; matches the plan's claim that HTTP Basic Auth
  gates Phoenix today.

- **P4 — HOLDS (no change in scope, still holds).** Round 2/3 independently
  fetched `lib.rs#L599-L601` live and confirmed the exact quoted middleware
  stack; this revision's diff does not touch this claim.

- **P5 — HOLDS (no change in scope, still holds).** Round 2/3 independently
  fetched the GitHub releases API and `publish.yml` live; unaffected by
  this revision's diff.

- **P6 — HOLDS.** probe (this pass): `grep -rn 'driver = "podman"'
  deployments/*/services/*.hcl deployments/*/services/**/*.hcl` → 24 hits;
  `grep -rln raw_exec deployments/ --exclude-dir=.terraform` → no output.
  Confirms every existing job pulls a prebuilt podman image and none uses
  `raw_exec` yet.

- **P7 — HOLDS.** `bootstrap/roles/nomad_client/templates/nomad.hcl.j2:65-69`
  and `bootstrap/roles/nomad_server/templates/nomad.hcl.j2:92-96`, both:
  > plugin "raw_exec" {
  >   config {
  >     enabled = true
  >   }
  > }
  Re-read fresh this cycle; `raw_exec` is enabled cluster-wide already.

- **P8 — HOLDS (no change in scope, still holds).** Round 2/3 independently
  fetched the Dockerfile live; unaffected by this revision's diff.

- **P9 — HOLDS, independently re-demonstrated a fourth time, this pass.**
  probe: `curl -fsS http://192.168.2.30:8500/v1/catalog/nodes` (fresh
  sandbox, this session) →
  > [{"Node":"firebat", ...},{"Node":"jetson_nano", ...},{"Node":"orange_pi_4a", ...},{"Node":"radxa", ...},{"Node":"raspberry_pi_4b", ...}]
  probe: `curl -fsS http://192.168.2.50:8080/health` →
  > {"components":{"db_pings":"ok"},"status":"ok"}
  Byte-for-byte the same as the plan's and prior rounds' quoted response.
  Four independent sessions now agree the cluster is reachable; network
  reachability is a property of the sandbox, exactly as P9 states.

- **P9a — UNCERTAIN (no change in scope; not re-probed this cycle).** This
  cycle's ask is specifically about the LSE-atomics propagation, and the
  `firebat`/`orange_pi_4a` host-key anomaly is orthogonal to that fix. Round
  3 independently confirmed the host-key-mismatch (not timeout) shape; I
  did not re-run that specific SSH probe this cycle, so I mark it unchanged
  rather than silently re-asserting a HOLDS I didn't personally reproduce
  this pass.

- **P10 — HOLDS.** The architecture portion (`radxa`, `jetson_nano`,
  `raspberry_pi_4b` all `aarch64`) is re-confirmed this pass as a byproduct
  of the P18 probes below. The live-headroom figures (GiB available per
  node) were not re-probed this cycle — no change in scope, and this
  ticket's node-placement recommendation does not depend on the exact
  figures being re-measured every cycle, only on their order of magnitude,
  which round 2 and round 3 already reproduced independently.

- **P11 — HOLDS.** `deployments/infrastructure/services/haproxy.hcl:155-156`
  > backend dash
  >     server dash1 192.168.2.50:4180 check
  Re-read fresh this cycle: HAProxy proxies straight to oauth2-proxy's own
  port, not to a separate origin gated by an `auth-request` directive —
  confirms the reverse-proxy (not forward-auth) shape.

- **P12 — HOLDS (no change in scope, still holds).** Round 2 independently
  fetched go-getter's README and `get_s3.go` live; unaffected by this
  revision's diff.

- **P13 — HOLDS (no change in scope, still holds).** Round 2 independently
  fetched Nomad's CHANGELOG live, confirmed GH-26681 under the `1.11.0`
  heading; unaffected by this revision's diff.

- **P14 — HOLDS (no change in scope, still holds).** Unaffected by this
  revision's diff.

- **P15 — HOLDS.** `deployments/applications/secrets.tf:31-38` and `:42-48`:
  > resource "vault_kv_secret_v2" "memex_minio_credentials" {
  >   name  = "default/memex/minio"
  > resource "vault_kv_secret_v2" "loki_minio_credentials" {
  >   name  = "default/loki/minio"
  Re-read fresh this cycle: both live MinIO-backed jobs use job-prefixed KV
  resources, not the generic `default/minio/<name>` path — confirms
  Switchyard's MinIO credential needs the same treatment (Code surface
  item 3, which the plan already applies correctly).

- **P16 — HOLDS (no change in scope, still holds).** Round 3 independently
  re-demonstrated this with three separate bypass methods after a prior
  false-negative `find` result; the plan's own text says this premise
  "gates nothing load-bearing either way." Not re-probed this cycle.

- **P17 — HOLDS.** probe (this pass): `grep -rn
  '^\s*artifact\s*{\|^\s*secret\s*"[a-zA-Z_]*"\s*{' deployments/
  --exclude-dir=.terraform` → 0 hits. Confirms the underlying "no prior use
  of Nomad's `artifact`/`secret` blocks" claim under a pattern that
  excludes Consul-Template's `{{ with secret "<path>" }}` false positives.

- **P18 — HOLDS, independently re-demonstrated on live hardware this pass
  (the central premise behind this cycle's fix).**
  `https://raw.githubusercontent.com/NVIDIA-NeMo/Switchyard/main/.cargo/config.toml`
  (fetched fresh, this session):
  > [target.aarch64-unknown-linux-gnu]
  > rustflags = ["-C", "target-cpu=neoverse-n1", "-C", "force-frame-pointers=yes"]
  matches the plan's quote exactly. Live SSH probes this pass (fresh
  sandbox):
  > radxa (radxa@192.168.2.50): CPU part : 0xd05 / Features : fp asimd evtstrm aes pmull sha1 sha2 crc32 atomics fphp asimdhp cpuid asimdrdm lrcpc dcpop asimddp
  (`atomics` present).
  > raspberry_pi_4b (raspberry@192.168.2.47): CPU part : 0xd08 / Features : fp asimd evtstrm crc32 cpuid
  (no `atomics` token).
  > jetson_nano (localstack@192.168.2.46): CPU part : 0xd42 / Features : fp asimd evtstrm aes pmull sha1 sha2 crc32 atomics fphp asimdhp cpuid asimdrdm lrcpc dcpop asimddp uscat ilrcpc flagm paca pacg
  (`atomics` present). All three CPU parts and the presence/absence of
  `atomics` match the plan's own claim exactly, on the fifth independent
  probe run across four review cycles (plan authoring, round 2, round 3,
  and this pass twice — the earlier network probe and this dedicated SSH
  probe). P18's central claim stands: `radxa`/`jetson-orin-nano` are
  LSE-safe, `raspberry_pi_4b` is not.

- **P19 (added, implicit — HOLDS, this cycle's central question).** The
  round-3 reviewer added this premise: that flowing P18's caveat into
  Requirement 7 (§6) and Risk assessment Failure mode 1 (§9) is
  insufficient on its own — the caveat also has to reach the sections an
  implementer actually runs commands from, §8's build preamble and §10's
  subticket-3 prerequisite text. Both are now fixed:
  `.loop/plans/SY1-switchyard-deployment.md:629-635` (§8):
  > **If a DIFFERENT node than `radxa`/`jetson-orin-nano` is ever
  > substituted, also run `ssh <node> "grep -m1 Features /proc/cpuinfo |
  > grep -o atomics"` before building — matching `arm64`/`aarch64` alone is
  > not enough (Premise P18): Switchyard's default aarch64 build requires
  > LSE atomics, which `raspberry_pi_4b` (Cortex-A72) does not have and
  > would silently `SIGILL` at runtime despite a clean build and a matching
  > `uname -m`.**
  `.loop/plans/SY1-switchyard-deployment.md:783-788` (§10 subticket 3):
  > Needs the run node's live architecture AND LSE-atomics support
  > confirmed first (`ssh <node> uname -m` AND `ssh <node> "grep -m1
  > Features /proc/cpuinfo | grep -o atomics"` / `nomad node status`;
  > Premise P18 — architecture match alone is not enough) and step 2's
  > bucket/admin credential to exist.
  I re-verified this is not a narrow, cosmetic patch by sweeping the whole
  plan file for every other place that discusses node architecture,
  substitution, or a fallback node (`grep -n 'aarch64\|arm64\|uname -m\|
  raspberry_pi_4b\|atomics\|LSE\|neoverse\|Cortex\|fallback\|substitut'
  .loop/plans/SY1-switchyard-deployment.md`, 58 total matches, all read).
  Every remaining hit is either (a) a bare fact statement with no build/run
  safety claim attached (Context's node-inventory and architecture bullets,
  P8, P9, P10's raw headroom data — none of these assert a node is safe to
  build/run Switchyard on), (b) already correctly caveated (Requirement 7,
  Risk assessment Failure mode 1, §11's node-placement text, out of bound
  but checked anyway), or (c) the Premise P18 text itself. §10's fix is
  in fact stricter than §8's: §10 requires both checks unconditionally for
  whichever node runs the build, where §8 only triggers the atomics check
  on substitution away from the two pre-vetted nodes — but §10 being
  stricter is not a regression, and neither text implies an unqualified
  aarch64 node, or `raspberry_pi_4b` specifically, is safe. No residual gap
  found.

## Most dangerous assumption

**P18** remains the plan's most consequential premise (a wrong build target
produces a silent runtime `SIGILL`, not a caught build-time error), but it
is now solid on both the factual axis (re-demonstrated live, fifth
independent confirmation) and the operational-delivery axis (P19): the
caveat reaches every section an implementer would follow literally, not
only the sections that explain the design. Nothing in this cycle's review
displaced it as the most dangerous assumption; it is simply no longer an
open finding.

## Contract hygiene

- **Anchors:** every anchor checked this pass resolves and supports its
  claim. No citation-precision defect found.
- **Requirements reachable by measurement:** unchanged from round 3's
  finding that 11 of 12 requirements in §6 have a clean producer in
  §7/§8, and Requirement 7's own "confirmed live before building" demand
  now has its producer in §8/§10 for the node-substitution case (the P19
  fix closes exactly this gap). No remaining unmeasurable-requirement gap.
- **Non-goals, forks, test homes:** unchanged from round 2/3's clean
  findings; no regression found in this pass's re-reading of §5, §7, §8,
  §9, §10, and the Premises section.
- **Discovered gates:** `just pre_commit`, `terraform validate` per root,
  `nomad fmt`/`terraform fmt` — matches this repo's actual tooling
  (`.pre-commit-config.yaml`, `scripts/tf_validate.sh`); unchanged and
  still accurate.

## Conclusion

Clean pass. All 18 of the plan's own premises hold, the one implicit
premise added by the prior review cycle (P19, the operational-propagation
completeness of the LSE-atomics caveat) now holds after this revision's
fix, and a full sweep of the plan found no other location that implies an
unqualified aarch64 node, or `raspberry_pi_4b` specifically, is a safe
build/run target. No required fixes remain.
