---
epic = "netsec"
depends_on = []
priority = 10
summary = "Make Terraform's ufw management converge and clean up after itself. Today null_resource.firewall runs `ufw allow` once at create and has no destroy step, so removed rules stay open on the host and host-side drift is invisible. Adds a scoped reconcile that adds what is missing and deletes what this map owns and no longer wants."
tags = ["firewall", "ufw", "terraform", "provisioner", "drift"]
---

# N3 — Make the firewall provisioner converge and delete

## Title
`null_resource.firewall` applies rules once and never again. Make it reconcile
desired against actual on every apply, and remove rules it no longer declares,
without touching rules it does not own.

## Size / Effort
**Medium.** The reconcile logic is small. The effort is in scoping the prune
safely and proving it cannot lock the operator out of a node, which is the
failure mode that makes this worth doing carefully rather than quickly.

## Triggered by
Operator, 2026-07-26, after N1/N2/T3 shipped: "Why am I doing a manual ufw when
that should be in the terraform code?" It should be. Three concrete costs paid
in one day:
- N2 destroyed `null_resource.firewall["dnsmasq"]` and ports 53/udp and 53/tcp
  stayed open on firebat until deleted by hand.
- N1's narrowing left the superseded broad rules live, so the change was
  cosmetic until three manual `ufw delete` commands ran.
- Grafana's LAN rule on 3000 existed in the live iptables chain but not in
  ufw's database for an unknown period. Terraform reported everything in sync
  throughout, because "in sync" only ever meant "the strings in state match the
  strings in config".

## Context (today's state)
- **Two firewall mechanisms exist and only one is correct.**
  - `bootstrap/roles/firewall/tasks/main.yml` uses `community.general.ufw`, a
    real idempotent module, driven by `firewall_ufw_ports` from
    `bootstrap/playbooks/configure_network.yml:9` (manager) and `:34` (worker).
    This owns the platform ports: 22, 8200/8201, 8300/8301/8500/8600,
    4646/4647/4648, and the Nomad dynamic range `20000:32000`.
  - `deployments/infrastructure/services.tf:279-295` and
    `deployments/applications/services.tf:85-101` use `null_resource` +
    `remote-exec`. These own the service ports. They are the broken half.
- **What state actually holds.** `terraform state show
  'null_resource.firewall["prometheus"]'` returns an `id` and
  `triggers.rules`, the command strings verbatim. Nothing about the host's
  firewall. `null_resource` has no `Read`, so drift is structurally invisible
  and no plan ever consults the host.
- **The two roots differ in `triggers`**, which matters for the fix:
  - infra (`services.tf:282-284`): `rules` only.
  - applications (`services.tf:88-91`): `rules` and `host`.
  A `when = destroy` provisioner may reference ONLY `self`, `count` and
  `each`, so both `host` and `ssh_user` must live in `triggers` before a
  destroy step can connect anywhere.
- **Scale:** 14 map entries in the infrastructure root, 6 in the applications
  root, across five hosts.
- Rules are applied over SSH with the key at `${path.root}/../../.ssh/id_rsa`
  (`services.tf:290`, `applications/services.tf:97`).
- `ufw allow` is idempotent and `ufw delete` on a non-existent rule is a
  no-op that exits 0, so a reconcile that over-issues either is safe.
- Measured 2026-07-26: `ufw --dry-run` prints the projected ruleset and
  mutates nothing, verified by hashing `/etc/ufw/user.rules` either side. This
  is the mechanism a dry-run mode should use.

## Non-goals / out of scope
- **Moving service ports into the Ansible role.** Considered and rejected for
  now (see Q1): it would split a service's ports from the service definition
  and make `just apply` insufficient to deploy a service. Revisit only if this
  approach fails.
- Changing which ports are open. This ticket changes the *mechanism*, and the
  desired end state must be byte-identical to today's declared rules.
- Touching `bootstrap/roles/firewall/` or `configure_network.yml`. The Ansible
  half already converges correctly.
- Replacing ufw with nftables, or managing `/etc/ufw/user.rules` directly.
- IPv6 rules. `IPV6=no` is set (`bootstrap/roles/firewall/tasks/main.yml`).

## Requirements & restrictions
1. **A rule removed from the map is removed from the host.** Deleting a
   `firewall_rules` entry, or a line within one, must close the port on the
   next apply. This is the primary deliverable.
2. **Convergence.** If a declared rule is missing from the host, the next
   apply restores it, without needing the map to change.
3. **THE PRUNE MUST BE SCOPED, and this is the whole risk.** Only `(port,
   source, proto)` tuples that this map has declared may be considered for
   deletion. A "delete anything not in my list" reconcile would remove port
   22, Consul, Nomad and the dynamic port range, all owned by Ansible, and
   lock the operator out of the node mid-apply. Prove the scoping, do not
   assert it.
4. **Never delete SSH.** A hard guard on port 22 regardless of what the map
   says, so no future map edit can strand a host.
5. Destroy provisioners may reference only `self`, so add `host` and
   `ssh_user` to `triggers` in BOTH roots. Note this forces replacement of all
   20 resources on the first apply (see Risk).
6. Provide a dry-run path that prints what would be added and deleted per host
   without changing anything, using `ufw --dry-run`. The operator must be able
   to inspect the plan before the first real run.
7. The desired end state after this ticket must match today's declared rules
   exactly. Diff the live chain before and after: only rules this ticket
   intends to remove may disappear.
8. Terraform providers pinned at `providers.tf:1-24`. Do not bump.
9. `.claude/rules/adversarial-reviews.md`: adversarial review before done.

## Code surface
- `deployments/infrastructure/services.tf:279-295` — add `host` and `ssh_user`
  to `triggers`; replace the create-only `inline` with the reconcile; add the
  `when = destroy` provisioner.
- `deployments/applications/services.tf:85-101` — the same. `host` is already
  in `triggers`; `ssh_user` is not.
- A shared reconcile script, most likely
  `deployments/infrastructure/scripts/ufw-sync.sh` **(new)**, uploaded with a
  `file` provisioner or rendered inline. It must: read `ufw status`, compute
  the difference against the desired list passed to it, add what is missing,
  delete only tuples within its own declared scope, and support `--dry-run`.
  Both roots consume it, so decide where it lives and how the applications
  root reaches it (Q2).
- `docs/monitoring.md` — its "Applying a change to these rules" section
  documents the current fire-once behavior and the manual `ufw delete` dance.
  Rewrite once the mechanism converges.
- `docs/firewall.md` **(new, or a section elsewhere)** — where the two
  mechanisms split, which owns what, and why.

## Tests & validation gates
No unit-test harness for infra HCL, no CI. Repo gate, an offline check, then
live evals.

### Repo gate
- **Command:** `just pre_commit` -> all Passed.
- **Command:** `terraform plan` in BOTH roots. Expect all 20
  `null_resource.firewall` instances to be replaced (the `triggers` change)
  and nothing else.

### Offline check before any apply
The reconcile script is the dangerous artifact, so exercise it away from the
cluster first. Run it against a captured `ufw status` fixture and assert:
- it proposes deleting a superseded rule that the map no longer declares
- it proposes adding a declared rule absent from the fixture
- **it proposes deleting NOTHING owned by Ansible**, given a fixture
  containing port 22, 8500, 4646 and `20000:32000`
- it refuses to delete port 22 even when handed a malicious map that declares
  it
Run each as a negative control too, so the checks are known to discriminate.

### Evals — the authoritative set is `.loop/evals/N3-netsec-converging-firewall-provisioner.md`

## Risk assessment
- **Locking yourself out of a node is the failure that matters.** Every host
  is administered over SSH, and the reconcile runs as root over that same SSH
  connection. A prune bug closes 22 and the node needs physical access.
  Requirements 3 and 4 and the offline check exist for this.
- **The first apply replaces all 20 resources.** Terraform takes destroy
  provisioners from configuration rather than state, so the new destroy step
  runs against the old instances: every declared rule is deleted and then
  re-added across five hosts in one apply. Net zero if it completes, but there
  is a window, and a mid-apply failure could leave rules deleted. Apply per
  host with `-target` the first time.
- **Scoping is subtler than it looks.** ufw normalizes rules: `allow from
  192.168.0.0/16 to any port 9090 proto tcp` reads back from `ufw status` as
  `9090/tcp ALLOW IN 192.168.0.0/16`, and a rule with no `proto` expands to
  both tcp and udp entries. Matching declared against actual needs
  normalization on both sides or the reconcile will thrash, deleting and
  re-adding the same rule every apply.
- **Blast radius is every host in the cluster**, unlike N1 which touched one.
- **Reversibility: moderate.** Reverting the code restores fire-once
  behavior, but any rule the reconcile deleted stays deleted until re-applied.

## Subtickets (ordered)
1. Add `host` and `ssh_user` to `triggers` in both roots and add the
   `when = destroy` provisioner. This alone fixes the leftover-rules class
   (ports 53, the superseded broad rules) and is worth landing on its own.
2. Write the reconcile script with `--dry-run`, and the offline fixture checks
   including the Ansible-ports and port-22 negative controls.
3. Swap the create provisioner to the reconcile. Dry-run against every host
   and have the operator read the output before the first real apply.
4. Apply per host with `-target`. Diff each host's live chain before and after.
5. Docs.
6. Adversarial review.

## Evaluated alternative: the `SimonPrinz/ufw` Terraform provider

Recorded 2026-08-02. Raised by the operator; measured rather than dismissed.

**It addresses this ticket's actual defect.** N3 is blocked because
`null_resource` provisioners run at create and replace only, so nothing detects
or corrects drift and the convergence premise has no mechanism. A real provider
gives CRUD plus a read path, which is convergence by construction.
`registry.terraform.io/providers/SimonPrinz/ufw` ships `ufw_rule` and
`ufw_status`, and its own example orders them the right way round:

```terraform
resource "ufw_status" "status" {
  enabled    = true
  depends_on = [ufw_rule.allow_ssh]   # enable only once SSH is allowed
}
```

That is a neat answer to the lock-yourself-out problem this ticket has to solve
somehow.

**Two blockers, one of which we could remove.**

1. **No SSH key authentication.** `host`, `username` and `password` are all
   Required in the provider schema, and there is no private-key attribute —
   `PrivateKey` returns zero hits across the source. This cluster is key-only
   (`bootstrap/` has an `ssh_keygen` recipe). Adopting it as shipped means
   creating SSH passwords for a privileged user on five boards to fix a
   Terraform ergonomics problem. Wrong trade.

   Tracked upstream as **`SimonPrinz/terraform-provider-ufw` issue #3**
   (`github.com/SimonPrinz/terraform-provider-ufw/issues/3`), open since
   2026-03-28. The requester's motivation is identical to ours,
   migrating an existing Ansible ufw playbook. The maintainer has agreed it
   belongs on the roadmap and has been candid that "the project started mainly
   as a way for me to try and learn Go".

   **The fix is small and we could send it.** `internal/provider/provider.go`
   builds one `goph.Config` with `Auth: goph.Password(password)`; the key form
   is `goph.Key(path, passphrase)`. Add `private_key` and `passphrase` to the
   schema, make `password` optional, validate exactly one is set, swap the
   `Auth:` line. Roughly 40 lines plus generated docs.

2. **The host key callback accepts every key**, and this one is worse than the
   missing feature:

   ```go
   Callback: func(hostname string, remote net.Addr, key ssh.PublicKey) error {
       return nil
   },
   ```

   No `known_hosts`, no fingerprint pinning, no error path. Anything answering
   on that address is trusted. Key auth alone does not fix it: you would stop
   sending a reusable password but still complete a handshake with an
   unverified server, and here a machine-in-the-middle does not merely observe
   — it obtains root on the firewall of every cluster node. A contribution
   should carry `goph.DefaultKnownHosts()` or an explicit `known_hosts`
   attribute, with any opt-out spelled `insecure_ignore_host_key`. Worth its
   own upstream issue first, since the maintainer has not been asked for it.

   Also noted, not worth bundling: connection failure calls
   `log.Fatal(err.Error())`, which kills the provider process instead of
   returning a Terraform diagnostic. The operator sees a crash, not "could not
   reach host X".

**Status: deferred with a trigger, not rejected.** Revisit when #3 closes and a
release ships. Even then, adopting it means a `1.x` community provider (4
stars, 392 downloads, one maintainer plus dependabot, first commit 2026-01-22)
in the path of every node's firewall, where the recovery path from a bad
release is physical access to five ARM boards. That is a blast-radius judgment,
not a code-quality one.

**Interim answer, and it is enough for N3's scope.** Ansible's
`community.general.ufw` module is idempotent by construction, so re-running
converges, and `just bootstrap` is the invocation that already exists. The
rules this ticket governs are keyed on host *group* — manager versus worker
(`bootstrap/playbooks/configure_network.yml:7,28`) — which is exactly what
Ansible inventory models. **No Terraform placement is involved**, because
`configure_network.yml:24` opens the Nomad dynamic range `20000:32000`
wholesale, so wherever Terraform schedules a job its port is already permitted.

That last point stops being true under N4, which narrows to per-service ports.
See N4's note on the same subject before assuming this conclusion carries.

## Open questions
- **Q1 — Terraform or Ansible?** Ansible's `community.general.ufw` already
  converges and the role already exists, so moving service ports there is less
  code than building a reconcile. *Recommendation: stay in Terraform.* The
  rules co-vary with service placement, which Terraform owns, and moving them
  would mean `just apply` no longer deploys a service completely. Revisit if
  the reconcile proves fragile.
- **Q2 — Where does the shared script live, given two roots?** Options: keep a
  copy per root; put it in a shared path both reference; render it inline from
  a Terraform template. *Recommendation: a single file under the
  infrastructure root, referenced by relative path from applications*, matching
  how both roots already reach `../../.ssh/id_rsa`.
- **Q3 — Should the reconcile also prune duplicate rules?** `192.168.2.47`
  currently carries duplicate entries for 3000 and 9100, created when rules
  were re-added while already present. Harmless but untidy. *Recommendation:
  yes, collapse exact duplicates within owned scope*, since it costs nothing
  once the matching logic exists.
- **Q4 — What happens when a host is unreachable during apply?** Today the
  provisioner fails and the apply errors. A reconcile that runs on every apply
  makes this more frequent, for example when a node is down for maintenance.
  *Recommendation: fail loudly rather than skip*, since a silently skipped
  host is how drift returns, but confirm the operator agrees.
