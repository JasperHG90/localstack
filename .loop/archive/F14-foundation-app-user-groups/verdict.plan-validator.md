---
verdict: fail
---

# Plan verdict — F14-foundation-app-user-groups (pass `plan-validator`)

Fingerprint verified locally: `sha256sum .loop/plans/F14-foundation-app-user-groups.md`
returns `fb8f0b3d6b6a62aaa60c2739ce6b01c5b636fa36f95f3b180122ca8417faa3e6`,
matching the briefing. Per the contract a `fail` carries no `plan:` line, so
this verdict cannot authorize the `PLANNING -> READY` flip.

Reviewed against the repo, the live cluster (read-only), MinIO's source at the
deployed release tag, oauth2-proxy's and Grafana's upstream config surface, and
the four consumer plans the ticket names.

## Premise verdict: PARTIALLY SOUND

The mechanism the plan is built on is real. Vault's `groups` scope does emit
group names as a JSON array, an empty-policy group is usable, and the group
name is a workable cross-service handle. What breaks is everything the plan
says about who consumes it and how the ticket gets proven:

- The Definition of Done cannot be run. Eval rows 4 and 5 want the same scratch
  entity to be in the two application-user groups **and nothing else** and to
  obtain an ID token. On this cluster those are mutually exclusive, and the
  plan's own non-goals forbid the only fix it hints at.
- Three of the five consumer claims in the Context section are wrong. G1 does
  not read the claim, R4 no longer uses oauth2-proxy at all, and R1 never
  mentions groups. The contract doc (Requirement 3) and eval row 8 would write
  those errors down as the record.
- Q2 is not a deferrable fork. MinIO resolves a claim value **as a policy
  name**, so per-resource groups force a name collision with the existing
  bucket policies and reverse M2's design. The eval file itself says it cannot
  be signed until Q2 is settled.

That last point alone makes this `fail` rather than `pass-with-required-fixes`:
the fixes have to land in `.loop/evals/F14-foundation-app-user-groups.md` as
well as the plan, and a passing verdict would flip the ticket to `ready` with
an acceptance gate that cannot be satisfied. This mirrors the M2 precedent
(`.loop/verdicts/M2-minio-poc-human-tiers.plan-validator.md`).

## Assumptions attacked

### P1 — The `groups` scope emits `identity.entity.groups.names` as a real JSON array in the ID token. **HOLDS**

- `deployments/infrastructure/oidc.tf:39-53` is the scope, template
  `{"groups":{{identity.entity.groups.names}}}`, unquoted, no `jsonencode`.
- `oidc.tf:82` puts it in the provider's `scopes_supported`.
- Live: `vault list identity/oidc/scope` returns `groups`; `vault list
  identity/oidc/provider` returns `default` and `lab`.
- F2's close-out row 5 (`.loop/archive/F2-foundation-vault-oidc-provider/plan.md:451-458`)
  decoded a real token and saw `"groups": ["oidc-smoke"]` as an array.

The plan's claim at its line 34-38 is accurate, and the anchor `oidc.tf:39` is
exact.

### P2 — Each named consumer reaches the group name via the claim, and the plan describes each mechanism correctly. **BREAKS (three of five)**

Per consumer, with the capability question separated from the what-the-plan-says
question:

| Ticket | Can it map group names? | Does the plan describe it correctly? |
|---|---|---|
| G1 Grafana | yes | **no** |
| G2 Nomad UI | yes | yes, but out of scope by F14's own non-goal |
| M2 MinIO | not while `role_policy` is set | substance yes, anchor wrong |
| R1 MLflow | allow/deny only | unsupported |
| R4 Phoenix | yes, natively | **no** |

- **G1 (Grafana).** The capability is real: `[auth.generic_oauth]` in Grafana's
  `conf/defaults.ini` carries `role_attribute_path`, `groups_attribute_path`
  and `allowed_groups`. But the plan's flat statement "`G1` (Grafana) reads the
  claim" is false as of the standing G1 plan, which is `ready` in
  `.loop/ledger.json`: `.loop/plans/G1-grafana-native-oidc-login.md:140-146`
  (Q2) recommends *"start flat, with every authenticated user an Editor"* and
  calls role mapping *"unnecessary complexity"*. G1 today does not consume the
  taxonomy.
- **G2 (Nomad UI).** Reads the claim for real:
  `.loop/plans/G2-nomad-ui-oidc-login.md:225-232` uses `list_claim_mappings`
  plus a binding-rule selector `"nomad-developers" in list.groups`, binding the
  `developer` Nomad policy. That is **infra** access gated by an **infra**
  group, which F14's own first non-goal (plan line 59, *"No Vault, Nomad or
  Consul access for these groups. By construction."*) forbids an
  application-user group from ever having. Listing G2 as a consumer of this
  taxonomy contradicts the non-goal; it consumes the *claim*, not the
  application-user tier. Live: `nomad acl auth-method list` returns none yet
  (Nomad v2.0.3), so this is plan-level, not deployed.
- **M2 (MinIO).** The substance is confirmed at source for the deployed release
  `RELEASE.2025-09-07T16-13-09Z` (`services/minio.hcl:66`):
  `internal/config/identity/openid/openid.go:319-325` returns
  *"Role Policy (=`%s`) and Claim Name (=`%s`) cannot both be set"*. With
  `role_policy` set the claim is genuinely bypassed and Vault's per-client
  assignment does the gating. **But the anchor is wrong.** The plan cites
  `oidc.tf:30-33`; lines 30-33 are `verification_ttl`, the closing brace, a
  blank line, and the first line of a comment. The sentence recording M2's
  bypass is at **`oidc.tf:36-38`**. Eval row 8 repeats the same wrong anchor.
- **R1 (MLflow).** `grep -n "groups\|claim\|allowed_group\|X-Forwarded"
  .loop/plans/R1-rollout-mlflow-oauth2-proxy.md` returns **zero matches**. R1
  does front MLflow with oauth2-proxy (`R1:122-129`), and the flag is real
  (oauth2-proxy `docs/docs/configuration/overview.md` line 99,
  `--oidc-groups-claim`, default `groups`; `pkg/apis/options/providers.go:312-314,
  403-404`). But oauth2-proxy's only group behavior is **allow or deny**
  (`--allowed-group`, overview.md line 82). It has no role concept, so the
  *level* half of the taxonomy (`reader` vs `writer`) cannot reach MLflow
  through the proxy unless MLflow reads `X-Forwarded-Groups`, which nothing in
  R1 claims it does. The contract's clause "each application maps the group
  names it recognizes to its own roles" is not achievable for a proxied app.
- **R4 (Phoenix).** The plan's claim is stale. R4 was rewritten on 2026-07-26
  and **has no proxy**: `.loop/plans/R4-rollout-phoenix-oauth2-proxy.md:9-27`
  (*"The oauth2-proxy design, the port-6006 split, and the L1 dependency are
  all consequences of that premise and are removed"*) and `:307-310`
  (*"Q1 ... SUPERSEDED. No proxy exists in this design"*). R4's Q3 (`:295-303`)
  further recommends flat access and notes that oauth2-proxy's allowed-group
  setting *"no longer exists in this design"*.

So the sentence "`R1` and `R4` go through oauth2-proxy, which reads the claim
via `--oidc-groups-claim`" is half false, and "Two mechanisms, five tickets" is
really at least three mechanisms (claim-read, assignment-gate, proxy
allow/deny) across five tickets of which three currently map nothing.

### P3 — An application-user group with `policies = []` is usable: the entity can authenticate to the OIDC provider and appear in an assignment. **HOLDS, with one overclaim**

- Live: `vault read identity/group/name/oidc-smoke` returns `policies: []`,
  `type: internal`, one member entity. `oidc.tf:92-98` is the Terraform for it,
  and the anchor is exact.
- `vault read identity/oidc/assignment/oidc-smoke` shows the group id in
  `group_ids`, and F2 issued a token through it. An assignment gates on
  membership, not on the group's policies, so `policies = []` costs nothing.
- The reason login works is that `userpass` attaches the `default` policy, and
  `vault policy read default` on this cluster ends with:

      # Allow a token to make requests to the Authorization Endpoint for OIDC providers.
      path "identity/oidc/provider/+/authorize" {
          capabilities = ["read", "update"]
      }

  Requirement 2 is therefore sound but load-bearing on something the plan never
  names: a user created with `token_no_default_policy` cannot authorize at all.
  Worth one sentence in the contract doc.

**Overclaim.** Plan line 45-46 says such a person "can authenticate to Vault's
OIDC provider and read nothing from Vault itself", and Requirement 5 says
"denied every Vault read". The live `default` policy grants `cubbyhole/*`
(create/read/update/delete/list), `auth/token/lookup-self`,
`sys/internal/ui/resultant-acl`, `identity/entity/id/{{identity.entity.id}}`
and the `sys/wrapping/*` set. F11 already enumerates this
(`.loop/plans/F11-foundation-human-read-role.md:89-92`). The eval's four probes
are all correctly chosen and do fail closed; it is the prose that is wrong.

### P4 — The Definition of Done can actually be run. **BREAKS. This is the one that sinks the ticket.**

The DoD (plan line 145-150) and eval rows 4 and 5
(`.loop/evals/F14-foundation-app-user-groups.md:30-31`) require **one scratch
entity** that is simultaneously:

- row 4: in two application-user groups "**and nothing else**", to prove it can
  read nothing in Vault; and
- row 5: able to complete an OIDC login and produce an ID token whose `groups`
  array contains "**exactly the two names**".

On this cluster those cannot both be true:

- `vault list identity/oidc/client` returns exactly one client, `oidc-smoke`.
- `vault read identity/oidc/client/oidc-smoke` shows `assignments:
  ['oidc-smoke']`.
- `vault read identity/oidc/assignment/oidc-smoke` shows
  `group_ids: ['e86ec229-...']` (the smoke group) and `entity_ids: []`.

So the only route to a token is membership in the `oidc-smoke` group. That
makes the entity a member of a third group, breaking row 4's "and nothing else"
and row 5's "exactly the two names". Every escape the plan leaves open is
closed by the plan itself:

- Creating a throwaway client or assignment is barred by the non-goal "**No new
  OIDC clients.**" (plan line 65-66).
- Adding the entity to the smoke group, or to the smoke assignment's
  `entity_ids`, edits resources Terraform owns authoritatively
  (`oidc.tf:97` `member_entity_ids`, `oidc.tf:103` `entity_ids = []`) and is
  barred by "**Do not touch**: `oidc.tf`" (plan line 102).
- The built-in `allow_all` assignment exists (`entity_ids: ['*']`,
  `group_ids: ['*']`) but no client references it, and a client is still
  required for `authorize`.

The plan never mentions `vault_identity_oidc_assignment` at all, which is the
resource that decides whether an application user can get a token from a given
app. That omission is the gap: the taxonomy's second half is the assignment,
not just the name.

### P5 — Q2 (per-app vs per-resource) can honestly be left open. **BREAKS as scoping**

Leaving a fork open with a recommendation is fine. This one is left open with
**no** recommendation, it determines the naming scheme that Requirement 1's map
encodes and that eval rows 1, 2 and 6 score, and the eval file states it
outright (`.loop/evals/F14-foundation-app-user-groups.md:21-23`): *"Q2 must be
settled before this eval can be signed."* A ticket whose acceptance gate cannot
be signed is not `ready`.

The plan also under-states the cost of the per-resource branch. It says only
that "the group count grows with buckets". The real constraint, from MinIO's
source at the deployed tag:

- A claim-based mapping uses the claim **value as the MinIO policy name**:
  `GetIAMPolicyClaimName` returns `ClaimPrefix + ClaimName`
  (`internal/config/identity/openid/openid.go:542-550`), and
  `cmd/sts-handlers.go:466-493` sets that value as `policyName`. MinIO performs
  no translation.
- Today's per-bucket policies are named `<bucket>_read_write` and
  `<bucket>_read_only` (`deployments/applications/modules/bucket/main.tf:12`
  and `:30`, for example `memex_read_write`). A per-resource Vault group would
  have to be named that, which collides head-on with `app-<service>-<level>`.
- Claim mode and `role_policy` are mutually exclusive per provider
  (`openid.go:319-325`), and **at most one** claim-based provider may exist
  server-wide (`openid.go:378-386`, `errSingleProvider`). So adopting
  per-resource groups for MinIO reverses M2's whole `role_policy` design.

Answering the briefing's question directly: **yes, MinIO can express a
per-bucket mapping from an OIDC claim**, but only by abandoning `role_policy`
for that provider and by making the Vault group names equal MinIO policy names.
That is a design decision, not a naming detail, and it belongs in Q2.

### P6 — Eval row 5's decode step is specified well enough to catch F2's silent-drop failure, and row 6 is not self-certifying. **HOLDS, weakly**

- Row 5 (`evals:31`) names the exact failure: not the string `"null"`, not a
  quoted string containing a bracketed list, and its scorer is "decoded
  payload's `groups` is an array containing exactly the two names". That does
  catch the `{"groups": "null"}` mode described at `oidc.tf:48-52` and proven
  in F2's close-out. Type and content are both asserted. Good.
- Row 6 (`evals:32`) discriminates against a checker that says yes to any
  token, which is what it claims to do. It is weak in one way: if the control
  entity is in **zero** groups, its claim renders as the string `"null"` and
  "its `groups` array does not contain either name" is vacuously true against a
  broken renderer. It also inherits P4's problem, since a zero-group entity
  cannot pass any assignment.
- Row 5 does not tell the implementer to request `scope=openid groups`. That is
  the second silent-drop mode, documented at `docs/vault-human-auth.md:89-95`
  and flagged in G2's R1. Omitting it fails the row rather than passing it, so
  this is a usability gap, not a correctness hole.

### P7 — Nothing in the plan contradicts F11, and the dependency direction is right. **HOLDS on direction, BREAKS on the reconciliation the ticket claims to do**

Direction is clean and mutual. F11's non-goals (`F11:108-110`) hand application
users to F14; F11's Q2 (`F11:176-179`) settles group-vs-entity binding and F14
does not reopen it; F11 Requirement 2 (`F11:126-129`) names the same
`oidc.tf:39` claim. F14 does not re-decide anything F11 settled. `depends_on`
lists F11, which is at `planning` in `.loop/ledger.json`, so eval row 7 (which
runs probes from a `developer` session) is correctly gated.

What breaks is the plan's own headline: *"Consumers are not consistent today,
and that is the real problem this ticket fixes."* It does not fix it.

- M2 expects Vault groups named `minio-admins`, `minio-readers`,
  `minio-writers` (`.loop/plans/M2-minio-poc-human-tiers.md:113-115`, and eval
  step 3 at `:250-252` hard-codes them). F14's scheme renames them to
  `app-minio-<level>` and never says so, never lists M2's plan or eval as
  needing the rename, and puts `oidc.tf` and every consumer file off limits.
- G1 (`:43-46`) and R4 (`:295-296`) both reference a group `dashboard-users`.
  F14 does not mention it or say what it becomes.
- Nobody currently owns creating M2's groups. M2's non-goals assign them to F2
  (`M2:112-116`), but F2 shrank on 2026-07-30 to the singletons only
  (`.loop/archive/F2-foundation-vault-oidc-provider/plan.md:385-395`) and
  `oidc.tf` ships only `oidc-smoke`. F14 is the natural owner and does not
  claim it.

### P8 — Every `path:line` anchor resolves. **BREAKS (one of seven)**

| Plan claim | Actual | Status |
|---|---|---|
| `oidc.tf:39` — the `groups` scope | exact (`resource "vault_identity_oidc_scope" "groups"`) | holds |
| `oidc.tf:30-33` — records M2's bypass | 30-33 is `verification_ttl`, `}`, blank, comment opener; the bypass note is at **36-38** | **shifted** |
| `oidc.tf:92` — `vault_identity_group.smoke` | exact | holds |
| `oidc.tf:118` — the allowed-client-id pattern | exact | holds |
| `storage.tf:62-65` — `readers` / `writers` | exact (the `permissions` block) | holds |
| `storage.tf:2-29` — MinIO's per-bucket model | exact (the `buckets` locals map) | holds |
| `.loop/config.json:2-4` — the gate | exact (`"gates": ["just pre_commit"]`); `justfile:18-19` runs `pre-commit run --all-files` | holds |

Gates are discovered rather than assumed, and `docs/vault-human-auth.md` exists
as an edit target. Non-goals are explicit. Tests are homed. The contract
hygiene is otherwise fine; the premise is what fails.

## Most dangerous assumption

**P4.** If the Definition of Done cannot be run, nothing else about the ticket
matters. There is exactly one OIDC client on this cluster and its assignment
admits exactly one group, so "a scratch entity in two application-user groups
and nothing else gets a token" is unreachable without an assignment the plan
forbids creating. The plan never mentions `vault_identity_oidc_assignment`,
which is the resource that actually decides whether an application user can log
in to a given app. A taxonomy of group names that cannot get an entity through
an assignment is half a contract.

## Required fixes

1. **Give the proof a way to run.** Decide and write down how the scratch
   entity obtains a token. Either add a throwaway
   `vault_identity_oidc_assignment` (and client) owned by F14, which means
   amending the "No new OIDC clients" non-goal, or split the proof across two
   entities: one in only the app groups for the denial row, one in the app
   groups plus an assignment-bearing group for the claim row. Then relax eval
   row 5 from "exactly the two names" to "contains both names", since any
   workable route adds a third. Evidence: `vault list identity/oidc/client`
   (one client), `vault read identity/oidc/assignment/oidc-smoke`,
   plan lines 65-66 and 102.
2. **State the assignment half of the contract.** The contract currently names
   only the group name. Add: an application user reaches an app only if that
   app's `vault_identity_oidc_client` carries an assignment listing the group,
   and say which ticket owns each assignment. Anchor:
   `oidc.tf:100-104`.
3. **Settle Q2 before this leaves PLANNING**, and carry MinIO's real
   constraint into it: a claim-based mapping uses the claim value as the MinIO
   policy name (`openid.go:542-550`, `cmd/sts-handlers.go:466-493`), today's
   bucket policies are named `<bucket>_read_write` / `_read_only`
   (`modules/bucket/main.tf:12`, `:30`), claim mode excludes `role_policy`
   (`openid.go:319-325`), and only one claim-based provider may exist
   (`openid.go:378-386`). Per-resource groups reverse M2's design; per-app
   groups do not. The eval says it cannot be signed until this is settled.
4. **Correct the consumer table.** G1 recommends flat, no group mapping
   (`G1:140-146`). R4 has no proxy at all (`R4:9-27`, `:307-310`). R1 mentions
   groups nowhere (grep, zero matches). Rewrite the Context paragraph and eval
   row 8 to say what each ticket does **today** and what it would have to
   change to consume the taxonomy. Otherwise `docs/cluster-roles.md` becomes a
   record of things that are not true.
5. **State oauth2-proxy's limit.** The flag exists (`overview.md:99`) but a
   proxy can only allow or deny (`overview.md:82`); it has no roles. Say
   plainly that behind oauth2-proxy the *level* half of the taxonomy is not
   expressible unless the app itself reads `X-Forwarded-Groups`.
6. **Fix the anchor `oidc.tf:30-33` to `oidc.tf:36-38`** in both the plan (line
   54) and eval row 8.
7. **Drop the "read nothing from Vault" overclaim.** The `default` policy
   grants `cubbyhole/*`, `auth/token/lookup-self`, `sys/wrapping/*`,
   `sys/internal/ui/resultant-acl` and self entity read; F11 already lists them
   (`F11:89-92`). Say "no access to any secret, policy or identity path" and
   keep the four eval probes as they are. Add the rider that OIDC login depends
   on the `default` policy being attached, since it is what grants
   `identity/oidc/provider/+/authorize`.
8. **Say what happens to the group names other tickets already assume.** M2's
   `minio-admins` / `minio-readers` / `minio-writers` (`M2:113-115`, eval step
   3 at `M2:250-252`) and `dashboard-users` (`G1:43-46`, `R4:295-296`). Name
   who renames them and who creates them, given F2 no longer does
   (`F2 archive plan:385-395`). This is the inconsistency the ticket exists to
   settle.
9. **Resolve the G2 tension.** Either drop G2 from the application-user
   consumer list, since it grants Nomad access and non-goal 1 forbids that, or
   say explicitly that G2 consumes the *claim* with an infra group and is not
   an application-user consumer.
10. **Sharpen eval row 6.** Put the control entity in a real non-application
    group and assert its decoded `groups` is an array containing that group's
    name and neither application-user name. As written, a zero-group entity
    renders the string `"null"` and passes the row vacuously.
