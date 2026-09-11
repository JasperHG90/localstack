---
slug: gcs-backups-doc-to-runbook
blockers: []
friction: [vacuous-tests, other:batch-discretionary-fixes]
worked: [other:reviewer-ran-the-mutations, other:operator-overrode-the-defer]
harness_change:
---

## What worked

The operator overruling my "follow-up ticket" proposal. I had offered to defer
the reframing on scope grounds, and the file was already on the previous
ticket's code surface with four false claims fixed in it that week. The
deferral would have left a document that invites nobody to re-check it.
Reading it properly turned up a fifth false claim within minutes.

Both reviewers ran mutations instead of reasoning about the tests. That is
what caught the real defect: my assertion compared the jobspec side keyed by
task against the doc side as plain membership in the whole section, so
swapping `pgdump` and `upload` figures inside one section stayed green. Those
two are the exact pair that drifted historically. Reading the test would not
have found it; running a swap did, in one command.

Probing the ACL rather than assuming. `nomad job status` shows both jobs
registered, which reads like confirmation until the children query returns
403. That single probe is why the document now says what nobody can confirm
instead of asserting nightly success, and it changed a requirement rather than
a sentence.

## What worked less well

Two of my own tests were vacuous in ways the green bar hid. The `constraint`
regex used a `[^}]*` span that died on `${attr.unique.hostname}`'s brace, and
`_doc_section` stopped only at `##`, so each job was checked against the other
job's facts. The self-check caught the first loudly. Nothing caught the second
except running negative controls, which is the only reason to write them.
Drift tests that cannot be shown to redden are decoration.

Three review cycles again, for the same reason as the previous ticket: I
applied fixes in the order I found them instead of batching. Cycle 3 existed
for two one-line edits. The rule is now obvious in hindsight and worth
stating: collect every finding from every pass, apply them in one edit, stamp
once, re-dispatch once.
