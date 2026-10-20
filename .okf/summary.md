---
type: summary
title: "Summary"
description: "The whole project in at most 500 words: what the knowledge says, citing the concepts; start here."
generated:
  by: claude-opus/5.5
  at: 2026-10-19
tags: [summary]
---

# Summary

## The project

This repository builds and runs one personal homelab: five small computers on
one LAN running Consul, Vault and Nomad, with Podman for containers. The
operator runs it for the household and their own work, and a few people with
Vault accounts reach its web apps through Vault's single sign-on.
[firebat](/nodes/firebat.md) carries every control-plane service, and four
arm64 workers each hold a fixed set of jobs, as [node
placement](/nodes/placement.md) shows.

## How it works

[Three layers](/architecture/deployment-layers.md) deploy the cluster in
order: [Ansible](/components/bootstrap.md) installs the HashiStack and hands
Vault its tokens, then [two Terraform roots](/components/terraform-roots.md)
run the shared services and the workloads. No layer reads another's state. A
later layer finds what an earlier one made by a fixed name in Vault or Consul,
or by a literal kept equal by hand, so a wrong order shows up as a denied read
or a job that cannot be placed.

Jobs prove who they are to Vault through [the workload identity
chain](/components/workload-identity-chain.md), and people sign in through
[Vault's OIDC provider](/components/vault-oidc-provider.md). One [HAProxy
edge](/components/edge-proxy.md) on firebat terminates TLS for every lab name.
The [localstack CLI](/components/localstack-cli.md) logs the operator in,
brokers short-lived Nomad and Consul tokens, and only ever reads the cluster.

## What it has settled

Least privilege runs through the decisions: each job gets only what it needs.
A job that needs more gets its own Vault role rather than a wider shared
policy ([ADR 0006](/decisions/0006-each-converted-job-gets-its-own-vault-jwt-role.md)).
Short-lived credentials from Vault beat static ones
([ADR 0005](/decisions/0005-postgres-credentials-come-from-vaults-database-engine.md)),
and where a static key cannot be avoided, no policy beside it pretends
otherwise ([ADR 0007](/decisions/0007-openviking-static-key-has-no-claim-policy.md)).
A surface that cannot sign a person in comes down
([ADR 0009](/decisions/0009-openviking-has-no-browser-surface.md)), and Login
MFA names the userpass mount so other sign-in paths keep working
([ADR 0011](/decisions/0011-login-mfa-enforcement-names-the-userpass-mount.md)).

The household must not depend on the cluster, so lab names resolve from
public DNS ([ADR 0003](/decisions/0003-lab-names-resolve-from-public-dns.md)).
The practices teach one lesson again and again: a passing validate, a catalog
entry or a rule that looks applied is not proof. [Write-only credential
chains](/practices/terraform-write-only-credentials.md), [ufw
rules](/practices/ufw-rules-outside-user-rules.md) and [vision
models](/practices/openviking-vision-models.md) each failed quietly until
measured.

## Where it stands

The cluster runs, and Login MFA is built. All eleven of the manifesto's
invariants have a passing test. Several gaps remain open:

- [SeaweedFS](/components/seaweedfs.md) runs beside
  [MinIO](/components/minio.md) and is replacing it, restoring from the GCS
  copies of the four durable buckets that the [backup
  jobs](/components/gcs-backups.md) now make. ov-dash is stopped for lack of
  memory on orangepi4a until MinIO is removed.
- Postgres still uses static passwords. [Dynamic
  credentials](/proposals/postgres-dynamic-credentials.md) were proven in a
  spike but never rolled out.
- The manifesto's values are a draft awaiting the operator.
- Older loop tickets stopped at the `5b2ed1b` reset and were dropped, not
  built.

The bundle holds only one architecture page, says little about Grafana
dashboards or alert coverage, and records no restore test of any backup.
