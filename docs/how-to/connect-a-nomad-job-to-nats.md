---
description: Hand a Nomad task the NATS broker's URL through its environment.
stale_after: 2027-01-19
sources:
  - resource: deployments/infrastructure/services/nats.hcl
  - resource: deployments/infrastructure/services.tf
---

# How to connect a Nomad job to NATS

## Introduction

This hands a Nomad task the broker's URL as an environment variable. NATS
has no auth, so the task needs no secret.

## Prerequisites

- A Nomad jobspec using the `podman` driver.
- The broker's address, see [NATS and JetStream](../reference/nats.md).

## Directions

### Step 1: Render the URL into the task's environment

```hcl
task "myapp" {
  driver = "podman"

  service {
    name = "myapp"
    # ... your usual stuff
  }

  template {
    data = <<EOF
NATS_URL=nats://192.168.2.50:4222
EOF
    destination = "secrets/file.env"
    env         = true
  }
}
```

Use the node address, not `nats.service.localstack.consul`. Nodes do not
forward `.consul` names to Consul, and Consul would answer with the
container's bridge address, which nothing outside radxa can reach.

No firewall change is needed. The rule on radxa already admits port 4222 from
`192.168.0.0/16`.

## Additional resources

- [NATS and JetStream](../reference/nats.md)
- [How to use NATS from Python](use-nats-from-python.md)
