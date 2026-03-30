# Adding Orange Pi RV2 (RISC-V) to the Cluster

## Context

The Orange Pi RV2 (SpacemiT K1, 8-core RISC-V, up to 4GB RAM, Ubuntu 24.04) will join the existing 4-node homelab cluster as a Nomad worker running monitoring (node_exporter) and NATS + JetStream.

HashiCorp doesn't publish pre-compiled Nomad/Consul binaries for riscv64. NATS doesn't publish riscv64 container images either. All three are Go-based and can be cross-compiled, with Nomad/Consul needing a patched `raft-boltdb` dependency.

Prometheus and Grafana run on `firebat` per the existing monitoring plan -- their riscv64 support is irrelevant.

## riscv64 Support Matrix

| Component | Official riscv64? | Action needed |
|---|---|---|
| Nomad | No | Cross-compile with `raft-boltdb` fork |
| Consul | No | Cross-compile with `raft-boltdb` fork |
| nomad-driver-podman | No | Cross-compile (pure Go, trivial) |
| CNI plugins | Yes | Download from GitHub releases |
| Podman | Debian repos | `apt install` or build from source |
| node_exporter | Binary: yes, Image: no | Use official binary via `raw_exec`, or build riscv64 image |
| NATS server | No | Cross-compile (pure Go, trivial) or build riscv64 image |

## Implementation Plan

### Step 1: Cross-compile binaries

Create `bootstrap/cross-compile/build-riscv64.sh` -- a script that builds all required binaries for riscv64.

**Prerequisites** (on dev machine or CI):
- Go 1.22+
- `riscv64-linux-gnu-gcc` (for Nomad's CGO)

**Binaries to build:**

1. **Nomad** (pin to version matching cluster):
   - Clone `hashicorp/nomad` at the matching tag
   - Add `replace` directive in `go.mod`: replace `github.com/hashicorp/raft-boltdb/v2` with Elara6331's fork
   - `CGO_ENABLED=1 CC=riscv64-linux-gnu-gcc GOOS=linux GOARCH=riscv64 go build -o nomad ./`

2. **Consul** (pin to version matching cluster):
   - Same `raft-boltdb` replace approach
   - `CGO_ENABLED=0 GOOS=linux GOARCH=riscv64 go build -o consul ./`

3. **nomad-driver-podman**:
   - `CGO_ENABLED=0 GOOS=linux GOARCH=riscv64 go build -o nomad-driver-podman ./`

4. **nats-server** (for the NATS workload):
   - `CGO_ENABLED=0 GOOS=linux GOARCH=riscv64 go build -o nats-server ./`
   - Alternatively, build a riscv64 container image: `FROM golang:1.22 AS builder` + multi-stage with `riscv64/ubuntu`

Output: place binaries in `bootstrap/cross-compile/bin/riscv64/`

### Step 2: Update Ansible inventory

**`bootstrap/inventory/cluster.ini`** -- add under `[worker]`:
```ini
orange_pi_rv2 ansible_host=<IP>
orange_pi_rv2 ansible_user=<user>
```

### Step 3: Update bootstrap playbooks

**`bootstrap/playbooks/install_dependencies.yml`**:

1. Extend arch map:
   ```yaml
   hashicorp_arch_map:
     aarch64: arm64
     x86_64: amd64
     riscv64: riscv64
   ```

2. Make the "Install Hashistack products" task conditional on architecture:
   ```yaml
   - name: Install Hashistack products (apt)
     ansible.builtin.apt:
       name: [consul, vault, nomad, nomad-driver-podman]
       state: present
     when: ansible_architecture != 'riscv64'

   - name: Install Hashistack products (riscv64 cross-compiled)
     ansible.builtin.copy:
       src: "cross-compile/bin/riscv64/{{ item }}"
       dest: "/usr/bin/{{ item }}"
       mode: '0755'
     loop: [nomad, consul]
     when: ansible_architecture == 'riscv64'

   - name: Install nomad-driver-podman (riscv64)
     ansible.builtin.copy:
       src: "cross-compile/bin/riscv64/nomad-driver-podman"
       dest: "/opt/nomad/plugins/nomad-driver-podman"
       mode: '0755'
     when: ansible_architecture == 'riscv64'
   ```

3. CNI plugins download already uses `hashicorp_arch` variable -- just ensure riscv64 release exists for the pinned version (containernetworking publishes riscv64 tarballs).

**`bootstrap/playbooks/configure_podman.yml`**:
- Podman should be available via `apt` on Ubuntu 24.04 riscv64. If not, add a fallback to install from Debian sid riscv64 repos.

### Step 4: NATS + JetStream Nomad job

Create `deployments/applications/services/nats.hcl`:

```hcl
job "nats" {
  datacenters = ["localstack"]
  type        = "service"

  constraint {
    attribute = "${attr.unique.hostname}"
    value     = "orange-pi-rv2"  # confirm actual hostname
  }

  group "nats" {
    count = 1

    network {
      port "client"  { static = 4222 }
      port "monitor" { static = 8222 }
    }

    volume "nats_data" {
      type   = "host"
      source = "nats_data"
    }

    task "nats" {
      driver = "raw_exec"  # use raw_exec with cross-compiled binary

      artifact {
        # or copy binary via Ansible and use local path
        source = "<url-or-local-path>/nats-server"
        destination = "local/nats-server"
        mode = "file"
      }

      config {
        command = "local/nats-server"
        args = [
          "--config", "local/nats.conf",
          "--store_dir", "${NOMAD_ALLOC_DIR}/jetstream",
        ]
      }

      template {
        data = <<-EOT
          listen: 0.0.0.0:4222
          http: 0.0.0.0:8222
          jetstream {
            store_dir: {{ env "NOMAD_ALLOC_DIR" }}/jetstream
            max_mem: 256M
            max_file: 4G
          }
        EOT
        destination = "local/nats.conf"
      }

      resources {
        cpu    = 1000
        memory = 512
      }

      service {
        name = "nats"
        port = "client"
        check {
          type     = "http"
          port     = "monitor"
          path     = "/healthz"
          interval = "10s"
          timeout  = "2s"
        }
      }
    }
  }
}
```

**Alternative**: If Podman works reliably on the RV2, build a custom riscv64 NATS container image and use the `podman` driver instead of `raw_exec`. This is cleaner but adds the image build step.

### Step 5: Infrastructure Terraform additions

**`deployments/infrastructure/services.tf`**:
- Add `nats_data` dynamic host volume on the RV2 node
- Add firewall rules for ports 4222 (NATS client) and 8222 (NATS monitoring)

**`deployments/infrastructure/services/haproxy.hcl`**:
- Optionally add NATS monitoring backend (`nats.localstack` -> RV2:8222)

### Step 6: Monitoring integration

The node_exporter system job from the monitoring plan will auto-schedule on the RV2 once it joins the cluster. **However**, the `prom/node-exporter` container image doesn't have riscv64 support.

Options:
- **A (Recommended)**: Use `raw_exec` driver for node_exporter on riscv64 nodes (official binary exists), `podman` driver on others. This requires a second task group with a `constraint` on `attr.cpu.arch == "riscv64"`.
- **B**: Build a custom riscv64 node_exporter container image.

Add NATS as a Prometheus scrape target (port 8222 exposes `/varz` metrics, or use the [prometheus-nats-exporter](https://github.com/nats-io/prometheus-nats-exporter)).

## Key Files

| File | Action |
|---|---|
| `bootstrap/cross-compile/build-riscv64.sh` | **New** -- cross-compile script |
| `bootstrap/inventory/cluster.ini` | Add RV2 node |
| `bootstrap/playbooks/install_dependencies.yml` | Add riscv64 arch map + conditional binary install |
| `bootstrap/playbooks/configure_podman.yml` | Verify/add riscv64 Podman install path |
| `deployments/applications/services/nats.hcl` | **New** -- NATS + JetStream job |
| `deployments/infrastructure/services.tf` | Add nats_data volume + firewall rules |
| `deployments/infrastructure/services/haproxy.hcl` | Add NATS monitoring backend |
| `deployments/infrastructure/services/node-exporter.hcl` | Add riscv64 task group variant (when monitoring deploys) |

## Verification

1. Run `build-riscv64.sh` -- produces binaries in `bootstrap/cross-compile/bin/riscv64/`
2. Run `just bootstrap` -- RV2 node gets Nomad + Consul + Podman installed
3. `nomad node status` shows the RV2 with `riscv64` arch and `ready` status
4. `nomad job run nats.hcl` -- allocation lands on RV2, NATS starts
5. `nats sub test` / `nats pub test hello` from any cluster node confirms connectivity
6. Prometheus targets page shows RV2's node_exporter as UP
7. `curl http://<rv2-ip>:8222/varz` returns NATS metrics
