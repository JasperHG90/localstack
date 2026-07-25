# TLS certificates

The cluster's edge certificate is a Let's Encrypt wildcard for
`*.lab.orangecluster.nl`, renewed nightly by a Nomad job and published to
Vault KV2. Nothing on the network needs a certificate installed: the
certificate is publicly trusted, so a phone on the wifi gets a valid padlock
with no configuration.

## How it works

A periodic batch job named `acme` runs every night at 04:00 Amsterdam time on
firebat. It has two tasks.

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

The edge proxy templates these into a single PEM file and reloads when they
change.

## What is public and what is not

Only two things about this domain are visible from the internet. The first is
a CAA record on `lab.orangecluster.nl` naming Let's Encrypt as the only CA
permitted to issue for the zone. The second is the `_acme-challenge` TXT
record, which lego creates during issuance and removes afterward.

There is no public A record for the lab zone. Names resolve on the LAN only,
from the local resolver. Nothing about the cluster's addressing is published.

One thing is public and permanent: certificate transparency logs record every
Let's Encrypt certificate, so `*.lab.orangecluster.nl` is a matter of public
record. That is one entry naming the wildcard, not a list of every service,
which is a reason to prefer the wildcard over a certificate enumerating each
hostname.

## State, and why it matters

lego keeps its ACME account key and the issued bundle on a Nomad host volume
named `acme_state`, mounted at `/acme-state`. Each nightly run is a new
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

## Checking on it

When did it last renew, and what is stored:

```bash
vault kv get -field=certificate secret/default/haproxy/tls \
  | openssl x509 -noout -issuer -subject -dates -ext subjectAltName
```

The issuer should be a Let's Encrypt intermediate. If it names
`(STAGING)` anything, the job is still pointed at the staging endpoint.

Did last night's run succeed:

```bash
nomad job status acme
nomad alloc logs <alloc-id> store
```

A successful run that had nothing to do still exits 0 and the store task still
republishes the existing certificate, so a green run does not by itself mean a
renewal happened. Check the certificate dates for that.

Does the certificate a client actually sees validate:

```bash
curl -sS -o /dev/null -w '%{http_code}\n' https://grafana.lab.orangecluster.nl/
```

No `-k`, no `--cacert`. Needing either means the certificate is not publicly
trusted and something is wrong.

## Recovering a failed renewal

The 30-day margin means a failure is not urgent, but it is silent, so find out
why before the margin runs out.

**The TransIP credential.** It lives at `secret/data/default/acme/transip`
with fields `account_name` and `private_key`. `account_name` is the TransIP
login username, not the email address on the account. The key pair must be
created in the TransIP control panel with the whitelisted-IP option turned
off; a whitelisted key mints tokens that authenticate but then fail on every
subsequent call.

**Propagation.** TransIP's DNS is not fast. lego waits up to 600 seconds by
default. If challenges fail intermittently, raise that rather than lowering
it, since each failed attempt consumes a rate-limit slot.

**Rate limits.** If issuance is refused outright, check whether something has
been re-issuing in a loop. The cure is to wait for the 7-day window, so it is
worth confirming the host volume is still attached before assuming the CA is
at fault.

## Changing the ACME environment

`var.acme_server` defaults to the Let's Encrypt staging endpoint. Staging
certificates are untrusted by design, which makes them safe for proving the
job works without spending the production budget.

To go live, set `acme_server` to
`https://acme-v02.api.letsencrypt.org/directory` and apply. Because state is
namespaced by environment, the production run starts from an empty tree,
registers a fresh account, and issues a real certificate. Before flipping,
run the job twice against staging and confirm the certificate serial is
unchanged the second time. That is what proves the job is idempotent, and an
idempotency bug discovered on production costs a week of lockout.
