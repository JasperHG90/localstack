---
verdict: pass-with-required-fixes
plan: 3e6e12774dfb230d2862d9bc2d0fe217c386a80459a49278486e8e8ebb6341b6
---

# F9-foundation-scope-nomad-workloads-policy — plan-validator

Plan fingerprint verified locally with `sha256sum
.loop/plans/F9-foundation-scope-nomad-workloads-policy.md` ->
`3e6e12774dfb230d2862d9bc2d0fe217c386a80459a49278486e8e8ebb6341b6`, matching
the briefing.

Reviewed against the repo at `/home/vscode/workspace/.loop/worktrees/A1-audit-plan-premise-sweep`
and against the live cluster (`VAULT_ADDR=http://192.168.2.30:8200`,
`NOMAD_ADDR=http://192.168.2.30:4646`). Read-only throughout: no `vault
write`/`policy write`/`patch`, no JWT login (minting a token is a Vault state
change), no `nomad job run`/`stop`, no `terraform apply`, no mutating git.

## Premise verdict: PARTIALLY SOUND

The load-bearing core survives attack. The policy really is over-broad, the
plan's line-by-line breakdown of it byte-matches the live policy, the fix
mechanism it names is real and proven, and its refusal to decide the consumer
list up front is correct discipline. Three defects are real: one false claim
about which jobs hold the policy, a missing required eval artifact, and an
unflagged collision with a sibling `ready` ticket. All three are fixable in
the plan text; none invalidates the approach.

## Assumptions attacked

**P1 — The shared policy is `vault_nomad_workloads.hcl.j2`, 24 lines, and is
what `jwt-nomad`'s `default_role` attaches. HOLDS.**
`wc -l bootstrap/roles/nomad_server/templates/vault_nomad_workloads.hcl.j2` =
24. Live `vault read auth/jwt-nomad/config` -> `default_role
nomad-workloads`; `vault read auth/jwt-nomad/role/nomad-workloads` ->
`token_policies [nomad-workloads]`. The Ansible task that writes it is
`bootstrap/roles/nomad_server/tasks/main.yml:257-271` (`vault policy write
nomad-workloads /opt/nomad/policies/vault_nomad_workloads.hcl`).

**P2 — The grant breakdown `:1-7` read / `:9-15` list incl. cluster-wide /
`:17-24` read+create+update on `bootstrap/data/*`. HOLDS, exactly.**
`vault policy read nomad-workloads` renders line-for-line onto the template:
`:1-3` and `:5-7` `read` on the job-scoped `secret/data/<ns>/<job_id>/*` and
the bare path; `:9-11` `list` on `secret/metadata/<ns>/*`; `:13-15` `list` on
`secret/metadata/*`; `:17-20` `read, create, update` on `bootstrap/data/*`
under the comment `# Bootstrap secrets (for rotation jobs)`; `:22-24` `list`
on `bootstrap/metadata/*`. Unlike the F1 plan's original 11-of-24-line
citation, F9 characterizes the policy completely and accurately.

**P3 — "Every job using a bare `vault {}` — which is every job except haproxy
— holds it" (plan `:34-35`). BREAKS.**
The exception is `acme`, not `haproxy`. Repo: `haproxy.hcl:39` is a bare
`vault {}`; `acme.hcl:73-75` and `:154-156` are `vault { role =
"${vault_role}" }`. Live: `nomad job inspect haproxy` -> task Vault
`Role: ""` (so it lands on `default_role` = `nomad-workloads`), while `nomad
job inspect acme` -> both tasks `Role: acme`. The claim is also imprecise in a
second way: `node-exporter` and `promtail` carry no Vault block at all
(`nomad job inspect` -> `Vault: None`), so they hold nothing.

Why this matters beyond a typo: `haproxy` is the single highest-blast-radius
holder of this policy. It renders the edge TLS PEM from Vault
(`haproxy.hcl:64` `{{ with secret "${tls_secret}" }}`, resolved at
`services.tf:323` to `secret/data/default/haproxy/tls`), and a blocked
template there takes every routed service down (the reasoning the repo itself
records at `acme.tf:1-6`). The plan names precisely that job as exempt, and
its eval-2 population (`memex, grafana, minio`) omits it.

The narrowing itself does not break haproxy: its read stays covered by the
job-scoped grant that survives (`ns=default`, `job_id=haproxy`). So this is a
descriptive error with an operational consequence for the verification step,
not a fatal design error.

**P4 — `bootstrap/metadata` holds `github` and `tailscale`, the GitHub PAT and
Tailscale auth key. HOLDS.**
Live `vault list bootstrap/metadata` -> `github`, `tailscale`.
`docs/credential-rotation.md:20` (`bootstrap/tailscale`, field `auth_key`) and
`:29` (`bootstrap/github`, fields `user`, `pat`) resolve as cited. The mount
is KV v2 (`vault read sys/mounts/bootstrap` -> `options
map[version:2]`), so eval 1's `vault kv get -mount=bootstrap github` is a
valid probe.

**P5 — The dedicated-role mechanism exists and is proven at `acme.tf:41-90`,
selected via `acme.hcl:73-75`. HOLDS.**
`acme.tf:41-49` is `vault_policy.acme_tls_write`; `:66-90` is
`vault_jwt_auth_backend_role.acme` on `backend = "jwt-nomad"`.
`acme.hcl:73-75` is the `vault { role = "${vault_role}" }` block. Live `vault
list auth/jwt-nomad/role` -> `acme`, `nomad-workloads`.

**P6 — One token per task, so a dedicated role REPLACES `nomad-workloads`;
`acme.tf:87` therefore carries both. HOLDS.**
`acme.tf:87`: `token_policies = ["nomad-workloads",
vault_policy.acme_tls_write.name]`. Live `vault read
auth/jwt-nomad/role/acme` -> `token_policies [nomad-workloads
acme-tls-write]`. The repo states the same reasoning independently at
`acme.tf:56-61`.

**P7 — "Which jobs actually read `bootstrap/*` is not yet established"
(plan `:53-54`). HOLDS as written, and the evidence points hard at "none".**
Not a defect — the plan is correctly conservative — but three findings should
be folded in so subticket 1 starts from evidence rather than zero:
(a) I inspected all 19 live jobs (`nomad job inspect <job>` for every row of
`nomad job status`) grepping for the `bootstrap` mount: zero hits. The only
match was prose in the `hermes` system prompt, unrelated to Vault.
(b) Repo-wide grep for `bootstrap/data`, `bootstrap/metadata`, or `secret
"bootstrap` across `*.hcl`/`*.tf`/`*.j2` outside `bootstrap/` itself: zero
consumers.
(c) `docs/credential-rotation.md:34-40` is a section titled "Why Ansible (Not
Nomad Periodic Jobs)" that states both credentials are host-level and consumed
by Ansible playbooks, precisely because a container cannot use them. That is a
documented, in-repo answer to Q2 and it says "nothing".

**P8 — The change applies via an Ansible re-run against live Vault, outside
`terraform plan`. HOLDS.** `tasks/main.yml:265-271` shells `vault policy
write` under the bootstrap token. Nothing in `deployments/` manages this
policy.

**P9 — Repo gate anchors. HOLDS.** `justfile:18-19` is `pre_commit:` /
`pre-commit run --all-files`; `justfile:30-32` is `worktree_setup path:` with
its two body lines. `git show --stat 3c12c7a` confirms the commit that added
it ("seed loop worktrees with the gitignored inputs the gates need").
`.loop/config.json` `gates` = `["just pre_commit"]`, matching.

**P10 — Providers pinned at `providers.tf:1-24`. HOLDS.**
`deployments/infrastructure/providers.tf:1-24` is the
`terraform { required_providers { ... } }` block.

**P11 — "Evals (live) — encoded in `.loop/evals/<slug>.md`" (plan `:119`).
BREAKS.** `.loop/evals/F9-foundation-scope-nomad-workloads-policy.md` does not
exist (`ls .loop/evals/F9*` -> No such file). `.loop/config.json` sets
`"require_eval": true`, so the loop refuses to pick the ticket up until a
signed-off eval marker exists, and the plan points at a file that was never
written.

To be fair to the plan on the substance: its prose eval set is NOT a shape
check. Eval 1 is a genuine deny-assertion (`vault kv get -mount=bootstrap
github` -> 403, with the before/after contrast stated), evals 2, 3 and 5 are
genuine permit-assertions against live allocations and rendered templates, and
eval 5 correctly accounts for the fact that a blocked Vault template hangs
rather than failing fast. That is exactly the permit-and-deny pair a
policy-narrowing ticket needs. The defect is that none of it is encoded in a
scored artifact, so there are no scorer rows to audit and nothing the harness
can gate on.

**P12 — F9 can run independently of F1 (implicit; `depends_on =
["A1-audit-plan-premise-sweep"]` only). BREAKS.**
F1 is `ready` with `dependencies = []` and `priority = 40`; F9 is `priority =
48`, so on the loop's stated ordering ("higher is picked sooner") F9 is
preferred once A1 clears. F1's plan requires documenting the policy "**as it
actually is** (including the `bootstrap/data/*` write grant and the
cluster-wide `secret/metadata/*` list)"
(`.loop/plans/F1-foundation-nomad-wi-jwt-trust.md:180-182`), cites `:9-15` and
`:17-24` in its own code surface (`:256-258`), and carries the restriction
"**Do not narrow it either**" (`:169`). Whichever ticket runs second inherits
a falsified Context. F9 neither orders itself relative to F1 nor records that
it invalidates F1's documentation requirement, even though it does list
`docs/credential-rotation.md` for exactly that kind of downstream update.

The `depends_on` edge F9 does declare is sound: `A1-audit-plan-premise-sweep`
is a real slug at stage `implementing` in `.loop/ledger.json`, a deliberate
hold gate, satisfiable. The problem is a missing edge, not a broken one.

## Required attack surface, reported explicitly

1. **Stale premise (a claim true at authoring, false now): none found.** Every
   current-state claim in the Context was re-verified live today and still
   holds. P3 is wrong, but it was wrong on 2026-07-25 as well: `haproxy.hcl:39`
   has carried a bare `vault {}` throughout, and `acme` has had its dedicated
   role since `acme.tf` landed. That is an authoring error, not drift.
2. **Inlined conclusion (a fact asserted as settled that an unrun ticket was
   to establish): none found.** The plan is disciplined here. It routes the
   consumer list to subticket 1 and Q2 rather than asserting it, routes the
   `secret/metadata/*` decision to requirement 4 and Q3 rather than deciding
   it, and marks the dedicated-role code-surface entry "(new, only if subticket
   1 finds a real consumer)". Notably it does NOT inline the conclusion my own
   probe supports (that nothing consumes `bootstrap/*`), which is the correct
   call for a plan.
3. **Broken dependency edge: none.** See P12: the declared edge to A1 is
   valid; the finding is a MISSING edge to F1.
4. **Shape-check eval: no eval file exists to check.** See P11. There are no
   `ls`/`grep`/file-existence scorer rows to flag because there are no rows at
   all. The prose evals do carry both halves of the crucial question (still
   permits what live jobs need; now denies what it should), so the fix is to
   encode them, not to redesign them.
5. **Unresolvable anchor: one, plus one false characterization.** Every
   `path:line` in the plan resolves to what it claims:
   `vault_nomad_workloads.hcl.j2:9-15` and `:17-24`, `acme.tf:41-90`,
   `acme.tf:87`, `acme.hcl:73-75`, `docs/credential-rotation.md:20,29`,
   `justfile:18-19`, `justfile:30-32`, `providers.tf:1-24`,
   `.claude/rules/adversarial-reviews.md`, and the unnumbered
   `tasks/main.yml` reference (`:257-271`). The unresolvable one is
   `.loop/evals/<slug>.md` (P11). The false characterization is the
   haproxy/acme claim at plan `:34-35` (P3), which cites no anchor — had it
   cited one, it would not have survived writing.
   One harmless over-inclusion: `docs/credential-rotation.md` is listed in the
   code surface "update if it documents the current grant as the mechanism
   rotation jobs rely on". It does not (the file never mentions the Nomad
   policy), so that entry resolves to a no-op. The conditional phrasing makes
   this correct rather than wrong.

## Most dangerous assumption

**P3 — that haproxy is the job exempt from the shared policy.** It is the
inverse of the truth, and it is dangerous in the specific direction that
matters for this ticket. The plan's own risk section says the failure mode is
a template that blocks cluster-wide rather than erroring, so verification
coverage IS the safety net; P3 removes from that net the one job whose blocked
template takes down every routed service. An implementer who trusts `:34-35`
verifies memex, grafana and minio, sees green, and never checks the edge.

## Required fixes

1. **Correct plan `:34-35`.** The job with a dedicated role is `acme`
   (`acme.hcl:73-75`, `:154-156`; live `Role: acme`), not `haproxy`
   (`haproxy.hcl:39` bare `vault {}`; live `Role: ""`). Note also that
   `node-exporter` and `promtail` declare no Vault block at all. Correct the
   affected-jobs list at `:47-50` to include haproxy, bifrost, mlflow,
   phoenix, talat-shim and talat-consumer, or restate it as explicitly
   illustrative.
2. **Add haproxy to the eval-2 population at `:123-127`,** with a one-line
   note that its read (`secret/data/default/haproxy/tls`, `services.tf:323`)
   stays covered by the surviving job-scoped grant, so a blocked haproxy
   template after the change means over-narrowing and must trigger the
   rollback at `:145-147`.
3. **Author `.loop/evals/F9-foundation-scope-nomad-workloads-policy.md`**
   before the ticket leaves PLANNING, encoding evals 1-5 in the five-column
   Behavior/Input/Expected/Scorer/Threshold form with the operator sign-off
   marker `require_eval` demands (`.loop/config.json`). Keep both halves: the
   403 deny-assertion (eval 1) and the live permit-assertions (evals 2, 3, 5).
   An eval that only checks the policy file changed would be a shape check and
   must not be what lands.
4. **Resolve the F1 collision.** Either add `F1-foundation-nomad-wi-jwt-trust`
   to `depends_on` (and drop `priority` below F1's 40), or add an explicit
   note to Non-goals/Risk that F9 falsifies F1's plan at
   `F1-...:169` and `:180-182` and that F1 must be re-planned if F9 lands
   first. Silence here means one of the two tickets documents or protects a
   policy that no longer exists.

## Recommended (not required)

Fold P7's three evidence items into the Context so subticket 1 begins from
evidence: the all-19-job live inspect showing zero `bootstrap` consumers, the
repo-wide grep showing zero, and `docs/credential-rotation.md:34-40` ("Why
Ansible (Not Nomad Periodic Jobs)") stating the consumers are Ansible
playbooks by design. This does not decide Q2 — subticket 1 should still
confirm — but it converts an open search into a confirmation and strengthens
Q2's existing recommendation to delete the grants outright.

## Contract hygiene

All eleven contract sections are present. Anchors resolve (one exception,
fix 3). Gates are discovered rather than assumed and match
`.loop/config.json`. Non-goals are explicit and five-deep. Open questions Q1,
Q2 and Q3 each carry a recommendation and none is silently decided. The
"tests homed in the code surface" clause is satisfied vacuously and honestly:
the plan states "No unit-test harness for infra HCL, no CI" (`:111`), which is
true of this repo, and substitutes live evals.
