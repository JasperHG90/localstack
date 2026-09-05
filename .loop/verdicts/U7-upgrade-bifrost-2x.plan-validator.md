---
verdict: pass-with-required-fixes
plan: 3dc861971bfcb2ea21fe07b9530bbb1f2c39ed59d52dfcb1052d824bd7f4da7b
bound_paths: front-matter, 5, 6, 7, 8, 9, 10, premises
scope: 5d8faf358b6e77e8bb3cfa64f31c73da7cadb95ab348c3e175250f89adc2707d
fix_sections: 6, 8, 10, premises
citations: deployments/applications/services/bifrost.hcl:126 =     "enforce_auth_on_inference": true
  deployments/applications/services/bifrost.hcl:158 =       "network_config": {
  deployments/applications/services/bifrost.hcl:162 =         "allow_private_network": true
  deployments/applications/services.tf:537 =       bifrost_version  = "1.6.7"
  deployments/applications/services.tf:562 =   # Bifrost migrates its config_store schema on startup, so the DB must exist
  deployments/applications/services.tf:621 = resource "bifrost_virtual_key" "hermes" {
  deployments/applications/services.tf:636 = resource "bifrost_virtual_key" "memex" {
  deployments/infrastructure/services/prometheus.hcl:129 =           - job_name: bifrost
  scripts/embark_rerank.py:123 =         "documents": [{"id": str(i), "text": d} for i, d in enumerate(documents)],
  .pre-commit-config.yaml:71 =         entry: python3 scripts/tf_block_diff.py --self-test
  .pre-commit-config.yaml:87 =         entry: python3 scripts/check_oauth2_proxy_guard.py --self-test
  .loop/plans/U7-upgrade-bifrost-2x.md:261 =      200, `data[0].embedding` of length 768, `routing_info` naming provider
  .loop/plans/U7-upgrade-bifrost-2x.md:334 = Four files: three edited, one created. No other file needs touching, and
  .loop/plans/U7-upgrade-bifrost-2x.md:400 = different measurement. Mark the operator-only rows as
  .loop/plans/U7-upgrade-bifrost-2x.md:486 = None. One loop iteration, three files.
  .loop/plans/U7-upgrade-bifrost-2x.md:660 =     request payload"},"extra_fields":{"routing_info":{}}}`. The empty
  .loop/plans/U7-upgrade-bifrost-2x.md:984 =   `usage` `{"prompt_tokens": 4, "total_tokens": 4}`, and `routing_info`
---

# Premise verdict: PARTIALLY SOUND

Every load-bearing claim in this cycle's new and repaired material holds
against the live gateway. Three defects remain, all mechanical, none of them
blocking: an under-specified JSON path, a stale file count, and one word of
pre-Q5 terminology. Implementation can start on this plan; the fixes can ride
along with the commit.

`loopctl verify-plan U7-upgrade-bifrost-2x`: `valid`, six provenance warnings
only (Q0 through Q5, each a recorded decision). No hard fail.

## Prior-cycle findings, re-attacked

- **U7-F8 — RESOLVED.** The document-shape trap is fixed and I re-measured it
  rather than taking the report. Live at 1.6.7, `POST /v1/rerank`:
  > object docs, no key  -> 401 `{"type":"virtual_key_required", ... "message":"virtual key is required. Provide a virtual key via the x-bf-vk header."}`
  > object docs, bogus key -> 401 `{"type":"virtual_key_not_found", ... "message":"virtual key not found. The provided virtual key does not exist or has been revoked."}`
  > string docs, no key  -> 400 `{"is_bifrost_error":false,"status_code":400,"error":{"message":"Invalid request payload"},"extra_fields":{"routing_info":{}}}`
  > string docs, bogus key -> 400, same body
  P18's 2x2 table is exact. `type` really is top-level on the two object
  rejections and really is absent on the string rejections, so §6.6's
  instruction to assert on `type` rather than on the bare 401 is the right
  measurement, and the "do not soften this assertion" note is warranted.

- **U7-F9 — RESOLVED.** `deployments/applications/services.tf:537`
  > `      bifrost_version  = "1.6.7"`
  §5 now carries the struck non-goal saying the apply runs in-session, and
  §6.3's replacement reason is true: `localstack env` emits `VAULT_TOKEN`
  (len 95), `NOMAD_TOKEN` (len 36) and `CONSUL_HTTP_TOKEN` (len 36). Nothing
  printed. One word of the old terminology survives; see RF3.

- **U7-F10 — RESOLVED, and the reasoning holds.** `.pre-commit-config.yaml:71`
  > `        entry: python3 scripts/tf_block_diff.py --self-test`
  `.pre-commit-config.yaml:87`
  > `        entry: python3 scripts/check_oauth2_proxy_guard.py --self-test`
  Those are the only two `--self-test` hooks, and both belong to scripts that
  run INSIDE pre-commit. `scripts/` also holds `embark_rerank.py`,
  `embark_bench.py` and `chunk_embed.py`, none of which carries one, and all
  three need live hardware for the same reason `bifrost_smoke.py` does. So the
  parity claim is with `embark_rerank.py`, not with the two checkers. No
  `--self-test` is required, `.pre-commit-config.yaml` stays out of §7, and
  §7's "Four files" is correct. I am not asking for a self-test.

- **U7-F1 through U7-F7, U7-F11, U7-F12 — no change in scope, still hold.**
  U7-F1: the front-matter OV1 claim re-resolves
  (`.loop/plans/OV1-openviking-service.md:3` carries
  `depends_on = ["U7-upgrade-bifrost-2x"]`, `:126` carries "No rerank bypass",
  `:624` carries the bypass as OV1's fallback option (a)). U7-F2 through
  U7-F5: citation fixes, untouched this cycle. U7-F6: the `sonic.Unmarshal`
  read-side demonstration, corroborated again by the string-form 400 above.
  U7-F7: the SSRF migration-guide quote, untouched. U7-F11 and U7-F12:
  `setup_token` and the hook coverage, untouched.

## Per-assumption findings, this cycle's material

- **P18 — HOLDS.** Demonstrated, not inferred. Probe output quoted under
  U7-F8. The key state changes nothing for the string form (both 400), which
  is the evidence that the parser short-circuits before governance. The two
  consequences P18 draws are the right ones.

- **P17 (rerank rows) — HOLDS.** Four rows, all four reproduced above. The
  claim that the string rows "carry no `type` and an empty `routing_info`" is
  exact: the 400 body has no `type` key and `extra_fields.routing_info` is
  `{}`.

- **§6.6 assertion 1's 2.0.0 expectation — UNCERTAIN, and harmlessly so.**
  The plan states that at 2.0.0 an unkeyed bare-string probe returns 401 where
  1.6.7 returns 400. The gateway is still `"v1.6.7"` (`GET /api/version`
  returned `"v1.6.7"`), so that cannot be measured before the apply. It rests
  on P4, settled in an earlier cycle. Nothing depends on the number: §6.6 and
  P18 both tell the script not to compare a bare-strings probe across
  versions. No fix.

- **§6.6 assertion 4 — HOLDS.** `deployments/applications/services.tf:621`
  > `resource "bifrost_virtual_key" "hermes" {`
  `deployments/applications/services.tf:636`
  > `resource "bifrost_virtual_key" "memex" {`
  Those are the only two `bifrost_virtual_key` resources in the repo
  (`secrets.tf:205,217` merely read their values). Live probe, admin basic
  auth from Vault, nothing printed:
  > `A4 virtual-keys -> 200 count=4 names=['Leo', 'hermes', 'jasper-laptop-cc', 'memex']`
  Exactly the four names the plan lists, two of them unmanaged. The claim that
  `terraform plan` structurally cannot see the unmanaged pair is correct, so
  the assertion is not redundant with §6.3.

  One boundary worth naming, not a fix: assertion 4 observes the FORWARD half
  of Q0 (the 2.0.0 migration did not drop rows). It cannot observe the half
  the front-matter calls out explicitly, whether 1.6.7 can read a
  2.0.0-migrated schema. §5 keeps that closed by operator decision and §10
  step 3's `pg_dump` is its fallback, so the gap is disclosed rather than
  papered over. §6.6's wording ("keys disappearing across it") stays inside
  what the probe can see, so it does not overclaim.

- **§6.6 assertion 3 — HOLDS.** Live, unauthenticated:
  > `A3 unauth /api/governance/virtual-keys -> 401`
  > `A3 unauth /api/providers -> 401`
  > `A3 unauth /api/config -> 401`
  > `A3 unauth /metrics -> 401`
  and 200 on `/api/governance/virtual-keys` with the admin credentials, which
  is also what assertion 4 reuses, so "one comparison, not one request" is
  accurate.

- **§6.6 assertion 2's dependency — HOLDS.**
  `deployments/infrastructure/services/prometheus.hcl:129`
  > `          - job_name: bifrost`
  followed at :130-133 by `metrics_path: /metrics` and a `basic_auth` block
  templating the Vault admin username and password. Prometheus really does
  depend on `/metrics` staying behind basic auth.

- **P19 — HOLDS on substance, under-specified on shape (RF1).** Live:
  > `RAW embeddings keys: ['data', 'extra_fields', 'model', 'object', 'usage']`
  > `{"data": [{"index": 0, "object": "embedding", "embedding": "<768 floats>"}], "model": "embedding", "object": "list", "usage": {"prompt_tokens": 4, "total_tokens": 4}, "extra_fields": {"request_type": "embedding", "routing_info": {"provider": "embark", "model": "embedding", "key": "embark-cluster"}, "provider": "embark", ...}}`
  Every fact P19 states is true: 200, 768 elements, `model` `embedding`,
  `usage` `{"prompt_tokens": 4, "total_tokens": 4}`, and a `routing_info`
  naming provider `embark` and key `embark-cluster`. But `routing_info` is NOT
  a top-level field; it is at `extra_fields.routing_info`, while `model` and
  `usage` beside it in the transcript ARE top-level. See RF1.

- **§6.6 assertion 5's routing_info-over-768 argument — HOLDS.** The argument
  is right, and the anchor supports the shared-config half.
  `deployments/applications/services/bifrost.hcl:158`
  > `      "network_config": {`
  `deployments/applications/services/bifrost.hcl:162`
  > `        "allow_private_network": true`
  That single `network_config` sits under provider `embark`, whose
  `custom_provider_config.allowed_requests` sets both `"embedding": true` and
  `"rerank": true` (:164-168). So one SSRF widening would fail both paths
  together, and the converse genuinely does not hold: a break confined to
  embeddings leaves `run_suite` green. The 768 alone cannot distinguish an
  embark answer from an edge answer, and `routing_info` naming
  `embark-cluster` can. Assertion 5 is not a duplicate of §6.2.

- **Q1's "three auth behaviors" against §6.6's five — ACCEPTABLE, not a
  defect.** §6.6's lead-in says "Assertions 1-3 come from §11 Q1's
  `widen-surface` resolution; assertions 4 and 5 were added in cycle 3", which
  is the provenance stated in the plan itself. The front-matter Q1 premise and
  §11 Q1 describe the fork AS RAISED, and a fork record that grows every time
  a later requirement is added stops being a record. Nothing downstream reads
  the count: §7, §8 and §10 all point at the script rather than at a number.
  Leave both texts alone.

## Most dangerous assumption

Still P16, unchanged: that 2.0.0's SSRF hardening does not reach a custom
provider's private-IP `base_url`. It is the one whose failure is both
catastrophic and invisible to every other gate. What changed for the better
this cycle is that it now has two independent observables rather than one:
§6.2's `run_suite` 3/3 on the rerank path and §6.6 assertion 5's
`routing_info` on the embeddings path. That is the right response to it.

Runner-up, and the reason RF1 is worth writing down: §8 makes the before-run
BLOCKING, so any assertion the script gets wrong stalls the upgrade rather
than merely reporting. That is what made the F8 shape trap dangerous last
cycle and it is what makes an unstated JSON path worth one line of the plan.

## Required fixes

All three are mechanical. **None blocks starting implementation.** They are
polish that can ride along with the commit, and I would rather the
implementer fix them in the plan than discover them at the keyboard.

- **RF1 (§6.6 assertion 5 and P19) — name the JSON path.** Write
  `extra_fields.routing_info`, not bare `routing_info`, in both places.
  `.loop/plans/U7-upgrade-bifrost-2x.md:261`
  >      200, `data[0].embedding` of length 768, `routing_info` naming provider
  `.loop/plans/U7-upgrade-bifrost-2x.md:984`
  >   `usage` `{"prompt_tokens": 4, "total_tokens": 4}`, and `routing_info`
  Both list `routing_info` alongside `model` and `usage`, which are top-level,
  so the transcript reads as though `routing_info` is too. It is not. A script
  written from §6.6 alone raises `KeyError` and fails its own blocking
  before-run. Two things keep this from being a blocker: P3 already quotes the
  correct nesting at `.loop/plans/U7-upgrade-bifrost-2x.md:660`
  >     request payload"},"extra_fields":{"routing_info":{}}}`. The empty
  and the eval rows for the blocker and for assertion 5 both say
  `extra_fields.routing_info` explicitly.

- **RF2 (§10) — "three files" should be "four".**
  `.loop/plans/U7-upgrade-bifrost-2x.md:486`
  > `None. One loop iteration, three files.`
  against `.loop/plans/U7-upgrade-bifrost-2x.md:334`
  > `Four files: three edited, one created. No other file needs touching, and`
  Left over from before Q1's `widen-surface` added `scripts/bifrost_smoke.py`.
  Steps 2 and 6 of the same section both run that file, so the intent is not
  in doubt; the count is just stale.

- **RF3 (§8) — one word of pre-Q5 terminology.**
  `.loop/plans/U7-upgrade-bifrost-2x.md:400`
  > `different measurement. Mark the operator-only rows as`
  Q5 resolved the apply to run in this session, and the two sentences just
  above already give the true reason ("It still needs the live cluster and a
  virtual key, so a review pass without those cannot reproduce it"). Say
  "live-cluster rows" or "rows a reviewer cannot reproduce". As written, the
  word still carries the meaning §5 and §6.3 were corrected away from.

## Observations, no fix required

- **Eval consistency.** The 17 scored rows cover §6.1, §6.2 (twice: the diff
  row and the `run_suite` 3/3 row), §6.3, §6.5, §6.6 (all five assertions plus
  the gate row) and §6.10. Two soft spots, neither worth a rewrite. §6.4
  (`/health` survives, `bifrost_ready` does not wedge the apply) has no row of
  its own; it is scored only implicitly by the two rows that require the apply
  to succeed, since a failed poll fails the apply. And "Rerank still accepts
  the object form" scores a gateway behavior no §6 requirement produces. That
  is NOT the F10 shape: it demands no artifact and cannot falsify §7's file
  count, and §6.6 assertion 1 needs objects to keep parsing anyway.
- **The eval's Definition of Done and its "two of the three smoke assertions"
  preamble still say three**, the same as-raised framing as Q1. Harmless there
  too, since the guardrail rows for assertions 4 and 5 are present and marked
  not optional. Mention only.
- **Every §7 file is reached by a §6 requirement**, and every §6 requirement
  names a producer. No `unmeasurable-requirement` gap remains open.

Scratch created at `.loop/scratch/U7-upgrade-bifrost-2x.plan-validator/`
(`probe_cycle3.py`, `probe_raw.py`); probe files removed at end of pass, ledger
retained at `findings.json` with U7-F13 through U7-F17 appended. No key
material was printed at any point: virtual key and admin credentials were read
from Vault into memory and only status codes, response shapes and token lengths
were emitted.
