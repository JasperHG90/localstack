---
verdict: pass
tree: 1a68ffa24651badd1125455e46eab830e2af26b2
---

# Adversarial review — T2-tls-dnsmasq-lab-zone-dns (cycle 2, final)

Supersedes my cycle-1 `fail`, which was bound to the now-stale tree
`262bf006f9…`.

Fingerprint recomputed independently with the harness algorithm
(`git add -A .` / `git rm -r --cached .loop` / re-bind `.loop/config.json` /
`git write-tree`) against the live working tree: `1a68ffa24651badd1125…`,
matching the briefing and `.loop/stamp.json`.

B1 is resolved, and resolved the right way. I re-ran every measurement from
cycle 1 against the new config rather than reasoning that removal was safe.

---

## B1 — confirmed fixed, and genuinely gone

I checked the specific thing you asked me to check: whether the forward is
actually absent from the *rendered* config or merely commented out in the
source. It is absent. Rendering `services/dnsmasq.hcl` through
`terraform console` with the real `var.acme_domain` and stripping comments
and blank lines leaves exactly six active directives:

```
address=/lab.orangecluster.nl/192.168.2.30
listen-address=192.168.2.30
bind-interfaces
no-resolv
server=1.1.1.1
server=1.0.0.1
```

`consul` survives only on comment lines 22 and 24 of the rendered file, and
`grep -c 'consul'` over the non-comment lines returns `0`. No `server=/consul/`
directive reaches dnsmasq.

Runtime confirms it. I ran the pinned image with that exact rendered config
and queried it:

```
nats.service.localstack.consul  A -> (empty), status: NXDOMAIN
consul.service.consul           A -> (empty)
```

The honest fast-fail is restored. No `10.88.0.83`.

Your reasoning for full removal over a corrected comment is the right call,
and it is the part of this cycle I'd have pushed back on if you had gone the
other way. An approval given for a rationale does not transfer to the same
feature once the rationale is disproved. Handing Q4 back rather than keeping
the line on a corrected justification is the honest move.

The record is in all three places you said, and each is accurate against my
measurements:

- `services/dnsmasq.hcl:54-58` states the absence is deliberate and cites
  `10.88.0.83` / `10.88.0.4`. Both match what I measured on the live cluster.
- `docs/dns.md:30-39` states plainly that `.consul` is not forwarded, why,
  and that the documents advertising those URLs remain wrong with the real
  fix being to correct them or make Consul advertise routable addresses. It
  does not overclaim.
- The plan's Q4 is marked `WITHDRAWN 2026-07-26` with the measurement, the
  `10.88.0.83:4222` unreachability, and an explicit statement that it is the
  operator's to re-decide.

---

## Removal disturbed nothing — re-measured, not assumed

Every cycle-1 result reproduced against the new config.

**Apex guardrail: intact.**

```
grafana.lab.orangecluster.nl      -> 192.168.2.30
anything-new.lab.orangecluster.nl -> 192.168.2.30
lab.orangecluster.nl              -> 192.168.2.30
orangecluster.nl        A         -> 37.97.254.29   (public, not the edge)
orangecluster.nl        MX        -> 10 orangecluster.nl.
orangecluster.nl        TXT       -> "v=spf1 ~all"
orangecluster.nl        NS        -> ns0.nl. ns5.be. ns11.net.
notlab.orangecluster.nl A         -> (empty, correctly not captured)
xlab.orangecluster.nl   A         -> (empty, correctly not captured)
example.com / github.com          -> public answers
tcp grafana.lab.orangecluster.nl  -> 192.168.2.30
```

**Port-53 binding: intact.** Still exactly one address, both protocols, no
wildcard and no `127.0.0.1`:

```
udp UNCONN 172.31.53.20:53   0.0.0.0:*
tcp LISTEN 172.31.53.20:53   0.0.0.0:*
```

systemd-resolved's `127.0.0.53`/`127.0.0.54` remain unaffected, and the two
bound protocols still match the two firewall rules.

**Non-A forwarding: intact.** This was the one most worth re-checking, since
removing a `server=` line touches the forwarding path. All three probes still
carry the genuine upstream `orangecluster.nl.` SOA in the authority section:

```
TXT _acme-challenge.lab.orangecluster.nl  dnsmasq NOERROR, authority SOA orangecluster.nl.
SOA lab.orangecluster.nl                  dnsmasq NOERROR, authority SOA orangecluster.nl.
TXT lab.orangecluster.nl                  dnsmasq NOERROR, authority SOA orangecluster.nl.
```

**Terraform: unchanged.** `services.tf` is byte-identical to the version I
verified in cycle 1, so the firewall analysis carries over unaltered. Plan
re-run: `6 to add, 0 to change, 0 to destroy`, with
`null_resource.firewall["dnsmasq"]` a pure CREATE of a new `for_each` key and
no instance replaced. `haproxy` untouched.

**Gate:** `just pre_commit` all Passed, including Terraform Validate and
Nomad Format.

---

## Eval row 5 — the rewrite discriminates

It does, and the change is better than what I asked for. Making the positive
control primary is the right structure: the direct query on the lab name
returns NOERROR/0-answers whether or not forwarding works, so it cannot
discriminate on its own, while `address=` pointed at a domain that has a real
upstream TXT record separates the two cases cleanly. That is the test I used
in both cycles and it is the one that actually fails on a pre-2.86 build.

The authority-section rule is stated correctly: NODATA carrying the genuine
upstream SOA is a PASS, empty authority is the failure. An operator following
the row as written will now score a correct system correctly.

---

## `no-hosts` — agreed, leave it out

You asked. It is not load-bearing and I would not add it. I measured
firebat's `/etc/hosts` and it holds only `127.0.0.1 localhost` and
`127.0.1.1 firebat`, so the entire exposure is a LAN client resolving bare
`firebat` to a loopback address instead of getting NXDOMAIN. Nothing does
that, and nothing breaks if it does. Adding a directive to defend against it
is speculative configuration of exactly the kind the repo's simplicity rule
pushes against. Declining it was correct.

---

## Minor findings from cycle 1 — all addressed

- **M1**, the orphaned `### 2.91.` fragment: fixed. `dnsmasq.hcl:22-26` now
  opens "The tag reads 2.90-r3 but the binary is 2.91" and explains the floor.
  A reader checking the version no longer meets an unexplained contradiction.
- **M2**, invisible logging: `docs/dns.md:75-77` warns that routine query
  logging never reaches `nomad alloc logs` because dnsmasq logs to an absent
  syslog socket, and correctly notes fatal startup errors do reach stderr.
  Matches what I measured (0 bytes on stdout+stderr with `log-queries` on;
  the bind failure visible on stderr).
- **M3**, startup failure messages: `docs/dns.md:67-73` now names both, gets
  the attribution right (`Address not available` is the likelier one after a
  reboot because the LAN address is DHCP-assigned), and notes Nomad restarts
  the allocation.

I fact-checked the new `bind-dynamic` remedy rather than taking it on faith,
since a recommended option that the pinned build rejected would be a
hallucination in a doc. It is supported and behaves as described: with
`bind-dynamic` substituted for `bind-interfaces`, the container stays
`running` even when the configured address is absent from every interface,
where `bind-interfaces` exits immediately. The advice is sound.

---

## Remaining nit (not blocking, not a required fix)

Prose semicolon splices went from one to three: `docs/dns.md` around lines
36, 67, and 101 ("…are therefore still wrong; the fix is…", "…resolves
itself; if it does not…", "…do not take LAN DHCP either; pointing the
zone…"). House rules classify these as low-confidence and explicitly say to
surface rather than auto-rewrite, so I am surfacing and nothing more. Each
reads fine; a period would read slightly better. Entirely your call, and it
does not gate the commit.

Everything else in the doc is clean: no lines over 80 characters, zero em
dashes, no `--` in prose, no tier-1 slop or self-narration, no British
spellings, no smart quotes, no stubs, and every address, path, command, and
identifier I checked resolves to a real thing.

---

## Verdict

**pass.**

The blocker is genuinely gone from the rendered config, not merely commented
out. Removing it disturbed none of the behavior I verified in cycle 1: the
apex guardrail, the port-53 socket binding, the non-A forwarding property,
and the Terraform plan all reproduce exactly. The eval row now discriminates.
All three minor findings are addressed, and the one I flagged as declinable
was correctly declined with reasoning.

Nothing is applied, which is right. The remaining work is the operator's:
apply, run evals 1 through 7 against `@192.168.2.30` before pointing any
device at it, then the router DHCP change and the phone check that row 8
scores.
