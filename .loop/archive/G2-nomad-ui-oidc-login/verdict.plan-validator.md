---
verdict: pass
plan: c3e0ffa386c9e9ab6c471cdbb6ba0853770f2a3402961c6726c2015ee529b191
---

# G2-nomad-ui-oidc-login — narrow re-bind pass (plan-validator)

Fingerprint checked before binding: `sha256sum .loop/plans/G2-nomad-ui-oidc-login.md`
returns `c3e0ffa386c9e9ab6c471cdbb6ba0853770f2a3402961c6726c2015ee529b191`, which
matches the briefing.

Scope: the three findings the previous pass raised, plus a sweep for breakage.
The rest of the plan body and the items the prior pass already settled were not
re-walked.

## Premise verdict: SOUND

All three claimed fixes hold under measurement, not inspection. Two residual
observations are recorded below; neither is a required fix.

## Per assumption

**P1 — `nomad acl token self` has no `-t` and no `-json`, and the rejection is a
flag-parse error before any network call. HOLDS (measured).**
`nomad acl token self -h` lists only general options: `-address`, `-region`,
`-no-color`, `-force-color`, the TLS flags, and `-token`. No `-t`, no `-json`,
and no occurrence of "json" anywhere in the help text. Both flags were probed
against a dead local address (`NOMAD_ADDR=http://127.0.0.1:1`, never the live
cluster) and both returned `flag provided but not defined: -json` /
`flag provided but not defined: -t` with no connection attempt, confirming the
parse happens first. Local CLI is `nomad v2.0.3`; the cluster runs 2.0.4, and
the flag set for this command is the same in both (no `-json` was added).
Plan text at `.loop/plans/G2-nomad-ui-oidc-login.md:545-547` states exactly this.

**P2 — the replacement form `nomad acl token self | grep -E '^(Type|Global)'`
is runnable and does not print the Secret ID. HOLDS (measured, not assumed).**
Measured on a throwaway local Nomad server started in the scratchpad
(server-only, ACLs on, port 14646, its own `data_dir`; the live cluster was
never contacted, and the agent was stopped afterwards). Raw output, with UUIDs
redacted here:

```
Accessor ID  = <REDACTED-UUID>
Secret ID    = <REDACTED-UUID>
Name         = Bootstrap Token
Type         = management
Global       = true
Create Time  = ...
Expiry Time  = <none>
Create Index = 8
Modify Index = 8
Policies     = n/a
Roles        = n/a
```

The same output through `grep -E '^(Type|Global)'` yields exactly two lines,
`Type         = management` and `Global       = true`. The anchor drops
`Secret ID` and `Accessor ID`, and no other field label starts with `Type` or
`Global`. So the plan's two claims both check out: the bare form does print the
Secret ID in full, and the filtered form shows what subticket 2 asks the
operator to confirm and nothing sensitive
(`.loop/plans/G2-nomad-ui-oidc-login.md:547-548`).

**P3 — no `token self -<flag>` survives in `.loop/plans/` or `.loop/evals/`.
HOLDS.** `grep -rn "self -t\|self -json\|token self -" .loop/plans/ .loop/evals/`
returns zero matches. The surviving mentions are the corrected prose at
`.loop/plans/G2-nomad-ui-oidc-login.md:545-548`, the bare form in the measured
transcript at `:277`, the bare form in eval rows 43 and 53, and a prose mention
in `.loop/plans/F8-foundation-deployer-provider-cutover.md:518`. Your grep was
right.

**P4 — eval:59 no longer contradicts eval:52, and the gate it scores is
otherwise unchanged. HOLDS.**
`.loop/evals/G2-nomad-ui-oidc-login.md:59` now reads "This change is Terraform
only" and names `deployments/infrastructure/nomad_oidc.tf`. The word Ansible
appears nowhere in it. Line 52 asserts one declaration each of
`nomad_acl_auth_method` and `nomad_acl_binding_rule` under that same file with
`bootstrap/` untouched, so the two agree. The only Ansible references left in
the eval are the policy-ownership ones at `:5`, `:51` and `:52`, all correct.
The gate itself is unchanged and real: Input is still `just worktree_setup
<path>` then `just pre_commit` (`justfile:30` and `justfile:18`), Scorer and
Threshold are untouched, and the claim about what bites is accurate —
`.pre-commit-config.yaml:22-32` defines `terraform-fmt`
(`terraform fmt -check -recursive`) and `terraform-validate`, both with
`types: [terraform]`.

**P5 — eval:57 now discriminates. HOLDS for both named failure modes
(simulated).** Built three variants in the scratchpad from the file layout the
plan specifies and ran the row's three greps against each:

| build | `type = "management"` | `depends_on` | `nomad/creds/manage` |
|---|---|---|---|
| correct | 1 | 1 | 1 |
| missing `depends_on` | 1 | **0** | 1 |
| missing the policy grant | 1 | 1 | **0** |

So a build omitting the `depends_on` reds grep 2, and a build omitting the grant
reds grep 3. The grant grep is genuinely vacuous today: `developer_group.tf`
carries `nomad/creds/deploy` at `:123` and a comment naming `nomad/creds/*` at
`:121`, but no `nomad/creds/manage` anywhere, so the string can only appear if
the implementer adds it. The row's targets match what the plan says will be
written (`.loop/plans/G2-nomad-ui-oidc-login.md:296` for the role, `:318` for
the `depends_on`, `:330-332` for the grant).

**P6 — table integrity survived the edits. HOLDS.** All 20 table lines
(`.loop/evals/G2-nomad-ui-oidc-login.md:40-59`) split to exactly 7 fields on
`|`, and the count of escaped pipes is 0. No new contradiction between rows 52,
57 and 59, and row 56 (README, zero `nomad_oidc` matches) is untouched by these
edits and does not collide with 59's naming of the file.

## Most dangerous assumption

P2, the replacement command. It is the one an operator will actually type, it
replaces a form that was propagated from an advisory without ever being run, and
a second wrong replacement would have shipped a Secret ID into a terminal
transcript. It was measured end to end rather than reasoned about, and it holds.

## Observations (non-blocking, no fix required)

1. **`grep -n 'depends_on'` in eval:57 is unanchored to the resource.** A build
   that omits the `depends_on` on the `vault_nomad_access_token` data source but
   carries one on some *other* resource in `nomad_oidc.tf` still matches the
   grep. Simulated: a decoy build with the data source's `depends_on` removed and
   `depends_on = [vault_identity_oidc_client.nomad]` added to the auth method
   still produces a hit. The row survives it in practice, because the grep prints
   the line and its target list, and the Expected column names the required
   target (`vault_policy.developer`), so a scorer reading Expected sees the wrong
   target. Only a `depends_on = [vault_policy.developer]` placed on the wrong
   resource would be invisible, which is contrived; nothing else in that file
   plausibly depends on that policy (`.loop/plans/G2-nomad-ui-oidc-login.md:318`
   is the sole `depends_on` the plan specifies). Tightening the grep to
   `depends_on = \[vault_policy.developer\]` would close it if you want it shut.
2. **eval:59's file enumeration is incomplete, not wrong.** It lists the Vault
   client, the assignment, the management role and both Nomad ACL resources as
   living in `nomad_oidc.tf`, all of which is true, but the change also appends
   the `nomad/creds/manage` grant to `vault_policy.developer` in
   `developer_group.tf` (plan `:543`, `:330-332`; required by eval:57). Nothing
   contradicts, and the gate is per-root so the scoring is unaffected — a reader
   should just not take the sentence as the complete file list.
3. **The eval file is not covered by the bound fingerprint.** The plan does not
   embed the eval table, so `.loop/evals/G2-nomad-ui-oidc-login.md` can change
   without changing the hash this verdict binds. That is a standing property of
   the harness, not something this pass introduced; noting it so the binding is
   not read as stronger than it is.

## Required fixes

None.
