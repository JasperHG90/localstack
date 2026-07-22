eval: C1-cicd-tailscale-github-actions-deploy

**Definition of Done:** A tag push runs a GitHub Actions workflow
(`.github/workflows/deploy-talat-webhook-exporter.yaml`) that brings up an
ephemeral `tag:ci` Tailscale node, renders and submits the
`talat-webhook-exporter` job to firebat:4646 over the tailnet using the repo's
render-and-submit convention, and tears the node down; the render/submit path
validates and plans cleanly in-harness against the live cluster, the deploy's
Nomad ACL token is scoped to `submit-job`/`read-job` (denied `alloc-exec`), and
tailnet reachability to 4646 is granted only to `tag:ci`, not the whole tailnet.

| Behavior | Input | Expected | Scorer | Threshold |
| --- | --- | --- | --- | --- |
| Operator can trust the deploy workflow YAML is well-formed before it ever runs (in-harness, static) | `pre-commit run check-yaml --files .github/workflows/deploy-talat-webhook-exporter.yaml` (or `just pre_commit`) | check-yaml passes; the workflow file parses as YAML (syntax only — no Actions-schema linting is gated, there is no actionlint in this repo) | deterministic check (`pre-commit run check-yaml --files .github/workflows/deploy-talat-webhook-exporter.yaml`) | 100% |
| Operator confirms the render-and-submit path produces a valid Nomad job (in-harness, against live cluster) | Render the `talat-webhook-exporter` template with its pinned version, then `nomad job validate <rendered>.hcl` against `$NOMAD_ADDR` | Prints `Job validation successful`, exit 0, no errors | deterministic check (`nomad job validate <rendered>.hcl`) | 100% |
| Operator confirms the submit command line the workflow runs plans cleanly against the live server (in-harness) | `nomad job plan <rendered>.hcl` (firebat at `192.168.2.30:4646`) | A plan diff prints and the command exits 0 or 1 (1 = plan with changes) — not a connection or auth error, proving the render-and-submit invocation is well-formed and reachable | deterministic check (`nomad job plan <rendered>.hcl`) | 100% |
| Guardrail: the scoped Nomad ACL token grants only what a deploy needs, not developer-level access (in-harness) | With the scoped token: `NOMAD_TOKEN=<scoped> nomad job validate <rendered>.hcl`; then `NOMAD_TOKEN=<scoped> nomad alloc exec <id> sh` | Allowed action succeeds; `alloc exec` (and any `alloc-exec`/host-volume-write action) returns `Permission denied` / HTTP 403, proving the policy is narrower than `developer` | deterministic check (`NOMAD_TOKEN=<scoped> nomad alloc exec <id> sh` returns 403) | 100% |
| Operator sees a tag push deploy the service end-to-end over an ephemeral tailnet node that tears itself down (real CI run, on GitHub — the true close-out) | Push a throwaway tag (per Q2) to fire the workflow | The job brings up an ephemeral node tagged `tag:ci`, the render-and-submit step reaches firebat:4646 and submits the job, `nomad job status talat-webhook-exporter` shows the new version/submit time, and the ephemeral node deregisters from the tailnet device list on job end | human + rubric (real CI run) | 100% |
| Guardrail: tailnet access to the Nomad API is scoped to `tag:ci` only, not the whole tailnet (real CI run, from the CI node before teardown) | From within the CI job: connect to firebat:4646, then attempt a second non-Nomad tailnet host/port | 4646 is reachable from the CI node; the non-granted tailnet target is refused — proving the `tag:ci` grant is scoped to the Nomad API alone, not a blanket tailnet open | deterministic check (connection to a non-granted tailnet host/port is refused from the CI node) | 100% |
