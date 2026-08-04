---
verdict: pass
plan: affd6b2d43af36234a64e2601e269ad8700aac3e880ea012f0fcde3bebbbf098
---

# Plan review — R5-rollout-memex-oidc-auth (pass 6, plan-validator)

**Premise verdict: SOUND.** P1..P22 hold, carried forward from pass 4 and
unchanged since. The single defect pass 5 raised is fixed. The plan is ready
for implementation.

## Deterministic floor

- `loopctl verify-plan R5-rollout-memex-oidc-auth` -> `valid`
- `loopctl eval R5-rollout-memex-oidc-auth` -> `valid`
- `loopctl verify-eval-substance R5-rollout-memex-oidc-auth` -> `valid`

Plan sha256 recomputed before and after writing this verdict:
`affd6b2d43af36234a64e2601e269ad8700aac3e880ea012f0fcde3bebbbf098`. Matches the
briefed fingerprint.

## The plan is untouched. VERIFIED, not taken on trust.

`sha256sum .loop/plans/R5-rollout-memex-oidc-auth.md` returns
`affd6b2d43af36234a64e2601e269ad8700aac3e880ea012f0fcde3bebbbf098`, byte for
byte the revision pass 5 reviewed. Plan `:418-422` still reads "ten
deterministic rows at a 100% bar, one per check above plus two guardrails on
the §5 non-goals". Pass 5's reconstruction proof therefore still stands: this
plan differs from the pass-4 revision by exactly the one appended §8 paragraph
and nothing else.

So the whole question this pass is whether that paragraph is now true of the
eval it points at. It is.

## Fix 1 — eval row H2 restored to §8's polarity. HOLDS.

`.loop/evals/R5-rollout-memex-oidc-auth.md:20` now reads:

> The credential path is healthy, with no silent downgrade | After R5e lands:
> `nomad alloc logs <hermes-alloc> hermes | grep -iE 'workload token
> file|Falling back to X-API-Key'` | No output. Both `Could not read workload
> token file ...` (wrong `token_file` path) and `Falling back to X-API-Key
> client (shared memex config unusable): ...` (config present but invalid) must
> be ABSENT. ... | Deterministic (assert absence of both log lines) | 100%

Every objection pass 5 raised is answered, and answered at the root rather than
patched around:

| Pass 5 objection | Status in the new row |
|---|---|
| ANDs two log lines from disjoint faults | GONE. It now asserts absence of a disjunction, which is safe: neither line may appear, whichever fault would have produced it. |
| Fails against a correct implementation | GONE. See below. |
| Inverts §8 H2's polarity | GONE. Matches plan `:387`, "Both must be **absent**". |
| Mutates a running hermes with an induced fault | GONE. The input is a passive `nomad alloc logs` grep, read-only like every other §8 check (plan `:610-612`). |
| Needs §10 scheduling for the induced fault | MOOT. "After R5e lands" matches §10 subticket 5 (plan `:510-512`, "Run H1, H2, H3, then S2 again"). |

**It passes against a correct implementation.** On a healthy post-R5e system
neither line can fire, and I checked both paths at upstream v1.1.0 rather than
inferring:

- Nomad writes `secrets/nomad_memex.jwt` per the §7 identity stanza (`file =
  true`, `filepath` pinned; P5, P6), so `_read_workload_token` in
  `memex_common/auth_client.py` never reaches its `except OSError` and never
  logs `Could not read workload token file %s: %s`.
- `MemexConfig()` builds from the three `MEMEX_OIDC__*` vars (P11 measured
  this; `issuer` is https so `require_https` passes and
  `validate_grant_requirements` at `memex_common/config.py:1678-1692` is
  satisfied by a non-empty `token_file`), so
  `memex_hermes_plugin/memex/provider.py` never enters the `except Exception`
  at `:278` and never logs `Falling back to X-API-Key client (shared memex
  config unusable): %s`.

No output, row green. On a broken system either line appears and the row goes
red, which is the point.

The row's two parentheticals are also now correct, and they internalize
precisely the distinction the old row collapsed: "(wrong `token_file` path)"
for the `auth_client` warning, "(config present but invalid)" for the provider
fallback. Its closing claim holds too: either line means hermes silently fell
back to `MEMEX_API_KEY` while requests keep returning `200`, because the first
path returns `{'X-API-Key': ...}` from `resolve_client_headers` and the second
returns a client carrying `headers['X-API-Key']`.

## Fix 2 — the plan needed no edit. CONFIRMED.

With H2 restored, plan `:418-422`'s "one per check above" is now accurate for
all ten rows, which pass 5 found it was not. Re-verified the full mapping
against the current eval: `:15` -> S1, `:16` -> W1, `:17` -> D1, `:18` -> D2,
`:19` -> H1, `:20` -> H2, `:21` -> H3, `:22` -> S2, `:23` -> G1, `:24` -> G2.
Ten rows, every `Scorer` cell opens with `Deterministic`, every `Threshold`
cell is `100%`, and each of the eight §8 rows now asserts what §8 asserts, in
§8's polarity.

## The other rows, re-checked this pass

Comparing the current file against my in-context copy of the pre-fix revision,
line 20 is the only line that changed; lines 1-19 and 21-27 are identical,
including the preamble's check list at `:7-11`. I re-read all ten rows anyway.

- **D1 (`:17`) HOLDS.** A `vault.io`-audience token from the Nomad issuer
  resolves a provider, verifies, then fails the `aud` claim option and raises
  `JoseError` into `logger.info('OIDC token rejected for issuer %s: %s', ...)`
  at `memex_core/server/oidc.py:209`.
- **D2 (`:18`) HOLDS.** Its absence assertion is right: a token with the right
  `iss` and `aud` but a non-hermes `nomad_job_id` verifies cleanly, then
  `_claims_to_context` (`oidc.py:83-115`) falls through its `for/else` to `if
  provider.default_policy is None: return None` with no logger call on that
  path. A silent 403 is the pass.
- **S1 (`:15`) HOLDS**, including the deliberate `3 key(s)`, which matches
  P10's measured line and the `writer_key_vault_meetings` drift §4 puts out of
  scope.
- **W1 (`:16`) HOLDS.** Its `http://192.168.2.46:8000` is the right address
  from inside the hermes alloc: `hermes.hcl:203`/`:449` render
  `http://${memex_host}:8000` and `memex_host = "192.168.2.46"` at
  `deployments/applications/services.tf:127` and `:169`.
- **H1 (`:19`), H3 (`:21`), S2 (`:22`), G1 (`:23`), G2 (`:24`) HOLD** and match
  §8 and §5, including H3's "env visibility alone does not pass this row" and
  G2's anchors at `hermes.hcl:201` and `:405`.

## Most dangerous assumption

Unchanged: **P12**, that once the bearer resolves the client sends only
`Authorization` and never falls back on a server-side rejection. It sets the
R5a-before-R5e ordering, keeps `MEMEX_API_KEY` under Q4, and makes §9 failure
mode 2 an outage rather than a degradation. Verified at upstream
`auth_client.py` `resolve_client_headers`: `bearer = await
_resolve_bearer(...)` / `if bearer is not None: return {'Authorization':
bearer}` / then the `X-API-Key` branch. It holds.

## Non-blocking nits

1. **The new H2 grep carries a markdown-escaping wrinkle.** Inside the table
   cell the command reads `grep -iE 'workload token file\|Falling back to
   X-API-Key'`. Both `\|` in that cell are table escapes (the first is the
   shell pipe, exactly as in row `:15`), so the intended command uses ERE
   alternation and is correct. But if a scorer copy-pastes the cell verbatim
   without unescaping, `grep -E` reads `\|` as a *literal* pipe, and the
   pattern matches nothing even when both failure lines are present:

   ```
   $ grep -icE 'workload token file\|Falling back to X-API-Key' fakelog   # 0
   $ grep -icE 'workload token file|Falling back to X-API-Key'  fakelog   # 2
   ```

   That turns an absence check into a tautology. It does not gate: the
   `Expected` and `Scorer` columns state the assertion unambiguously twice
   ("Both ... must be ABSENT", "assert absence of both log lines"), those
   columns govern what is scored, and §8 H2 (plan `:381-387`) gives the two
   separate greps verbatim, which is what lands in
   `docs/memex-oidc-verification.md`. Cheapest fix: keep §8's two separate
   `grep -i` invocations in the cell, or drop the backslash before the
   alternation.
2. **D2's prose** (`:18`) still says "the server log emits NOTHING for this
   request", which is loose since uvicorn's access log records the 403. The
   scorer resolves it correctly as absence of the one OIDC line.
3. Pass 4's three cosmetic plan nits are unchanged and still non-blocking: the
   vendored `config.py` line-number sub-clause (plan `:628-629`), §7 `:244`
   citing P22 for the `noop` shape when P22's quoted probe used `restart` (I
   validated `noop` live against the cluster in pass 4), and
   `nomad_oidc_issuer` landing in the `locals` block under an unrelated
   firewall heading at `services.tf:22`.

## Contract hygiene

Clean, and unchanged from pass 4. Real code surface with resolved anchors (§7).
Gates discovered rather than assumed (§8 matches `.pre-commit-config.yaml`,
`scripts/tf_validate.sh`, `.loop/config.json`). Explicit non-goals (§5,
including the R6 split and the deliberate refusal to fix the
`writer_key_vault_meetings` drift). No unit-test surface, correctly justified,
with every live check homed in `docs/memex-oidc-verification.md`. Forks
surfaced in §11 with a recommendation each, Q5 marked SETTLED against its own
earlier recommendation.

## Verdict

`pass`. The premise is sound, the plan is byte-identical to the revision I
reviewed, and the one row that would have gone red on a working system now
asserts the absence §8 actually specifies. What remains is three cosmetic notes
and one grep-escaping nit that no implementer would be misled by.
