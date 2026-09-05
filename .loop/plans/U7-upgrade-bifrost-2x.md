---
epic = "upgrade"
depends_on = []
priority = 30
summary = """Bump the Bifrost gateway pin from 1.6.7 to 2.0.0 so its rerank endpoint accepts `documents` as a list of bare strings. 2.0.0 is the first release carrying `RerankDocument.UnmarshalJSON`; no 1.6.x backport exists. OV1-openviking-service depends on this ticket (`depends_on = ["U7-upgrade-bifrost-2x"]`) and holds the embark bypass in reserve as a documented fallback if this one stalls. Two lines of value change plus two now-false comments; the weight is in proving the Terraform bifrost provider still plans clean against a 2.0.0 gateway and in the outage window for Hermes, Memex and embark."""
premise = { Q0 = "Bifrost manages its own config_store schema migration at startup; operator accepted this without independent verification, and specifically did not verify whether 1.6.7 can read a 2.0.0-migrated schema", Q1 = "the three post-upgrade auth behaviors that no repo file produces (inference auth enforced, /metrics behind basic auth, no unauthenticated admin path) are worth a new gated producer rather than a labelled proxy, because two of the three are security posture", Q2 = "the Terraform bifrost provider at the locked 0.1.1 decodes a 2.0.0 gateway's virtual-key responses without a version bump", Q3 = "setup_token stays absent from config.json because a config_store that already holds an admin never reaches the first-admin path", Q4 = "sending documents as bare strings only is sufficient regression cover, because 2.0.0 normalizes the bare-string and object forms into the same struct", Q5 = "an unattended apply is acceptable because no agent traffic is expected through the gateway during this session" }
measured_against = { Q0 = { kind = "operator-decision", version = "2026-09-05", ref = "deployments/applications/services.tf:562 states the startup migration; decision relayed by the coordinator during planning", note = "downgrade-readability was raised as an open uncertainty and deliberately closed by operator decision rather than by probe. If a rollback ever fails, this is the premise that broke." }, Q1 = { kind = "agent-decision", version = "2026-09-05", ref = "coordinating agent under an explicit grant of full loop control from JasperHG90, operator offline; resolved widen-surface, adding scripts/bifrost_smoke.py to the code surface", note = "the unmeasurable-requirement fork. Chosen over declared-proxy because a /health poll measures process start, not auth posture. If the smoke script is ever quietly dropped, this requirement silently reverts to unmeasured." }, Q2 = { kind = "agent-decision", version = "2026-09-05", ref = "coordinating agent, same grant; provider constraint at deployments/applications/providers.tf:27-30 stays ~>0.1.0, resolving to 0.1.1", note = "rests on P7, which is structural evidence only. A plan/apply failure on decode makes this the premise that broke, and the fix is a follow-up provider bump with the failure in hand." }, Q3 = { kind = "agent-decision", version = "2026-09-05", ref = "coordinating agent, same grant; setup_token stays out of the config.json at deployments/applications/services/bifrost.hcl:121-195", note = "rests on the store already holding an admin (P8 lists four virtual keys behind admin basic auth). Q1 smoke assertion 3 is what would catch it if wrong." }, Q4 = { kind = "agent-decision", version = "2026-09-05", ref = "coordinating agent, same grant; scripts/embark_rerank.py:123 sends bare strings only", note = "the object form stays valid upstream and is simply no longer exercised here." }, Q5 = { kind = "agent-decision", version = "2026-09-05", ref = "coordinating agent, same grant, operator offline and unreachable for the apply window", note = "no-traffic is an EXPECTATION, not a guarantee. Nothing in this repo reserves the gateway or drains it, so an in-flight Hermes or Memex turn during the restart fails rather than retries." } }
tags = ["bifrost", "upgrade", "terraform", "nomad", "rerank", "embark", "postgres", "openviking"]
---

# Ticket: U7-upgrade-bifrost-2x

## 1. Title

Bump the Bifrost gateway pin from `1.6.7` to `2.0.0` so `/v1/rerank`
accepts `documents` as a list of bare strings.

## 2. Size / Effort

**M**, upper end. Two value changes and two comment corrections across
three files, plus one new ~120-line gated Python probe. The size comes
from what has to be proven, not from what is typed:

- Major version bump. Six upstream breaking changes to check off, one
  Postgres config_store schema migration at startup.
- The Terraform `bifrost` provider (locked `0.1.1`) decodes Bifrost's VK
  API responses. Nothing proves compatibility short of a real
  `terraform plan`/`apply` against a running 2.0.0 gateway.
- `scripts/bifrost_smoke.py` is new scope, added when §11 Q1 resolved
  `widen-surface`. It is a strict-mypy file under the existing `scripts/`
  hooks that must run against BOTH gateway versions, because its
  before-run is what makes its after-run mean anything.
- Single instance on radxa, applied unattended (§11 Q5). Hermes, Memex and
  embark all lose traffic for the restart, with nobody watching.

Not L: no new service, no new dependency, no new Terraform resource. The
new file is a probe, and the Terraform diff is still one attribute.

U5 (`.loop/archive/U5-upgrade-hermes-bifrost-versions/plan.md:12-16`) was
S/M for a comparable-looking three-line diff, but it was a minor bump with
no API-consumer downstream. Do not copy its sizing.

## 3. Triggered by

Operator: "Bump bifrost to 2.0.0".

The reason it exists: `OV1-openviking-service` is blocked on it. Every
OpenViking rerank client emits `documents` as a list of plain strings;
Bifrost 1.6.7 rejects that shape with a flat 400 before the request reaches
embark. OV1 carries this as premise Q2
(`.loop/plans/OV1-openviking-service.md:7`) and has already settled the
fork in this ticket's favor: it declares
`depends_on = ["U7-upgrade-bifrost-2x"]`
(`.loop/plans/OV1-openviking-service.md:3`), states "No rerank bypass.
Rerank stays on the gateway (R5)"
(`.loop/plans/OV1-openviking-service.md:126`), and records its Q2 as
"RESOLVED by operator decision: upgrade the gateway"
(`.loop/plans/OV1-openviking-service.md:617`). Pointing rerank straight at
embark is now OV1's documented FALLBACK if this ticket stalls, out of
scope there unless it does
(`.loop/plans/OV1-openviking-service.md:624-629`). So this upgrade is not
an optimization for OV1. It is the path OV1 chose.

## 4. Context

**The pin.** `deployments/applications/services.tf:537` sets
`bifrost_version = "1.6.7"`, interpolated at
`deployments/applications/services/bifrost.hcl:40` as
`docker.io/maximhq/bifrost:v${bifrost_version}`. One knob, one number,
one place it is written.

**The blocker, measured.** Against the live gateway (P3): object
documents return 200 with populated `routing_info`; bare-string documents
return 400 `{"is_bifrost_error":false,...,"message":"Invalid request
payload"}` with EMPTY `routing_info`, meaning Bifrost rejects at its own
edge and embark never sees the request. embark itself accepts both
spellings.

**The fix.** 2.0.0 adds `RerankDocument.UnmarshalJSON`, which tries a bare
string first and falls back to the object shape
(https://github.com/maximhq/bifrost/blob/transports/v2.0.0/core/schemas/rerank.go#L26-L41). The method is
absent at every 1.6.x tag through `v1.6.11` (P4), so 2.0.0 is the minimum
version that fixes this and there is no backport to wait for.

**Two comments in the repo record the old behavior as fact** and become
wrong on apply:

- `deployments/applications/services/bifrost.hcl:107-112` ("Bifrost's own
  rerank schema takes `documents` as OBJECTS, not strings").
- `scripts/embark_rerank.py:116-118` (the `rerank()` docstring saying
  Bifrost requires objects), with the workaround itself at
  `scripts/embark_rerank.py:123`.

`scripts/embark_rerank.py` is the repo's only executable check of this
behavior. Its `run_suite` asserts rank ordering across three cases rather
than printing scores, so it fails when the model or the wire format is
wrong.

**What the upgrade touches around it.** Virtual keys are Terraform-managed
(`deployments/applications/services.tf:621`, `:636`) through the
`AirHelp-OSP/bifrost` provider, constrained `~>0.1.0` in
`deployments/applications/providers.tf:27-30`, resolving to `0.1.1` (P7;
the lock file is gitignored, so it carries no citable anchor). The
provider hits `/api/governance/virtual-keys` and `/api/providers` with
HTTP Basic auth.
`null_resource.bifrost_ready`
(`deployments/applications/services.tf:578-607`) polls `/health` for 120s
after every redeploy and gates both the VK resources and the provider's
own configuration (`deployments/applications/providers.tf:59-70`).

## 5. Non-goals / out of scope

- **Reworking OV1.** OV1 already routes rerank through the gateway (§3);
  building the OpenViking service that does so belongs to
  `OV1-openviking-service`, not here. This ticket only removes the
  constraint that made the bypass its recommendation.
- **Bumping the Terraform `bifrost` provider** past the locked `0.1.1`.
  Newer releases exist (`v0.2.0` through `v0.3.0`); see §11 Q2. Adding a
  second uncontrolled variable to a major gateway bump is the thing to
  avoid.
- **Adding `setup_token` to config.json.** New top-level key in 2.0.0,
  governs first-admin bootstrap only. See §11 Q3.
- **Touching the Grafana dashboard or alert rules.** Verified
  unnecessary: `deployments/infrastructure/services/grafana/bifrost.json`
  queries only Prometheus instrument names (`bifrost_active_requests`,
  `bifrost_provider_key_up`, `bifrost_upstream_latency_seconds_bucket`
  and eight more), which the migration guide says did not change. No
  `gen_ai.*` span attribute and no `x-bf-prom-*` header appears anywhere
  under `deployments/`.
- **The `allow_private_network` comment** at
  `deployments/applications/services/bifrost.hcl:114-118`. Still correct,
  and load-bearing enough that it is a premise rather than a note: see
  **P16**, the assumption whose failure would be both catastrophic and
  invisible to every other check here.
- ~~**Running `just apply` against the cluster.**~~ **NO LONGER A
  NON-GOAL.** U5 left the apply to the operator
  (`.loop/archive/U5-upgrade-hermes-bifrost-versions/plan.md:82-86`) and so
  did this ticket until §11 Q5 resolved. The apply now runs in this
  session, unattended, and is §10 step 4. Kept as a struck line rather than
  deleted because the change of scope is the thing a reader needs to
  notice.
- **Digest pins.** Plain-tag convention holds.
- **Independently verifying Bifrost's config_store schema migration**, or
  whether 1.6.7 can read a 2.0.0-migrated schema. Closed by operator
  decision and recorded as front-matter premise `Q0`.

## 6. Requirements & restrictions

Each requirement names the thing that produces its observable.

1. **`bifrost_version` becomes `"2.0.0"` at
   `deployments/applications/services.tf:537`, and no other value in that
   file changes.** Producer: `git diff` of
   `deployments/applications/services.tf` (§7). `bifrost.hcl:40`
   interpolates the variable and needs no edit.

2. **`scripts/embark_rerank.py` sends `documents` as bare strings and its
   `run_suite` passes 3/3 against the upgraded gateway.** Producer:
   `scripts/embark_rerank.py` (§7), run in this session against the live
   cluster with a virtual key read from Vault (§11 Q5). A 3/3 also proves
   the request reached embark and came back ranked, which is P16's SSRF
   premise made observable: had 2.0.0's hardening reached a custom
   provider's private-IP `base_url`, this is the requirement that would
   fail. This is the requirement the whole ticket exists
   for: it exercises exactly the shape OV1 emits. Order matters, see §8.

3. **`terraform plan` from `deployments/applications/` reports no diff on
   `bifrost_virtual_key.hermes` or `bifrost_virtual_key.memex` after the
   apply, and the apply itself does not fail the post-apply consistency
   check.** Producer: `terraform plan -var-file=./vars/prod.tfvars`, the
   var-file the `apply` recipe uses
   (`deployments/applications/justfile:13-24`), over
   `deployments/applications/services.tf` (§7). This is the single most
   likely way the upgrade breaks: the provider's `VirtualKeyResponse`
   mirrors Bifrost's `TableVirtualKey` JSON, so a field rename or a
   response-ordering change breaks plan/apply even though the paths are
   unchanged. Two specific things it proves:
   - The response decode survives (P7).
   - `provider_configs` still comes back in alphabetical order by
     `provider`. `deployments/applications/services.tf:615-620` records
     the measured gotcha: any other order fails with "produced an
     unexpected new value: .provider_configs[N].provider", the write
     lands and the plan errors.
   Runnable in this session. It needs the cluster tokens `localstack env`
   exports, and this session carries `CONSUL_HTTP_TOKEN`, `NOMAD_TOKEN` and
   `VAULT_TOKEN` (presence and length checked, never printed). What is NOT
   reproducible is a review pass running without them: U5 recorded exactly
   that as inherent
   (`.loop/archive/U5-upgrade-hermes-bifrost-versions/reflection.md`,
   `reviewer-could-not-run-plan`). So a reviewer that cannot produce this
   evidence has hit a session limit, not a defect in the work.

4. **The gateway returns to health so the apply does not wedge.**
   Producer: `null_resource.bifrost_ready`'s `local-exec` provisioner
   (`deployments/applications/services.tf:592-606`, §7). It polls
   `/health` 60 times at 2s intervals and fails the apply otherwise, so
   it produces its own verdict. If 2.0.0 changed `/health`'s path or made
   it require auth, every apply from here on would stall for 120s and
   then fail. P9 says it did not.

5. **Both comments that assert the object-only wire format are corrected
   in the same commit.** Producer: `git diff` of
   `deployments/applications/services/bifrost.hcl` and
   `scripts/embark_rerank.py` (§7). Required by
   `.claude/rules/minimal-comments.md`: pre-existing comments stay put
   unless the change makes them wrong, and this change makes both wrong.
   Correct them rather than deleting: they record a measured constraint
   and its version boundary, which no source states.

6. **`scripts/bifrost_smoke.py` asserts five behaviors and is run BEFORE
   the bump as well as after.** Producer: `scripts/bifrost_smoke.py`
   (§7). Assertions 1-3 come from §11 Q1's `widen-surface` resolution;
   assertions 4 and 5 were added in cycle 3, to give premise `Q0` an
   observable and to guard both halves of P16. Each carries its measured
   1.6.7 baseline, from P17 except assertion 5 which uses P19:
   - `client.enforce_auth_on_inference: true`
     (`deployments/applications/services/bifrost.hcl:126`) still rejects an
     inference request carrying no virtual key. **Send OBJECT-form
     documents**, `[{"id":"0","text":"a"}]`, on BOTH runs. Baseline:
     `POST /v1/rerank` with no `x-bf-vk` returns 401 with
     `type: virtual_key_required`, and with an unknown `x-bf-vk` returns 401
     with `type: virtual_key_not_found`. Assert on the `type` field, not on
     the bare status: a 401 alone does not distinguish enforcement from any
     other rejection.

     The shape is pinned because at 1.6.7 payload parsing PRECEDES the
     virtual-key check (P18), so the same request with bare-string documents
     returns 400 `Invalid request payload` and measures the parser, not the
     auth. Pinning it to objects makes the gateway version the only variable
     between the before-run and the after-run, which is the entire point of
     having a before-run. Do NOT soften this assertion if a bare-strings
     variant looks inconsistent across versions: that inconsistency is P18
     working as designed, not a flaw in the assertion.

     Expect the mechanism to differ after the bump even where the status
     matches. At 2.0.0 bare strings parse (P4), so an unkeyed BARE-STRING
     probe returns 401 there against 400 at 1.6.7. That is the fix landing,
     not a regression. The script must not compare a bare-strings probe
     across versions and call the difference a failure.
   - `/metrics` still demands basic auth, which the Prometheus scrape at
     `deployments/infrastructure/services/prometheus.hcl:129-133` depends
     on. Baseline: 401 without credentials, 200 with them.
   - 2.0.0's `setup_token` opens no unauthenticated admin path on a store
     that already holds an admin. Baseline: `/api/governance/virtual-keys`,
     `/api/providers` and `/api/config` each 401 without credentials, and
     `/api/governance/virtual-keys` returns 200 with them.
   - Every virtual key present before the bump is present after it, by name.
     Baseline: four, `hermes`, `memex`, `jasper-laptop-cc` and `Leo` (P8).
     Two are Terraform-managed and two are not, so Terraform's own plan
     (§6.3) cannot see the unmanaged pair at all. This is the only
     observable this ticket has for premise `Q0`: the config_store schema
     migration was accepted by operator decision without verification, and
     keys disappearing across it is what "the migration went wrong" would
     look like from outside. Uses the same authenticated
     `GET /api/governance/virtual-keys` call assertion 3 already makes, so
     it costs one comparison, not one request.

   - An embeddings call through the gateway as `embark/embedding` returns
     200 with a 768-element vector. Baseline (P19): `POST /v1/embeddings`
     with `{"model":"embark/embedding","input":"dimension probe"}` returns
     200, `data[0].embedding` of length 768, and
     `extra_fields.routing_info` naming provider `embark` and key
     `embark-cluster`. The nesting is load-bearing: `routing_info` sits
     under `extra_fields`, NOT at the top level. The 200 response's
     top-level keys are `data`, `extra_fields`, `model`, `object` and
     `usage`, so a script that reads `routing_info` beside `model` and
     `usage` raises `KeyError` and fails its own blocking before-run.

     This is the guardrail for BOTH halves of P16, not a duplicate of
     §6.2. Embedding and rerank are different code paths on Bifrost's side
     but share one provider `network_config`
     (`deployments/applications/services/bifrost.hcl:158-163`), so if
     2.0.0's SSRF hardening had widened to provider `network_config` they
     would fail together on the same private-IP `base_url`. Kept separate
     from §6.2 because the converse does not hold: a break confined to the
     embeddings path would leave `run_suite` green at 3/3 and ship a silent
     regression into Memex's only embedding route. One request answers it.

   The before-run is not optional. A post-only assertion cannot tell "2.0.0
   broke it" from "it was never true", which is the whole reason this stopped
   being a `declared-proxy`. Both runs are read-only: assert on GETs and on
   a rerank POST that carries no key, never on an admin-creating write.

7. **Comment edits inside the jobspec are free here, and only here.**
   `.claude/rules/terraform-file-layout.md` records that editing a
   comment in a jobspec re-registers the Nomad job, because
   `templatefile()` folds the whole file into `nomad_job.jobspec`. That
   cost is already paid: `bifrost_version` is a template variable, so the
   jobspec hash changes from the version bump regardless. Do not use this
   as license to tidy anything else in the file.

8. **No new file in the Terraform roots.** `bifrost_version` stays in
   `deployments/applications/services.tf`, where the `nomad_job` lives, per
   `.claude/rules/terraform-file-layout.md`'s one-file-per-subsystem
   table.

9. **Plain language in the corrected comments.**
   `.claude/rules/plain-language.md` governs comments and commit
   messages, not just prose.

10. **Fix, do not skip, anything the gates surface.**
   `.claude/rules/pre-existing-issues.md`. `scripts/` is inside mypy's
   strict scope (`.pre-commit-config.yaml`, the `mypy` hook's
   `files: '^(cli|scripts)/'`), so both the edited script and the new
   `scripts/bifrost_smoke.py` must be strict-clean. `rerank()`'s
   `documents` parameter is already `list[str]`, so passing it through
   unwrapped types without a change.

## 7. Code surface

- **`deployments/applications/services.tf:537`** — `bifrost_version =
  "1.6.7"` becomes `"2.0.0"`. The only value change in this file.
- **`deployments/applications/services/bifrost.hcl:107-112`** — rewrite
  the comment block. It currently states the object-only constraint as
  present tense. New text records that 2.0.0 accepts both spellings, that
  1.6.x accepted objects only, and keeps the still-true sentence about
  the reranker returning raw logits so a negative `relevance_score` is
  normal. Do not touch line 40 (interpolation, unchanged) or lines
  114-118 (`allow_private_network`, still correct).
- **`scripts/embark_rerank.py:123`** — `"documents": [{"id": str(i),
  "text": d} for i, d in enumerate(documents)]` becomes `"documents":
  documents`. The `id` field is not read back; `run_suite` and `run_file`
  both index results by `r["index"]` (lines 142, 148, 178).
- **`scripts/embark_rerank.py:116-118`** — rewrite the `rerank()`
  docstring's second paragraph. It currently says Bifrost requires
  objects. Docstrings are API surface and exempt from the
  no-narration bullets in `.claude/rules/minimal-comments.md`, so this
  stays a docstring. Only its content changes.
- **`scripts/bifrost_smoke.py`** (NEW) — the producer for §6.6. Asserts
  the five behaviors in §6.6 against a `--base-url`, pinning OBJECT-form
  documents for the inference-auth probe (P18), reads admin
  credentials and a virtual key from Vault the way
  `scripts/embark_rerank.py:97-108` already does (never printing either),
  and exits non-zero on the first failed assertion so it works as a
  before/after gate rather than a report. Lands under the existing
  `scripts/` hooks, so it is ruff-, ruff-format- and strict-mypy-clean on
  arrival.

Four files: three edited, one created. No other file needs touching, and
no Terraform root gains one (§6.8). Grep for `bifrost` across
`deployments/`, `docs/` and `scripts/` returns no other version
reference: the tag appears exactly twice, at
`deployments/applications/services.tf:537` (the value) and
`deployments/applications/services/bifrost.hcl:40` (the interpolation).

## 8. Tests & validation gates

**Repo gates** (from `.loop/config.json` `gates` and
`.pre-commit-config.yaml`, not assumed):

- `just pre_commit` from the repo root (root `justfile:18-19`, runs
  `pre-commit run --all-files`). Across the four files in §7 that fires:
  `terraform-fmt` (`terraform fmt -check -recursive`),
  `terraform-validate` (`scripts/tf_validate.sh`, which validates all
  three roots offline), `nomad-fmt` (`nomad fmt -recursive`), `ruff`,
  `ruff-format`, `mypy` (strict, `--config-file cli/pyproject.toml`, and
  `scripts` is in its argument list), `check-ast`, `debug-statements`,
  `end-of-file-fixer`. The last six also cover the new
  `scripts/bifrost_smoke.py`, which is why it can be a gated producer
  rather than an ungoverned helper.
- `terraform plan -var-file=./vars/prod.tfvars` from
  `deployments/applications/`. Use `plan`, not `just apply`: the recipe
  applies. Expect exactly `nomad_job.bifrost` (image tag and the two
  comment lines inside the jobspec) plus the `null_resource.bifrost_ready`
  replacement its jobspec hash forces. Nothing else.

**Reproducing test, in this order.** `.claude/rules/python-testing.md`
requires a bug fix to reproduce first:

1. Before bumping the pin, apply only the
   `scripts/embark_rerank.py:123` change and run
   `python3 scripts/embark_rerank.py` against the live 1.6.7 gateway.
   Expect it to fail: `urllib.error.HTTPError: 400`. That is the blocker,
   reproduced from the repo's own tooling rather than from a hand-rolled
   curl.
2. Bump the pin, apply, re-run. Expect `3/3 cases ranked correctly`.

**Auth-posture check, before and after** (§6.6, from §11 Q1). Run
`python3 scripts/bifrost_smoke.py` against the live gateway BEFORE the
apply to capture the 1.6.7 baseline, then again after. Both runs must
pass. A failure on the before-run means the baseline itself is wrong and
the bump should not proceed until that is understood; a pass-then-fail
means 2.0.0 changed the behavior. Home: `scripts/bifrost_smoke.py`,
listed in §7. Content is gated by `just pre_commit` (ruff, ruff-format,
strict mypy, all scoped `^(cli|scripts)/`). The live runs happen in this
session (§11 Q5), not after handover.

Home: `scripts/embark_rerank.py`, listed in §7. `scripts/` holds no
pytest project (`.pre-commit-config.yaml` says so in the
`tf-block-diff-self-test` hook comment), so this is a runnable probe, not
a collected test. U5's equivalent was left to the operator
(`.loop/archive/U5-upgrade-hermes-bifrost-versions/plan.md:157-161`); this
one runs in-session under §11 Q5. It still needs the live cluster and a
virtual key, so a review pass without those cannot reproduce it. Do not
treat a missing reviewer run as a defect in the work.

**Eval marker:** `.loop/evals/U7-upgrade-bifrost-2x.md`.
`.loop/config.json` sets `require_eval: true`, so the loop refuses pickup
until it exists. Co-author it with the `create-eval` skill. Rows should
cover, at minimum: the pin value change and its isolation, the two
comment corrections, the bare-string payload, the terraform plan showing
only the expected two resources, and the five `bifrost_smoke.py`
assertions with their before/after runs. Row the inference-auth assertion
with the document shape named, or it scores something P18 says is a
different measurement.

## 9. Risk assessment

**Lead risk: the Terraform provider's response-schema compatibility.**
The `bifrost` provider at `0.1.1` decodes `/api/governance/virtual-keys`
responses into `VirtualKeyResponse`, documented in its own source as
mirroring Bifrost's `TableVirtualKey` JSON. Static evidence says it
survives (P7: additive-only struct diff, plain `json.Unmarshal` with no
`DisallowUnknownFields`; P8: the live 1.6.7 response already carries four
fields the struct does not declare and omits two it does, so lenient
decoding is already load-bearing). But static evidence proves the shape,
not the run. The ordering half is genuinely unresolved: nothing outside a
live plan tells you whether 2.0.0 still returns `provider_configs`
alphabetically. Failure mode is loud and mid-apply: the write lands, then
"produced an unexpected new value: .provider_configs[N].provider" errors
the plan, leaving Terraform's state and Bifrost's disagreeing.
Recovery is a re-plan and, if ordering genuinely changed, reordering the
`provider_configs` lists at
`deployments/applications/services.tf:623-627` and `:638-642`.

**Second risk: the outage window, taken unattended.** §11 Q5 resolved to
apply in this session with the operator offline, so nothing human is
watching the restart and nothing will notice a wedged apply until someone
comes back. Hermes and Memex both hold virtual keys and route model
calls through this gateway, and embark is reachable only through it
(`deployments/applications/services.tf:556-559`). One instance, pinned to
radxa-dragon-q6a
(`deployments/applications/services/bifrost.hcl:6-9`). The window is a
2.0.0 image pull on arm64, container start, and the config_store schema
migration, and the apply blocks on `bifrost_ready` for up to 120s after
that. Anything longer and the apply fails with the gateway possibly still
starting. `BifrostGatewayDown` fires after 5m
(`deployments/infrastructure/services/grafana/alert-rules.yaml:436-469`),
which is the signal to watch. Agent traffic is down for the duration.

Two costs the unattended decision carries, stated plainly because nobody
is present to absorb them:
- **In-flight turns fail rather than retry.** Nothing in this repo drains
  or reserves the gateway before a redeploy. A Hermes or Memex turn
  already routed through it when the alloc stops returns an error to its
  caller.
- **"No traffic right now" is an expectation, not a guarantee.** Nothing
  enforces it. Hermes runs on a schedule this ticket does not read, and
  the two unmanaged virtual keys from P8 (`jasper-laptop-cc`, `Leo`) are
  human-held and can fire at any time. §10 step 1 therefore says to CHECK
  for in-flight traffic rather than assume none.

**Reversibility.** Revert `deployments/applications/services.tf:537` to
`"1.6.7"` and re-apply. The old image is not deleted from Docker Hub (P5
confirms `v1.6.7` still resolves). Per front-matter premise `Q0`, the
operator has accepted that Bifrost manages its own config_store
migration, so a binary revert is treated as sufficient. That premise is
the one to revisit first if a rollback misbehaves.

**Backstop, verified.** `nomad_job.backup_postgres`
(`deployments/infrastructure/services.tf:638`) renders
`deployments/infrastructure/services/backup-postgres.hcl`, a Nomad
`periodic` batch job: `crons = ["0 2 * * *"]`, `time_zone =
"Europe/Amsterdam"`, `prohibit_overlap = true`, pinned to
radxa-dragon-q6a. Its `pgdump` task runs `pg_dumpall` on
`docker.io/library/postgres:18` and the `upload` task rclones the gzip to
GCS under `postgres/`. `pg_dumpall` covers all databases plus roles and
globals, so the `bifrost` config_store is in it, and
`docs/gcs-backups.md:36,109` records a 180-day bucket lifecycle with
dated dumps accumulating, so there is real restore history.

Two properties of that backstop worth knowing before you lean on it, both
arguing for the runbook's pre-step in §10 rather than against the backup:

- RPO is up to ~24h. An afternoon upgrade sits hours after the 02:00
  dump. Anything Bifrost wrote to the config_store in between is not in
  it, and it writes real state: the live gateway holds two virtual keys
  Terraform does not manage, `jasper-laptop-cc` and `Leo` (P8), created
  through the admin UI.
- It is a cluster-wide `pg_dumpall`, not a per-database dump. Restoring
  it touches memex, phoenix, ducklake, openviking and the roles. A naive
  `psql -f` of the whole archive would stomp every other database on the
  node.

**Blast radius outside Bifrost:** none. No other Terraform resource, no
other jobspec, and no dashboard reads anything this changes (P10).

## 10. Subtickets

None. One loop iteration, four files: three edited, one created.

Deployment runbook, after review passes. Steps 1-3 run BEFORE the apply;
their outputs are the baseline the rest is judged against. Runs unattended
per §11 Q5, so the order matters more than usual: nobody is watching to
catch a skipped step.

1. **Check for in-flight traffic**, do not assume none. §9 explains why
   this is an expectation rather than a guarantee. Abort if a Hermes or
   Memex turn is mid-flight.
2. `python3 scripts/bifrost_smoke.py` against the live 1.6.7 gateway.
   Expect every assertion to pass. This is the baseline; without it
   the after-run cannot distinguish a regression from a thing that was
   never true.
3. `pg_dump -d bifrost` against the Postgres host, held locally. Cheap
   insurance and a clean single-database restore path, closing the two
   gaps in §9's backstop. Not a gate and not a §6 requirement.
4. `just apply` from `deployments/applications/`.
5. `curl -s http://192.168.2.50:8080/api/version`. Expect `"v2.0.0"`.
   The endpoint is registered in both tags
   (https://github.com/maximhq/bifrost/blob/transports/v2.0.0/transports/bifrost-http/handlers/config.go#L125)
   and answers unauthenticated on 1.6.7 today (P2).
6. `python3 scripts/bifrost_smoke.py` again. Expect the same passes as
   step 2. A pass-then-fail here is 2.0.0 changing auth posture and is
   grounds to roll back, not to investigate later.
7. `python3 scripts/embark_rerank.py`. Expect `3/3`.
8. `terraform plan -var-file=./vars/prod.tfvars`. Expect no diff on the
   two `bifrost_virtual_key` resources.
9. Confirm one Hermes chat turn and one Memex call complete.

## 11. Open questions

All resolved. Each was a real fork when raised; the reasoning that made it
one is kept below so the trail survives the decision. Decider for Q1
through Q5: the coordinating agent, under an explicit grant of full loop
control from JasperHG90, 2026-09-05, operator offline. Recorded
machine-readably in the front-matter `premise` and `measured_against`
tables, keyed by the same labels.

**Q1 — the gateway's post-upgrade behavior under an unchanged config.json
had no producer in this repo.** Tag: `unmeasurable-requirement`.
**RESOLVED `widen-surface`.**

Why it was a fork: the schema comparison (P6) proves config.json will
PARSE under 2.0.0. It does not prove the gateway BEHAVES the same, and
three behaviors that matter had no producer in the declared code surface:

- `client.enforce_auth_on_inference: true`
  (`deployments/applications/services/bifrost.hcl:126`) still rejects an
  inference request that carries no virtual key.
- `/metrics` still requires basic auth. The Prometheus scrape depends on
  it (`deployments/infrastructure/services/prometheus.hcl:129-133`), and
  `deployments/applications/services/bifrost.hcl:25-28` records that the
  service is deliberately not tagged `prometheus` for exactly this reason.
- 2.0.0's new `setup_token` does not open an unauthenticated first-admin
  path on a store that already has an admin.

Partial coverage already existed and was never the fork: §6.4's
`bifrost_ready` gate produces "the config parsed and the server came up
healthy", and §6.3's `terraform plan` produces "admin basic auth against
the governance API still works", because the provider authenticates that
way (`doRequest` at
https://github.com/AirHelp-OSP/terraform-provider-bifrost/blob/v0.1.1/internal/client/client.go#L78-L81).
What was left uncovered is the three bullets above.

The decision: add `scripts/bifrost_smoke.py` as the producer. It is now
§6.6 (requirement), §7 (code surface), §8 (gate) and §10 steps 2 and 6
(before and after runs). Chosen over `declared-proxy` because two of the
three are security posture and a silent regression there is worse than a
loud one, and a `/health` poll measures that a process started, not that
it enforces anything. Chosen over `split-ticket` because deferring the
three assertions would let the upgrade ship with its auth posture
unverified, which is the wrong order. Chosen over `drop-requirement`
because the operator is offline and cannot check by hand. §2 was revised
for the added scope. P17 records the 1.6.7 baseline the script asserts
against.

**Q2 — keep the Terraform `bifrost` provider at the locked `0.1.1`, or
bump it?** **RESOLVED: keep `0.1.1`. Do not bump.**

Why it was a fork: `deployments/applications/providers.tf:27-30`
constrains `~>0.1.0`; the gitignored dependency lock resolves that to
`0.1.1`. Upstream has `v0.2.0`, `v0.2.1`, `v0.2.2` and `v0.3.0`, so
staying put is a choice rather than a default.

The decision: P7 and P11 say the paths and the response shape both
survive, so there is no known reason to move, and bumping adds a second
uncontrolled variable to a major gateway upgrade. If §6.3's plan fails on
decode, that becomes a follow-up ticket with the failure in hand rather
than a guess made in advance.

**Q3 — add `setup_token` to config.json defensively?** **RESOLVED: do not
add it.**

Why it was a fork: it is the one new top-level key in 2.0.0, described
upstream as "required to create the very first admin account when no admin
account is configured yet ... if left unset, creating the first admin
account is rejected until this is configured". Left unexamined, it could
in principle have meant the gateway refusing to start, or coming up
unauthenticated.

The decision: this deployment has a persistent Postgres config_store with
an existing admin (P8 lists four virtual keys returned under admin basic
auth), so the first-admin path is unreachable. Adding the key would mean a
new Vault secret, a new template line and a new env var for a code path
that never runs. The residual worry is now covered directly rather than
argued away: it is the third assertion in §6.6's smoke check.

**Q4 — should `scripts/embark_rerank.py` send bare strings, or keep
objects and add strings as a second case?** **RESOLVED: bare strings
only.**

Why it was a fork: keeping both spellings would preserve the existing
regression cover while adding the new one, which is the conservative
instinct.

The decision: bare strings are the shape OV1 emits, so they are the one
worth regression-testing, and 2.0.0 normalizes both forms into the same
struct, so a second case would assert a code path the first already
covers. Keeping both doubles the suite's runtime against a live GPU for no
new information. The object form remains valid upstream; it is simply no
longer exercised here.

**Q5 — when should the apply run?** **RESOLVED: in this session,
unattended.**

Why it was a fork: Hermes, Memex and embark all stop for the restart, and
the usual answer is to pick a quiet window with someone watching.

The decision: the operator is offline and authorized the unattended run.
What that costs is recorded in §9 rather than waved past: in-flight turns
fail rather than retry, because nothing in this repo drains or reserves
the gateway before a redeploy; and "no agent traffic right now" is an
expectation with nothing enforcing it, since Hermes runs on a schedule
this ticket does not read and the two unmanaged virtual keys from P8 are
human-held. §10 step 1 therefore says to CHECK for in-flight traffic
before applying, not to assume none.

**Q0 — can 1.6.7 read a 2.0.0-migrated config_store schema?**
**RESOLVED by operator decision, 2026-09-05, before planning closed.**
Bifrost is treated as properly managing its own schema migration at
startup (`deployments/applications/services.tf:562`). Not carried as an
open uncertainty and not probed. Decided by JasperHG90 directly, unlike Q1
through Q5. Recorded in the front-matter `premise` table so the decision
leaves a trail if it turns out wrong.

## Premises / assumptions

- **P1** (VERIFIED). The pin is written once. Anchors:
  `deployments/applications/services.tf:537` reads `bifrost_version =
  "1.6.7"`; `deployments/applications/services/bifrost.hcl:40` reads
  `image = "docker.io/maximhq/bifrost:v${bifrost_version}"`.
  probe: `grep -rn 'bifrost:v\|1\.6\.7' deployments/ docs/ scripts/`
  returns those two lines and nothing else, so there is no third place to
  update.

- **P2** (VERIFIED, 2026-09-05). The running gateway is 1.6.7 and serves
  both liveness endpoints without credentials.
  probe: `curl -s http://192.168.2.50:8080/api/version` returns
  `"v1.6.7"`, HTTP 200, no auth header sent.
  probe: `curl -s http://192.168.2.50:8080/health` returns
  `{"components":{"db_pings":"ok"},"status":"ok"}`, HTTP 200, no auth
  header sent.

- **P3** (VERIFIED, 2026-09-05). The blocker reproduces. Virtual key read
  from Vault at `secret/default/hermes/bifrost` and never printed.
  probe: `curl -X POST http://192.168.2.50:8080/v1/rerank` with
  `model: embark/reranker`, twice.
  - Objects `[{"id":"0","text":...},{"id":"1","text":...}]` gave HTTP 200,
    `relevance_score` `0.3208027482032776` and `-5.246216297149658`, with
    `routing_info:
    {"provider":"embark","model":"reranker","key":"embark-cluster"}`.
  - Bare strings gave HTTP 400,
    `{"is_bifrost_error":false,"status_code":400,"error":{"message":"Invalid
    request payload"},"extra_fields":{"routing_info":{}}}`. The empty
    `routing_info` is the evidence that Bifrost rejects at its own edge
    rather than relaying an embark answer.
  Matches the behavior recorded at
  `deployments/applications/services/bifrost.hcl:107-112` and OV1's premise
  Q2 at `.loop/plans/OV1-openviking-service.md:8`.

- **P4** (VERIFIED, 2026-09-05). 2.0.0 is the minimum version that fixes
  it and no 1.6.x backport exists.
  probe: fetch `core/schemas/rerank.go` at tags `transports/v1.6.7`,
  `v1.6.8`, `v1.6.9`, `v1.6.10`, `v1.6.11`, `v2.0.0` and
  `grep -c 'func (d \*RerankDocument) UnmarshalJSON'` each. Count is 0 at
  every 1.6.x tag, 1 at `v2.0.0`.
  source: at 1.6.7 `RerankDocument` is a plain struct,
  https://github.com/maximhq/bifrost/blob/transports/v1.6.7/core/schemas/rerank.go#L4-L8 ; at 2.0.0 the new
  method carries the comment "UnmarshalJSON accepts either a bare string or
  an object. Every rerank API in the wild takes `documents: ["a", "b"]`, so
  the canonical route accepts that form and normalizes it",
  https://github.com/maximhq/bifrost/blob/transports/v2.0.0/core/schemas/rerank.go#L26-L41 .

- **P5** (VERIFIED, 2026-09-05). 2.0.0 is simultaneously the fix and the
  current release, and the rollback image still resolves.
  probe: `docker manifest inspect docker.io/maximhq/bifrost:v2.0.0`
  succeeds; so do `:v1.6.11` and `:v1.6.7`; `:v2.0.1` fails as missing.
  probe: `curl -s https://api.github.com/repos/maximhq/bifrost/tags` lists
  `transports/v2.0.0` as the newest non-prerelease tag, above
  `transports/v2.0.0-prerelease3` and `transports/v1.6.11`.

- **P6** (VERIFIED, 2026-09-05). The config.json at
  `deployments/applications/services/bifrost.hcl:121-195` PARSES under
  2.0.0. It says nothing about behavior. That gap is §11 Q1.
  probe: fetch `transports/config.schema.json` at both tags and compare
  with Python `json` plus `sha256` over `json.dumps(sort_keys=True)`.
  source: https://github.com/maximhq/bifrost/blob/transports/v2.0.0/transports/config.schema.json
  - Top-level `properties` keys identical except 2.0.0 adds `setup_token`.
  - `providers` and `config_store` sub-schemas byte-identical: digests
    `788d6d77f25b27b4` and `f7f55e23ee8cb4f8` at both tags.
  - `client` gained and lost no keys; only `mcp_tool_sync_interval`
    changed, which this deployment does not set. The three it does set at
    `deployments/applications/services/bifrost.hcl:123-127` are unchanged.
  - `$defs.auth_config` identical at both tags (`admin_password`,
    `admin_username`, `disable_auth_on_inference`, `is_enabled`), covering
    `deployments/applications/services/bifrost.hcl:128-134`.
  - `logs_store` gained and lost no keys. Its entire delta between the
    tags is one field on the POSTGRES branch,
    `config.oneOf[1].then.properties.matview_refresh_interval`, whose
    `pattern` goes from `^[0-9]+(ns|us|µs|ms|s|m|h)$` to
    `^(off|[0-9]+(ns|us|µs|ms|s|m|h))$` with a matching `description`
    edit (adds `off`, clamps positive values below 5s up to 5s). This
    deployment is on the SQLITE branch
    (`deployments/applications/services/bifrost.hcl:190-194`), so that
    field does not apply to it and the shape it does use is untouched.
  - `governance.virtual_keys` changed additively too
    (`is_access_profile_managed`), `required` unchanged at `["id","name"]`.

- **P7** (VERIFIED structurally, 2026-09-05; behaviorally UNCERTAIN until
  §6.3 runs). The Terraform provider's response decode survives.
  probe: fetch `framework/configstore/tables/virtualkey.go` at both tags
  and `diff`. The change is purely additive: `VKProvider` gains
  `ModelBudgets []VKProviderModelBudget`
  (`json:"model_budgets,omitempty"`) and `TableVirtualKey` gains
  `IsAccessProfileManaged bool`
  (`json:"is_access_profile_managed,omitempty"`). No field renamed,
  removed or retyped.
  source: https://github.com/maximhq/bifrost/blob/transports/v2.0.0/framework/configstore/tables/virtualkey.go
  source: the provider decodes with plain `json.Unmarshal` and no
  `DisallowUnknownFields`, so unknown fields are ignored:
  https://github.com/AirHelp-OSP/terraform-provider-bifrost/blob/v0.1.1/internal/client/client.go#L94-L100
  probe: the gitignored Terraform dependency lock in
  `deployments/applications/` resolves
  `registry.terraform.io/airhelp-osp/bifrost` to version `0.1.1` under the
  `~> 0.1.0` constraint. That file is gitignored, so it carries no citable
  anchor. The constraint it satisfies is at
  `deployments/applications/providers.tf:27-30`.

- **P8** (VERIFIED, 2026-09-05). Admin creds read from Vault at
  `secret/default/bifrost/credentials` and never printed.
  probe: `curl -u <admin>
  http://192.168.2.50:8080/api/governance/virtual-keys` returns HTTP 200
  and an envelope keyed `count/limit/offset/total_count/virtual_keys`.
  Four facts follow:
  - HTTP Basic auth against the governance API works today. That is the
    provider's mechanism.
  - `provider_configs` comes back alphabetically, `["embark", "gemini",
    "ollama"]`, for both `hermes` and `memex`, matching the ordering gotcha
    recorded at `deployments/applications/services.tf:615-620`.
    UNCERTAIN whether 2.0.0 preserves that ordering; only §6.3's plan
    settles it.
  - Each `provider_configs` entry carries `allow_all_keys`,
    `blacklisted_models`, `keys` and `virtual_key_id`, which the provider's
    `VKProviderConfigResponse` does not declare, and omits `budget` and
    `rate_limit`, which it does. Lenient decoding is therefore already
    load-bearing at 1.6.7, not something 2.0.0 would newly demand.
  - Two virtual keys exist that Terraform does not manage,
    `jasper-laptop-cc` and `Leo`. They live only in the Postgres
    config_store, so a database rollback drops state Terraform cannot
    recreate.

- **P9** (VERIFIED, 2026-09-05). `null_resource.bifrost_ready`'s poll
  target survives the bump at the source level. The definitive check is
  the apply itself, §6.4.
  probe: fetch `transports/bifrost-http/handlers/health.go` at both tags
  and `diff`. Byte-identical; it registers `r.GET("/health", ...)` at line
  28. Same for `transports/bifrost-http/lib/middleware.go`, also
  byte-identical.
  source: https://github.com/maximhq/bifrost/blob/transports/v2.0.0/transports/bifrost-http/handlers/health.go
  source: `/api/version` is registered in both,
  https://github.com/maximhq/bifrost/blob/transports/v2.0.0/transports/bifrost-http/handlers/config.go#L125

- **P10** (VERIFIED, 2026-09-05). Five of the six upstream breaking
  changes do not reach this deployment.
  source: https://docs.getbifrost.ai/migration-guides/v2.0.0
  - BC1 (plugin download SSRF) and BC2 (plugin creation needs admin auth):
    the config.json at
    `deployments/applications/services/bifrost.hcl:121-195` has no
    `plugins` array and no `server` block. The guide states custom
    providers use the separate, unmodified `allow_private_network`
    mechanism.
  - BC4 (`HTTPTransportPreHook` moves after auth): no custom Go plugin in
    this repo.
  - BC5 (`BifrostCost` restructured, `LogStore.BulkUpdateCost` signature):
    nothing here parses `cost`, and `logs_store` is the built-in sqlite one
    at `deployments/applications/services/bifrost.hcl:190-194`, not a
    custom implementation.
  - BC6 (observability alias removal): probe: parsing
    `deployments/infrastructure/services/grafana/bifrost.json` yields
    eleven instrument names, all `bifrost_*`, which the guide says did not
    change; zero `gen_ai.*` and zero `x-bf-prom-*` matches anywhere under
    `deployments/`.
  UNCERTAIN: whether the LABELS on those Prometheus metrics survive. The
  guide addresses instrument names and the custom-dimension header prefix,
  not label sets. Two rules read labels off `bifrost_provider_key_up`, and
  a rename would degrade them differently:
  `deployments/infrastructure/services/grafana/alert-rules.yaml:482`
  groups by `provider` (`sum by (provider) (...)`), so losing that label
  would break `BifrostProviderDown`'s grouping.
  `BifrostProviderKeyDown` does not group at all, `:515` is a bare
  `bifrost_provider_key_up == bool 0`; it consumes `key_name` only in its
  annotations at `:536-537`, so losing that label would blank the alert
  text rather than silence the alert. Not load-bearing for the upgrade,
  but worth an eye on the dashboard after the apply.

- **P11** (VERIFIED, 2026-09-05). BC3's `/api/governance` consolidation
  does not move the two paths the provider uses.
  source: https://docs.getbifrost.ai/migration-guides/v2.0.0 endpoint
  mapping table lists `/api/teams`, `/api/users`, `/api/roles`,
  `/api/audit-logs`, `/api/access-profiles`, `/api/resources`,
  `/api/operations`, `/api/permissions` and their children. It does not
  list `/api/governance/virtual-keys` (already canonical) or
  `/api/providers`. The same page states Basic auth remains a supported
  admin authentication method, and scopes the limit/offset pagination
  change to Team and User lists.
  probe: P8's live call shows the VK list already returns
  `count/limit/offset/total_count` at 1.6.7, so that pagination change
  cannot reach it.

- **P12** (OPERATOR-DECIDED, 2026-09-05, NOT independently verified).
  Bifrost manages its own config_store schema migration at startup, as the
  comment at `deployments/applications/services.tf:562` states. The
  operator accepted this without verification and specifically declined to
  establish whether 1.6.7 can read a 2.0.0-migrated schema, so that
  question stays UNCERTAIN by decision rather than by omission. Recorded in
  the front-matter `premise` table under `Q0`. This is the premise to
  revisit first if a rollback misbehaves.

- **P13** (VERIFIED). The Postgres backstop exists and covers the
  `bifrost` database. Anchors:
  `deployments/infrastructure/services.tf:638` declares
  `nomad_job.backup_postgres`, rendering
  `deployments/infrastructure/services/backup-postgres.hcl`, whose
  `periodic` block at lines 6-9 sets `crons = ["0 2 * * *"]`, `time_zone =
  "Europe/Amsterdam"` and `prohibit_overlap = true`, pinned to
  `radxa-dragon-q6a` by the constraint at lines 14-15. The `pgdump` task
  runs `pg_dumpall` piped through `gzip` on
  `docker.io/library/postgres:18` (lines 26-29) and the `upload` task
  rclones the result to GCS under `postgres/` (lines 54-56).
  `pg_dumpall` covers all databases plus roles and globals, so the
  `bifrost` config_store is in it. `docs/gcs-backups.md:36` and `:109`
  record the 180-day bucket lifecycle and that dated dumps accumulate.

- **P14** (VERIFIED). The gates are what the repo declares, not an
  assumption. Anchors: `.loop/config.json` declares
  `gates: ["just pre_commit"]`, `require_review: true`,
  `require_eval: true`, `max_review_cycles: 3` and a `plan-validator`
  planning pass. Root `justfile:18-19` defines `pre_commit` as
  `pre-commit run --all-files`. `.pre-commit-config.yaml` defines
  `terraform-fmt`, `terraform-validate` (running `scripts/tf_validate.sh`,
  which validates `deployments/infrastructure`,
  `deployments/applications` and `deployments/applications/modules/bucket`
  offline), `nomad-fmt`, and the `ruff`/`ruff-format`/`mypy` hooks scoped
  `^(cli|scripts)/`.
  probe: the three `pytest` hooks in `.pre-commit-config.yaml` are scoped
  to `cli/tests` and to the two service backends
  (`deployments/applications/services/dash/backend`,
  `.../registry-ui/backend`), each with its own `pyproject.toml`. None
  covers the Terraform roots, the jobspecs, or `scripts/`, and
  `.pre-commit-config.yaml` says the last part itself in the
  `tf-block-diff-self-test` hook comment ("scripts/ holds no pytest
  project, so the tool carries its own cases"). So no automated test in
  this repo can assert anything about the running gateway. Same constraint
  OV1 recorded as its premise Q7 at
  `.loop/plans/OV1-openviking-service.md:7`, and what makes §11 Q1 a real
  fork rather than a formality.

- **P15** (VERIFIED). `scripts/tf_block_diff.py` is not needed here.
  source: `.claude/rules/terraform-file-layout.md` requires it for proving
  a block REORGANIZATION moved blocks intact. This ticket moves no block;
  it changes one attribute value in place and edits comments.

- **P16** (VERIFIED, 2026-09-05). 2.0.0's SSRF hardening does NOT reach a
  custom provider's private-IP `base_url`. This is the assumption the most
  rides on: `deployments/applications/services/bifrost.hcl:154-163`
  configures `embark` with `base_url: "http://${embark_host}:8000"` at
  `:159`, guarded by `allow_private_network: true` at `:162`.
  `embark_host` is `192.168.2.46`
  (`deployments/applications/services.tf:558`), an RFC1918 address. If
  2.0.0's hardening had been widened from native plugin `.so` downloads to
  provider `network_config`, every embedding and rerank call to embark
  would fail on the private destination. That would destroy the exact
  capability this ticket exists to deliver AND take Memex embeddings down
  with it, while P1 through P15, the gates in §8 and the `bifrost_ready`
  health poll all still went green. Catastrophic and invisible to every
  other check here, which is why it is a premise and not the §5 note it
  started as.
  source: https://docs.getbifrost.ai/migration-guides/v2.0.0 , Breaking
  Change 1, verbatim: "Custom LLM providers are not affected. This
  hardening applies only to downloading native plugin ( .so ) binaries via
  framework/plugins. Custom providers (an LLM endpoint registered with a
  custom base_url, e.g. a self-hosted or OpenAI-compatible server) use a
  separate, unmodified mechanism (the existing per-provider
  allow_private_network setting) and are untouched by this change or by
  server.plugin_download_private_allowlist."
  The premise therefore rests on `allow_private_network` keeping its
  current meaning in 2.0.0, which the same sentence calls "unmodified".
  probe: P6's schema comparison independently corroborates the shape half,
  the `providers` sub-schema is byte-identical at both tags (digest
  `788d6d77f25b27b4`), so `allow_private_network` is neither removed nor
  redefined in the config contract. Re-check this one on the next Bifrost
  bump, where the guarantee may not be restated.

- **P17** (VERIFIED, 2026-09-05). The 1.6.7 auth posture that §6.6's smoke
  check asserts, measured so the script has a baseline to be written
  against rather than an assumption. Admin credentials read from Vault at
  `secret/default/bifrost/credentials` and a virtual key from
  `secret/default/hermes/bifrost`, neither printed. All probes read-only.
  probe: `curl` against `http://192.168.2.50:8080`, status codes only.

  | request | no credentials | with credentials |
  |---|---|---|
  | `GET /health` | 200 | n/a |
  | `GET /api/version` | 200 | n/a |
  | `GET /metrics` | 401 | 200 |
  | `GET /api/governance/virtual-keys` | 401 | 200 |
  | `GET /api/providers` | 401 | n/a |
  | `GET /api/config` | 401 | n/a |
  | `POST /v1/rerank`, OBJECT docs, no `x-bf-vk` | 401 | n/a |
  | `POST /v1/rerank`, OBJECT docs, unknown `x-bf-vk` | 401 | n/a |
  | `POST /v1/rerank`, STRING docs, no `x-bf-vk` | 400 | n/a |
  | `POST /v1/rerank`, STRING docs, unknown `x-bf-vk` | 400 | n/a |

  The document shape is part of the measurement, not a detail. The two
  OBJECT rows reject from governance and are distinguishable: no key
  returns `{"type":"virtual_key_required", ...,"message":"virtual key is
  required. Provide a virtual key via the x-bf-vk header."}` and an unknown
  key returns `{"type":"virtual_key_not_found", ...,"message":"virtual key
  not found. The provided virtual key does not exist or has been
  revoked."}`. Asserting on the `type` field rather than on the bare 401 is
  what makes assertion 1 mean "inference auth is enforced" instead of
  "something returned 401".

  The two STRING rows never reach governance at all. They carry no `type`
  and an empty `routing_info`, because the parser rejects them first
  (P18). An auth assertion written against the string form would therefore
  measure the parser, which is why §6.6 pins assertion 1 to objects.

  This is the row that would move if 2.0.0 regressed: a `/metrics` or
  `/api/*` endpoint answering 200 without credentials after the bump is
  the unauthenticated-admin failure §11 Q3 worried about, and a rerank
  without a key succeeding is `enforce_auth_on_inference` silently
  ceasing to apply. UNCERTAIN by construction whether 2.0.0 preserves any
  of it. That is the point: §6.6 measures it rather than assuming it, and
  the before-run in §10 step 2 is what makes the after-run in step 6
  attributable to the upgrade.

- **P18** (VERIFIED, 2026-09-05). At 1.6.7, payload parsing PRECEDES the
  virtual-key check on `/v1/rerank`. This is the trap §6.6 assertion 1 is
  written around, and it is easy to walk into on a ticket whose whole
  subject is the document shape.
  probe: four `POST /v1/rerank` calls against `http://192.168.2.50:8080`,
  crossing document shape with key state. No key material sent or printed;
  the keyed calls used an obviously bogus `x-bf-vk`.

  | documents | `x-bf-vk` | result |
  |---|---|---|
  | `[{"id":"0","text":"a"}]` | absent | 401 `virtual_key_required` |
  | `[{"id":"0","text":"a"}]` | bogus | 401 `virtual_key_not_found` |
  | `["a"]` | absent | 400 `Invalid request payload` |
  | `["a"]` | bogus | 400 `Invalid request payload` |

  The key state changes nothing for the string form: both 400. So the
  parser runs first and short-circuits before governance is consulted.
  Corroborated on the read side by the cycle-1 finding that
  `sonic.Unmarshal(ctx.PostBody(), req)` is the first thing the rerank
  handler does and that its failure branch returns the literal
  `"Invalid request payload"` this probe sees.

  Two consequences the smoke script must encode:
  - **Before and after must send the SAME shape**, and it must be the
    object form, so the gateway version is the only variable. §6.6 says so
    in the requirement itself.
  - **The string form's status is EXPECTED to change across the bump.** At
    2.0.0 bare strings parse (P4), so an unkeyed string probe returns 401
    there against 400 here. That is this ticket succeeding. A script that
    diffed a bare-strings probe before against after would read the fix as
    a regression and, under §8's blocking before-run rule, could stall the
    upgrade or invite someone to weaken the assertion.

- **P19** (VERIFIED, 2026-09-05). Embeddings reach embark through the
  gateway and come back at 768 dimensions. The baseline for §6.6's fifth
  assertion, and the second half of P16's guardrail.
  probe: `POST http://192.168.2.50:8080/v1/embeddings` with
  `{"model":"embark/embedding","input":"dimension probe"}` and a virtual
  key read from Vault at `secret/default/hermes/bifrost`, never printed.
  Returns HTTP 200, `len(data[0].embedding) == 768`, `model` `embedding`,
  `usage` `{"prompt_tokens": 4, "total_tokens": 4}`, and
  `extra_fields.routing_info`
  `{"provider":"embark","model":"embedding","key":"embark-cluster"}`.
  `routing_info` is nested under `extra_fields`; the top-level keys are
  `data`, `extra_fields`, `model`, `object` and `usage`.

  The `routing_info` is the load-bearing part: it proves the call reached
  embark at `http://192.168.2.46:8000` rather than being answered or
  refused at Bifrost's edge, which is exactly the failure P16 says would be
  catastrophic and invisible. UNCERTAIN whether 2.0.0 preserves it; that is
  what the after-run measures.

