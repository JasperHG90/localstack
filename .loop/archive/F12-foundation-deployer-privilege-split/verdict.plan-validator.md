---
verdict: fail
---

<!--
No `plan:` line: a failing verdict must not carry the authorizing hash, so
it cannot flip the ticket to `ready`. The plan I reviewed hashes to
c2f7b593ca909faeddaef628ddd9e653ebc6b7ab9244211e983e4cb481beca62, which
matches the briefing.
-->

# F12 plan re-review (rescoped) - premise falsification

**Premise verdict: PARTIALLY SOUND.** The rescope worked. Every fix from the
last pass landed and I re-verified each one. The applications-only scope
stands on its own, the three-path shape is right, and `auth/token/create`
grants nothing above the token's own policies. But two of the six granted
capabilities have no caller, the sentence justifying one of them is false
against the pinned provider's source, the eval row that claims to test that
grant cannot fail on it, and the identity that is this ticket's deliverable
is never exercised by any row. The last two are the F7 shape again: a
guardrail that certifies a boundary it never touches. That needs
re-measurement and an eval rewrite, so this stays at `PLANNING`.

## What I ran this pass

**Live, read-only** against `http://192.168.2.30:8200` (Vault **2.0.3**,
build 2026-06-17): `vault status`, `policy list`, `policy read default`,
`policy read default-ceiling`, `policy read acme-tls-write`, `secrets list
-format=json`, `auth list`, `list secret/metadata/default`, `list
identity/group/name`, `list identity/entity/name`, `read
identity/entity/name/operator`, and two `read -format=json` calls whose
output I filtered to the `metadata` block only. No writes, no token mints,
no `terraform` invocation.

**Upstream source, pinned to the exact versions in play**:
`terraform-provider-vault` **v5.3.0** `vault/resource_kv_secret_v2.go`,
`internal/vault/secrets/ephemeral/kv_secret_v2.go`, `util/util.go`; and
`hashicorp/vault` at tag **v2.0.3** `vault/token_store.go`.

**In-repo**: both roots' resource inventories, every cited `path:line`,
`sha256sum` of the plan.

## Per assumption

### P1. The applications-only scope stands alone - HOLDS

Nothing here needs F13 first. The policy and identity are additive
`vault_*` resources in the infrastructure root, and that root still runs on
the root token throughout (plan:124-125 keeps it, F13 owns its removal).
The eval covers the one coupling that matters (the infrastructure root must
still plan). F13's own frontmatter carries `depends_on =
["F11-...", "F12-..."]` and names `vault_policy.deployer_applications` as
one of the three it will move (`F13...md:43,155,201`), so the direction is
agreed on both sides. Answering the operator's first question directly:
**the policy living in the infrastructure root is not a problem.**

One disclosure gap, low severity: F12 alone reads as if Requirement 3's
"created by Terraform in the infrastructure root" is the end state. F13
will delete that resource and hand the policy to Ansible. Say so in one
line so the implementer is not surprised.

### P2. `read` on `secret/metadata/default/*` is needed - HOLDS, and I found why

The plan asserts this from a plan run. The mechanism confirms it and is
worth recording, because it is not obvious. `resource_kv_secret_v2.go:317-335`
reads the metadata endpoint only when the data-read response's `metadata`
block contains a `custom_metadata` key. Live, an applications-owned secret
returns:

```json
{ "created_time": "...", "custom_metadata": null, "destroyed": false, "version": 1 }
```

The key is present with a null value, so the Go map lookup `_, ok :=
v[consts.FieldCustomMetadata]` is true and `readKVV2Metadata` fires on every
refresh of every `vault_kv_secret_v2` in this root. The grant is real and
it survives even though no resource sets `custom_metadata`.

### P3. `delete` on `secret/metadata/default/*` is needed because a destroy removes metadata - BREAKS

Plan:68-69 and eval row 3 both rest on this. It is false for the pinned
provider. `resource_kv_secret_v2.go:379-402`:

```go
	base := consts.FieldData
	deleteAllVersions := d.Get("delete_all_versions").(bool)
	if deleteAllVersions {
		base = consts.FieldMetadata
	}
	path := getKVV2Path(mount, name, base)
	_, err := client.Logical().Delete(path)
```

`delete_all_versions` defaults to `false` (`:146-151`), and `grep` over
`deployments/applications/*.tf` returns no occurrence of it. So a destroy in
this root issues `DELETE secret/data/<name>`, which the data block's
`delete` already covers. The metadata endpoint is never touched. The
repository already knows this: `deployments/infrastructure/acme.tf:38-40`
says in a comment, "A KV2 data write needs no `secret/metadata/*`
capability."

Two consequences, and the second is the serious one:

1. The `delete` capability has no caller, which contradicts Requirement 1
   ("every grant traces to a measured 403 without it"). It is also the one
   capability in the whole policy that destroys data irreversibly: `DELETE
   secret/metadata/<path>` removes the key and every version, with no
   undelete. Granting it buys nothing and costs the only unrecoverable
   action in the set.
2. It contradicts Requirement 2, which lists `delete_all_versions` as a
   field that would force the grant to widen. `delete` is exactly what that
   field needs, and it is already granted.

### P4. Eval row 3 tests the metadata grant - BREAKS (self-certifying)

This follows from P3 and it is the headline finding. Row 3's Input is
"`terraform destroy -target` one disposable `vault_kv_secret_v2` in this
root, then re-apply", and its Expected says "Destroying a KV2 secret removes
its metadata, which is the only reason `delete` is in the grant. If this
fails, the grant is wrong."

That row passes identically with the metadata block set to `["read"]`, to
`["read","list","delete"]`, or to full CRUD, because the destroy never
reaches the metadata endpoint. **It cannot fail on the thing it exists to
test.** The eval's own opening paragraph says every denial row is written so
that a policy granting too much fails a row rather than passing one; this
row does the opposite for the only capability whose justification is
disputed.

Second defect in the same row: it names "one **disposable**
`vault_kv_secret_v2` in this root". There is none. All 13 carry live service
credentials (`secrets.tf:1,11,22,31,42,53,62,79,94,105,117,128,137`), every
one consumed by a Nomad job template. A `-target` destroy soft-deletes the
current version, so any template render during that window gets a 404. That
is a real, if brief, service risk, and plan:200 says flatly "No secret is
rotated. No cluster service restarts." Row 2 ("Make a real change to one
`vault_kv_secret_v2`") has the same tension. Name the target resource and
name the window in the risk section, or make the row use a scratch secret
created and destroyed for the probe.

### P5. `list` on metadata and `patch` on data are needed - BREAKS

Neither has a caller anywhere in the applications root's provider surface.

- **`list`**: no code path in `resource_kv_secret_v2.go` calls `List`. The
  read is `client.Logical().Read(metadataPath)` (`:346`), a GET, covered by
  `read`. The ephemeral resource never reads metadata at all: it builds
  `fmt.Sprintf("%s/data/%s", mount, name)`
  (`internal/vault/secrets/ephemeral/kv_secret_v2.go:199`) and takes
  `custom_metadata` from the data response (`:57-61`). No
  `vault_kv_secrets_list_v2` data source exists in this root.
- **`patch`**: the create and update path is `util.RetryWrite`
  (`resource_kv_secret_v2.go:244`), which is `client.Logical().Write`
  (`util/util.go:436`), a POST. The provider issues no PATCH for this
  resource type.

So the measured-minimal policy for this root is:

```hcl
path "auth/token/create"         { capabilities = ["create","update"] }
path "secret/data/default/*"     { capabilities = ["create","read","update","delete"] }
path "secret/metadata/default/*" { capabilities = ["read"] }
```

The plan run that reached `No changes` cannot distinguish this from the
granted set, because a superset always plans clean. Requirement 6 removes
each of the **three path blocks** in turn, which is blind to capability
breadth, and eval row 7 asserts the metadata block carries "`read`, `list`,
`delete`", so it locks the over-grant in rather than catching it. The
ticket's entire value proposition is that the grant is provably minimal, and
three of its six capabilities are not.

### P6. "There is no path from it to more privilege" - BREAKS

Plan:91-93. The Vault-native surface is genuinely closed (P7, P8 below), but
the read grant itself carries the path. `secret/data/default/*` includes
`secret/data/default/vault/operator`, which is **the human operator's Vault
userpass password**, written by the infrastructure root at
`deployments/infrastructure/secrets.tf:121-135` (`name =
"default/vault/operator"`, `password = random_password.operator.result`) and
the same value written to the userpass user at `auth_userpass.tf:28-36`.
Live, `vault list secret/metadata/default` returns `vault/` among 19
prefixes.

So a leaked applications deployer token reads that password and logs in as
`operator`, acquiring whatever that entity holds. Today that is nothing:
`identity/entity/name/operator` returns `policies: []` and one group, and
`vault_identity_group.smoke` sets `policies = []` (`oidc.tf:92-97`).
Verified live. But F11 attaches `human-read` to a `humans` group containing
that entity, and after F11 lands the deployer inherits it by reading a
secret it is allowed to read. Requirement 4 forbids attaching the deployer
policy to the human, which is the right instinct; this is the same merge
arriving from the other direction, and no probe in the eval can see it.

The same grant also reaches `default/postgres/localstack` (Postgres
superuser), `default/minio/localstack` (MinIO root), `default/grafana/admin`,
`default/backup-*/gcs` (GCS service-account keys) and `default/haproxy/tls`
(the cluster's TLS private key, per `acme.tf:44`). Those are lateral rather
than Vault-privilege, but the ceiling section should name them.

**The fork this hides.** Q4 asks only whether to *split the prefix by root*
and rejects it because that would rename live secret paths. It never
considers the option that renames nothing: enumerate the sub-prefixes this
root actually touches. From `secrets.tf` and `services.tf:11,16,212` those
are `postgres/`, `minio/`, `phoenix/`, `memex/`, `loki/`, `mlflow/`,
`hermes/` and `bifrost/`. Eight path blocks instead of one, no rename, and
`vault/`, `grafana/`, `openfang/`, `prometheus/`, `acme/`, `haproxy/` and
both `backup-*` prefixes drop out of reach, including the human credential.
The cost is that adding an app means editing the policy in the other root.
That is a real trade and it belongs in Open Questions with a recommendation,
not settled by an argument against a different option.

### P7. `auth/token/create` cannot mint a token above its own policies - HOLDS

Answering the operator's fourth question, verified in `hashicorp/vault` at
tag **v2.0.3**, `vault/token_store.go`:

- `:3035-3041` - `case !isSudo:` compares sanitized requested policies
  against the parent's and returns "child policies must be subset of parent"
  on any excess.
- `:3099-3103` - an orphan token needs root or sudo.
- `:3155-3166` - a periodic token needs root or sudo.

The grant is `["create","update"]` with no `sudo`, so all three checks bind.
`auth/token/create/<role>` is a different path and the grant carries no
glob; live, `vault list auth/token/roles` returns "No value found", so no
role exists to abuse anyway. A child also dies with its parent, which keeps
Requirement's reversibility claim honest. **No over-grant here.**

### P8. The four escalation probes cover the surface - PARTIALLY HOLDS

For Vault-native escalation, yes, and I could not construct a fifth. I
checked the whole reachable surface: `default` grants no `auth/token/create`
(read live, confirming plan:70-78), and its remaining paths are self-scoped
(`lookup-self`, `renew-self`, `revoke-self`, `capabilities-self`,
`cubbyhole/*`, the wrapping trio, `identity/entity/id/{{identity.entity.id}}`
read-only, `identity/oidc/provider/+/authorize`). None of those plus the
three grants composes into privilege. `default-ceiling` adds two reads.

The fifth route is the credential-mediated one in P6, and it is invisible to
all four probes because every one of them tests a Vault write the token does
not hold. A probe that would catch it: as the deployer token, read
`secret/data/default/vault/operator` and confirm it **succeeds**, then state
in the docs what that means. Expected to pass, and recording it is the
point, exactly as F13's Requirement 8 does for its residual.

### P9. The eval's proof token is well defined - BREAKS

Rows 1, 3 and 5 say "Mint a token holding only the ticket's three path
blocks", which means `vault token create -policy=deployer-applications`. By
P7's subset rule, only a token that already holds that policy, or root, can
mint it. The Definition of Done says "The root token is not used at any
point in the proof" (plan:241-242). So the minting route contradicts the
DoD, and the only consistent route is `vault login -method=userpass` as the
new identity.

That route fails eval row 9 as written. Q2 settles the policy onto the
entity directly, and Vault reports entity-derived and group-derived policies
in a **separate field**: `token_store.go:3482` sets `"policies": out.Policies`
while `:3546-3556` sets `resp.Data["identity_policies"]`. A userpass login
token whose entity carries `deployer-applications` therefore looks up as
`policies: ["default"]`, `identity_policies: ["deployer-applications"]`. Row
9 requires `policies` to be exactly `["default","deployer-applications"]`,
so the correct implementation fails the row and the incorrect one (mint with
the root token) passes it.

Downstream of that: **no row exercises the identity at all.** The userpass
user, entity and alias are Requirement 4 and half the Code surface, and the
eval proves only that *a token carrying the policy* works. An entity with
the policy misattached, an alias bound to the wrong mount accessor, or a
user that cannot log in all pass every row. Add a row that logs in as the
deployer and checks `identity_policies`, and drive the plan and apply rows
from that token.

Row 9's Input has a second trap inherited from my last pass's fix: "unset
`VAULT_TOKEN`, then `vault token lookup` on the token under test". With
`VAULT_TOKEN` unset, `vault token lookup <token>` hits `auth/token/lookup`,
which `default` does not grant (only `lookup-self`), and otherwise falls
back to `~/.vault-token`. Specify `VAULT_TOKEN=<candidate> vault token
lookup -format=json` so it is a lookup-self.

### P10. Eval row 10's negative controls can fire - BREAKS

The control for the bootstrap rows is "the bootstrap-mount probes against a
token granted `secret/data/bootstrap/*` read". That path is under the
`secret` mount, not the `bootstrap` mount. Live, `vault secrets list
-format=json` shows `bootstrap/` is its own `kv` mount with
`{"version":"2"}`, so the control token needs `bootstrap/data/*` read (and
`bootstrap/metadata/*` list for the `kv list` sub-probe). As written the
control is denied, and since the row's threshold is "every control succeeds
on every sub-probe" at 100%, the row cannot pass. A row that cannot pass
invites the implementer to improvise the check, which is how the last
guardrail got hollowed out.

Row 10 is otherwise the best row in the marker and the right structural
answer to F7. Fix the path and keep it.

### P11. The remaining eval rows can fail - HOLDS

Row 1 (plan), row 2 (apply, subject to P4's target problem), row 4
(minimality, at path-block granularity only, see P5), row 5 (four denials),
row 6 (bootstrap denial), row 7 (policy read, which now asserts capabilities
as I asked, but asserts the wrong set per P5), row 8 (human separation, with
the F11 state recorded, which fixes last pass's vacuity), row 11
(infrastructure root still plans), row 12 (docs rubric) all have real
failure modes. Row 8's hard-coded entity id checks out live:
`identity/entity/name/operator` returns
`351f302a-ada1-0e79-15d3-e22a4be2e3e4`.

### P12. Cited anchors resolve - HOLDS, two nits

Verified good: `deployments/applications/providers.tf:36` is `provider
"vault" {}`; `acme.tf:41` is `vault_policy.acme_tls_write`;
`auth_userpass.tf:13-17` is `vault_auth_backend.userpass`;
`auth_userpass.tf:28-56` now matches the file's true length of 54 lines only
loosely (the block is 28-54, cited twice at plan:172 and plan:210);
`.loop/config.json:2-4` is `just pre_commit`;
`.devcontainer/devcontainer.json:37-40` is the `runArgs` env-file block. The
resource inventory at plan:36-37 is now correct for the applications row (13
plus 3). The infrastructure row still says "2 policies" where `grep
'resource "vault_policy"'` returns one, and "9 KV secrets" where the count
is 11 (`secrets.tf` 7, `backup.tf` 4); the "Yes, privileged" conclusion is
unaffected.

Nit: `vault_policy.acme_tls_write` interpolates `${var.secret_mount}`
(`acme.tf:44`). The new policy's HCL is written with a literal `secret/`.
The mount is `secret` today (live `vault secrets list`), so both work, but
the precedent this ticket says it copies uses the variable.

## Most dangerous assumption

**P3 with P4: that `delete` on the metadata endpoint is load-bearing, and
that eval row 3 measures it.** If that is wrong, and the provider source
says it is, then the ticket ships an unjustified capability that is also the
only irreversible one in the policy, and it ships a guardrail that reported
the grant as proved without ever exercising it. That is the exact failure
this ticket's eval opens by promising to prevent, one level down from where
F7 committed it.

Runner-up: **P9**, because the identity is the deliverable and no row
touches it, while the row that comes closest fails against the correct
implementation and passes against the wrong one.

## Required fixes

1. **P3, P5.** Narrow the policy to
   `secret/metadata/default/*` = `["read"]` and `secret/data/default/*` =
   `["create","read","update","delete"]`, or justify `list`, `delete` and
   `patch` against a measured 403. Delete the "destroying a
   `vault_kv_secret_v2` removes its metadata" sentence at plan:68-69; the
   provider deletes `secret/data/<name>` unless `delete_all_versions` is
   true, which nothing here sets. Reconcile Requirement 2, which lists
   `delete_all_versions` as a widening trigger for a capability already
   granted. Record the mechanism from P2 as the reason `read` stays.
2. **P4.** Rewrite eval row 3. As written it passes with any metadata
   capability set. Either drop it and fold the destroy into row 2, or make
   it a capability probe: as the deployer token, run `vault kv metadata
   delete secret/default/<x>` and require **denied**, with a negative
   control that succeeds under a token that does hold metadata delete. Also
   name the concrete resource rows 2 and 3 operate on, and reconcile the
   soft-delete window with plan:200's "No secret is rotated".
3. **P5.** Make Requirement 6 and eval row 4 remove **capabilities**, not
   only path blocks, and update row 7's asserted capability set to whatever
   step 1 measures.
4. **P6.** Replace "there is no path from it to more privilege" (plan:91-93)
   with what the read grant actually reaches: the operator's Vault userpass
   password at `secret/data/default/vault/operator`
   (`deployments/infrastructure/secrets.tf:121-135`), the Postgres and MinIO
   admin credentials, the GCS backup keys and the HAProxy TLS key. Say that
   the ceiling rises when F11 gives the operator entity a policy. Add a
   probe that reads that path as the deployer and records the success.
5. **P6 fork.** Add an Open Question, with a recommendation, on enumerating
   the eight sub-prefixes this root uses instead of `default/*`. Q4 rejects
   only the rename option and never considers this one.
6. **P9.** Settle where the proof token comes from. Recommended: `vault
   login -method=userpass` as the new identity, which is the only route
   consistent with the DoD's "the root token is not used at any point". Then
   fix row 9 to assert `identity_policies` contains `deployer-applications`
   and `policies` does not contain `root` (entity-attached policies do not
   appear in `policies`: `token_store.go:3482` versus `:3546-3556`), and
   spell the check as `VAULT_TOKEN=<candidate> vault token lookup
   -format=json`.
7. **P9.** Add an eval row that exercises the identity itself: log in as the
   deployer userpass user and confirm the login resolves to
   `deployer-applications`. Without it, Requirement 4 has no coverage.
8. **P10.** Fix row 10's bootstrap negative control to grant
   `bootstrap/data/*` read and `bootstrap/metadata/*` list. `bootstrap/` is
   its own KV v2 mount; `secret/data/bootstrap/*` is a path that does not
   exist.
9. **P1, P12.** Add one line saying F13 moves this policy resource out of
   Terraform into Ansible, so Requirement 3 is not read as the end state.
   Correct the infrastructure inventory row ("9 KV secrets, 2 policies" is
   11 and 1), and cite `auth_userpass.tf:28-54`.

## What is good and should survive

The rescope is the right call and the applications half genuinely stands
alone. The `auth/token/create` finding is correct, non-obvious, and I
confirmed both halves of it: `default` does not grant it, and the subset
rule means holding it grants nothing further. Q1's AppRole premise is now
honest. The metadata narrowing was the right direction even though it did
not go far enough, and the reasoning about where `custom_metadata` actually
lives is now correct. Row 8 records the F11 state instead of passing
vacuously, row 9 scores `policies` instead of `display_name`, row 7 scores
the applied policy instead of the source file, and row 10 exists at all.
Those are the fixes from the last pass and they all landed.
