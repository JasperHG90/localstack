eval: R5-rollout-memex-oidc-auth

hermes reaches memex with a Nomad Workload Identity JWT instead of a static
admin key, every other identity is refused, and nothing that worked before
stops working.

Rows trace to the live checks in the ticket's §8 (S1, S2, W1, D1, D2, H1,
H2, H3) plus two guardrails on its §5 non-goals. Every row is machine-
checkable and every bar is 100%: the failure modes here are silent, and the
security-shaped rows (D1, D2, G1, G2) protect an invariant, so a row that
passes 90% of the time is a row with a hole.

| Behavior | Input | Expected | Scorer | Threshold |
|----------|-------|----------|--------|-----------|
| memex trusts the Nomad issuer, and only it | `nomad alloc logs <memex-alloc> memex \| grep -i 'authentication enabled'`, after the memex redeploy | An `info` line reading `OIDC bearer-token authentication enabled (1 provider(s)).` — the count is `1`, not `2`; the existing `API key authentication enabled (3 key(s) configured, 3 exempt path(s)).` line is still present | Deterministic (string match on both lines) | 100% |
| A hermes workload token is accepted | From the hermes alloc, `curl -H "Authorization: Bearer $(cat /secrets/nomad_memex.jwt)" http://192.168.2.46:8000/api/v1/vaults`, run after the `identity` stanza lands and BEFORE any `MEMEX_OIDC__*` var is set | `200`. The token's decoded payload carries `iss` = `https://nomad.lab.orangecluster.nl`, `aud` containing `memex`, and `nomad_job_id` = `hermes` | Deterministic (HTTP status + JSON claim equality on the decoded payload) | 100% |
| A token minted for another audience is refused | A throwaway Nomad job carrying `identity { name = "vault_default", aud = ["vault.io"], file = true, filepath = "secrets/nomad_vault_default.jwt" }`; present that token to `/api/v1/vaults` | `403`, AND the memex server log emits `OIDC token rejected for issuer ...` | Deterministic (HTTP status + server-log string match) | 100% |
| A token from a job that is not hermes is refused | From the same throwaway job, its `aud = ["memex"]` token presented to `/api/v1/vaults` | `403` from the authorization path, NOT the signature path: the server log emits NOTHING for this request. A silent 403 is the pass; an `OIDC token rejected for issuer` line means the wrong failure fired | Deterministic (HTTP status + assert absence of the log line) | 100% |
| The hermes client sends the bearer, not the key | In the hermes alloc: `/opt/hermes/.venv/bin/python -c "import asyncio; from memex_common.config import MemexConfig; from memex_common.auth_client import resolve_client_headers; print(asyncio.run(resolve_client_headers(MemexConfig())))"` | `{'Authorization': 'Bearer eyJ...'}`. An `X-API-Key` key in the returned dict is a fail | Deterministic (dict key equality) | 100% |
| The credential path is healthy, with no silent downgrade | After R5e lands, two separate greps over `nomad alloc logs <hermes-alloc> hermes`: one for `workload token file`, one for `Falling back to X-API-Key` (kept separate on purpose — a single alternation written in a markdown cell needs an escaped pipe, which `grep -E` then reads as a literal and matches nothing, making the check vacuous) | No output from either grep. Both `Could not read workload token file ...` (wrong `token_file` path) and `Falling back to X-API-Key client (shared memex config unusable): ...` (config present but invalid) must be ABSENT. Either line means hermes is silently back on the API key while requests still return `200` | Deterministic (assert absence of both log lines) | 100% |
| Both sandboxes get the credential, not just the env | Through the hermes agent, run the `resolve_client_headers` one-liner once via the terminal tool (`env_passthrough` at `hermes.hcl:254-262`) and once via code_execution (`:265-273`) | `{'Authorization': 'Bearer ...'}` in BOTH. An `X-API-Key` in either means that sandbox silently kept the key. Env visibility alone does not pass this row | Deterministic (dict key equality, both sandboxes) | 100% |
| Existing API-key access is unbroken | The P8 triple against `http://192.168.2.46:8000/api/v1/vaults`: no credential, a garbage bearer, the admin API key | `401` / `403` / `200`, unchanged from the pre-change baseline | Deterministic (HTTP status triple) | 100% |
| G1 (guardrail): the human login path does not reappear | `terraform plan` on both roots, plus a grep of the diff | No `vault_identity_oidc_client`, no `vault_identity_oidc_assignment`, no `vault_identity_oidc_key_allowed_client_id`, no new file under `deployments/infrastructure/`, no edit to `deployments/infrastructure/oidc.tf` or `docs/vault-human-auth.md`, and `MEMEX_SERVER__AUTH__OIDC` holds exactly ONE element. That path is R6's | Deterministic (grep over the diff and the rendered job) | 100% |
| G2 (guardrail): static API keys survive | The rendered memex and hermes job specs after apply | `MEMEX_SERVER__AUTH__KEYS` still present in `memex.hcl`, and `MEMEX_API_KEY` still present in `hermes.hcl` at both `:201` and `:405`. Removing either is a follow-up (Q4), never this ticket | Deterministic (grep over the rendered specs) | 100% |

signed-off-by: JasperHG90 2026-08-03

---

## SUPERSESSION NOTE (added by R6-rollout-memex-human-oidc, 2026-08-04)

The rows above are UNCHANGED and remain the signed record of what was true
when R5 shipped, against memex **v1.1.0** with one OIDC provider. Do not edit
them. Three are now false about the live system, superseded by R6:

- **Row 1 (S1)** asserts `(1 provider(s))`. R6 adds the Vault human provider,
  so the live count is `2`. Both must be present.
- **Row 4 (D2)** asserts the server log emits **NOTHING** on the
  verified-but-unauthorized path. That polarity INVERTED at memex v1.2.0,
  which logs `OIDC token verified for issuer ... but matched no grant_rule
  and the provider has no default_policy ...`. Against a v1.2.0 server,
  silence is now a FAILURE.
- **Row 9 (G1)** asserts exactly ONE element in `MEMEX_SERVER__AUTH__OIDC`
  and no `vault_identity_oidc_client`. R6 adds both, deliberately.

The corrected assertions live in `.loop/evals/R6-rollout-memex-human-oidc.md`
and in `docs/memex-oidc-verification.md`. If a check here fails against the
current cluster, read that runbook before concluding anything is broken — and
do NOT "fix" the runbook backwards to match these rows.
