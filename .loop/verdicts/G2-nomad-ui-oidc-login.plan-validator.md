---
verdict: fail
---

# G2-nomad-ui-oidc-login — plan premise review (pass `plan-validator`)

Reviewed against plan sha256 `8ab982b52366a544c66f83b1951152fcf5688d2de4bed37f22b025c6ae19878a`.
No `plan:` line is written, because this is a `fail` and a failing verdict must
never carry an authorizing hash.

## Premise verdict

**PARTIALLY SOUND, failing on severity.**

Every claim the prior verdict flagged has been fixed, and I re-measured each fix
rather than reading the corrected prose. The plan's OIDC mechanism itself is
sound: I built the exact auth method and binding rule this plan describes,
selector and all, against a throwaway Nomad dev agent and they were accepted.

Two findings the prior pass did not reach force the `fail`, and neither is a
text fix:

1. **The plan puts two management-token-only Nomad resources into a Terraform
   root whose own sibling file writes down the invariant that they must not go
   there.** Measured, not inferred. G2 never mentions the credential its
   resources need, and no row in its eval can catch this.
2. **The group non-goal and the group mechanism contradict each other.** The
   non-goal says G2 consumes a group name and does not define one, and demands
   G2 state which of two sources the name comes from. §Code surface and Q3 then
   define one, and the name matches neither source.

Both reverse a design decision or need an operator call, which is the
`unresolved-design-fork` shape rather than a required-fix shape.

---

## Prior verdict's required fixes: all five addressed, re-measured

| RF | Status | Evidence I re-ran |
|----|--------|-------------------|
| RF1 PKCE rationale | **fixed** | R2 (`:167-179`) now says "defense in depth", cites `sso-pkce-jwt` "supports", and states the guide never mentions PKCE. Eval row 7 carries the same correction. |
| RF2 broken grep guardrail | **fixed and verified** | Eval row 9 now uses `grep -nE -e 'client_secret[[:space:]]*=[[:space:]]*"' -e 'hvo_secret_'`. Ran it here on ugrep 7.5.0: matches both leak shapes (exit 0), clean file exit 1, and the by-reference form the plan mandates (`oidc_client_secret = vault_identity_oidc_client.nomad.client_secret`) exit 1. It can fail and does not false-red. |
| RF3 row 11 workload path | **fixed and verified live** | Row 11 now reads `vault auth list` + `vault read auth/jwt-nomad/config`. Live: `jwt-nomad/ jwt` present; config returns `default_role = nomad-workloads`, `jwks_url = http://127.0.0.1:4646/.well-known/jwks.json` — the row's asserted values are exact. |
| RF4 Q1 import missing from §Code surface | **fixed by reversal** | Q1 now resolves to reference-by-name. §Code surface `:240-254` explicitly forbids the policy resource and the import block. Ansible ownership confirmed: `bootstrap/roles/nomad_server/tasks/main.yml:182-187` is the `nomad acl policy apply … developer` task with `NOMAD_TOKEN: {{ nomad_bootstrap_token }}`. Anchor resolves. |
| RF5 a–d | **fixed** | (a) the Consul non-goal now cites the doc banner and explicitly retracts the `Edition: n/a` probe. (b) §Code surface `:224-231` states the nested `config` block and `bound_issuer` as a list — measured: `nomad acl auth-method create -config='{…"BoundIssuer":"https://example.com"…}'` returns `json: cannot unmarshal string into Go struct field .Alias.BoundIssuer of type []string`; the list form is accepted. (c) §Risk `:286-294` states the Vault UI authorize path — live discovery confirms `authorization_endpoint: https://vault.lab.orangecluster.nl/ui/vault/identity/oidc/provider/lab/authorize`, and `https://vault.lab.orangecluster.nl/ui/` returns 200. (d) R1 now says `oidc_scopes = ["groups"]`. |

## Per assumption

### P1 — Nomad CE supports the OIDC auth method at the pinned version — **HOLDS**

Re-verified live, not carried over. `nomad license get` → `Error getting
license: Nomad Enterprise only endpoint` (CE). `nomad server members` →
leader `firebat.global`, `Build 2.0.4`. `nomad acl auth-method create -help` →
`Sets the type of the auth method. Supported types are 'OIDC' and 'JWT'.`

### P2 — the auth method and binding rule this plan describes are accepted as written — **HOLDS** (built them)

I ran a throwaway `nomad agent -dev` with ACLs on Nomad 2.0.3 (same
minor as the cluster's 2.0.4 servers) and created the plan's exact objects with
a management token:

```
OIDC Enable PKCE       = true
OIDC Scopes            = groups
Bound issuer           = https://example.com
Allowed redirects URIs = http://localhost:4649/oidc/callback,
                         https://nomad.lab.orangecluster.nl/ui/settings/tokens
```

and the binding rule `Selector = "\"nomad-developers\" in list.groups"`,
`Bind Type = policy`, `Bind Name = developer`. Both accepted. `nomad login
-help` confirms `-oidc-callback-addr … defaults to "localhost:4649"`, so R3's
CLI URI is right.

Two things I learned doing it, neither a break:

- **The binding rule does not validate that `bind_name` names a live policy.**
  I created a rule bound to `does-not-exist-xyz` and it was accepted. So
  referencing Ansible's `developer` by name imposes no ordering dependency —
  and equally, a typo is silent until someone logs in. Eval row 2 catches it,
  which is the right place, but the plan should say so.
- The auth method does not validate that `oidc_discovery_url` resolves at
  create time (`https://example.com` was accepted), so a misaimed URL surfaces
  only at first login. R4's `bound_issuer` is the right guard.

### P3 — **Terraform is the right owner for these two resources** — **BREAKS** ← most dangerous

This is the finding that fails the plan. The plan asserts, throughout §Code
surface and the subticket list, that `nomad_acl_auth_method` and
`nomad_acl_binding_rule` belong in `deployments/infrastructure/`. It never
states what credential applies them.

**Measured.** On the throwaway dev agent I created a deliberately maximal Nomad
client policy — `namespace "*" write`, `host_volume "*" write`, and
`node`/`agent`/`operator`/`quota`/`plugin` all `write` — minted a
`Type = client` token from it, and tried both creates:

```
=== A. maximal CLIENT policy -> auth-method create ===
Error creating ACL auth method: Unexpected response code: 403 (Permission denied)
=== B. MANAGEMENT token -> auth-method create (positive control) ===
Name = probe   Type = OIDC   ...
```

Same 403 for `binding-rule create`. An earlier run with a token carrying the
repo's real `developer` policy
(`bootstrap/roles/nomad_server/files/nomad_developer_policy.hcl`) gave the same
403 on both. **No Nomad ACL policy can grant this.** Confirmed independently:

- `nomad acl auth-method create -help` → "Use requires a management token."
- `developer.hashicorp.com/nomad/api-docs/acl/auth-methods` → `ACL Required:
  YES / all management token`, and the same on
  `.../acl/binding-rules`. The **read** endpoints are management-only too, so
  even a `terraform plan` refresh needs one.

Why that sinks the plan rather than merely annoying it:

- **The repo already writes the opposing invariant down, in the sibling file.**
  `deployments/infrastructure/consul_deploy_role.tf:7-15`: "The `consul`
  secrets engine mount, its `config/access` … AND the scoped `deploy` Consul
  ACL policy are all owned by Ansible bootstrap … Each requires the Consul
  management token, **which the config-split invariant keeps out of
  Terraform.**" G2 puts two management-token-only Nomad objects into Terraform.
- **F8's replan applies that same reasoning to Nomad and is the current
  direction.** `.loop/plans/F8-foundation-deployer-provider-cutover.md:514-540`:
  the brokered `nomad/creds/deploy` token is `type: client` (live: `Type =
  client`), "so the deployer can never apply the very policy that defines it",
  and the decision is to move `nomad_acl_policy.deploy` out of Terraform into
  Ansible. `F8:632` adds an eval row that fails while any `nomad_acl_policy`
  resource remains.
- **G2 satisfies F8's literal row while violating its reason.** G2 adds no
  `nomad_acl_policy` (eval row 10 enforces that, correctly). It adds two
  resources with the *identical* constraint that F8's row was written to
  express. After F8's cutover the infrastructure root would 403 on refresh of
  `nomad_acl_auth_method`, so F8's own acceptance criterion — "**A full `just
  apply` of the infrastructure root under the brokered path**" (`F8:624`) —
  becomes unachievable again. That is precisely the `unresolved-design-fork`
  F8 is blocked on today, reintroduced from a different ticket.
- **Nothing in G2 can catch it.** G2's plan never mentions a management token,
  F8, or the config-split invariant (`grep -n "F8" ` over the plan returns
  nothing). Its gate is `just pre_commit`, which runs `terraform fmt -check`
  and `terraform validate` (`.pre-commit-config.yaml:22-33`) — neither
  contacts Nomad. Eval row 1 assumes the operator applies with today's
  management `NOMAD_TOKEN` from `.devcontainer/.env` (live: `Type =
  management`, `Name = Bootstrap Token`), which is the token F8 exists to
  delete.

This is a fork the plan does not contain: does the Nomad auth method and
binding rule live in Terraform (which then pins the infra root to a management
token forever, contradicting `consul_deploy_role.tf:7-15` and F8), or in
Ansible bootstrap beside the `developer` policy it binds to (which is where the
management token already is, at `nomad_server/tasks/main.yml:186`)? The plan
picks the first silently, and its whole §Code surface, subticket order and eval
depend on the answer.

### P4 — "G2 consumes a group name; it does not define one" is coherent with G2's mechanism — **BREAKS**

The non-goal at `:144-149` says F14 owns the naming convention and the OIDC
assignment wiring, that G2 consumes a name rather than defining one, and that
G2 "must state which" of F14's scaffold or a service-specific group it binds,
"and follow F14's convention either way."

The plan then does define one, and does not state which, and does not follow
the convention:

- §Code surface `:218-220` creates `vault_identity_group` and
  `vault_identity_oidc_assignment`. Q3 and §Forks resolved `:397-400` name it
  `nomad-developers`. Eval row 3 scores that literal name.
- **F14's convention is `app-<service>-<level>`**
  (`.loop/plans/F14-foundation-role-taxonomy.md` R7: "Naming is
  `app-<service>-<level>`, documented, not enforced"). `nomad-developers` is
  not that shape.
- **F11 creates a Vault identity group literally named `developer`** and says
  so explicitly: F11 R2, "**A `vault_identity_group` named `developer`** …
  The group name also rides the OIDC `groups` claim (`oidc.tf:39`), which is
  how F14 and the per-app tickets consume it." G2 is a per-app ticket. So the
  live fork is: bind the selector to F11's `developer` tier group, or mint an
  app-user group named `app-nomad-<level>` per F14. `nomad-developers` is
  neither, and the plan never argues against either.
- **`depends_on` lists only `F2`** (plan frontmatter `:3`, and
  `.loop/ledger.json` `G2 → dependencies: ["F2-foundation-vault-oidc-provider"]`).
  A non-goal that makes F14 the owner of a convention G2 must follow, with no
  dependency edge on F14 or F11, lets G2 be picked up before either exists.
  F14 is `ready` and F11 is unbuilt; priority ordering (F14=35, G2=25) happens
  to favour F14 first, but priority is not a dependency.

The non-goal as written is coherent *as an instruction*; the plan simply does
not obey it. Q3 was resolved on 2026-07-31, before F11 and F14 became the
owners, and was never revisited.

Ancillary: F14 R11 rewrites `docs/vault-human-auth.md:71-87` step 2, which
today "tells every consumer to create its own `vault_identity_group`", to say a
consumer references tier groups first. G2 edits the same doc section
(`:262-263`) and takes the behavior F14 is about to demote.

F14 *does* disclaim consumer wiring ("No consumer wiring. `G1`, `G2`, `M2`,
`R1`, `R4` each wire their own service"), so G2 minting its own
`vault_identity_oidc_assignment` and client is coherent. The break is the group
name and the unanswered "which source", not the assignment.

### P5 — `developer` is live, Ansible-owned, and grants what the plan says — **HOLDS, exactly**

Live `nomad acl policy info developer` returns, verbatim: namespace "default"
`policy = "write"` with `submit-job, read-job, list-jobs, dispatch-job,
read-logs, read-fs, alloc-exec, alloc-lifecycle, alloc-node-exec`;
`host_volume "*" { policy = "write" }`; `node`/`agent`/`operator` read. Matches
§Context `:98-104` grant for grant. `nomad acl policy list` → `deploy`,
`developer` only. Ansible ownership anchor `main.yml:182-184` resolves (the
task block is `:182-187`). R7's two-owners argument is correct and the Q1
reversal is right.

The plan's §Risk `:295-302` is honest that this hands `alloc-node-exec` — shell
on the node — to everyone in the bound group. See P7 for why the guard on that
is weak.

### P6 — repo anchors — **HOLDS**

Every `path:line` I opened resolves:

- `haproxy.hcl:101` `acl is_nomad hdr(host) -i nomad.lab.orangecluster.nl`;
  `:112` `use_backend nomad if is_nomad`; `:136-137` `backend nomad / server
  nomad1 192.168.2.30:4646 check`. Live: `https://nomad.lab.orangecluster.nl/`
  → 307 to `/ui/`.
- `oidc.tf:63-67` is the `locals { oidc_provider_client_ids = [...] }` block
  with the "APPEND YOUR CLIENT HERE" marker above it.
- `oidc.tf:118-121` is `vault_identity_oidc_key_allowed_client_id "smoke"`.
- `oidc.tf:26-31` (`vault_identity_oidc_key.lab`) carries no inline
  `allowed_client_ids`, so R5's warning and eval row 8's third assertion are
  meaningful.
- `nomad_deploy_role.tf:13-30` is `nomad_acl_policy.deploy`, narrow exactly as
  §Context says.
- `providers.tf:3-6` is `hashicorp/nomad ~>2.5.0`.
- `secrets.tf:15-29` is the `vault_kv_secret_v2` + `custom_metadata` pattern R6
  says to match.
- `docs/vault-human-auth.md:71` is `## Adding a service that logs people in
  through Vault`.

Live Vault: `identity/oidc/provider/lab` → `allowed_client_ids
[zsJxdNqN7vIBQXhGmlgkwVIHigjhweGF]`, issuer the HTTPS `lab` path; discovery
document advertises `scopes_supported ["groups","openid"]`,
`code_challenge_methods_supported ["plain","S256"]`,
`response_types_supported ["code"]`. `vault list identity/oidc/client` →
`oidc-smoke` only. P2's PKCE claim in R2 is achievable.

### P7 — R1's "something below the Terraform surface adds `openid`" — **HOLDS, and is settleable**

The plan is honest here: it marks this an assumption with no citation and
defers to a decode in subticket 3. That posture is correct and I am not asking
for a change. But the citation exists, and the plan would be stronger with it:

- `hashicorp/cap/oidc/config.go`: "The `oidc` scope will **always** be added to
  the new configuration's Scopes, regardless of what additional scopes are
  requested via the WithScopes option", and `configDefaults()` returns
  `withScopes: []string{oidc.ScopeOpenID}`.
- `hashicorp/cap/oidc/options.go:51-65`: for `configOptions`, `WithScopes`
  **appends** ("configOptions already has the oidc.ScopeOpenID in its
  defaults"); for `reqOptions` it prepends `ScopeOpenID`.
- Nomad depends on `github.com/hashicorp/cap v0.13.0` (`go.mod:46`).

I did not read Nomad's exact call site, so I record this as strong support, not
proof — which is why it stays a decode-to-confirm rather than a settled fact.
`oidc_scopes = ["groups"]` is the right thing to write.

### P8 — the gates are this repo's real gates — **HOLDS**

`.loop/config.json` gates on `just pre_commit`; `justfile:18-19` is
`pre-commit run --all-files`; `.pre-commit-config.yaml:22-33` defines
`terraform-fmt` (`terraform fmt -check -recursive`) and `terraform-validate`.
`justfile:30-32` defines `worktree_setup path`, which eval row 13 invokes.
`detect-private-key` is at `:12`, so R6's rejection of it names a real hook.
Discovered, not assumed.

## Most dangerous assumption

**P3 — that these two Nomad ACL resources belong in Terraform.** Being wrong
about it does not cost a rewrite of the plan's text; it moves the entire code
surface to a different layer, changes who applies it, and reopens the exact
design fork that has F8 blocked. Every other finding here is repairable inside
the plan as structured.

---

## Eval marker review — `.loop/evals/G2-nomad-ui-oidc-login.md`

**Can every row fail?** Rows 1–11 and 13, yes, and I checked the ones that
looked soft. Row 1 can fail because the cluster has zero auth methods today
(`nomad acl auth-method list` → "No ACL auth methods found"). Row 9's pattern
is now genuinely falsifiable (ran it, above). Row 11's asserted values match
live exactly, so it fails on real drift rather than on a stale constant. Row 4
requires the scratch entity to log in to Vault successfully first, which is the
right discrimination test.

Three defects:

**E1. Row 12 is self-certifying.** Input is "Read the ticket's close-out
notes"; the expectation is that the notes state the `alloc-exec` /
`alloc-node-exec` inheritance **and** "the close-out must confirm **the
operator accepted it**". A review agent reading the implementer's own close-out
cannot verify operator acceptance — the implementer writes the sentence and the
row goes green. This is the only guard on the one grant the plan itself calls
undecided (§Risk `:295-302`). Either score it against an artifact the
implementer does not author, or scope the expectation down to disclosure and
route acceptance to the operator's sign-off.

**E2. Row 10 is labelled `deterministic check` but needs judgment, and will
false-red.** `grep -rn 'developer' deployments/**/*.tf` **always** matches on a
correct implementation, because the binding rule's `bind_name = "developer"` is
required. And `terraform state list` "read for any `nomad_acl_policy` address"
matches the pre-existing `nomad_acl_policy.deploy` (live, at
`nomad_deploy_role.tf:13`). A mechanical scorer reading "no match" fails a
correct ticket; a scorer reading loosely passes a wrong one. State the expected
shape: exactly one `developer` occurrence and it is a `bind_name`, and no
`nomad_acl_policy` address **named `developer`**.

**E3. No row fails on P3.** Nothing in the marker observes that
`nomad_acl_auth_method` and `nomad_acl_binding_rule` need a management token,
or that they now sit in the root F8 is cutting over to a brokered client token.
Row 13 (`just pre_commit`) runs `terraform validate`, which never contacts
Nomad. This is the same false-green class the marker's own preamble is written
to prevent, one layer up: the whole board can be green on a change that cannot
be applied after F8.

**Contradiction with a requirement:** row 4's expectation ("Authorization is
REFUSED and no Nomad ACL token is issued") conflates the Vault assignment gate
with the Nomad selector gate. An entity outside the assignment is refused; an
entity inside the assignment but outside `nomad-developers` gets a token with
**no policy**, which is the F2 defect shape, not a refusal. They coincide today
only because G2's assignment lists exactly one group. Say which gate the row
scores, or add the second case.

Row 3 also carries the F14 collision from P4: it scores the bound group name,
so whichever way the group fork resolves, this row changes.

---

## Required fixes

**RF1 (P3, blocking, needs an operator decision).** Settle where the Nomad auth
method and binding rule live, and write the credential requirement into the
plan.
 (a) Add to §Context, as a measured fact: creating or reading a Nomad ACL auth
     method or binding rule requires a **management** token. Evidence: `nomad
     acl auth-method create -help` "Use requires a management token";
     `nomad/api-docs/acl/auth-methods` and `.../binding-rules` "ACL Required:
     YES all management token"; and the probe above, where a client token with
     `namespace "*" write` plus node/agent/operator/quota/plugin write got 403
     on both creates while a management token succeeded.
 (b) Reconcile with `consul_deploy_role.tf:7-15`, which states the config-split
     invariant, and with `F8:514-540`, which moves `nomad_acl_policy.deploy`
     out of Terraform for exactly this reason. Either put these two resources
     in Ansible bootstrap beside the `developer` policy they bind to
     (`nomad_server/tasks/main.yml:182-187`, where the management token already
     is), or state and defend the exception and add the dependency edge on F8
     plus an eval row asserting the infra root still applies under the brokered
     path.
 (c) Add an eval row that fails if the chosen owner is wrong — today no row
     can.

**RF2 (P4, blocking, needs an operator decision).** Answer the question the
non-goal asks. Either bind the selector to **F11's `developer` Vault group**
(F11 R2 says its name rides the `groups` claim and is how per-app tickets
consume it), or mint an app-user group under **F14's `app-<service>-<level>`**
convention (F14 R7). `nomad-developers` is neither. Whichever you pick, update
Q3, §Code surface `:218-220`, §Forks resolved `:397-400` and eval row 3
together, and add `F14-foundation-role-taxonomy` (and `F11` if you bind its
group) to `depends_on`, which today lists only F2.

**RF3 (E1).** Rewrite eval row 12 so it is not scored by the artifact the
implementer wrote. At minimum drop "the close-out must confirm the operator
accepted it" from a row a review agent scores, and route acceptance to the
operator sign-off line.

**RF4 (E2).** Give row 10 an expected shape a scorer can apply: exactly one
`developer` occurrence in the Terraform diff and it is the binding rule's
`bind_name`; no `nomad_acl_policy` address **named `developer`** in state
(`nomad_acl_policy.deploy` is pre-existing and expected); no `import` block;
`bootstrap/` unchanged.

**RF5 (small, group them).**
 (a) Row 4: name which gate is being scored — the Vault assignment refuses, the
     Nomad selector yields an empty-policy token. Add the second case or scope
     the row.
 (b) §Code surface or R7: note that a binding rule does **not** validate that
     `bind_name` names a live policy — measured, a rule bound to
     `does-not-exist-xyz` was accepted — so a typo is silent until first login,
     and eval row 2 is the only thing that catches it.
 (c) Optional, R1: the `openid` question is settleable.
     `hashicorp/cap/oidc/config.go` always adds `oidc.ScopeOpenID` to a
     config's scopes and `options.go:51-65` appends rather than replaces;
     Nomad pins `github.com/hashicorp/cap v0.13.0` (`go.mod:46`). Keep the
     decode gate either way.

## Contract hygiene

Beneath the two premise breaks, the contract is in good shape and better than
most: all sections present, every anchor I opened resolves (P6), gates
discovered from `.loop/config.json`, `justfile` and `.pre-commit-config.yaml`
rather than assumed (P8), non-goals explicit, forks surfaced with
recommendations and then resolved in a dated block that marks its own
corrections. §8 names no unit tests, which is genuinely empty for a
Terraform-only change and is stated as such. The one contract break is the
non-goal at `:144-149` that the plan's own §Code surface does not satisfy
(P4) — a fork stated as settled that is not.

## What I could not verify

- The end-to-end browser login. It cannot be driven without applying, and I am
  read-only against the live cluster. Eval rows 2–5 are the right shape.
- Nomad's exact `cap/oidc` call site (P7), so `openid` injection is strongly
  supported rather than proven. The plan's decode-to-confirm handles it.
- Whether F8's replan will be accepted as written. F8 is `blocked` on
  `unresolved-design-fork`. But P3 does not depend on F8's fate: the
  management-token requirement is a property of Nomad, and the config-split
  invariant is already checked into `consul_deploy_role.tf:7-15`.

**What I re-ran versus only read:** re-ran — live Nomad version/members/policy
list/auth-method list/role list/token self/`developer` policy body, live Vault
auth list, OIDC client list, `lab` provider read, `auth/jwt-nomad/config`, the
`lab` discovery document, the HAProxy edge probes, the row 9 grep against real
leak and clean fixtures, and a throwaway `nomad agent -dev -acl` on which I
built the plan's auth method and binding rule and ran the management-token
probe both ways. Only read — the plan, the eval marker, F8/F11/F14 plans, the
ledger, the repo `.tf`/Ansible files, the HashiCorp API docs pages, and the
`hashicorp/cap` sources.
