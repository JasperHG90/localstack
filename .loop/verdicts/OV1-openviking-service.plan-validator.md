---
verdict: pass-with-required-fixes
plan: d5b7d92a1aefa1d483d869442e2ec4bb86626ed73a9f9555644db10d7dd790e7
bound_paths: front-matter, 5, 6, 7, 8, 9, 10, premises
scope: fbda2b19ccde1a0944a1d6a093e6406e9037a3848cb3da4ef2bb1043ba11d689
fix_sections: front-matter, premises
citations:
deployments/applications/services.tf:131 =         "allow from 192.168.0.0/16 to any port 8080 proto tcp",
deployments/applications/services.tf:537 =       bifrost_version  = "1.6.7"
deployments/applications/services.tf:30 =   vault_oidc_issuer = "https://vault.lab.orangecluster.nl/v1/identity/oidc/provider/lab"
deployments/applications/services/bifrost.hcl:40 =         image        = "docker.io/maximhq/bifrost:v${bifrost_version}"
deployments/infrastructure/services/oauth2-proxy-registry-ui.hcl:62 =         OAUTH2_PROXY_OIDC_ISSUER_URL="{{ with secret "${oidc_secret}" }}{{ .Data.data.issuer }}{{ end }}"
deployments/infrastructure/services/oauth2-proxy-registry-ui.hcl:98 =         network_mode = "host"
deployments/infrastructure/secrets.tf:268 =     issuer        = "https://${var.vault_issuer_host}/v1/identity/oidc/provider/${vault_identity_oidc_provider.lab.name}"
openviking@v0.4.17.1 openviking/models/rerank/cohere_rerank.py:22 = class CohereRerankClient(RerankBase):
openviking@v0.4.17.1 openviking/models/rerank/cohere_rerank.py:62 =             resp = self._client.post(
openviking@v0.4.17.1 openviking/models/rerank/cohere_rerank.py:67 =                     "documents": documents,
openviking@v0.4.17.1 openviking/models/rerank/openai_rerank.py:75 =     def _build_request_body(self, query: str, documents: List[str]) -> dict:
openviking@v0.4.17.1 openviking/models/rerank/litellm_rerank.py:67 =             response = litellm.rerank(
maximhq/bifrost@transports/v2.0.0 transports/go.mod:18 = 	github.com/maximhq/bifrost/core v1.8.3
maximhq/bifrost@transports/v2.0.0 transports/Dockerfile:30 =   COPY transports/go.mod transports/go.sum ./
maximhq/bifrost@core/v1.8.3 core/schemas/rerank.go:28 = func (d *RerankDocument) UnmarshalJSON(data []byte) error {
---

rebound-by: claude-opus-5 (delegated by JasperHG90, operator offline) 2026-09-05T15:41:25Z (reason: Cycle-3 required fixes 1 and 2: removed the false 'shares that builder' mechanism claim from P2 and the matching clause from front-matter premise.Q2. Both one-clause wording corrections the verdict specified, confined to fix_sections (front-matter, premises). Reviewer rated severity low and confirmed no requirement, subticket or dependency moves; the operative conclusion was independently verified. verify-plan valid.)

# Plan review — OV1-openviking-service, cycle 3 of 3

## Deterministic floor

`loopctl verify-plan OV1-openviking-service` returns `valid` with six
provenance `warn`s only (one per premise carrying a `measured_against`
entry). No hard-fail, so the semantic pass ran.

## Premise verdict

**PARTIALLY SOUND.** One sub-clause in P2, mirrored in front-matter `Q2`,
is false as written. Every other load-bearing premise holds, including
P20, the one the whole `U7-upgrade-bifrost-2x` dependency rests on, which
I re-demonstrated end to end this cycle.

## What changed since cycle 2, checked one by one

### Required fix 1 — the Q2-flip ripple in §6 R1: GENUINELY FIXED

`deployments/applications/services.tf:126-133`
> ```
> 126    # Bifrost LLM gateway on radxa-dragon-q6a — single OpenAI-compatible endpoint for all agent consumers (ADR-001)
> 127    bifrost = {
> 128      host     = "192.168.2.50"
> 129      ssh_user = "radxa"
> 130      rules = [
> 131        "allow from 192.168.0.0/16 to any port 8080 proto tcp",
> 132      ]
> 133    }
> ```

R1 now reads "It needs NO application-side firewall change: under R5
OpenViking dials only Bifrost, whose rule already admits the whole
`192.168.0.0/16` to port 8080", and explains that adding an embark entry
would open a port on a node with no reason to reach it and, being
ONE-WAY, would outlive `terraform destroy`. That is exactly right and the
anchor supports it: line 131 is the whole-`/16` grant. R5 still says the
embark rule and its intent comment at `services.tf:102-114` stay
untouched, so the two no longer contradict each other.

Ripple check, plan-wide: `grep -n '192.168.2.47\|embark rule'` over the
plan returns only R1's own corrected text. §5 records "No rerank bypass.
Rerank stays on the gateway (R5)"; §7 says "No `embark` entry: R5 keeps
rerank on the gateway"; §6 R6 says OpenViking needs no copy of embark's
API key. No section still carries the pre-flip assumption. **F9 RESOLVED.**

### Required fix 2 — P2's litellm clause: FIXED for litellm, BROKEN for cohere

The litellm half is now correct and its `UNCERTAIN` is honest.
`openviking/models/rerank/litellm_rerank.py:67-70` @ v0.4.17.1
> ```
>  67            response = litellm.rerank(
>  68                model=self.model_name,
>  69                query=query,
>  70                documents=documents,
> ```
with `def rerank_batch(self, query: str, documents: List[str])` at `:48`.
The plan says litellm "hands the same `List[str]` to `litellm.rerank(...)`
and never reaches OpenViking's own body builder, so what its transformer
emits on the wire is UNCERTAIN and was not measured; it does not matter
here, because R5 configures `provider: 'openai'`." That is the label used
correctly: it bounds a claim the plan then declines to rely on, rather
than preserving an unverified one. **F15 RESOLVED.**

But the fix moved the false mechanism rather than removing it. P2 now
says "the `cohere` client shares that builder and does the same", and
front-matter `Q2` says the two clients send strings "through the same
body builder". Neither is true.

`openviking/models/rerank/cohere_rerank.py:22` @ v0.4.17.1
> class CohereRerankClient(RerankBase):

`openviking/models/rerank/cohere_rerank.py:62-70` @ v0.4.17.1
> ```
>  62            resp = self._client.post(
>  63                "/v2/rerank",
>  64                json={
>  65                    "model": self.model,
>  66                    "query": query,
>  67                    "documents": documents,
>  68                    "top_n": len(documents),
>  69                    "return_documents": False,
>  70                },
> ```

`CohereRerankClient` extends `RerankBase`, not `OpenAIRerankClient`; the
file imports only `RerankBase` and `get_logger`; and it posts an inline
dict to its own `/v2/rerank` path. It never calls
`OpenAIRerankClient._build_request_body`
(`openai_rerank.py:75`)
> def _build_request_body(self, query: str, documents: List[str]) -> dict:

The plan's own cited range for cohere, `#L64-L70`, resolves onto that
inline dict, so the anchor actively refutes the sentence attached to it.
This is the same defect cycle 2 found on litellm, with the client name
swapped and the wrong mechanism kept. **F14 BREAKS.**

Severity is low and bounded. The operative conclusion is independently
true: both clients type `documents` as `List[str]` and pass it through
unwrapped, so both send the shape Bifrost 1.6.7 rejects, and R5 pins
`provider: "openai"` so cohere is never on the path. No requirement,
subticket or dependency moves under the correction. Hence
`pass-with-required-fixes` rather than `fail`.

### Required fix 3 — P20's tag attribution: FULLY VERIFIED, HOLDS

I re-ran the whole chain this cycle rather than trusting cycle 2.

Link 2, the pin. `maximhq/bifrost@transports/v2.0.0 transports/go.mod:18`
> 	github.com/maximhq/bifrost/core v1.8.3

No `replace` directive anywhere in that file; `go.work` at the repo root
of that tag returns HTTP 404. So the binary links published `core v1.8.3`.

Link 2, the byte-identity. Captured probe output:
```
core/v1.8.3/core/schemas/rerank.go       -> http=200 md5=6d6fafb30462aad8847793176ed53041 bytes=3739
transports/v2.0.0/core/schemas/rerank.go -> http=200 md5=6d6fafb30462aad8847793176ed53041 bytes=3739
transports/v1.6.7/core/schemas/rerank.go -> http=200 md5=22ad17711ea7831f50b700eb6af8f76c bytes=2041
v2.0.0/core/schemas/rerank.go            -> http=200 md5=22ad17711ea7831f50b700eb6af8f76c bytes=2041
core/v2.0.0/core/schemas/rerank.go       -> http=404
UnmarshalJSON matches: core_v183=1  intree_t200=1  intree_t167=0  bare_v200=0
```
The claimed md5 `6d6fafb30462aad8847793176ed53041` is correct and the two
files are byte-identical.

`maximhq/bifrost@core/v1.8.3 core/schemas/rerank.go:26-31`
> ```
>  26  // UnmarshalJSON accepts either a bare string or an object. Every rerank API in the wild takes
>  27  // `documents: ["a", "b"]`, so the canonical route accepts that form and normalizes it.
>  28  func (d *RerankDocument) UnmarshalJSON(data []byte) error {
>  29  	var text string
>  30  	if err := sonic.Unmarshal(data, &text); err == nil {
>  31  		*d = RerankDocument{Text: text}
> ```
Line 28 is exactly where the plan says it is, and the cited `#L26-L41`
range spans comment through closing brace.

Both negative claims hold: `core/v2.0.0` 404s, and the bare `v2.0.0` tag's
copy is byte-identical to `transports/v1.6.7` with zero unmarshalers.

Link 1, the image-tracks-transports chain. `transports/version` reads
`2.0.0` at `transports/v2.0.0` and `1.6.7` at `transports/v1.6.7`;
`transports/Dockerfile:30`
> ```
>   COPY transports/go.mod transports/go.sum ./
> ```
and the repo pin, `deployments/applications/services.tf:537`
> ```
>       bifrost_version  = "1.6.7"
> ```
consumed at `deployments/applications/services/bifrost.hcl:40`
> ```
>         image        = "docker.io/maximhq/bifrost:v${bifrost_version}"
> ```

Live cross-check at review time: `GET http://192.168.2.50:8080/api/version`
returned `"v1.6.7"`, so "the deployed one is 1.6.7" was true when this
verdict was written. **F10 RESOLVED, F11 re-confirmed.**

### Change 4 — the disclosed out-of-fix_sections edits: WARRANTED

§1 now reads "embedding and rerank through Bifrost against embark's
served models" and "Gated on `U7-upgrade-bifrost-2x`, without which the
rerank path cannot work." The alternative was leaving the plan's first
line contradicting R5, which is worse than a disclosed out-of-scope edit.
It introduces nothing new. **F12 RESOLVED.**

Front-matter `Q2` was narrowed for the same over-reach as fix 2, and
inherits the same false "same body builder" clause, which is why
`front-matter` appears in `fix_sections:`.

### Change 5 — P22 gained evidence and stayed UNCERTAIN: CORRECT

`deployments/infrastructure/services/oauth2-proxy-registry-ui.hcl:98`
> ```
>         network_mode = "host"
> ```
`:62`
> ```
>         OAUTH2_PROXY_OIDC_ISSUER_URL="{{ with secret "${oidc_secret}" }}{{ .Data.data.issuer }}{{ end }}"
> ```
That secret is written by `deployments/infrastructure/secrets.tf:268`
> ```
>     issuer        = "https://${var.vault_issuer_host}/v1/identity/oidc/provider/${vault_identity_oidc_provider.lab.name}"
> ```
which renders the same string `deployments/applications/services.tf:30`
hard-codes
> ```
>   vault_oidc_issuer = "https://vault.lab.orangecluster.nl/v1/identity/oidc/provider/lab"
> ```
So "the same issuer" is accurate. Live Consul at 192.168.2.30:8500 reports
node `radxa` 192.168.2.50 with `Serf Health Status` and `oauth2-proxy ping`
both `passing`.

The premise still opens "is UNCERTAIN", labels the new evidence
"Supporting, not decisive", says "That is a different runtime and a
different image, so it lowers the risk rather than settling it", and keeps
"Verify from the OpenViking alloc before S5 is called done." It did not
quietly become a settled claim. **F16 stays UNCERTAIN by design.**

### New context — the U7 dependency: HONEST

`.loop/ledger.json` now records `dependencies: ["U7-upgrade-bifrost-2x"]`
for OV1, so cycle 2's F13 (the gate had no teeth until `reconcile` ran) is
cleared. U7 is at stage `ready`, not `done`, and OV1 never says otherwise:
P20 link 3 says OV1 "must NOT be implemented before `U7-upgrade-bifrost-2x`
reaches `done`"; S0 says "nothing below may start before
`U7-upgrade-bifrost-2x` reaches `done`"; S3 "Depends on S0 and on U7 being
done"; §9 failure mode 2 spells out the diagnostic trap if OV1 lands first
("a flat `400 Invalid request payload` naming no field and an empty
`routing_info`, which reads like a Bifrost or embark fault"). §5 says
Bifrost's version bump "lives in `U7-upgrade-bifrost-2x`, which this ticket
depends on rather than performs". OV1 inherits U7's risk explicitly and
claims nothing about its completion. **F13 RESOLVED.**

## Per-assumption findings

- **P2 — BREAKS (one sub-clause).** `openviking/models/rerank/cohere_rerank.py:22`
  > class CohereRerankClient(RerankBase):

  The cohere client does not share `OpenAIRerankClient`'s builder; it
  builds its body inline at `:62-70` and posts to its own `/v2/rerank`.
  Everything else in P2 stands: the openai `List[str]` pass-through
  (`openai_rerank.py:75`), the litellm carve-out, the vikingdb
  object-wrapping exception, and the 200-vs-400 Bifrost behavior twice
  reproduced live (ledger F6; gateway still at `v1.6.7` this cycle).

- **P20 — HOLDS.** `maximhq/bifrost@core/v1.8.3 core/schemas/rerank.go:28`
  > func (d *RerankDocument) UnmarshalJSON(data []byte) error {

  All three links and both negative claims demonstrated this cycle by
  captured probe (md5s and HTTP codes above). This is the premise the U7
  dependency rests on and it is now the best-evidenced claim in the plan.

- **P22 — UNCERTAIN (correctly, by the author's own label).**
  `deployments/infrastructure/services/oauth2-proxy-registry-ui.hcl:98`
  > ```
  >         network_mode = "host"
  > ```
  Supporting evidence verified accurate; the premise still requires an
  in-alloc check before S5 closes. Do not force a probe where the author
  already disclaimed the measurement.

- **P1, P3 to P19, P21 — no change in scope, still hold**, on the evidence
  settled in cycles 1 and 2 and recorded in the ledger:
  - P1 — no change in scope, still holds, demonstrated twice inside the
    pinned image `ghcr.io/volcengine/openviking:v0.4.17.1` (ledger F5).
  - P4, P7, P8, P9, P12, P16, P17, P18 — no change in scope, still hold,
    source anchors resolved at the deployed tag in cycles 1 and 2.
  - P3, P5, P13, P15 — no change in scope, still hold, live probes
    (Vault discovery, Bifrost `dim=768`, Postgres 18.3 / pgvector 0.8.2,
    MinIO policy list) recorded in ledger F6 and cycle-1 entries.
  - P6, P10, P11, P14, P19 — no change in scope, still hold; P14's
    three-pytest-hook wording was the cycle-1 F4 fix and re-verified in
    cycle 2.
  - P21 — no change in scope, still holds, ghcr digest and in-image
    `__version__` re-probed in cycle 2 (ledger F1 RESOLVED).

- **PI-1 (implicit, added) — HOLDS.** The plan must not treat U7 as
  complete. `.loop/ledger.json` has U7 at `ready`; every OV1 reference
  gates on U7 reaching `done`. Verified above.

## Most dangerous assumption

**P20.** If the 2.0.0 container did not link a `core` module carrying
`RerankDocument.UnmarshalJSON`, the entire `depends_on` would buy nothing
and R5's rerank path would still 400 after U7 lands, making OV1
unimplementable as written. It has now been rewritten twice, so I
re-demonstrated it rather than inheriting it: the md5, the `go.mod` line,
the absent `replace`, the absent `go.work`, the 404 on `core/v2.0.0`, and
the unmarshaler-free bare `v2.0.0` tag all check out. It holds.

## Required fixes

1. **§ Premises, P2.** Delete the claim that cohere shares the openai body
   builder. `CohereRerankClient` extends `RerankBase`
   (`cohere_rerank.py:22`) and builds its own body inline at `:62-70`.
   State the true and sufficient fact instead: each of the two builds its
   own flat body and both pass `documents` through as a plain `List[str]`,
   which is the shape Bifrost 1.6.7 rejects. Keep the cited range
   `cohere_rerank.py#L64-L70` — it already shows the inline dict.
2. **Front-matter, `premise.Q2`.** Remove "through the same body builder"
   for the same reason, leaving the wire-shape claim, which is true.

Both are confined to `front-matter` and `premises`, which is what
`fix_sections:` declares. Neither changes a requirement, a subticket, the
code surface, the gate table, or the U7 dependency.

## Observations (not blocking, no fix required)

- Q3 lists four `auth_mode` options; the registry actually exposes five
  (`ldap` is still absent). Immaterial: no LDAP in the cluster and the
  plugin logs "LDAP library not available". Carried from cycle 2 as F7.
- P2's sentence "Switching between those two changes nothing" is true of
  the wire *shape*, which is what the premise is about, but cohere also
  posts to a fixed `/v2/rerank` path and adds `return_documents`. Worth a
  half-sentence if fix 1 is being written anyway.

## Scratch

scratch created at `.loop/scratch/OV1-openviking-service.plan-validator/p20/`
(nine fetched `rerank.go` / `go.mod` copies used for the md5 comparison).
Retained deliberately alongside the cycle-1 and cycle-2 artifacts in the
same root so the operator can re-check the md5 claim without refetching.
WARN — scratch artifact left at
`.loop/scratch/OV1-openviking-service.plan-validator/p20/`. Diagnostic
only; `.gitignore` carries `.loop/scratch/` and the fingerprint builder
strips `.loop`, so it cannot reach the tree fingerprint.

Findings ledger updated at
`.loop/scratch/OV1-openviking-service.plan-validator/findings.json`
(28 entries; F9, F10, F12, F13, F15 resolved, F14 and F16 added).
