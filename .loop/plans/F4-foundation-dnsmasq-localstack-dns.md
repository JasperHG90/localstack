# F4 — Network-wide `.localstack` DNS via a dnsmasq Nomad job (foundation)

## Title
Deploy dnsmasq as a Nomad job on firebat that answers the whole
`.localstack` TLD with `192.168.2.30` (a wildcard record) and forwards
every other query upstream, so any LAN device — not just the Mac's
`/etc/hosts` — resolves `*.localstack`.

## Size / Effort
**Small.** One new job spec (`services/dnsmasq.hcl`), one new
`nomad_job` resource in `services.tf`, one firewall entry for port 53,
and a doc update. The whole config is one wildcard line
(`address=/localstack/192.168.2.30`) plus upstream forwarding. The only
sharp edge is binding privileged UDP+TCP port 53 under the podman
driver — and the HAProxy job already solved the identical problem for
port 80 (`network_mode = "host"` + `cap_add = ["NET_BIND_SERVICE"]`,
`deployments/infrastructure/services/haproxy.hcl:27-28`), so the pattern
is a copy, not a discovery. Effort is small because routing already
works cluster-wide; the only missing piece is resolution.

## Triggered by
`*.localstack` hostnames currently resolve **only** on the operator's
Mac, via a hand-maintained `/etc/hosts` line
(`docs/haproxy_reverse_proxy.md:24-28`). Every other device on the LAN
(phones, other laptops, containers) cannot reach `minio.localstack`,
`grafana.localstack`, etc., even though HAProxy already host-header
routes for all of them from a single IP. The operator wants network-wide
resolution.

## Context (today's state)
Routing is already universal; resolution is not.

- **The routing target is a single IP.** Every `*.localstack` name is
  meant to point at firebat `192.168.2.30`, where the HAProxy job does
  host-header routing to the real backends
  (`deployments/infrastructure/services/haproxy.hcl:48-75`, backends at
  `haproxy.hcl:84-121`). So one flat wildcard `A` record for the whole
  TLD is sufficient — no per-name records are needed.
- **Resolution today is manual and Mac-only.** The documented setup is a
  single `/etc/hosts` line on the Mac
  (`docs/haproxy_reverse_proxy.md:24-28`), and "Add the hostname to your
  `/etc/hosts`" is step 2 of the "Adding a New Service" runbook
  (`docs/haproxy_reverse_proxy.md:54`). No DNS server serves these names.
- **The privileged-port precedent already exists.** HAProxy binds
  privileged port 80 by running the podman task with
  `network_mode = "host"` and `cap_add = ["NET_BIND_SERVICE"]`
  (`haproxy.hcl:21-29`), with its static port declared in the group
  `network` stanza (`haproxy.hcl:11-19`). The podman driver plugin is
  configured with only volume support and no privileged-port sysctl
  (`bootstrap/roles/nomad_client/templates/nomad.hcl.j2:61-68`); the only
  sysctl the bootstrap sets is bridge netfilter, **not**
  `net.ipv4.ip_unprivileged_port_start`
  (`bootstrap/playbooks/install_dependencies.yml:142-149`). So the
  host-network + capability route is the established, in-repo way to bind
  a low port, and there is no unprivileged-port sysctl to lean on.
- **Existing cluster DNS is a different domain — do not conflate.**
  Consul serves `*.service.localstack.consul` on port 8600. That is a
  distinct domain and does **not** serve the flat vanity `*.localstack`
  names this ticket adds. This job is the sole authority for the flat
  `.localstack` TLD.
- **The wiring pattern is one-job-per-tf-resource.** Each
  `services/*.hcl` job has a matching `nomad_job` resource rendered via
  `templatefile(...)` in `services.tf`
  (HAProxy at `services.tf:308-316`, MinIO at `services.tf:300-306`).
  A new job needs the same treatment. The simplest jobs take no
  interpolations at all (e.g. `nats` /`promtail`,
  `services.tf:359-361,363-367`).
- **Firewall rules are declarative per service.** Ingress is opened by
  entries in `local.firewall_rules` applied over SSH via `ufw`
  (`services.tf:162-290`); HAProxy's own entry opens 80 to the LAN and
  Tailscale ranges (`services.tf:182-192`). A new port needs a new entry.

## Non-goals / out of scope
- **Router DHCP hand-off.** Pointing the router's DHCP at this resolver
  so every device auto-adopts it is a manual network-admin action the
  repo cannot perform. It is documented as a required post-deploy manual
  step (see §8), **not** code. Until it is done, a client must set the
  firebat IP as its DNS server manually to benefit.
- **TLS trust.** Browsers trusting `*.localstack` certificates is the
  separate `F3-foundation-haproxy-tls-vault-pki` ticket. Resolution is
  not trust — this ticket only makes names resolve, over plain HTTP.
- **Pi-hole.** Explicitly rejected in favor of dnsmasq. Do not introduce
  ad-blocking, a web UI, or DHCP serving.
- **Retiring the Mac `/etc/hosts` entry.** Leaving it in place is
  harmless (it resolves to the same IP). This ticket does not force its
  removal; the doc update just notes it is now optional.

## Requirements & restrictions
1. **One wildcard record for the whole TLD.** The load-bearing config is
   exactly `address=/localstack/192.168.2.30`. This resolves every
   `*.localstack` name — including names not yet added to HAProxy — to
   firebat. Per CLAUDE.md "Simplicity First," do not enumerate per-name
   records.
2. **Forward everything else upstream.** dnsmasq must forward
   non-`.localstack` queries to a real resolver (e.g. `server=1.1.1.1`,
   with a secondary such as `server=1.0.0.1`) so any client using it as
   primary DNS keeps reaching the public internet. Set `no-resolv` so
   dnsmasq does **not** read the host `/etc/resolv.conf` (which, under
   host networking, could point back at itself and loop).
3. **Bind privileged port 53 the way HAProxy binds 80.** Use
   `network_mode = "host"` + `cap_add = ["NET_BIND_SERVICE"]` on the
   podman task and declare a static `port "dns" { static = 53 }` in the
   group `network` stanza, mirroring `haproxy.hcl:11-29`. Do **not**
   introduce a new `net.ipv4.ip_unprivileged_port_start` sysctl (none
   exists today, and the host-network route already works for HAProxy).
   Port 53 is both UDP and TCP; ensure both transports are served
   (host networking exposes both from the container).
4. **Match the existing edge-infra idiom.** New job constrained to
   `firebat` (`attr.unique.hostname == "firebat"`, as in
   `haproxy.hcl:6-9`); a `service` block with a health `check`; a
   `resources` block sized like the other light jobs; config rendered by
   a `template` into `local/` (as HAProxy renders its `.cfg`,
   `haproxy.hcl:31-124`). Respect CLAUDE.md "Surgical Changes": touch
   only the files in §7.
5. **Open port 53 (UDP + TCP) on firebat to the LAN.** Add a
   `firewall_rules` entry mirroring HAProxy's
   (`services.tf:182-192`): allow 53/udp and 53/tcp from
   `192.168.0.0/16` (and the Tailscale `100.64.0.0/10` range, to match
   HAProxy's remote-access parity). Secrets rule (CLAUDE.md): no
   credentials — dnsmasq needs none here.
6. **Pre-deploy port check.** Before deploy, verify nothing already
   binds 53 on firebat (see §8). If something does (e.g. host
   `systemd-resolved`), the job will fail to bind and the operator must
   free the port first — this is Q2.

## Code surface
- **`deployments/infrastructure/services/dnsmasq.hcl`** (new) — the
  Nomad job. `job "dnsmasq"`, `type = "service"`,
  `datacenters = ["localstack"]`; group constrained to `firebat`
  (`haproxy.hcl:6-9`); `network { port "dns" { static = 53 } }`; one
  podman `task` with `network_mode = "host"`,
  `cap_add = ["NET_BIND_SERVICE"]` (`haproxy.hcl:27-28`), the pinned
  image `docker.io/4km3/dnsmasq:2.90-r3@sha256:52e25fb2601156ab66f6a0872c180b285df7cafaa41267d8d65689f066490641`
  (minimal alpine, dnsmasq 2.90, arm64-verified — see Q1), pointed at the
  rendered config via `args = ["--conf-file=/local/dnsmasq.conf", ...]` (or
  a mount to `/etc/dnsmasq.conf`), a `template` rendering the config
  (`address=/localstack/192.168.2.30`, `no-resolv`, `server=1.1.1.1`,
  `server=1.0.0.1`) into `local/dnsmasq.conf`, a `service` block with a
  TCP `check` on the `dns` port (mirroring `haproxy.hcl:126-137`), and a
  small `resources` block.
- **`deployments/infrastructure/services.tf`** — add a
  `resource "nomad_job" "dnsmasq"` rendering the new spec via
  `templatefile("${path.module}/services/dnsmasq.hcl", {})` (no
  interpolations needed), following the no-arg pattern of `nats`
  (`services.tf:363-367`). Add a `dnsmasq` entry to
  `local.firewall_rules` (`services.tf:162-272`) opening 53/udp and
  53/tcp on `192.168.2.30` (ssh_user `firebat`) to `192.168.0.0/16` and
  `100.64.0.0/10`, mirroring the HAProxy entry (`services.tf:182-192`).
- **`docs/haproxy_reverse_proxy.md`** — update the "DNS Setup" section
  (`docs/haproxy_reverse_proxy.md:22-30`) to state that `*.localstack` is
  now served network-wide by the dnsmasq job, that the Mac `/etc/hosts`
  line is optional, and document the manual router-DHCP step (§8). Update
  the "Adding a New Service" runbook (`docs/haproxy_reverse_proxy.md:54`)
  so per-name `/etc/hosts` edits are no longer needed (the wildcard
  covers new names automatically). This file is markdown, so the
  `.claude/rules/slop-scan-for-docs.md` gates apply to the edit.

## Tests & validation gates
This is infrastructure HCL with no automated unit-test harness, so the
reproducing-test rule in `.claude/rules/python-testing.md` does not bind
here (there is no python and no `pytest` surface). The gate that binds is
the repo's configured loop gate; acceptance is the live evals below plus
the adversarial review (`.claude/rules/adversarial-reviews.md`).

### Repo gate (must be green before `just apply`)
The single configured loop gate is **`just pre_commit`**
(`.loop/config.json` `gates`), which runs `pre-commit run --all-files`
(root `justfile` `pre_commit` recipe). The hooks that touch this change,
from `.pre-commit-config.yaml`:
- `nomad-fmt` (`nomad fmt -recursive`) — the new `dnsmasq.hcl` must be
  formatted. Run `just format` first.
- `terraform-fmt` (`terraform fmt -check -recursive`) and
  `terraform-validate` (`scripts/tf_validate.sh`, which
  `terraform validate`s the `deployments/infrastructure` root offline) —
  the `services.tf` edit must format and validate.
- `check-yaml` / `end-of-file-fixer` — the doc and any YAML.
The `.pre-commit-config.yaml` `exclude: '^\.(claude|loop)/'` means the
ticket and eval files themselves are not linted.

### Evals (live cluster — close-out acceptance, run after `just apply`)
Substitute `<firebat>` with `192.168.2.30`. Command + expected each.

1. **The dnsmasq alloc is healthy.**
   - **Command:** `nomad job status dnsmasq`
   - **Expected:** `Status = running`, latest deployment `successful`,
     alloc `healthy` (not `pending`/`failed`). A stuck alloc is the
     signature of the port-53-already-bound gap (Q2).
2. **Wildcard resolution — a known name.**
   - **Command:** `dig @<firebat> minio.localstack +short`
   - **Expected:** `192.168.2.30`.
3. **Wildcard resolution — an arbitrary name (proves the wildcard, not a
   per-name record).**
   - **Command:** `dig @<firebat> anyrandom.localstack +short`
   - **Expected:** `192.168.2.30`.
4. **Upstream forwarding — a public name still resolves.**
   - **Command:** `dig @<firebat> example.com +short`
   - **Expected:** a real public A record (non-empty, not
     `192.168.2.30`), proving `no-resolv` + `server=` forwarding works
     and clients keep internet DNS.
5. **TCP transport also answers (port 53 TCP, not just UDP).**
   - **Command:** `dig +tcp @<firebat> minio.localstack +short`
   - **Expected:** `192.168.2.30`.
6. **End-to-end reachability through the resolved name.**
   - **Command:** `curl -s -o /dev/null -w '%{http_code}\n'
     --resolve grafana.localstack:80:<firebat>
     http://grafana.localstack/` (the `--resolve` mirrors what the new
     DNS gives every client)
   - **Expected:** `200`/`302` — the name resolves to firebat and HAProxy
     routes to Grafana.

**Eval marker:** the six scenarios above are encoded as the
Definition-of-Done marker at
`.loop/evals/F4-foundation-dnsmasq-localstack-dns.md` (co-author it with
the `create-eval` skill before implementation). `.loop/config.json` sets
`require_eval: true`, so the loop will refuse pickup until this marker
exists.

## Risk assessment
- **Blast radius — low for existing services, high for any client that
  adopts this as primary DNS.** The job itself only adds a listener on
  firebat:53; it changes nothing about existing HAProxy routing or
  backends. But once a device points its resolver here, a
  misconfiguration (missing/failing upstream forwarding) breaks **all**
  DNS for that device, not just `.localstack`. This is why Requirement 2
  (upstream forwarding + `no-resolv`) and eval 4 are load-bearing.
- **Reversibility — high.** `nomad job stop dnsmasq` removes the
  listener; clients fall back to their previous DNS (or the operator
  reverts the router DHCP pointer). The Mac `/etc/hosts` line, left in
  place, still works. No data, no migration.
- **Likeliest failure modes:**
  1. **Port 53 already bound on firebat** (host `systemd-resolved` or
     similar) → job stuck `pending`/`failed`. Caught by the pre-deploy
     check (§Requirement 6) and eval 1. See Q2.
  2. **Upstream forwarding misconfigured** (forgot `no-resolv`, or
     `/etc/resolv.conf` under host networking points back at firebat) →
     resolution loop or dead public DNS. Caught by eval 4.
  3. **Firewall not opened for 53** → LAN clients time out even though
     the job is healthy. Caught by evals 2-5 run from a *remote* host.
  4. **UDP works, TCP does not** (or vice versa) → large responses or
     TCP-only clients fail. Caught by eval 5.

## Subtickets (ordered, dependency-aware)
1. **Pre-deploy port check.** Confirm nothing binds firebat:53 (Q2). If
   occupied, resolve out-of-band before proceeding.
2. **Author `services/dnsmasq.hcl`.** New job per §7, copying HAProxy's
   host-network + `NET_BIND_SERVICE` idiom; config template carries the
   wildcard, `no-resolv`, and upstream `server=` lines. Run
   `just format`.
3. **Wire Terraform.** Add the `nomad_job "dnsmasq"` resource and the
   `dnsmasq` firewall entry in `services.tf` per §7. Run
   `scripts/tf_validate.sh` (via `just pre_commit`).
4. **Update `docs/haproxy_reverse_proxy.md`.** DNS Setup + Adding-a-
   Service runbook + the manual router-DHCP step. Run the doc slop gates.
5. **Deploy + verify.** `just apply` from
   `deployments/infrastructure/`, then run the six evals in §8, then the
   adversarial review.

## Resolved decisions (operator-settled)
- **Q1 — dnsmasq image: RESOLVED.** Pin
  `docker.io/4km3/dnsmasq:2.90-r3@sha256:52e25fb2601156ab66f6a0872c180b285df7cafaa41267d8d65689f066490641`.
  Verified via `docker buildx imagetools inspect` to publish a
  `linux/arm64` variant (the cluster is Orange Pi / arm64); minimal
  alpine base, dnsmasq 2.90. The tag@manifest-list-digest is pinned so
  podman still selects the arm64 variant while the digest guarantees
  immutability. Do not substitute `latest`.
- **Q3 — firewall reach: RESOLVED → LAN + Tailscale.** Open 53/udp and
  53/tcp to both `192.168.0.0/16` and `100.64.0.0/10`, matching HAProxy's
  reach (`services.tf:188-192`), so remote Tailscale clients also resolve
  `.localstack`. (Already encoded in Requirement 5.)
- **Q4 — upstream resolver: RESOLVED → Cloudflare.** Forward to
  `server=1.1.1.1` and `server=1.0.0.1`. (Already encoded in
  Requirement 2.)

## Open questions
- **Q2 — Is firebat:53 already bound (e.g. `systemd-resolved`)?** The only
  outstanding pre-deploy check. Many Debian/Ubuntu hosts run
  `systemd-resolved` on `127.0.0.53:53`, but the job binds the host's LAN
  IP `192.168.2.30:53` under host networking, which may or may not
  collide. **Action:** operator runs `sudo ss -ulpn 'sport = :53'` on
  firebat before deploy; if occupied by `systemd-resolved`, either disable
  its stub listener (`DNSStubListener=no`) or bind dnsmasq to the LAN IP
  explicitly. This is a host-state fact the repo cannot see; it gates the
  deploy (§Requirement 6, eval 1), not the coding.
