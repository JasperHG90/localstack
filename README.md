# Localstack server

TODO:

- https://developer.hashicorp.com/nomad/docs/networking/cni # Use bridge networking on all devices set up with ansible
- Podman permanent login
- Add service tags to nomad docker registry
- Deploy minio with service tags

---

Todo

- Describe static IPS
- Use ansible for setup
  + Networking setup: default deny all but allow nodes to talk to each other
- Use [consul template](https://github.com/hashicorp/consul-template) for updating UFW rules on nodes

## Core

- [Nomad](https://developer.hashicorp.com/nomad)
- [Vault](https://developer.hashicorp.com/vault)
- [Consul](https://developer.hashicorp.com/consul)

## Logging, monitoring, and alerting

- [Alertmanager](https://hub.docker.com/r/prom/alertmanager)
- [Prometheus](https://prometheus.io/)
- [Loki](https://grafana.com/oss/loki/)
- [Grafana](https://grafana.com/)

NB: keep an eye on the storage usage

## Shared services

- [Docker registry](https://hub.docker.com/_/registry)
- [Docker registry UI](https://github.com/Joxit/docker-registry-ui)
- [Gitea](https://about.gitea.com/)

## Databases & message brokers

- Postgresql
- [NATS + Jetstream](https://docs.nats.io/nats-concepts/jetstream)

## Other services
