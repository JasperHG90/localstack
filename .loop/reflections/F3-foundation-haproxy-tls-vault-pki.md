---
slug: F3-foundation-haproxy-tls-vault-pki
blockers: []
friction: [other:worktree-missing-gitignored-inputs, other:worktree-dir-not-gitignored, other:cwd-drift-between-loopctl-calls]
worked: [other:offline-binary-validation, other:image-inspect-before-deploy, other:reviewer-resume-keeps-context]
harness_change: implement-ticket should seed a fresh worktree with the repo's gitignored gate inputs, or the first gate run fails on environment rather than on code.
---

Review cycles: 2. Gates red: 1 (environmental, not code — see below). Blockers: none;
all six design forks were pre-resolved by the operator in the plan, so implementation
never had to stop on a fork.

## What worked

**Validating the rendered artifact offline with the real binary.** The ticket's top
risk was that a broken frontend rewrite takes the whole edge down, and the repo has no
test harness for infra HCL. Extracting the config template, substituting the Terraform
var, and running `haproxy -c -f` inside `haproxy:3.1-alpine` turned an untestable
change into a checkable one. Running two negative controls first (missing cert file,
bogus directive — both exit 1) mattered as much as the positive result: exit 0 means
nothing until you have shown the check can fail.

**Inspecting the container image before deploying to it.** `docker inspect` revealed
`USER=haproxy` (uid 99), which is what made an intended-as-careful `perms = "0600"` an
outage: Nomad renders templates as the agent user, so the process could not have read
its own key. Cheap to check, and the failure mode would have been a dead edge rather
than a caught error.

**Resuming the reviewer instead of respawning it.** Cycle 2 went to the same agent via
SendMessage, so it already knew the ticket and could focus on whether the two fixes
did what was claimed. It finished in ~4 minutes against ~16 for the cold pass, and it
retested the wildcard after `allow_localhost = false` — a regression I had not thought
to check, since Vault's localhost and allowed-domains branches share a validation loop.

## What worked less well

**A fresh worktree lacks the repo's gitignored gate inputs.** `.ssh/id_rsa` and
`vars/prod.tfvars` are both gitignored, so `git worktree add` produces a tree where
`terraform validate` fails on a missing SSH key before it evaluates any of the code
under review. The first gate run reported red for a reason that had nothing to do with
the change. Fixed by symlinking `.ssh` and copying the tfvars in — both gitignored, so
neither touches the diff or the fingerprint — but this will recur on every ticket in
this repo that reaches the Terraform gates.

**`.loop/worktrees/` is not gitignored here.** The implement-ticket protocol states it
is, and the stamp fingerprint excludes `.loop/` so nothing broke, but the primary
checkout carries an untracked `.loop/worktrees/` for the life of the ticket. Left
alone deliberately: adding the line would have been a change tracing to the harness
rather than to the ticket. Worth fixing once, outside a ticket.

**cwd drift between loopctl calls.** A `cd deployments/infrastructure` in one Bash call
persisted into the next, and loopctl then failed with a bare `KeyError` on the slug
because it was resolving a ledger from the wrong root. The error named the slug, not
the real cause. Anchoring every loopctl invocation with an absolute `cd` avoids it.
