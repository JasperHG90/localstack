# Prometheus + Grafana Monitoring Stack

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
