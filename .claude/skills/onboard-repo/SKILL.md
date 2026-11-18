---
name: onboard-repo
description: Connect another of the operator's GitHub repositories to the lab, so a workflow there joins the tailnet, gets a Vault token, and optionally syncs its docs into OpenViking. Creates the repo's lab Environment, adds its Vault caller and ov-sync prefix in this repo's Terraform, applies both roots from checked plans, and prints the caller workflow. Use when the operator says "onboard <repo>", "connect <repo> to the lab", "let <repo> sync its docs into OpenViking", or "give <repo> a Vault role".
---

# onboard-repo

Connects one repository, `JasperHG90/<repo>`, to the lab. Ask the operator
for anything below that they have not said:

- **repo**: the repository name, without the owner.
- **workflow**: the file under the repo's `.github/workflows/` that will call
  the action. Default `openviking-sync.yaml`. The Vault role accepts only
  this exact file on `refs/heads/main`.
- **sync docs**: yes when the workflow pushes docs into OpenViking. Default
  yes for `openviking-sync.yaml`.
- **folders**: with sync docs, which folders go to OpenViking. Default
  `docs` and `.okf`, the openviking-sync action's own default.

The role key is `<repo>-<workflow without .yaml>`, for example
`loop-engineering-harness-openviking-sync`. Background and the manual steps
are in `docs/how-to/authenticate-a-github-workflow-to-the-lab.md`.

The Tailscale side needs nothing. The lab-auth action picks the identity
that matches the repo's OIDC subject format (ADR 0031).

## 1. Check the repo and create its lab Environment

```sh
gh api repos/JasperHG90/<repo> --jq .full_name
gh api repos/JasperHG90/<repo>/environments --jq '[.environments[].name]'
```

When `lab` is missing:

```sh
gh api -X PUT repos/JasperHG90/<repo>/environments/lab
```

Run the list again and see `lab` in it.

## 2. Route the change

Run the `route-ask` skill with the operator's words. The Terraform and test
edits below are a change to this repo, so they go through the loop like any
other.

## 3. Edit the Terraform and the tests

1. In `deployments/infrastructure/variables.tf`, add to the `default` of
   `vault_ci_callers`, after the last entry:

   ```hcl
   <repo>-<workflow stem> = {
     repository  = "JasperHG90/<repo>"
     ref         = "refs/heads/main"
     environment = "lab"
     workflow    = "<workflow>"
     ov_sync     = true # only when it syncs docs; leave the line out otherwise
   }
   ```

2. When it syncs docs, add to `prefixes` in
   `deployments/applications/services.tf`:

   ```hcl
   "JasperHG90/<repo>/" = "viking://user/jasper/resources/projects/<repo>/"
   ```

3. `cli/tests/test_lab_auth_action.py` holds both lists exactly. Add the new
   caller to `test_default_callers` in key order, because Terraform sorts the
   map by key, and the new prefix to `test_ov_sync_prefix_map` when it syncs
   docs.

4. Run `terraform fmt` on both roots and
   `uv run --directory cli pytest tests/test_lab_auth_action.py -q`.

## 4. Apply both roots from saved plans

Never run `just apply` or a bare `terraform apply`. Both re-plan and wait for
`yes`, so what gets applied is not what you checked. Save each plan to the
scratchpad, check it, and apply that file.

Run each block below as one shell call. A new call can start in another
directory without the `localstack env` variables. `<checkout>` is the
absolute path of the worktree you edited, and `<scratchpad>` is your session
scratchpad.

Infrastructure first. In a fresh worktree, run
`terraform init -backend-config=./vars/backend-config.hcl` in the same call
before the plan.

```sh
cd <checkout>/deployments/infrastructure && eval "$(uv run localstack env)" &&
  terraform plan -var-file=./vars/prod.tfvars -out <scratchpad>/infra.tfplan
```

The plan may hold only:

- `vault_jwt_auth_backend_role.github_ci["<key>"]`, created
- with sync docs: `vault_identity_oidc_role.ci_ov_sync["<key>"]` and
  `vault_policy.ci_ov_sync["<key>"]`, created, and `nomad_job.seaweedfs`
  updated in place with one new policy and role named `ci-<key>`, scoped to
  `arn:aws:s3:::ov-sync/JasperHG90/<repo>/*`
- `null_resource.firewall[...]` replacements. Their `always_run` trigger
  replaces them on every apply.

Anything else: stop, show the operator the plan, and wait. Otherwise:

```sh
cd <checkout>/deployments/infrastructure && eval "$(uv run localstack env)" &&
  terraform apply <scratchpad>/infra.tfplan &&
  vault read auth/jwt-github/role/<key>
```

The role shows `bound_claims` with `repository`, `ref`, `environment` and
`workflow_ref` for this repo and workflow.

The `nomad_job.seaweedfs` update restarts SeaweedFS. Before the applications
plan, wait until `192.168.2.29:8333` accepts connections, or that plan fails
reading IAM users.

Then applications, only when it syncs docs:

```sh
cd <checkout>/deployments/applications && eval "$(uv run localstack env)" &&
  terraform plan -var-file=./vars/prod.tfvars -out <scratchpad>/apps.tfplan
```

The plan may hold only `nomad_job.ov_sync_consumer` updated in place, with
the new prefix added to its map. Anything else: stop and ask. Otherwise apply
`<scratchpad>/apps.tfplan` the same way, in one call from that root.

A saved plan holds secrets in plain text. Delete both files once applied. If
an apply fails with a 403 because a short-lived token expired while you
waited, plan and check again.

## 5. Commit, then push with the operator's go-ahead

Finish the ticket the way the loop says: stamp, review, commit, done, land.
Then ask the operator before you push `main`. The caller workflow pins a
commit SHA of this repo, so that commit must exist on GitHub, and `main` there
should match what you applied.

## 6. Hand over the caller workflow

After the push, take the SHA with `git rev-parse origin/main` and give the
operator this file for the repo's `.github/workflows/<workflow>`:

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
      - uses: JasperHG90/localstack/.github/actions/lab-auth@<sha>
        with:
          vault-role: <key>
      - uses: JasperHG90/localstack/.github/actions/openviking-sync@<sha>
```

With other folders than `docs` and `.okf`, give the openviking-sync step
`with: folders: <folders, one per line>` and list the same folders in
`paths`. Without sync docs, drop that step and the `paths` filter.
Never add a `pull_request` or `pull_request_target` trigger: it would run a
fork's code with the job's token.

The first run shows whether it worked:

```sh
gh workflow run <workflow> --repo JasperHG90/<repo> --ref main
gh run watch --repo JasperHG90/<repo>
```

A `Vault refused role <key>` error means the workflow file name or branch
differs from the caller entry.
