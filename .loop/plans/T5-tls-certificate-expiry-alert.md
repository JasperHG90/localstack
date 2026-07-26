---
epic = "tls"
depends_on = []
priority = 90
summary = "Alert on days-to-certificate-expiry at the edge. Deferred out of T3 because nothing in the cluster measures it: needs a blackbox exporter, a scrape config and a firewall rule before an alert rule has anything to read. Until this lands, a failed renewal is silent for 30 days and then takes all twelve routed services down at once."
tags = ["tls", "monitoring", "alerting", "prometheus", "blackbox-exporter"]
---

# T5 — Alert on certificate expiry before the edge silently outlives its cert

## Title
Measure days-to-expiry on the edge certificate and alert on it, so a failed
renewal is noticed while there is still time to fix it rather than when every
routed service stops answering.

## Size / Effort
**Medium.** One new Nomad job, one scrape config, one firewall entry, one
alert rule. Small in lines, but it adds a service to the monitoring path and
the alert has to be provably firing rather than merely present.

## Triggered by
Deferred out of T3-tls-edge-cutover-lab-domain by operator decision,
2026-07-26. T3 carried this as requirement 11 and could not deliver it: an
alert rule alone has no metric to read, and creating one falls outside T3's
declared code surface. T3's plan and eval row both record the deferral.

## Context (today's state)
- **Nothing in the cluster measures certificate expiry.** Confirmed by
  measurement, not inference:
  - HAProxy's exporter serves 39 SSL-related metrics on
    `http://192.168.2.30:8404/metrics` and every one is a connection or rate
    counter (`haproxy_process_current_ssl_connections`,
    `haproxy_process_ssl_connections_total`, `..._current_ssl_rate`, and so
    on). None carries a notAfter or an expiry.
  - No blackbox exporter exists anywhere in the repo: a search for
    `blackbox`, `probe_ssl`, `ssl_expiry` and `x509` across
    `deployments/` returns nothing.
  - Prometheus scrapes eight jobs (`services/prometheus.hcl:71-126`:
    prometheus, nomad, consul, haproxy, postgres, minio, node,
    consul_services) and **none over HTTPS**, so no scrape observes a
    certificate at all.
- **The exposure this closes.** Since T3, HAProxy serves the Let's Encrypt
  wildcard from Vault KV2 for all twelve routed hostnames. The `acme` job
  runs daily on a cron (`services/acme.hcl:11`) with `--renew-days 30`
  (`services/acme.hcl:65`), so renewal attempts begin 30 days before expiry
  and retry daily. If every attempt fails, nothing reports it. **The window
  between the first failed renewal and a dead edge is 30 days**, and the
  failure mode is all twelve services at once. 30 days is the margin, not the
  90-day life of the leaf; do not conflate them.
- **The alert file is Grafana-provisioned, not Prometheus rules.**
  `services/grafana/alert-rules.yaml` holds 16 rules under `apiVersion: 1`
  with `groups[].rules[]`, each carrying `uid`, `title`, `condition`, and a
  `data` list of refIds where the query model has `datasourceUid: prometheus`
  and an `expr`. Copy `alert-node-down` (`alert-rules.yaml:8-20`) for shape.
  A Prometheus-style `alerting_rules.yml` would not be loaded.
- **A working delivery path already exists.** The `NodeDown` alert routes to
  a Telegram contact point configured in `services/grafana.hcl`, so this
  ticket does not need to build notification delivery, only to reuse it.
- Firewall entries follow the `firewall_rules` map shape, applied over SSH by
  `null_resource.firewall` (`services.tf`). The single-source pattern to copy
  is `node_exporter_ubuntu` (`services.tf:250-254`).

## Non-goals / out of scope
- Changing issuance, renewal, or anything about the `acme` job.
- Alerting on the `acme` job's success or failure. That was considered and
  rejected in T3: it catches one link in the chain and stays silent when the
  job succeeds but HAProxy never picks the new certificate up. Alert on the
  certificate a client actually receives.
- Probing anything other than the edge certificate. No HTTP uptime checks,
  no multi-target probing of every service, no synthetic monitoring.
- Adding authentication to Prometheus or Loki (that gap is real and recorded
  in `docs/monitoring.md`, but it is not this ticket).
- Restructuring `alert-rules.yaml` or touching the other 16 rules.

## Requirements & restrictions
1. The metric must come from **the certificate a client actually receives at
   the edge**, not from Vault's stored copy and not from the acme job's
   state. A certificate that is fine in Vault but not being served is exactly
   the case that must fire.
2. Probe over the real hostname so the check also exercises SNI and the
   served chain. `grafana.lab.orangecluster.nl` is a reasonable target.
3. The alert fires on **days remaining**, with a threshold that leaves room
   to act. The renewal margin is 30 days, so alerting below ~21 days means
   roughly nine days of failed renewals have already passed and there are
   still three weeks to fix it. Justify whatever number is chosen.
4. Follow the Grafana provisioned-alert shape in `alert-rules.yaml`
   (`apiVersion: 1`, `groups[].rules[]`, `datasourceUid: prometheus`), not
   Prometheus alerting rules.
5. Pin the exporter image by digest, not by tag. Tag-plus-digest refs are
   rejected by the podman driver, which is what
   T4-tls-fix-podman-image-digest-refs exists for. Use an arm64 image.
6. The exporter must not be reachable from the whole LAN. Narrow its
   firewall entry to the Prometheus node, in the spirit of
   N1-netsec-restrict-prometheus-loki-to-cluster.
7. **The ufw hazard N1 documented applies to any firewall change here.**
   Both `ufw allow` and `ufw delete` rebuild the chain from
   `/etc/ufw/user.rules`, so a rule present only in the live chain is lost on
   the next write. Read the runbook in `docs/monitoring.md` before applying,
   and check for divergence on the target node first.
8. Terraform providers pinned at `providers.tf:1-24`. Do not bump.
9. `.claude/rules/adversarial-reviews.md`: adversarial review before done.

## Code surface
- `deployments/infrastructure/services/blackbox-exporter.hcl` **(new)** — the
  Nomad job. Driver `podman`, arm64 image pinned by digest, a `tls_connect`
  or `http_2xx` module that records the certificate, a `network` port, a
  `service` + health `check`. Pattern: `services/node-exporter.hcl` for a
  small exporter, `services/prometheus.hcl:55` for `network_mode = "host"`.
- `deployments/infrastructure/services.tf` — a `resource "nomad_job"
  "blackbox_exporter"` (pattern: the `nomad_job` blocks nearby), plus a
  `firewall_rules` entry admitting only `192.168.2.47` to the exporter's
  port (pattern `services.tf:250-254`).
- `deployments/infrastructure/services/prometheus.hcl:71-126` — a
  `job_name: blackbox` scrape config using the standard relabel dance
  (`__address__` to the exporter, `__param_target` to the probed URL).
- `deployments/infrastructure/services/grafana/alert-rules.yaml` — one new
  rule on `probe_ssl_earliest_cert_expiry`, modeled on `alert-node-down`
  (`:8-20`).
- `docs/monitoring.md` — document the probe and the alert in the current-state
  section at the top of the file.
- `docs/tls-certificates.md` — its "Recovering a failed renewal" section says
  a failure "is silent". Once this lands it is not. Update it.

## Tests & validation gates
No unit-test harness for infra HCL, no CI. Repo gate plus live evals.

### Repo gate
- **Command:** `just pre_commit` -> all Passed.
- **Worktree prerequisite:** `just worktree_setup <path>`. Note it copies
  only the infrastructure root's `prod.tfvars`; the applications root needs
  its own copy if you plan there.
- **Command:** `terraform -chdir=deployments/infrastructure plan` -> adds the
  exporter job and its firewall entry, updates prometheus and grafana in
  place, and touches nothing else.

### Offline check before applying
Prometheus and Grafana both fail closed on a malformed config. Render the
scrape config and the alert rule and validate them before the apply, the way
T3 validated the HAProxy config: `promtool check config` for the scrape
block, and confirm the alert YAML parses under Grafana's provisioning schema.
Run a negative control on each so the check is known to discriminate.

### Evals — the authoritative set is `.loop/evals/T5-tls-certificate-expiry-alert.md`

## Risk assessment
- **Blast radius: small and additive.** A new job, one scrape config, one
  alert rule. Nothing existing changes behavior. The one way to hurt the
  cluster is a malformed Prometheus config, which fails the scrape reload,
  hence the offline check.
- **The alert that never fires is the real risk.** An alert rule that is
  present, parses, and would never fire is worse than no alert, because it
  buys false confidence about exactly the failure it was built for. The eval
  must force the condition rather than assert the rule exists.
- **Probing through the edge couples this to the edge.** If HAProxy is down,
  the probe fails and the alert may fire for the wrong reason. That is
  arguably correct behavior, but decide it deliberately rather than
  discovering it at 3am.
- **Reversibility: high.** Remove the job, the scrape config and the rule.
  The ufw rule needs deleting by hand, per requirement 7.

## Subtickets (ordered)
1. Deploy the blackbox exporter job, narrowed by firewall to the Prometheus
   node.
2. Add the scrape config; confirm `probe_ssl_earliest_cert_expiry` appears in
   Prometheus with a sane value for the current certificate.
3. Add the alert rule; force the condition and observe it fire and deliver.
4. Docs.
5. Adversarial review.

## Open questions
- **Q1 — Probe the edge hostname or `192.168.2.30:443` with an SNI
  override?** *Recommendation: the hostname.* It exercises DNS, SNI and the
  served chain together, which is what a client does. The cost is that a DNS
  failure also trips this alert.
- **Q2 — What threshold?** *Recommendation: 21 days.* The renewal margin is
  30, so 21 means renewal has been failing for about nine days and there are
  three weeks left. A threshold above 30 would fire constantly; one below 7
  leaves no room.
- **Q3 — Should this also alert when the probe itself stops reporting?**
  A deleted job or a broken scrape makes the metric absent, and an alert on a
  value can never fire on a missing series. *Recommendation: yes, add an
  `absent()` companion condition.* Otherwise removing the exporter silently
  removes the alarm, which is the same class of failure this ticket exists to
  close.
