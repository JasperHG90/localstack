---
verdict: pass
tree: 152f6a7a99ed75a34b870d724004d1dcb3aee4ee
---

# Adversarial review — N2-netsec-remove-dnsmasq-for-public-dns (cycle 2)

All three cycle-1 findings are resolved. The eval row is now satisfiable and
I ran it. The two doc sections say what the hand-off claims, and the new
factual assertions in them are true — I verified each against the live
cluster rather than reading them. Nothing behavioral moved. Pass.

## Nothing behavioral moved — confirmed

The Terraform diff is byte-identical to cycle 1: 24 deletions in
`services.tf`, 93 in the deleted `services/dnsmasq.hcl`, and `git diff
--stat -- deployments/` shows those two files and nothing else. Re-planned
from scratch:

```
# nomad_job.dnsmasq will be destroyed
# null_resource.firewall["dnsmasq"] will be destroyed
Plan: 0 to add, 0 to change, 2 to destroy.
```

`just pre_commit` — all Passed, working tree unchanged afterward.

The precondition still holds at review time, from three resolvers including
the household router:

```
1.1.1.1 / 8.8.8.8 / 192.168.2.254
  grafana.lab.orangecluster.nl -> 192.168.2.30
  lab.orangecluster.nl         -> 192.168.2.30
  orangecluster.nl             -> 37.97.254.29
```

Nothing is applied. `nomad job status dnsmasq` is `running`, and ufw `[22]
53/udp` and `[23] 53/tcp` are still present on firebat.

## Eval row 6 — satisfiable, and I ran it

The rewritten row judges against the current edge with `-k`, comparing
before and after. I captured the "before" side for all twelve hostnames in
`haproxy.hcl:97-108`:

```
minio 200   s3 403      vault 307    nomad 307
consul 301  phoenix 401 memex 401    prometheus 302
grafana 302 loki 404    mlflow 401   bifrost 401
```

Twelve distinct, non-degenerate codes. This is a real comparison rather than
a row that passes vacuously, and it is capturable today, which is what
cycle 1 said the old row was not. The row's explicit statement that a lab
hostname returning `000` and an unflagged `curl` failing verification are
correct pre-cutover behavior matches what I measured in cycle 1 (`CN =
*.localstack` from `localstack Root CA`, `ssl_verify_result=19`). Recording
why the row was wrong so the next person reordering tickets sees the trap is
the right call — that is the failure mode, not the row.

You fixed the row and not the code. That was correct.

## Doc finding 1 (LAN browser) — accurate, and not overcorrected

`docs/dns.md:44-59`. Every technical claim holds:

- Write-only via same-origin policy (`:49-51`). Correct, and the right
  nuance. A weaker doc would have called it "access" and been wrong in the
  other direction.
- Scoping it to endpoints without a CSRF token or without authentication
  (`:50-51`). Correct.
- "JavaScript cannot click through a certificate warning the way a human
  can" (`:54-55`). Correct — a TLS failure on a subresource or `fetch` is
  fatal with no interstitial.
- "Modern browsers increasingly block requests from public pages to private
  addresses" (`:57-58`). Appropriately hedged, and real (Private Network
  Access). Not a hallucination and not oversold.

The section is proportionate. It names the exposure plainly, bounds it, and
then says what closes it. It does not moralize and does not inflate a home
LAN into a breach. No overcorrection.

**Informational, and I recommend leaving it alone.** Two small leans, both
in the same direction, neither worth an edit:

1. "The certificate is what enables it, not the DNS record" (`:53`) is a
   simplification. Both are necessary: without the A record the browser
   cannot resolve the name and the request never arrives either. The
   sentence is doing rhetorical work rather than causal work, and the work
   it is doing is fair.
2. "A local resolver answering the same names would have created the same
   exposure" (`:56-57`) is the correct counterfactual against T2 *as
   designed* — the router pointed at dnsmasq, every device resolving the
   zone. Against T2 *as deployed* it is generous: the TTL evidence from
   cycle 1 showed the router never forwarded to dnsmasq, so in practice
   almost no browser resolved these names before. The intended
   architecture is the honest comparison, so I am not asking for a change.
   Flagging it only so nobody later reads the sentence as a claim about the
   as-built prior state.

Tightening either of these would be exactly the overcorrection I warned
against. Ship as written.

## Doc finding 2 (`.consul`) — restored, and every new claim verified

`docs/dns.md:105-121`. This section makes four checkable assertions. I
checked all four against the live cluster:

| Claim | Evidence |
| --- | --- |
| Consul answers `.consul` on 8600 only | `dig @192.168.2.30 -p 8600 nats.service.localstack.consul` -> `10.88.0.83`; the same query on port 53 returns nothing |
| Resolves to `10.88.0.83` | exactly what Consul returned, to the octet |
| Unreachable even from firebat | from firebat: connect to `10.88.0.83:4222` -> `No route to host` |
| `192.168.2.50:4222` is open | TCP connect from the dev container succeeds |

The stale URLs are still where cycle 1 found them: `docs/nats.md:7,91,157`
and `docs/nats-postgres-cdc-bridge.md:20,183,255,288`. The section names both
files, and assigning the fix to whoever owns NATS is the right disposition —
correcting seven call sites in a DNS-removal ticket would have been scope
creep, and I would have flagged it as such.

This is better than what was lost. The old doc asserted the URL was wrong;
this one shows the measurement that makes it wrong and says why forwarding
was rejected. The "honest NXDOMAIN rather than a connect timeout" framing is
the reasoning that was worth preserving.

## Doc gates

Zero em dashes, zero ` -- `, no line over 80 columns, no tier-1 vocabulary,
no British spellings, no semicolon splices, no smart quotes, no negative
parallelism, no participial tail-loading. Rubric row 9 still passes on all
four required elements (`:3-6`, `:31-34`, `:61-75`, `:77-86`), now with the
exposure discussion strengthened.

## Your question about the ufw refinement

**Put it in requirement 3, one clause.** Your reasoning for keeping it out of
the diff is right — it is a host step, there is no file in this repo that
executes it. But the runbook it belongs to *is* the plan, and there is a
specific reason to write it down rather than leave it to the operator's
judgment: eval row 4 instructs `sudo ufw status numbered`, which prints
`[22]` and `[23]`, and the natural next move after reading numbered output is
`ufw delete 22`. That renumbers `[23]`. Requirement 3 already says `ufw
delete allow`, which is the spec form, so the correction is half a sentence
naming the trap rather than a new instruction. The plan is where the two
halves meet, so that is where the note lands.

Not blocking, and not something I need to see again.

## Scope

Five paths: the two Terraform files (unchanged from cycle 1), `docs/dns.md`,
and the two `.loop/` harness files. Nothing touched the ACME job, HAProxy,
any Vault resource, or any other `firewall_rules` entry.

Informational: eval row 8 reads "nothing beyond the three declared files
changed", and the eval marker itself is now one of the modified files. That
is self-consistent with how `.loop/ledger.json` is already treated — `.loop/`
is harness bookkeeping, excluded from pre-commit at
`.pre-commit-config.yaml:1` — so the row should be read as covering the
product surface. Worth knowing only if the eval runner diffs literally.

## What remains open

The apply, deliberately. Rows 3, 4, 5 (post-state), 6 (the "after" half) and
7 are post-apply and belong to the operator. Row 5's resolution half already
passes from the dev container, which has never used dnsmasq. Row 1 and row 2
pass now, re-verified above.

Carry forward: delete the two ufw rules on firebat by rule spec, not by
index.
