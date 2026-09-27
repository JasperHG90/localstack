---
type: component
title: The ACME certificate job
description: "A nightly Nomad batch job on ubuntu runs lego's DNS-01 challenge against TransIP and writes the Let's Encrypt wildcard to Vault KV2 for HAProxy. It holds lego state on a host volume split by ACME environment, and uses its own Vault JWT role because the shared role cannot write to haproxy's prefix."
tags: [acme, tls, lego, transip, vault, nomad, letsencrypt]
status: stable
generated:
  by: claude-opus/5.5
  at: 2026-09-27
sources:
  - id: acme-jobspec
    resource: git:3ec5d1e:deployments/infrastructure/services/acme.hcl
  - id: infra-services
    resource: git:3ec5d1e:deployments/infrastructure/services.tf
  - id: machine-roles
    resource: git:3ec5d1e:deployments/infrastructure/machine_roles.tf
  - id: variables
    resource: git:3ec5d1e:deployments/infrastructure/variables.tf
  - id: move-off-firebat
    resource: git:5a1b16b:deployments/infrastructure/services/acme.hcl
  - id: relocate-volume
    resource: git:871ed68:deployments/infrastructure/services/acme.hcl
  - id: T1-tls-acme-letsencrypt-transip
    resource: loop:T1-tls-acme-letsencrypt-transip
  - id: T3-tls-edge-cutover-lab-domain
    resource: loop:T3-tls-edge-cutover-lab-domain
  - id: T4-tls-fix-podman-image-digest-refs
    resource: loop:T4-tls-fix-podman-image-digest-refs
---

# The ACME certificate job

The edge certificate is issued by a periodic Nomad job named `acme`. It runs
lego against Let's Encrypt with a DNS-01 challenge at TransIP, then writes
the result to `secret/data/default/haproxy/tls`, where the
[edge proxy](/components/edge-proxy.md) templates it. If this job stops
working, nothing fails for at least 30 days, and then every routed hostname
fails
together. What the job does for an operator, and the storage format, is
`docs/reference/tls-certificates.md`. The zone's public records are
[ADR 0003](/decisions/0003-lab-names-resolve-from-public-dns.md).

## The pieces

All in `deployments/infrastructure`:

| Piece | Where |
| --- | --- |
| Jobspec: `issue` prestart task (lego) and `store` task (vault CLI) | `services/acme.hcl` |
| `nomad_job.acme` and its template vars | `services.tf`, `### --- acme` section |
| `nomad_dynamic_host_volume.acme_lego_state`, pinned to ubuntu | `services.tf` |
| `vault_policy.acme_tls_write` and `vault_jwt_auth_backend_role.acme` | `machine_roles.tf` |
| `acme_domain`, `acme_email`, `acme_server` | `variables.tf` |
| TransIP key, fields `account_name` and `private_key` | `secret/data/default/acme/transip`, written by hand |

The TransIP key is created in the TransIP control panel and shown once, so no
resource can generate it. Terraform passes only the path as a string, and the
job reads the value itself. Create the key with "whitelisted IP" unchecked.
lego asks for a global token, and a whitelisted key mints tokens that
authenticate and then fail every later call. The key is account-wide with no
per-zone scope, so whoever holds it can edit every zone on the account, mail
records included. The T1 plan counts the CAA record and 2FA on the TransIP
account as the mitigations.

## One run

1. `issue` runs `lego run --renew-days 30` with every other setting in
   `LEGO_*` variables from a template. lego skips issuance while the leaf has
   more than 30 days left. It still fetches the ACME directory first, so a
   night with no DNS or no CA fails the run even when nothing was due. A red
   run is not proof of a renewal problem.
2. `store` runs only if `issue` succeeded, since a failed prestart task fails
   the allocation. It globs `*.crt` under the state directory, because lego
   names the file after the first domain with the wildcard rewritten. Then it
   runs `vault kv put` with `key=@file`, because the image has no `jq` and
   hand-escaped PEM in JSON is how an unloadable certificate gets stored.
3. `VAULT_ADDR` is the direct listener `http://192.168.2.30:8200`, never the
   edge. Routing through the edge would make renewal depend on the
   certificate it renews.

The store task writes on every successful run, renewed or not, so KV gains a
version each night. HAProxy's template re-renders only when the content
changes.

## Invariants and what holds them

- **State survives between runs.** Only `acme_lego_state` keeps lego from
  re-issuing nightly into Let's Encrypt's weekly limit. The reference page
  explains the limit.
- **Staging and production never share a directory.** The split is computed
  in `services.tf` (`acme_path`, from `var.acme_server`), not in the jobspec,
  so flipping `acme_server` is the only switch needed. The collision it
  prevents is in `docs/reference/tls-certificates.md`.
- **The job reads its own key and writes haproxy's.** `nomad-workloads`
  grants only a read on the job's own prefix. The dedicated role carries both
  `nomad-workloads` and `acme-tls-write`, because a task logs in once and a
  named role replaces the default instead of adding to it. With only the
  write policy, the TransIP template would block forever. `claim_mappings`
  must mirror the shared role, or the templated policy paths resolve to
  nothing. `vault_jwt_auth_backend_role.dash` and `.redis_cache` copy this
  shape.
- **The schedule is daily.** A daily run with a 30-day margin gives 30
  retries before expiry. A cron matching the 60-day renewal interval would
  spend the whole margin on one unseen failure.
- **`LEGO_DNS_RESOLVERS="1.1.1.1:53"`.** lego uses the system resolver to
  find the zone apex. T1 pinned a public one so renewal would not depend on
  the LAN resolver T2 was adding. That resolver is gone, and the pin still
  keeps renewal off whatever ubuntu resolves through.

Nothing checks any of these automatically. `nomad job validate` and
`terraform plan` accept them all.

## Traps

- **Two template layers.** Terraform's `templatefile` renders the jobspec,
  then Nomad interpolates the result again. A shell brace expansion cannot
  survive both. T1 hit this live and fixed it by restructuring: `basename`
  instead of a brace expansion, env vars instead of an argument string. A
  comment describing the escape also broke the template, because it contained
  the sequence.
- **Pin images by digest alone.** A reference carrying a tag and a digest
  passes every gate and fails when the podman driver parses it, with the
  error `unsupported transport`. T4 fixed both images here.
- **Check lego's CLI in the pinned image.** T1's plan named a `renew`
  command that lego v5 does not have. Run `--help` in the image, not from
  memory.
- **A host volume stays on the node it was created on.** Moving the job from
  firebat to ubuntu in `5a1b16b` left the volume behind. The provider reports
  a constraint change and a name change as in-place updates, and neither
  moves it. Only a new resource address (`871ed68`, `acme_state` to
  `acme_lego_state`) produces a destroy and a create.

The job moved from firebat to ubuntu in `5a1b16b` because firebat had no
CPU left to reserve. The reference page gives the numbers.

## Gaps

Nothing alerts on a failed run or on days to expiry. T5 would add the expiry
alert. It was deferred out of T3 because nothing in the cluster measures
expiry, and it is blocked because its plan has never been reviewed.
`docs/how-to/check-the-edge-certificate.md` and
`docs/how-to/recover-a-failed-certificate-renewal.md` are the manual checks,
and `docs/how-to/test-acme-job-changes-on-staging.md` is the safe way to
change the job.
