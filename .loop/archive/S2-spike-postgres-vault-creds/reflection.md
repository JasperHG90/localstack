---
slug: S2-spike-postgres-vault-creds
blockers: []
friction:
  - other:worktree-setup-misses-applications-tfvars
  - other:targeted-apply-splits-ephemeral-credential
  - other:corrected-one-clause-left-neighbour
worked:
  - other:falsifier-stated-before-evidence
  - other:live-proof-over-documented-proof
  - other:reviewer-remeasures-instead-of-rereads
harness_change: just worktree_setup should seed deployments/applications/vars/prod.tfvars and .devcontainer/.env, not only the infrastructure tfvars
review_cycles: 2
gates_red: 0
---

## What worked

**Stating the falsifier before running anything.** The plan forced the doc to
name the observation that would rule Path A out, up front. It nearly fired: the
first `creation_statements` produced a role Postgres would not drop and a
revocation that failed while reporting success. Because the falsifier was
already written down, that read as the spike doing its job rather than as an
obstacle to work around. A spike whose conclusion is fixed in advance would have
buried it.

**Proving it live rather than documenting it.** Every claim in the decision doc
is a captured command output. The two defects that cost the most time, the
ownership failure and the credential desync, are both invisible to
`terraform validate` and to any amount of reading. Neither would have been found
by a paper spike, and both are exactly what R3 would have hit at production
scale.

**Reviewers that re-measure instead of re-reading.** The adversarial pass minted
its own credential, ran the grant test itself, diffed the two tree objects to
confirm scope, and copied the Terraform root to scratch to prove
`replace_triggered_by` fires on a version bump. It also found live corroboration
I had not cited: Vault's identity store holds both the denial run and the real
run with their distinct roles and timestamps. Verdicts grounded in fresh
measurement caught things a reading-based review would have accepted.

## What worked less well

**`just worktree_setup` only seeds the infrastructure root.** This ticket lives
in `deployments/applications`, whose `vars/prod.tfvars` is gitignored and was
therefore absent in the worktree, as was `.devcontainer/.env` carrying the
`CONSUL_TOKEN` the Consul backend needs. Both were copied by hand. Any future
ticket touching the applications root hits this. The recipe should seed both
roots and the env file.

**Targeted applies silently split the write-only credential chain.** Applying
`postgresql_role` in one `-target` run and the Vault connection in the next gave
them different passwords, because an ephemeral value is regenerated per run and
persisted nowhere. `verify_connection` caught it as `failed SASL auth`, which was
luck in the sense that a weaker design would have failed later and more
confusingly. The lesson generalizes past this ticket: any resource that WRITES a
write-only attribute, whether newly created or version-bumped, must apply
together with every other consumer of the same ephemeral value.

**I fixed one overclaim and left its neighbour standing.** The doc's lead
claimed "No password in Terraform, none in Vault KV2, none on disk". The
documentation reviewer caught the KV2 half, since the change writes the minting
admin's password to KV2. I corrected that clause and shipped the sentence with
"no file" still in it, which the next cycle caught: the credential is rendered
to `secrets/db.env` exactly as today's static passwords are. Correcting a
flagged clause without re-reading the whole claim cost a review cycle. Both
review cycles went on the summary prose, not on the engineering.
