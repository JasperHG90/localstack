---
slug: F11-foundation-human-read-role
blockers: []
friction: [other:plan-before-measure, other:unverified-citation, vacuous-tests, other:missed-existing-recipe]
worked: [other:measure-then-write, other:probe-both-directions]
harness_change:
---

## What worked

**Measuring before writing.** The final plan was built by standing up candidate
policies against the live cluster and running both Terraform roots under them
until they stopped 403ing. Every claim derived that way survived review; the
implementation then applied first try and the eval probes passed without a
single adjustment. Nothing measured was ever overturned.

**Probing denials as well as grants.** The escalation probes — policy write,
auth enable, entity-with-root, token-with-root — turned "this policy looks
narrow" into a statement about what it actually refuses. They also produced the
honest finding that this is *not* a boundary, which is now written into the
policy comments and the docs rather than quietly implied.

**Verifying live rather than trusting exit codes.** The apply test compares
mount descriptions read back from Vault against the config, not `terraform`'s
exit status. That is the only reason the auth-mount tune grant is right: the
provider swallows a denial there and reports success.

## What worked less well

**Three grants existed that no code review could have found**, and each cost a
review cycle: `auth/token/create` (the provider mints a child token on first
use and `default` does not grant it), `sys/mounts/secret/tune` and
`sys/mounts/auth/userpass/tune` (mount paths are exact-match and do not cover
their own tune subpath), and `sudo` on the `sys/auth/` tune form. The last one
was first measured against the *CLI's* endpoint rather than the provider's, so
the grant looked correct and was wrong. Deriving a Vault policy by reading
`vault_*` resource blocks does not work; only running the root does.

**Writing the plan before measuring it, then measuring to defend it.** Earlier
passes produced ~250 lines of prose per revision, and each revision's new
sentences were new unverified claims. Two reviews said in those words that a
pass introduced worse defects than it fixed. It converged only once rewritten
from measurements outward and cut to roughly half its length.

**Citations asserted from memory.** A claim about another ticket's content was
written without opening that ticket, and was wrong. Separately an ownership
claim was generalised from one system to another without checking the second.
Both read as coherent and were caught only by review.

**Eval rows that could not fail, or failed correct work.** Checking `policies`
when group binding puts the answer in `identity_policies`; asserting a denial
on `sys/raw`, where the negative control cannot succeed either because the
endpoint is disabled cluster-wide. A row needs a control that passes before it
proves anything.

**I reported a harness defect that was already solved.** `just pre_commit`
failed in the linked worktree because `services.tf:290` resolves an SSH key
relative to the repo root, so I symlinked `.ssh` in by hand and wrote it up as
an incompatibility between worktree isolation and this repo's gate. The root
`justfile` already has a `worktree_setup` recipe that does exactly that, plus
the tfvars copy I had not thought about. Found it while implementing D1. The
lesson is narrower than the one I first drew: before declaring a tool broken,
grep its own task runner for the fix.

**A probe left drift on the live cluster.** Testing tune permissions with
`vault write` changed two real mount descriptions, caught only when a reviewer
noticed the root no longer planned clean. Probes that write must restore what
they overwrote in the same command.
