---
slug: D10-cli-broker-nomad-manage
blockers: []
friction: [other:respx-recall-resets-mock, other:verdict-citation-comma-nulls-scope-digest]
worked: [other:plan-was-precise-and-implementable-as-written, other:doc-review-caught-real-security-gap]
harness_change: warn (or hard-fail) at verdict-write time when a citations: line's quoted text contains a comma, since _split_list_field silently shreds it into a bogus out-of-scope citation and nulls the whole pass's commit-authorizing digest -- this has now bitten two different reviewer-agent instances across two tickets tonight
---

## What worked

The plan was precise enough to implement directly: every Code surface bullet
named an exact line and an exact change, and the eval was already signed off
by the operator, so this ticket needed no design judgment calls at all. The
adversarial review passed clean on the first cycle. The documentation review
earned its keep: it caught a real, security-relevant gap in
`docs/vault-human-auth.md`'s incident-response runbook, whose manual
token-deletion procedure only named one Nomad accessor to revoke when this
ticket makes a session mint two -- an operator following the old runbook
during a real incident would have left the more dangerous (`manage`) token
live. It also caught the same stale "still partial" framing repeated in two
other docs and ROADMAP.md, and a third instance in `docs/monitoring.md` that
survived the first fix round entirely.

## What worked less well

Two non-obvious bugs cost real time, neither in the ticket's own code.
First: three new tests called `respx.get(url)` a second time on an
already-mocked route purely to get a handle for asserting request headers.
`respx` resets that route's response to the unconfigured default (200, empty
body) whenever it is re-registered without a chained `.mock(...)`, which is
not obvious from its API and silently made three tests fail with a
connection-shaped error message. Fixed by filtering the global `respx.calls`
log by request path instead. Second: two review verdicts this cycle produced
a `scope:` digest the commit gate rejected as invalid, because their
`citations:` lines quoted verbatim source/prose text containing commas, and
the harness's own comma-based list splitter (`_split_list_field`) shredded
those into bogus extra "citations" outside the declared `bound_paths`,
nulling the digest. Fixed by dropping the optional `citations:` field from
both verdict files rather than rewrite every quoted line to avoid commas.
