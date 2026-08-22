---
verdict: pass
plan: a36c2a86b08898f2fcaa9ad545487899ce0e093d3dce4bd1590a7061397638e5
bound_paths: front-matter, 5, 6, 7, 8, 9, 10, premises
scope: dabacd3293e10129de2d13f992bb3c8cd5708f039e8bbf1c951b37962e20611d
citations: .loop/plans/L2-landing-homepage.md:158-162 = constrained to `ubuntu` (Q3, resolved), `network_mode = "host"` (the common pattern in this repo — most podman tasks use it; `minio.hcl` and `redis.hcl` are the counterexamples, both static-ported without it, so "host" here is a deliberate choice matching the majority convention, not an unconditional repo rule)
.loop/plans/L2-landing-homepage.md:336-351 = ## 9. Risk assessment / **Precondition, checked before trusting any gate-dependent row in §8.** ... confirm `http://192.168.2.30:8404/;csv` shows `dash` as `UP`.
.loop/plans/L2-landing-homepage.md:465-488 = **P2.** oauth2-proxy's job is deployed and healthy at the application layer (Nomad/Consul) ... but its HAProxy backend is DOWN as of this writing.
.loop/plans/L2-landing-homepage.md:58-65 = **oauth2-proxy is live but points at a placeholder.** ... Confirmed live 2026-08-22: `curl -sI https://dash.lab.orangecluster.nl/` → `HTTP/2 503`
deployments/infrastructure/services/oauth2-proxy.hcl:54 = OAUTH2_PROXY_UPSTREAMS="static://200"
deployments/infrastructure/services.tf:288-292 = oauth2_proxy = { host = "192.168.2.50" ssh_user = "radxa" rules = ["allow from 192.168.2.30 to any port 4180 proto tcp"] }
deployments/infrastructure/services.tf:296-306 = resource "null_resource" "firewall" { for_each = local.firewall_rules ... triggers = { rules = jsonencode(each.value.rules) always_run = timestamp() } }
deployments/infrastructure/services/minio.hcl:18 = network {
deployments/infrastructure/services/redis.hcl:12 = network {
---

# plan-validator: L2-landing-homepage (narrow re-check)

Plan fingerprint verified locally: `sha256sum .loop/plans/L2-landing-homepage.md`
returns `a36c2a86b08898f2fcaa9ad545487899ce0e093d3dce4bd1590a7061397638e5`,
matching the briefing exactly. `loopctl verify-plan L2-landing-homepage` →
`valid`. `loopctl verify-eval-substance L2-landing-homepage` → `valid`.
`loopctl plan-snapshot L2-landing-homepage` (run twice, idempotent)
reproduces the same plan fingerprint, the same floor `bound_paths`, and
the scope digest `dabacd3293e1...` bound above, so this verdict authorizes
against the dispatch-time bindings, not a value I invented.

This pass is scoped as directed: a narrow re-check of the three required
fixes applied since the `a6f8f68d...` verdict
(`pass-with-required-fixes`), not a full re-litigation. `git status`/`git
diff` confirm nothing in the repo changed between that verdict and this
one except `.loop/plans/L2-landing-homepage.md` and
`.loop/evals/L2-landing-homepage.md` (the eval rewrite already covered by
the prior full pass's item 6 and independently re-confirmed `valid` above)
— every anchor the prior verdict resolved (`haproxy.hcl`,
`oauth2-proxy.hcl`, both `services.tf` files, `grafana.hcl`, `loki.hcl`,
etc.) is byte-identical, so P1, P3-P11 carry forward unchanged rather than
being re-typed from scratch.

## Premise verdict: SOUND

Gate verdict: **pass**.

## Per-assumption findings

- **P1 — `dash` ACL/backend already exists and is owned by L1. HOLDS — no
  change in scope, still holds.** `haproxy.hcl` is untouched since the
  prior verdict (confirmed via `git diff`, zero delta); the prior pass's
  anchors (`haproxy.hcl:107,118,155-156`) and quotes stand.

- **P2 — oauth2-proxy's job is deployed/healthy, configured to a
  placeholder, but its HAProxy backend is DOWN. HOLDS (rewritten, and
  independently re-verified live today).**
  `.loop/plans/L2-landing-homepage.md:465-471`
  > **P2.** oauth2-proxy's job is deployed and healthy at the application
  > layer (Nomad/Consul), configured to proxy to a hardcoded placeholder,
  > not to Homepage — but its HAProxy backend is DOWN as of this writing.

  This is the rewrite required fix (1) asked me to confirm. It no longer
  calls oauth2-proxy "live" outright; it separates "job healthy" from
  "edge reachable" and states the edge is currently unreachable, matching
  required fix (1)'s wording exactly (job healthy via Consul's local
  check, HAProxy backend `L4TOUT`, `bifrost` on the same node `UP` ruling
  out a node/network explanation, pointing at the firewall rule). I did
  not take this on faith — I re-ran the same three probes myself, live,
  just now:

  ```
  $ curl -sI https://dash.lab.orangecluster.nl/
  HTTP/2 503
  $ curl -s "http://192.168.2.30:8404/;csv" | grep -E "^dash,|^bifrost,"
  bifrost,bifrost1,...,UP,...,L4OK,...
  bifrost,BACKEND,...,UP,...
  dash,dash1,...,DOWN,...,L4TOUT,...
  dash,BACKEND,...,DOWN,...
  $ curl -s $CONSUL_HTTP_ADDR/v1/health/checks/oauth2-proxy
  [{"Node":"radxa", ... ,"Status":"passing", ...
    "Output":"HTTP GET http://192.168.2.50:4180/ping: 200 OK Output: OK", ...}]
  ```

  All three facts the rewritten premise asserts are true right now, not
  merely at the time of the original probe: Consul's check is `passing`
  (verified via the Consul HTTP API directly, not by trusting the plan's
  citation), HAProxy's own stats page shows `dash` `DOWN`/`L4TOUT` while
  `bifrost` on the identical host (`192.168.2.50`) is `UP`, and the edge
  HTTPS request still 503s. The premise as now written is accurate, not
  merely plausible.

- **P3 — TLS termination/redirect split; zero `haproxy.hcl` edits. HOLDS —
  no change in scope, still holds.** `haproxy.hcl:91-96` unchanged since
  the prior verdict.

- **P4 — Public wildcard DNS; no F4 dependency. HOLDS — no change in
  scope, still holds.** Ledger reconfirmed this pass: `L1-landing-oauth2-proxy`
  → `done`, `A1-audit-plan-premise-sweep` → `done` (`loopctl ledger`),
  matching front-matter `depends_on` exactly.

- **P5 — Prometheus/Loki have no edge route. HOLDS — no change in scope,
  still holds.** `deployments/infrastructure/services.tf:204-215` and
  `haproxy.hcl` unchanged.

- **P6 — MLflow no longer exists. HOLDS — no change in scope, still
  holds.** `deployments/applications/storage.tf:23-26` unchanged.

- **P7 — Only `phoenix` carries basic-auth. HOLDS — no change in scope,
  still holds.** `haproxy.hcl:142-144,152-153` unchanged.

- **P8 — Grafana/Prometheus/Loki all run on `ubuntu`. HOLDS — no change in
  scope, still holds.** `services.tf:111-114`, `grafana.hcl:9,14`,
  `prometheus.hcl:9,14`, `loki.hcl:9,14,17` unchanged.

- **P9 — `deployments/applications/` is the correct root for Homepage.
  HOLDS — no change in scope, still holds.** Directory contents unchanged
  (`ls` reconfirmed both roots' `services/` directories this pass).

- **P10 — Cross-root host volumes are an established pattern. HOLDS — no
  change in scope, still holds.** `services.tf:42-60,122-140` and
  `loki.hcl:21-26` unchanged.

- **P11 — L1 is done and pre-approved this handoff. HOLDS — no change in
  scope, still holds.** Ledger reconfirmed: `L1-landing-oauth2-proxy` →
  `done`; `.loop/plans/L1-landing-oauth2-proxy.md:529-553` unchanged.

- **P12 (implicit, added by the prior cycle: "oauth2-proxy's `dash`
  backend is a healthy foundation L2 can build on"). Re-attacked, not
  rubber-stamped: the underlying fact still BREAKS as a bare claim (see
  P2 — `dash` is DOWN right now, freshly reconfirmed), but the plan no
  longer depends on it silently. HOLDS as now written.** Required fix (2)
  asked me to confirm §9 carries an explicit precondition rather than
  leaving this implicit. It does, and it is the first thing in the
  section, not buried under the six failure-mode bullets that follow:
  `.loop/plans/L2-landing-homepage.md:336-351`
  > ## 9. Risk assessment
  >
  > **Precondition, checked before trusting any gate-dependent row in
  > §8.** *(Added 2026-08-23, second plan review.)* As of this writing,
  > oauth2-proxy's `dash` HAProxy backend is DOWN (`check_status=L4TOUT`)
  > even though the job itself is healthy — see Premise P2. This is a
  > pre-existing condition unrelated to this ticket's own changes, most
  > likely the firewall rule in `local.firewall_rules["oauth2_proxy"]`
  > having fallen out of effect on the live host. Before running any §8
  > eval row that depends on `dash` actually routing traffic (the
  > unauthenticated-block row, the post-login tile-view row), confirm
  > `http://192.168.2.30:8404/;csv` shows `dash` as `UP`. If it does not,
  > this is an operator fix outside L2's scope (most likely: re-run
  > `terraform apply` in `deployments/infrastructure/`, which
  > unconditionally re-executes every `local.firewall_rules` entry via
  > its `timestamp()` trigger) before continuing.

  I independently verified the diagnosis, not just the prose: the
  self-heal mechanism it names is real.
  `deployments/infrastructure/services.tf:296-306`
  > resource "null_resource" "firewall" {
  >   for_each = local.firewall_rules
  >
  >   # timestamp() changes every plan, so every apply re-runs the ufw commands.
  >   ...
  >   triggers = {
  >     rules      = jsonencode(each.value.rules)
  >     always_run = timestamp()
  >   }

  and the `oauth2_proxy` entry that would be re-applied is present:
  `deployments/infrastructure/services.tf:288-292`
  > oauth2_proxy = {
  >   host     = "192.168.2.50"
  >   ssh_user = "radxa"
  >   rules    = ["allow from 192.168.2.30 to any port 4180 proto tcp"]
  > }

  So the escalation path the precondition names ("re-run `terraform
  apply`... unconditionally re-executes every `local.firewall_rules`
  entry via its `timestamp()` trigger") is a real, working mechanism, not
  an invented excuse, and it is scoped as an *operator* action outside
  L2's own subtickets — consistent with the Non-goal "Do not implement or
  redesign L1 (done)." The load-bearing assumption the plan now rests on
  is not "`dash` is healthy" (false) but "if `dash` is down, this
  precondition catches it before a gate-dependent eval row is
  misattributed to L2's own diff, and the named remedy is real and
  correctly scoped" — and that assumption holds.

## Required-fix confirmation (this pass's actual task)

1. **Fix 1 (Premise P2 reframing) — confirmed accurate and correctly
   placed.** See P2 above. Matches the described fix verbatim: job
   healthy/Consul-passing vs. edge/HAProxy-backend-down, same-node
   `bifrost` control ruling out a node explanation, firewall-drift
   hypothesis. Independently re-verified live (not re-stated from the
   plan's own citation).
2. **Fix 2 (§9 precondition) — confirmed present, accurate, and NOT
   buried.** It is the opening paragraph of §9 (`plan:338-351`), ahead of
   Blast radius/Reversibility/Failure modes, so an implementer reading §9
   top-to-bottom hits it before the six risk bullets, and §8 (read
   immediately before §9) is exactly where the eval rows it gates live.
   The diagnosis (firewall rule "fallen out of effect") and remedy
   (`terraform apply` + `timestamp()` self-heal) both check out against
   the actual Terraform code.
3. **Fix 3 (`network_mode` claim softened) — confirmed accurate.**
   `plan:158-162` now names `minio.hcl`/`redis.hcl` as counterexamples
   instead of claiming a universal rule. I independently counted: of the
   18 `driver = "podman"` services across both roots, 16 set
   `network_mode` and exactly 2 — `minio.hcl` (`network { port "http_api"
   { static = 9000 } ... }`, no `network_mode` line) and `redis.hcl`
   (`network { port "cache" { static = 6379 ... } }`, no `network_mode`
   line) — do not. "Most podman tasks use it; `minio.hcl` and `redis.hcl`
   are the counterexamples" is the exact, correct count, not an
   approximation.

All three required fixes land where an implementer reading the plan
top-to-bottom (Context → Requirements → Code surface → Tests → Risk →
Subtickets → Open Questions → Premises) would encounter them before they
matter: the Requirement 1 fix sits inside Requirement 1 itself, the §9
precondition sits at the top of §9 (read before the Subtickets an
implementer executes), and the Premise fix sits in Premises, which §9
explicitly cross-references ("see Premise P2") rather than assuming the
reader will stumble onto it unprompted.

## Minor, non-blocking observation (not a required fix)

**Context (§4, `plan:58-65`) still carries the pre-fix framing** and now
contradicts the corrected Premise P2 on the same fact:
`.loop/plans/L2-landing-homepage.md:58-65`
> - **oauth2-proxy is live but points at a placeholder.**
>   ...
>   Confirmed live 2026-08-22: `curl -sI https://dash.lab.orangecluster.nl/` →
>   `HTTP/2 503`; ...

This reads the same `503` that P2's own probe text later calls "HAProxy's
own 'no server available' response, not a response from oauth2-proxy" as
evidence of liveness instead — the opposite conclusion, about the same
fact, in the same document. Context (§1-4, §11) is outside this floor's
`bound_paths` by design, and the load-bearing account of this fact
correctly lives in Premises (P2) and the §9 precondition, both of which
an implementer must read as part of the contract and both of which are
now accurate. This is **not blocking**: implementation is not impossible
and the eval is not unrunnable — the authoritative, gating text is
correct and is read before Subtickets execute. It is a one-line
find-and-reword an operator could clear in the same pass that promotes
this ticket, not a reason to hold it in `PLANNING`.

## Sanity checks (this pass's item 2)

- `loopctl verify-plan L2-landing-homepage` → `valid`.
- `loopctl verify-eval-substance L2-landing-homepage` → `valid`.
- `loopctl plan-snapshot L2-landing-homepage`, run twice: stable fingerprint
  `a36c2a86b08898f2fcaa9ad545487899ce0e093d3dce4bd1590a7061397638e5` and
  stable scope `dabacd3293e10129de2d13f992bb3c8cd5708f039e8bbf1c951b37962e20611d`.
- `loopctl ledger`: `L1-landing-oauth2-proxy` → `done`,
  `A1-audit-plan-premise-sweep` → `done` (both of L2's `depends_on`
  entries satisfied). Note: the ledger's `L2-landing-homepage` blocker
  text is still the stale 2026-07-30 `BROKEN` message; that is a
  reconcile-timing artifact for the operator/harness to clear on the next
  `loopctl advance`, not a defect in the plan itself.

## Contract hygiene

Unchanged from the prior pass's clean assessment: no dropped section, all
named tests homed in §7, every §6 requirement demanding a
quantity/observable has a named producer in §7, non-goals explicit, forks
surfaced with recommendations (§11). The three edits reviewed here do not
touch this.

## Most dangerous assumption

Still **P12/P2 together**: that an implementer who reaches the live
cluster to run the gate-dependent eval rows will actually perform the §9
precondition check before doing so, rather than skipping straight to the
eval table. The plan's fix is correct and complete on paper (see above,
independently re-verified live), but it is a manual step, not a mechanized
gate — nothing in `loopctl verify-eval-substance` or the eval marker
itself enforces reading §9 first. That is a process risk inherent to
"precondition in prose," not a defect in this rework, and not something
this ticket's contract requires a mechanized enforcement for.

## Required fixes before this plan leaves PLANNING

None. All three fixes from the prior cycle are confirmed applied,
accurate, and adequately placed. The Context wording overlap noted above
is advisory only.

## Method and constraints observed

Read-only throughout except the two placeholder/final verdict writes to
this file. Live probes were read-only network requests (`curl` against
HAProxy's public stats page and the authenticated Consul HTTP API already
exported into this environment's `CONSUL_HTTP_ADDR`, `getent hosts`,
`git diff`/`git status`, `grep`) — no `vault write`, no `nomad job
run`/`stop`, no `terraform apply`, no mutating git command. No scratch
artifact was needed (every check was a `Read`, a `grep`/`git diff`, or a
read-only network probe, each well under the 5-minute wall-clock
ceiling); no scratch directory was created at
`.loop/scratch/L2-landing-homepage.plan-validator/`.
