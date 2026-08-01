eval: N3-netsec-converging-firewall-provisioner

**Definition of Done:** Removing a rule from `firewall_rules` closes it on the
host at the next apply, a declared rule missing from a host is restored at the
next apply, and neither ever touches a rule the Ansible role owns. The desired
end state after the change matches today's declared rules exactly.

**The failure that matters is lockout.** Every host is administered over the
same SSH the reconcile runs on. A prune that is not correctly scoped closes
port 22 and the node needs physical access. Rows 1, 2 and 3 are the scoping
guardrails and they are checked offline, before anything runs against a real
host.

**The second failure is a reconcile that thrashes.** ufw normalizes rules on
read, so a matcher that compares declared text against `ufw status` text
without normalizing will delete and re-add the same rule forever. Row 7 catches
it.

| Behavior | Input | Expected | Scorer | Threshold |
| --- | --- | --- | --- | --- |
| **Guardrail: the reconcile will not delete an Ansible-owned rule, checked OFFLINE** | Run the reconcile in dry-run against a captured `ufw status` fixture containing port 22, 8500/tcp, 4646/tcp and `20000:32000/tcp`, with a desired map that declares none of them | It proposes deleting NONE of them. These belong to `bootstrap/roles/firewall` via `configure_network.yml`, and a "delete anything not in my list" reconcile would strand every node. **Run before any live execution** | deterministic check (dry-run output proposes zero deletions among the Ansible-owned tuples) | 100% |
| **Guardrail: port 22 is refused even when the map demands it** | Hand the reconcile a deliberately malicious desired map that declares port 22 for deletion | It refuses and exits non-zero, or skips 22 with a clear message. Requirement 4 is a hard guard independent of the map, so no future edit can strand a host | deterministic check (22 is never in the delete set) | 100% |
| **Guardrail: the offline checks can actually fail** | Negative controls for rows 1 and 2: a fixture where a rule genuinely IS in scope and should be deleted, and a map that legitimately removes a service port | The reconcile proposes those deletions. A checker that never proposes deleting anything would pass rows 1 and 2 vacuously, which is the way this eval gets fooled | deterministic check (in-scope deletions ARE proposed) | 100% |
| **A rule removed from the map is removed from the host** | Delete one entry from `firewall_rules` (or one line within an entry) for a service that is safe to close, apply, then check the host | The port is closed: `ufw status` no longer lists it, and a connection from a host that previously reached it now fails. This is the primary deliverable and the thing that failed for ports 53/udp and 53/tcp under the old mechanism | deterministic check (`ufw status` lacks the rule AND a connection attempt fails) | 100% |
| **A declared rule missing from a host is restored** | On one host, delete by hand a rule that the map still declares, then apply without changing any Terraform | The rule is back. Under the old mechanism nothing happened, because `triggers` had not changed. This is the drift half, and it is what would have caught Grafana's 3000 rule silently leaving ufw's database | deterministic check (rule present again after apply, with no map change) | 100% |
| **Guardrail: SSH survives on every host, checked per host** | After applying to all five nodes, SSH to each of firebat, orangepi4a, jetson-orin-nano, ubuntu and radxa-dragon-q6a | All five accept the connection. **Check each one, not a sample.** A scoping bug is likely to affect every host identically, and discovering it on the fifth node after losing the first four is the bad outcome | deterministic check (SSH succeeds on all 5) | 100% |
| **Guardrail: the reconcile is stable, not thrashing** | Apply twice in a row with no code change between runs. Capture the reconcile's output both times | The second run proposes zero additions and zero deletions. ufw reads rules back normalized (`allow from X to any port 9090 proto tcp` becomes `9090/tcp ALLOW IN X`, and a proto-less rule expands to two entries), so an unnormalized matcher will churn the same rule on every apply while appearing to work | deterministic check (second consecutive apply is a no-op) | 100% |
| **Guardrail: the end state equals today's declared rules** | Capture `sudo iptables -S ufw-user-input` on all five hosts before the first apply and after. Diff | The only differences are rules this ticket intends to remove. No declared rule is lost, and nothing new appears that the map does not declare. Requirement 7: this ticket changes the mechanism, not which ports are open | deterministic check (per-host diff contains only intended removals) | 100% |
| **Guardrail: ufw's database and the live chain agree afterwards** | On each host: `sudo iptables -S ufw-user-input` versus `sudo grep '^### tuple ###' /etc/ufw/user.rules`, normalizing the `/32` suffix on single-host sources | No rule exists in one and not the other. The divergence on `192.168.2.47` (Grafana's 3000, node-exporter 9100) and on `192.168.2.30` (9187) is exactly the condition this mechanism should now heal rather than preserve | deterministic check (no rule present in only one of the two) | 100% |
| **Guardrail: an unreachable host fails loudly** | Stop one node, or block its SSH, and apply | The apply fails with a clear error naming the host. A silently skipped host is how drift returns, and Q4 resolves this deliberately. If Q4 was answered the other way, this row is waived and the plan records why | deterministic check (apply errors and names the host) OR waived with recorded justification | 100% |
| **Guardrail: the change is confined to the mechanism** | `git diff` across both roots | Only the two `null_resource.firewall` blocks, the new reconcile script, and docs. No `firewall_rules` map entry gains or loses a rule as part of this ticket, and `bootstrap/roles/firewall/` and `configure_network.yml` are untouched | deterministic check (`git diff` confined to the declared surface) | 100% |
| A reader learns which mechanism owns what, and why there are two | Read the new firewall documentation and the rewritten section of `docs/monitoring.md` | It states that Ansible owns the platform ports and Terraform owns service ports, that the Terraform half now reconciles rather than applying once, and that the prune is deliberately scoped so it cannot touch the Ansible half. The old manual `ufw delete` runbook is gone rather than left beside the new behavior | model + rubric (adversarial review agent) | 4/5 |

signed-off-by: JasperHG90 2026-08-01
