# How to recover a failed certificate renewal

## Introduction

The 30-day margin means a failure is not urgent, but it is silent, so find out
why before the margin runs out. Check the three causes below.

## Prerequisites

- A failed or suspect `acme` run, confirmed with
  [How to check the edge certificate](check-the-edge-certificate.md). A red
  run alone is not proof, see
  [How it works](../reference/tls-certificates.md#how-it-works).
- A Vault session that can read `secret/data/default/acme/transip`.

## Directions

### Step 1: Check the TransIP credential

**The TransIP credential.** It lives at `secret/data/default/acme/transip`
with fields `account_name` and `private_key`. `account_name` is the TransIP
login username, not the email address on the account. The key pair must be
created in the TransIP control panel with the whitelisted-IP option turned
off; a whitelisted key mints tokens that authenticate but then fail on every
subsequent call.

### Step 2: Check propagation

**Propagation.** TransIP's DNS is not fast. lego waits up to 600 seconds by
default. If challenges fail intermittently, raise that rather than lowering
it, since each failed attempt consumes a rate-limit slot.

### Step 3: Check rate limits

**Rate limits.** If issuance is refused outright, check whether something has
been re-issuing in a loop. The cure is to wait for the 7-day window, so it is
worth confirming the host volume is still attached before assuming the CA is
at fault.

## Additional resources

- [TLS certificates](../reference/tls-certificates.md), including why lost
  state exhausts the rate limit
