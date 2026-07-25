---
epic = "cicd"
depends_on = []
priority = 0
---

# C1 — Prove GitHub Actions can reach the cluster over the tailnet

## Title
A GitHub Actions workflow joins the tailnet as `tag:ci` and reaches one
cluster service over it. That is the whole deliverable: the CI-to-cluster
path, proven, with nothing deployed.

**Rewritten 2026-07-25.** The operator rescoped this ticket on 2026-07-23
(talat-webhook-exporter moved to its own repo) but the rescope was appended
rather than applied, leaving ~470 lines specifying a cancelled talat deploy
and an eval marker whose Definition of Done was unsatisfiable by the ticket
actually wanted. Body and eval are rewritten to the rescope; the cancelled
content remains in git history.

## Size / Effort
**Small.** A ~30-line workflow, a Tailscale console ACL edit, and a runbook
page. No Terraform, no Nomad job, no credentials beyond a Tailscale OAuth
client. The effort is console-side setup (`tagOwners`, OAuth client) and
getting the dial target right, not code.

## Triggered by
Operator wants CI able to reach the private cluster. Proving the transport in
isolation, before anything depends on it, keeps the first real CI ticket from
debugging connectivity and deployment at the same time.

## Context (today's state)
- No CI exists for infrastructure. The repo's only workflows are
  `.github/workflows/claude-ollama.yaml` and `hermes-interactive.yaml`, both
  agent-assistant workflows, neither touching the cluster.
- **The tailnet path to firebat is already open.** `services.tf:182-193`
  admits `100.64.0.0/10` to firebat on ports 80, 443, and 8404;
  `services.tf:204-221` does the same for Prometheus 9090 and Grafana 3000.
  HAProxy binds all three of its ports and already proxies `nomad.localstack`
  to firebat:4646; `docs/haproxy_reverse_proxy.md:30` documents the tailnet
  path. **The original plan's central premise — that port 22 is the only
  precedent for admitting the CGNAT range, so a new ufw rule is needed — was
  false.** A curl against HAProxy over the tailnet needs no infrastructure
  change at all.
- The manager (firebat) is a Tailscale subnet router advertising
  `192.168.2.0/24` (`bootstrap/playbooks/configure_tailscale.yml:40-47`).
  Workers have tailscaled stopped and disabled (`:52-58`).
- The cluster's own Tailscale role sets `--accept-routes`
  (`bootstrap/roles/tailscale/tasks/main.yml:64`). **`tailscale/github-action`
  does not**, which decides the dial target below.
- Tailnet ACLs are console-managed and live outside this repo.

## Non-goals / out of scope
- Deploying anything: no `terraform plan`, no `terraform apply`, no Nomad job
  submission, no `nomad job validate`. (Operator rescope, 2026-07-23.)
- The `talat-webhook-exporter` job, its ACL policy, and its scoped Nomad
  token. It moved to its own repo.
- Any Nomad ACL policy or token work. A reachability check needs none, so
  there is no dependency on F7/F8 and no static-token rework.
- Editing `bootstrap/playbooks/configure_network.yml`. Per Context, no new
  firewall rule is required. If one proves necessary it belongs in the
  Terraform `firewall_rules` map (`services.tf:163-272`), not the Ansible
  base playbook — that is where service-level tailnet exposure lives here.
- Self-hosted runners. GitHub-hosted `ubuntu-latest` throughout, so the
  cluster's arm64 nodes are irrelevant.
- Making this workflow a gate on anything.

## Requirements & restrictions
1. Workflow joins the tailnet via `tailscale/github-action` with an OAuth
   client carrying `tag:ci`, then reaches one named service and asserts a
   specific HTTP status.
2. **Name the dial target explicitly.** Two paths exist and they differ at
   ufw: firebat's tailnet IP (`100.x`, matching the existing
   `100.64.0.0/10` rules) versus its LAN IP `192.168.2.30` through the
   advertised subnet route, which requires `--accept-routes` on the runner —
   off by default in the action. *Prefer the tailnet IP.*
3. **Target a hostname-independent endpoint.** Anything reached with a
   `Host: <svc>.localstack` header silently starts hitting the default
   backend when T3 renames all twelve ACLs, and port 80 becomes a 301 to
   https after T3. Do not couple this smoke test to hostnames in flight.
4. **The Tailscale OAuth secret goes in a GitHub Environment with a
   protection rule, not a repository secret.** Repository-level Actions
   secrets are readable by every workflow in the repo, and this repo runs
   `claude-ollama.yaml` — an autonomous agent with tool use and a 25-turn
   budget, triggered on `pull_request: [opened]`, `issues: [opened]`,
   `issue_comment`, and `pull_request_review_comment`, with `PR_BODY` and
   `ISSUE_BODY` interpolated into its prompt (`claude-ollama.yaml:72-78,
   96-97, 110-111`). A repo-scoped credential granting entry to the home LAN
   would widen a prompt injection there from "posts a bad comment" to "joins
   the tailnet". The actor gate at `:48-55` limits triggering, not secret
   scope.
5. **`workflow_dispatch` only.** No `on: pull_request` — fork PRs receive no
   secrets, so the Tailscale step fails with an opaque auth error rather than
   skipping cleanly, and a tailnet join per PR is not wanted.
   `pull_request_target` is forbidden.
6. The tailnet ACL must declare `tagOwners` for `tag:ci` before the OAuth
   client can advertise it; without it `tailscale up --advertise-tags` fails
   outright. Console-side, and the likeliest first-run wall.
7. ACL grants `tag:ci` access to firebat only, on the target port only.
8. No credential in the workflow file or any committed file
   (`detect-private-key`, `.pre-commit-config.yaml:12`).
9. `.claude/rules/adversarial-reviews.md`: adversarial review before done.

## Code surface
- `.github/workflows/tailnet-reachability.yaml` **(new)** — `workflow_dispatch`
  only, `runs-on: ubuntu-latest`, explicit `permissions` and
  `timeout-minutes` (shape per `claude-ollama.yaml:34-38,56-57`),
  `tailscale/github-action` with `tag:ci`, then the reachability assertion.
- `docs/ci-tailnet.md` **(new)** — the runbook: creating the OAuth client,
  the `tagOwners` prerequisite, a read-only reference copy of the relevant
  ACL stanza (console stays authoritative), the GitHub Environment setup, and
  how to re-run the proof.

## Tests & validation gates
**C1 introduces CI; it cannot inherit one.** There is no `actionlint` in this
repo, and `check-yaml --unsafe` (`.pre-commit-config.yaml:16-21`) proves
syntax only, not workflow validity. Do not assume coverage that is absent.

### Repo gate
- **Command:** `just pre_commit` (`justfile:18-19`) -> all Passed.
- **Prerequisite in a worktree:** `just worktree_setup <path>`
  (`justfile:30-32`, added in `3c12c7a`). `terraform-validate` has
  `pass_filenames: false`, so it runs on every gate invocation regardless of
  what C1 touched, and it evaluates `file("${path.root}/../../.ssh/id_rsa")`
  (`services.tf:287`), which is gitignored. Without this step the gate
  red-fails for a reason unrelated to the ticket.

### Evals — encoded in `.loop/evals/<slug>.md`
Real acceptance requires a GitHub Actions run and cannot execute inside the
harness. **Do not report complete on the static checks alone.**
1. Workflow parses: `check-yaml` passes on the new file.
2. No secret literal committed: `detect-private-key` green, no token-shaped
   string in the workflow.
3. A `workflow_dispatch` run joins the tailnet as `tag:ci` — operator
   observes the node with that tag in the Tailscale console.
4. **The run reaches the target and asserts the expected status.** With
   `:8404` as target, HTTP 200 from HAProxy stats. This is the ticket.
5. The ephemeral node deregisters after the run, or manual cleanup is
   documented.
6. No infrastructure changed: `git diff` touches no `.tf`, no `.hcl` under
   `deployments/`, and nothing under `bootstrap/`.

## Risk assessment
- **Blast radius: the credential, not the cluster.** Nothing is deployed and
  no infrastructure changes, so the only lasting artifact is a credential
  admitting a GitHub runner to the tailnet. Requirement 4 is the control that
  matters.
- **Prompt-injection reach** via the shared secret store — see requirement 4.
  This is the one way C1 measurably changes the lab's security posture.
- **Ephemeral node sprawl** if runs do not deregister. Cosmetic; check it.
- **T3 coupling** if the target is hostname-dependent. Requirement 3 avoids
  it.
- **Reversibility: total.** Delete the workflow, revoke the OAuth client,
  remove the ACL stanza. No state, no infrastructure.

## Subtickets (ordered)
1. Console setup: `tagOwners` for `tag:ci`, OAuth client, ACL granting
   `tag:ci` -> firebat on the target port. Record in the runbook.
2. GitHub Environment holding the OAuth secret, with a protection rule.
3. The workflow. Gate green.
4. Operator runs `workflow_dispatch`; evals 3-5.
5. `docs/ci-tailnet.md`.
6. Adversarial review.

## Open questions
- **Q1 — Which service is the target?** The rescope says "one cluster
  service" without naming one. *Recommendation:* HAProxy stats at
  `<firebat-tailnet-ip>:8404` — already admitted by `services.tf:189-190`,
  hostname-independent so T3 cannot break it, and it returns a body proving
  the proxy answered rather than just that a port is open.
- **Q2 — Ephemeral or persistent tailnet node?** *Recommendation:* ephemeral
  via the OAuth client, so runners self-deregister and the tailnet does not
  accumulate dead nodes.
- **Q3 — Does this earn its keep at priority 0?** It unblocks nothing in the
  ledger. *Recommendation:* keep it at priority 0 now that it is small, since
  it de-risks the transport for a later CI ticket. If no such ticket
  materializes, drop it rather than growing it.
