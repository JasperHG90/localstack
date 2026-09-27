---
name: terraform-file-layout
description: Name .tf files after the subsystem they configure, not the feature. Read before adding, splitting, or renaming a file in a Terraform root.
---

<constraint name="one-file-per-subsystem">
Within a Terraform root, a `.tf` file is named after the subsystem it
configures, never after a feature, a ticket, or a single resource. A feature
that touches three subsystems is written across three files. Adding a feature
does not add a file.
</constraint>

The roots under `deployments/` already hold these names. Reuse one before
inventing another:

| File | Holds |
|---|---|
| `backend.tf` | the state backend |
| `providers.tf` | `required_providers` and the default provider blocks |
| `variables.tf` | input variables |
| `services.tf` | Nomad jobs, host volumes, and the firewall rules that open their ports |
| `secrets.tf` | Vault KV writes and the random passwords they carry |
| `storage.tf` | object storage: buckets, their IAM, their access keys |
| `database.tf` | database engines and the roles that mint credentials against them |
| `identity.tf` | human auth backends, entities, groups, and the policies they carry |
| `oidc.tf` | the OIDC provider, its keys and scopes, and every client |
| `machine_roles.tf` | credentials Vault brokers to machines |

One exception to the `providers.tf` row: an aliased provider fed by a brokered,
short-TTL credential stays beside the data source that reads it, so the reason
it must be re-read every run stays next to the thing that does the reading. See
`provider "nomad"` with `alias = "manage"` in
`deployments/infrastructure/machine_roles.tf`.

Add a file only when a new subsystem arrives. Terraform loads every `.tf` in a
root into one flat namespace, so the split buys readability and nothing else.
A name that does not survive the next feature buys less than that.

<example name="a-feature-spans-files">
Loki needs a bucket, a credential, and a job. Its `minio_iam_policy` goes in
`storage.tf`, its `vault_kv_secret_v2` in `secrets.tf`, its `nomad_job` in
`services.tf`. There is no `loki.tf`, and adding one would leave the next
reader guessing which of four files holds the part they came for.
</example>

<example name="the-failure-this-prevents">
`deployments/infrastructure` once held 17 `.tf` files, 10 of them named after a
feature or a single resource: `acme.tf`, `backup.tf`, `memex_oidc.tf`,
`nomad_oidc.tf`, `auth_userpass.tf`, `consul_deploy_role.tf`,
`developer_group.tf`, `nomad_deploy_role.tf`, `nomad_dash_read_role.tf`,
`redis_secrets_engine.tf`. Eight were under 100 lines.

The cost showed up in the comments. Three `vault_jwt_auth_backend_role` blocks
shared one shape and sat in three files, so two of them opened by pointing at
the others: "Same shape as `vault_jwt_auth_backend_role.acme` (acme.tf) and
`.redis_cache` (redis_secrets_engine.tf)". Collected into one file, that
sentence became "both in this file" and the shape is visible instead of
asserted.
</example>

## Moving a block is free. Editing one is not.

A resource's Terraform address is `<type>.<name>`. The filename is not part of
it, so moving a block between files in the same root changes no state and
produces no plan diff. Two kinds of text inside a file are not free:

- **Heredoc bodies.** A `vault_policy` document or a `rules_hcl` block is a
  string Terraform stores and the target system serves. Its `#` comments are
  part of that string, so fixing a typo in one rewrites the policy on the next
  apply.
- **Jobspec files.** `templatefile("services/x.hcl", ...)` folds that whole
  file, comments included, into `nomad_job.jobspec`. Editing a comment there
  re-registers the job.

A reorganization therefore moves blocks byte for byte and edits only the `###`
comments outside them. A stale filename reference trapped inside a heredoc or a
jobspec stays stale. That is cheaper than the write it would cost to fix.

## Proving the move was clean

Copy the root before you start. Then run `terraform fmt -check` and
`scripts/tf_validate.sh` before you compare: the comparison below reaches only
as far as a brace-counting parser, not Terraform's own, and on HCL those two
accept, every block boundary it finds is real. On HCL they reject, it can
mistake one.

```
scripts/tf_block_diff.py <before-dir> <after-dir>
```

It parses both roots into top-level blocks keyed by header, holds heredoc
bodies verbatim, and prints a diff for every block whose body changed. Once
those two gates pass, silence means every block moved intact.

Read each reported diff and judge it. The tool reports any body change,
including a `#` comment you edited on purpose inside a resource body, which is
safe. It cannot tell that apart from an attribute you edited by accident, which
is not. `--self-test` covers the cases that would let a change escape, among
them the two the parser has to get right: a brace inside a string, and a
heredoc it must skip whole. Treat a clean run as evidence, not as a proof that
outranks reading the diff.

<constraint name="do-not-diff-sorted-lines">
Do not prove this by stripping comments from every `.tf`, sorting the lines,
and diffing. Sorting discards which block each line belonged to, so swapping
two lines between blocks passes: exchange `client_type` between a public and a
confidential OIDC client and the sorted output is byte-identical while the two
clients have traded security posture. That check also strips heredoc `#`
comment lines, which is exactly the state-bearing text above.
</constraint>

Finish with `terraform plan`. It should report `0 to change`. Account for every
resource it does list before calling the move clean.
