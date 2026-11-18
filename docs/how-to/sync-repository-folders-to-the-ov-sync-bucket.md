---
description: "Mirror a repository's docs/ and .okf/ into its own prefix of the ov-sync bucket on every push to main, so ov-sync-consumer writes them to OpenViking."
stale_after: 2027-02-15
sources:
  - resource: .github/actions/openviking-sync/action.yml
  - resource: .github/actions/openviking-sync/sync.py
  - resource: .github/workflows/openviking-sync.yaml
  - resource: deployments/infrastructure/variables.tf
  - resource: deployments/applications/services.tf
---

# How to sync repository folders to the ov-sync bucket

## Introduction

Mirror a repository's `docs/` and `.okf/` into
`s3://ov-sync/<owner>/<repo>/` on every push to `main`. `ov-sync-consumer`
then writes each change to OpenViking, and a file you delete is deleted there
too. No S3 key is stored anywhere. Do this once per repository.

## Prerequisites

- A workflow set up for the lab-auth action, with the `lab` Environment, per
  [How to authenticate a GitHub workflow to the lab](authenticate-a-github-workflow-to-the-lab.md).
- A `localstack login` session ([CLI login](../reference/cli-login.md)),
  because `just apply` runs `localstack env`.

## Directions

### Step 1: Add an ov_sync caller

Add an entry for the sync workflow to `vault_ci_callers` in
`deployments/infrastructure/variables.tf`, with `ov_sync = true`:

```hcl
my-repo-openviking-sync = {
  repository  = "JasperHG90/my-repo"
  ref         = "refs/heads/main"
  environment = "lab"
  workflow    = "openviking-sync.yaml"
  ov_sync     = true
}
```

Apply the root. SeaweedFS restarts, because it reads its roles only at start.

```sh
cd deployments/infrastructure && just apply
vault read identity/oidc/role/ci-my-repo-openviking-sync
```

The output shows `client_id` `seaweedfs` and a template with
`"ci_repository":"JasperHG90/my-repo"`.

### Step 2: Map the prefix to an OpenViking folder

In `deployments/applications/services.tf`, add the prefix to `prefixes` in
`nomad_job.ov_sync_consumer`:

```hcl
prefixes = jsonencode({
  "JasperHG90/localstack/" = "viking://user/jasper/resources/projects/localstack/"
  "JasperHG90/my-repo/"    = "viking://user/jasper/resources/projects/my-repo/"
})
```

Apply that root with `cd deployments/applications && just apply`. A prefix
missing here is skipped: the files reach the bucket and go no further.

### Step 3: Add the workflow

Create `.github/workflows/openviking-sync.yaml` in the repository:

```yaml
name: openviking-sync

on:
  push:
    branches: [main]
    paths: ["docs/**", ".okf/**"]
  workflow_dispatch:

permissions:
  id-token: write
  contents: read

concurrency:
  group: openviking-sync
  cancel-in-progress: false

jobs:
  sync:
    runs-on: ubuntu-latest
    environment: lab
    timeout-minutes: 5
    steps:
      - uses: actions/checkout@v4
      - uses: JasperHG90/localstack/.github/actions/lab-auth@<commit-sha>
        with:
          vault-role: my-repo-openviking-sync
      - uses: JasperHG90/localstack/.github/actions/openviking-sync@<commit-sha>
```

Keep `cancel-in-progress: false`. Two runs racing on the manifest would lose
a write. Never add a `pull_request` trigger.

### Step 4: Run it

Push the workflow to `main`, or start it by hand:

```sh
gh workflow run openviking-sync.yaml --repo JasperHG90/my-repo --ref main
gh run watch --repo JasperHG90/my-repo
```

The sync step prints one `uploaded JasperHG90/my-repo/<path>` line per file
and ends with `N to upload, 0 to delete, 0 failed`. A second run with no
change prints `0 to upload, 0 to delete, 0 failed`. A large first sync that
the job's `timeout-minutes` stops keeps what it uploaded, so run it again and
it continues. If the step fails with
`Vault refused identity token`, the caller has no `ov_sync = true` or Step 1
was not applied.

## Additional resources

- [GitHub Actions reference](../reference/github-actions.md#openviking-sync):
  inputs, the manifest and the credential chain.
- [Workload identity](../explanation/workload-identity.md): why SeaweedFS
  trusts Vault's identity tokens.
- [ADR 0028](../../.okf/decisions/0028-ci-syncs-repo-folders-to-ov-sync-with-a-manifest-and-a-vault-identity-token.md):
  why the bucket, manifest and credential are shaped this way.
