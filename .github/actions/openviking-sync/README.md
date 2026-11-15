# openviking-sync

Mirrors git-tracked folders into the calling repository's own
`<owner>/<repo>/` prefix of the `ov-sync` bucket. `ov-sync-consumer` reads the
bucket's events and writes the files to OpenViking. Run it after `lab-auth`:

```yaml
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
          vault-role: <your caller key>
      - uses: JasperHG90/localstack/.github/actions/openviking-sync@<commit-sha>
```

The caller needs an entry in `var.vault_ci_callers` with `ov_sync = true`,
and its prefix mapped to an OpenViking folder in the consumer's `prefixes`.
Setup, inputs and the credential chain are in
`docs/how-to/sync-repository-folders-to-the-ov-sync-bucket.md` and
`docs/reference/github-actions.md`.
