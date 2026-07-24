---
epic = "cicd"
depends_on = []
priority = 0
---

# C1: Tailscale-based GitHub Actions deploy path for talat-webhook-exporter

## 1. Title

Build a secure CI/CD deploy path so GitHub Actions can deploy the
already-running `talat-webhook-exporter` service to the Nomad cluster
over the private tailnet: an ephemeral Tailscale CI node (OAuth client +
ACL tag) joins the tailnet for the job, submits the job to the Nomad API
using the repo's existing render-and-submit pattern, and tears itself
down, with network access scoped by tailnet ACL and a least-privilege
Nomad ACL token.

## 2. Size / Effort

**M (medium).** The service already exists and is deployed; this ticket
ships only the deploy *path*, not the service. Effort drivers:

1. The change spans three trust boundaries that must line up — the
   GitHub Actions secret store, the Tailscale control plane (OAuth
   client + tailnet ACL, which live *outside* this repo), and the Nomad
   ACL system (bootstrapped imperatively in Ansible, not Terraform).
2. There is a real network-reachability subtlety: the Nomad API port is
   firewalled to the LAN CIDR only, while a CI node reaches the cluster
   from the Tailscale CGNAT range. Getting least-privilege right without
   silently opening 4646 to the whole tailnet is the design load.
3. The workflow reuses an existing render-and-submit convention rather
   than inventing one, so most of the work is wiring and scoping, not
   new mechanism.

## 3. Triggered by

CI/CD thread C1 (independent of the auth/OIDC epic). `talat-webhook-
exporter` is built and deployed today; deploys are manual. The request
is to make a tag push deploy it automatically over the tailnet, with
least-privilege access on both the tailnet and Nomad, and the ephemeral
node removed when the job ends.

## 4. Context

Today's state, cited:

- **Render-and-submit pattern (the thing to reuse).** Nomad jobs in this
  repo are deployed as Terraform `nomad_job` resources whose `jobspec` is
  a rendered `templatefile(...)`. Application jobs:
  `deployments/applications/services.tf:97-107` (phoenix),
  `:110-136` (hermes), `:139-144` (loki), `:147-163` (memex),
  `:166-184` (bifrost), `:187-200` (mlflow). Infra jobs follow the same
  shape: `deployments/infrastructure/services.tf:293-365`
  (postgres/minio/haproxy/prometheus/grafana/promtail/nats). This
  render-and-submit-via-Terraform IS the pattern the request means; there
  is **no** Nomad Pack or `nomad-pack` usage anywhere in the repo
  (confirmed: zero matches for `nomad pack`/`nomad-pack` across
  `deployments/`, `bootstrap/`, `docs/`).
- **How the Nomad provider authenticates.** The provider block is empty:
  `deployments/applications/providers.tf:30` (`provider "nomad" {}`),
  so it reads `NOMAD_ADDR` / `NOMAD_TOKEN` from the environment. The
  local dev convention seeds these from
  `.devcontainer/.env.example` (`NOMAD_ADDR=http://localstack.local:4646`,
  `NOMAD_TOKEN=...`). The cluster's Nomad server is firebat at
  `192.168.2.30:4646` (see `deployments/applications/services/hermes.hcl:205`).
- **Version-pinning convention.** Each job pins an image/version as a
  literal passed into the template:
  `deployments/applications/services.tf:116` (`hermes_version`),
  `:159` (`memex_version`), `:172` (`bifrost_version`),
  `:196` (`mlflow_version`). The `rebuild_hermes` recipe reads that
  literal back out of `services.tf` so image build and job stay in
  lockstep: `deployments/applications/justfile:23-31`. Var-files hold
  environment inputs: `deployments/applications/vars/prod.tfvars` (applied
  via `deployments/applications/justfile:13-15`).
- **Tailscale on the cluster.** Only the `manager` host (firebat) runs
  Tailscale, as a subnet router advertising `192.168.2.0/24`:
  `bootstrap/playbooks/configure_tailscale.yml:52-58`. Workers have
  `tailscaled` stopped/disabled:
  `bootstrap/playbooks/configure_tailscale.yml:60-71`. The role installs
  Tailscale and authenticates with a **plain auth key** read from Vault
  (`bootstrap/tailscale`), not an OAuth client, and applies **no ACL
  tags**: `bootstrap/roles/tailscale/tasks/main.yml:57-68`. The auth key
  is sourced at `bootstrap/playbooks/configure_tailscale.yml:26-30`.
  There is no tailnet ACL policy file in this repo (tailnet ACLs live in
  the Tailscale admin console).
- **Nomad ACL system.** ACLs are enabled and bootstrapped in Ansible, not
  Terraform. A bootstrap token is read at
  `bootstrap/roles/nomad_server/tasks/main.yml:160-164` and a single
  broad "developer" policy is applied imperatively at
  `bootstrap/roles/nomad_server/tasks/main.yml:174-186`, from
  `bootstrap/roles/nomad_server/files/nomad_developer_policy.hcl`. That
  policy grants `namespace "default" { policy = "write" }` with
  `submit-job` and much more — far broader than a deploy needs. There is
  **no** `nomad_acl_policy` / `nomad_acl_token` Terraform resource in the
  repo (confirmed: zero matches under `deployments/`).
- **Firewall / reachability (the load-bearing subtlety).** On the
  manager, port 4646 is allowed only from the LAN CIDR:
  `bootstrap/playbooks/configure_network.yml:21`
  (`{ port: 4646, ... from_ip: "192.168.0.0/16" }`). By contrast, SSH
  (port 22) is allowed from **both** the LAN and the Tailscale CGNAT
  range: `configure_network.yml:10-11`
  (`192.168.0.0/16` and `100.64.0.0/10`). A CI node reaching the Nomad
  API over the tailnet arrives from `100.64.0.0/10`, which the current
  4646 rule does **not** permit. This gap must be closed deliberately and
  narrowly, or the deploy will fail to connect.
- **Existing GitHub Actions conventions.** Workflows live in
  `.github/workflows/` (`claude-ollama.yaml`, `hermes-interactive.yaml`).
  Both gate on `github.actor == 'JasperHG90'`
  (`.github/workflows/claude-ollama.yaml:46-54`,
  `.github/workflows/hermes-interactive.yaml:18-22`), pin `runs-on:
  ubuntu-latest`, set `timeout-minutes`, declare least-privilege
  `permissions:`, and read credentials from `secrets.*`. Any new workflow
  should match this style.

What is missing: no automated deploy path exists, no ephemeral-CI
Tailscale identity (OAuth client + `tag:ci`), no scoped Nomad ACL policy
or token for deploys, and no firewall/ACL rule that lets a tailnet CI
node reach 4646 under least privilege.

## 5. Non-goals / out of scope

- **Not building or changing `talat-webhook-exporter`.** The service is
  implemented and deployed. Its source lives in a separate repo. This
  ticket touches only the deploy path.
- **Not the auth/OIDC epic.** Independent thread. No Vault OIDC, HAProxy,
  Boundary, or human-SSO work.
- **Not migrating the cluster's own Tailscale setup.** The manager's
  subnet-router auth-key flow
  (`bootstrap/playbooks/configure_tailscale.yml`) stays as is. This
  ticket adds a *CI* identity, it does not re-do node onboarding.
- **Not adopting Nomad Pack.** The repo's render-and-submit pattern is
  Terraform `nomad_job` + `templatefile`; reuse it. Do not introduce
  `nomad-pack` as new tooling unless Open Question Q1 is settled that
  way.
- **Not broadening the existing `developer` Nomad policy** or reusing the
  bootstrap token for CI. The deploy gets its own scoped policy/token.
- **Not managing tailnet ACLs in code beyond what the repo can hold.**
  The tailnet ACL policy lives in the Tailscale admin console; this
  ticket specifies the required tag/rule and documents it, but cannot
  commit the console's ACL file into this repo unless the operator keeps
  one here (Q4).

## 6. Requirements & restrictions

Must achieve:

1. **Ephemeral tailnet join.** A GitHub Actions job uses
   `tailscale/github-action` with an **OAuth client** (id + secret) and
   an **ACL tag** (e.g. `tag:ci`) to bring up an ephemeral node for the
   duration of the job, and the node is removed on job end (ephemeral
   nodes auto-deregister; verify the action's teardown/`--ephemeral`
   behavior).
2. **Submit over the tailnet using the existing pattern.** Once joined,
   the job talks to the Nomad API at the cluster (firebat) and submits
   the `talat-webhook-exporter` job via the repo's render-and-submit
   convention (Terraform `nomad_job` + `templatefile`, provider reading
   `NOMAD_ADDR`/`NOMAD_TOKEN` from env — see
   `deployments/applications/providers.tf:30`). If Q1 settles on a
   standalone `nomad job run` render instead, it must still render a
   template and submit, matching the "render then submit" spirit.
3. **Least-privilege tailnet ACL.** The `tag:ci` grant permits the CI
   node to reach **only** the Nomad API endpoint it needs
   (firebat:4646), nothing else on the tailnet.
4. **Least-privilege Nomad token.** A dedicated Nomad ACL policy scoped
   to submitting *this* job (model it on, but far narrower than,
   `bootstrap/roles/nomad_server/files/nomad_developer_policy.hcl`;
   `submit-job`/`read-job` on the job's namespace, no `alloc-exec`, no
   host-volume write), and a token minted from it, stored as a GitHub
   Actions secret.
5. **Reachability closed narrowly.** The 4646 firewall gap
   (`configure_network.yml:21` allows only `192.168.0.0/16`) is closed so
   the CI node's traffic is permitted, scoped as tightly as the setup
   allows (see Q3) — not a blanket open of 4646 to the tailnet.
6. **Secrets configured, none hardcoded.** Tailscale OAuth client
   id/secret and the scoped Nomad token are GitHub Actions secrets; no
   credential appears in the workflow or any committed file.
7. **Version pinning consistent with the repo.** The deployed version is
   pinned via git tag / var-file the same way existing jobs pin
   `*_version` (`deployments/applications/services.tf:116,159,172,196`)
   and the `rebuild_hermes` tag-read convention
   (`deployments/applications/justfile:23-31`).

Restrictions the repo enforces (each cited):

- **Simplicity / surface tradeoffs, do not pick silently**
  (`CLAUDE.md` sections 1-2): minimum mechanism, no speculative
  configurability; present the forks in section 11 rather than choosing.
- **Secrets in Vault / never hardcode** (`CLAUDE.md` "Key Conventions"):
  the Nomad token and Tailscale OAuth secret must not be committed. GitHub
  Actions secrets are the CI store; the long-lived source of truth stays
  Vault where applicable.
- **Task runner is `just`, HCL is `nomad fmt`-clean**
  (`CLAUDE.md` "Key Conventions"; `.pre-commit-config.yaml` `nomad-fmt`
  hook): any `.hcl` this ticket adds must pass `nomad fmt -recursive`.
- **Docs slop scan** (`.claude/rules/slop-scan-for-docs.md`): any markdown
  this ticket writes (runbook/secret-setup doc) must pass the three-layer
  scan and have every cited path/identifier resolve.
- **Adversarial review before done** (`.claude/rules/adversarial-reviews.md`):
  hand the finished deploy path to a review sub-agent.

## 7. Code surface

Exact files and anchors this change touches or must mirror. Several
targets are **new files**; the fork over *where* they live is Q1.

- **CREATE** `.github/workflows/deploy-talat-webhook-exporter.yaml` — the
  deploy workflow. Triggers on a tag push (Q2), gates on
  `github.actor == 'JasperHG90'` and pins `runs-on`/`timeout-minutes`/
  least-privilege `permissions` to match
  `.github/workflows/claude-ollama.yaml:32-55` and
  `.github/workflows/hermes-interactive.yaml:9-22`. Steps: checkout →
  `tailscale/github-action` (OAuth client + `tag:ci`, ephemeral) →
  render-and-submit the job with `NOMAD_ADDR`/`NOMAD_TOKEN` from secrets.
- **CREATE** the Nomad job artifact + its render/submit wiring. Two
  shapes depending on Q1:
  - *Terraform reuse:* a `talat-webhook-exporter.hcl` job template plus a
    `nomad_job` resource, mirroring
    `deployments/applications/services.tf:110-136` and the empty provider
    at `deployments/applications/providers.tf:30`. Note the blast-radius
    concern in Q1: `terraform apply` reconciles **all** jobs in the
    stack, not just talat.
  - *Standalone render-and-submit:* a template + `nomad job run` step in
    the workflow, matching the "render then submit" spirit without the
    full Terraform stack.
- **CREATE** a scoped Nomad ACL policy file, modeled on but narrower than
  `bootstrap/roles/nomad_server/files/nomad_developer_policy.hcl` (which
  today grants `namespace "default" { policy = "write" }` + `submit-job`
  and more). Decide whether it is applied imperatively like
  `bootstrap/roles/nomad_server/tasks/main.yml:182-186` or via a new
  `nomad_acl_policy`/`nomad_acl_token` Terraform resource (Q5).
- **EDIT** `bootstrap/playbooks/configure_network.yml:21` — the 4646
  firewall rule currently allows only `192.168.0.0/16`. Add the narrowest
  rule that admits the CI node's tailnet source (compare the port-22
  precedent at `configure_network.yml:10-11`, which already pairs
  `192.168.0.0/16` with `100.64.0.0/10`). Scope per Q3.
- **CREATE (docs)** a short deploy runbook / secret-setup note (e.g. under
  `docs/`) listing the required GitHub secrets (Tailscale OAuth client
  id/secret, scoped Nomad token), the `tag:ci` tailnet ACL grant, and how
  the OAuth client is provisioned. Subject to the slop scan.
- **Read-only anchors to cite, do not edit:**
  `bootstrap/roles/tailscale/tasks/main.yml:57-68` (current auth-key
  join, contrast with CI OAuth),
  `bootstrap/playbooks/configure_tailscale.yml:41-58` (manager is the
  subnet router),
  `deployments/applications/justfile:23-31` (version/tag-read
  convention).

## 8. Tests & validation gates

- **Repo gate:** `just pre_commit` (root `justfile:17-18` →
  `pre-commit run --all-files`). Configured hooks
  (`.pre-commit-config.yaml`): check-json, check-ast,
  check-merge-conflict, check-yaml (`--unsafe`), debug-statements,
  detect-private-key, end-of-file-fixer, the local `nomad-fmt` hook on
  `*.hcl` (`.pre-commit-config.yaml:16-21`), and — new since this ticket
  was first scoped — two local Terraform hooks: `terraform-fmt`
  (`terraform fmt -check -recursive`, `:22-27`) and `terraform-validate`
  (`scripts/tf_validate.sh`, `:28-33`). `tf_validate.sh` validates each
  root offline (`deployments/infrastructure`, `deployments/applications`,
  `deployments/applications/modules/bucket`) with no backend or
  credentials. This closes the earlier "Terraform is not validated by any
  gate" caveat: if Q1 settles on the Terraform-stack shape, any new
  `nomad_job`/`*.tf` this ticket adds under those roots **is** now
  fmt-checked and `terraform validate`-checked by `just pre_commit`.
  Concretely for this ticket:
  - The primary deliverable is a **GitHub Actions workflow YAML**
    (`.github/workflows/deploy-talat-webhook-exporter.yaml`). `check-yaml`
    (`--unsafe`) validates its YAML syntax only; it does **not**
    understand Actions schema. There is **no `actionlint`** in this repo
    (confirmed: zero matches in `.pre-commit-config.yaml` and the root
    `justfile`), so workflow-semantic linting is not gated here — do not
    assume it. If deeper workflow linting is wanted, adding `actionlint`
    is a separate decision, not part of this gate.
  - The new workflow YAML and any edited `configure_network.yml` must
    pass check-yaml and end-of-file-fixer.
  - Any new `.hcl` (job template, ACL policy) must pass `nomad fmt
    -recursive`. Note: a **Nomad ACL policy** `.hcl` is not a job spec;
    confirm `nomad fmt` accepts it, and if not, keep policy HCL outside
    the `nomad-fmt` `files: '\.hcl$'` glob or format it acceptably.
  - Any new `*.tf` must pass `terraform fmt -check -recursive` and
    `scripts/tf_validate.sh`.
  - detect-private-key must not trip — no key material in any committed
    file. `.pre-commit-config.yaml:1` excludes `^\.(claude|loop)/`, so
    this ticket file is not linted, but files under `.github/`,
    `bootstrap/`, `deployments/`, and `docs/` **are**.

- **No unit-test suite applies to CI YAML/HCL.** The
  `all-code-needs-tests` rule (`.claude/rules/python-testing.md`) targets
  code; this ticket ships infra config. Verification is the evals below,
  not a pytest.

**Evals — acceptance for C1.** The live cluster is reachable from *this*
harness via the environment (`NOMAD_ADDR`/`NOMAD_TOKEN`, plus
`VAULT_ADDR`/`VAULT_TOKEN`/`CONSUL_HTTP_ADDR`), so the render/submit path
can be validated statically here. The CI **workflow itself runs on GitHub,
not in this harness**, so its true acceptance is a real tag-push run.
Be explicit about which evals run where.

- **Runs in-harness (static / local, gate before hand-off):**
  1. **Workflow YAML parses.**
     Command: `just pre_commit` (or `pre-commit run check-yaml
     --files .github/workflows/deploy-talat-webhook-exporter.yaml`).
     Expected: check-yaml passes. (Syntax only — see the `actionlint`
     caveat above; a green check-yaml does **not** prove the Actions
     schema is correct.)
  2. **Render-and-submit path is a valid Nomad job.** Render the
     `talat-webhook-exporter` template with its pinned version, then:
     Command: `nomad job validate <rendered>.hcl` against `$NOMAD_ADDR`.
     Expected: `Job validation successful`, no errors.
  3. **The submit plans cleanly against the live server.**
     Command: `nomad job plan <rendered>.hcl` (server firebat at
     `192.168.2.30:4646`, confirmed reachable: `nomad server members`
     shows `firebat.global` alive/leader).
     Expected: a plan diff prints and the command exits 0/1 (1 = plan
     produced with changes), not a connection or auth error — proving the
     render-and-submit command line the workflow will run is well-formed.
  4. **Scoped Nomad ACL token has only the needed capabilities.** Once
     the scoped policy/token exist (subticket 3): with the *scoped*
     token, confirm the allowed action succeeds and an out-of-scope one is
     refused.
     Command (allowed): `NOMAD_TOKEN=<scoped> nomad job validate
     <rendered>.hcl` → success.
     Command (denied): `NOMAD_TOKEN=<scoped> nomad alloc exec <id> sh` (or
     any `alloc-exec`/host-volume-write action) → expected `Permission
     denied` (HTTP 403), proving the policy is narrower than `developer`
     (`bootstrap/roles/nomad_server/files/nomad_developer_policy.hcl`).

- **Runs only on a real CI run (end-to-end — the true close-out, on
  GitHub, not here):**
  5. **Tag push deploys over the ephemeral tailnet.** Push a throwaway
     tag (per Q2) to fire the workflow.
     Expected: the job brings up an ephemeral Tailscale node tagged
     `tag:ci`; the render-and-submit step reaches firebat:4646 and submits
     the job; on the cluster `nomad job status talat-webhook-exporter`
     shows the **new version/submit time**; and the ephemeral node
     deregisters on job end (verify it is gone from the tailnet device
     list).
  6. **ACL-tag scoping confirmed (least-privilege proof).** From within
     the CI job, before teardown: firebat:4646 is reachable **only** from
     `tag:ci` (the tailnet ACL, per Q3), and a non-Nomad tailnet target is
     unreachable from the CI node.
     Expected: 4646 reachable from the CI node; a second, non-granted
     tailnet host/port is refused — proving the `tag:ci` grant is scoped
     to the Nomad API alone, not a blanket tailnet open.

  Honest scope: evals 1-4 run in this harness against the live cluster and
  gate the hand-off; evals 5-6 cannot be reproduced here (they require the
  GitHub-hosted runner, the OAuth client, and a real tag push) and are the
  operator-visible acceptance for marking C1 done. Do not report the
  ticket complete on the static evals alone.

- **Docs slop scan** (`.claude/rules/slop-scan-for-docs.md`) on the
  runbook: Layer 0 (identity leaks, hallucinated paths, bare stubs) is
  categorical; every cited path/identifier must resolve.
- **Adversarial review** (`.claude/rules/adversarial-reviews.md`) before
  reporting done.

- **Eval marker** (the acceptance spec for this ticket, five-column
  scenarios): `.loop/evals/C1-cicd-tailscale-github-actions-deploy.md`.

## 9. Risk assessment

- **Blast radius.**
  - *If deployed via the full Terraform stack (Q1 option A):* HIGH — a CI
    `terraform apply` on `deployments/applications` reconciles **every**
    `nomad_job` (phoenix, hermes, loki, memex, bifrost, mlflow), so a
    drifted state or a bad var could redeploy or disrupt unrelated
    services. Strong argument for a targeted submit (option B).
  - *Firewall edit:* MEDIUM — `configure_network.yml:21` governs access
    to the Nomad control plane. Too broad a rule (all of
    `100.64.0.0/10`) exposes 4646 to anything on the tailnet; too narrow
    and the deploy can't connect.
  - *Nomad token:* MEDIUM — a token scoped like `developer` would hand CI
    `alloc-exec` and host-volume write across the default namespace.
    Scope tightly.
- **Reversibility.** HIGH for the additive pieces (delete the workflow,
  revoke the OAuth client, revoke the Nomad token, remove the `tag:ci`
  ACL grant). The firewall edit is a one-line revert in Ansible but
  requires a re-run of `configure_network.yml` to take effect on the
  host.
- **Likeliest failure modes.**
  1. **Reachability overlooked** — workflow joins the tailnet but 4646
     still refuses the `100.64.0.0/10` source (`configure_network.yml:21`
     unchanged), so the submit hangs/fails. Mitigation: requirement 5 and
     the firewall edit in section 7.
  2. **Over-broad grants** — reusing `developer` or opening 4646 tailnet-
     wide. Mitigation: dedicated scoped policy + narrow ACL, negative
     checks in section 8.
  3. **Full-stack apply side effects** — see blast radius; Q1.
  4. **Ephemeral node not torn down** — misconfigured `tailscale/github-
     action` leaves a stale node. Mitigation: `--ephemeral` + verify
     deregistration in the acceptance check.
  5. **Secret leakage** — OAuth secret or Nomad token committed. detect-
     private-key catches key material but not all tokens; requirement 6
     and review guard this.
  6. **Where the tag lives** — if the deploy triggers on a localstack tag
     but the service versions live in the talat repo, the pinned version
     and the tag can drift (Q2).

## 10. Subtickets

Ordered, dependency-aware.

1. **Settle the deploy shape (Q1) and trigger (Q2).** Decide
   Terraform-stack vs standalone render-and-submit, and which repo's tag
   push fires the workflow. Blocks everything. Depends on: operator
   answering Q1/Q2.
2. **Provision the CI Tailscale identity.** Create the OAuth client and
   the `tag:ci` ACL grant in the Tailscale admin console; scope the tag
   to reach only firebat:4646. Store OAuth client id/secret as GitHub
   secrets. Depends on: 1.
3. **Mint the scoped Nomad ACL policy + token.** Author the narrow policy
   (model: `nomad_developer_policy.hcl`, far tighter), apply it (Q5),
   mint a token, store as a GitHub secret. Depends on: 1.
4. **Close the 4646 reachability gap.** Edit
   `bootstrap/playbooks/configure_network.yml:21` to admit the CI node's
   tailnet source at the narrowest scope (Q3); re-run the network play.
   Depends on: 2 (know the source range/identity).
5. **Author the render-and-submit artifact.** The job template + submit
   mechanism per the option chosen in 1, with version pinning matching
   the `*_version` / tag-read convention
   (`services.tf:116`, `justfile:23-31`). Depends on: 1.
6. **Author the workflow.** `.github/workflows/deploy-talat-webhook-
   exporter.yaml`: tag trigger, actor gate, ephemeral Tailscale step,
   render-and-submit step reading secrets. Depends on: 2,3,5.
7. **Dry-run + negative checks + runbook.** Throwaway-tag end-to-end,
   least-privilege negative checks, secret-setup runbook, `just
   pre_commit`, slop scan, adversarial review. Depends on: 4,6.

## 11. Open questions

Each fork the request/repo does not settle, with a recommendation.
Operator should settle Q1-Q4 before the loop runs; Q5 is an
implementation fork the loop must not resolve silently.

- **Q1 — Full Terraform stack, or standalone render-and-submit?** The
  repo's render-and-submit is Terraform `nomad_job` + `templatefile`
  (`services.tf`), but a CI `terraform apply` reconciles *all* app jobs
  (section 9 blast radius). *Recommendation:* a **standalone** render-
  and-submit for just `talat-webhook-exporter` (render its template,
  `nomad job run` over the tailnet). It preserves the "render then
  submit" convention, keeps blast radius to one job, and matches the
  single-service tag-push model. Confirm.
- **Q2 — Which repo's tag push triggers the deploy, and where does the
  workflow live?** The service source is in a separate repo; this ticket
  file and the render-and-submit convention are in `localstack`. A tag on
  the service repo is the natural version signal, but the deploy
  mechanism lives here. *Recommendation:* trigger on a tag in the
  **service's own repo** and have that workflow check out this repo's
  deploy assets (or a thin published action), so the pinned version and
  the tag cannot drift. If the operator prefers everything in
  `localstack`, trigger on a `talat-v*` tag here. Confirm.
- **Q3 — How narrowly can 4646 be scoped for the CI node?** The CI node
  arrives from `100.64.0.0/10` (CGNAT); the manager is a subnet router.
  A UFW `from_ip` on 4646 cannot pin a single ephemeral tailnet IP.
  *Recommendation:* rely primarily on the **tailnet ACL** (`tag:ci` →
  firebat:4646 only) for least privilege, and add the *minimum* UFW rule
  needed to admit tailnet traffic to 4646 (mirroring the port-22
  precedent at `configure_network.yml:10-11`). Document that the tight
  boundary is the tailnet ACL, the UFW rule is the coarse gate. Confirm
  the operator accepts this split.
- **Q4 — Is the tailnet ACL kept in this repo or only in the Tailscale
  console?** There is no ACL file in the repo today; tailnet ACLs are
  console-managed. *Recommendation:* keep the authoritative ACL in the
  console, and add a **read-only reference copy + the OAuth/tag setup
  steps** to the runbook under `docs/` so the CI grant is reviewable.
  Confirm whether the operator wants a committed ACL file (GitOps) or
  console-only.
- **Q5 — How is the scoped Nomad policy/token created: Ansible-imperative
  or Terraform?** Today policies are applied imperatively
  (`nomad_server/tasks/main.yml:182-186`); there are no `nomad_acl_*`
  Terraform resources. *Recommendation:* add the scoped policy the same
  imperative way for consistency with the existing bootstrap, and mint
  the token out-of-band into a GitHub secret; only introduce
  `nomad_acl_policy`/`nomad_acl_token` Terraform if the operator wants
  ACLs under Terraform state. The loop must not pick silently.
- **Q6 — Namespace for the talat job.** The `developer` policy and all
  current jobs use `namespace "default"`. *Recommendation:* keep talat in
  `default` and scope the CI policy to `namespace "default"` with only
  `submit-job`/`read-job` (not `write`), unless the operator wants a
  dedicated namespace for blast-radius isolation. Surface, do not
  pre-decide.

## Resolved forks (operator, 2026-07-23)

**RESCOPE (operator, 2026-07-23): C1 is now a connectivity smoke test,
not a talat deploy.** talat-webhook-exporter has moved to its own repo, so
C1 no longer deploys it. C1's purpose is to **stand up the Tailscale
CI→cluster connection and prove it from GitHub Actions by reaching one
service over the tailnet** (a ping/curl reachability check). No deploy, no
`terraform plan`, no Nomad job submission.

- **Q1 → Neither deploy option; a reachability ping.** GHA joins the
  tailnet (`tag:ci`) and pings/curls one cluster service to prove it can
  get through. That's the whole deliverable.
- **Q2 → N/A (skipped).** No talat tag-trigger needed. Trigger the proof
  via `workflow_dispatch` (and/or on PR). The service-repo-tag question
  is moot under the rescope.
- **Q3 → Tailnet ACL primary + minimal UFW.** Least privilege via the
  tailnet ACL (`tag:ci` → firebat only); minimum UFW rule to admit
  tailnet traffic to the target port (mirroring the port-22 precedent).
  Tight boundary = ACL; UFW = coarse gate.
- **Q4 → Console-authoritative ACL + docs reference copy.** Keep the
  authoritative tailnet ACL in the Tailscale console; add a read-only
  reference copy + the OAuth/`tag:ci` setup steps to a `docs/` runbook so
  the CI grant is reviewable.
- **Q5 → N/A.** A reachability ping needs no Nomad ACL policy/token and
  no provider creds. Drop the scoped-token work.
- **Q6 → N/A.** No job is submitted, so namespace scoping does not apply.

**Dependencies:** C1 is independent of the auth epic (F/S/L/M/R tickets).
It needs only the Tailscale tailnet + a reachable service endpoint.
