eval: C1-cicd-tailscale-github-actions-deploy

**Definition of Done:** A `workflow_dispatch` run of
`.github/workflows/tailnet-reachability.yaml` brings up an ephemeral Tailscale
node tagged `tag:ci`, reaches HAProxy stats on firebat's tailnet address at
`:8404` over the tailnet, asserts HTTP 200, and the node deregisters. The
Tailscale OAuth credential lives in a protected GitHub Environment rather than
a repository secret, the `tag:ci` grant reaches firebat only, and **no
infrastructure changes** — no Terraform, no Nomad job, no Ansible, no ufw rule.

*Rewritten 2026-07-25 to the operator's 2026-07-23 rescope. The previous
marker specified the cancelled talat-webhook-exporter deploy and was
unsatisfiable by the rescoped ticket.*

| Behavior | Input | Expected | Scorer | Threshold |
| --- | --- | --- | --- | --- |
| The workflow file is well-formed before it ever runs (in-harness, static) | `just pre_commit` (run `just worktree_setup <path>` first in a worktree) | All hooks Passed, including `check-yaml` on the new workflow. Syntax only — there is no actionlint in this repo, so a parse is not a validity proof | deterministic check (`just pre_commit` exit 0) | 100% |
| No credential is committed (in-harness, static) | `pre-commit run detect-private-key --all-files`; inspect the workflow for token-shaped literals | Hook passes; the workflow references secrets only via `${{ secrets.* }}` from the Environment, never a literal | deterministic check (`detect-private-key` passes) | 100% |
| The ticket changes no infrastructure — the rescope's central constraint (in-harness, static) | `git diff --name-only main...HEAD` | No path under `deployments/`, no path under `bootstrap/`, no `.tf` and no `.hcl`. Only the workflow and `docs/ci-tailnet.md` | deterministic check (`git diff --name-only` matches no infra path) | 100% |
| The runner joins the tailnet as `tag:ci` (real CI run) | Trigger the workflow via `workflow_dispatch` | The Tailscale step succeeds and a node carrying `tag:ci` appears in the Tailscale console for the duration of the run | human + rubric (operator observes the console) | 100% |
| **The runner reaches the cluster over the tailnet — the deliverable** (real CI run) | From the CI job: `curl -sS -o /dev/null -w '%{http_code}' http://<firebat-tailnet-ip>:8404/` | `200`, from HAProxy's stats frontend. A connection timeout or refusal means the tailnet path is not established; a non-200 means the target is wrong | deterministic check (curl returns 200 in the workflow log) | 100% |
| The `tag:ci` grant is scoped to firebat, not the whole tailnet (real CI run) | From within the CI job, after the successful check: attempt a connection to a tailnet host/port the ACL does not grant | The non-granted target is refused or times out, proving the ACL narrows access rather than opening the tailnet | deterministic check (non-granted target refused from the CI node) | 100% |
| The ephemeral node does not linger (real CI run) | Inspect the Tailscale device list after the run completes | The `tag:ci` node has deregistered, or the runbook documents the manual cleanup step and the operator has followed it | human + rubric (operator observes the console) | 100% |
| The credential is not readable by the repo's agent workflows (in-harness, static) | Inspect the workflow's `environment:` key and the GitHub Environment's protection rule | The OAuth secret is an Environment secret behind a protection rule, not a repository secret, so `claude-ollama.yaml` cannot read it | human + rubric (operator confirms in repo settings) | 100% |
