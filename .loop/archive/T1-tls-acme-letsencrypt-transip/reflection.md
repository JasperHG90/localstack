---
slug: T1-tls-acme-letsencrypt-transip
blockers: []
friction: [other:cli-version-drift-in-plan, other:double-template-dollar-escaping, other:positional-eval-row-reference, other:prose-lags-code-fix]
worked: [other:run-the-binary-not-the-docs, other:negative-controls-on-every-check, other:reviewer-resume-keeps-context]
harness_change: A ticket whose remaining findings are prose-only has no way to land them at the review cap; either exempt fingerprint-irrelevant files or allow a documentation-only cycle that does not count.
---

Review cycles: 3 of 3, all consumed. Gates red: 0. Blockers: none. Nothing
applied; the nine live eval rows are pending an operator run.

## What worked

**Running the binary instead of trusting the plan.** The plan specified a lego
invocation that does not exist in the pinned version: v5 has no `renew`
command and every flag I passed as a global is a `run` option. Both branches
of the command would have died at argument parsing on the operator's first
apply. The reviewer found it by executing the rendered shell in the image, and
I confirmed it the same way rather than by reading. The fix was better than a
patch: every flag has a `LEGO_*` environment equivalent, so the invocation
collapsed to `args = ["run", "--renew-days", "30"]` and the shell wrapper
disappeared along with its whole class of escaping bugs.

**Negative controls on every check.** `haproxy -c` exiting 0 means nothing
until a missing cert and a bogus keyword both exit 1. The store shell picking
the right file means nothing until an empty directory exits non-zero. Running
lego with `--network none` proved the arguments parsed, because the failure
arrived at the socket rather than at the flag parser. Each of these turned a
green result into evidence.

**Resuming one reviewer across four cycles.** It kept the prior tree
fingerprints and diffed against them, which is how it could state "the
rendered jobspec is byte-identical to cycle 3" rather than re-deriving. On the
last two cycles that let it verify the *absence* of behavior change, which is
exactly the claim that is tedious to prove and easy to assert.

## What worked less well

**The plan encoded a CLI that had moved.** The plan was written the same day
against remembered flags, and every downstream artifact inherited the error:
the jobspec, the eval marker's row 4 text, and a comment. Discovering it cost
a full review cycle. Checking `--help` in the pinned image takes one command
and would have prevented all of it.

**Two template layers, two different dollar-escaping rules.** Terraform's
`templatefile` escapes a doubled dollar only when a brace follows, so a lone
doubled dollar survives as two characters that the shell reads as its PID.
Nomad's HCL then interpolates brace expressions again, so a shell brace
expansion cannot survive both layers at once. I hit both live. The durable fix
was to stop escaping and restructure: `basename` instead of a brace expansion,
environment variables instead of an argument string. A comment explaining the
escaping also broke the template, because it contained the literal sequence it
was describing.

**A positional reference in the eval marker went silently wrong.** The
rate-limit guard said "production is blocked until row 4 passes on staging".
Inserting a row above it retargeted the guard onto the publicly-trusted-issuer
check, which cannot pass on staging by definition. The precondition protecting
against a week-long issuance lockout had quietly become unsatisfiable, and it
took the reviewer two cycles to spot because the row it now pointed at still
read plausibly. Reference rows by title.

**Prose lagged the code fix twice.** I corrected the "does not contact the CA"
claim in the jobspec comment and left the identical claim in the doc, which is
the copy an operator reads at 04:30 with a red allocation. The reviewer had
cited both locations in the same finding. Fixing the instance rather than
every instance of a wrong claim is how a document ends up disagreeing with the
code it documents.

**The cap and prose findings interact badly.** The last cycle closed with a
correct, non-blocking finding about the doc describing future state in present
tense. With 3 of 3 cycles consumed, acting on it would have staled the verdict
and forced a block over a verb tense, so it goes to the ticket that already
owns the file. That is the right routing here, but a documentation-only cycle
should not have to compete with behavioral ones for the same budget.
