---
epic = "tls"
depends_on = []
priority = 65
---

# T2 — Network-wide DNS for `*.lab.orangecluster.nl` via a dnsmasq Nomad job

## Title
dnsmasq on firebat answers `*.lab.orangecluster.nl` with `192.168.2.30` and
forwards everything else upstream, so any LAN device — phones included —
resolves the lab zone with no per-device configuration.

**Supersedes `F4-foundation-dnsmasq-localstack-dns`** (dropped from the
ledger), which is the same change against the abandoned `.localstack` name.

## Size / Effort
**Medium**, not Small. The job itself is one wildcard line plus forwarding,
but **port 53 on firebat is already occupied** (see Context), so the ticket
must resolve a bind conflict against a host service before anything runs.
That is the effort driver.

## Triggered by
The lab is moving to publicly-trusted certs on `*.lab.orangecluster.nl` (T1).
Those names must resolve on the LAN or the T3 cutover leaves every service
dark. The operator's requirement: **everyone on the network, mobile included,
reaches the cluster with nothing installed**. A DHCP-advertised resolver
delivers that, since a phone joining the wifi takes DNS from DHCP.

## Context (today's state)
- Resolution today is a hand-maintained `/etc/hosts` line on one Mac
  (`docs/haproxy_reverse_proxy.md:24-28`). No other device resolves the lab.
- Routing is already universal: every name targets firebat `192.168.2.30`,
  where HAProxy host-header routes to all backends.
- **PORT 53 IS TAKEN.** Verified over SSH to firebat 2026-07-25:
  `ss -lnup 'sport = :53'` and `ss -lntp 'sport = :53'` show
  `127.0.0.53:53` and `127.0.0.54:53` bound, `systemctl is-active
  systemd-resolved` -> `active`, `/etc/resolv.conf` -> `nameserver
  127.0.0.53` with `search home tail534b76.ts.net` (Tailscale MagicDNS).
  dnsmasq under `network_mode = "host"` binds `0.0.0.0:53` by default and
  will die with `failed to create listening socket for port 53: Address
  already in use`. **This is not the same problem HAProxy solved.** HAProxy's
  problem was privilege (`cap_add = ["NET_BIND_SERVICE"]`,
  `services/haproxy.hcl:30-31`); nothing else wants 80 or 443. This is
  contention.
- firebat is **amd64** (`nomad node status -verbose`); the other four nodes
  are arm64. The dnsmasq image F4 pinned (`4km3/dnsmasq:2.90-r3`,
  `sha256:52e25fb2…`) is a manifest-list digest covering both, so it resolves
  correctly on firebat.
- **No public A records for the lab zone, by design.** Only the CAA record and
  lego's transient `_acme-challenge` TXT records are public. Split-horizon:
  public DNS proves control for issuance, internal DNS answers addresses.
- **Consul DNS does not collide.** Verified: Consul is authoritative for
  `.consul` only, on port 8600 — `nats.service.localstack.consul` against
  `192.168.2.30:8600` answers, `grafana.localstack` there returns REFUSED.
  Nothing in the repo forwards `.consul`, firebat:53 does not answer from the
  LAN today, and no live Nomad job resolves a `.consul` name. dnsmasq cannot
  regress what nothing uses. See Q4.

## Non-goals / out of scope
- Publishing any public A record for the lab zone.
- Renaming HAProxy ACLs or touching the edge. T3.
- Obtaining or renewing certificates. T1.
- Split-DNS for Tailscale clients (Q3).
- Replacing the operator's `/etc/hosts` entries; they can stay until T3.

## Requirements & restrictions
1. Answer `*.lab.orangecluster.nl` AND `lab.orangecluster.nl` with
   `192.168.2.30` via `address=/lab.orangecluster.nl/192.168.2.30`, which
   covers the domain and all subdomains in one line.
2. **Resolve the port-53 conflict without touching the host.** Use
   `listen-address=192.168.2.30` plus `bind-interfaces` so dnsmasq binds only
   the LAN address and coexists with systemd-resolved's stub listener. If the
   implementer instead proposes disabling the stub (`DNSStubListener=no`),
   that is a bootstrap/Ansible change outside this Code surface AND it
   interacts with Tailscale MagicDNS on firebat — treat it as
   `out-of-scope-fix-needed`, not a judgment call.
3. **Pre-deploy check** (restored from F4 requirement 6): confirm what binds
   53 on firebat before applying, and confirm after applying that the stub
   listener still answers on 127.0.0.53 so the host's own resolution is
   unaffected.
4. **Pin dnsmasq >= 2.86.** Below that, a name inside an `address=` domain
   that does not match returns NODATA instead of being forwarded upstream,
   which would break lego's apex determination for `lab.orangecluster.nl`
   (see Risk). `4km3/dnsmasq:2.90-r3` satisfies this — state it explicitly
   rather than relying on it incidentally.
5. **Do NOT add `local=/lab.orangecluster.nl/`.** It restores the pre-2.86
   NODATA behavior and would silently break certificate renewal.
6. Forward every other query upstream unchanged, including `orangecluster.nl`
   itself, whose apex (`37.97.254.29`) and mail records must keep resolving
   from public DNS.
7. Runs as a Nomad `service` job on firebat, pinned image
   (`grafana.hcl:48`, `nats.hcl:69`).
8. Firewall: open UDP **and** TCP 53 to the LAN in `services.tf`
   `firewall_rules` (pattern `services.tf:182-194`). UDP is the one easy to
   forget; large answers and retries fall back to TCP.
9. Terraform providers pinned at `providers.tf:1-24`. Do not bump.
10. `.claude/rules/adversarial-reviews.md`: adversarial review before done.
11. Docs updated (see Code surface). F3 shipped stale docs and had to relay
    the fix downstream; do not repeat it.

## Code surface
- `deployments/infrastructure/services/dnsmasq.hcl` **(new)** — the job:
  `network_mode = "host"`, `cap_add = ["NET_BIND_SERVICE"]`, pinned image,
  config template with `address=`, `listen-address`, `bind-interfaces`, and
  upstream servers.
- `deployments/infrastructure/services.tf:182-194` — add a `dnsmasq` entry to
  `firewall_rules` opening 53/udp and 53/tcp to `192.168.0.0/16` (plus
  `100.64.0.0/10` if Q3 resolves that way).
- `deployments/infrastructure/services.tf` — add
  `resource "nomad_job" "dnsmasq"` with `templatefile(...)`; the HAProxy
  resource at `:315-330` is the nearest pattern.
- `docs/dns.md` **(new)** or a section in `docs/haproxy_reverse_proxy.md` —
  what resolves the lab zone, how to point a device at it, how to verify.

## Tests & validation gates
No unit-test harness for infra HCL, no CI. Repo gate plus live evals.

### Repo gate
- **Command:** `just pre_commit` (`justfile:17-19`) -> all Passed.
- **Worktree note:** `just worktree_setup <path>` first (`3c12c7a`).
- **Command:** `terraform -chdir=deployments/infrastructure plan` -> adds the
  job and firewall entry; destroys nothing but the replaced
  `null_resource.firewall` instance whose triggers changed.

### Evals (live, after apply) — encoded in `.loop/evals/<slug>.md`
1. Job healthy: `nomad job status dnsmasq` -> running, deployment successful.
   A crash-looping alloc is the signature of the port-53 conflict.
2. Lab zone resolves: `dig +short @192.168.2.30 grafana.lab.orangecluster.nl`
   -> `192.168.2.30`. Same for a name that does not exist yet
   (`anything.lab.orangecluster.nl`), proving the wildcard.
3. **Apex still resolves publicly:** `dig +short @192.168.2.30
   orangecluster.nl` -> `37.97.254.29`, NOT `192.168.2.30`. This is the
   regression that would break the operator's website and mail.
4. **Non-A queries inside the lab zone forward upstream** (the >=2.86
   behavior T1 depends on): `dig +short TXT @192.168.2.30
   _acme-challenge.lab.orangecluster.nl` -> the upstream answer or NXDOMAIN,
   never NODATA-from-local.
5. Recursion works: `dig +short @192.168.2.30 example.com` -> a public answer.
6. TCP path: `dig +tcp +short @192.168.2.30 grafana.lab.orangecluster.nl`.
7. Host unaffected: on firebat, `dig +short @127.0.0.53 example.com` still
   answers, confirming the stub listener survived.
8. **The motivating requirement:** a phone on the wifi, unconfigured,
   resolves `grafana.lab.orangecluster.nl`. Operator-observed.

## Risk assessment
- **Blast radius: the whole LAN's name resolution**, once devices point at it.
  A broken forwarder breaks internet access for every device using it — more
  disruptive than any edge outage. Evals 3 and 5 are the guards.
- **Port-53 contention is the likeliest failure** and it fails loudly at
  startup, which is the good case. Requirement 2 is the fix.
- **The quiet failure is lego.** lego uses the SYSTEM resolver for apex
  determination. Once DHCP points at dnsmasq, a pre-2.86 dnsmasq or a stray
  `local=` line returns NODATA for the zone's SOA lookup and every renewal
  fails ~60 days later, silently. Requirements 4-5 and eval 4 exist for this;
  T1 additionally pins `--dns.resolvers` so it never depends on this at all.
- **Wildcard over-capture.** A typo dropping `lab.` would hijack the
  operator's public site and mail cluster-wide. Eval 3 catches exactly this.
- **Single point of failure.** One dnsmasq on one node becomes the LAN
  resolver. If firebat is down, DNS is down for anything pointed at it.
  Mitigated by leaving the router's resolver as secondary (Q2).
- **Reversibility: high.** Stop the job, point DHCP back. No state.

## Subtickets (ordered)
1. Pre-deploy port check on firebat (requirement 3).
2. `dnsmasq.hcl` with `listen-address` + `bind-interfaces`, firewall entry,
   `nomad_job`. Gate green.
3. Apply; run evals 1-7 against `@192.168.2.30` explicitly, before any device
   is pointed at it. Nothing is at risk until DHCP changes.
4. Advertise the resolver (Q2), then eval 8 from a phone.
5. Docs.
6. Adversarial review.

## Open questions
- **Q1 — Image pin.** *Recommendation:* reuse F4's `4km3/dnsmasq:2.90-r3`
  manifest-list digest `sha256:52e25fb2…`; it satisfies requirement 4 and
  resolves on amd64. Re-verify with `docker manifest inspect` before pinning.
- **Q2 — How do LAN devices learn about this resolver?** The zero-config
  mobile requirement depends entirely on this, and it is the one step outside
  Terraform, in the router's DHCP settings. *Recommendation:* set the router's
  DHCP DNS option to `192.168.2.30` primary with the router itself secondary,
  documented as a manual step rather than automated. Operator must confirm the
  router allows it; some ISP-supplied routers do not.
- **Q3 — Tailscale clients.** They do not take LAN DHCP, and firebat's
  resolv.conf already shows a MagicDNS search domain. *Recommendation:* out of
  scope; Tailscale split-DNS can point the lab zone at `192.168.2.30` later.
  Its own ticket.
- **Q4 — Forward `.consul` to Consul's resolver?** One line
  (`server=/consul/192.168.2.30#8600`) would make `docs/nats.md:7,91,157` and
  `docs/nats-postgres-cdc-bridge.md:20,183,255,288` true for the first time —
  they advertise `nats://nats.service.localstack.consul:4222` as a client URL,
  which today only works for a client explicitly pointed at port 8600.
  *Recommendation:* include it; it is one line, regresses nothing (nothing
  resolves `.consul` on the LAN today), and fixes a live documentation lie.
  Operator to confirm, since it slightly widens scope.
- **Q5 — DNS rebinding protection.** Some dnsmasq builds ship
  `stop-dns-rebind`, which refuses UPSTREAM answers pointing into private
  ranges. Our records are local (`address=`), so they are unaffected — but
  confirm the chosen image's defaults, because a surprise here presents as
  intermittent resolution failure.
