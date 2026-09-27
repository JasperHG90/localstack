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

## `.consul` names are still not usable

The [NATS pages](nats.md) and the unbuilt
`.okf/proposals/postgres-nats-cdc-bridge.md` advertise
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

## See also

- [Why lab names are in public DNS](../explanation/public-lab-dns.md): what
  the public records expose, why there is no local resolver, and why
  certificate renewal does not depend on LAN DNS.
- [How to check that lab names resolve](../how-to/check-lab-dns.md), including
  what to do when one device cannot resolve the zone.
