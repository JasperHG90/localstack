eval: F11-foundation-human-read-role

**Definition of Done:** `vault login -method=userpass username=operator`, and
from that session alone: both Terraform roots plan and apply clean **including
a mount-description change**, both brokered tokens are readable, a user and a group can be created and removed,
and every secret under `default/` is readable. From the same session the
`bootstrap` mount, `sys/audit` and `vault operator key-status` all refuse.
**The credential under test is never the root token**; the root token appears
only as the negative control proving those denials can fire.

**Every Terraform row needs a Consul token too.** Both roots keep state in
Consul, so a Vault token alone cannot plan either one — broker it with
`vault read consul/creds/deploy` from the session under test and pass it as
`CONSUL_HTTP_TOKEN`. That is a prerequisite of the rows, not a gap in the
policy, and forgetting it looks like a policy failure.

**The failure that matters is a proof that ran on the root token.**
`VAULT_TOKEN` outranks `~/.vault-token`, and `.devcontainer/devcontainer.json:38`
injects the root token into every shell. A probe that forgets to clear it
passes every row and proves nothing. The last row is the guard, and it asserts
`identity_policies` — the group carries the policy, so it does NOT appear in
`policies`, and a row demanding it there fails every correct build.

**The second failure is a plan-only proof**, and its worst form produces no
error. Mount paths are exact-match, so `sys/mounts/secret` does not cover its
own `/tune` subpath — that one 403s honestly. The auth mount does not: denied on
`sys/mounts/auth/<path>/tune` the provider exits 0, reports `changed`, leaves
live untouched and writes the value into state. Rows 1 and 2 are therefore
applies, they **name the changes** rather than leaving "one real change" to the
tester, and they score by **comparing live against config** rather than by
looking for a 403 that never appears.

**Probes that write to the live cluster restore what they overwrote.** Two
mount descriptions were left drifted this way on 2026-08-01 and had to be put
back by hand.

**This eval does not test containment.** The `developer` group can grant itself
anything short of `root`; that is the operator's decision, recorded in the
plan. **There is no access boundary at all**: a `developer` writes a policy,
attaches it to their own group and re-logs in, reaching `sys/audit` and the
`bootstrap` mount in three commands. The two denial rows record what the policy
*as written* refuses, which is a weaker claim, and the docs row forbids
upgrading it. Both were narrowed after `sys/raw` and `sys/unseal` turned out to
be untestable here for reasons unrelated to this policy.

| Behavior | Input | Expected | Scorer | Threshold |
| --- | --- | --- | --- | --- |
| **The infrastructure root runs, including BOTH mount tunes** | From the login session: `terraform plan` in `deployments/infrastructure/`, then change the `description` on **`vault_mount.kvv2`** and on **`vault_auth_backend.userpass`**, `terraform apply`, then revert both and apply again. Keep the root token in a second shell in case the apply sticks | Both applies clean **and the live descriptions actually match the config afterwards**. Score by reading `sys/mounts/secret/tune` and `sys/mounts/auth/userpass/tune` back from Vault and comparing to the `.tf` — **not** by looking for a 403. Denied on the auth tune the provider exits 0, prints `changed`, leaves live untouched and writes the value into state; there is no 403 and no audit device here to see it. Both changes are named because mount paths are exact-match and each tune is a separate endpoint | deterministic check (both applies exit 0 AND live descriptions equal the `.tf` values after each apply) | 100% |
| **The applications root runs** | Same session: `terraform plan` in `deployments/applications/`, then change one `vault_kv_secret_v2` value and `terraform apply`, then revert | Both clean, and the secret's live value matches the config after each apply. One policy serves both roots; this is what collapsing Developer and Deployer bought. This root has no mount of its own, so the tune trap does not apply. **Expect a job restart** — Nomad's default `change_mode` is `restart`, so pick a secret whose consumer tolerates one | deterministic check (plan and apply exit 0; live secret equals config) | 100% |
| **Guardrail: `auth/token/create` is load-bearing** | Re-run row 1's plan with `auth/token/create` removed from the policy. **Remove it by applying a trimmed `vault_policy.developer`, not by hand** — measured safe, because both token mints precede the policy write, so the apply does not half-complete. **Before running it, note the recovery step**: with that grant gone Terraform cannot restore its own policy — every apply dies at the first resource for want of it — so recovery is a hand `vault policy write`, the one sanctioned exception to Requirement 3 | It fails **once per resource**, each error carrying a resource address, all after `Refreshing state...`. **Not** a single failure before the graph is read: the provider builds its client lazily on first use (`setClient` opens `if p.client != nil { return nil }`; `ConfigureFunc: NewProviderMeta` builds nothing), so a scorer expecting "fails at provider configure" fails every correct build. The live `default` policy does not grant this path and it appears in no `vault_*` resource block | deterministic check (plan fails with per-resource errors after refresh begins, then the hand-restore recovers it) | 100% |
| **`localstack login` can broker both tokens** | Same session: `vault read nomad/creds/deploy` and `vault read consul/creds/deploy`, then use each against its service | Both return usable tokens. This is the capability `D2` is blocked on; without it `login` authenticates and every broker call 403s | deterministic check (both reads exit 0, and each token authenticates to its service) | 100% |
| **A developer can onboard a person** | Same session: create a `userpass` user, create an identity group carrying an existing policy, add the user's entity to it, then delete all three | Every step succeeds. This is the "create users & groups, assign users" the operator asked for. Clean up every object | deterministic check (all steps exit 0, nothing left behind) | 100% |
| **Every secret under `default/` is readable** | Same session: `vault kv list -mount=secret default`, then `vault kv get` on one key from each top-level prefix | All succeed, and the listing matches what the root token sees. Do not assert a key count — it changes whenever a secret is added | deterministic check (listing equals the root token's listing; every sampled get exits 0) | 100% |
| **The applied policy matches the plan's** | `vault policy read developer` | Byte-for-byte the path set in the plan, after whitespace normalization. Scored on the applied policy, never the `.tf` file, so a hand-edit or a partial apply is caught | deterministic check (applied policy equals the plan's path set) | 100% |
| **What the policy as written refuses: the bootstrap mount** | Same session, **without first self-granting**: `vault kv list -mount=bootstrap /` and `vault kv get -mount=bootstrap <any key>` | Both denied. `bootstrap/` is a separate KV mount, not a subtree of `default/`, and it holds the cluster's founding credentials. **This is not a boundary** — the same session reaches it by writing a policy, attaching it to its own group and re-logging in. The row records what the policy says, nothing more | deterministic check (both non-zero, "permission denied", with no self-grant performed first) | 100% |
| **What the policy as written refuses** | Same session, **without first self-granting**: `vault read sys/audit` and `vault operator key-status` | Both denied. **This row records what the policy says, not a boundary** — the same session can write a policy, attach it to its own group, re-login and reach both. The docs row below enforces that distinction. **Do not probe `sys/unseal`**: it is unauthenticated, so the token reaches it and fails on the key argument, passing for the wrong reason. **Do not probe `sys/raw`**: this cluster sets no `raw_storage_endpoint`, so it 404s even for `root` and neither the row nor its control can discriminate | deterministic check (both non-zero, "permission denied", with no self-grant performed first) | 100% |
| **Guardrail: the denial rows can actually fire** | Negative controls: run the `bootstrap`-mount and operational-surface probes against the root token | Every probe succeeds. A denial checker that reports "denied" unconditionally would pass both denial rows vacuously — the exact defect that failed this ticket's predecessor twice. This is also why `sys/raw` was dropped: its control cannot succeed either, so it could never have discriminated | deterministic check (every control succeeds on every sub-probe) | 100% |
| **Guardrail: the proof did not run on the root token** | Before every row: `unset VAULT_TOKEN`, then `vault token lookup` | `identity_policies` contains `developer`, `policies` is `[default]`, and `display_name` is `userpass-operator`. **Assert `identity_policies`, not `policies`** — the group carries the policy, so under group binding it lands in `identity_policies` and `policies` holds only `default`. A row demanding `developer` in `policies` fails every correct implementation. Note also that `vault login -format=json` reports the merged set while `vault token lookup` splits them | deterministic check (`identity_policies` contains `developer`; `policies` excludes `root`; on every run) | 100% |
| **The docs claim only what was proved** | Read the new section of `docs/vault-human-auth.md` | It states what `developer` grants, says plainly that a developer can grant themselves anything short of `root` and that this was a deliberate choice, names the one thing the credential buys over the root token — it is per-person and can be revoked by removing it from the group — and says plainly that it is **not** an access boundary: a `developer` reaches `sys/audit` and the `bootstrap` mount in three commands. It states that no audit device is enabled, so there is no attribution yet. It points at `F14` for the rest of the taxonomy and `D5` for breakglass. The phrase "least privilege" must not appear, no claim of audit attribution may appear, and the denial row above must not be described as a boundary | model + rubric (adversarial review agent) | 4/5 |

signed-off-by: JasperHG90 2026-08-01
