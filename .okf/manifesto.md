---
type: manifesto
title: "Manifesto"
description: "What this project is for, where its parts live, its invariants and its values."
generated:
  by: claude-opus/5.5
  at: 2026-10-19
tags: [manifesto]
---

# Manifesto

## What this is for

This repository builds and runs one personal homelab: five small computers on
one LAN, running Consul, Vault and Nomad with Podman as the container runtime.
The operator runs it for the household and for their own work, and the few
people with a Vault account reach its web apps through Vault's single sign-on.
It is public as a reference, not as a template: hostnames, nodes and service
choices fit this hardware. [Node placement](/nodes/placement.md) names the
five nodes and what each carries.

The cluster is deployed in three layers, applied in order.
[Ansible](/components/bootstrap.md) under `bootstrap/` installs and wires the
HashiStack on every node and hands Vault the tokens it brokers from. The
infrastructure root `deployments/infrastructure` configures Vault and runs the
shared services: Postgres, object storage, the HAProxy edge, monitoring and
backups. The applications root `deployments/applications` runs the workloads
and the buckets, databases and secrets they own. No layer reads another's
state. [The three deployment layers](/architecture/deployment-layers.md) says
where each boundary is and why, and [the two Terraform
roots](/components/terraform-roots.md) says how the roots find each other.

The `localstack` CLI under `cli/` is the operator's cockpit. It logs a person
in to Vault, brokers short-lived Nomad and Consul tokens from that session,
installs the HashiStack binaries at the versions the cluster runs, and reads
cluster state without writing to it. [The localstack
CLI](/components/localstack-cli.md) covers how it is built, and [the
devcontainer](/components/devcontainer.md) is the workstation it runs in.

Why each part is shaped the way it is goes in [the decision
records](/decisions/index.md). Lessons paid for in real time are in [the
practices](/practices/index.md).

## Invariants

Each `enforced` invariant names the test in `cli/tests/` that pins it. Run the
whole set with `uv run --directory cli pytest`.

- **I1** (enforced): `bootstrap/inventory/group_vars/all.yml` is the one place
  that declares the HashiStack versions. Ansible reads it, `localstack deps`
  reads it, and no source under `cli/src` carries a version literal. Pinned by
  `cli/tests/test_versions.py::test_the_ansible_pin_reads_the_same_file` and
  `cli/tests/test_versions.py::test_source_carries_no_currently_pinned_version`.
- **I2** (enforced): `localstack deps` installs nothing whose checksum does
  not match the published SHA256SUMS, and leaves no partial file behind.
  Pinned by `cli/tests/test_install.py::test_a_checksum_mismatch_installs_nothing`.
- **I3** (enforced): in the devcontainer PATH, the token shims come before the
  pinned binaries, and both come before the system PATH, so a bare `nomad`
  never runs what apt installed. Pinned by
  `cli/tests/test_devcontainer_path.py::test_shims_come_before_binaries_and_both_before_the_system`.
- **I4** (enforced): the devcontainer mounts its uv and prek caches as the
  volumes `loop-harness-uv-cache` and `loop-harness-prek-cache`, the names the
  loop-harness devcontainer uses, and points `UV_CACHE_DIR` and `PREK_HOME` at
  them. Pinned by
  `cli/tests/test_devcontainer_volumes.py::test_the_cache_is_the_loop_harness_volume`.
- **I5** (enforced): the CLI's API layer and the monitor panel only read from
  the cluster: no POST, PUT, DELETE or PATCH call. Pinned by
  `cli/tests/test_read_guardrails.py::test_the_api_layer_is_read_only` and
  `cli/tests/test_monitor_guardrails.py::test_the_panel_never_writes_to_the_cluster`.
- **I6** (enforced): the CLI takes cluster state from the live APIs, never
  from job files or `deployments/` in the repository, because some jobs run
  with no file here. Pinned by
  `cli/tests/test_read_guardrails.py::test_the_repo_tree_is_never_read_for_cluster_state`.
- **I7** (enforced): no Vault token value appears in a test fixture captured
  from the cluster or in a snapshot baseline. Pinned by
  `cli/tests/test_monitor_guardrails.py::test_no_token_value_appears_in_a_fixture_or_baseline`.
- **I8** (enforced): `docs/README.md` links every page under `docs/`, and every
  link in it resolves. Pinned by
  `cli/tests/test_docs_index.py::test_index_lists_every_page` and
  `cli/tests/test_docs_index.py::test_index_links_resolve`.
- **I9** (enforced): every page in `docs/how-to/` has the four sections of
  `.claude/rules/how-to-skeleton.md` in order, with steps numbered from one.
  Pinned by
  `cli/tests/test_how_to_skeleton.py::test_how_to_page_follows_the_skeleton`.
- **I10** (enforced): the bucket the nightly object storage backup syncs is
  one that `deployments/applications/storage.tf` declares, so a typo cannot
  buy a silently empty backup. Pinned by
  `cli/tests/test_backup_coverage.py::test_minio_backup_syncs_a_declared_bucket`.
- **I11** (planned): every durable bucket (`openviking`, `registry`, `models`
  and `datalake`) is synced to GCS nightly, not only `openviking`. Loop ticket
  `backup-durable-buckets` widens the job and the test in
  `cli/tests/test_backup_coverage.py`.

## Values

These values are a draft for the operator to approve. An agent proposed them
from the records they cite, and no test checks them.

- **Each workload gets only what it needs.** A job that needs a new grant gets
  its own Vault role and policy, and the shared `nomad-workloads` policy is
  not widened. See
  [ADR 0006](/decisions/0006-each-converted-job-gets-its-own-vault-jwt-role.md).
- **Short-lived credentials beat static ones.** Vault mints a database user
  per lease rather than a job holding a fixed password. See
  [ADR 0005](/decisions/0005-postgres-credentials-come-from-vaults-database-engine.md).
  Where a static key cannot be avoided, no policy sits beside it that reads as
  live while granting nothing. See
  [ADR 0007](/decisions/0007-openviking-static-key-has-no-claim-policy.md).
- **A surface that cannot sign a person in comes down.** Removing a web UI
  beats leaving it up without its login gate. See
  [ADR 0009](/decisions/0009-openviking-has-no-browser-surface.md).
- **The household does not depend on the cluster.** Home DNS keeps working
  when the cluster is down, at the cost of publishing private addresses. See
  [ADR 0003](/decisions/0003-lab-names-resolve-from-public-dns.md).
- **One path per kind of traffic.** Model calls go through Bifrost, even when
  a direct route would be simpler. See
  [ADR 0008](/decisions/0008-openviking-rerank-goes-through-bifrost.md).
- **Measure before trusting.** A catalog entry, a passing `terraform validate`
  or a plan that reads well is not proof. Run it against the real thing first.
  See [the vision model check](/practices/openviking-vision-models.md),
  [Terraform write-only credential
  chains](/practices/terraform-write-only-credentials.md) and [the plan
  premise sweep](/practices/plan-premise-sweep.md).
- **Knowledge goes where its reader looks.** User docs in `docs/` are sorted
  by what the reader wants to do. Decisions, lessons and designs for people
  working on the repository go in `.okf/`. See
  [ADR 0001](/decisions/0001-durable-knowledge-lives-in-an-okf-bundle.md) and
  [ADR 0002](/decisions/0002-docs-are-sorted-by-reader-intent.md).
- **Gates survive a rebuild.** The devcontainer sets up the commit gate and
  the shared caches itself, so a fresh container checks the same things. See
  [ADR 0013](/decisions/0013-devcontainer-shares-caches-with-loop-harness.md)
  and
  [ADR 0015](/decisions/0015-loopctl-owns-the-pre-commit-hook-and-chains-prek-behind-it.md).
