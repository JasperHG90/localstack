---
slug: F6-foundation-vault-consul-secrets-engine
blockers: []
friction: [other:ticket-invariant-vs-provider-reality, other:live-eval-cluster-unreachable]
worked: [f5-parallel-mirror, schema-dump-resolved-fork, adversarial-review-caught-latent-bug]
harness_change:
cycles: 0
gates_red: 0
---

## What worked

- F5 was an exact structural parallel (Nomad secrets engine); mirroring its
  idempotent enable guard, config/access shape, and TF role kept the design
  decisions small and the diff surgical.
- Dumping the pinned provider's schema offline (filesystem-mirror + a scratch
  dir, `-backend=false`) resolved the policy-attachment fork definitively
  instead of guessing: it proved `vault_consul_secret_backend_role` has no
  inline-policy field and attaches only by name.
- The adversarial pass caught a real latent bug (inert `session_prefix
  "terraform/"`) that no F6 eval would have surfaced, and it routed cleanly to
  F8 via relay-finding rather than scope-creeping into F6.

## What worked less well

- other:ticket-invariant-vs-provider-reality — the ticket's config-split
  invariant asserted two things (Terraform owns the Consul policy AND never
  holds the Consul mgmt token) that the pinned vault ~>5.3.0 provider makes
  mutually exclusive. Surfaced as an operator fork (Option B chosen). A ticket
  that names a specific provider version should sanity-check the invariant
  against that provider's actual resource schema before freezing it.
- other:live-eval-cluster-unreachable — the seven Definition-of-Done evals run
  against the live cluster (192.168.2.30), which is unreachable from the dev
  container, so they could not be executed and remain pending an operator run.
  The enforced gate (`just pre_commit`, offline) passed, but F6's real
  acceptance is deferred. IaC tickets whose DoD is live-cluster evals need a
  reachable target or an explicit "operator runs the evals" handoff baked in.
