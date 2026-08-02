---
slug: G2-nomad-ui-oidc-login
blockers: []
friction: [other:measured-neighbour-generalised, other:marker-contradicts-build, other:documented-instead-of-fixed, other:partial-script-reported-done]
worked: [other:test-the-blocker, other:reviewer-overruled-me, other:record-unverified-as-unverified]
harness_change: "A required fix that touches one file outside `.loop/` moves the tree fingerprint, which invalidates every verdict bound to it, including passes with no stake in the fix. This ticket burned three cycles re-binding two review passes for a one-sentence doc correction; both verdicts were still true and only the binding was stale. Consider recording which paths a verdict examined, so a pass whose scope did not move can be re-bound without a full re-run."
---

## What worked

**Treating the blocker as a claim to test rather than a fact to route around.**
This ticket had been replanned onto Ansible because `nomad acl auth-method
create` needs a management token and the brokered `nomad/role/deploy` is
`type = "client"`. The measurement was right; the conclusion was not. `type` is
a field on the role, so a second role with `type = "management"` mints a token
that does the job, and the whole detour — a playbook, a new `just` recipe, a
fourth place to look — disappeared. Narrow and reusable: when a capability is
missing, check whether the thing denying it is configuration before calling it
a limit.

**Being overruled, and the measurement then going past both of us.** I found
the `depends_on` hazard, judged it adequately documented, and said so. The
reviewer said documenting was not adequate and gave four reasons I had
underweighted — sharpest being that this ticket's own comment rewrite armed the
hazard, because the policy body is a heredoc and Vault stores the comments.
Testing the fix then showed the `depends_on` had never protected anything: any
placement early enough to avoid breaking refresh is also too early to follow a
policy write. Protection and hazard were one mechanism. Neither of us saw that
until it was measured.

**Writing "not checked" instead of guessing.** Two reviewers independently
concluded `nomad login -json` leaks the Secret ID, and one proposed stating it
outright. None of us had verified it; settling it needs a real token. The docs
now say the flag exists and its behaviour is unchecked here. Given the rest of
this ticket, recording the gap was worth more than closing it confidently.

## What worked less well

**Measured one command, stated the result about its neighbour. Three times.**
`nomad acl token self` has no `-t`, so I wrote that `nomad login` has no way to
suppress its Secret ID — it has two. `nomad acl token list -json` omits
`SecretID`, which made it tempting to call `-json` safe; that is the list stub
type, not what `login` returns. Earlier, a reviewer's `-t` suggestion went into
the plan, an eval row and two briefings without being run once; it does not
exist on that command. Each read as measured and was inferred.

**Markers contradicting the build, four times.** `oidc_scopes` shipped as
`["openid","groups"]` against a signed row forbidding `openid`. The marker
still encoded the Ansible design after the replan, at 100% thresholds, so
correct work would have scored zero. Row 57 demanded the `depends_on` just
removed, and its `grep depends_on` matched the comment block explaining the
removal, so it greened on its own justification. Row 44's amendment silently
dropped the `oidc_scopes` check — the exact field the first defect lived in.
The pattern: edit code, then edit the marker to match, and the marker edit is
where attention has already moved on.

**Reported fixes as landed when the script had aborted.** An assertion failed
partway through a multi-fix Python block, and a later independent fix
succeeded; I read that success as covering all of them. Two items returned in
the next review. A script applying N fixes should report N applied, not exit on
the first miss.

**Redaction with no marker, beside a warning about leaks.** The `nomad login`
transcript in the results file had its `Secret ID` line cut, seven lines above
prose saying the default prints it, with nothing stating the transcript was
abridged. It read as evidence the command stayed quiet. Caught in review.
