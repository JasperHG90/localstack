# TLS certificates

The cluster's edge certificate is a Let's Encrypt wildcard for
`*.lab.orangecluster.nl`, renewed nightly by a Nomad job and published to
Vault KV2. Nothing on the network needs a certificate installed: the
certificate is publicly trusted, so a phone on the wifi gets a valid padlock
with no configuration.

## How it works

A periodic batch job named `acme` runs every night at 04:00 Amsterdam time on
ubuntu. It has two tasks.

It runs there rather than on firebat, which hosts the edge, because the
certificate travels through Vault rather than through the filesystem, so the
job does not need to sit next to the proxy that serves it. Firebat is also
fully reserved: 3200 of 3200 MHz, most of it held by Postgres, which leaves no
room to schedule anything new even though actual usage across the node is near
zero.

The `issue` task runs [lego](https://go-acme.github.io/lego/) with the
DNS-01 challenge against TransIP. DNS-01 is the only challenge type that can
produce a wildcard, and it proves domain control by writing a temporary TXT
record rather than by exposing anything to the internet. lego is invoked as
`lego run --renew-days 30`, which skips issuance when the certificate still
has more than 30 days left, so the nightly schedule is cheap and self-healing:
a failed night simply retries the next night, and the full 30 days of margin
survives a run of failures.

It does still contact the CA on a night when nothing is due. lego fetches the
ACME directory before it checks the expiry date, so if DNS or Let's Encrypt is
unreachable the allocation fails even though no renewal was needed. **A red
run therefore does not mean a renewal problem.** Check the certificate's dates
before treating it as one. A failed directory fetch is not rate-limited
issuance, so nothing is consumed by these failures.

The `store` task reads what lego wrote and puts it into Vault KV2 at
`secret/data/default/haproxy/tls` with three fields:

| Field | Contents |
|---|---|
| `certificate` | the leaf **and its issuing chain**, PEM |
| `private_key` | the leaf's private key, PEM |
| `issuer_chain` | the issuing intermediate on its own, PEM |

Note that `certificate` is a full chain, not a bare leaf: lego writes the
leaf and its intermediates into one `.crt` file, and `issuer_chain` is the
intermediate repeated separately. A consumer that concatenates all three
fields therefore sends the intermediate twice. That is harmless, since
receivers ignore the duplicate, but a consumer needs only `certificate` and
`private_key` to serve a complete chain.

HAProxy reads `certificate` and `private_key` from this path with a Vault
template, writes them as the single concatenated PEM its `crt` argument
expects, and restarts when the stored secret changes. It does not append
`issuer_chain`, for the reason above. See the TLS section of
[the edge reference](edge-routes.md#tls) for the serving side.

## State, and why it matters

lego keeps its ACME account key and the issued bundle on a Nomad host volume
named `acme_lego_state`, mounted at `/acme-state`. Each nightly run is a new
allocation with a fresh working directory, so without this volume lego would
register a new ACME account and request a new certificate every single night.

That is not merely wasteful. Let's Encrypt permits 5 certificates per exact
set of names per 7 days. A job that re-issues nightly exhausts that in under a
week and then cannot issue at all until the window rolls forward, which means
no certificate when the current one expires.

State is namespaced by ACME environment: `/acme-state/staging` and
`/acme-state/production` are separate trees. lego namespaces accounts by
server but names certificate files after the domain alone, so a shared
directory would let a staging certificate satisfy a production run's
not-due check. The production run would skip issuance and the store task
would republish the untrusted staging certificate.

## Public records

A CAA record on `lab.orangecluster.nl` names Let's Encrypt as the only CA
permitted to issue for the zone, and lego creates an `_acme-challenge` TXT
record during issuance and removes it afterward.

## ACME environment

`var.acme_server` points at the Let's Encrypt production endpoint. It was on
staging until the idempotency gate was cleared on 2026-07-26: the job ran
twice, lego reported `Skip renewal` with the certificate serial unchanged, and
only then was production enabled.

## See also

- [How to check the edge certificate](../how-to/check-the-edge-certificate.md)
- [How to recover a failed certificate renewal](../how-to/recover-a-failed-certificate-renewal.md)
- [How to test ACME job changes on staging](../how-to/test-acme-job-changes-on-staging.md)
- [Why lab names are in public DNS](../explanation/public-lab-dns.md), which
  covers what the certificate makes public.
