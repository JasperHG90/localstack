# How to check that lab names resolve

## Introduction

Use this when a lab name does not load, or after touching the records, to
confirm that `lab.orangecluster.nl` names resolve to the edge and that the
apex still points at the public site.

## Prerequisites

- `dig`, on a machine with internet access.
- The expected records, from [DNS for the lab zone](../reference/dns.md).

## Directions

### Step 1: Query the public resolvers

```bash
dig +short @1.1.1.1 grafana.lab.orangecluster.nl   # -> 192.168.2.30
dig +short @8.8.8.8 lab.orangecluster.nl           # -> 192.168.2.30
dig +short @1.1.1.1 anything.lab.orangecluster.nl  # -> 192.168.2.30 (wildcard)
dig +short @1.1.1.1 orangecluster.nl               # -> 37.97.254.29
```

The last one is the guard: the apex must return the real public site, not the
edge. The records live under `lab.`, and a mistake there would point the
website and mail at the cluster.

### Step 2: Check what one device sees

To check what a particular device sees, query without naming a server so it
uses its own resolver. A device that disagrees with `1.1.1.1` is either
caching an old answer or filtering the private address.

**The failure mode worth knowing.** Some resolvers and routers refuse public
DNS answers that point into private address ranges, because that pattern is
how DNS rebinding attacks work. Where such filtering is enabled, lab names
will not resolve, and there is no longer a local resolver to fall back on.

Cloudflare (`1.1.1.1`) and Google (`8.8.8.8`) both return the answers
normally. A consumer router with rebind protection is the likely culprit if
one device cannot resolve the zone while others can.

## Additional resources

- [DNS for the lab zone](../reference/dns.md)
- [Why lab names are in public DNS](../explanation/public-lab-dns.md)
