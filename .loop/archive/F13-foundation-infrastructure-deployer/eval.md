eval: F13-foundation-infrastructure-deployer

**Definition of Done:** `deployments/infrastructure/` plans and applies clean
under an identity holding no `sys/policies/acl` grant, and the two-step
escalation chain fails at its first step. The three ACL policies are owned by
an Ansible playbook that `just bootstrap` actually runs, and `acme-tls-write`
was live throughout the move. The docs state the identity is scoped and **not**
least-privilege, record the residual ceiling and what raises it, and name the
follow-up that would close it. The root token is not used in the proof.

**The failure this ticket exists to close is two steps, not four.** Vault
resolves identity-group policies at request time. A token that can write any
ACL policy and can write identity groups rewrites a policy to `path "*"`, then
adds its own entity to a group carrying it. No new auth mount, no new user, no
re-login. Narrowing `sys/policies/acl/*` to exact names closes the direct
self-rewrite and leaves this chain wide open, which is why the deliverable is
the policy **move**, not a narrower glob. Rows 5 and 6 are the closure.

**The second failure is the move leaving a gap.** `acme-tls-write` is live and
the ACME renewal depends on it. A `terraform state rm` ordered wrongly, or a
playbook that never runs, deletes it. Rows 1, 2 and 9 check the move from both
ends.

**The third failure is a guardrail that certifies the escalation green — F7's
defect, twice.** Every denial row below has a negative control in row 11, and
row 6 deliberately *expects success* because the plan claims a bounded residual
and an unrun probe is an unsupported claim.

| Behavior | Input | Expected | Scorer | Threshold |
| --- | --- | --- | --- | --- |
| **The three policies exist under Ansible, with the right rules** | Run the new playbook on a cluster where Terraform has **not** created them (or after step 2's `state rm`). Then `vault policy read` each of `acme-tls-write`, `human-read`, `deployer-applications` | All three exist and their rules match what the Terraform resources granted, byte for byte after whitespace normalization. Compare against the pre-move `vault policy read` output captured in step 1, not against the `.tf` source | deterministic check (all three present, rules equal to the captured baseline) | 100% |
| **`acme-tls-write` was live at every step of the move** | Capture `vault policy read acme-tls-write` before step 1, after step 1, after the `terraform state rm`, and after the resource block is deleted | It exists and is unchanged at all four points. A window where it exists in neither owner breaks ACME renewal, and the symptom appears weeks later at certificate expiry | deterministic check (present and identical at all four captures) | 100% |
| **Removing the resources proposes no destroy** | After `terraform state rm` and deleting the blocks: `terraform plan` in `deployments/infrastructure/` | No destroy is proposed for any policy. A plan that wants to delete `acme-tls-write` means the `state rm` did not take, and applying it would remove a live policy Ansible now owns | deterministic check (plan proposes zero destroys, and none naming a policy) | 100% |
| **The root plans and applies under the scoped identity, after the move** | With `VAULT_TOKEN` set to the new identity's token and nothing else: `terraform plan`, then a real change and `terraform apply`. Keep the root token in a second shell in case the apply sticks | Both clean. **The 19-path policy in the plan was measured before the move**, with four `sys/policies/acl` lines present; this row proves the remainder is sufficient without them. Apply matters separately: this root sets `custom_metadata` 10 times, which writes the metadata endpoint and which no plan exercises | deterministic check (plan and apply both exit 0, no 403) | 100% |
| **Denial: the two-step chain fails at step one** | As the new identity, attempt to write **each** policy that exists — `acme-tls-write`, `human-read`, `deployer-applications`, `default-ceiling`, `nomad-workloads` — with a body granting `path "*"` | Every write denied. Not a sample: the chain needs only one writable name, so a policy list checked partially is a chain checked not at all | deterministic check (every write non-zero with "permission denied") | 100% |
| **The residual ceiling is exactly what the docs claim** | As the new identity: create an identity group carrying an existing policy (`acme-tls-write`) with the identity's own entity as a member. Then read back what the group grants. Clean up both objects afterwards | **This is expected to SUCCEED.** The plan claims the ceiling is the union of existing policies, none root-equivalent today. That claim is unsupported until someone runs it. Record the result and confirm the resulting capability is bounded by `acme-tls-write` and does not reach `root` | deterministic check (group creation succeeds, resolved capability is `acme-tls-write` and not root, objects cleaned up) | 100% |
| **The applied policy carries no `sys/policies/acl` grant at all** | `vault policy read deployer-infrastructure` | No path under `sys/policies/acl`, not even `list`. This is the single line the ticket turns on. Scored on the applied policy, not the playbook source, so a task that failed silently is caught | deterministic check (no `sys/policies/acl` path in the applied policy) | 100% |
| **Denial: the identity cannot reach the founding credentials or unseal** | As the new identity: `vault kv list -mount=bootstrap /`; `vault read sys/raw/core`; `vault write sys/unseal key=x`; `vault read sys/audit` | All four denied. These are the capabilities that separate "scoped" from "root" and the docs claim them, so they are checked rather than assumed | deterministic check (all four non-zero, "permission denied") | 100% |
| **The playbook actually runs** | Fresh `just bootstrap` on a tree where the policies have been deleted from Vault by hand | All three policies come back. `bootstrap/justfile:40-49` names each playbook explicitly, so one that is written but not listed is a silent no-op — the policies survive only because Terraform made them before the move, and the next clean bootstrap has none | deterministic check (all three present after `just bootstrap`, with the policies deleted beforehand) | 100% |
| **Guardrail: the proof did not run on the root token** | Before each of row 4's runs: `unset VAULT_TOKEN`, then `vault token lookup` on the token under test | Its `policies` list contains `deployer-infrastructure` and does not contain `root`. **Check `policies`, not `display_name`** — a token from `vault token create` reports `display_name: token` whatever policy it holds. `VAULT_TOKEN` outranks `~/.vault-token` and `.devcontainer/devcontainer.json:38` injects the root token into every shell | deterministic check (`policies` contains `deployer-infrastructure`, excludes `root`, on both runs) | 100% |
| **Guardrail: the denial rows can actually fire** | Negative controls. Run row 5's policy writes against the root token, and row 8's four probes against the root token | Every control succeeds where the real row denies. A denial checker that reports "denied" unconditionally passes rows 5 and 8 vacuously. F7 failed twice on exactly this shape, and its guardrail read the HCL instead of running the probe | deterministic check (every control succeeds on every sub-probe) | 100% |
| **The docs claim only what was proved** | Read the new documentation section | It names the identity and what this root needs, says plainly that it is scoped and **not** least-privilege, records the residual ceiling from row 6 **with that row's actual result**, states that the ceiling rises whenever a privileged policy is added — including by editing the new playbook — and names the follow-up that would close it by moving `identity/entity` and `identity/group` out of Terraform. The phrase "least privilege" must not appear anywhere near this identity | model + rubric (adversarial review agent) | 4/5 |
