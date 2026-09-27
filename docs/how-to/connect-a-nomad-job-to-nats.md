# How to connect a Nomad job to NATS

## Introduction

Treat NATS the way other shared infra is treated — Consul DNS, no secrets,
just env vars. This hands a Nomad task the broker's URL.

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
NATS_URL=nats://nats.service.localstack.consul:4222
EOF
    destination = "secrets/file.env"
    env         = true
  }
}
```

No firewall changes needed for clients — outbound to `192.168.2.50:4222` is allowed by default within the LAN. The inbound rule on radxa is already open from `192.168.0.0/16`.

## Additional resources

- [NATS and JetStream](../reference/nats.md)
- [How to use NATS from Python](use-nats-from-python.md)
