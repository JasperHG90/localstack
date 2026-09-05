---
verdict: pass
tree: 59d4051fa727a67e818642a0bfbb05f4267a057f
---

# Adversarial review — U7-upgrade-bifrost-2x

Pass id: `adversarial`. Tree asserted with
`loopctl verify --expect-tree 59d4051fa727a67e818642a0bfbb05f4267a057f` (exit 0,
`ok [/home/vscode/workspace/.loop/worktrees/U7-upgrade-bifrost-2x]`) before the
placeholder was written.

## Scope binding: omitted deliberately

The briefing carried the slug, the pass id and the tree fingerprint, but no
64-hex scope digest and no `verdict_binding_inputs`. Writing a digest I computed
myself would bind a set nobody asked me to bind, so the three scope lines are
omitted and this verdict falls back to the whole-tree binding, which is stricter.

The reviewed path set, for the record, is exactly the four §7 files and nothing
else:

- `deployments/applications/services.tf`
- `deployments/applications/services/bifrost.hcl`
- `scripts/embark_rerank.py`
- `scripts/bifrost_smoke.py` (new)

## Deterministic floor

`loopctl verify-eval-substance U7-upgrade-bifrost-2x` → `valid`, exit 0, no
`warn:` lines. No hard-fail, no advisory, so the deep pass proceeded.

## Gate, re-run independently

`just pre_commit` → 25 hooks, all Passed, exit 0. Trust stamp at
`.loop/scratch/U7-upgrade-bifrost-2x.adversarial/trust-stamp.json`.

`pre-commit run --all-files` walks `git ls-files`, which does not include an
untracked file, so the `ruff` and `ruff-format` hooks did not see the new script
in my run. I checked it directly instead: `ruff check` clean, `ruff format
--check` clean, `mypy --config-file cli/pyproject.toml scripts` clean over 6
source files. The `mypy` hook does cover it even untracked, because it passes the
`scripts` DIRECTORY with `pass_filenames: false`
(`.pre-commit-config.yaml:58 = entry: uv run --project cli mypy --config-file cli/pyproject.toml cli/src cli/tests scripts`),
so the eval's claim about that anchor is accurate. At commit time the gate's
`git add --intent-to-add -A .` stages the file and the ruff hooks pick it up too.

## What I attacked, and what the evidence says

### 1. `scripts/bifrost_smoke.py` — does it earn the widened surface?

Yes. Run live against the 1.6.7 gateway: 5/5, exit 0.

**Assertion 1 really sends objects and really asserts `type`.**
`scripts/bifrost_smoke.py:106-109` builds `[{"text": ...}, {"text": ...}]`;
`:125` reads `json.loads(raw).get("type")` and `:126` compares it to the label.
I confirmed the field placement against the live gateway rather than trusting
P17's abbreviation: the 401 body's top-level keys are
`['error', 'extra_fields', 'is_bifrost_error', 'status_code', 'type']` with
`type` = `virtual_key_required` (no key) and `virtual_key_not_found` (bogus key).
The bare-string 400 body carries no `type` key at all.

The object pin is load-bearing, not decorative. Mutant `m1_barestrings.py`
(objects swapped for bare strings, nothing else) fails on the live 1.6.7 gateway:
`inference auth: expected 401 for virtual_key_required, got 400`. That is P18
reproduced, and it is exactly the blocking before-run failure §6.6 warns about.

**Assertion 5's nesting is right.** `scripts/bifrost_smoke.py:191 = routing =
payload.get("extra_fields", {}).get("routing_info", {})`. The live embeddings
response's top-level keys are exactly `data, extra_fields, model, object, usage`
— no top-level `routing_info`, matching P19. Mutant `m3_toplevel.py` reading
`payload.get("routing_info", {})` fails with `routing_info {} does not name
embark`. The shipped nesting is the reason the assertion passes.

**No assertion is vacuous.** I loaded the module and stubbed `request` to drive
every negative branch. All ten raised the intended `SmokeFailure`: `/metrics`
open, `/metrics` auth 500, `/metrics` missing `bifrost_` lines, an admin path
answering 200, VK list 503, embeddings 429, embeddings at 384 dimensions,
embeddings routed to `ollama`, rerank answering 200, and a 401 whose `type` is
`unauthorized`. Two live mutants confirm the same: `m2_ghostkey.py` (a fifth
expected key) fails with `['ghost-key'] absent`.

Assertion 3 is discriminating rather than trivially satisfied. I probed a
nonexistent admin path: `/api/definitely-not-a-real-path` returns **200** with
the SPA HTML fallback (3657 bytes), not 401. So a renamed or dropped admin path
in 2.0.0 turns assertion 3 red rather than green — it errs loudly and in the safe
direction. `/api/teams` returns the same 3657-byte HTML fallback, so that
unauthenticated 200 is not a data path and not a pre-existing security issue.

Mutant `m4_statusonly.py` (the `type` check neutered) still passes at 1.6.7. That
is expected, not a defect: at a healthy 1.6.7 both the status and the type hold,
so the `type` check's extra strength can only show under a transport-level 401.
It is a strictly stronger assertion, which is what §6.6 asked for.

**No credential can reach stdout, stderr or an exception message.** These are
literals no gate exercises and the first of their kind in the repo, so I checked
them at runtime instead of scoring them from the diff. I injected the sentinel
`SUPERSECRETVK` as the virtual key and rendered all ten stubbed failure messages
plus the three live ones: zero hits. The only response-derived value any message
prints is `routing_info` (`scripts/bifrost_smoke.py:194`), which live carries
`{'provider': 'embark', 'model': 'embedding', 'key': 'embark-cluster'}` — labels
only. `embark-cluster` is the key NAME at
`deployments/applications/services/bifrost.hcl:157`, whose `value` is
`env.EMBARK_API_KEY`, not the secret. The virtual key does not appear anywhere in
the embeddings response body. `vault_field` (`:58-69`) captures both streams and
prints neither. The credential-missing path prints the static line at `:210` and
exits 2, distinct from an assertion failure's 1 — verified by running under
`env -i`.

### 2. `scripts/embark_rerank.py` — the over-claim is gone

`scripts/embark_rerank.py:123 = "documents": documents,` and the docstring at
`:116-118`, both exactly where the eval row demands them. Live run against 1.6.7
reproduces the blocker as §8 step 1 specifies: `urllib.error.HTTPError: HTTP
Error 400: Bad Request`, exit 1. Dropping the `id` field breaks nothing — every
read-back is by `r["index"]` (`:142,148,151,158,162,164,178,179`), never by `id`.

The false "every OpenViking rerank client" claim is gone. The replacement scopes
to `OpenAI-compatible` clients, which excludes the `vikingdb` client that OV1's
P2 records as the one that DOES wrap each document as `{"text": doc}`
(`.loop/plans/OV1-openviking-service.md:830-832`). `OpenViking` appears nowhere
else in the diff — not in `bifrost.hcl`, not in `bifrost_smoke.py`.

Residual nuance, advisory only (LOW-7 below): OV1 counts three OpenAI-compatible
clients and its own P2 marks the `litellm` one's wire output "UNCERTAIN and was
not measured" (`.loop/plans/OV1-openviking-service.md:826-828`). So the plural is
measured for two and inferred for the third. The docstring is nonetheless
strictly narrower and more accurate than U7 §3's own "Every OpenViking rerank
client emits `documents` as a list of plain strings", so this diff tightened the
claim rather than loosening it.

### 3. The `bifrost.hcl` comment

Factually correct on the half I can measure. Against the live 1.6.7 gateway, a
bare-string rerank returns exactly `400` with
`{"error":{"message":"Invalid request payload"},"extra_fields":{"routing_info":{}}}`
— a flat message naming no field, with empty routing info, so the request never
reached embark. The 2.0.0 half and the "through 1.6.11" widening rest on P4's
per-tag source fetch, which is sound structural evidence. The block asserts
nothing unmeasured, and it keeps the still-true raw-logits sentence §7 asked for.
No em dash, no ` -- ` in the added prose (the ` -- ` at `:104` is a pre-existing
context line the diff does not touch), no tier-1 slop in any changed file.

### 4. Scope discipline

Exact. Tracked changes against `40b0f47` outside `.loop/` are the three declared
files; the only untracked non-`.loop` path is `scripts/bifrost_smoke.py`.
`.pre-commit-config.yaml` is untouched, as §7 and the eval's "must not grow one"
row both require. `.loop/ledger.json` moved, which is harness bookkeeping under a
prefix the fingerprint builder strips. My scratch is ignored via
`.loop/.gitignore:4 = scratch/`, so it cannot be staged.

### 5. Repo rules

`minimal-comments.md`: the two comments in the new script both record something
absent from the source — `:46-48` records that two of the four keys are outside
Terraform's sight, `:189-190` records the `extra_fields` nesting trap. Neither
narrates the next line. The long module docstring is API surface and §7 blessed
the shape. `plain-language.md`: clean. `pre-existing-issues.md`: nothing skipped;
the gate is green with no suppressions, and I found no `# type: ignore`, `skip`
or `xfail` in the diff.

## Findings

All LOW. None blocks the commit; none is a required fix.

- **LOW-1 — speculative envelope branch.** `scripts/bifrost_smoke.py:164 = keys =
  payload.get("virtual_keys") or payload.get("data") or []`. The live envelope is
  `count/limit/offset/total_count/virtual_keys` with no `data` key, matching P8.
  Neither §6.6 nor §7 asks for a second shape, so the `data` arm is flexibility
  that was not requested (CLAUDE.md §2). It cannot cause a silent pass — for it
  to fire, 2.0.0 would have to rename the list to `data`, in which case reading
  it is correct — so this is a tidy, not a risk.
- **LOW-2 — subset where the eval says equality.** `scripts/bifrost_smoke.py:166
  = missing = EXPECTED_VIRTUAL_KEYS - names` implements containment; the eval's
  scorer parenthetical says "set equality on names". I judge the code right and
  the parenthetical loose: the eval's own Expected column says "All four still
  present", the failure mode being guarded is keys DISAPPEARING across the
  migration, and equality would false-alarm if a human created a fifth key
  between the before-run and the after-run.
- **LOW-3 — timeout asymmetry.** `scripts/bifrost_smoke.py:44 = TIMEOUT = 30`
  against `scripts/embark_rerank.py`'s `timeout=120` for the same GPU backend.
  Assertion 5 is the only GPU-bound call. A transient timeout raises `URLError`
  outside the `SmokeFailure` channel, so the operator would read a traceback
  where §10 step 6 primes them to read "2.0.0 changed auth posture". Exit stays
  non-zero, and embark is not restarted by this upgrade so it stays warm. Low.
- **LOW-4 — parses outside the assertion channel.** `json.loads` at `:125`,
  `:163`, `:183` and `payload["data"][0]["embedding"]` at `:184` raise
  `JSONDecodeError`/`KeyError` rather than a `SmokeFailure`. The gate property
  survives (a traceback still exits non-zero) but the diagnosis is worse than the
  assertion the script wrote for itself.
- **LOW-5 — the key roster rots.** `scripts/bifrost_smoke.py:49` bakes in the
  2026-09-05 roster, and the eval correctly rules out ever making this a
  pre-commit hook, so nothing will notice when `Leo` or `jasper-laptop-cc` is
  retired. The plan asked for exactly this and `:46-48` explains why, so it is a
  sanctioned cost; naming it so the next Bifrost bump does not trip over it.
- **LOW-6 — the ticket slug and the dropped evidence marker.**
  `deployments/applications/services/bifrost.hcl:110-111` reads "That version
  boundary is why U7 exists." `minimal-comments.md` sanctions a ticket link, but
  a bare `U7` is the first loop slug under `deployments/`, `scripts/` or `docs/`
  (the only prior hit anywhere is
  `docs/notes/audit/plan-premise-sweep-2026-07.md:220`), and it is not resolvable
  without knowing the loop archive layout. Separately, the same edit dropped the
  old block's "Measured against this deployment." while widening the claim from
  1.6.7 to "through 1.6.11", so the comment no longer marks which half was
  measured and which inferred from source tags.
- **LOW-7 — one unmeasured client inside a true plural.** See §2 above.
  `scripts/embark_rerank.py:116-117`. Inherited from OV1's own summary phrasing,
  not introduced here.

## Unverified — not scored, and not counted against the work

- **`terraform plan`.** My review shell carries no `NOMAD_TOKEN` and no
  `CONSUL_HTTP_TOKEN` (both length 0), and running `plan` would write
  `.terraform/` into the worktree, breaching the read-only contract. §6.3
  pre-declares this a session limit rather than a defect, citing U5's
  `reviewer-could-not-run-plan`. The reported "exactly `nomad_job.bifrost` updated
  and `null_resource.bifrost_ready` replaced, nothing else" is the implementer's
  word and I did not confirm it. Two eval rows ride on it.
- **Every 2.0.0 runtime row.** `GET /api/version` still answers `"v1.6.7"` live,
  confirmed by me. The bare-string rerank 200, the smoke after-run, the
  post-bump `embark_rerank.py` 3/3 and the provider decode against a 2.0.0
  gateway are all unscored. §10 places the runbook after the review passes, so
  this is the ticket's design and not a defect in the diff. Stated plainly: this
  verdict authorizes the COMMIT of these four files. It does not attest that the
  eval's Definition of Done is met, and §10 steps 4-9 remain outstanding.

## Cross-cycle

No prior findings ledger existed at
`.loop/scratch/U7-upgrade-bifrost-2x.adversarial/findings.json`, so this is cycle
1 and there is nothing to re-attack. My findings are appended there for the next
cycle.

## Verdict

**pass.** The gate is green and re-run independently. Scope is exactly the four
declared files with no `.pre-commit-config.yaml` drift. The two things most
likely to be quietly wrong — assertion 1's document shape and assertion 5's
`extra_fields` nesting — are both right, and mutation testing against the live
gateway proves each is load-bearing rather than incidental. No assertion is
vacuous, and no credential reaches any output path. The seven findings are all
LOW advisories the operator can take or leave.
