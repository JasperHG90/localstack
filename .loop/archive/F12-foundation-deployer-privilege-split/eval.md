eval: F12-foundation-deployer-privilege-split

**Definition of Done:** `deployments/applications/` plans and applies clean
under a Vault token whose only grants are `auth/token/create`,
`secret/data/default/*` and `secret/metadata/default/*` at read/list/delete.
Removing any one of the three breaks the plan. All four escalation probes are
denied. The root token is not used at any point in the proof.

**The failure this ticket exists to prevent already happened twice.** F7's
policy was root-equivalent by a one-step self-rewrite while presented as least
privilege, and its own eval row *required* that write to succeed and then
"guarded" root-equivalence by grepping the HCL. The guardrail certified the
escalation. Every denial row here is written so that a policy granting too
much fails a row rather than passing one.

**The second failure is a policy validated by reading rather than running.**
F7's grants were derived by walking `vault_*` resource blocks, which misses
`auth/token/create` — provider 5.3.0 calls it at configure time before reading
anything, and the live `default` policy does not grant it. No amount of
re-reading the Terraform finds that 403.

**The third failure is a plan-only proof.** A plan performs no writes. This
root sets no `custom_metadata`, no `max_versions`, no `cas_required` and no
`delete_all_versions`, which is why the metadata grant is read-only plus
delete — but that is a claim about writes, and only an apply tests it.

| Behavior | Input | Expected | Scorer | Threshold |
| --- | --- | --- | --- | --- |
| **The root plans on three grants** | Mint a token holding only the ticket's three path blocks. With `VAULT_TOKEN` set to it and nothing else, run `terraform plan` in `deployments/applications/` | Reaches a clean plan with every Vault, Nomad, MinIO, Postgres and Bifrost resource refreshed. This is the ticket's central claim, and it is measured rather than read | deterministic check (plan exits 0, no 403) | 100% |
| **The root applies on three grants** | Same token. Make a real change to one `vault_kv_secret_v2` in this root, then `terraform apply`. Keep the root token available in a second shell in case the apply sticks | Applies clean. A plan writes nothing, so a metadata grant that is wrong in either direction — too narrow to delete, or needed for a write nobody predicted — passes the previous row and fails here | deterministic check (apply exits 0, no 403) | 100% |
| **The metadata grant is not silently too narrow** | With the same token: `terraform destroy -target` one disposable `vault_kv_secret_v2` in this root, then re-apply it | Both succeed. Destroying a KV2 secret removes its metadata, which is the only reason `delete` is in the grant. If this fails, the grant is wrong and the fix is `delete`, not full CRUD | deterministic check (destroy and re-apply both exit 0) | 100% |
| **Guardrail: each of the three grants is load-bearing** | Three runs of the plan, each with exactly one grant removed | Each run fails. The `auth/token/create` run fails at **provider configure**, before any resource is read — a distinct signature from the two KV runs, which fail during refresh. A policy that still passes with a grant removed is carrying privilege this ticket did not justify | deterministic check (all three fail, and the `auth/token/create` run fails at configure) | 100% |
| **Denial: the identity cannot escalate** | With the same token, run all four: `vault policy write probe-esc <file>`; `vault auth enable -path=probe-esc userpass`; `vault write identity/entity name=probe-esc policies=root`; `vault token create -policy=root` | All four denied. This is what makes the applications half a real boundary rather than a smaller pile of privilege. Clean up nothing, because nothing should have been created | deterministic check (all four non-zero with "permission denied") | 100% |
| **Denial: the identity cannot reach the bootstrap mount** | Same token: `vault kv list -mount=bootstrap /` and `vault kv get -mount=bootstrap <any key>` | Both denied. `bootstrap/` is a separate mount holding the cluster's founding credentials. The `default/`-scoped grants must not reach it, and nothing in this root needs to | deterministic check (both non-zero, "permission denied") | 100% |
| **The applied policy grants nothing outside its three paths** | `vault policy read deployer-applications` | Exactly three path blocks. No `sys/`, no `identity/`, no `auth/` other than `auth/token/create`, no wildcard at a path root, and the metadata block carries `read`, `list`, `delete` and **not** `create` or `update`. Scored on the applied policy rather than the `.tf` file, so a hand-edit or a partial apply is caught | deterministic check (applied policy matches the three blocks and contains none of the forbidden prefixes) | 100% |
| **Guardrail: the identity is not attached to the human** | `vault read identity/entity/id/351f302a-ada1-0e79-15d3-e22a4be2e3e4`, and read F11's `humans` group if it exists | Neither carries `deployer-applications`, directly or through group membership. Merging them would hand the operator KV write across the whole `default/` prefix and undo F11's central claim. **If F11 has not landed, the group does not exist and only the entity check applies** — record which case ran, so a skipped check is not mistaken for a passing one | deterministic check (`deployer-applications` appears in neither, with the F11 state recorded) | 100% |
| **Guardrail: the proof did not run on the root token** | Before the plan and the apply: `unset VAULT_TOKEN`, then `vault token lookup` on the token under test | Its `policies` list is exactly `["default", "deployer-applications"]` and does not contain `root`. **Check `policies`, not `display_name`** — a token minted with `vault token create` has `display_name: token` regardless of which policy it carries, so a display-name assertion cannot pass. `VAULT_TOKEN` outranks `~/.vault-token` and `.devcontainer/devcontainer.json:38` injects the root token into every shell, so without this row a passing plan proves only that the root token still works | deterministic check (`policies` is exactly `["default","deployer-applications"]` on both runs) | 100% |
| **Guardrail: the denial rows can actually fire** | Negative controls. Run the four escalation probes against the root token, and the bootstrap-mount probes against a token granted `secret/data/bootstrap/*` read | Every control succeeds where the real row denies. A denial checker that reports "denied" unconditionally would pass both denial rows vacuously, which is the exact shape of F7's broken guardrail | deterministic check (every control succeeds on every sub-probe) | 100% |
| **The infrastructure root still plans** | `terraform plan` in `deployments/infrastructure/` with the root token, after this ticket's resources are applied | Clean. The policy is declared in that root, so this ticket changes it, and a resource that breaks the more privileged root is not an acceptable way to secure the less privileged one | deterministic check (plan exits 0) | 100% |
| **The docs do not claim more than was proved** | Read the new documentation section | It names the identity and what the applications root needs, explains why the infrastructure root differs, states that F13 owns that half, and says plainly that the root token is **still required** until F13 lands. It does not describe the split as finished | model + rubric (adversarial review agent) | 4/5 |
