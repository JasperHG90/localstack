---
verdict: pass
tree: fe62c56563a9b6863caadb70c424604c95a769d6
---

# Adversarial review (cycle 4) — N1-netsec-restrict-prometheus-loki-to-cluster

I reproduced the fingerprint before reading anything: `git read-tree HEAD`
into a throwaway index at `$GIT_INDEX_FILE`, `git add -A .`,
`git rm -r --cached .loop`, `git add -f .loop/config.json`, `git write-tree`
yields `fe62c56563a9b6863caadb70c424604c95a769d6`. The tree I reviewed is the
tree I am binding. That reconstruction also settles a scope question up
front: `.loop/config.json` **is** inside the fingerprint, so the
`max_review_cycles` bump is part of the commit, not harness bookkeeping
outside it. `.loop/ledger.json`, the verdict files and
`deployments/applications/vars/prod.tfvars` are not.

SSH worked. Every on-host claim below was measured directly on
`192.168.2.47` and `192.168.2.30` with read-only commands and one
`ufw --dry-run`. `/etc/ufw/user.rules` on `.47` still hashes
`c5e2524535f379d3cb2e0ac888653266` after my dry-run, identical to before it
and identical to the hash cycle 3 recorded, and `ufw-user-input` still holds
23 ACCEPT rules. I mutated nothing, and the host has not drifted since cycle
3, so cycle 3's measured claims are still current.

Both of cycle 3's minors were addressed. Claim (1) is now true and I
confirmed it from ufw's source at four independent points. Claim (2) is
honest and survives the apply, with one wording weakness recorded below. The
Terraform is unchanged and I re-derived both allow-lists from live
measurement rather than from the diff. No new defect of substance was
introduced by the polish pass. The one finding worth the operator's
attention is the config bump, and it is not a code finding.

---

## Claim (1), the `-parallelism=1` justification, is TRUE — read from ufw source on the host

`docs/monitoring.md:114-119`:

> ufw does take an exclusive lock on `/run/ufw.lock`, but it reads the rule
> set before acquiring it, so two overlapping invocations can each start
> from the same pre-write state and the second then writes a file missing
> the first's rule.

Four separate checks on `192.168.2.47`, ufw 0.36.2, Python 3.12.3:

1. **The lock is exclusive and the path is right.**
   `/usr/lib/python3/dist-packages/ufw/util.py:1100-1106` is
   `create_lock`: `lock = open(lockfile, 'w')` then
   `fcntl.lockf(lock, fcntl.LOCK_EX)`. `/usr/sbin/ufw:122-123` sets
   `lockfile = '/run/ufw.lock'` when `datadir is None`, and `:124-125`
   only diverts it for non-root or `TESTSTATE`. The provisioner runs
   `sudo ufw`, so uid 0, so `/run/ufw.lock`. Both details in the sentence
   are exact.

2. **The read precedes the lock.** `/usr/sbin/ufw:114-116` constructs
   `ufw.frontend.UFWFrontend(...)`. `frontend.py:173-180` has that
   constructor build `UFWBackendIptables(...)`, and
   `backend.py:32-56` has `UFWBackend.__init__` end in
   `self._read_rules()`. `create_lock` is not called until
   `/usr/sbin/ufw:130`. Sixteen lines of ordering, and it is the right way
   round for the claim.

3. **There is no second read after the lock.** `grep -rn "_read_rules"`
   across `/usr/lib/python3/dist-packages/ufw/` returns exactly two hits:
   the definition at `backend_iptables.py:684` and the single call site at
   `backend.py:56`. Nothing re-reads `user.rules` once the lock is held, so
   the stale snapshot is what gets written. This is the check that closes
   the argument, and it is the one that would have falsified the sentence
   had ufw re-read under the lock.

4. **The write is of the whole stale list.** In `set_rule`
   (`backend_iptables.py:954`), the tail assigns `self.rules = newrules`
   and then calls `self._write_rules(rule.v6)` before reloading the chain.
   `_write_rules` (`:785`) re-emits `:ufw-user-input - [0:0]` and re-lists
   every rule it holds. So the second writer's file is the pre-state plus
   its own rule, and the first writer's rule is gone from both the file and
   the rebuilt chain.

The sentence is correct in mechanism, in conclusion, and in every named
identifier. Cycle 3's Finding 1 is closed. The neighbouring claim it
supports, that serialized invocations accumulate and order does not matter
(`:98-102`, `:119-120`), follows from the same reading and is also correct.

## The doc's central hazard, re-measured today, not carried over

I did not take the divergence claim on trust from cycle 3, because the doc
asserts it with a date (`docs/monitoring.md:59-61`) and a stale measurement
would silently invalidate the `-replace` list in the runbook.

On `.47`, comparing `iptables -S ufw-user-input` against the
`### tuple ###` lines of `/etc/ufw/user.rules`, the rules present in the
chain with no matching tuple are still exactly two:

```
-A ufw-user-input -s 192.168.0.0/16 -p tcp --dport 3000 -j ACCEPT
-A ufw-user-input -s 192.168.2.47/32 -p tcp --dport 9100 -j ACCEPT
```

Every one of the other 21 ACCEPT rules has a tuple. Then the loss itself,
using the exact rule this ticket adds:

```
sudo ufw --dry-run allow from 192.168.2.47 to any port 9090 proto tcp
```

The emitted payload contains one `:ufw-user-input - [0:0]` declaration and,
on the four ports that matter, only `9090/192.168.0.0/16`,
`3000/100.64.0.0/10`, `9090/100.64.0.0/10`, `3100/192.168.0.0/16` and the
new `9090/192.168.2.47`. No LAN rule for 3000. No rule for 9100 at all.
Applying this ticket's Prometheus change without the heal really would drop
both, exactly as `:55-61` says. `md5sum` on `user.rules` was unchanged after
the dry-run, which also re-confirms `:86-87`.

On `.30`, `--dport 9187 -s 192.168.2.47/32` is in the chain with no tuple
and is the only such rule, matching `:83-84`. Nothing in either plan touches
`.30`.

The asymmetry argument at `:63-81` holds on today's host. `ubuntu` has
interfaces `lo eth0 wlan0 podman0 veth0` and no `tailscale0`, so the doc's
parenthetical list is exact and the `100.64.0.0/10` rule beside Grafana's is
indeed dead at the interface level. `ufw-before-input`'s **first** rule is
`-A ufw-before-input -i lo -j ACCEPT` and its **last** is the jump to
`ufw-user-input`; `INPUT` never jumps to `ufw-user-input` directly. So
same-host traffic is accepted before the user chain is consulted, the 9100
rule is not load bearing, and by extension neither are the `192.168.2.47`
entries this ticket adds. Correct.

The two `-replace` addresses in the runbook both resolve: planning with
`-replace='null_resource.firewall["grafana"]'` and
`-replace='null_resource.firewall["node_exporter_ubuntu"]'` reports both
"will be replaced, as requested".

## The Terraform, re-derived independently

Unchanged in every cycle. I did not read it off the diff.

**Loki's five addresses are right, complete and minimal**
(`deployments/applications/services.tf:56-63`). Two independent derivations
agree:

- `ip route get 192.168.2.47` on each of the five nodes yields source
  addresses `192.168.2.30`, `192.168.2.29`, `192.168.2.46`,
  `192.168.2.47` (over `lo`), `192.168.2.50`. Exactly the list, no node
  reaching Loki from a second interface.
- On `.47`, `ss -Htnp state established '( sport = :3100 )'` shows live
  peers `192.168.2.29`, `192.168.2.30`, `192.168.2.46`, `192.168.2.47`
  (x2), `192.168.2.50` and nothing else. The empirical peer set is the
  allow-list. This is the strongest evidence available short of applying,
  and it closes eval row 5's silent-failure mode.

promtail is `type = "system"`
(`deployments/infrastructure/services/promtail.hcl:3`), `network_mode =
"host"` (`:39`), pushing to `http://192.168.2.47:3100/loki/api/v1/push`
(`:59`), so per-node host addresses are the right unit.

**Prometheus's two addresses are right**
(`deployments/infrastructure/services.tf:208-215`). Grafana is host-networked
(`services/grafana.hcl:50`) and its datasources dial
`http://192.168.2.47:9090` (`:94`) and `http://192.168.2.47:3100` (`:101`),
so `.47`. HAProxy's `server prometheus1 192.168.2.47:9090`
(`services/haproxy.hcl:153`) dials from `.30`, which `ip route get` on
firebat confirms. Live peers on `:9090` are `.47` only, with `.30`
transient by nature.

**Dropping the `100.64.0.0/10` rule for 9090 is a strict no-op, not a
tradeoff.** `ubuntu` has no tailscale interface, so there is no tailnet path
to `.47:9090` for that rule to have been serving. Tailnet users reach the
edge, and `.30`'s chain does admit `100.64.0.0/10` on both 80 and 443.

**No forgotten consumer.** Repo-wide grep for `:9090` and `:3100` across
`.hcl`, `.tf`, `.yaml`, `.yml`, `.py`, `.json`, `.sh` returns: HAProxy's two
backends, Grafana's two datasources, promtail's push URL, Prometheus's own
self-scrape target (`services/prometheus.hcl:74`), and one alert
description string that is prose, not a connection. Prometheus's other
scrape jobs are all outbound to other hosts. Plan Q2 is answered.

**Grafana untouched.** Its entry (`services.tf:216-224`) is byte-identical
and appears in the diff only as context, and it still answers 302 from the
dev container. Eval row 7 passes on both halves.

## Claim (2), the headline hedge

`docs/monitoring.md:5-11` now asserts the closure, then immediately says
"This describes what Terraform declares. It is true of the host once the
apply in *Applying a change to these rules* below has run, and the last
commands in that section are how to confirm it."

This is honest rather than weaselly. It names which world the paragraph
describes, it names the event that makes it true of the other world, and it
points at the three verification curls. It also reads correctly after the
operator applies: the sentence stays true, it just stops being a caveat. I
confirmed the pre-state it hedges against is still live: from the dev
container at `192.168.215.2`, a LAN host that is not a cluster node, 9090
returns 200, 3100 returns 200, 3000 returns 302. Nothing is applied.

One weakness, recorded as Finding 2.

---

## Finding 1 — MAJOR (scope) — the `max_review_cycles` bump rides inside this ticket's commit

`.loop/config.json:9`, `3` to `4`, is in the fingerprinted tree. I checked
its history: `git log -- .loop/config.json` shows only the two harness
build commits (`6820319`, `cfec9b7`). No ticket has ever modified this file
before, and there is no `DECISIONS.md` or equivalent in the repo where the
authorization would be recorded. The tree therefore carries a change to the
harness's own governance config, made by the agent the config governs, in a
commit whose message will be about firewall rules, with nothing in the tree
explaining why.

I was asked to say plainly whether this is gate-tampering. My answer is no,
on substance, and yes, on packaging.

Not tampering, because of the direction. `max_review_cycles` bounds how many
review rounds the loop will run before giving up. Raising it buys **more**
adversarial scrutiny, not less. `require_review` is still `true`,
`require_eval` is still `true`, the `gates` array is untouched, and the
adversarial pass still holds a full veto, which I am exercising right now.
There is no configuration of this value that lets unreviewed code through.
Contrast the changes that would be tampering: flipping `require_review` to
`false`, disabling the adversarial pass, or editing the `gates` list. None
of those happened.

Packaging is the real problem, and it has a concrete edge the authorization
does not cover. The operator authorized one more cycle for one ticket. The
change made is permanent and global: every future ticket in this repo now
gets a cap of 4. That is a standing policy change delivered as a side effect
of a firewall ticket. Either the operator wants 4 as the new standing policy,
in which case it deserves its own commit and its own sentence, or they wanted
N1 unblocked, in which case the line should go back to 3 once this commit
lands.

I cannot verify the authorization from the tree, and no agent message is
authorization as far as I am concerned. What I can do is make sure the
operator sees the line rather than discovering it later. Recommendation, in
priority order: commit the bump separately with its own rationale, or revert
it to `3` immediately after this ticket commits, or state deliberately that
4 is the new policy. I am not blocking on it, because killing a correct and
well-evidenced security fix on the final cycle over a one-line bookkeeping
change in the harness config would be worse judgment than passing it with
this written down.

Note on eval row 8: its stated **input** is "`git diff` for the ticket
across both Terraform roots", so `.loop/config.json` falls outside the
scorer's domain and the row passes on its own terms. Under CLAUDE.md rule 3
("every changed line should trace directly to the user's request") it does
not, which is why this is a finding rather than a shrug.

## Finding 2 — MINOR — the hedge names the apply, but the apply alone is not sufficient

`docs/monitoring.md:9-10`: "It is true of the host once the apply in
*Applying a change to these rules* below has run".

By the document's own account eighty lines further down (`:132-133`), the
apply is **not** what makes it true. The three `ufw delete` commands at
`:136-138` are, and without them "skipping it leaves the change cosmetic".
The most natural reading of "the apply in <section>" is the `terraform
apply` command in that section, not the whole procedure including the manual
deletes.

Cycle 3 suggested "after the apply **and the deletes** below". What shipped
is the weaker half of that. This matters more than the four words suggest,
because this ticket's named failure mode is precisely "appears done while
changing nothing", and the opening paragraph is the part most likely to be
read alone by someone who then believes the ports are closed.

Mitigated, which is why it is minor rather than required: the same sentence
points at "the last commands in that section", and those are the three
verification curls at `:148-150`, which only pass once the deletes have run.
A reader who follows the pointer lands in the right place. One word fixes
it: "once the apply and the deletes in ... have run".

## Finding 3 — MINOR — two cited paths do not resolve as written

`docs/monitoring.md:30` cites `services/haproxy.hcl` and `:78` cites
`services/grafana/alert-rules.yaml`. Neither path exists from the repo root
or relative to `docs/`. There is no top-level `services/` directory; the
only two are `deployments/infrastructure/services` and
`deployments/applications/services`, and both files live under the former.

`.claude/rules/slop-scan-for-docs.md` Layer 0 item 2 is categorical that
every cited file path must resolve. These are unambiguous abbreviations
(exactly one `haproxy.hcl` and one `alert-rules.yaml` exist in the tree, and
I verified their contents back the claims: the `prometheus` and `loki`
backends at `haproxy.hcl:152-159` carry no `http-request auth` while
`phoenix` `:146`, `mlflow` `:162` and `bifrost` `:166` do; `NodeDown` is at
`alert-rules.yaml:9`), so no reader is misled about substance. Pre-existing
since the section was written and missed by cycle 3, not introduced by this
cycle's polish. Prefixing both with `deployments/infrastructure/` closes it.

## Finding 4 — NIT — reflow artifact introduced by this cycle's edit

`docs/monitoring.md:120` is `matter above. Check the plan`, 28 columns, in
the middle of a paragraph whose other lines run to the 80-column margin. It
is the seam where the new `-parallelism=1` sentences were spliced in. It
renders identically and no rule is violated, but it is the visible fingerprint
of a patch rather than a rewrite. Rewrap the paragraph.

## Finding 5 — NIT — cycle 3's undercount survived

`docs/monitoring.md:114`, "three separate `ufw` writes against one host".
The heal apply replaces `prometheus` (2 rules), `grafana` (2) and
`node_exporter_ubuntu` (1), and `inline = [for rule in each.value.rules :
"sudo ufw ${rule}"]` (`services.tf:294`) makes each rule its own `sudo ufw`
process. That is five writes across three `remote-exec` sessions. Three is
the number that matters for the parallelism argument, since the commands
inside one session share a shell and are already serial, so the advice is
unaffected and the flag is still correct. Cycle 3 called this a sub-nit; it
was not fixed and it remains one.

## Finding 6 — INFORMATIONAL — the downstream line citation moved again

`.loop/plans/L1-landing-oauth2-proxy.md:127` cites
`docs/monitoring.md:206-207`. That content ("Visit `prometheus.localstack`
...") is now at `363-364`, verified by diffing `git show
HEAD:docs/monitoring.md` against the working copy. Cycle 3 recorded `356-357`,
which this cycle's seven added lines have made stale. Recording the corrected
number so nobody chases either old value. Not N1's to fix.

---

## What else I verified positively

**Gates, re-run independently.**

- `just pre_commit` from the repo root: every hook Passed, including
  Terraform Validate per root and Terraform Format.
- `deployments/infrastructure`: `Plan: 1 to add, 0 to change, 3 to destroy`.
  The only firewall change is `null_resource.firewall["prometheus"]`,
  swapping `192.168.0.0/16` and `100.64.0.0/10` for `192.168.2.47` and
  `192.168.2.30`. The other two destroys are N2's `nomad_job.dnsmasq` and
  `null_resource.firewall["dnsmasq"]`, which confirms the doc's note at
  `:121-123` that the apply also carries the previous ticket's removal.
- `deployments/applications`: `Plan: 1 to add, 0 to change, 1 to destroy`,
  `null_resource.firewall["loki"]` only, one rule out and five in.

Both match the hand-off exactly.

**Remaining factual claims in the changed section, each checked.** The admin
API is on (`services/prometheus.hcl:52`, `--web.enable-admin-api`).
`prometheus.localstack` and `loki.localstack` are NXDOMAIN from the dev
container while `grafana.localstack` resolves to `100.117.172.3`.
`T3-tls-edge-cutover-lab-domain` does rename all twelve routed hostnames to
`<svc>.lab.orangecluster.nl` (`plan:6`, `:88`, `:123`), so "which is when
the names start working" holds. No ticket owns edge auth for these two
backends: grepping every plan for `http-request auth` returns L1, L2, R1 and
R4, and none of them covers the `prometheus` or `loki` backend (L2's mentions
are a homepage service list, `plan:78-79`). Grafana's row in the table
matches `services.tf:216-224` byte for byte.

**Slop scan on the changed section (lines 1-158), all layers.** Zero em
dashes, no ` -- `, no prose semicolon splices, no tier-1 slop, no
self-narration, no "not just"/"not only", no British spellings, no smart
quotes, no identity leaks, no `TODO`/`FIXME`/`XXX`/`HACK`. Zero non-table,
non-code lines over 80 columns. Layer 1 economy passes: the lead states the
takeaway, the long section earns its length because it is a runbook, and the
one repetition ("the order among them does not matter", `:101` and `:119`) is
a deliberate back-reference rather than filler. Layer 0's only residue is
Finding 3's two abbreviated paths. The false clause cycle 3 found is gone.

**Scope.** The tree changes four files:
`deployments/infrastructure/services.tf`,
`deployments/applications/services.tf`, `docs/monitoring.md` and
`.loop/config.json`. The first two are confined to the two `firewall_rules`
entries plus their comments. The doc change traces to the plan's code surface
and subticket 5. The fourth is Finding 1. No jobspec, no scrape config, no
promtail change, no Consul rule, no provider bump. Leaving the historical
build plan below the divider untouched, with a dated note instead of a
rewrite, is the right call under the surgical-changes rule.

**Eval coverage.** Rows 1 through 6 are runtime checks that require the apply
and the three manual deletes, neither of which has happened, so the tree
cannot satisfy them by construction. I measured the pre-state the eval
expects as the contrast (9090 and 3100 both 200 from a non-cluster LAN host),
so the baseline the rows are scored against is intact and the operator owns
the after. The runbook hands over the exact commands for each row. Row 7
passes on both halves today. Row 8 passes on its stated input.

## Why a pass

Both fixes cycle 3 asked for landed. The ufw locking claim is now true and I
attacked it where it would break, at the source on the host, including the
one check that would have falsified it: whether ufw re-reads `user.rules`
under the lock. It does not, and there is exactly one call site to prove it.
The headline hedge is honest and durable past the apply, with a four-word
imprecision recorded. The polish pass introduced no new defect of substance,
only a reflow seam. The Terraform is unchanged and I re-derived both
allow-lists twice from live measurement, once from routing and once from the
live peer set on the Loki socket, and they agree with each other and with the
diff, with no node missing and no address spare. Both gates and both plans
are green and match the hand-off. What remains is a governance line in the
harness config that does not belong in this commit and that the operator
should decide about deliberately, and three doc nits that change no action
anyone takes.
