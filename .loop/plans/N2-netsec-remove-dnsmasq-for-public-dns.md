---
epic = "netsec"
depends_on = []
priority = 22
summary = "Retire the dnsmasq resolver once the lab zone is published as public A records. Removes the job, its firewall rule and its doc. Reverses T2 deliberately: the operator declined to make household DNS depend on a cluster machine."
tags = ["dns", "dnsmasq", "cleanup", "revert"]
---

# N2 — Retire dnsmasq once the lab zone is published in public DNS

## Title
Remove the dnsmasq job, its firewall rule and its documentation, because the
lab zone resolves from public DNS and a local resolver no longer earns its
keep.

## Size / Effort
**Small.** One jobspec deleted, two Terraform blocks removed, one doc
rewritten. The work is almost entirely in confirming the precondition before
deleting anything.

## Triggered by
Operator, 2026-07-26: household DNS should not depend on a machine in the
cluster. Pointing the router at dnsmasq would have made every device's
internet contingent on firebat, and the alternative of a second resolver
instance was declined on the same grounds. Publishing `*.lab.orangecluster.nl`
as public A records makes the names resolve everywhere with no local resolver
in the path.

## Context (today's state)
- **This reverses T2, which is `done` and applied.** Say so plainly rather
  than framing it as cleanup. T2 was built for split-horizon resolution; the
  operator has since chosen a different trade, and the job is now redundant
  rather than wrong.
- dnsmasq is live and healthy: allocation `running` on firebat, answering the
  lab zone, the apex, and recursion. Nine of T2's ten eval rows passed live.
- Code surface as it stands:
  - `deployments/infrastructure/services/dnsmasq.hcl` — 93 lines, the job.
  - `deployments/infrastructure/services.tf:195-205` — the `dnsmasq`
    `firewall_rules` entry (53/udp and 53/tcp).
  - `deployments/infrastructure/services.tf:394-404` — the
    `resource "nomad_job" "dnsmasq"`.
  - `docs/dns.md` — 128 lines describing the resolver.
- **THE PRECONDITION IS MET.** The operator published the records on
  2026-07-26. Verified the same day against two independent public resolvers,
  `1.1.1.1` and `8.8.8.8`, both returning identically:
  - `grafana.lab.orangecluster.nl` -> `192.168.2.30`
  - `lab.orangecluster.nl` (bare, needs its own record; a wildcard does not
    match it) -> `192.168.2.30`
  - `brand-new-name.lab.orangecluster.nl` -> `192.168.2.30`, proving the
    wildcard covers names that do not exist yet
  - `orangecluster.nl` -> `37.97.254.29`, the real public site, unaffected
  Re-run this check at implementation time rather than trusting this note. It
  was false a few hours before it was written, and a DNS record can be removed
  as easily as it was added.
- **Certificate renewal is unaffected.** The ACME job pins
  `LEGO_DNS_RESOLVERS="1.1.1.1:53"` (`services/acme.hcl:104`), so it never
  consults the local resolver. That pin was added precisely so renewal could
  not depend on LAN DNS, and it means this ticket cannot break issuance.
- Nothing else in the repo depends on the resolver. A repo-wide search for
  `dnsmasq` outside `.loop/` returns only the three files above plus
  references in the T3 and L1 plans, which describe it rather than consume it.
- No Nomad job uses the cluster's DNS for service discovery; every
  service-to-service address in the tree is a literal IP.

## Non-goals / out of scope
- **Creating the public DNS records.** That is a manual step in the TransIP
  control panel and cannot be done from this repo. It is a precondition, not
  part of the change.
- Rewriting the history of T2. Its plan, eval, reflection and verdict stay in
  `.loop/archive/T2-tls-dnsmasq-lab-zone-dns/` as the record of why it was
  built.
- Removing the `.consul` forwarding decision. It was never implemented; there
  is nothing to remove.
- Changing the ACME job, its resolver pin, or anything about certificates.
- Any change to HAProxy or the edge.
- Touching the router's DHCP configuration. It was never pointed at dnsmasq.

## Requirements & restrictions
1. **Verify the public records resolve BEFORE deleting anything.** A wildcard
   `*.lab` A record and a bare `lab` A record, both answering `192.168.2.30`
   from a public resolver. Confirm from a resolver that is NOT dnsmasq: query
   `1.1.1.1` directly. If either is missing, this ticket is blocked, not
   adaptable — removing the resolver first strands every lab hostname.
2. Remove the job, the `nomad_job` resource, and the firewall rule together.
   A `nomad_job` removed from Terraform stops the job; leaving the ufw rule
   behind opens port 53 on firebat to a service that no longer listens.
3. **The ufw rule is not removed by Terraform.** `null_resource.firewall` only
   runs `ufw allow` and has no destroy provisioner
   (`services.tf:274-290`), so deleting the map entry leaves 53/udp and
   53/tcp open on the host. Delete them explicitly with `ufw delete allow`,
   or the port stays open indefinitely. This is the same trap N1 documents.
4. Rewrite `docs/dns.md` rather than deleting it: how the lab zone resolves
   now, what is published publicly, and why there is no local resolver. A
   reader arriving from the git history should find the answer, not a gap.
5. Record what is given up (see Risk), so the trade is legible later rather
   than looking like unexplained deletion.
6. Terraform providers pinned at `providers.tf:1-24`. Do not bump.
7. `.claude/rules/adversarial-reviews.md`: adversarial review before done.

## Code surface
- `deployments/infrastructure/services/dnsmasq.hcl` — **delete the file.**
- `deployments/infrastructure/services.tf:195-205` — remove the `dnsmasq`
  entry from `firewall_rules`.
- `deployments/infrastructure/services.tf:394-404` — remove
  `resource "nomad_job" "dnsmasq"`.
- `docs/dns.md` — rewrite to describe public-DNS resolution; keep the file.
- Manual, not in the repo: `ufw delete allow` for 53/udp and 53/tcp on
  `192.168.2.30`, per requirement 3.

## Tests & validation gates
No unit-test harness for infra HCL, no CI. Repo gate plus live evals.

### Repo gate
- **Command:** `just pre_commit` -> all Passed.
- **Worktree prerequisite:** `just worktree_setup <path>` (`justfile:30-32`).
- **Command:** `terraform -chdir=deployments/infrastructure plan` -> destroys
  `nomad_job.dnsmasq`, replaces the `null_resource.firewall` instance whose
  entry was removed, and touches nothing else. Confirm no other job, volume or
  Vault resource appears.

### Evals — the authoritative set is
`.loop/evals/N2-netsec-remove-dnsmasq-for-public-dns.md`.
The load-bearing rows: the public records answer from `1.1.1.1` BEFORE
removal; lab hostnames still resolve on a device that never used dnsmasq;
port 53 is closed on firebat afterwards; and the edge still serves every
routed hostname.

## Risk assessment
- **The precondition is the whole risk.** Remove the resolver before the
  public records exist and every lab hostname stops resolving for every
  device. Requirement 1 and the first eval row exist for this, and the ticket
  should be blocked rather than adapted if the records are absent.
- **What is given up, deliberately:** split-horizon. The cluster's internal
  addressing (`192.168.2.30`) and the existence of the lab zone become
  publicly visible. Certificate transparency already publishes the wildcard,
  so the marginal disclosure is the address and the fact the names resolve.
- **Devices behind DNS-rebinding protection may stop resolving the zone.**
  Some resolvers and routers refuse public answers pointing into RFC1918.
  Where that is enforced, the name fails and there is no longer a local
  resolver to fall back on. This is the failure mode most likely to appear
  later and look unrelated.
- **Blast radius is bounded and reversible.** dnsmasq serves nothing except
  the lab zone; no device is pointed at it by DHCP; certificate renewal pins
  a public resolver. Restoring it is `git revert` plus an apply.
- **Ordering against T3 matters more than it appears.** T3 renames all twelve
  hostnames in a single apply. Doing that while the only resolution path is
  brand-new public records removes the fallback if the records are wrong. See
  Q1.

## Subtickets (ordered)
1. Verify the public records answer from `1.1.1.1` (requirement 1). Stop here
   if they do not.
2. Remove the `nomad_job` resource and the firewall entry; delete the jobspec.
3. Apply; confirm the job is gone and the edge still serves every hostname.
4. Delete the superseded ufw rules on firebat (requirement 3).
5. Rewrite `docs/dns.md`.
6. Adversarial review.

## Open questions
- **Q1 — Run this before or after T3?** *Recommendation: after.* T3 is the
  flag day that renames all twelve hostnames at once. Keeping dnsmasq until
  the cutover is verified means there are two independent paths resolving the
  lab zone during the riskiest change, and removing it afterwards costs
  nothing. The reverse order removes the fallback exactly when it is most
  likely to be wanted. This is a soft ordering, so it is expressed as a
  recommendation rather than a `depends_on`, but the operator should
  deliberately choose to ignore it rather than drift into it.
- **Q2 — Delete `docs/dns.md` or rewrite it?** *Recommendation: rewrite.* The
  question "how do lab names resolve" still has an answer worth documenting,
  and a deleted file leaves a reader who found it in the history with nothing.
- **Q3 — Keep the `acme` job's `LEGO_DNS_RESOLVERS` pin?** It was added so
  renewal would not depend on the LAN resolver that this ticket removes.
  *Recommendation: keep it.* It costs nothing and it keeps issuance
  independent of whatever the household resolver does next. Removing it would
  be a second, unrelated change.
