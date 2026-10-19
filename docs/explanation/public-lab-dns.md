---
description: Why lab names resolve from public DNS to a private address, what that exposes, and why there is no local resolver.
stale_after: 2027-01-19
sources:
  - resource: deployments/infrastructure/services/acme.hcl
  - resource: deployments/infrastructure/services/haproxy.hcl
---

# Why lab names are in public DNS

Names under `lab.orangecluster.nl` resolve from public DNS to a private
address, and the edge serves them with a publicly-trusted wildcard
certificate. This page explains what that exposes and why the cluster does not
run its own resolver instead. The records themselves are in
[DNS for the lab zone](../reference/dns.md).

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

## Certificate renewal does not depend on this

The ACME job pins its own resolver (`LEGO_DNS_RESOLVERS="1.1.1.1:53"`) rather
than using whatever the host is configured with. Renewal therefore keeps
working regardless of what happens to LAN DNS, which is why removing the local
resolver could not break certificate issuance.
