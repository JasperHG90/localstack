# DNS for the lab zone

Names under `lab.orangecluster.nl` resolve to the cluster edge
(`192.168.2.30`) from a dnsmasq instance on firebat, and from nowhere else.
The zone has no public A record. Once a device uses this resolver, every lab
name works with no per-device configuration, which is what lets a phone on
the wifi reach the cluster.

**Status:** this describes the deployment after `just apply` in
`deployments/infrastructure` AND after the router change in "Pointing devices
at it" below. Until both are done, lab names resolve only where a manual
`/etc/hosts` entry exists.

## What answers what

One line in the dnsmasq config covers the whole zone:

```
address=/lab.orangecluster.nl/192.168.2.30
```

That answers the domain itself and every name under it, including names that
do not exist yet. Adding a service to the edge needs no DNS change.

Everything else is forwarded to `1.1.1.1` and `1.0.0.1`. That includes
`orangecluster.nl` itself, whose apex and mail records must keep resolving
from public DNS. The distinction matters: the `address=` line covers the lab
subdomain, not the parent, so the website and mail are untouched.

`.consul` names are **not** forwarded to Consul's resolver, though the option
was considered. Consul answers with the container bridge address for
bridge-networked services: `nats.service.localstack.consul` resolves to
`10.88.0.83` and minio to `10.88.0.4`, neither of which is routable from the
LAN. Forwarding would turn an honest NXDOMAIN into an answer that connects to
nothing and times out, which is harder to diagnose than a name that simply
does not resolve. Documents elsewhere in this repo that advertise
`nats://nats.service.localstack.consul:4222` as a client URL are therefore
still wrong; the fix is to correct them or to make Consul advertise routable
addresses, not to forward the zone.

## Split horizon, and why

Public DNS carries two things for this zone: a CAA record naming Let's
Encrypt as the only permitted certificate authority, and the transient
`_acme-challenge` TXT records the certificate client creates during issuance
and removes afterward. There is no public A record, so nothing about the
cluster's internal addressing is published.

This is the reason certificates are obtained with the DNS-01 challenge rather
than HTTP-01: DNS-01 proves control of the domain without the cluster being
reachable from the internet.

## Coexisting with systemd-resolved

firebat runs systemd-resolved, which already listens on `127.0.0.53:53` and
`127.0.0.54:53`. dnsmasq would collide with it and fail at startup if it
bound the wildcard address, so the config restricts it:

```
listen-address=192.168.2.30
bind-interfaces
```

dnsmasq therefore answers only on the LAN address. The host's own resolution
continues to go to systemd-resolved on the loopback stub, unchanged.

Two startup failures look similar and mean different things. `Address already
in use` means something else holds the LAN address on port 53. `Address not
available` means the LAN address is not up yet, which is the likelier one
after a reboot, since firebat's address comes from DHCP and the allocation
can start before the interface is configured. Nomad restarts the allocation,
so the second resolves itself; if it does not, `bind-dynamic` in place of
`bind-interfaces` makes dnsmasq attach to addresses as they appear.

Note that routine query logging does not reach `nomad alloc logs`: dnsmasq
logs to a syslog socket that does not exist in the container. Fatal startup
errors do still reach stderr, so the two messages above are visible there.

## The version floor

dnsmasq must be at least 2.86, and the pinned image runs 2.91.

Below 2.86, a query inside an `address=` domain that does not match the
record type returns NODATA instead of being forwarded upstream. That would
break the certificate client's zone lookup and stop renewals about sixty days
later, silently. For the same reason, do not add a `local=` line for the lab
zone: it restores the old behavior.

## Pointing devices at it

This is the step that cannot be automated from this repo, and the zero-config
experience depends on it: set the router's DHCP DNS option to `192.168.2.30`,
with the router itself as secondary. Devices then pick up the resolver when
they join the network, including phones, with nothing installed.

Leaving the router as the secondary matters. One dnsmasq on one node becomes
the resolver for everything pointed at it, so if firebat is down, clients
fall back rather than losing DNS entirely.

Some ISP-supplied routers do not allow a custom DNS option. If yours does
not, devices need the resolver set by hand, and the zero-config property is
lost.

Devices that force their own resolver bypass this regardless. A phone with
private DNS or DoH enabled, or a machine hardcoded to `8.8.8.8`, will not see
the lab zone. Tailscale clients do not take LAN DHCP either; pointing the
zone at this resolver for the tailnet is a separate piece of work.

## Checking it

Ask the resolver directly, before pointing anything at it:

```bash
dig +short @192.168.2.30 grafana.lab.orangecluster.nl   # -> 192.168.2.30
dig +short @192.168.2.30 anything.lab.orangecluster.nl  # -> 192.168.2.30
dig +short @192.168.2.30 orangecluster.nl               # -> 37.97.254.29
dig +short @192.168.2.30 example.com                    # -> a public answer
dig +tcp +short @192.168.2.30 grafana.lab.orangecluster.nl
```

The third is the important one. It must return the real public address, not
`192.168.2.30`. If it returns the edge, the `address=` line has captured the
parent domain and the website and mail are broken for every device using this
resolver.

The TCP check matters because large answers and retries fall back to TCP, and
a firewall rule that opens only UDP fails intermittently rather than
outright.
