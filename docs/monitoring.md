# Prometheus + Grafana Monitoring Stack

## How to reach the monitoring stack today

Prometheus and Loki do not accept **direct** connections from the LAN. Both
serve their query APIs with no authentication, so their firewall rules admit
only the callers that need them, and going straight to `192.168.2.47:9090` or
`192.168.2.47:3100` from an ordinary LAN device fails. This describes what
Terraform declares. It is true of the host once the apply in *Applying a
change to these rules* below has run, and the last commands in that section
are how to confirm it.

| Service | Port | Who may connect directly |
|---|---|---|
| Prometheus | 9090 | `192.168.2.47` (Grafana's datasource, same node), `192.168.2.30` (HAProxy) |
| Loki | 3100 | all five node addresses (promtail is a `system` job), which includes `192.168.2.30` for HAProxy |
| Grafana | 3000 | `192.168.0.0/16` and `100.64.0.0/10`, unchanged |

Grafana is unchanged. It requires a login, so it keeps its LAN and tailnet
reach on port 3000.

Prometheus scraping is unaffected. It dials outward to its targets, and no
inbound rule touches that.

### The edge path is still open, and still unauthenticated

Closing the direct port does **not** make these services private. HAProxy on
`192.168.2.30` stays on both allow-lists, and the `prometheus` and `loki`
backends carry no `http-request auth` line, unlike `phoenix`, `mlflow` and
`bifrost` in the same file (`services/haproxy.hcl`). Anyone who can reach the
edge can still read every metric and every log line, and Prometheus's admin
API is enabled. What the firewall change removes is the direct path, which is
one exposure of two.

Closing the second one means adding authentication at the edge, either the
existing basic-auth pattern or the OIDC work the rollout epic is doing for
other services. No ticket owns that for these two backends today.

Note also that `prometheus.localstack` and `loki.localstack` do not resolve
on the LAN, so the edge is reachable by address or by a hosts entry rather
than by name. The edge cutover ticket renames this whole set to the
`lab.orangecluster.nl` domain, which is when the names start working.

### Applying a change to these rules

`null_resource.firewall` runs `ufw allow` and has no destroy provisioner, so
narrowing a rule in Terraform does not remove the old permissive one. The
broad rule must be deleted by hand or the change is cosmetic while looking
applied.

**Before running any ufw command that writes a rule, check for rules that
exist in the live chain but not in ufw's database.** Both `ufw allow` and
`ufw delete` emit an `iptables-restore` payload that re-declares
`ufw-user-input` and rebuilds it from `/etc/ufw/user.rules`, so a rule
missing from that file is dropped by the next write of any kind. This is not
a delete-only hazard: a plain `terraform apply` of a neighboring rule is
enough to lose it, silently and with no error.

Measured on 2026-07-26, `192.168.2.47` had two such rules: Grafana's LAN
access on 3000, and node-exporter on 9100. Applying this ticket's narrowed
Prometheus rule would have dropped both from the chain.

Only one of them matters, and it is the dangerous one. **Losing Grafana's
3000 rule takes Grafana down by every route, tailnet included.** `ubuntu`
has no tailscale interface (`lo`, `eth0`, `wlan0`, `podman0`, `veth0`), so
the `100.64.0.0/10` rule beside it is already dead at the interface level and
is not a fallback. Tailnet users arrive at `grafana.localstack`, which
resolves to the tailnet address of HAProxy, and HAProxy then dials
`192.168.2.47:3000` from `192.168.2.30`, a LAN source admitted by the LAN
rule. Everyone depends on the rule that would vanish, and nothing announces
it.

Losing the 9100 rule, by contrast, breaks nothing. Its source and its host
are the same machine, `.47` to `.47` routes over `lo`
(`ip route get 192.168.2.47`), and ufw accepts loopback in
`ufw-before-input` (`-A ufw-before-input -i lo -j ACCEPT`) before the user
chain is consulted. The scrape keeps working and `NodeDown`
(`services/grafana/alert-rules.yaml`) stays quiet. The same is true of the
`192.168.2.47` entries this ticket adds for 9090 and 3100: they are
belt-and-braces, matching the shape of the neighboring rules, not load
bearing.

`192.168.2.30` has one diverged rule of its own, `9187` from `192.168.2.47`.
That one is between different machines, so it is real.

Check it, and preview the result, without changing anything. `--dry-run`
prints the payload and touches neither the chain nor `user.rules`:

```bash
# rules that are live but absent from ufw's database
sudo iptables -S ufw-user-input | grep ACCEPT
sudo grep '^### tuple ###' /etc/ufw/user.rules

# the exact chain the next write would leave behind
sudo ufw --dry-run allow from 192.168.2.47 to any port 9090 proto tcp
```

Re-assert anything missing in the **same** apply that narrows the rules,
rather than in a separate pass beforehand. Every `ufw allow` writes its rule
to `user.rules` before rebuilding the chain from it, so once all the writes
have run the database holds everything and the order among them does not
matter. Both diverged rules are already declared in Terraform, so adding
`-replace` for their resources restores them through the normal path:

```bash
cd deployments/infrastructure
CONSUL_HTTP_TOKEN=${CONSUL_TOKEN} terraform apply \
  -var-file=./vars/prod.tfvars \
  -parallelism=1 \
  -replace='null_resource.firewall["grafana"]' \
  -replace='null_resource.firewall["node_exporter_ubuntu"]'
```

`-parallelism=1` matters here: this apply drives three separate `ufw` writes
against one host, and concurrent writes can lose each other's rules. ufw does
take an exclusive lock on `/run/ufw.lock`, but it reads the rule set before
acquiring it, so two overlapping invocations can each start from the same
pre-write state and the second then writes a file missing the first's rule.
Serialized invocations are safe, which is why the order among them does not
matter above. Check the plan
before confirming. It also carries whatever else is pending in this root. At
the time of writing that includes the dnsmasq removal from the ticket before
this one, which is expected rather than a surprise.

Then the applications root, for Loki:

```bash
cd deployments/applications
CONSUL_HTTP_TOKEN=${CONSUL_TOKEN} terraform apply -var-file=./vars/prod.tfvars
```

Last, delete the superseded broad rules on `192.168.2.47`. Nothing in
Terraform does this, and skipping it leaves the change cosmetic:

```bash
sudo ufw delete allow from 192.168.0.0/16 to any port 9090 proto tcp
sudo ufw delete allow from 100.64.0.0/10 to any port 9090 proto tcp
sudo ufw delete allow from 192.168.0.0/16 to any port 3100 proto tcp
```

Delete by rule spec rather than by index: `ufw status numbered` renumbers
after every deletion, so a list of index numbers goes stale as you work
through it. Confirm afterwards from a non-cluster LAN device, since a rule
still listed in `ufw status` is the whole failure this section exists to
prevent:

```bash
curl -sS --max-time 5 'http://192.168.2.47:9090/api/v1/query?query=up'  # must fail
curl -sS --max-time 5 http://192.168.2.47:3100/loki/api/v1/labels       # must fail
curl -s -o /dev/null -w '%{http_code}\n' http://192.168.2.47:3000       # must stay 302
```

---

The rest of this document is the original build plan for the stack. It
predates the move of Prometheus and Grafana from firebat to
`ubuntu` (`192.168.2.47`) and the addition of Loki, so treat the addresses
and file lists below as history rather than as current state.

## Context

The cluster has 4 nodes running various services but no metrics collection or dashboarding. Prometheus + Grafana will provide visibility into node health, service metrics, and infrastructure components. Memex, MinIO, HAProxy, PostgreSQL, Nomad, and Consul all expose Prometheus-compatible metrics endpoints.

## Placement Decision

**Prometheus + Grafana on `firebat` (192.168.2.30)** -- the server node has the most headroom (2500 CPU / 4224 MEM currently used) and already hosts infrastructure services (PostgreSQL, HAProxy). Monitoring belongs in the infrastructure layer.

## Scrape Targets

| Target | Endpoint | Host |
|---|---|---|
| Prometheus self | :9090/metrics | firebat |
| Node exporter (x4) | :9100/metrics | all nodes |
| Nomad | :4646/v1/metrics?format=prometheus | firebat |
| Consul | :8500/v1/agent/metrics?format=prometheus | firebat |
| HAProxy | :8404/metrics (prometheus-exporter) | firebat |
| PostgreSQL | :9187/metrics (postgres_exporter sidecar) | firebat |
| MinIO | :9000/minio/v2/metrics/cluster | orangepi4a |
| Memex | :8000/metrics | jetson-orin-nano |

## Implementation

### Phase 1: Bootstrap config changes (Ansible templates)

**1a. Add Nomad telemetry block** to both server and client templates:

- `bootstrap/roles/nomad_server/templates/nomad.hcl.j2` -- add before `plugin` block:
  ```hcl
  telemetry {
    publish_allocation_metrics = true
    publish_node_metrics       = true
    prometheus_metrics         = true
  }
  ```
- `bootstrap/roles/nomad_client/templates/nomad.hcl.j2` -- same block before `server` block

**1b. Enable Consul Prometheus retention** in `bootstrap/roles/consul_server/templates/consul.hcl.j2`:

Change existing `telemetry {}` block to:
```hcl
telemetry {
  disable_hostname          = true
  prometheus_retention_time = "60s"
}
```

> After these changes, user must re-run bootstrap playbooks to propagate.
> Nomad/Consul ACL tokens may be needed for scraping -- handle with Vault templates in the Prometheus job config. If anonymous access works, tokens are simply unused.

---

### Phase 2: Infrastructure Terraform changes

All changes in `deployments/infrastructure/`.

#### 2a. `secrets.tf` -- Grafana admin password

```hcl
resource "random_password" "grafana_admin" {
  length  = 24
  special = false
}

resource "vault_kv_secret_v2" "grafana_admin_credentials" {
  mount = vault_mount.kvv2.path
  name  = "default/grafana/admin"
  data_json = jsonencode({
    username = "admin"
    password = random_password.grafana_admin.result
  })
  delete_all_versions = false
  custom_metadata {
    max_versions = 5
    data = { managed_by = "terraform" }
  }
}
```

#### 2b. `services.tf` -- Volumes, firewall, job resources

**Dynamic host volumes:**
- `prometheus_data` on firebat (50 GiB max / 5 GiB min)
- `grafana_data` on firebat (5 GiB max / 1 GiB min)

**Firewall rules** (add to existing `locals.firewall_rules`):
- `prometheus`: firebat, allow 192.168.0.0/16 + 100.64.0.0/10 to port 9090
- `grafana`: firebat, allow 192.168.0.0/16 + 100.64.0.0/10 to port 3000
- `node_exporter_*` (one per node): allow only 192.168.2.30 (Prometheus) to port 9100
- `postgres_exporter`: firebat, allow 192.168.2.30 to port 9187

**Nomad job resources:**
```hcl
resource "nomad_job" "prometheus" {
  jobspec = templatefile("${path.module}/services/prometheus.hcl", {})
  depends_on = [nomad_dynamic_host_volume.prometheus_data]
}

resource "nomad_job" "grafana" {
  jobspec = templatefile("${path.module}/services/grafana.hcl", {
    grafana_secret = vault_kv_secret_v2.grafana_admin_credentials.path
  })
  depends_on = [nomad_dynamic_host_volume.grafana_data]
}

resource "nomad_job" "node_exporter" {
  jobspec = templatefile("${path.module}/services/node-exporter.hcl", {})
}
```

#### 2c. New file: `services/prometheus.hcl`

- Job type `service`, constrained to `firebat`
- Image: `docker.io/prom/prometheus:v3.2.1`
- Static port 9090, `network_mode = "host"`
- Volume `prometheus_data` mounted at `/prometheus`
- Args: `--config.file=/local/prometheus.yml`, `--storage.tsdb.path=/prometheus`, `--storage.tsdb.retention.time=30d`
- Template block renders `prometheus.yml` to `/local/prometheus.yml` with all static scrape configs (30s interval)
- Consul service registration with health check on `/-/healthy`
- Resources: 1000 CPU / 1024 MEM
- No Vault block needed (all scrape targets are on private LAN)

#### 2d. New file: `services/grafana.hcl`

- Job type `service`, constrained to `firebat`
- Image: `docker.io/grafana/grafana:11.5.2`
- Static port 3000, `network_mode = "host"`
- Volume `grafana_data` mounted at `/var/lib/grafana`
- Vault block + template for `GF_SECURITY_ADMIN_PASSWORD` from `secret/data/default/grafana/admin`
- Template block for datasource provisioning YAML (auto-configures Prometheus at `http://192.168.2.30:9090`)
- Podman volume mount: `local/provisioning/datasources/prometheus.yml:/etc/grafana/provisioning/datasources/prometheus.yml:ro`
- Env: `GF_SECURITY_ADMIN_USER=admin`
- Consul service registration with health check on `/api/health`
- Resources: 500 CPU / 256 MEM

#### 2e. New file: `services/node-exporter.hcl`

- Job type `system` (runs on all 4 nodes automatically)
- Image: `docker.io/prom/node-exporter:v1.9.0`
- Static port 9100, `network_mode = "host"`
- Podman volumes: `/proc:/host/proc:ro`, `/sys:/host/sys:ro`, `/:/host/root:ro`
- Args: `--path.procfs=/host/proc`, `--path.sysfs=/host/sys`, `--path.rootfs=/host/root`, `--collector.filesystem.mount-points-exclude=^/(sys|proc|dev|host|etc)($$|/)`
- No vault block, no volumes
- Consul service registration with health check on `/metrics`
- Resources: 200 CPU / 64 MEM

#### 2f. Modify: `services/postgres.hcl`

Add `port "exporter" { static = 9187 }` to the network block.

Add postgres_exporter sidecar task:
- `lifecycle { hook = "poststart", sidecar = true }`
- Image: `docker.io/prometheuscommunity/postgres-exporter:v0.16.0`
- `network_mode = "host"`
- Vault block + template for `DATA_SOURCE_NAME` using the existing `${postgres_secret}` path (same Vault path as main task -- both are in the `postgres` job)
- Consul service registration on port `exporter` with health check on `/metrics`
- Resources: 200 CPU / 64 MEM

#### 2g. Modify: `services/haproxy.hcl`

Add to `frontend stats`:
```
    http-request use-service prometheus-exporter if { path /metrics }
```

Add to `frontend http_in`:
```
    acl is_prometheus hdr(host) -i prometheus.localstack
    acl is_grafana    hdr(host) -i grafana.localstack
    use_backend prometheus if is_prometheus
    use_backend grafana    if is_grafana
```

Add backend blocks:
```
backend prometheus
    server prometheus1 192.168.2.30:9090 check

backend grafana
    server grafana1 192.168.2.30:3000 check
```

---

## Key Files

| File | Action |
|---|---|
| `bootstrap/roles/nomad_server/templates/nomad.hcl.j2` | Add telemetry block |
| `bootstrap/roles/nomad_client/templates/nomad.hcl.j2` | Add telemetry block |
| `bootstrap/roles/consul_server/templates/consul.hcl.j2` | Add prometheus_retention_time |
| `deployments/infrastructure/secrets.tf` | Add grafana admin password |
| `deployments/infrastructure/services.tf` | Add volumes, firewall, job resources |
| `deployments/infrastructure/services/prometheus.hcl` | **New** -- Prometheus job |
| `deployments/infrastructure/services/grafana.hcl` | **New** -- Grafana job |
| `deployments/infrastructure/services/node-exporter.hcl` | **New** -- Node exporter system job |
| `deployments/infrastructure/services/postgres.hcl` | Add postgres_exporter sidecar + port |
| `deployments/infrastructure/services/haproxy.hcl` | Add backends + prometheus-exporter directive |

## Verification

1. After bootstrap re-run: `curl http://192.168.2.30:4646/v1/metrics?format=prometheus` returns metrics
2. After `just apply`: check Nomad UI for jobs `prometheus`, `grafana`, `node-exporter` (system), `postgres` (updated)
3. Visit `prometheus.localstack` -- Status > Targets should show all 8+ targets as UP
4. Visit `grafana.localstack` -- login with admin/password-from-vault, Prometheus datasource should be pre-configured
5. Import community dashboards: Node Exporter Full (1860), PostgreSQL (9628)
