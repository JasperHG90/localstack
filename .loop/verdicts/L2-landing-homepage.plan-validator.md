---
verdict: fail
---

# plan-validator: L2-landing-homepage

Plan fingerprint verified locally: `sha256sum .loop/plans/L2-landing-homepage.md`
returns `8f1c0b5d1aec37b2a0985325d8d3c7dfabeb11824bed9b909769bd344831e258`,
matching the briefing. The `plan:` line is deliberately omitted because this is
a `fail` and must not authorize the flip to `ready`.

## Premise verdict: BROKEN

Gate verdict: **fail**.

The plan's model of the front door it must edit is false. F3 plus T3 replaced
the cleartext edge with an HTTPS-only one, and N1 removed two of the nine
services the plan promises to tile. On top of that, the plan's own resolved
fork (reverse-proxy, per L1-Q2) contradicts the body's Requirement 4 and Code
surface, which still instruct the implementer to point the `dash` backend at
Homepage. Following the body literally produces the exact "ungated `dash`
backend" the plan names as its headline risk, and the eval's security-critical
row passes today against an empty cluster, so nothing in the acceptance loop
would catch it.

## Load-bearing assumptions

### P1 — The front door is plain HTTP on `*:80` with no TLS, so "No TLS work" is a safe non-goal. **BREAKS**

Plan claims: "binds plain HTTP on `*:80` (`haproxy.hcl:48-49`, `frontend
http_in`)" (plan:44-46) and "No TLS work. The front door is plain HTTP:80
today (`haproxy.hcl:48-49`)" (plan:102-103).

Repo now says otherwise. `deployments/infrastructure/services/haproxy.hcl:91-96`:

```
frontend http_in
    bind *:80
    http-request redirect scheme https code 301 unless { ssl_fc }

frontend https_in
    bind *:443 ssl crt /secrets/haproxy.pem
```

Port 80 does nothing but 301 to HTTPS. All hostname routing moved into
`https_in`. `haproxy.hcl:16-18` adds a static `443` port; `haproxy.hcl:39,62-72`
add a `vault {}` stanza and a second `template` rendering
`secrets/haproxy.pem`. `docs/haproxy_reverse_proxy.md:3-11,41-45` confirms:
"single HTTPS entry point... Plain HTTP on port 80 answers only with a 301."
Delivered by `99bc210` (F3, done) and `a6cc9c6` (T3, done). Live cluster agrees:
`nomad job inspect haproxy` renders the same config, and
`curl -sI http://grafana.lab.orangecluster.nl/` returns `HTTP/1.1 301` with
`location: https://grafana.lab.orangecluster.nl/`.

Consequence: the ACL and `use_backend` this ticket adds must land in
`https_in`, not in the frontend the plan describes; the non-goal "No TLS work"
is describing a world that no longer exists; and every `http://` URL in
Section 8 and in the eval file is now testing the redirect, not the service.

### P2 — The cited `haproxy.hcl` anchors resolve to the constructs described. **BREAKS**

Anchor-by-anchor against the current file:

| Plan cite | Claimed | Actually at that line |
|---|---|---|
| `haproxy.hcl:6-9` | firebat constraint | correct (`haproxy.hcl:6-9`) |
| `haproxy.hcl:48-49` | `frontend http_in`, `bind *:80` | mid-comment inside the TLS cert template block; real location `haproxy.hcl:91-92` |
| `haproxy.hcl:51-62` | host ACLs | TLS template comment; real ACLs `haproxy.hcl:98-107` |
| `haproxy.hcl:64-75` | `use_backend` rules | cert template body; real rules `haproxy.hcl:109-118` |
| `haproxy.hcl:84-121` | `backend` blocks | config template preamble; real backends `haproxy.hcl:127-157` |
| `haproxy.hcl:31-124` | "a single inline `template`" | there are now two templates; the config one is `haproxy.hcl:74-158` |
| `haproxy.hcl:45-46` | `userlist openfang_users` | real location `haproxy.hcl:88-89` |
| `haproxy.hcl:100,116,120` | basic auth on phoenix, mlflow, bifrost | real: phoenix `haproxy.hcl:143`, mlflow `haproxy.hcl:153`; bifrost has none (see P5) |
| `haproxy.hcl:25` | pinned image | real `haproxy.hcl:28` |

Every haproxy anchor in the plan is off by roughly 40 to 45 lines, and the
"single inline template" claim is structurally wrong, not just shifted. The
Code surface section (plan:183-188) directs edits "near" line numbers that now
sit inside a Vault certificate template.

### P3 — Prometheus and Loki are reachable through HAProxy backends and can be tiled at `*.lab.orangecluster.nl` hostnames. **BREAKS**

Plan claims the nine services "are already reachable through HAProxy backends"
including "prometheus (`haproxy.hcl:106-107`), loki (`haproxy.hcl:112-113`)"
(plan:76-81), and Requirement 5 says tiles point at "the
`*.lab.orangecluster.nl` HAProxy hostnames where routed" (plan:138-141).

There is no prometheus or loki ACL, `use_backend`, or `backend` anywhere in
`haproxy.hcl`. `grep -n "prometheus\|loki" haproxy.hcl` returns one hit, the
unrelated `prometheus-exporter` stats service at `haproxy.hcl:122`. This was
deliberate: commit `fe681b4` "N1 follow-on: stop routing Prometheus and Loki
through the edge" (N1-netsec-restrict-prometheus-loki-to-cluster, ledger stage
`done`). `docs/haproxy_reverse_proxy.md:30-36` states it as policy: "Prometheus
and Loki are deliberately not routed here... Routing them would have meant
every metric and every log line readable by anyone who can reach the edge."

The firewall backs this up: `services.tf:204-214` restricts Prometheus 9090 to
`192.168.2.47` and `192.168.2.30` only, so an operator's browser on the LAN
cannot reach a direct-IP tile either.

Consequence: two of the nine mandated tiles have no valid target. An
implementer working from Requirement 5 has three bad options, and the one that
looks most like "make the tile work" is re-adding the edge route that N1
deliberately deleted, undoing a done security ticket. The plan gives no
guidance because it does not know the routes are gone.

### P4 — L2 owns the `dash` HAProxy backend and it points at the Homepage host:port. **BREAKS** (most dangerous)

Requirement 4 (plan:133-137): "a `backend` block pointing at the Homepage
host:port. The backend MUST be gated by L1's forward-auth". Code surface
(plan:186-188) repeats it. Subticket 6 (plan:332-333) repeats it.

The plan's own resolved fork (plan:379-384) says the opposite: "Integration is
**reverse-proxy**, not forward-auth (per L1-Q2): HAProxy routes
`dash.lab.orangecluster.nl` to oauth2-proxy (L1) to `--upstream` Homepage (L2).
**Reconcile all 'forward-auth' wording in this ticket to reverse-proxy.**"
That reconciliation was never done: 19 occurrences of "forward-auth" remain in
the plan body, and one in the eval file's Definition of Done
(`.loop/evals/L2-landing-homepage.md:5`).

L1 already owns that route. `.loop/plans/L1-landing-oauth2-proxy.md:105-110`,
Requirement 6: "Wire the gate into HAProxy for the `dash.lab.orangecluster.nl`
host: add the ACL + `use_backend` in the frontend and the backend definition."
`.loop/plans/L1-landing-oauth2-proxy.md:374-377`, resolved Q2: "oauth2-proxy
runs as the `dash` backend with `--upstream=<L2 Homepage>`; HAProxy just routes
`dash.lab.orangecluster.nl` to it. NOTE: L2's ticket text says 'forward-auth'
and must be reconciled to this reverse-proxy wiring."

Under the settled architecture, L2 must add no `dash` ACL and no `dash`
backend at all. It must publish a Homepage host:port for L1's `--upstream`.
The plan mandates the opposite in three places. An implementer following
Requirement 4 either writes a `backend dash` pointing straight at Homepage
(bypassing oauth2-proxy entirely, the ungated page of Risk 1, plan:296-300) or
overwrites L1's already-deployed backend with one that skips the gate. There
is no "L1 forward-auth ACL" to attach because HAProxy has no native
`auth_request`, which is precisely why L1-Q2 chose reverse-proxy.

### P5 — Bifrost is gated by the openfang basic-auth userlist. **BREAKS**

Plan:53-55 lists `http-request auth unless { http_auth(openfang_users) }` on
"the phoenix, mlflow, and bifrost backends (`haproxy.hcl:100,116,120`)".
`haproxy.hcl:156-157` shows `backend bifrost` with no auth line at all. Commit
`ac3267b` (B1-bifrost-native-auth-and-virtual-keys, ledger stage `done`) moved
it to native auth. `docs/haproxy_reverse_proxy.md:26-28`: "`bifrost`
authenticates with its own native `governance.auth_config`... so HAProxy no
longer gates it." Low blast radius for L2 (context only), but it is another
false current-state claim in the same paragraph.

### P6 — L2 depends on F4 for DNS and must not be marked done until F4 lands. **BREAKS**

Plan:397-400: "L2 depends on **L1**... and on **F4** (network-wide
`.localstack` DNS) — L2 must not be marked done until F4 lands, so
`dash.lab.orangecluster.nl` resolves from non-Mac LAN devices, not just via the
operator's `/etc/hosts`."

F4 (`F4-foundation-dnsmasq-localstack-dns`) is ledger stage `ready` and is
about the retired `.localstack` zone. `N2-netsec-remove-dnsmasq-for-public-dns`
is `done` (commit `5062342`, "retire the local resolver for public DNS"), and
`docs/haproxy_reverse_proxy.md:47-52` states: "Nothing to configure.
`*.lab.orangecluster.nl` and the bare `lab.orangecluster.nl` resolve from public
DNS to `192.168.2.30`... No `/etc/hosts` entries, no local resolver."

Verified live: `getent hosts dash.lab.orangecluster.nl` returns
`192.168.2.30`, as does an arbitrary `random-xyz.lab.orangecluster.nl`, proving
a public wildcard record. The ledger's own `depends_on` for L2 is
`['L1-landing-oauth2-proxy', 'A1-audit-plan-premise-sweep']`, with no F4.

The plan therefore carries a self-imposed completion blocker on a ticket that
is superseded, still `ready`, and irrelevant to this hostname. This is a
dependency-edge finding, not a hostname-rename finding; the `.localstack`
naming sweep is T3's and is not proposed here.

### P7 — The acceptance checks over `http://` URLs are meaningful. **BREAKS** (shape-check eval)

Attack surface item 4, checked against `.loop/evals/L2-landing-homepage.md`.
All four curl-based rows use `http://`, which since T3 never reaches routing.

Row 5, the security-critical one: "`curl -sI http://dash.lab.orangecluster.nl/`
with no L1 session cookie... expect a `302` redirect... `Location:` header...
NOT `HTTP/1.1 200`". Probed live, right now, with no Homepage, no L1 and no
`dash` route anywhere:

```
$ curl -sI http://dash.lab.orangecluster.nl/
HTTP/1.1 301 Moved Permanently
location: https://dash.lab.orangecluster.nl/
```

A redirect with a `Location` header and no 200. A scorer reading "a redirect,
not a 200" passes this today against nothing at all, and would keep passing
against a fully unauthenticated Homepage served on 443. The one row guarding
the plan's headline risk cannot detect that risk. Strict 301-vs-302 matching
saves it only by making it fail unconditionally instead.

Row 6 and plan check 7, regression: "`curl -sI http://grafana...` matches
baseline". Probed live: `HTTP/1.1 301` with a Location header. That response is
emitted by `frontend http_in` (`haproxy.hcl:91-93`), which this ticket does not
touch, and is independent of every ACL and backend in `https_in` where the edit
lands. Baseline and post-apply are identical even if the heredoc edit destroys
all HTTPS routing. Vacuous.

Row 2, the nine-tile check: `curl -s http://dash.../ | grep -Eio '...'` over
port 80 returns an empty body (verified live: `curl -s
http://dash.lab.orangecluster.nl/` prints nothing), so the grep matches nothing
and the row cannot pass as written. Separately, even over HTTPS a
`grep -Eio` across raw HTML is a shape check: it matches a service name in a
CSS class, a favicon path, or a bookmark, and passes against nine broken tiles.

Plan check 1, `[pre-apply]` baseline "expect NOT a Homepage 200": passes
trivially and permanently.

For the record, over HTTPS the current state is `curl -sI
https://dash.lab.orangecluster.nl/` returning `HTTP/2 503` with a valid
publicly-trusted certificate (no `-k` needed), which confirms P8 below.

### P8 — The Let's Encrypt certificate covers `dash.lab.orangecluster.nl`. **HOLDS** (unstated but load-bearing)

`services/acme.hcl:102` sets `LEGO_DOMAINS="*.${acme_domain},${acme_domain}"`,
a wildcard. Confirmed live: `curl -sI https://dash.lab.orangecluster.nl/`
completes TLS verification without `-k`. The plan never states this, but its
new hostname depends on it, and it is the one edge assumption that survives.

### P9 — The cited `services.tf` anchors resolve. **PARTIALLY BREAKS**

- `services.tf:102-120` (`grafana_data` host-volume model): **HOLDS** exactly,
  including `plugin_id = "mkdir"`, `node_pool = "default"`, the
  `unique.hostname` constraint and the `single-node-writer` /
  `file-system` capability.
- `services.tf:163-272` (`local.firewall_rules`): **HOLDS**; the local opens at
  `services.tf:163-164`.
- `services.tf:262-269` cited as "nats firewall": shifted. Lines 260-265 are
  `postgres_exporter`; the `nats` block with 8222 on `192.168.2.50` is
  `services.tf:266-275`. The substance holds, the anchor does not.
- `services.tf:308-316` cited as the haproxy `templatefile` with
  `openfang_password`: **BREAKS**. That range is now the `minio` job. The
  haproxy resource is `services.tf:318-326` and takes two vars,
  `openfang_password` and `tls_secret`.
- `services.tf:333-355` cited as the `nomad_job` + `depends_on` model: shifted.
  333-343 is `prometheus`, 345-368 is `grafana`. The cited range straddles two
  resources. A `nomad_job` with `templatefile` and `depends_on` on a host
  volume is still findable there, so this one is survivable.

### P10 — The `grafana.hcl` config-as-files and host-volume pattern anchors resolve. **HOLDS**

`grafana.hcl:18-23` is the `volume "grafana_data"` stanza, `grafana.hcl:51-59`
the `config.volumes` read-only mounts, `grafana.hcl:62-65` the `volume_mount`,
`grafana.hcl:86-125` the `template` stanzas, `grafana.hcl:48` the pinned image
`docker.io/grafana/grafana:11.5.2`. All as described. This is the plan's
strongest section.

### P11 — The tests-and-gates section matches this repo's real gates. **HOLDS**

`.pre-commit-config.yaml:1` is the `^\.(claude|loop)/` exclude;
`.pre-commit-config.yaml:16-21` `nomad-fmt`; `:22-27` `terraform-fmt`; `:28-33`
`terraform-validate` with `entry: scripts/tf_validate.sh`. `scripts/tf_validate.sh`
exists, is executable, and iterates `deployments/infrastructure`,
`deployments/applications`, `deployments/applications/modules/bucket` with
`init -backend=false`, exactly as described. `justfile:17-19` is
`pre_commit: pre-commit run --all-files`. The Section 8 caveat that no repo
gate parses the embedded HAProxy config is correct and well reasoned. This
section was evidently refreshed after authoring; the Context section was not.

### P12 — L1 has not run, so Q1's hard block still applies. **HOLDS**

Ledger: `L1-landing-oauth2-proxy` stage `ready`. `nomad job status` on the live
cluster lists 19 jobs with no oauth2-proxy among them. `grep -n "dash"
haproxy.hcl` returns nothing. The Q1 hard block is correctly stated.

### P13 — Placing Homepage on ubuntu avoids a port collision. **UNCERTAIN**

Resolved Q3 (plan:387-391) puts Homepage on ubuntu (192.168.2.47). Risk 4
(plan:305-307) warns that "Homepage default port (3000) collides with Grafana
if colocated on the same node" and tells the implementer to avoid it on
firebat. But Grafana runs on ubuntu, not firebat: `services.tf:111-114` pins
`grafana_data` to `ubuntu`, `grafana.hcl:69` sets
`GF_SERVER_HTTP_PORT = "3000"`, and `haproxy.hcl:150` routes
`grafana1 192.168.2.47:3000`. The resolved fork does say "Pick a
non-conflicting port", so the outcome is probably fine, but Risk 4 points the
implementer at the wrong node for the collision it describes. Marked
`UNCERTAIN` rather than `BREAKS` because the resolution's instruction, if
followed, avoids the clash.

## Attack surface, itemized

1. **Stale premise.** Found, and it is the bulk of the plan: P1 (cleartext
   edge), P2 (every haproxy anchor), P3 (Prometheus and Loki edge routes), P5
   (bifrost basic auth). All four were true when authored on 2026-07-24 and
   were falsified by F3 (`99bc210`), T3 (`a6cc9c6`), N1 follow-on (`fe681b4`)
   and B1 (`ac3267b`), all `done`.
2. **Inlined conclusion.** Found, in inverted form. The plan does not
   prematurely settle an unrun ticket's question; it does the reverse. Its own
   resolved fork records L1-Q2's reverse-proxy answer, then the body never
   applies it and keeps mandating the forward-auth wiring L1 explicitly
   rejected (P4). The eval file's Definition of Done
   (`.loop/evals/L2-landing-homepage.md:5`) inherits the rejected wording.
3. **Broken dependency edge.** Two. P4: the `dash` route is L1's deliverable
   (`L1-landing-oauth2-proxy.md:105-110`), and L2 mandates building it itself
   with the gate stripped out. P6: a hard completion block on F4, which is
   superseded by N2 (`done`) and irrelevant to `dash.lab.orangecluster.nl`.
4. **Shape-check eval.** Found, and it is the security-critical row. See P7.
   Row 5 passes today against a cluster with no Homepage and no auth at all;
   rows 2 and 6 are vacuous or unpassable over port 80.
5. **Unresolvable anchor.** Found, extensively. Eight of nine `haproxy.hcl`
   anchors and two `services.tf` anchors miss (P2, P9). Unusually for this
   sweep, the anchors do not merely resolve to the wrong lines: the plan's
   structural claim of "a single inline `template`" is false now that a second
   template renders the TLS PEM.

## Most dangerous assumption

**P4** — that L2 adds a `dash` backend pointing at the Homepage host:port,
gated by an "L1 forward-auth" that L1 decided not to build.

An implementer following Requirement 4, the Code surface, and Subticket 6
writes a `backend dash` that reaches Homepage directly. There is no
forward-auth snippet to attach because HAProxy has no native `auth_request`,
which is exactly why L1-Q2 settled on reverse-proxy. The result is the
unauthenticated landing page the plan itself names as its headline risk
(plan:296-300), or a clobbering of L1's already-deployed gate. P1 removes the
safety net: with the acceptance checks aimed at port 80, which only ever
returns a 301, the eval passes while the page sits open on 443. P1 has the
wider blast radius, but P4 is the one that ships an open door and hides it.

## Required fixes before this plan leaves PLANNING

1. **Rewrite Section 4 Context against the current edge.** State that HAProxy
   terminates TLS on `*:443` with a Let's Encrypt wildcard from Vault KV2
   (`haproxy.hcl:95-96`, `acme.hcl:102`) and that `*:80` only 301s
   (`haproxy.hcl:91-93`). Re-anchor every haproxy cite: ACLs 98-107,
   `use_backend` 109-118, backends 127-157, config template 74-158, userlist
   88-89, basic auth on phoenix 143 and mlflow 153 only.
2. **Delete or replace the "No TLS work / plain HTTP:80" non-goal**
   (plan:102-103) and state that the `dash` ACL and `use_backend` land in
   `frontend https_in`, not `http_in`.
3. **Resolve the forward-auth vs reverse-proxy contradiction.** Apply the
   resolved fork (plan:379-384) throughout: remove Requirement 4's
   "backend pointing at the Homepage host:port", remove Subticket 6, and
   restate L2's deliverable as publishing a Homepage host:port for L1's
   `--upstream`, with the `dash` ACL and backend owned by L1
   (`L1-landing-oauth2-proxy.md:105-110,374-377`). Fix all 19 "forward-auth"
   occurrences and the one in the eval Definition of Done.
4. **Fix the Prometheus and Loki tiles.** N1 removed both edge routes on
   purpose (`docs/haproxy_reverse_proxy.md:30-36`, commit `fe681b4`) and the
   firewall confines Prometheus to two cluster hosts (`services.tf:204-214`).
   Either drop them from the nine, or specify a cluster-internal
   `siteMonitor`-only tile with no clickable edge URL, and state explicitly
   that re-adding the edge route is forbidden.
5. **Rebuild the eval against HTTPS.** Every check must use
   `https://<host>` so it exercises `https_in`. The unauthenticated-block row
   must distinguish HAProxy's global 301 from L1's auth redirect: assert a 302
   whose `Location` points at the oauth2-proxy or Vault authorize endpoint,
   probed on 443. The regression row must compare an HTTPS status from a
   routed backend, not a port-80 redirect that the edit cannot affect. The
   nine-tile row should assert against Homepage's service-status API rather
   than `grep -Eio` over raw HTML.
6. **Drop the F4 dependency claim** (plan:397-400). Public wildcard DNS already
   resolves `dash.lab.orangecluster.nl` to `192.168.2.30`
   (`docs/haproxy_reverse_proxy.md:47-52`, verified by `getent hosts`). Do not
   attempt the `.localstack` naming sweep here; that is T3's territory.
7. **Correct the bifrost basic-auth claim** (plan:53-55) and the two shifted
   `services.tf` anchors: haproxy job resource is `services.tf:318-326` with
   `openfang_password` and `tls_secret`; the nats firewall block is
   `services.tf:266-275`.
8. **Point Risk 4 at the right node.** Grafana's 3000 is on ubuntu
   (`services.tf:111-114`, `grafana.hcl:69`), which is where resolved Q3 puts
   Homepage.

## Method and constraints observed

Read-only throughout. Cluster access was limited to `nomad job status`,
`nomad job inspect haproxy`, `getent hosts`, and `curl -sI` probes of already
public endpoints. No `vault write`, no `nomad job run`, no `terraform apply`,
no mutating git command. The only file written is this verdict.
