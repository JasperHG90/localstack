---
slug: F5-foundation-vault-nomad-secrets-engine
blockers: [unresolved-design-fork]
friction: [other:ticket-premise-wrong-on-live-behavior, other:eval-not-covering-sibling-resources, reviewer-boilerplate]
worked: [other:live-eval-caught-scope-gap, other:acl-parser-sentinel-probe]
cycles: 2
gates_red: 0
harness_change:
---

## What worked

- The two-layer split held cleanly: Ansible (holding the management token)
  enabled + configured the engine idempotently, Terraform owned the role +
  policy. Running the actual Ansible playbook path (`--start-at-task`
  scoped to the nomad_server role) rather than hand-running vault CLI is
  what the operator required and is the correct source-of-truth method.
- Live evals did their job: the adversarial reviewer's Major finding (deploy
  policy could not manage the 8 dynamic host volumes co-located in the same
  root) was a real gap the offline gate could never catch. Tag
  `other:live-eval-caught-scope-gap`.
- Discovering the valid Nomad ACL host-volume capability names by probing
  the live parser with a candidate + guaranteed-invalid sentinel (so the
  policy never persists) was fast and non-destructive. Tag
  `other:acl-parser-sentinel-probe`.

## What worked less well

- The ticket asserted `vault_nomad_secret_role` takes `ttl`/`max_ttl` (it
  does not - lease is a mount property) and that `host_volume "*" { policy
  = "write" }` grants dynamic-host-volume management (it does not - that
  needs namespace `host-volume-*` caps). Both were provably wrong against
  live behavior and only surfaced by running the real thing. Tag
  `other:ticket-premise-wrong-on-live-behavior`.
- Eval 5 only exercised a `nomad_job`, so the DoD's own safety net missed
  the `nomad_dynamic_host_volume` resources in the same root that F8 must
  deploy. An eval should cover every resource kind the ticket's downstream
  consumer will touch, not just the headline one. Tag
  `other:eval-not-covering-sibling-resources`.
- I introduced a false "developer lacks host-volume-* caps" claim into the
  amendment while fixing the mechanism; the reviewer had to empirically
  disprove it. Coarse `policy = "write"` expands to those caps on Nomad
  v2.0.3. Tagged `reviewer-boilerplate` for the review's contract-only
  wording fix, though the substance was mine to own.

## Follow-ups (not blocking F5)

- The `deploy` role holds `host-volume-register` and `host-volume-write`,
  which the current create-only `nomad_dynamic_host_volume` resources do
  not use (reviewer Minor). Kept per the operator's explicit "broadest
  single-role" choice; a future least-privilege pass could trim to
  create/read/delete.
- F6 (Consul) is the exact parallel and will hit the same deployer-Vault-
  policy prerequisite; mirror this engine-config-in-Ansible / role-in-
  Terraform split.
