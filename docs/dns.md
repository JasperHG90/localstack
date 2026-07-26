# DNS for the lab zone

Names under `lab.orangecluster.nl` resolve from public DNS to the cluster
edge at `192.168.2.30`. There is no resolver to run and nothing to configure
on any device: a phone, a laptop or a guest reaches the lab through whatever
DNS it already uses.

## The records

Two A records in the TransIP control panel, under `orangecluster.nl`:

| Naam | Type | Waarde |
|---|---|---|
| `*.lab` | A | `192.168.2.30` |
| `lab` | A | `192.168.2.30` |

Both are needed. A wildcard does not match the bare name, which is the same
reason the TLS certificate carries `*.lab.orangecluster.nl` and
`lab.orangecluster.nl` as separate SANs.

The wildcard covers names that do not exist yet, so adding a service to the
edge needs no DNS change.

A third record, a CAA on `lab` naming Let's Encrypt, restricts which
certificate authority may issue for the zone. Certificate renewal also
creates `_acme-challenge` TXT records under the zone and removes them when it
finishes.

## What this exposes, and what it does not

The address `192.168.2.30` is RFC1918. It is not routable from the internet,
so someone who resolves a lab name cannot reach it: their packets die at their
own gateway. Reaching the cluster still requires being on the LAN or the
tailnet.

What a remote attacker gains is information rather than access:

- the internal address, and the fact that the lab zone exists
- the wildcard name, through certificate transparency logs, which record every
  Let's Encrypt certificate permanently. That is one entry for the wildcard
  rather than a list of every service, which is a reason to prefer a wildcard
  certificate over one enumerating each hostname

There is one case where it is more than information, and it is worth
understanding. A browser already inside the network can now reach internal
services **by name, against a publicly-trusted certificate**. So a page loaded
from anywhere, including an advertisement on an unrelated site, can issue
requests to those services and the TLS handshake will succeed silently.
Same-origin policy still prevents that page from reading the responses, so
this is a write-only exposure: it matters for endpoints that act on a request
without a CSRF token, or that need no authentication at all.

The certificate is what enables it, not the DNS record. Without a trusted
name the browser aborts the connection and the request never arrives, and
JavaScript cannot click through a certificate warning the way a human can.
A local resolver answering the same names would have created the same
exposure. Modern browsers increasingly block requests from public pages to
private addresses, which narrows it further, and putting services behind
authentication closes it properly.

## Why there is no local resolver

A dnsmasq instance on firebat used to answer this zone, with nothing published
publicly. That arrangement is called split horizon, and it was removed
deliberately.

Making it work for every device meant pointing the router's DHCP at it, which
would have made the whole household's internet depend on a machine in the
cluster: firebat rebooting, or Nomad rescheduling the allocation, would have
taken DNS down for everyone. A second instance on another node would have
fixed the availability problem while keeping the zone private, but the
operator declined to tie household DNS to cluster machines at all.

Public records trade a little disclosure for that independence. Nothing in the
house now depends on the cluster to resolve anything.

## The failure mode worth knowing

Some resolvers and routers refuse public DNS answers that point into private
address ranges, because that pattern is how DNS rebinding attacks work. Where
such filtering is enabled, lab names will not resolve, and there is no longer
a local resolver to fall back on.

Cloudflare (`1.1.1.1`) and Google (`8.8.8.8`) both return the answers
normally. A consumer router with rebind protection is the likely culprit if
one device cannot resolve the zone while others can.

## Checking it

```bash
dig +short @1.1.1.1 grafana.lab.orangecluster.nl   # -> 192.168.2.30
dig +short @8.8.8.8 lab.orangecluster.nl           # -> 192.168.2.30
dig +short @1.1.1.1 anything.lab.orangecluster.nl  # -> 192.168.2.30 (wildcard)
dig +short @1.1.1.1 orangecluster.nl               # -> 37.97.254.29
```

The last one is the guard: the apex must return the real public site, not the
edge. The records live under `lab.`, and a mistake there would point the
website and mail at the cluster.

To check what a particular device sees, query without naming a server so it
uses its own resolver. A device that disagrees with `1.1.1.1` is either
caching an old answer or filtering the private address.

## `.consul` names are still not usable

`docs/nats.md` and `docs/nats-postgres-cdc-bridge.md` advertise
`nats://nats.service.localstack.consul:4222` as a client URL in several
places. That does not work, and removing the resolver did not change it
either way.

Consul answers `.consul` names on port 8600 only, so an ordinary client never
resolves them. Forwarding the zone to Consul was considered and rejected:
Consul hands out the container bridge address for bridge-networked services,
so `nats.service.localstack.consul` resolves to `10.88.0.83`, which is not
routable from the LAN and is unreachable even from firebat, while
`192.168.2.50:4222` is open. Forwarding would have replaced an honest
NXDOMAIN with an answer that connects to nothing and times out.

Use the node address and port. Correcting those documents, or making Consul
advertise routable addresses, belongs to whoever owns NATS.

## Certificate renewal does not depend on this

The ACME job pins its own resolver (`LEGO_DNS_RESOLVERS="1.1.1.1:53"`) rather
than using whatever the host is configured with. Renewal therefore keeps
working regardless of what happens to LAN DNS, which is why removing the local
resolver could not break certificate issuance.
