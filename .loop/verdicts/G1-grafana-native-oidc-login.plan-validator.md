---
verdict: pass
plan: 0574f8a141b40982b75b88b0de818053db4249d4337ff96f23b8a5708c673fba
---

# Plan review, fifth pass: G1-grafana-native-oidc-login

## Premise verdict: SOUND

Both fourth-round fixes are applied and both hold. The two questions this pass
was called to settle both come back clean: row 2's method is runnable, and it
cannot be fooled by Grafana synthesizing an email. No new defect. The plan is
ready to leave `PLANNING`.

## Deterministic floor

`loopctl verify-plan G1-grafana-native-oidc-login` returns `valid`, with only
ambiguous-basename warnings (`secrets.tf`, `services.tf`, `providers.tf`,
`variables.tf` each match several files in the repo). No hard fail. The
`pkg/services/org/model.go:147` reformat that hard-failed last round is gone
and the checker is green.

Plan fingerprint on disk matches the briefing:
`0574f8a141b40982b75b88b0de818053db4249d4337ff96f23b8a5708c673fba`.

## The headline question: can row 2 be fooled?

**No. There is no synthesis path.** This is the strongest evidence in the
review, so it is worth stating exactly.

Grafana 11.5.2 resolves an email through `extractEmail`
(`pkg/login/social/connectors/generic_oauth.go:422-450` at the `v11.5.2` tag),
which has exactly four sources and then gives up:

1. `data.Email`, the raw `email` claim from the id_token or the userinfo JSON.
2. `s.emailAttributePath`, **only if set**. It ships empty
   (`conf/defaults.ini:850`, `email_attribute_path =`) and this ticket does not
   set it.
3. `data.Attributes[s.emailAttributeName]`.
4. `data.Upn`, and only when `mail.ParseAddress` succeeds on it
   (`:441-447`). A `sub` UUID does not parse, so it is rejected.
5. Otherwise `return ""`.

`fetchPrivateEmail` is gated on `canFetchPrivateEmail` (`:358-360`), which is
`ApiUrl != "" && userinfo.Email == ""`. It GETs `<api_url>/emails` (`:520`), a
path Vault does not serve, and returns the error rather than swallowing it
(`:328-334`), which kills the login.

Then `pkg/services/authn/clients/oauth.go:164-166` refuses outright:
`required attribute email was not provided`.

The one fallback that does exist runs the **other** way:
`userInfo.Login = userInfo.Email` (`generic_oauth.go:337-340`). Login falls back
from email. Email never falls back from login, sub, or username.

So with the configuration this plan mandates, the `email` in `GET /api/org/users`
is the Vault `email` claim verbatim. The row asserts the thing it claims to
assert.

**Runnable, confirmed live.** `GET /api/org/users` against
`http://192.168.2.47:3000` returns `401` unauthenticated and
`{"messageId":"password-auth.failed"}` with a wrong basic-auth password, so the
route and basic auth are both live. `org.OrgUserDTO` carries `Email` with json
tag `email` (`pkg/services/org/model.go:147`) and `Role` (`:151`), so one
response feeds both rows. Grafana reports `"version":"11.5.2"` on
`/api/health`.

**One honest caveat, reported and not gated.** The row's stated failure signal,
"a blank ... email there", describes a state that cannot occur. Grafana refuses
the login before any user is created, which the plan itself establishes at P11
and Q4(a). The observable failure is that there is **no SSO user in the list at
all**. The check still fails correctly in that case, because "present and
non-empty" is false when the user is absent, so the row works. Only the
explanation of how it fails is slightly off. Related: row 2's line "without it
every other row can pass while the login is broken" is no longer true, since a
missing email claim also fails row 1. That sentence is a leftover from before
the first review killed Q4 route (a) and made an email mandatory. Neither
misstatement makes the row unrunnable or wrong, and both bias the marker author
toward keeping the row rather than dropping it, so neither is a required fix.

## Per assumption

Stated premises (the plan numbers them P1 to P11, P13, P14, P15, P12; all
fifteen are present, just listed out of order, which is cosmetic).

- **P1 HOLDS.** `curl http://192.168.2.47:3000/` returns `302` to
  `http://192.168.2.47:3000/login`. Probed this pass.
- **P2 HOLDS.** `deployments/infrastructure/services/grafana.hcl:48` pins
  `docker.io/grafana/grafana:11.5.2`; `/api/health` returns
  `{"database":"ok","version":"11.5.2","commit":"598e0338..."}`. Probed this pass.
- **P3 HOLDS.** `grafana.hcl:29` is `vault {}`; `:67-75` is the plain `env`
  block; `:77-84` is the `template { env = true }` block injecting
  `GF_SECURITY_ADMIN_PASSWORD`. Read this pass.
- **P4 HOLDS.** `grafana.hcl:70` is
  `GF_SERVER_ROOT_URL = "http://192.168.2.47:3000"`.
- **P5 HOLDS.** `secrets.tf:47-50` is `random_password.grafana_admin`;
  `services.tf:346-368` renders the job with `grafana_secret`.
- **P6 HOLDS.** `oidc.tf:95-101` sets `https_enabled = true`; the live discovery
  document returns
  `"issuer":"https://vault.lab.orangecluster.nl/v1/identity/oidc/provider/lab"`.
  Probed this pass.
- **P7 HOLDS.** Live discovery returns `"scopes_supported":["groups","openid"]`
  and `"claims_supported":[]`. Probed this pass, unchanged from the plan's
  2026-08-04 measurement.
- **P8 HOLDS.** `docs/vault-human-auth.md:447-449`: Vault "ignores an
  unsupported scope rather than erroring". `:300-306` records the same for
  `groups`, verified live 2026-07-31.
- **P9 HOLDS.** Live discovery returns
  `"authorization_endpoint":"https://vault.lab.orangecluster.nl/ui/vault/identity/oidc/provider/lab/authorize"`,
  a UI path. `docs/vault-human-auth.md:324-330` records the first-attempt
  failure.
- **P10 HOLDS.** `oidc.tf:80-84` lists smoke, nomad, memex, no Grafana.
  `nomad_oidc.tf:44-57` is a `confidential` client on
  `vault_identity_oidc_key.lab`, and `oidc.tf:134-149` is the smoke client, same
  shape. `memex_oidc.tf:53-57` carries the immutability warning the plan cites.
  All eight `memex_oidc.tf` mentions in the plan are negative or historical;
  nothing points there as the example.
- **P11 HOLDS**, all three parts re-derived from the `v11.5.2` tag this pass.
  No discovery (the connector reads `s.info.ApiUrl` directly,
  `generic_oauth.go:395-420`, never a well-known document). Email mandatory
  (`oauth.go:164-166`). Default scope list omits `openid`
  (`conf/defaults.ini:847`, `scopes = user:email`).
- **P13 HOLDS.** `oidc.tf:55-69` states the unquoted rule as general, not
  list-specific, and `oidc.tf:100` is the `scopes_supported` line the `email`
  scope must be appended to.
- **P14 HOLDS.** `haproxy.hcl:105` is the `is_grafana` ACL, `:116` the
  `use_backend`, `:149-150` the backend to `192.168.2.47:3000`.
- **P15 HOLDS.** `grafana.hcl:70` and `services.tf:364` both hold
  `http://192.168.2.47:3000`. `services.tf:364` is `grafana_external_url`, and
  its only consumer is `grafana.hcl:300`, the
  `<a href="${grafana_external_url}/alerting/list">Open Grafana</a>` link in the
  Telegram template. The plan describes this correctly.
- **P12 HOLDS.** `justfile:18` is `pre_commit:`, `:44` is `worktree_setup path:`.
  `.pre-commit-config.yaml:1` is `exclude: '^\.(claude|loop)/'`; `:12`
  `detect-private-key`, `:16` `nomad-fmt`, `:22` `terraform-fmt`, `:28`
  `terraform-validate`.

Implicit assumptions the two fixes introduce, added and attacked this pass:

- **I1 HOLDS.** `GET /api/org/users` exposes an `email` field.
  `pkg/services/org/model.go:147` at `v11.5.2`, json tag `email`. The plan's
  reworded citation is accurate.
- **I2 HOLDS.** The SSO-created user appears in the local admin's org listing.
  `conf/defaults.ini:492` `auto_assign_org = true` and `:495`
  `auto_assign_org_id = 1`, and nothing in `grafana.hcl:67-75` overrides either,
  so the SSO user lands in org 1 alongside admin. Had `auto_assign_org` been
  false, each new user would get its own org and both rows would read an empty
  list. It is not.
- **I3 HOLDS.** Grafana never synthesizes an email from login, sub or username.
  See the headline section.
- **I4 HOLDS.** A Grafana user with an empty email cannot exist.
  `oauth.go:164-166`. This is what makes row 2's "blank email" wording describe
  an unobservable state.
- **I5 HOLDS.** Local-admin basic auth survives OIDC being enabled. Probed:
  wrong password returns `password-auth.failed`, not a route error. Nothing in
  the job disables `[auth.basic]`.
- **I6 HOLDS.** Row 3's four-in-one probe works. `pkg/api/login_oauth.go`
  branches on `code == ""` into `RedirectURL` and issues
  `reqCtx.Redirect(redirect.URL)`; `oauth.go` builds that URL via
  `connector.AuthCodeURL(state, opts...)`, which emits `client_id`,
  `redirect_uri`, `response_type` and `scope`. Live, `/login/generic_oauth`
  already returns `302`.
- **I7 HOLDS.** Both recorded dead routes are genuinely dead. `oidc-smoke`'s
  redirect is `https://vault.lab.orangecluster.nl/ui/vault/auth/oidc/oidc/callback`
  (`variables.tf:64-68`) and the client is `confidential` (`oidc.tf:140`). The
  `id_token` is unreachable: live discovery returns
  `"response_types_supported":["code"]`, and the signout `id_token_hint` path
  returns early when `signout_redirect_url` is empty (`oauth.go:281-285`;
  default empty in `conf/defaults.ini`).

## Rows 2 and 7 sharing one request: no ordering or state problem

- The shared call is a read-only `GET`. It mutates nothing, so running it once
  for both rows or once per row is equivalent. No coupling is created.
- Neither row gains a new ordering constraint. Both already depended on row 1:
  row 2 says "After completing the SSO login", row 7 says "the user created
  through the OIDC login".
- Org scoping is safe (I2), so the admin's listing contains the SSO user.
- Row 4 (the local-admin fallback sign-in) cannot interfere. Basic auth is
  stateless per request.
- Row 7's note that the role re-syncs on every login means an intervening login
  between the two reads cannot desync them.

## Are the seven rows enough to author the marker from?

Yes. Every part of the change surface maps to a row: both root-URL copies to
rows 3 and 6; the client and its `local.oidc_provider_client_ids` entry to rows
1 and 3, since Vault refuses the authorize request without it; `scope`
containing `openid` to row 3; the `email` scope and the claim arriving to rows 1
and 2; the Editor role to row 7; the non-Vault way in (requirement 6, Q1) to row
4; no anonymous regression to row 5.

The five columns `create-eval` wants (`skills/create-eval/SKILL.md:30-44`:
Behavior, Input, Expected, Scorer, Threshold) are all fillable. Each row names a
behavior, an input and an expected result. Scorer and Threshold are the author's
to set with the operator by design, so §8 not supplying them is correct. Seven
rows also sits in the skill's stated range.

## Recommendations for the marker author (not required fixes)

1. **Assert the value, not just non-emptiness.** Row 2's literal bar, "present
   and non-empty", is implied by row 1 passing. The stronger and equally cheap
   assertion is that the email **equals the operator's actual address**, the one
   subticket 2 adds to `vault_identity_entity.operator`'s metadata
   (`auth_userpass.tf:38-44`, which today has only `managed_by` and `kind`).
   That is what catches a wrong value in the metadata or the scope template,
   which is the failure row 1 cannot see. Row 2's own prose already points this
   way when it calls a "synthesized" email a failure.
2. **Restate the row-1 precondition in row 7's Input column**, the way row 2
   does. A marker row re-run in isolation before any SSO login finds no user,
   and the reason should not have to be rediscovered.
3. **Consider an eighth guardrail row for requirement 2.** The client secret in
   KV2 has no row, and §7 records that `detect-private-key` will not catch a
   Vault client secret because it matches a fixed list of PEM headers
   (`docs/vault-human-auth.md:308-312`, verified). So the repo gate is known to
   be blind here and nothing else covers it. Grepping the tracked tree for
   `hvo_secret_` and expecting no match closes it, and rows 5 and 6 already
   establish the guardrail idiom. The plan says "at least these seven rows", so
   this needs no plan edit.

## Most dangerous assumption

**I3: that Grafana cannot fill the email from anything but the claim.** If
Grafana had any fallback that produced a non-empty string, row 2 would pass
while the identity was garbage, and the plan's central check would be theater.
It does not. `extractEmail` has four sources, three are unset or unemitted by
Vault, the fourth requires a parseable mail address, and the only fallback in
the code runs from email to login rather than the reverse
(`generic_oauth.go:422-450`, `:337-340`). This is the assumption that took four
rounds to get a runnable check for, and it is now settled.

## Contract hygiene

Clean. All twelve sections present. Every `path:line` I opened resolved to what
the plan claims, in the repo and against the `v11.5.2` and Vault 2.0.3 sources.
Gates are discovered, not assumed (`just pre_commit` at `justfile:18`, the three
hooks that bite, `terraform plan`, and the `just worktree_setup` prerequisite at
`justfile:44`). Non-goals are explicit and include the tempting one, putting
Grafana behind oauth2-proxy. Q1, Q2 and Q3 carry recommendations; Q4 is resolved
with its dead branch documented rather than deleted. No test is named without a
home.

## Verdict

`pass`. The premise is SOUND, the two fixes are correctly applied, row 2 is
finally both runnable and un-foolable, rows 2 and 7 share a request safely, and
the seven rows are enough to write the marker from. The three items above are
suggestions for whoever writes the eval, not conditions on this plan.
