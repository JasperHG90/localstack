eval: T2-tls-dnsmasq-lab-zone-dns

**Definition of Done:** dnsmasq runs on firebat, answers
`*.lab.orangecluster.nl` and the bare `lab.orangecluster.nl` with
`192.168.2.30`, forwards everything else upstream unchanged, coexists with the
host's systemd-resolved stub listener, and is reachable by any LAN device —
including a phone with no configuration. No public A record is created.

**The motivating requirement is row 8** (operator decision, 2026-07-25:
human-scored at 100%). A phone joining the wifi, with nothing installed and
nothing configured, must resolve the lab zone. Everything else here is
plumbing that makes that possible, so the ticket does not close until you
have confirmed it yourself.

| Behavior | Input | Expected | Scorer | Threshold |
| --- | --- | --- | --- | --- |
| **Guardrail: the job actually starts, despite port 53 already being occupied on firebat** | `nomad job status dnsmasq`, then `nomad alloc logs <alloc-id>` | Deployment `successful`, alloc healthy, and NO `failed to create listening socket for port 53: Address already in use` in the logs. systemd-resolved holds `127.0.0.53:53` and `127.0.0.54:53` on firebat, so a default `0.0.0.0:53` bind collides. This is the likeliest failure and it fails at startup | deterministic check (`nomad job status dnsmasq` successful AND no bind error in logs) | 100% |
| Any name under the lab zone resolves to the edge, including names that do not exist yet | `dig +short @192.168.2.30 grafana.lab.orangecluster.nl` and `dig +short @192.168.2.30 anything-new.lab.orangecluster.nl` | Both return `192.168.2.30`. The second proves the wildcard covers future hostnames, so adding a service needs no DNS change | deterministic check (both `dig` calls return 192.168.2.30) | 100% |
| The bare lab domain resolves too | `dig +short @192.168.2.30 lab.orangecluster.nl` | Returns `192.168.2.30`. dnsmasq's `address=/lab.orangecluster.nl/` covers the domain and its subdomains in one line | deterministic check (`dig` returns 192.168.2.30) | 100% |
| **Guardrail: the operator's public website and mail keep resolving** | `dig +short @192.168.2.30 orangecluster.nl` and `dig +short MX @192.168.2.30 orangecluster.nl` | The apex returns the real public A record `37.97.254.29`, NOT `192.168.2.30`, and the MX record resolves from public DNS. A typo dropping `lab.` from the `address=` line would hijack the operator's live site and mail for every device on the LAN | deterministic check (apex returns 37.97.254.29, not 192.168.2.30) | 100% |
| **Guardrail: non-A queries inside the lab zone are forwarded upstream, so certificate renewal keeps working** | `dig +short TXT @192.168.2.30 _acme-challenge.lab.orangecluster.nl` | The upstream answer or NXDOMAIN — never a local NODATA. Below dnsmasq 2.86 a non-matching name inside an `address=` domain returns NODATA instead of being forwarded, which would break lego's apex determination and silently kill renewals ~60 days later. Confirms the pinned version is >= 2.86 and that no `local=` line was added | deterministic check (`dig TXT` returns an upstream answer or NXDOMAIN, not NODATA) | 100% |
| The resolver is safe as a general-purpose LAN resolver | `dig +short @192.168.2.30 example.com` and `dig +short @192.168.2.30 github.com` | Both return public answers. Once DHCP points devices here, a broken forwarder breaks internet access for the whole LAN — a bigger outage than anything at the edge | deterministic check (both return public addresses) | 100% |
| Resolution works over TCP, not just UDP | `dig +tcp +short @192.168.2.30 grafana.lab.orangecluster.nl` | Returns `192.168.2.30`. Large answers and retries fall back to TCP, and the ufw rule for 53/tcp is easy to omit | deterministic check (`dig +tcp` returns 192.168.2.30) | 100% |
| **The requirement this epic exists for: a phone on the wifi just works, with nothing installed** | Join the wifi with a phone that has never been configured for the lab, then open `http://grafana.lab.orangecluster.nl` in its browser | The name resolves and the request reaches the edge. The phone took DNS from DHCP with no profile, no hosts file, and no VPN. (Expect a TLS warning until T3 — this row scores RESOLUTION, not trust) | human + rubric (operator observes from a phone) | 100% |
| Firebat's own resolution is unaffected | On firebat: `dig +short @127.0.0.53 example.com` | Still answers. The systemd-resolved stub listener survives, so the host and anything using `/etc/resolv.conf` is untouched by this change | deterministic check (`dig @127.0.0.53` still resolves) | 100% |
| **Guardrail: nothing about the cluster's addressing becomes public** | `dig +short A grafana.lab.orangecluster.nl @1.1.1.1` and `dig +short A lab.orangecluster.nl @1.1.1.1` | NXDOMAIN or empty from public resolvers. Split-horizon is the whole security argument for this design: public DNS carries only the CAA record and lego's transient `_acme-challenge` TXT records, never an address | deterministic check (public resolver returns no A record) | 100% |
