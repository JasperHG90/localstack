---
verdict: pass-with-required-fixes
plan: a0f550263d7b03566473b8b6587394a418aa33ec4bf909aba1f9b66cc10b7ae0
---

# Premise verdict: PARTIALLY SOUND

The two defects that failed the last pass are fixed and I re-measured both.
Eval row 3 now describes the failure shape the provider actually produces, and
I ran it end to end — removal, failure, hand restore, clean plan — on a
throwaway server. X4 has a recovery path that works. Fixes 4, 5 and 6 land.

One new inaccuracy came in with fix 1, and two accepted fixes from last pass
were never applied. All four remaining items are one-line edits; none touches
the policy path set or the code surface.

**Method.** Fresh `vault server -dev` on 127.0.0.1:8321 under a fake `HOME`,
with a file audit device, the plan's policy block loaded **verbatim** from plan
lines 55-111, bound through `identity/group name=developer` to an entity
aliased to a `userpass` login. Real `terraform init/apply/plan/import` cycles
against the repo's pinned `hashicorp/vault 5.3.0` binary copied out of
`deployments/infrastructure/.terraform/providers`, through a filesystem mirror.
Provider source re-read at v5.3.0. Live cluster: reads only (`vault audit
list`, `vault read sys/mounts/...`, `vault policy read default`). Dev server
stopped, `~/.vault-token` mtime unchanged at `2026-08-01 09:34:41` before and
after, `git status` shows no file I touched.

## Per assumption

### P1. "The provider mints a child token LAZILY, on first use per resource" (plan:55) — BREAKS on the mechanism, HOLDS on the consequence

This is the briefing's first question, and the answer is that the wording is
off in one word: **per resource**.

Measured. Four resources in state, all grants present, one `terraform plan`,
audit log truncated immediately before:

```
1 ('update', 'auth/token/create')       <- ONE mint
1 ('read',   'secret/data/default/probe/one')
1 ('read',   'secret/data/default/probe/two')
1 ('read',   'identity/group/id/71dbe9d5-...')
2 ('read',   'identity/oidc/key/probe-key')
```

Four resources, **one** child token. The mint is once per `ProviderMeta`
instance, not once per resource — and the very evidence the plan cites is what
proves it. `setClient`'s opening `if p.client != nil { return nil }`
(`internal/provider/meta.go:184-188`) is a cache guard; the source comment
three lines up says so outright: *"It should typically only need to be called
once per ProviderMeta instance."* So the sentence cites a caching guard as
evidence for per-resource minting, which is self-contradicting.

The rest of the sentence holds, and I re-measured it. With `auth/token/create`
removed, `terraform plan` over the same four resources:

```
vault_identity_group.g: Refreshing state... [id=71dbe9d5-...]
vault_identity_oidc_key.k: Refreshing state... [id=probe-key]
vault_kv_secret_v2.b: Refreshing state... [id=secret/data/default/probe/two]
vault_kv_secret_v2.a: Refreshing state... [id=secret/data/default/probe/one]

Error: failed to create limited child token: ...   (x4, each `with vault_...`)
EXIT=1
```

Four errors for four resources, each carrying a resource address, all after
refresh began. The reason is not "one mint per resource" — it is that a
**failed** mint never populates `p.client`, so the guard never trips and every
resource retries. Right consequence, wrong cause.

The other two source claims in the same comment hold verbatim:
`ConfigureFunc: NewProviderMeta` at `internal/provider/provider.go:202`, and
`NewProviderMeta` at `internal/provider/meta.go:431-439` returns
`&ProviderMeta{resourceData: d}` and builds no client. `createChildToken` sits
inside `setClient` at `meta.go:340`.

Also re-confirmed live, read-only: `vault policy read default | grep -c
auth/token/create` returns `0`, so plan:60-62 is right that `default` does not
carry it.

### P2. Eval row 3's expected result and scorer (eval:44) — HOLDS

The rewrite matches what I measured, phrase for phrase: "once per resource",
"each error carrying a resource address", "after `Refreshing state...`", and
the explicit warning that a configure-phase scorer fails every correct build.
Row 3's own copy of the mechanism is worded correctly ("builds its client
lazily on first use") — it does **not** carry P1's "per resource" slip. Last
pass's most dangerous assumption is closed.

### P3. Eval row 3 is runnable end to end, and the live cluster survives it — HOLDS, with one unnamed step

The briefing's third question. Ran the whole loop.

**Recovery works.** As the developer token, not root:

```
vault policy write developer developer.hcl      -> Success
vault policy read developer | grep -c auth/token/create -> 1
terraform plan                                   -> "no changes"  PLAN_EXIT=0
```

**Nothing is left broken.** Row 3 is a `plan`, so no live write happens inside
the failing step, and the restore is a single policy write.

**The removal step is not named, and it matters.** Row 3 says "with
`auth/token/create` removed from the policy" without saying how, and
Requirement 3 (plan:184-191) sanctions exactly one hand write — the *restore*.
Both routes work but they are not equivalent:

- Hand `vault policy write` of a trimmed policy: works (measured, as the
  developer token), but it is a **second** hand write the requirement does not
  sanction.
- `terraform apply` of a trimmed `.tf`: also works, and does not half-apply the
  root. I imported `vault_policy.developer` into the fixture and applied a
  trimmed policy alongside two other changed resources. `APPLY_EXIT=0`,
  `3 changed`. The audit order shows why:

  ```
  update auth/token/create          <- refresh walk mints
  read   sys/policies/acl/developer
  update auth/token/create          <- apply walk mints
  update sys/policies/acl/developer <- grant removed HERE, after both mints
  read   sys/policies/acl/developer
  ```

  No mint follows the removal, so the cached client carries the rest of the
  walk. Measured on a 5-resource graph; I did not prove it for a graph large
  enough to spawn another provider instance mid-walk.

One trap the plan does not mention: after a hand restore, the `.tf` must be
reverted too, or the next apply silently re-removes the grant. Eval row 7
(`vault policy read developer` equals the plan's path set) catches it, but only
if row 7 runs after row 3.

### P4. The no-boundary framing holds everywhere — HOLDS across all twelve eval rows, BREAKS at one plan line

The briefing's second question. The eval is clean now. I read all twelve rows.
Row 8 is retitled "What the policy as written refuses: the bootstrap mount" and
carries "**This is not a boundary** — the same session reaches it by writing a
policy, attaching it to its own group and re-logging in. The row records what
the policy says, nothing more." Row 9 matches. Row 12 requires the docs to say
"not an access boundary". The preamble at eval:31-38 agrees. The "one secrets
boundary" clause is gone. Fix 4 lands.

Plan prose is clean too: plan:133-150 states it plainly, the DoD is factual.

One line did not get the memo, and it is last pass's **required fix 7,
unapplied**. Plan:102-103:

```
# The KV domain this repo owns. `bootstrap/` is a SEPARATE MOUNT, not a
# subtree, so this cannot reach the cluster's founding credentials.
```

Read as a claim about the path glob it is fine. Read as a capability claim it
is false, and plan:145-148 says so twelve lines further down. This is not
harmless prose: Requirement 1 says the policy carries "exactly the paths
above", so this comment ships into `developer_group.tf`, where eval row 12's
rule against upgrading the denial into a boundary would catch it in the docs
but not in the `.tf`.

### P5. "A token holding exactly this policy and nothing else" plans both roots (plan:35-41) — BREAKS, last pass's required fix 8, unapplied

Both roots keep state in Consul, not Vault: `infrastructure/backend.tf:2` and
`applications/backend.tf:2` both declare `backend "consul" {}`. A Vault token
alone cannot read that state, so the two table rows at plan:40-41 and
Requirement 4's "from that session alone" are not achievable as written.

The capability chain exists — the policy grants `consul/creds/deploy`
(plan:110) and the brokered `deploy` Consul policy carries `key_prefix
"terraform/" { policy = "write" }`
(`bootstrap/playbooks/enable_consul_secrets.yml:43-45`) — but the plan never
tells the tester to broker it and export `CONSUL_HTTP_TOKEN`. Last pass this
blocked me from re-running the infrastructure plan at all. It blocks eval rows
1, 2 and 3.

### P6. The provider bug's root cause is recorded (plan:115-119) — HOLDS, re-verified

`vault/resource_auth_backend.go:222-225` at v5.3.0, verbatim:

```go
if callTune {
    if err := tuneMount(ctx, client, "auth/"+path, config); err != nil {
        return diag.FromErr(e)
    }
```

`e` is the nil error from `client, e := provider.GetClient(d, meta)` at
`resource_auth_backend.go:180`. `diag.FromErr(nil)` yields no diags, and the
early return also skips `authBackendRead` at :230, which is why state keeps the
config value.

The "all 17 resource types these two roots use were scanned and this is the
only one" claim holds. `grep -rhoP '^resource "\Kvault_[a-z0-9_]+'
infrastructure/*.tf applications/*.tf | sort -u | wc -l` gives exactly **17**,
every one maps to a `resource_*.go` that exists, and an AST-shaped scan for
"guard on `X`, return a different variable" across those 17 files returns one
hit: `resource_auth_backend.go:223`.

### P7. Fix 6, the honest-403 split (plan:74-77, eval:19-21) — HOLDS

Plan:74-77 now reads "The SECRET mount's tune 403s honestly at apply. The AUTH
mount's does not -- see the silent-failure section below," and the eval
preamble says the same. The half-applied contradiction is gone. Resource names
check out: `secrets.tf:2` is `resource "vault_mount" "kvv2"`,
`auth_userpass.tf:13` is `resource "vault_auth_backend" "userpass"`.

### P8. Fix 5, the eval's DoD (eval:3-9) — HOLDS in part

The root-token half is fixed: "The credential under test is never the root
token; the root token appears only as the negative control proving those
denials can fire" now agrees with plan:258-261 and with rows 1, 6 and 10.

The other half of last pass's fix 6 did not land. Eval line 4 still reads "both
Terraform roots plan and apply clean" while the plan's DoD at :253-254 says
"plan and apply clean **including a mount-description change**". Row 1 covers
the change, so this is a stale copy, not a hole.

### P9. Eval row 1's scorer is executable — HOLDS

Row 1 says to score by reading `sys/mounts/secret/tune` and
`sys/mounts/auth/userpass/tune` back. I checked those endpoints actually return
`description` (live, read-only): both do, and both currently match the `.tf`
(`KV Version 2 secret engine mount` = `secrets.tf:6`; `Human logins. Entities
created here are what OIDC assignments gate on.` = `auth_userpass.tf:16`). So
Requirement 4's restore mandate from last pass held: no drift.

### P10. Live-vs-state or live-vs-config — UNCERTAIN wording, both work

Plan:126 says "the eval compares live against state instead" and Requirement 4
(plan:197) says "comparing live against state", while eval:24-25 and row 1 both
say **config**. In the silent failure live holds the old value and state and
config both hold the new one, so either comparison catches it. Three statements
of the same rule, two of them disagreeing with the scorer that will actually
run. Last pass flagged this as optional; it is now the only place the plan and
its eval describe the same check differently.

### P11. Anchors — ALL HOLD

`acme.tf:41` = `resource "vault_policy" "acme_tls_write" {`. `oidc.tf:92` =
`resource "vault_identity_group" "smoke" {`. `oidc.tf:39` = `resource
"vault_identity_oidc_scope" "groups" {`. `auth_userpass.tf:16` is the
description line. `vars/prod.tfvars:1` = `secret_mount = "secret"`, so
`sys/mounts/secret/tune` is the right literal. `.loop/config.json:2-4` =
`"gates": ["just pre_commit"]` and the `justfile` defines `pre_commit`.
`docs/vault-human-auth.md` (5.0K) and
`.loop/plans/F14-foundation-role-taxonomy.md` (9.5K) exist.
`developer_group.tf` does not, correctly marked **(new)**. Every "Do not touch"
file exists. The eval's `.devcontainer/devcontainer.json:38` anchor lands on
the `"--env-file"` line of `runArgs`, and `.devcontainer/.env` does carry
`VAULT_TOKEN` — right mechanism, anchor one line high.

### P12. Live-cluster facts the plan leans on — HOLD

`vault audit list` still returns "No audit devices are enabled", so
plan:152-156 and the silent-failure section's "no audit device on this cluster
to see the denial" stay true. Re-confirmed the group-binding assertion eval row
11 depends on: on the fixture, `vault token lookup` gives `policies ['default']
identity_policies ['developer'] display_name userpass-operator`.

## Most dangerous assumption

**P5, the Consul credential.** Everything else on this list is a sentence that
reads wrong. This one stops the tester before eval row 1 produces a single
result: the plan asserts as measured that a token holding "exactly this policy
and nothing else" plans both roots, and both roots authenticate their state
backend to Consul. Nobody can reproduce the plan's own headline table until the
brokering step is written down. It is the second pass it has been raised.

## Required fixes

1. **Drop "per resource" from plan:55.** Measured: four resources, one
   `auth/token/create`. The mint is lazy and cached per `ProviderMeta`
   (`meta.go:184-188`, whose own comment says "once per ProviderMeta
   instance"); the per-resource *errors* happen because a failed mint never
   caches, so every resource retries. Say that. Eval row 3 already words it
   correctly and needs no change.
2. **Reword plan:102-103** so "cannot reach the cluster's founding
   credentials" reads as a claim about the path grant, not the credential —
   for example "so this path grant does not reach the `bootstrap` mount". The
   comment ships into `developer_group.tf`, and as written it is the boundary
   claim plan:145-150 forbids. (Last pass's fix 7.)
3. **Name the Consul credential in Requirement 4**: broker `consul/creds/deploy`
   and export `CONSUL_HTTP_TOKEN` before running Terraform, because both roots
   store state in Consul (`infrastructure/backend.tf:2`,
   `applications/backend.tf:2`) and the Vault policy alone does not get you a
   plan. (Last pass's fix 8.)
4. **Say how row 3 removes the grant.** Measured: a `terraform apply` of the
   trimmed policy is safe — both child-token mints precede the policy write, so
   the root does not half-apply — while a hand removal is a second hand write
   Requirement 3 does not sanction. Pick one and name it, and add that the
   restore must put the `.tf` back too, or the next apply re-removes the grant.

Cheap and worth doing at the same time:

- Make plan:126 and Requirement 4 (plan:197) say **config**, matching eval:24
  and row 1's scorer, so the same check is not described three ways.
- Add "including a mount-description change" to the eval's DoD at line 4 so it
  matches plan:253-254.
- Forward note: `vault_jwt_auth_backend` carries the same swallow
  (`resource_jwt_auth_backend.go:426`), in case F1 or F10 brings `jwt-nomad`
  under Terraform.

# What is honest and should survive

The premise is sound and this pass strengthens it again. One group covering
both roots is right; the tune fix is verified with the live value changing; the
silent failure has a named provider bug behind it, confirmed as the only one of
its kind across all 17 resource types these roots use; eval row 3 now describes
a failure I reproduced exactly and recovers from it cleanly; the no-boundary
framing is right in all twelve eval rows and everywhere in the plan but one
comment; and the restore mandate demonstrably held — the live cluster shows no
drift a day later. What is left is four sentences.
