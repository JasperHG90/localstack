---
type: verdict
title: 'Verdict: ci-tailscale-access reviewer round 1'
description: 'reviewer verdict for round 1 of ci-tailscale-access: fix.'
tags:
- verdict
- review
generated:
  by: claude-opus/5.5
  at: '2026-11-15T22:23:16+00:00'
slug: ci-tailscale-access
pass: reviewer
round: 1
body_schema: verdict/1
---

## Summary

The change does what the plan says, and I found no defect that would ship.
The action passes inputs only through env, masks the JWT and the Vault token
before anything writes them out, and fails when no token comes back. The
Vault role has the same shape as spike 2's working role. The tailscale pin
is v4, and the guard tests assert their rows. What is left is two small gaps
in the how-to and one hardening note, none of which needs another look from
me.

## Checked

- `loopctl gate stamp` from the worktree: every gate passed (pre_commit,
  cli_tests, rows r1 to r5). Stamp green
  `81dfe0a13ad615f7e75d8d759a1d57bec030a6a04ce92eb608a29eb9df79dd03`.
- Pin: `gh api repos/tailscale/github-action/git/matching-refs/tags/v4`
  shows `refs/tags/v4` and `v4.4.0` both at
  `064b10558093f38325e838ddea35486bdc6b1d5c`. At that SHA its action.yml has
  the inputs `oauth-client-id`, `audience`, `tags` and `args` (default empty).
- Action security: no `${{ }}` in the run script, and vault-addr, vault-mount
  and vault-role come in through env. The OIDC request is
  `$ACTIONS_ID_TOKEN_REQUEST_URL&audience=vault.io` with the bearer request
  token, and a guard fails early when id-token permission is missing. The JWT
  is masked right after it is fetched. The Vault error path prints only
  Vault's error body. `jq -e` with `// empty` fails when no client_token
  comes back. The token is masked before the GITHUB_ENV and GITHUB_OUTPUT
  writes.
- Vault role against spike 2 (`files/vault_bind.sh`, stdout): it has the same
  discovery URL and bound_issuer, `role_type` jwt, `user_claim` repository,
  `bound_claims_type` string, and the four claims. workflow_ref is built as
  `<repo>/.github/workflows/<file>@<ref>`, the format spike 2 recorded. The
  audience is vault.io, the TTL is 300 s and the max TTL 600 s.
- r1: the test renders the role body through `terraform console` and asserts
  exact bound_claims, the audience, string type and a TTL under 3600 s. It
  also refuses any other role on the mount. r2: it finds every workflow job
  that uses the action and asserts no pull_request or pull_request_target
  trigger, plus environment, timeout-minutes and id-token write. r3: it
  refuses secret, key, token or password input names and any `secrets.`
  reference. The `with:` keys must be exactly oauth-client-id, audience and
  tags, args must be empty, `--accept-routes` must not appear, the audience
  must be only vault.io, and the mask must come before every export. r4:
  exact default list. Each test fails on its row's fails_when. The eval's
  wording "oauth-client-id, audience" names the tailscale action's inputs,
  which the test pins; the lab-auth inputs are tailscale-client-id and
  tailscale-audience, as the plan says. These agree.
- lab-auth-check: treating a refused connection as FAIL is right. The
  tailnet filter drops packets silently, so a RST means the packet passed the
  policy and reached a host. A connection that cannot be made at all also
  counts as FAIL, which errs on the safe side. The reach checks need a TLS
  answer (curl code 000 fails), so they also check the certificate.
- r6: cannot be shown yet. It needs the operator to apply and push, then a
  dispatch on main and a refused dispatch from a branch.
- r7 (judged): the only identifiers committed are the federated client ID and
  audience, which are useless without a GitHub-signed token matching the
  subject. No secrets input, and claude-ollama.yaml has no actions:write, so
  it cannot dispatch lab-auth-check.
- r8 (judged): ADR 0027, the subnet-router page (its policy copy matches the
  handoff's description: tagOwners, both grants, the default ssh rule, the
  tests block), vault-identity (the mount, the bindings, the TTLs, MFA on the
  userpass accessor only, confirmed in identity.tf:121), the how-to (four
  sections, numbered steps, the immutable-subject step with a real API check;
  `use_immutable_subject` exists in the response, checked against this repo)
  and the reference inputs table match action.yml. Apart from f1 and f2,
  these pages agree with the code.
- Terraform layout: no new .tf file. The mount and roles are in
  machine_roles.tf and the variable in variables.tf.

## Findings

- f1 (docs, non-blocking): Step 4's snippet should show the
  `tailscale-client-id` and `tailscale-audience` overrides for an
  immutable-subject repository, or Step 2 should give the snippet line.
- f2 (docs, non-blocking): link each prerequisite, per the how-to skeleton
  rule.
- f3 (hardening, non-blocking): make the JWT extraction fail on a missing
  value instead of passing the string null along.

## Notes

The summary.md rewording outside the new bullet keeps it near the 500-word
limit, and log.md records it.
