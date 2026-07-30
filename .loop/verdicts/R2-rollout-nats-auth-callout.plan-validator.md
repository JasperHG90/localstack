---
verdict: fail
---

# Plan review — R2-rollout-nats-auth-callout (pass `plan-validator`)

Plan fingerprint verified with `sha256sum` at review time:
`48c91e3e5929b0d78c72c8e8785efc61fdaef9a2395456f86a650438495a868a`
(matches the briefing). The `plan:` line is deliberately omitted: this is a
`fail` and must not authorize the `PLANNING -> READY` flip.

## Premise verdict: BROKEN

Gate verdict: **fail**.

Seven load-bearing assumptions BREAK, two are UNCERTAIN. Three of the breaks
are structural rather than cosmetic: the packaging target does not exist, the
key-provisioning pattern cannot produce the key it is asked to produce, and
the plan's own resolved fork contradicts its gates, code surface and eval
marker. The claim the plan leans on for its client-side acceptance contract
was supposed to be established by spike S3, which was dropped and never ran.

## Load-bearing assumptions

### P1 — NATS runs 2.10 today and auth callout exists at that version. HOLDS

Live: `http://192.168.2.50:8222/varz` returns `"version": "2.10.29"`,
`"git_commit": "f91ddd8"`, uptime 93d. `nomad job inspect nats` confirms
`"image": "docker.io/nats:2.10-alpine"`, matching
`deployments/infrastructure/services/nats.hcl:69`. Upstream: the
`nats-io/nats-server` `v2.10.0` release (published 2023-09-19) lists
"Authorization callout extension for delegating to external auth providers
(#3719, #3784, #3799, #3864, #3987, #4501, #4544)". The capability claim in
§3 holds.

### P2 — The bus has no authentication today. HOLDS

`nats.hcl:79-94` is the rendered server config and contains only
`server_name`, `listen`, `http` and a `jetstream` block; no `authorization`
stanza. Live `/varz` reports no `auth_required`. The firewall comment
(`deployments/infrastructure/services.tf:266`) and `docs/nats.md:8`
(`**Auth:** none`) agree. All three call-outs in §4 describe real text.

### P3 — "NATS has no native OIDC verification (nats-io/nats-server#5692)". BREAKS (citation)

`nats-io/nats-server#5692` is titled **"Auth callout - Better doc/guidance to
integrate with an OAuth2/OIDC provider"**, opened 2024-07-24, and is still
`open`. Its body is a documentation request from a user who says "I'm not
able to clearly understand how callout works with Oauth2&OIDC". It does not
state that NATS lacks native OIDC verification. The underlying claim is
broadly correct, but the plan's only cited evidence for the design premise
does not say what the plan attributes to it. This is the exact
inlined-conclusion signature the dispatch asked me to test: a specific
upstream issue number presented as settled proof, sourced to nothing that
ran.

### P4 — "Informed by the S3 finding on auth-callout maturity" (§3). BREAKS

`.loop/ledger.json` records `S3-spike-oidc-version-claims` as
`stage=ready, dropped=True`. Its plan is archived at
`.loop/archive/S3-spike-oidc-version-claims/plan.md`, where subticket S3.3
was the work that would have produced this finding: "S3.3 NATS — verify
auth-callout maturity at `nats:2.10-alpine`: whether callout can validate an
external Vault/Nomad JWT and return a signed NATS user JWT, and the 2.10-line
specifics (e.g. encrypted callout requests / xkey)"
(`.loop/archive/S3-spike-oidc-version-claims/plan.md:255-258`). No findings
doc exists anywhere under `docs/`. R2 cites a finding that was never
produced, and the two questions S3.3 would have answered are precisely the
two this review finds unresolved (P11 token presentation, P13 account/xkey
handling).

### P5 — The `services.tf` anchors resolve. BREAKS (4 of 4)

| Plan claim | Actual today |
| --- | --- |
| `services.tf:261` = `# NATS+JetStream ... no auth in v1` | `:261` is `postgres_exporter = {`; the comment is at `:266` |
| `services.tf:262-277` = nats firewall rules | rules are at `:267-275` |
| `services.tf:364-366` = `nomad_job "nats"` `templatefile(..., {})` | `:364` is `grafana_external_url = "http://192.168.2.47:3000"`; the nats job is at `:377-380` |
| `services.tf:194` = the private registry block | `:194` is a bare `}`; `registry = {` is at `:195-201` |

Proven cause, not guesswork. At `01a1149` (2026-07-20, the tree the plan was
authored against) all three of `:194`, `:261`, `:364` resolved *exactly* as
the plan describes. Commit `99bc210` ("F3-foundation-haproxy-tls-vault-pki",
2026-07-24) shifted every one of them, and T2/N1/N2/T3/B1 shifted them
further. Four separate subticket instructions (§7 twice, §10 items 4 and 6)
point at wrong lines.

### P6 — The non-`services.tf` anchors resolve. HOLDS

`nats.hcl:8-10` (hostname constraint `radxa-dragon-q6a`), `:35` and `:103`
(`driver = "podman"`), `:70` (`args = ["--config", ...]`), `:86-90`
(`jetstream`), `:102-143` (the `nats-exporter` task, file ends at 145);
`postgres.hcl:70` (`vault {}`) and `:72-80` (the `template` rendering
`POSTGRES_USER`/`POSTGRES_PASSWORD`); `secrets.tf:10-30` (the minio
`random_password` + `vault_kv_secret_v2 "default/minio/localstack"` pair);
`variables.tf:1-4` (`secret_mount`);
`bootstrap/roles/nomad_server/tasks/main.yml:220`
(`jwks_url="http://127.0.0.1:4646/.well-known/jwks.json"`);
`nomad.hcl.j2:42-44` (`default_identity { aud = ["vault.io"] ttl = "1h" }`);
`providers.tf:28` (`provider "vault" {}`); `docs/nats.md:8`
(`**Auth:** none`) and `:76-81` (§2 Python, `nats-py`). The
`.pre-commit-config.yaml` hook list and `exclude: '^\.(claude|loop)/'` in §8
are reproduced correctly, as is the root `justfile` `pre_commit:` recipe.

### P7 — The Nomad WI JWKS endpoint exists and is what the callout validates against. HOLDS (no discovery-document defect)

Live: `GET http://192.168.2.30:4646/.well-known/jwks.json` returns a key set
(one RSA key, `alg: RS256`, `kid 00d87b20-...`). Reported explicitly per the
briefing's item 3 template: `GET
http://192.168.2.30:4646/.well-known/openid-configuration` returns `OIDC
Discovery endpoint disabled`, **but R2 never assumes a discovery document**.
§4, §6.1, §7 and §10.2 all name the JWKS URL specifically. R2 does not carry
M1's broken edge. No instance found.

One inaccuracy inside this otherwise-sound assumption: Risk 9.4 says the
callout "cannot validate tokens whose JWKS endpoints do not yet exist" for
*both* F1 and F2. The Nomad JWKS endpoint exists today and is live; the F1
edge is a dependency on a *naming convention* (per Q3-resolved), not on an
endpoint. Overstated, not load-bearing.

### P8 — "Vault runs as plain HTTP"; its OIDC JWKS is an F2 deliverable. PARTIALLY SOUND / stale

Direct `http://192.168.2.30:8200` is still plain HTTP (Vault 1.21.4,
`sealed: false`). But two things moved after 2026-07-24:

- F3 and T3 put a TLS edge in front of Vault.
  `deployments/infrastructure/services/haproxy.hcl:96` binds `*:443 ssl crt
  /secrets/haproxy.pem` and `:100`/`:111` route `vault.lab.orangecluster.nl`
  to backend `vault` (`:133-134`, `192.168.2.30:8200`).
- F2's own plan now fixes the issuer:
  `.loop/plans/F2-foundation-vault-oidc-provider.md:65-67` — "The issuer is
  now `https://vault.lab.orangecluster.nl` over a certificate clients already
  trust". (Note F2 is internally inconsistent too: its Q2 at `:323-330` still
  proposes `http://...` with `https_enabled = false`.)

So R2's "Vault runs as plain HTTP" framing is stale, and the callout will
have to fetch JWKS from a TLS host name resolved by the lab zone (T2), from a
Podman task on `radxa-dragon-q6a`. R2 says nothing about this. Separately,
Vault already serves a `default` OIDC provider discovery document today
(`/v1/identity/oidc/provider/default/.well-known/openid-configuration`
returns a live `issuer` and `jwks_uri`), so "an F2 deliverable this ticket
consumes, not defines" understates what already exists.

### P9 — The callout image is pushed to and pulled from "the cluster's private registry on firebat:5000". BREAKS

§7 and subticket 3 both instruct the implementer to push the callout image to
this registry. It does not exist:

- No registry job runs. `nomad job status` lists 19 jobs; none is a registry.
- No registry jobspec exists. `deployments/infrastructure/services/` contains
  acme, backup-minio, backup-postgres, grafana, haproxy, minio, nats,
  node-exporter, postgres, prometheus, promtail. No registry.
- No bootstrap role provisions one: grep for `registry`/`5000` across
  `bootstrap/roles/*/tasks/` and `templates/` returns nothing.
- The only `5000` references in the repo outside `.loop/` are the firewall
  rule (`services.tf:200`), a doc example
  (`docs/nats-postgres-cdc-bridge.md:236`,
  `registry.localstack:5000/pg-nats-bridge:latest`), and a comment in
  `deployments/applications/services.tf:66`.
- Probe from `192.168.215.2` (inside the `192.168.0.0/16` range the rule
  permits, and able to reach `192.168.2.30` on 8200 and 4646):
  `curl http://192.168.2.30:5000/v2/` times out after 10s. Caveat noted
  honestly: a timeout is filtered rather than refused, so the probe alone is
  suggestive, not conclusive.
- Decisive independent evidence: **every** custom image in the cluster is on
  GHCR, not a private registry — `ghcr.io/jasperhg90/talat-webhook-exporter-consumer:v0.1.3`,
  `.../talat-webhook-exporter-shim:v0.1.1`, `ghcr.io/jasperhg90/hermes:...`,
  `ghcr.io/jasperhg90/memex-jetson:1.1.0`.

The plan inherited this from a stale line in `CLAUDE.md` ("Deploys
PostgreSQL, MinIO, a private Docker registry, and monitoring"). Subticket 3
cannot execute as written.

### P10 — The nkey signing identity can be provisioned with the `secrets.tf:10-30` `random_password` + `vault_kv_secret_v2` pattern. BREAKS

§6.3, §7 and subticket 1 all specify "a `random_password`/generated-nkey +
`vault_kv_secret_v2` pair". A NATS account nkey seed is not a random string:
it is an ed25519 key in NATS's base32 encoding with a type prefix and a CRC16
suffix, which is why `nkeys.ParseDecoratedNKey` validates the `SO`/`SA`/`SU`
prefix (`nats-io/nkeys/creds_utils.go:44-51`, returning `ErrInvalidNkeySeed`
otherwise). `random_password` produces none of that structure, `tls_private_key`
does not emit nkey encoding, and no Terraform provider in
`deployments/infrastructure/providers.tf` (nomad, vault, google) generates
nkeys. The signing key must be generated out of band (`nk`, `nsc`, or the Go
`nkeys` library) and seeded into Vault. The plan presents this as a settled
pattern with a `path:line` citation rather than as the open question it is,
and subticket 1 is declared to depend "on nothing".

### P11 — Clients present their OIDC/WI JWT to NATS via `nats ... --creds <jwt>`. BREAKS — MOST DANGEROUS

The plan's §8 evals 2, 3 and 5 and eval-marker rows 2, 3 and 6
(`.loop/evals/R2-rollout-nats-auth-callout.md:15,16,19`) all specify
`nats context save wi --server <nats>:4222 --creds <wi-jwt>`. `--creds` maps
to `nats.UserCredentials`, which wires **two** callbacks
(`nats-io/nats.go/nats.go:1501-1515`): the JWT from the file, and a signature
callback `sigHandler(nonce, keyFile)` reading the *same* file for an nkey
seed. `nkeys.ParseDecoratedNKey` returns `ErrNoSeedFound` when the file
carries no `SO`/`SA`/`SU` seed (`creds_utils.go:27-46`). A file holding a
bare Nomad WI or Vault OIDC JWT has no seed, so the connection fails
client-side before the server ever invokes the callout.

The correct surface is the connect **token** (or user/password) field:
ADR-26 states the authorization request "will include traditional
authentication parameters such as username and password, tokens, nkeys, or
JWT credentials"
(`nats-io/nats-architecture-and-design/adr/ADR-26.md:23-25`), and its worked
example connects with `nats.UserInfo("dlc", "zzz")` (`:98-100`).

This is the most dangerous assumption. It is the contract between every NATS
client and the callout; four of the seven eval rows and subtickets 2, 4 and 5
rest on it; the acceptance set as written cannot pass; and it is exactly the
question S3.3 existed to settle (P4). The remedy is small (`--token`), but
the plan never states it and the eval marker encodes the wrong one, so an
implementer following the plan builds and validates against a mechanism that
was never verified.

### P12 — The plan's gates and eval marker are consistent with its own resolved forks. BREAKS

Resolved fork Q1 (`:407-412`) overrides the planner: "**Q1 → Go,
`applications/nats-auth-callout/`** (revised from the planner's Python) ...
add Go gates (`go test`, `gofmt`/`golangci-lint`)". The body was never
reconciled:

- §6 restrictions still say "If written in Python, use `uv` + `uv run
  pytest` ... respx" (`:172-177`).
- §8 asserts as fact "The callout is a new Python service (Q1: `nats-py`
  ...), so its own test command is **`uv run pytest`**" (`:243-249`).
- §11 Q1 still recommends Python/`nats-py` (`:370-376`).
- Eval-marker row 7 (`.loop/evals/...:20`) — the **only** offline row — is
  `uv run pytest` in the callout service dir with respx-mocked JWKS.

Under the resolved fork that row can never pass. Worse, §8's gate section
claims completeness ("there is no 'Terraform not validated' caveat") while
the actual `.pre-commit-config.yaml` I read has no Go hook at all: its
`check-ast` and `debug-statements` hooks are Python-only, `nomad-fmt` is
`types: [hcl]`, and the terraform hooks are `types: [terraform]`. A Go
service ships with **zero** configured format, lint or test gate. The
toolchain exists in the dev container (`/usr/local/bin/go`) but the repo has
no `go.mod` and no `.go` file, so this is net-new gate work the plan does not
schedule.

### P13 — Non-goal "JetStream streams, subjects ... stay as-is". UNCERTAIN

ADR-26 shows a config-mode example where "all users are on the `$G` global
account" (`:73-88`), so preserving JetStream *is* possible. But the same
document recommends the opposite: "A good pattern to follow is that the
authorization service runs isolated in its own account, since the system can
bind a user to any authorized account" (`:59-60`), and the callout can
"request that the client be bound to a different account" (`:38-39`).
Existing JetStream assets live in `$G` (live `/varz` shows
`jetstream.stats.accounts: 1`, 475 KB stored). If the callout binds callers
to a named account, they lose access to the existing streams. §7's config
sketch names `account: ...` without saying which, and §6.2 says only
"Existing `jetstream` config must be preserved" — preserving the config block
is not the same as preserving stream reachability. Also unaddressed: ADR-26's
optional `xkey` request encryption (`:206-226`), which is one of the two
things S3.3 was chartered to check.

### P14 — A human can present a Vault OIDC token to NATS. UNCERTAIN

The live Vault OIDC provider advertises `"grant_types_supported":
["authorization_code"]` and `"response_types_supported": ["code"]` only.
Obtaining that ID token requires a browser authorization-code flow against
`/ui/vault/identity/oidc/provider/default/authorize`, and F2's plan defers
the redirect URIs to L1/M2 hostnames
(`.loop/plans/F2-foundation-vault-oidc-provider.md:163`). Eval 3 and
eval-marker row 3 assume a CLI already "holding a valid Vault (human OIDC)
JWT" with no stated mechanism to obtain one. Compounding this: a Vault ID
token's `aud` is the OIDC **client_id**, whereas Q3-resolved requires "a
dedicated NATS audience" that "the callout requires". Those are two different
audience models and the plan treats them as one. Marked UNCERTAIN rather than
BREAKS because Vault's separate `identity/oidc/token/:role` API can mint a
role-scoped token with a chosen audience — but the plan names neither API, so
the human path is unspecified, not merely stale.

## Required attack surface — explicit results

1. **Stale premise.** FOUND. P5 (four `services.tf` anchors invalidated by
   F3's `99bc210` on the evening of 2026-07-24), P8 (Vault-is-plain-HTTP,
   overtaken by F3+T3 and by F2's now-`https` issuer), P9 (the private
   registry, stale in `CLAUDE.md` itself).
2. **Inlined conclusion.** FOUND, confirmed. P4 — §3 cites "the S3 finding on
   auth-callout maturity"; S3 is `dropped=True` and never ran. P3 — the
   issue number `nats-io/nats-server#5692` is presented as settled proof and
   is a still-open documentation request that says something else. The two
   questions S3.3 would have answered (external-JWT presentation, xkey /
   account handling) are the two this review finds unresolved (P11, P13).
3. **Broken dependency edge.** NOT FOUND in the M1 shape. R2 depends on F1
   and F2 (both `ready`, neither run). F1 does deliver what R2 asks of it
   (the audience convention, per its own summary), and the Nomad JWKS R2
   consumes already exists live. F2 delivers the Vault OIDC issuer. R2 does
   **not** assume a Nomad OIDC discovery document, so the M1 defect is
   absent. The soft edge worth noting: R2 describes the F1/F2 blocker as
   "JWKS endpoints do not yet exist", which is false for Nomad today.
4. **Shape-check eval.** NO `ls`/`grep`/file-existence scorer found. All six
   deterministic rows in `.loop/evals/R2-rollout-nats-auth-callout.md` use
   "deterministic check" over a real command, and row 4 is `model + rubric`.
   The eval file's defects are of a different kind: rows 2, 3 and 6 encode
   the unexecutable `--creds` invocation (P11), and row 7 encodes `uv run
   pytest` against a service the resolved fork says is Go (P12).
5. **Unresolvable anchor.** FOUND. Four in `services.tf` (P5). All other
   anchors resolve (P6).

## Required fixes before this plan can leave PLANNING

1. Re-resolve every `services.tf` anchor against HEAD: `:261 -> :266`,
   `:262-277 -> :267-275`, `:364-366 -> :377-380`, `:194 -> :195-201`
   (§7 four times, §10 items 4 and 6).
2. Delete or correct the `nats-io/nats-server#5692` citation. The issue is a
   still-open documentation request titled "Auth callout - Better
   doc/guidance to integrate with an OAuth2/OIDC provider" and does not
   support "NATS has no native OIDC verification".
3. Delete "Informed by the S3 finding on auth-callout maturity" and fold the
   two questions S3.3 owned into Open Questions: (a) how an external OIDC/WI
   bearer token is presented on CONNECT, and (b) whether the callout account
   and optional `xkey` disturb the existing `$G` JetStream assets.
4. Replace `--creds <jwt>` with the token surface throughout §8 evals 2, 3, 5
   and eval-marker rows 2, 3, 6. Cite ADR-26 §Overview for the connect
   options the callout request carries.
5. Retarget packaging. Either name `ghcr.io/jasperhg90/...` (the repo's only
   proven path for custom images) or add an Open Question on standing the
   registry up; a firewall rule is not a deployment.
6. Reconcile the Go fork through the whole plan: §6 restrictions, §7 code
   surface, §8 repo gate, §11 Q1 and eval-marker row 7 all still say
   Python/`uv run pytest`/`nats-py`/respx. State the net-new `go.mod`,
   `gofmt`/`golangci-lint` and `go test` gate work as scheduled scope — no
   Go hook exists in `.pre-commit-config.yaml` today.
7. Turn nkey provisioning into an Open Question with a recommendation. A
   `random_password` cannot produce a valid nkey seed; name the out-of-band
   generator (`nk`/`nsc`/the Go `nkeys` library) and say how the seed reaches
   `vault_kv_secret_v2`. Subticket 1's "Depends on: nothing" is wrong.
8. Refresh the Vault-side premise for the post-F3/T3 world: the callout will
   fetch JWKS from `https://vault.lab.orangecluster.nl` (per
   `.loop/plans/F2-foundation-vault-oidc-provider.md:65-67`), not plain HTTP,
   and must resolve the lab zone from a Podman task on radxa-dragon-q6a.
9. Specify the human path: which Vault API mints the token eval 3 presents,
   and how its `aud` (an OIDC client_id) satisfies the Q3-resolved
   "dedicated NATS audience" contract.

## Read-only compliance

Every cluster interaction was a read: `nomad job status`, `nomad job
inspect`, `curl` GETs against Nomad JWKS/discovery, Vault
`sys/health` and the OIDC discovery document, and the NATS monitor port
(`/varz`, `/healthz`). No `vault write`/`delete`/`patch`/`enable`, no `nomad
job run`/`stop`, no NATS publish or stream mutation, no `terraform apply`, no
mutating git command. The only file written is this verdict.
