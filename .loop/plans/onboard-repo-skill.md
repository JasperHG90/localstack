---
type: plan
title: 'Plan: onboard-repo-skill'
description: A tracked project skill that connects one more of the operator's GitHub repositories to the lab and its docs to OpenViking, end to end.
tags:
- plan
generated:
  by: process:loopctl/2.2.2.dev1+gd84319696
  at: '2026-11-18T14:39:58+00:00'
slug: onboard-repo-skill
epic: null
depends_on: []
priority: null
---

# onboard-repo-skill

Relayed from: none

## Intent

Connecting `JasperHG90/loop-engineering-harness` to the lab took a long
conversation. The steps are spread over
`docs/how-to/authenticate-a-github-workflow-to-the-lab.md`, two Terraform
roots, two exact-match tests and a GitHub settings page. This ticket writes
one project skill, SKILL.md in a new .claude/skills/onboard-repo folder, that an agent
runs with a repository name and does the whole job:

1. Checks the repository exists under `JasperHG90`, and creates its `lab`
   GitHub Environment with `gh api -X PUT .../environments/lab` when it has
   none.
2. Adds a `vault_ci_callers` entry in
   `deployments/infrastructure/variables.tf` (key `<repo>-<workflow stem>`,
   `ov_sync` on when the repository syncs docs), and when it syncs docs the
   `prefixes` line in `deployments/applications/services.tf`. It updates the
   exact lists in `cli/tests/test_lab_auth_action.py` to match.
3. For each root, infrastructure first, saves a plan with
   `terraform plan -var-file=./vars/prod.tfvars -out <scratch file>` after
   `eval "$(uv run localstack env)"`, calling terraform directly because the
   `just apply` recipes in `deployments/infrastructure/justfile` and
   `deployments/applications/justfile` re-plan and wait for `yes`. It names
   what each plan should hold (three Vault resources, the
   `nomad_job.seaweedfs` IAM change, the `null_resource.firewall`
   `always_run` replacements, the consumer's prefix map), stops and asks the
   operator on anything else, then runs `terraform apply <that file>`, so
   what it applies is exactly what it checked. It checks the role with
   `vault read`, and waits for SeaweedFS's S3 port before the applications
   plan, since the infrastructure apply restarts that job.
4. Commits through the loop, asks the operator before pushing, and prints the
   caller workflow, pinned to the pushed commit, with no Tailscale inputs
   (ADR 0031).

`.gitignore` ignores `/.claude/*` except some rules, so it gains an
exception for `.claude/skills/onboard-repo/`. The how-to links to the skill.

Outcome: `git check-ignore` does not ignore the skill, Claude Code lists
`onboard-repo` in this repository, and every path, input and command it names
exists in the repository.

## Could invalidate this plan

- APM (`just kmctl-install`, `just kmctl-install-frozen`, `apm prune`) may
  delete or overwrite a skill directory under `.claude/skills/` that
  `apm.yml` does not list, which would wipe the skill on the next install.
  Then it needs another home. Settled by spike:onboard-repo-skill/3: APM
  0.33.0 left an unlisted onboard-repo SKILL.md
  byte-identical after `apm install`, `apm install --frozen` and
  `apm prune`. It would overwrite only a skill with the same name as one it
  installs, and no APM package ships `onboard-repo`.
