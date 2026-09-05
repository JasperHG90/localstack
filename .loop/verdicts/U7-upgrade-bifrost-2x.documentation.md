---
verdict: pass
tree: 59d4051fa727a67e818642a0bfbb05f4267a057f
---

<!--
SCOPE BINDING OMITTED, DELIBERATELY. The briefing gave a tree fingerprint but
no 64-hex scope digest, and named no verdict_binding_inputs. The floor is not
mine to choose and I must never write a digest I computed for a set I chose,
so the three lines (bound_paths / scope / citations) are omitted and this
verdict falls back to the whole-tree binding, which is stricter. This repo has
the same precedent at .loop/verdicts/L5-landing-registry-tab.documentation.md.
Recorded in .loop/scratch/U7-upgrade-bifrost-2x.documentation/trust-stamp.json
as "scope_digest_given": null.
-->

# Documentation pass — cycle 1 — PASS

No reader following this repo's docs would now be wrong. The change touches one
documented surface, the rerank wire format, and the same diff updates both
places in the repo that describe it. Nothing else drifted.

First cycle for this pass: no prior findings ledger existed at
`.loop/scratch/U7-upgrade-bifrost-2x.documentation/findings.json`, so there was
nothing to re-attack. Seven findings are appended there for the next cycle.

## What was checked, and against what

Repo-wide sweeps at this fingerprint, all bounded:

- `git grep -i rerank` over tracked files, excluding `.loop/` and `assets/`
- `git grep -i documents` over the working tree
- `git grep '1\.6\.7\|1\.6\.1[01]\|1\.6\.x'` over tracked files
- every file mentioning `bifrost`, minus `.git`, `.terraform`, `__pycache__`,
  `.mypy_cache` and `.pytest_cache`
- each `scripts/` sibling name, searched outside `scripts/`, to find the bar
- `docs/` (28 files), `README.md`, `ROADMAP.md`, `AGENTS.md`, `.claude/rules/`
  (10 files), `.claude/skills/` (11), the repo's own `SKILL.md` files, and
  `assets/localstack-architecture.drawio`

## Findings

### 1. The wire-format change — CLEAN, no third site exists

Two prose sites in this repo stated the object-only constraint as present-tense
fact. Both are corrected in this diff.

    deployments/applications/services/bifrost.hcl:107 = #     Bifrost's rerank schema takes `documents` as either bare strings
    deployments/applications/services/bifrost.hcl:109 = #     Through 1.6.11 it took objects only, and rejected
    scripts/embark_rerank.py:116 = Documents go as bare strings, the shape OpenViking's OpenAI-compatible

Both now carry the version boundary rather than a flat assertion, which is what
keeps them from going stale again on the next bump. The docstring and the code
agree:

    scripts/embark_rerank.py:123 = "documents": documents,

I searched for a third site and there is none. `git grep -i rerank` over
tracked files, excluding `.loop/` and `assets/`, returns only: the two files
above, the new `scripts/bifrost_smoke.py`, a section heading in `services.tf`,
the `"rerank": true` capability flag and the `embark/reranker` model name in
`bifrost.hcl`, the reranker artifact name in `embark/README.md` and
`embark/models.json`, two reranker env vars in `memex.hcl`, and one comment in
`infrastructure/services.tf` about ModelKit disk size. None of those makes a
claim about the request payload shape.

Two near-misses I checked and cleared:

- `deployments/applications/services/embark/README.md` (121 lines) contains no
  occurrence of `documents`, `/v1/rerank`, `payload`, `Bifrost` or `gateway`.
  It documents the served artifact names, not the gateway's wire format.
- `assets/registry-mockup.html` model cards say `POST /v1/rerank with a model,
  a query, and documents` and point at `docs/api.md`. That describes embark's
  own endpoint reached by `embark serve`, not the gateway, and it names no
  document shape. Nothing there went stale.

### 2. `scripts/bifrost_smoke.py` — CLEAN, it meets the repo's actual bar

The bar in this repo is the module docstring, and nothing else. `scripts/` has
no README. Searched outside `scripts/`, `embark_rerank`, `embark_bench` and
`chunk_embed` appear only in `.loop/` planning artifacts. They are named in no
doc, no README, no justfile recipe and no rule. The two scripts that do appear
elsewhere appear because they are pre-commit hooks (`tf_block_diff.py` in
`.pre-commit-config.yaml` and `.claude/rules/terraform-file-layout.md`;
`check_oauth2_proxy_guard.py` in `.pre-commit-config.yaml` and
`docs/registry-ui.md:29`). `bifrost_smoke.py` is an operator probe, not a hook,
so the hook precedent does not reach it.

Held to the sibling standard it passes cleanly. Compare the openers:

    scripts/bifrost_smoke.py:2 = """Assert Bifrost's auth posture and its reach to embark, before and after a bump.
    scripts/embark_bench.py:2 = """Time embark's embedding endpoint across input lengths.
    scripts/chunk_embed.py:2 = """Chunk a document into roughly equal pieces and embed each through Bifrost.

It carries the same four elements the siblings carry: purpose, the trap a
reader would otherwise hit (why assertion 1 pins object-form documents), the
Vault paths its credentials come from, and a Usage block.

    scripts/bifrost_smoke.py:28 =     python3 scripts/bifrost_smoke.py --base-url http://192.168.2.50:8080

One deliberate difference, and it is documented accurately rather than copied.
The siblings read `BIFROST_VK` from the environment first and fall back to
Vault; `bifrost_smoke.py` reads Vault only. Its docstring says exactly that
("Credentials come from Vault and are never printed"), which matches
`main()`. The prose describes the code it ships with, so there is no drift.
Whether the behavior *should* differ is an implementation question for the
adversarial pass, not a documentation one.

I am not asking for a `scripts/README.md`. Creating one would hold this file to
a higher standard than its four siblings and would invent a convention the repo
does not have.

### 3. The version pin — CLEAN, no doc names a Bifrost version

    deployments/applications/services.tf:537 =       bifrost_version  = "2.0.0"

After the change, `git grep '1\.6\.7'` over the tree returns zero hits. The only
version strings left in prose are the deliberate boundary markers at
`bifrost.hcl:109` and `embark_rerank.py:117`, both of which name 1.6.11 and
2.0.0 on purpose.

The ticket's §7 claim that the tag appears exactly twice holds: the value at
`services.tf:537` and the interpolation, correctly untouched, at

    deployments/applications/services/bifrost.hcl:40 =         image        = "docker.io/maximhq/bifrost:v${bifrost_version}"

Three `docs/` files mention Bifrost and none names a version:
`dash-landing-page.md:5` lists it among dashboard tiles;
`notes/audit/plan-premise-sweep-2026-07.md` is a dated audit of July commits,
historical by construction; and

    docs/haproxy_reverse_proxy.md:27 = `phoenix` sits behind HTTP basic auth. `bifrost` authenticates

which continues "with its own native `governance.auth_config` (admin creds from
Vault), so HAProxy no longer gates it." That is still true at 2.0.0, and
assertions 1 to 3 of the new smoke script are what would catch it if the
upgrade had changed it. `assets/localstack-architecture.drawio` names Bifrost
five times and carries no version. `ROADMAP.md` never mentions Bifrost, and
`git log` shows it is revised by explicit `docs: roadmap ...` commits rather
than per ticket: neither `c5cba06` (embark) nor `7e93194` (L5) touched it.

### 4. ADR-001 — does not exist. Informational, not a required fix

    deployments/applications/services.tf:530 = ### Bifrost — LLM gateway: load-balances two Ollama Cloud keys, falls back to Gemini (ADR-001)

There is no `adr/` directory and no ADR-001 file anywhere in the tree. The only
other occurrence of the string is the second reference at `services.tf:126` and
a verdict quoting it. `git blame` puts line 530 at `736e29c` (2026-07-02), so
the reference has been dangling for two months and this ticket did not create
it.

A major version bump is exactly what an ADR would record, if one existed. It
does not, so demanding one here would be inventing documentation the repo never
had, against a ticket whose §7 declares four files and no others. Logged as
`DOC-U7-04` in the findings ledger so a later ticket can pick it up on purpose.

### 5. The prose rules — checked, and the scanner does not fire

`.claude/rules/slop-scan-for-docs.md` is scoped to markdown files. The diff
adds and edits none: the four paths are `.tf`, `.hcl` and `.py`. Confirmed by
`git diff --name-status`, not assumed. It does not fire.

`.claude/rules/plain-language.md` does reach comments and docstrings, so I ran
the punctuation half of the scan over the added prose anyway. Zero em dashes,
zero smart quotes, zero ` -- ` prose separators across the `bifrost.hcl` comment
block, the `rerank()` docstring and all 244 lines of `bifrost_smoke.py`. The new
sentences are active and short. "That version boundary is why U7 exists" records
a reason, which `.claude/rules/minimal-comments.md` explicitly permits ("a link
to the ticket or upstream bug that explains the shape"), and the bare slug
follows existing practice: `infrastructure/identity.tf:397` writes "memex (R6)"
and `infrastructure/variables.tf:71` writes "F2's throwaway smoke-test OIDC
client".

Every identifier in the new prose resolves. `secret/default/bifrost/credentials`
is real (`services.tf:544`, `:571`, `infrastructure/secrets.tf:150`);
`secret/default/hermes/bifrost` is used by all three sibling scripts;
`enforce_auth_on_inference`, `allow_private_network`, `embark-cluster`,
`/api/governance/virtual-keys`, `/api/providers` and `/api/config` all appear in
`bifrost.hcl`. The one claim I cannot verify offline is upstream
`RerankDocument.UnmarshalJSON`, which the ticket records as measured at P4 with
a source link.

## Two pre-existing drifts, logged not demanded

Neither was caused by this change, and both are outside the ticket's declared
surface. Recorded as `DOC-U7-05` so they are not lost.

    deployments/applications/services.tf:530 = ### Bifrost — LLM gateway: load-balances two Ollama Cloud keys, falls back to Gemini (ADR-001)

says "two Ollama Cloud keys" while `bifrost.hcl:139-142` configures four
(personal, xebia, proton, rituals). Blame: `736e29c`, 2026-07-02.

    deployments/applications/services.tf:556 =       # "embark/embedding". Not user-facing: embark's firewall admits cluster

is the middle of a comment saying embark is "reached as `embark/embedding`",
which omits `embark/reranker`. Blame: `db51630b`, 2026-09-04, from commit
`c5cba06` which added the reranker. Ironically the comment block this ticket
*did* fix, at `bifrost.hcl:103-105`, names both served models correctly.

## Verdict

**PASS.** The change touches exactly one documented surface, the rerank
`documents` wire format, and both places describing it are corrected in the
same diff and now carry the version boundary instead of a bare assertion. No
doc names a Bifrost version. The new probe is documented to the same standard as
its four siblings, which is a module docstring and nothing more. No markdown
changed, so the slop scanner does not apply.
