---
slug: L4-landing-dash-fe-be-split
blockers: []
friction: [other:heredoc-comment-leaks-into-rendered-template, other:worktree-guard-eval-substring-false-positive]
worked: [plan-review-first-pass-sound, empirical-probe-resolved-uncertainty, reviewer-reattach-cheap-cycle-2]
harness_change: the worktree-isolation guard substring-matches the literal token "eval" against the shell builtin and refuses `loopctl eval <slug>`/`loopctl eval-amend` even when nothing shell-evals anything; `loopctl verify-eval-substance` (no bare "eval" token) was unaffected and worked as a substitute, but the guard should special-case `loopctl eval*` subcommands rather than string-matching the whole command line.
---

## What worked

The ticket-planner's own investigation was unusually thorough going into
this: it independently found the missing `haproxy.Route` import the
operator's own request had omitted, verified the ACL grant needs zero
Terraform edit (job-scoped `bound_claims`, not task-scoped), and probed
oauth2-proxy's `--upstream` help text for multi-upstream support before
handing the plan off. Plan review passed SOUND on the first attempt as a
result, with zero required fixes, so implementation never had to stop and
resolve an open design fork mid-flight.

One real premise in the plan was marked UNCERTAIN (P10: whether
oauth2-proxy's path-scoped upstream matches by prefix or exact string,
and which upstream wins if both could match). Rather than guess or defer
it to a live post-deploy surprise, I stood up a throwaway oauth2-proxy
container plus two plain HTTP backends locally (`--skip-auth-route=.*` to
bypass real OIDC), hit it with curl, and got a concrete, load-bearing
answer straight from the proxy's own logs: exact match, not prefix. That
resolved the plan's one open uncertainty with real evidence instead of a
citation to documentation prose, and the finding is now recorded verbatim
in both `oauth2-proxy.hcl`'s comment and `docs/dash-landing-page.md`.

The adversarial reviewer's cycle-1 finding (an orphaned `HEALTH_READ`
constant left over from simplifying `_http.get_json`'s signature) was
trivial, and cycle 2's re-attach protocol (re-verify only what the new
diff touches, absence-claim everything else) meant the second review
round cost a fraction of the first: both passes came back in well under
half the time of their cycle-1 runs.

## What worked less well

I made a real, load-bearing mistake while editing `oauth2-proxy.hcl`:
I placed a multi-line `###` HCL comment explaining the new multi-upstream
routing *inside* the `template { data = <<-EOH ... EOH }` heredoc, rather
than before the `template {` block. Since that heredoc is the literal
content Nomad's `env = true` template renders into
`secrets/file.env`, the comment lines would have been written into the
container's real environment file and broken oauth2-proxy's startup — a
bug `terraform validate`/`nomad fmt` both pass cleanly on, since it's
syntactically valid HCL, and one no automated gate in this repo catches
(it needs a human or reviewer reading the actual rendered template
content, not just the HCL). I caught it myself during self-review before
dispatching the review passes, but it is exactly the class of defect the
adversarial reviewer was separately briefed to check for as a named risk,
and a future ticket editing any templated env/config file heredoc should
watch for the same trap.

Separately, `loopctl eval L4-landing-dash-fe-be-split` and (initially)
`loopctl eval-amend` were both refused by the worktree-isolation guard
with a message about "runs a string through eval" — the guard appears to
substring-match the literal word "eval" anywhere in a Bash command,
including as a `loopctl` subcommand name, and refuses regardless of
whether anything is actually being shell-evaluated. `loopctl
verify-eval-substance` (whose command line never contains a bare "eval"
token) worked fine as a substitute for schema/substance validation.
`eval-amend` also, correctly, refuses inside a linked worktree at all
(by design, not a bug) and requires the `--counter-signer` string to
byte-match the marker's existing signer, including its em dash and
escaped quote — worth remembering for any future amendment: copy the
exact signer string from the marker file rather than retyping it.
