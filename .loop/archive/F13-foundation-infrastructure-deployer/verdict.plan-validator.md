---
verdict: fail
---

# F13 plan review: premise BROKEN

Plan: `/home/vscode/workspace/.loop/plans/F13-foundation-infrastructure-deployer.md`
(sha256 `b140bfc7b4ccbab0f34c63450294e6011a79a764dda9c4d5cb8d236599a68859`,
confirmed by `sha256sum`).
Eval: `/home/vscode/workspace/.loop/evals/F13-foundation-infrastructure-deployer.md`

**Premise verdict: BROKEN.** The plan closes the two-step chain it names and
leaves a different chain of the same length open. That chain ends at the Vault
root token, needs no `sys/policies/acl` grant, and becomes reachable exactly
when F13's own dependency F11 lands. The eval's residual row cannot discover it.
This is F7's defect one level up: the guardrail certifies the residual green.

No `plan:` line above, so this verdict cannot authorize the flip to `ready`.

---

## Assumptions, attacked

### P1. The escalation is "write a policy, then attach it via a group", and
### removing all policy-write closes it. HOLDS for that chain, BREAKS as a class.

The named chain is real and the fix closes it. Confirmed in the Vault 2.0.3
binary at `/usr/bin/vault`: `policies cannot contain root`,
`auth methods cannot create root tokens`, and
`root tokens may not be created without parent token being root`. So the three
obvious "just attach `root`" routes are compiled shut, and with no writable
policy the token cannot manufacture a privileged one. That much of the plan is
sound.

But the plan treats "identity-group write" as the lever. It is not the only
one. The same 13-path policy grants
`path "auth/userpass/users/*" { capabilities = [... "create","update" ...] }`
(plan `:68`). Creating a userpass user with `token_policies=[X]` and a chosen
password, then logging in at the unauthenticated `auth/userpass/login/<user>`,
mints a token carrying policy `X` in one step, with no identity object at all.
`auth/jwt-nomad/role/*` (plan `:67`) is a third lever. The plan's Q1 frames the
choice as binary (keep group write or lose `vault_identity_group.smoke`), and
Requirements 7 and 8 probe only the group route. Two equivalent levers go
unprobed.

### P2. "Leave the token no writable policy at all" means it cannot reach root.
### BREAKS. This is the finding that sinks the plan.

The post-move policy keeps two grants that are not policy grants and are not
identity grants:

```
path "nomad/role/*"     { capabilities = ["create","read","update","delete"] }
path "consul/roles/*"   { capabilities = ["create","read","update","delete"] }
```
(plan `:70-71`, required by `deployments/infrastructure/nomad_deploy_role.tf:36`
and `consul_deploy_role.tf:19`)

Measured against the live cluster today:

1. `vault read nomad/config/access` returns `address http://127.0.0.1:4646`.
   The stored credential is the **Nomad bootstrap token**, written by
   `bootstrap/roles/nomad_server/tasks/main.yml:293-303`
   (`token="{{ nomad_bootstrap_token }}"`). A management token.
2. `vault read nomad/role/deploy` returns `type client, policies [deploy]`.
   `type` is a writable field on `nomad/role/<name>`, which the deployer holds
   full CRUD on. Writing `type=management` is one request.
3. The deployer needs a read on `nomad/creds/<role>`. Its own policy has none.
   F11 supplies it: `.loop/plans/F11-foundation-human-read-role.md:145` grants
   `human-read` the path `nomad/creds/read`. The deployer mints itself a token
   carrying `human-read` by either lever in P1, because `human-read` is an
   existing policy and attaching an existing policy is exactly the residual the
   plan already concedes.
4. `vault read nomad/creds/read` now returns a **Nomad management token**.
5. `nomad node status` shows `firebat` as an eligible client node.
   `bootstrap/inventory/cluster.ini:1-3` shows `firebat` is the `[manager]`,
   the host holding `/opt/vault/init.json`.
   `bootstrap/roles/nomad_server/templates/nomad.hcl.j2:72-85` enables
   `nomad-driver-podman` with `volumes { enabled = true }` **and** `raw_exec`
   with `enabled = true`. `bootstrap/playbooks/configure_podman.yml:101`
   writes registry credentials to `/root/.config/containers`, labelled
   "for root (Nomad Podman driver)", so the driver drives rootful podman.
6. A job placed on `firebat` bind-mounts `/opt/vault` and reads `init.json`
   (`bootstrap/roles/vault_server/tasks/main.yml:117-122`, `owner: vault,
   mode: '0600'`, readable by root). That file's `root_token` field is the
   Vault root token, as
   `bootstrap/playbooks/seed_vault.yml:16-18` itself demonstrates.

Steps 1 through 4 are three Vault writes and one read. No `sys/policies/acl`
path is touched at any point. The same shape runs through
`consul/roles/*` plus `human-read`'s `consul/creds/read`
(`F11...md:146`) to a Consul token, and Consul is Vault's storage backend
(`vault status` reports `Storage Type consul`).

The Definition of Done says the identity "cannot escalate back to" the root
token. As specified, it can.

### P3. "Excluding `root`, none is root-equivalent, so today the ceiling is low."
### BREAKS at the moment this ticket can ship.

`vault policy list` today returns exactly what the plan says: `acme-tls-write`,
`default`, `default-ceiling`, `nomad-workloads`, `root`. I read all four
non-root policies. None grants `nomad/creds/*` or `consul/creds/*`, so the
sentence is true of today.

It is not true of the day F13 ships. `loopctl ledger` shows
`F13 ... deps: F11-foundation-human-read-role, F12-foundation-deployer-privilege-split
(2 unmet)`. F13 cannot ship before F11, and F11 creates `human-read`, the
missing link in P2. The plan itself lists `vault_policy.human_read` in
Requirement 1 as one of the policies it moves, so it knows the policy exists.
The residual paragraph (`:98-115`) reasons about the wrong policy set: today's,
not the ticket's own.

A second gap in the same paragraph: it treats a policy as its literal text.
`nomad-workloads` is templated on
`identity.entity.aliases.auth_jwt_649fd6cc.metadata.nomad_namespace` and
`.nomad_job_id` (read live). Its effective grant depends on alias metadata,
and the deployer holds `auth/jwt-nomad/role/*` write, which controls
`claim_mappings` and therefore alias metadata. I did **not** establish that
this is exploitable, and I did not mutate the cluster to try. Marking it
UNCERTAIN, but the plan's "union of every ACL policy" framing has no room for
the question at all.

### P4. Group write cannot be dropped (Q1). HOLDS.

`deployments/infrastructure/oidc.tf:92` is `resource "vault_identity_group"
"smoke"` with `member_entity_ids = [vault_identity_entity.operator.id]`, and
`.loop/plans/F11-...md:203-204` puts `vault_identity_group.humans` in the same
root. Q1's conclusion stands. Its reasoning does not: dropping group write
would not have closed the escalation either, because of P1's other two levers.

Related, and unaddressed: Requirement 5 says the identity "is never attached to
the `operator` entity or F11's `humans` group". With `identity/*` CRUD the
identity can attach itself whenever it likes. That is a design intention, not a
boundary, and the plan presents it as a restriction.

### P5. An Ansible home exists. HOLDS. Every anchor resolves.

- `bootstrap/playbooks/seed_vault.yml:11-28` is exactly the shape claimed:
  `slurp` of `/opt/vault/init.json`, `set_fact` parsing `.root_token`, then a
  `vault` command with `VAULT_ADDR`/`VAULT_TOKEN` in `environment`.
- `bootstrap/playbooks/enable_consul_secrets.yml:15-22` is the same pattern,
  and `:39-58` shows a Consul ACL policy authored in Ansible with
  `token: "{{ master_consul_token }}"` at `:58`, as cited.
- `bootstrap/justfile:40-49` is the `bootstrap:` recipe, naming nine playbooks
  explicitly. The silent-no-op risk the plan flags is real.
- `bootstrap/roles/nomad_server/tasks/main.yml:189-196` reads
  `/opt/vault/init.json` and parses `root_token`. The plan cites `:190-195`,
  off by one at each end; it resolves.
- `deployments/infrastructure/consul_deploy_role.tf:5-15` records the
  Ansible-owns-Consul-policies invariant; the plan cites `:5-14`, close enough.
- `nomad_deploy_role.tf:13` is `resource "nomad_acl_policy" "deploy"`, so the
  "do not assume symmetry" warning is correct.

### P6. Requirement 4's ordering is gap-free for `acme-tls-write`. HOLDS.

Walking the sequence: subticket 1 writes the identical policy from Ansible
while Terraform still owns it, so an apply in that window is a no-op.
`terraform state rm` then leaves config-without-state, so a plan in *that*
window proposes a **create**, not a destroy, and applying it rewrites the same
bytes. After the block is deleted, nothing is proposed. No window deletes the
policy. Eval row 2's four capture points cover it.

Two things the ordering does not cover, neither fatal:

- `acme.tf:87` reads `token_policies = ["nomad-workloads",
  vault_policy.acme_tls_write.name]`. The `state rm` and the config edit must
  land in one commit or `terraform plan` fails on an unresolved reference. The
  code surface says "anything referencing it moves to a literal name" but the
  subticket ordering implies `state rm` first, which reads as two steps.
- The policy body interpolates `${var.secret_mount}` (`acme.tf:45`). Ansible
  has no access to that variable and must hardcode `secret`. Silent drift if
  the variable ever changes. The eval handles the *comparison* correctly
  (row 1 compares against captured `vault policy read` output, not the `.tf`
  source), but the plan never names the coupling.

### P7. Exactly three `vault_policy` resources move. BREAKS.

Four policies must be Ansible-owned, not three. `deployer-infrastructure` is
the fourth: it cannot stay a `vault_policy` resource, because the identity
would then hold `sys/policies/acl/deployer-infrastructure` write and rewrite
itself, which is the whole point of the ticket. The plan half-knows this. The
code surface at `:197-199` says "**Not** the policy; Ansible owns that". But:

- Requirement 1 lists three and says "every `vault_policy` resource leaves
  Terraform" without naming the new one.
- Requirement 2 and the code surface bullet at `:191-192` both say the playbook
  carries "the three ACL policies".
- Subticket 1 says "the three policies". Subticket 3 says "the scoped policy"
  with no owner.
- Eval rows 1 and 9 check three names. Row 9 is the bootstrap-survives row, so
  as written a clean `just bootstrap` restores three policies and the
  infrastructure deployer comes back with **no policy at all**. That is the
  exact silent failure the plan's own risk section describes.

### P8. "The 19-path policy". BREAKS.

The quoted block at plan `:60-74` contains **13** `path` stanzas (counted).
The plan says the measured version also carried `sys/policies/acl` list plus
three exact policy names, which is four more, for 17. The label says 19 in the
plan (`:5`, `:58`, `:76`) and twice more in the eval (rows 4 and its preamble).
Either two measured-necessary paths were dropped in transcription or the count
is wrong. A reader cannot tell which, and the difference is a 403 during apply.
Requirement 6 would eventually surface it, but a plan that miscounts its own
measured artifact is not a reliable anchor for the implementer.

### P9. `sys/mounts/auth/*` read and `auth/token/create` are real needs. HOLDS
### (the first measured, the second taken on trust).

`vault read sys/mounts/auth/userpass` resolves on this cluster and returns
mount data including `accessor auth_userpass_ca653bd3`. The path is real and
appears in no resource block, as claimed. The provider is pinned at 5.3.0
(`providers.tf:8-9`, `~>5.3.0`; `.terraform.lock.hcl:87-89` resolves 5.3.0), so
the version the claim was measured against is the version that will run.
`auth/token/create` at provider-configure time I did not re-measure; the live
`default` policy does not grant it, which is consistent with the claim.

### P10. F11/F12 dependency ordering. HOLDS as a graph, contradicts F11 as a
### requirement.

Not circular. `loopctl ledger` puts F11 and F12 in `planning` with F13
depending on both. Citing resources that do not exist yet is legitimate here,
and Requirement 1's "grep at implementation time" is the right hedge.

But F11 Requirement 6 (`.loop/plans/F11-...md:179-182`) reads: "**The Vault
policy is created by Terraform in the infrastructure root.** ... Do not apply
it with `vault policy write` by hand; that creates drift the next apply
reverts." F13 reverses that requirement for the same policy, in the same epic,
in the ticket F11 gates. One of the two has to be amended, and F13 does not say
so. "F11 and F12 may have moved" is not a resolution.

### P11. Attaching `root` is denied. HOLDS.

Binary strings confirm all three guards (see P1). The plan's measurement is
consistent with the shipped code.

---

## Eval review

**Row 6 is a loophole, though not a dishonest one.** Recording an expected
success is the right instinct and the row's framing ("an unrun probe is an
unsupported claim") is correct. The execution defeats it:

- It probes `acme-tls-write`, whose entire body is
  `path "secret/data/default/haproxy/tls" { capabilities = ["create","update"] }`
  (read live). The most harmless policy on the cluster.
- The scorer asserts "resolved capability is `acme-tls-write` and not root".
  That passes by construction.
- The docs claim it is meant to support are about the **union** of every
  policy. Probing one member does not test a union, and the member that breaks
  the claim, `human-read`, is not probed.
- It tests only the identity-group route, missing the `auth/userpass/users/*`
  route entirely.

So row 6 cannot fail in any way that matters, and it certifies a residual
ceiling that P2 shows is unbounded. That is the shape the eval's own preamble
says it exists to prevent.

Other rows:

- **Row 5** hardcodes five policy names and omits `deployer-infrastructure`,
  the token's own policy, and `default`. The row's own text says "a policy list
  checked partially is a chain checked not at all". Enumerate from
  `vault policy list` at run time.
- **Row 9** instructs a full `just bootstrap`, which reruns
  `install_dependencies`, both `configure_hashistack_*`, `configure_tailscale`
  and `configure_network` against the live cluster (`bootstrap/justfile:41-49`).
  That is a heavy and disruptive way to test one playbook. Scope it to the new
  playbook plus a static check that `bootstrap/justfile` names it.
- **Row 10** says "`unset VAULT_TOKEN`, then `vault token lookup` on the token
  under test". After the unset, the CLI falls back to `~/.vault-token`, which
  is not necessarily the token under test. Make it explicit:
  `VAULT_TOKEN=<scoped> vault token lookup`. The `policies`-not-`display_name`
  point is correct and worth keeping.
- **Rows 1, 2, 3, 4, 7, 8, 11, 12 can fail.** Row 7 is well built: scored on
  the applied policy, not the source. Row 11's negative controls are the right
  answer to F7's defect. Row 1 correctly compares against captured
  `vault policy read` output rather than the `.tf` source, which is the only
  way to survive the `${var.secret_mount}` interpolation.
- **Missing rows:** nothing probes the P2 chain (rewrite `nomad/role/read` to
  `type=management`, or `consul/roles/read` to a management policy); nothing
  probes `auth/userpass/users/*` as a policy-minting route; nothing checks that
  `deployer-infrastructure` itself survives a bootstrap.
- The eval inherits the "19-path policy" error from the plan.
- `.devcontainer/devcontainer.json:38` is cited for root-token injection. Line
  38 is `"--env-file"` and 39 is `".devcontainer/.env"`; the claim holds, the
  anchor is one line off.

---

## Most dangerous assumption

**P2.** "No writable policy" is treated as equivalent to "no route to root".
The deployer's `nomad/role/*` write, combined with any grant of
`nomad/creds/<name>` read, converts into a Nomad management token, and Nomad on
this cluster runs rootful podman with volumes enabled on the node that stores
`/opt/vault/init.json`. F11, which F13 depends on, supplies the missing grant.
If this is right, the ticket's entire deliverable buys less than it claims, and
the docs it mandates would state a bounded ceiling that is not bounded. That is
the "failure with lasting cost" the plan's own risk section names.

---

## Required fixes before this can pass

1. **Close or explicitly bound the Nomad and Consul secret-role route (P2).**
   The residual is not "the union of existing policies". It is that union,
   *composed with* every engine role the deployer can rewrite. Either move
   `vault_nomad_secret_role` and `vault_consul_secret_backend_role` to Ansible
   alongside the policies, or drop `nomad/role/*` and `consul/roles/*` from the
   grant, or demonstrate with a probe that the chain does not complete. Do not
   settle it by assertion.
2. **Redo the residual analysis against the policy set that will exist at ship
   time** (P3): today's four, plus `human-read`, `deployer-applications` and
   `deployer-infrastructure`. Name `human-read`'s `nomad/creds/read` and
   `consul/creds/read` grants specifically, and say what they compose with.
3. **Add the P1 levers to Requirements 7 and 8, and to eval rows 5 and 6**:
   `auth/userpass/users/*` write plus unauthenticated login mints a token with
   any existing policy in one step, with no identity object. So does
   `auth/jwt-nomad/role/*` given a workload JWT. The plan currently reasons as
   if identity-group write is the only lever.
4. **Fix the count: four policies, not three** (P7). Name
   `deployer-infrastructure` in Requirement 1, Requirement 2, the code surface,
   subticket 1, and eval rows 1 and 9, and state that it must be Ansible-owned
   because a Terraform-owned self-policy reopens the self-rewrite.
5. **Fix "19-path"** (P8), or restore the two missing stanzas. Correct the eval
   in the same pass.
6. **Strengthen eval row 6** so it can fail: probe every existing policy, not
   `acme-tls-write` alone, and probe both attachment levers. Enumerate row 5's
   policy list from `vault policy list` at run time rather than hardcoding it.
7. **Fix eval row 10's token lookup** to set `VAULT_TOKEN` explicitly rather
   than unsetting it, and **scope row 9** to the new playbook plus a static
   check on `bootstrap/justfile`, not a full cluster bootstrap.
8. **Resolve the contradiction with F11 Requirement 6** (P10): say plainly that
   F13 reverses it, and either amend F11 or record that F11 ships and is
   immediately undone.
9. **Minor, in the same pass:** note that `acme.tf:87` references
   `vault_policy.acme_tls_write.name` and must become a literal in the same
   commit as the `state rm`; note that the Ansible copy must hardcode
   `${var.secret_mount}`; and drop or requalify Requirement 5's "never attached
   to ... `humans`", which `identity/*` cannot enforce against this identity.

Requirements 1 through 4, 6 and 9, the subticket ordering, and eval rows 1, 2,
3, 4, 7, 8, 11 and 12 are good work and should survive the revision unchanged.
