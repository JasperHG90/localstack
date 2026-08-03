---
epic = "rollout"
depends_on = ["F1-foundation-nomad-wi-jwt-trust", "F10-foundation-nomad-oidc-issuer", "A1-audit-plan-premise-sweep"]
priority = 10
summary = "Give hermes keyless auth to memex with a Nomad Workload Identity JWT. One OIDC provider on the memex server (the Nomad issuer), grant mapped on nomad_job_id=hermes, token pinned to secrets/nomad_memex.jwt by the identity stanza's filepath. Requires bumping hermes's bundled memex client from 1.0.1 to 1.1.0. Static API keys stay everywhere."
tags = ["memex", "oidc", "nomad", "workload-identity", "hermes"]
---

# Ticket: R5-rollout-memex-oidc-auth

## 1. Title

Extend the keyless-OIDC pattern (F1 Nomad WI JWT trust, F10 Nomad OIDC
issuer) to memex's **workload** path: memex trusts the Nomad issuer as one
OIDC provider, and hermes authenticates with a Nomad Workload Identity JWT
mapped on `nomad_job_id`. Static API keys stay.

## 2. Size / Effort

**M.** Small diff (one env line on the server, one `identity` stanza plus
env on the client, three wheel URLs in a Dockerfile, one Terraform local).
Effort drivers:

- The hermes image ships memex client **1.0.1**, which has no `oidc` config
  field at all (P14). An image rebuild is on the critical path.
- Both directions must be shown live: an accepted hermes token and refused
  tokens (wrong `aud`, non-hermes `nomad_job_id`).
- Once the bearer resolves, the API key is **not** sent (P12). Mis-ordering
  the rollout takes hermes's memex access down rather than falling back.

Every premise that was blocking in the previous revision is now measured.
There is no probe-first subticket.

## 3. Triggered by

Operator request. memex v1.1.0 added OIDC. F1 and F10 already landed the
upstream pieces. The previous revision of this ticket also covered human
login through the Vault `lab` provider. Plan review
(`.loop/verdicts/R5-rollout-memex-oidc-auth.plan-validator.md`, verdict
`fail`) proved that impossible: Vault issues an opaque batch token as
`access_token` and memex verifies the access token as a JWT. The human half
now lives in `R6-rollout-memex-human-oidc` (stub). **Do not re-open it
here.**

## 4. Context

### memex today: static API keys only

- Job template `deployments/applications/services/memex.hcl`. Server task
  `task "memex"` at `deployments/applications/services/memex.hcl:68`.
  Config arrives as flat env vars via `template { ... env = true }`
  rendering `secrets/file.env`
  (`deployments/applications/services/memex.hcl:180-181`).
- Auth is on and key-only: `MEMEX_SERVER__AUTH__ENABLED=true`
  (`deployments/applications/services/memex.hcl:138`) and
  `MEMEX_SERVER__AUTH__KEYS='[{...}]'`
  (`deployments/applications/services/memex.hcl:140`), which sits inside a
  `{{- with secret ... }}` / `{{- end }}` pair
  (`deployments/applications/services/memex.hcl:139` and `:141`). That
  line is the precedent for injecting a `list[Model]` field as one JSON
  env var. The new OIDC line has no need of that secret block, so it goes
  **after** `:141`, not after `:140`.
- `nomad_job.memex` is `deployments/applications/services.tf:159-179`.
  `memex_version = "1.1.0"` at
  `deployments/applications/services.tf:171`, so no server image bump.
- Keys come from `vault_kv_secret_v2.memex_auth_keys`
  (`deployments/applications/secrets.tf:79-86`), fed by
  `random_id.memex_admin_key` (`deployments/applications/secrets.tf:71`)
  and `random_id.memex_writer_key`
  (`deployments/applications/secrets.tf:75`).
- Pre-existing drift, do NOT fix here:
  `deployments/applications/services/memex.hcl:140` reads
  `.Data.data.writer_key_vault_meetings`, which
  `deployments/applications/secrets.tf:79-86` never writes. The server
  still reports three keys configured (P10), so the third renders empty.
  Out of scope.

### hermes today: one static memex admin key, on an old client

- Job `deployments/applications/services/hermes.hcl`, `job "hermes"` at
  `:1`, so its `nomad_job_id` claim value is `hermes`.
- The memex-calling task is `task "hermes"` at
  `deployments/applications/services/hermes.hcl:364`. It reads
  `MEMEX_API_KEY` from Vault at `:405` (rendered to `secrets/file.env`,
  `:415`) and gets `MEMEX_SERVER_URL` / `MEMEX_VAULT` from `env {}` at
  `:446-450`.
- The prestart `task "config"`
  (`deployments/applications/services/hermes.hcl:27`) renders the same
  values into `local/hermes.env` (`:201-204`, destination `:214`) and its
  setup script copies that to `/opt/data/.env` (`:72`). Both copies are
  live, which is why `MEMEX_SERVER_URL` and `MEMEX_VAULT` appear twice
  (`:203-204` and `:449-450`). Any new client var follows the same pair.
- `config.yaml` (`deployments/applications/services/hermes.hcl:218-330`)
  carries TWO `env_passthrough` lists: `:254-262` (terminal) and
  `:265-273` (code_execution). Both name `MEMEX_API_KEY`,
  `MEMEX_SERVER_URL`, `MEMEX_VAULT`. Half-updating them is silent: the
  sandboxed subprocess keeps using the API key (P21).
- The task has a bare `vault {}`
  (`deployments/applications/services/hermes.hcl:387`), so it rides the
  server-side `default_identity` and no JWT lands in the alloc today.
- hermes holds the memex **admin** key
  (`deployments/applications/services/hermes.hcl:201`, `:405`; source
  `deployments/applications/secrets.tf:79-86`), which is long-lived and
  over-privileged for a workload.
- **The blocker:** the hermes image bundles memex client **1.0.1**, whose
  `MemexConfig` has no `oidc` field (P14). The wheels are pinned at
  `deployments/applications/services/hermes/Dockerfile:28-30` and the
  image tag at `deployments/applications/services.tf:124`
  (`"0.19.1-memex-v1.0.1"`). The tag's `-memex-vX.Y.Z` segment records
  that wheel version.

### The upstream pieces this builds on

- **Nomad OIDC (F10).** `oidc_issuer` set at
  `bootstrap/roles/nomad_server/templates/nomad.hcl.j2:42`, valued
  `https://nomad.lab.orangecluster.nl` at
  `bootstrap/playbooks/configure_hashistack_server.yml:45`. Live discovery
  and JWKS in P3.
- **Vault JWT trust (F1).** The `jwt-nomad` mount is Ansible-owned. The
  per-job role pattern is `deployments/infrastructure/acme.tf:66-90`, with
  the claim names at `:72-84`. That is Vault *consuming* WI JWTs. memex
  verifies the same JWTs itself against Nomad's JWKS and needs no Vault
  role.
- **The identity-stanza convention.** `docs/workload-identity.md:119-174`.
  Two rules bind: `name` is load-bearing, an unnamed `identity {}` writes
  no file (`docs/workload-identity.md:132-153`); and `aud` names the
  **verifier**, not the job (`:155-166`), so `aud = ["memex"]` is right.
- `.loop/plans/M1-minio-poc-service-account.md` is the same shape (WI JWT
  to a service's own verifier). Cited as a pattern only. **M1 is `blocked`
  and is deliberately NOT a dependency.**

### What is missing

memex trusts no issuer. hermes's only memex credential is a static admin
key.

## 5. Non-goals / out of scope

- **The human login path.** `R6-rollout-memex-human-oidc` owns it. Do not
  create a `vault_identity_oidc_client`, do not touch
  `deployments/infrastructure/oidc.tf`, do not add a second element to
  `MEMEX_SERVER__AUTH__OIDC`, do not edit `docs/vault-human-auth.md`.
- **Do NOT remove static API keys.** `MEMEX_SERVER__AUTH__KEYS`
  (`deployments/applications/services/memex.hcl:140`) stays for the
  browser extension. `MEMEX_API_KEY` stays in hermes
  (`deployments/applications/services/hermes.hcl:201`, `:405`). Removal is
  a follow-up (Q4).
- No memex **server** image bump
  (`deployments/applications/services.tf:171` is already `1.1.0`). The
  hermes image bump is in scope and is a different thing.
- No change to `vault_kv_secret_v2.memex_auth_keys`
  (`deployments/applications/secrets.tf:79-86`) or the `random_id` key
  generators (`:71`, `:75`).
- No change to Vault's `jwt-nomad` mount, its config, or the
  `nomad-workloads` role. memex verifies WI JWTs itself.
- No new Vault audience. `vault.io` stays untouched
  (`docs/workload-identity.md:162-163`).
- Do not fix the `writer_key_vault_meetings` drift noted in §4.
- No second workload caller. hermes is the only one.
- No hermes **base image** (`hermes-agent`) upgrade beyond what is already
  pinned. See Q1 on the pinned-vs-running drift.
- No MinIO/M1 work. No HAProxy or TLS edge change.

## 6. Requirements & restrictions

| # | Requirement | Where the repo states it |
|---|---|---|
| R1 | One OIDC provider on the memex server: the Nomad issuer. `MEMEX_SERVER__AUTH__OIDC` is a ONE-element JSON array | Operator decision after the R6 split; mechanism proven by P1, P2 |
| R2 | Workload auth uses `grant: token_file` on a Nomad WI JWT, mapped by the `nomad_job_id` claim | Operator decision; claim values proven by P4 |
| R3 | `aud` names the verifier, one per verifying service, never per job. Use `aud = ["memex"]` | `docs/workload-identity.md:155-166` |
| R4 | The `identity` stanza MUST set `name`, and MUST pin `filepath`. Do not rely on the default path | `docs/workload-identity.md:132-153`; P5 |
| R5 | The issuer string must be byte-identical on both sides (server `issuer`, client `MEMEX_OIDC__ISSUER`). Derive both from one Terraform local | P3; `deployments/applications/services.tf:22` already holds a `locals` block |
| R6 | hermes's bundled memex client must be >= 1.1.0 before any `MEMEX_OIDC__*` var is set | P14, P15 |
| R7 | Static API keys are preserved on both server and client | §5; memex OIDC how-to line 73, "keep at least one API key" for Hermes and the extension |
| R8 | Nomad HCL is `nomad fmt`-clean; Terraform is `fmt`-clean and `validate`-clean per root | `.pre-commit-config.yaml:16-33`, `scripts/tf_validate.sh:8-20` |
| R9 | Surgical changes only; match surrounding style; no adjacent refactors | `CLAUDE.md` §3 |
| R10 | Plain language in every comment and doc line added | `.claude/rules/plain-language.md` |
| R11 | Docs generated or edited must clear the slop scan | `.claude/rules/slop-scan-for-docs.md` |
| R12 | An adversarial sub-agent review runs before this is reported done | `.claude/rules/adversarial-reviews.md`; `.loop/config.json` `require_review: true` |
| R13 | Do not silence a failing gate; fix the cause | `.claude/rules/prek-code-quality.md`, `.claude/rules/pre-existing-issues.md` |

## 7. Code surface

No new Terraform file. Every change is an edit.

### `deployments/applications/services.tf`

- `:22` (`locals`) — add `nomad_oidc_issuer =
  "https://nomad.lab.orangecluster.nl"`. One definition, two consumers
  (R5).
- `:159-179` (`nomad_job.memex`) — pass `nomad_oidc_issuer =
  local.nomad_oidc_issuer` into the templatefile vars.
- `:118-148` (`nomad_job.hermes`) — pass `nomad_oidc_issuer =
  local.nomad_oidc_issuer`.
- `:124` — bump `hermes_version` from `"0.19.1-memex-v1.0.1"` to
  `"0.19.1-memex-v1.1.0"` (the tag whose `-memex-v` segment records the
  wheel version, per U5's convention).

### `deployments/applications/services/hermes/Dockerfile`

- `:28-30` — bump the three wheel URLs from `v1.0.1` to `v1.1.0`
  (`memex_common`, `memex_hermes_plugin`, `memex_cli`). All three exist
  (P15). Rebuild and push with `just rebuild_hermes`
  (`deployments/applications/justfile:36-44`), which reads the tag from
  `services.tf`, so bump `services.tf:124` first.

### `deployments/applications/services/memex.hcl`

- In the `task "memex"` env template, **after**
  `deployments/applications/services/memex.hcl:141` (the `{{- end }}`,
  NOT after `:140` — the OIDC line needs no Vault secret), add one line:

  ```
  MEMEX_SERVER__AUTH__OIDC='[{"issuer":"${nomad_oidc_issuer}","audience":["memex"],"grant_rules":[{"claim":"nomad_job_id","value":"hermes","policy":"<Q3>"}]}]'
  ```

  A ONE-element array, one `grant_rule`. Leave `algorithms` at its
  default, since Nomad signs RS256 (P3). Leave `default_policy` unset, so
  an unmatched token is refused (that is what §8 check D2 asserts).
- Quoting: the line sits in a Terraform `templatefile` heredoc that also
  runs consul-template. `${...}` is Terraform, `$${...}` escapes to Nomad
  (see `deployments/applications/services/memex.hcl:7`), `{{ }}` is Vault
  templating. Single-quote the JSON, exactly as `:140` does.

### `deployments/applications/services/hermes.hcl`

- In `task "hermes"` (`:364`), next to the existing `vault {}` (`:387`),
  add:

  ```hcl
  identity {
    name        = "memex"
    aud         = ["memex"]
    file        = true
    filepath    = "secrets/nomad_memex.jwt"
    ttl         = "1h"
    change_mode = "noop"
  }
  ```

  `filepath` is alloc-relative. The in-container path is
  `/secrets/nomad_memex.jwt` (P6), which is what
  `MEMEX_OIDC__TOKEN_FILE` takes. This exact shape validates clean on the
  live cluster (P22).

  `change_mode = "noop"`, NOT `restart`: Nomad fires `lifecycle.Restart` on
  every renewal after the first with no materiality test, so `restart` at
  `ttl = "1h"` restarts the agent gateway hourly. `noop` is valid for a
  `file = true` identity. Q5 carries the pinned upstream sources.
- Add `MEMEX_OIDC__ISSUER = "${nomad_oidc_issuer}"`, `MEMEX_OIDC__GRANT =
  "token_file"`, `MEMEX_OIDC__TOKEN_FILE = "/secrets/nomad_memex.jwt"` to
  the `env {}` block at `:446-450`, beside `MEMEX_SERVER_URL`.
- Mirror the same three into the prestart `local/hermes.env` template at
  `:201-204`, matching how `MEMEX_SERVER_URL` / `MEMEX_VAULT` already
  appear in both places. That file becomes `/opt/data/.env` (`:72`), which
  the memex plugin documents as the home for client env
  (upstream `memex_hermes_plugin/memex/config.py`, lines 10-12).
- Add the same three names to BOTH `env_passthrough` lists, `:254-262` and
  `:265-273`. Omitting either leaves sandboxed subprocesses on the API key
  (P21, and §8 check H3).
- Leave `MEMEX_API_KEY` (`:201`, `:405`) in place.

### Docs (the declared home for every §8 artifact)

- **`docs/workload-identity.md`** — add `memex` to the audience registry at
  `:155-166` as the first non-Vault verifying service. Also correct
  `:178-185`, which still says "the discovery endpoint is disabled
  cluster-wide" and shows `OIDC Discovery endpoint disabled`. F10 enabled
  it, and P3 has the live 200. Record the `filepath` rule from P5 in the
  `identity`-stanza section (`:132-153`): pin the path, do not discover it.
- **`docs/memex-oidc-verification.md`** (new) — the runbook holding §8's
  live checks verbatim, so the negative controls stay reproducible after
  the loop ends. Every check named in §8 lives here.

## 8. Tests & validation gates

No unit-test surface: this is Terraform, Nomad HCL and a Dockerfile.
`.pre-commit-config.yaml` scopes its Python gates (ruff, ruff-format,
mypy, pytest) to `files: '^cli/'` (`:37-53`), which this ticket does not
touch. Verification is the repo's static gates plus live probes.

### Static gates (must pass)

| Gate | Command | Source |
|---|---|---|
| All hooks | `just pre_commit` | `justfile:18-19`; `.loop/config.json` `gates` |
| Nomad HCL format | hook `nomad-fmt` | `.pre-commit-config.yaml:16-21` |
| Terraform format | hook `terraform-fmt` | `.pre-commit-config.yaml:22-27` |
| Terraform validate, per root | hook `terraform-validate` running `scripts/tf_validate.sh` | `.pre-commit-config.yaml:28-33`, `scripts/tf_validate.sh:8-20` |
| Jobspec shape, before apply | `nomad job validate` on the rendered template | read-only; used for P5 and P22 |
| Plan review | `terraform plan` on the applications root, read before apply | layered apply order in `CLAUDE.md` |

Worktree note: `just worktree_setup <path>` (`justfile:44`) seeds the
gitignored SSH key and tfvars that `terraform validate` needs.

### Live checks

Baseline, measured today (P8), so a regression is visible:
no credential `401`, garbage bearer `403`, admin API key `200`.

**S1 — the server loaded exactly one provider.** After the memex redeploy:

```
nomad alloc logs <memex-alloc> memex | grep -i 'authentication enabled'
```

Expect a new `info` line `OIDC bearer-token authentication enabled (1
provider(s)).` alongside the existing `API key authentication enabled (3
key(s) configured, 3 exempt path(s)).` (P10). A silently dropped provider
(bad JSON in the env var) is the cheapest failure to catch here. `1`, not
`2` — the human provider is R6's.

**S2 — API-key regression.** Re-run the P8 triple against
`http://192.168.2.46:8000/api/v1/vaults`. Still `401` / `403` / `200`.
This is R7's proof.

**D1 — DENY, wrong `aud`.** Run a throwaway Nomad job carrying a second
`identity { name = "vault_default", aud = ["vault.io"], file = true,
filepath = "secrets/nomad_vault_default.jwt" }` and present that token to
memex. Expect `403`. (`nomad job validate` warns "identity called
vault_default but no vault block" on this shape. That warning is expected
and harmless.)

**D2 — DENY, non-hermes `nomad_job_id`.** From the same throwaway job,
present its `aud = ["memex"]` token. Expect `403` from the **authorization**
path, not the signature path: the token verifies, matches no `grant_rule`,
and `default_policy` is unset.

Assert this on the SERVER LOG, not the response. memex folds "valid token
that maps to no policy" and "signature failure" into the same `None`,
returns it unlogged, and renders both as the identical
`403 {'detail': 'Invalid API key or bearer token.'}`, so the response
cannot tell you which one you got. The discriminator: D1 emits
`OIDC token rejected for issuer ...`; D2 emits NOTHING. A silent 403 here
is the pass.

(Confirm the two log shapes against the running server during R5b. On why
they carry no local anchor, see the vendored-tree warning at the head of
the Premises section.)

Tear the probe job down afterward, as `docs/workload-identity.md:195-198`
requires.

**W1 — GRANT, the raw token.** After the `identity` stanza lands and
BEFORE any `MEMEX_OIDC__*` var is set:

```
nomad alloc exec -task hermes <hermes-alloc> sh -c \
  'cat /secrets/nomad_memex.jwt | cut -d. -f2 | base64 -d'
```

Decode, do not assume: assert `iss` = `https://nomad.lab.orangecluster.nl`,
`aud` contains `memex`, `nomad_job_id` = `hermes`. Then, from the same
alloc, `curl -H "Authorization: Bearer $(cat /secrets/nomad_memex.jwt)"`
against `/api/v1/vaults`. Expect `200`. Running this before the client
config means a failure costs nothing: hermes is still on the API key.

**H1 — the hermes client actually sends the bearer.** After the client
config lands:

```
nomad alloc exec -task hermes <hermes-alloc> \
  /opt/hermes/.venv/bin/python -c "import asyncio;\
from memex_common.config import MemexConfig;\
from memex_common.auth_client import resolve_client_headers;\
print(asyncio.run(resolve_client_headers(MemexConfig())))"
```

Expect `{'Authorization': 'Bearer eyJ...'}`, NOT `{'X-API-Key': ...}`.
This is the exact call `MemexClientAuth` makes on every request (P16), and
the exact probe that produced P11 and P12.

**H2 — the wrong-path detector.** §9 failure mode 1 is silent because the
client falls back. Name the detector: memex logs, at level `WARNING`,
logger `memex.common.auth_client`, message
`Could not read workload token file <path>: [Errno 2] No such file or
directory` (P13). hermes emits WARNING records to stderr already
(measured: `WARNING agent.tool_executor: ...` in the running alloc), so no
log-level change is needed. Check with:

```
nomad alloc logs <hermes-alloc> hermes | grep -i 'workload token file'
```

Also grep for the plugin's own fallback line, `Falling back to X-API-Key
client (shared memex config unusable)` (P16), which fires when
`MEMEX_OIDC__*` is present but fails validation. Both must be **absent**.

**H3 — `env_passthrough` covers both sandboxes.** §9 failure mode 5 is
silent in exactly the same way. Through the hermes agent, run `env | grep
MEMEX_OIDC` once via the terminal tool (list at
`deployments/applications/services/hermes.hcl:254-262`) and once via
code_execution (`:265-273`). Both must print all three vars. A list that
passes `MEMEX_API_KEY` but not `MEMEX_OIDC__*` yields a subprocess that
quietly keeps using the API key and looks like success.

Env visibility is necessary, NOT sufficient. Per P12 all three vars can be
set while the token file is unreadable to the subprocess, which is §9 mode
4's exact shape. So in the SAME sandbox, also resolve the credential:

```
/opt/hermes/.venv/bin/python -c "import asyncio;\
from memex_common.config import MemexConfig;\
from memex_common.auth_client import resolve_client_headers;\
print(asyncio.run(resolve_client_headers(MemexConfig())))"
```

Use the venv interpreter, not a bare `python`: the memex wheels install
into `/opt/hermes/.venv`
(`deployments/applications/services/hermes/Dockerfile:24`, `:26`).

Expect `{'Authorization': 'Bearer ...'}` in BOTH sandboxes. An
`X-API-Key` here means that sandbox silently kept the key.

Every check above is written verbatim into
`docs/memex-oidc-verification.md`.

The scored acceptance layer over these checks is the eval marker,
`.loop/evals/R5-rollout-memex-oidc-auth.md`: ten deterministic rows at a
100% bar, one per check above plus two guardrails on the §5 non-goals (the
human path must not reappear; the static API keys must not be removed).
Keep the two in step by hand — nothing enforces the link.

## 9. Risk assessment

**Blast radius.**

- The `memex.hcl` edit redeploys memex, the memory backend for hermes and
  the operator's MCP tooling. A malformed `MEMEX_SERVER__AUTH__OIDC` string
  either fails startup (loud) or loads with the provider missing (quiet).
  S1 is the detector for the quiet case.
- The `hermes.hcl` edits redeploy hermes, the agent gateway.
- The image bump is the largest single risk. It rebuilds and repushes
  `ghcr.io/jasperhg90/hermes`, and the first apply also carries the
  already-pinned-but-unapplied jump from the running `0.12.0-memex-v1.0.1`
  to `0.19.1-memex-v1.0.1` (P17). That jump is U5's, not this ticket's.
  See Q1.
- `terraform apply` on the applications root refreshes every job in it.
  Read the plan.
- **Do NOT add `user =` to `task "hermes"`.** The whole client path depends
  on the unprivileged gateway process reading a Nomad-written file. It works
  only because that task sets no `user`, so Nomad's `users.WriteFileFor`
  (upstream
  <https://github.com/hashicorp/nomad/blob/v2.0.4/helper/users/lookup.go#L69-L104>,
  not vendored here) skips the chown and leaves the JWT world-readable.
  `deployments/applications/services/hermes/Dockerfile:1-8` already says the
  same thing from the image side: "do NOT pin the Nomad task to a non-root
  UID". The sibling prestart task DOES set one
  (`deployments/applications/services/hermes.hcl:42`), so the pattern looks
  safe to copy. It is not: copying it silently breaks the credential and
  falls back to the API key.

**Reversibility.** Good on the config, weaker on the image. The env line,
the `identity` stanza, the `env_passthrough` entries and the Terraform
local all revert cleanly, and the static keys are never removed. The image
tag reverts by putting the old string back in `services.tf:124`; the old
image is still in the registry.

**Likeliest failure modes, in order.**

1. **Wrong `token_file` path.** The client cannot read the file, warns
   once, and falls back to `MEMEX_API_KEY`, so it looks like success.
   Mitigated by construction: `filepath` pins the path in the jobspec
   (P5). Detectors: H1 (positive) and H2 (the warning).
2. **The bearer resolves but memex rejects it.** This is NOT a fallback:
   once `_resolve_bearer` returns a token the client sends only
   `Authorization`, never `X-API-Key` (P12). hermes loses memex access
   outright. Mitigated by ordering: the server provider (R5a) and the raw
   token proof (W1) both land before the client config (R5e).
3. **Image bumped, config not, or the reverse.** Config without the image
   is inert on memex client 1.0.1 (no `oidc` field at all, P14) and hermes
   silently stays on the API key. Image without config is harmless.
   Detector: H1.
4. **`env_passthrough` half-updated.** Interactive use works, sandboxed
   subprocesses quietly keep the API key. Detector: H3.
5. **Issuer string drift** between the server `issuer` and
   `MEMEX_OIDC__ISSUER`. Provider selection is by exact `iss` match, so a
   trailing slash on one side 403s everything. Mitigated by the single
   Terraform local (R5).
6. **Policy too narrow.** hermes holds `admin` today (P20). A `writer`
   grant scoped to `vault_ids: ["hermes"]` is a capability cut that would
   surface as memex operations failing after the cutover, not at deploy.
   See Q3.

## 10. Subtickets

Ordered and dependency-aware. If these become separate plan files, encode
this order in each file's `depends_on`.

1. **R5a — memex server trusts the Nomad issuer.** The
   `local.nomad_oidc_issuer` definition and the memex templatefile var
   (`deployments/applications/services.tf:22`, `:159-179`), plus the
   `MEMEX_SERVER__AUTH__OIDC` line after
   `deployments/applications/services/memex.hcl:141`. Apply. Run S1 and
   S2. Inert until a matching token arrives, so it is safe to land alone.
2. **R5b — prove both denials.** Throwaway Nomad job with two identities.
   Run D1 and D2, then tear the job down. Depends on R5a. Needs no hermes
   change.
3. **R5c — hermes image carries memex client 1.1.0.**
   `deployments/applications/services.tf:124` to
   `"0.19.1-memex-v1.1.0"`, then
   `deployments/applications/services/hermes/Dockerfile:28-30` to the
   v1.1.0 wheels, then `just rebuild_hermes`, then apply. Verify in the
   alloc: `memex-common 1.1.0` and `'oidc' in
   MemexConfig.model_fields`. Depends on R5a only. Read the plan for the
   0.12.0-to-0.19.1 jump first (Q1).
4. **R5d — hermes `identity` stanza.** The stanza only, no client config.
   The JWT lands in the alloc and hermes still authenticates with the API
   key. Run W1. Depends on R5b.
5. **R5e — hermes client config.** `MEMEX_OIDC__*` in the `env {}` block
   and the prestart `hermes.env`, plus BOTH `env_passthrough` lists. Run
   H1, H2, H3, then S2 again. Depends on R5c and R5d.
6. **R5f — docs.** `docs/workload-identity.md` audience registry, the
   stale-discovery correction, the `filepath` rule, and the new
   `docs/memex-oidc-verification.md` runbook. Depends on R5e.

## 11. Open questions

**Q1 (blocking on ordering) — does the hermes image bump belong in this
ticket, and what about the 0.12.0-to-0.19.1 jump riding along?**
The bump is unavoidable: without memex client 1.1.0 there is no `oidc`
config field (P14), so R5e is dead code. But the running alloc is
`ghcr.io/jasperhg90/hermes:0.12.0-memex-v1.0.1` while
`deployments/applications/services.tf:124` already pins
`0.19.1-memex-v1.0.1` (P17). The first apply after this ticket therefore
carries an untested seven-minor hermes-agent jump that R5 did not cause.
*Recommendation:* keep the wheel bump in R5c, but land the pending
`0.19.1-memex-v1.0.1` apply **first**, on its own, as a separate operator
step, so a hermes regression is attributable. That tag must exist in the
registry before the apply: U5 (`971c257`) deferred the build, so run `just
rebuild_hermes` from the U5 tree first and confirm the push, rather than
assuming the tag is there.

The alternative — re-pinning to `0.12.0-memex-v1.1.0` — is NOT a one-line
change. U5 moved two lines, not one: `services.tf:124` AND
`deployments/applications/services/hermes/Dockerfile:9`, which carries the
base image `v2026.7.1` to `v2026.7.30` (agent `0.18.0` to `0.19.1`).
Re-pinning the tag alone rebuilds from the NEW base and ships the agent jump
under a tag that denies it. Taking this option means reverting
`Dockerfile:9` too, and §7 must then list that line.

Either is fine; combining both jumps in one apply is not.

**Q2 — one Terraform local, or literals in each template?**
`deployments/applications/services/hermes.hcl:205` and `:451` hardcode
`NOMAD_ADDR` today, so a literal would match some existing style. But the
issuer string must be byte-identical across two files or provider
selection fails (§9 mode 5).
*Recommendation: one `local`, settled.* Add `nomad_oidc_issuer` to the
existing `locals` block at `deployments/applications/services.tf:22` and
pass it into both templatefile calls. Same value, one place, no drift.

**Q3 — what policy and vault scope does the hermes grant get?**
Not settled by the request. memex policies are `reader`/`writer`/`admin`,
and a grant may carry `vault_ids` / `read_vault_ids`. hermes holds the
memex **admin** key today (`deployments/applications/services/hermes.hcl:201`,
`:405`, sourced from `admin_key` at
`deployments/applications/secrets.tf:79-86`), unscoped. memex's own worked
example for exactly this case uses `policy: writer` with `vault_ids:
["hermes"]`, which matches `MEMEX_VAULT=hermes`
(`deployments/applications/services/hermes.hcl:204`, `:450`).
*Recommendation:* grant `admin`, unscoped, in this ticket. Say plainly in
the comment what that buys: the win here is "no long-lived secret on the
host", not "less privilege". Changing the mechanism and the privilege
level in one step makes any failure ambiguous, and hermes's real vault
and delete usage is not measured. Open a follow-up to tighten to `writer`
+ `vault_ids: ["hermes"]` once §8's H1 has held and hermes's actual memex
calls have been observed. If the operator prefers the tighter grant now,
say so before R5a: it changes one string and adds a failure mode that
surfaces at runtime rather than at deploy.

**Q4 — when does hermes drop `MEMEX_API_KEY`?**
The operator settled *whether*: keep it. Only *when* is open. Note the
fallback is narrower than it looks: it fires only when the token source is
unreadable, not when memex rejects a token (P12).
*Recommendation: a follow-up ticket.* Removing it here would delete the
only cover for failure mode 1 and make a wrong path a hard outage instead
of a silent degradation. Open the follow-up once H1 and H2 have held in
production for a while.

**Q5 — does the `identity` stanza's `ttl = "1h"` with `change_mode =
"restart"` restart hermes hourly?**
SETTLED, against the earlier recommendation. Yes, it restarts hourly.
Nomad's identity hook calls `lifecycle.Restart` on every renewal after the
first, with no materiality test, so `restart` at `ttl = "1h"` restarts the
agent gateway every hour. Watching the restart count during R5d, as this
ticket first proposed, is a race R5d usually wins: the first renewal has
not happened yet.
*Resolution:* ship `change_mode = "noop"`. It is valid for a `file = true`
identity, and the restart warning is scoped to `Env`, not `File`. No
restart is needed anyway: the client re-reads the file on every request
(P12's code path), so a rotated token is picked up without one.

Sources, at Nomad tag `v2.0.4` (the deployed version,
`bootstrap/inventory/group_vars/all.yml:12`). Nomad's Go source is NOT
vendored in this repo, so these carry no local anchor by design:

- restart-on-every-renewal:
  <https://github.com/hashicorp/nomad/blob/v2.0.4/client/allocrunner/taskrunner/identity_hook.go#L160-L164>
- `noop` valid for a file identity, and the restart warning scoped to `Env`:
  <https://github.com/hashicorp/nomad/blob/v2.0.4/nomad/structs/workload_id.go#L43>,
  <https://github.com/hashicorp/nomad/blob/v2.0.4/nomad/structs/workload_id.go#L472>,
  <https://github.com/hashicorp/nomad/blob/v2.0.4/nomad/structs/workload_id.go#L522-L524>

Re-confirm against the deployed version if R5d sees different behavior.

## Premises / assumptions

Evidence is a resolved `path:line`, a probe command with captured output,
or an explicit `UNCERTAIN`. Every probe below is read-only or
self-restoring, and was run on 2026-08-03 against the live cluster unless
marked otherwise.

**Do NOT verify any memex premise against `apm_modules/JasperHG90/memex/`.**
That vendored tree is pinned (`.apm-pin`, commit `2a053a7b14bbdee2`) to a
**pre-1.1.0** snapshot containing NO OIDC code — no `oidc.py`, no
`memex_common/auth_client.py`, and a `config.py` with no `oidc` field. It
will make P1, P2, P11, P14, P15 and P16 look FALSE, and three files there
are actively booby-trapped — they resolve by bare basename to real code
that says something else:

- `auth.py` — the same line range upstream v1.1.0 uses for the 403 render
  holds an unrelated vault-access helper there.
- `memex_hermes_plugin/memex/provider.py` — the lines P16 and §7 cite hold
  the tail of `initialize` there, with no `_build_api_client`, no
  `MemexClientAuth`, and no `Falling back to X-API-Key` string anywhere in
  the file. H2's second detector will look fabricated.
- `memex_hermes_plugin/memex/config.py` — its docstring ends at line 11, so
  a cited line 10-12 resolves to `from __future__ import annotations`.

memex premises below are sourced from upstream v1.1.0 (URL given per
premise) or from a live probe. Likewise, Nomad's Go source is not vendored at all; the
upstream references are pinned to tag `v2.0.4` in Q5 and §9.

**P1 — memex v1.1.0 selects OIDC providers by `iss`, and the config field
is a list. VERIFIED.**
`server.auth.oidc` is `list[OidcProviderConfig]`, env var
`MEMEX_SERVER__AUTH__OIDC`, "Trusted OIDC providers ... Coexists with
`keys`" (memex config reference line 255). The how-to line 40: "Each
provider is selected by matching the token's `iss` claim, then verified:
signature against the JWKS, `aud` against `audience`, `iss` against
`issuer`". A one-element list is the same mechanism as a two-element one.
Sources:
<https://raw.githubusercontent.com/JasperHG90/memex/v1.1.0/docs/reference/configuration-options.md>,
<https://raw.githubusercontent.com/JasperHG90/memex/v1.1.0/docs/how-to/configuring-server/oidc.md>

**P2 — a memex `list[Model]` config field injects as one env var holding a
JSON string, in this deployment. VERIFIED.**
`deployments/applications/services/memex.hcl:140` does exactly this for
`MEMEX_SERVER__AUTH__KEYS`. `keys` (config reference line 254) and `oidc`
(line 255) have the same shape, and line 129 states the convention: "Pass
a JSON-string when using the env var: `'["a","b"]'`". Placement: `:140`
sits between `{{- with secret ... }}` at `:139` and `{{- end }}` at
`:141`, so the new line goes after `:141`.

**P3 — Nomad's OIDC issuer is `https://nomad.lab.orangecluster.nl`, serves
discovery and JWKS, and signs RS256. VERIFIED (live).**
```
$ curl -sk https://nomad.lab.orangecluster.nl/.well-known/openid-configuration
{"id_token_signing_alg_values_supported":["RS256","EdDSA"],
 "issuer":"https://nomad.lab.orangecluster.nl",
 "jwks_uri":"https://nomad.lab.orangecluster.nl/.well-known/jwks.json",
 "response_types_supported":["code"],"subject_types_supported":["public"]}
$ curl -sk .../.well-known/jwks.json | jq '[.keys[] | {kty,alg}]'
[{"kty":"RSA","alg":"RS256"},{"kty":"RSA","alg":"RS256"},
 {"kty":"RSA","alg":"RS256"}]
$ nomad version          # devcontainer CLI, NOT the cluster
Nomad v2.0.3
```
The CLUSTER runs Nomad **2.0.4** on every server and client
(`bootstrap/inventory/group_vars/all.yml:12` pins `nomad: 2.0.4-1`). The
`nomad version` above is the devcontainer's CLI and is not a cluster fact.
This matters for R5f: `docs/workload-identity.md:150-151` already says
"Confirmed live on Nomad 2.0.4" and is CORRECT — do not "fix" it to 2.0.3.

All three keys are RS256, which is inside memex's default
`algorithms: ["RS256","ES256"]` (config reference line 294), so no
override is needed. Config source:
`bootstrap/roles/nomad_server/templates/nomad.hcl.j2:42`, value at
`bootstrap/playbooks/configure_hashistack_server.yml:45`.

**P4 — Nomad WI JWTs from this cluster carry `nomad_job_id`,
`nomad_namespace` and `nomad_task`, with `nomad_job_id` equal to the job
name. VERIFIED (live, re-probed today).**
Read back from Vault's identity store, which records the claim values real
workload logins presented on the `jwt-nomad` mount:
```
$ vault list identity/entity/id | (read each entity's aliases)
entity_9833f71f | alias=memex   | auth/jwt-nomad/ |
  {"nomad_job_id":"memex","nomad_namespace":"default","nomad_task":"memex"}
entity_f1e203fe | alias=bifrost | auth/jwt-nomad/ |
  {"nomad_job_id":"bifrost","nomad_namespace":"default","nomad_task":"bifrost"}
(10 more, same shape)
```
Claim names corroborated by
`deployments/infrastructure/acme.tf:72-84`. hermes's value will be
`hermes` (`deployments/applications/services/hermes.hcl:1`).

**P5 — the `identity` stanza's `filepath` pins the token path, and Nomad
rejects it without `file = true`. VERIFIED (live, both directions,
read-only).**
probe: `nomad job validate <scratch-spec.hcl>`, which never registers a
job. Three scratch specs:
```
$ nomad job validate <identity with name+file=true+filepath>
Job validation successful
$ nomad job validate <same, filepath removed>
Job validation successful
$ nomad job validate <same, file = false>
* Identity "memex" is invalid: 1 error occurred:
        * file parameter must be true in order to specify filepath
```
So `filepath = "secrets/nomad_memex.jwt"` is accepted by this cluster's
Nomad 2.0.4 (`nomad job validate` is a server-side call, so this result
came from the cluster, not the devcontainer CLI — see P3) and the
`file = true` precondition is enforced. This replaces
the previous revision's plan to discover the default path from a running
alloc, and closes §9 failure mode 1 by construction. For the record, the
default is `secrets/nomad_<name>.jwt` (Nomad
`client/allocrunner/taskrunner/identity_hook.go` line 242,
`fmt.Sprintf("nomad_%s.jwt", widspec.Name)`, per the plan-validator
verdict), and memex's own how-to line 170 (`# writes the token to
secrets/nomad_token.jwt`) is wrong. Pinning makes both moot.

**P6 — the in-container path for the task's secrets dir is `/secrets/...`
under this repo's podman driver. VERIFIED.**
Three existing jobs read it that way:
`deployments/infrastructure/services/acme.hcl:97`
(`TRANSIP_PRIVATE_KEY_PATH="/secrets/transip.key"`),
`deployments/infrastructure/services/backup-minio.hcl:41`
(`service_account_file = /secrets/gcs-key.json`),
`deployments/infrastructure/services/haproxy.hcl:96`
(`bind *:443 ssl crt /secrets/haproxy.pem`). So `filepath` is
alloc-relative (`secrets/nomad_memex.jwt`) while
`MEMEX_OIDC__TOKEN_FILE` is container-absolute
(`/secrets/nomad_memex.jwt`). Mixing them up is §9 failure mode 1.

**P7 — the memex container can reach Nomad's discovery and JWKS AND
validates their TLS with its own trust store. VERIFIED (live, from inside
the running alloc).**
```
$ nomad alloc exec -task memex <alloc> python3 -c "urllib.request.urlopen(...)"
HTTP 200 https://nomad.lab.orangecluster.nl          # openid-configuration
HTTP 200 keys= 3 ['RS256']                           # jwks.json
```
No `verify=False`, so the private CA is trusted in-container. Also
reachable from the host (`ssh localstack@192.168.2.46 curl -w %{http_code}`
returns `200` for both, with no `-k`). This is the requirement memex's
how-to states at line 195.

**P8 — memex today answers `401` / `403` / `200` for no credential,
garbage bearer, valid API key. VERIFIED (live, read-only baseline).**
```
$ B=http://192.168.2.46:8000/api/v1/vaults
no credential:  401
garbage bearer: 403
admin api key:  200
```
Matches memex's own verification section (how-to lines 197-218). This is
the S2 baseline and the shape D1/D2 must reproduce.

**P9 — this ticket's changes are additive to a running, healthy memex.
VERIFIED (live).**
probe: `nomad job status memex` reports `Status = running`, latest
deployment `successful`, 1 healthy alloc. Nothing here removes or
replaces existing config.

**P10 — the memex startup auth log line is `info`-level, on stderr, and
readable with `nomad alloc logs`. VERIFIED (live).**
probe:
```
$ nomad alloc logs <memex-alloc> memex | grep -i auth
info  API key authentication enabled (3 key(s) configured, 3 exempt path(s)).
      [memex.core.server]
```
The OIDC line joins it at the same level. memex's how-to line 70 gives its
text: `OIDC bearer-token authentication enabled (N provider(s)).` With one
provider, expect `1`. ("3 key(s)" reflects the `writer_key_vault_meetings`
drift noted in §4, which is out of scope.)

**P11 — `MEMEX_OIDC__*` env vars DO materialize the optional nested
`OidcClientConfig` on memex-common 1.1.0. VERIFIED (live probe, both
directions).**
Scratch venv, memex_common 1.1.0 wheel, no repo files touched:
```
$ MEMEX_OIDC__ISSUER=... MEMEX_OIDC__GRANT=token_file \
  MEMEX_OIDC__TOKEN_FILE=/secrets/nomad_memex.jwt python -c "MemexConfig()"
oidc is None? False
issuer     = https://nomad.lab.orangecluster.nl
grant      = token_file
token_file = /secrets/nomad_memex.jwt
client_id  = None
with no MEMEX_OIDC__* -> oidc is None? True
```
This settles the previous revision's UNCERTAIN premise and removes the
`MEMEX_CONFIG_PATH` YAML fallback from scope. `client_id` is correctly
unused for `token_file` (config reference line 101).

**P12 — once the bearer resolves, the client sends ONLY `Authorization`.
The API key is a fallback for an unreadable token source, not for a
server-side rejection. VERIFIED (live probe, both directions).**
Same scratch venv, `MEMEX_API_KEY` set throughout:
```
GRANT  (token file present): {'Authorization': 'Bearer FAKE.WI.JWT'}
DENY   (wrong token path)  : {'X-API-Key': 'the-api-key'}
```
Source: upstream `memex_common/auth_client.py` lines 196-200 at tag
v1.1.0. The body is `bearer = await _resolve_bearer(...)`, then `if bearer
is not None: return {'Authorization': bearer}`, then the `X-API-Key`
branch. This drives §9 failure mode 2 and the R5a-before-R5e ordering.
<https://github.com/JasperHG90/memex/blob/v1.1.0/packages/common/src/memex_common/auth_client.py>

**P13 — the wrong-path failure has a concrete detector: a `WARNING` from
logger `memex.common.auth_client`. VERIFIED (live probe).**
Captured in the same run as P12:
```
WARNING memex.common.auth_client: Could not read workload token file
  /tmp/.../wrong-path.jwt: [Errno 2] No such file or directory
```
Source: upstream `memex_common/auth_client.py` line 258 at tag v1.1.0.
hermes already emits WARNING records to stderr (measured in the running
alloc: `WARNING agent.tool_executor: Tool skill_manage returned error
...`), so no log-level change is needed to see it. Match on the message
text, not the line number, which drifts upstream.

**P14 — hermes's CURRENT image bundles memex client 1.0.1, whose
`MemexConfig` has no `oidc` field at all. VERIFIED (live, inside the
running alloc). BLOCKING for the client half.**
```
$ nomad alloc exec -task hermes <alloc> python3 -c "..."
memex-cli 1.0.1
memex-common 1.0.1
memex-hermes-plugin 1.0.1
MemexConfig fields: ['api_key', 'server', 'server_url', 'vault']
```
No `oidc` key. Setting `MEMEX_OIDC__*` on this image is a no-op and hermes
stays on the API key silently. Pin at
`deployments/applications/services/hermes/Dockerfile:28-30`; image tag at
`deployments/applications/services.tf:124`.

**P15 — the memex v1.1.0 wheels exist and are fetchable. VERIFIED
(live).**
probe: `curl -sIL -o /dev/null -w '%{http_code}' <release-asset-url>`
```
$ curl -sIL .../releases/download/v1.1.0/<wheel> -w %{http_code}
memex_common-1.1.0-py3-none-any.whl        200
memex_hermes_plugin-1.1.0-py3-none-any.whl 200
memex_cli-1.1.0-py3-none-any.whl           200
```
Same three names and URL shape as the v1.0.1 pins at
`deployments/applications/services/hermes/Dockerfile:28-30`, so the bump
is three string edits. Installing `memex_common-1.1.0` into a scratch venv
gave `MemexConfig fields: ['api_key', 'oidc', 'server', 'server_url',
'vault']`, which is the field P14 shows missing.

**P16 — hermes's memex plugin routes its calls through the same auth
resolver, so `MEMEX_OIDC__*` covers plugin traffic. VERIFIED.**
Source: the `memex_hermes_plugin-1.1.0-py3-none-any.whl` wheel from
<https://github.com/JasperHG90/memex/releases/tag/v1.1.0>, read in a
scratch venv. Upstream `memex_hermes_plugin/memex/provider.py` lines
250-285 builds its httpx client with
`auth=MemexClientAuth(MemexConfig())`, and `MemexClientAuth.async_auth_flow`
(upstream `memex_common/auth_client.py`, lines 181-184) calls the same
`resolve_client_headers` probed in P12. The docstring names the case: "a
keyless workload token from `MEMEX_OIDC__*` — e.g. a Nomad Workload
Identity token via `grant=token_file`". It also gives a second detector,
`provider.py` lines 279-281: `Falling back to X-API-Key client (shared
memex config unusable): %s`, which fires when the OIDC env is present but
fails validation. The plugin's config module documents `$HERMES_HOME/.env`
as the home for these vars (upstream `memex_hermes_plugin/memex/config.py`,
lines 10-12), which is why §7 mirrors them into the prestart
`hermes.env`.

**P17 — the pinned hermes image and the running one differ already.
VERIFIED (live).**
`deployments/applications/services.tf:124` pins
`"0.19.1-memex-v1.0.1"`. The running alloc's task config reports
`ghcr.io/jasperhg90/hermes:0.12.0-memex-v1.0.1` for both `config` and
`hermes` tasks. That gap is U5's unapplied change, not this ticket's, but
this ticket's first apply carries it. See Q1.

**P18 — the repo's gates here are the pre-commit hooks plus per-root
`terraform validate`, with no Python gate. VERIFIED.**
`.pre-commit-config.yaml:16-21` is `nomad-fmt`, `:22-27` `terraform-fmt`,
`:28-33` `terraform-validate` running `scripts/tf_validate.sh`, which
validates `deployments/infrastructure`, `deployments/applications` and
`deployments/applications/modules/bucket` offline (`:8-20`). The Python
hooks are scoped `files: '^cli/'` (`:37-53`). `.loop/config.json` sets
`gates: ["just pre_commit"]`, `require_review: true`, `require_eval:
true`. `just pre_commit` is `justfile:18-19` and `just worktree_setup` is
`justfile:44`.

**P19 — the memex SERVER is already v1.1.0, so no server image bump.
VERIFIED.**
`deployments/applications/services.tf:171`: `memex_version = "1.1.0"`.

**P20 — hermes holds the memex ADMIN key today. VERIFIED.**
`deployments/applications/services/hermes.hcl:201` and `:405` both render
`MEMEX_API_KEY={{ .Data.data.admin_key }}` from
`vault_kv_secret_v2.memex_auth_keys`
(`deployments/applications/secrets.tf:79-86`), which writes `admin_key`
from `random_id.memex_admin_key` (`:71`). Load-bearing for Q3.

**P21 — both `env_passthrough` lists exist, carry the same three `MEMEX_*`
names, and must be updated together. VERIFIED.**
`deployments/applications/services/hermes.hcl:254-262` (terminal) and
`:265-273` (code_execution) each list `MEMEX_API_KEY`,
`MEMEX_SERVER_URL`, `MEMEX_VAULT`, then `NOMAD_TOKEN`, `NOMAD_ADDR`,
`CONSUL_ADDR`, `GH_TOKEN`, `GITHUB_PERSONAL_ACCESS_TOKEN`. Identical
contents, so a half-update is easy to miss. §8 check H3 is its detector.

**P22 — the exact identity-stanza shape hermes needs validates clean on
this cluster. VERIFIED (live, read-only).**
probe: `nomad job validate <scratch-spec.hcl>`, which never registers a
job. A scratch spec with `vault {}` plus `identity { name = "memex", aud =
["memex"], file = true, filepath = "secrets/nomad_memex.jwt", ttl = "1h",
change_mode = "restart" }` returns `Job validation successful` with no
warnings. The D1 probe shape (a second identity named `vault_default` with
`aud = ["vault.io"]`) also validates, with one expected warning: `Task
probe has an identity called vault_default but no vault block`.
