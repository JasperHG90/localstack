# Skills Single Source of Truth — Implementation Plan (Option 1)

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** Eliminate skill drift between the Terraform-managed baseline and the Hermes writable scratchpad by making `JasperHG90/hermes-skills` (private) the single git-based source of truth, with auto-sync of agent-created skills to an `agent-sync` branch and PR-based promotion.

**Architecture:** Replace the current TSV-base64-templating + tarball-pull approach with a single `git clone` at prestart. Initialize `/opt/data/skills/` as a git repo tracking the same remote, so a cron job can auto-commit and push agent changes to an `agent-sync` branch. Promotion is a PR from `agent-sync` → `main`, guided by a Hermes skill.

**Tech Stack:** Nomad, Terraform, Podman, git, GitHub, Hermes cron, shell scripts

---

## Current State (what exists today)

| Component | Location | Source |
|---|---|---|
| IaC-managed skills | `deployments/applications/services/hermes/skills/` in `localstack` repo | Templated into TSV via `services.tf` `fileset` → decoded at prestart to `/opt/data/skills-library/` |
| External public skills | `JasperHG90/skills` repo (public) | Tarball download at prestart to `/opt/data/skills-library-jasperhg90/skills` |
| Writable scratchpad | `/opt/data/skills/` | Hermes entrypoint copies bundled skills here; agent can create/modify |
| Prune script | `hermes.hcl` start-hermes.sh | Removes bundled skills that collide with IaC library |

**Problems:**
1. Two separate baseline sources (TSV template + tarball) with no unified versioning
2. Agent-created skills in `/opt/data/skills/` are lost on redeploy (volume is persistent but `rm -rf` + rebuild is not applied to `/opt/data/skills/`)
3. No mechanism to promote proven agent skills back to baseline
4. Skill content embedded in Terraform HCL as base64 — unreadable, unreviewable
5. Public repo (`JasperHG90/skills`) exposes internal skill configs that may contain environment-specific details

## Target State

```
JasperHG90/hermes-skills repo (private, single source of truth)
├── main branch
│   └── skills/
│       ├── architecture/       ← migrated from JasperHG90/skills (public)
│       ├── development/        ← migrated from JasperHG90/skills (public)
│       ├── documentation/      ← migrated from JasperHG90/skills (public)
│       ├── learning/           ← migrated from JasperHG90/skills (public)
│       ├── ops/                ← migrated from JasperHG90/skills (public)
│       ├── tools/              ← migrated from JasperHG90/skills (public)
│       ├── devops/             ← migrated from localstack IaC
│       ├── knowledge/          ← migrated from localstack IaC
│       ├── productivity/       ← migrated from localstack IaC
│       └── research/           ← migrated from localstack IaC
└── agent-sync branch
    └── skills/
        └── (agent-created/modified skills, auto-synced)

Hermes container filesystem:
├── /opt/data/skills-library/     ← git clone of JasperHG90/hermes-skills@main (read-only baseline)
└── /opt/data/skills/             ← git repo tracking agent-sync branch (writable scratchpad)
```

**Data flow:**
1. **Deploy:** prestart `git clone` → `/opt/data/skills-library/` (baseline, read-only)
2. **Runtime:** agent creates/modifies skills in `/opt/data/skills/`
3. **Sync:** cron job `git add -A && git commit && git push origin agent-sync --force` every 6h
4. **Promotion:** user reviews `agent-sync` branch, opens PR to `main`, merges proven skills
5. **Next deploy:** prestart re-clones `main` → new baseline includes promoted skills

---

## Phase 1: Consolidate All Skills into `JasperHG90/hermes-skills`

The new private repo `JasperHG90/hermes-skills` has been created (2026-07-11). It needs to receive skills from TWO sources:
- **Source A:** Public `JasperHG90/skills` repo (categories: `architecture/`, `development/`, `documentation/`, `learning/`, `ops/`, `tools/`)
- **Source B:** Localstack IaC skills (categories: `devops/`, `knowledge/`, `productivity/`, `research/`)

### Task 1.1: Audit skills from both sources

**Objective:** Enumerate all skills from both sources to know what needs migrating and detect collisions.

**Step 1:** List all skills in the public `JasperHG90/skills` repo

```bash
git clone https://github.com/JasperHG90/skills.git /tmp/skills-audit-public
find /tmp/skills-audit-public/skills -name SKILL.md | sort
```

Expected: skills in `architecture/`, `development/`, `documentation/`, `learning/`, `ops/`, `tools/` directories.

**Step 2:** List all skills in the localstack IaC directory

```bash
# From localstack repo root
find deployments/applications/services/hermes/skills -name SKILL.md | sort
```

Expected: skills in `devops/`, `knowledge/`, `productivity/`, `research/` directories.

**Step 3:** Check for name collisions between the two sets

```bash
comm -12 \
  <(find /tmp/skills-audit-public/skills -name SKILL.md | sed 's|.*/skills/||' | sort) \
  <(find deployments/applications/services/hermes/skills -name SKILL.md | sed 's|.*/skills/||' | sort)
```

Expected: empty (no collisions) or a list of collisions to resolve.

### Task 1.2: Migrate all skills into `JasperHG90/hermes-skills`

**Objective:** Copy skills from both sources into the new private repo, preserving directory structure.

**Step 1:** Clone the new private repo

```bash
git clone https://github.com/JasperHG90/hermes-skills.git /tmp/hermes-skills-migration
cd /tmp/hermes-skills-migration
git checkout -b feat/consolidate-baseline
mkdir -p skills
```

**Step 2:** Copy skills from the public `JasperHG90/skills` repo (Source A)

```bash
# Architecture, development, documentation, learning, ops, tools
for dir in architecture development documentation learning ops tools; do
  cp -r /tmp/skills-audit-public/skills/$dir /tmp/hermes-skills-migration/skills/$dir
done
```

**Step 3:** Copy skills from the localstack IaC directory (Source B)

```bash
# From localstack repo root
for dir in devops knowledge productivity research; do
  cp -r deployments/applications/services/hermes/skills/$dir /tmp/hermes-skills-migration/skills/$dir
done
```

**Step 4:** Copy supporting files from the public repo (if useful)

```bash
# Optionally copy .gitignore, AGENTS.md, CONTRIBUTING.md, templates/, scripts/
cp /tmp/skills-audit-public/.gitignore /tmp/hermes-skills-migration/ 2>/dev/null || true
cp /tmp/skills-audit-public/AGENTS.md /tmp/hermes-skills-migration/ 2>/dev/null || true
cp -r /tmp/skills-audit-public/templates /tmp/hermes-skills-migration/ 2>/dev/null || true
cp -r /tmp/skills-audit-public/scripts /tmp/hermes-skills-migration/ 2>/dev/null || true
```

**Step 5:** Verify all SKILL.md files are valid frontmatter

```bash
cd /tmp/hermes-skills-migration
find skills -name SKILL.md -exec sh -c 'head -1 "$1" | grep -q "^---" && echo "OK: $1" || echo "BAD: $1"' _ {} \;
```

Expected: all OK

**Step 6:** Commit and push

```bash
cd /tmp/hermes-skills-migration
git add -A
git commit -m "feat: consolidate all skills from public repo + localstack IaC

Migrated skills from two sources into this private repo to establish
a single source of truth for Hermes agent skills:
- From JasperHG90/skills (public): architecture, development, documentation,
  learning, ops, tools
- From localstack IaC: devops, knowledge, productivity, research"
git push origin feat/consolidate-baseline
```

**Step 7:** Open PR and merge

```bash
gh pr create --repo JasperHG90/hermes-skills \
  --title "Consolidate all skills from public repo + localstack IaC" \
  --body "Migrates skills from two sources to establish single source of truth."
# After review, merge
gh pr merge --squash
```

**Step 8:** Delete skills directory from localstack repo

```bash
# In localstack repo
git checkout -b chore/remove-iac-skills
rm -rf deployments/applications/services/hermes/skills/
git add -A
git commit -m "chore: remove IaC-managed skills (migrated to JasperHG90/hermes-skills)

Skills now live in JasperHG90/hermes-skills repo. The TSV template approach
is replaced by git clone at prestart (see hermes.hcl changes)."
git push origin chore/remove-iac-skills
gh pr create --title "Remove IaC-managed skills (migrated to JasperHG90/hermes-skills)" \
  --body "Skills have been consolidated into JasperHG90/hermes-skills repo."
```

**Note:** The public `JasperHG90/skills` repo stays as-is for now. It's no longer referenced by the Hermes deployment. It can be archived or deleted later if desired.

---

## Phase 2: Replace TSV Templating with Git Clone

### Task 2.1: Add git to the Hermes container image

**Objective:** Ensure the Hermes container image has `git` installed so prestart can clone the repo.

**Step 1:** Check if git is already in the image

```bash
podman run --rm ghcr.io/jasperhg90/hermes:0.12.0-memex-v1.0.1 which git
```

Expected: either a path (git exists) or empty (git missing).

**Step 2:** If git is missing, add to Dockerfile

```dockerfile
RUN apt-get update && apt-get install -y --no-install-recommends git && rm -rf /var/lib/apt/lists/*
```

**Step 3:** Rebuild and push image

```bash
cd deployments/applications/services/hermes/
podman build -t ghcr.io/jasperhg90/hermes:0.12.0-memex-v1.0.1 .
podman push ghcr.io/jasperhg90/hermes:0.12.0-memex-v1.0.1
```

**Step 4:** Verify

```bash
podman run --rm ghcr.io/jasperhg90/hermes:0.12.0-memex-v1.0.1 git --version
```

### Task 2.2: Replace TSV template with git clone in prestart

**Objective:** Replace the base64 TSV approach with a `git clone` of `JasperHG90/hermes-skills` into `/opt/data/skills-library/`.

**Step 1:** Remove the `skills` map from `services.tf`

Find the `resource "nomad_job" "hermes"` block and remove:

```hcl
      skills = {
        for f in fileset("${path.module}/services/hermes/skills", "**/SKILL.md") :
        trimsuffix(f, "/SKILL.md") => file("${path.module}/services/hermes/skills/${f}")
      }
```

**Step 2:** Remove the `skills-bundle.tsv` template block from `hermes.hcl`

Remove:

```hcl
      template {
        data        = <<-EOT
%{for path, body in skills~}
${base64encode(path)}|${base64encode(body)}
%{endfor~}
EOT
        destination = "local/skills-bundle.tsv"
      }
```

Also remove the volume mount:

```hcl
          "local/skills-bundle.tsv:/tmp/hermes/skills-bundle.tsv:ro",
```

**Step 3:** Replace the TSV decode section in `setup.sh` with git clone

Replace:

```sh
# IaC-managed read-only skill library...
if [ -f /tmp/hermes/skills-bundle.tsv ]; then
  rm -rf /opt/data/skills-library
  mkdir -p /opt/data/skills-library
  while IFS='|' read -r path_b64 body_b64; do
    ...
  done < /tmp/hermes/skills-bundle.tsv
fi
```

With:

```sh
# ── Baseline skill library: git clone of JasperHG90/hermes-skills ──
# Single source of truth. Refreshed from scratch every deploy so removed
# skills are pruned. Read-only by convention; Hermes enforces this via
# skill_manage refusing writes outside HERMES_HOME/skills.
# Writable agent skills live in /opt/data/skills/ and are never touched here.
SKILLS_REF="${skills_repo_ref}"
rm -rf /opt/data/skills-library
if git clone --depth 1 --branch "$SKILLS_REF" \
     "https://github.com/JasperHG90/hermes-skills.git" \
     /opt/data/skills-library 2>/dev/null; then
  rm -rf /opt/data/skills-library/.git
  echo "hermes: baseline skills synced @ $SKILLS_REF"
else
  echo "hermes: WARN failed to clone JasperHG90/hermes-skills@$SKILLS_REF (continuing)"
  mkdir -p /opt/data/skills-library
fi
```

> **Note:** The clone uses a git credential helper (set up in Task 2.3) rather than embedding the token in the URL. The `GITHUB_PERSONAL_ACCESS_TOKEN` env var is available to the prestart task via the Vault template.

**Step 4:** Replace the external tarball pull with cleanup

Replace:

```sh
# External read-only library: JasperHG90/skills (public, refresh per deploy).
EXT_JG_REF="${external_skills_jasperhg90_ref}"
rm -rf /opt/data/skills-library-jasperhg90
mkdir -p /opt/data/skills-library-jasperhg90
if curl -fsSL "https://github.com/JasperHG90/skills/archive/$EXT_JG_REF.tar.gz" \
   | tar xz -C /opt/data/skills-library-jasperhg90 --strip-components=1 2>/dev/null; then
  ...
fi
```

With:

```sh
# External tarball pull removed — baseline clone above now covers all skills.
# Clean up stale directory from previous deploys.
rm -rf /opt/data/skills-library-jasperhg90
```

**Step 5:** Update `config.yaml` template to remove the jasperhg90 external_dir

Replace:

```yaml
skills:
  external_dirs:
    - /opt/data/skills-library
    - /opt/data/skills-library-jasperhg90/skills
```

With:

```yaml
skills:
  external_dirs:
    - /opt/data/skills-library
```

**Step 6:** Update `services.tf` templatefile variables

Replace:

```hcl
      external_skills_jasperhg90_ref = "main"
```

With:

```hcl
      skills_repo_ref = "main"
```

**Step 7:** Add `GITHUB_PERSONAL_ACCESS_TOKEN` to the prestart task

The private repo requires authentication for clone. Add a Vault template for the GitHub PAT:

```hcl
      template {
        data = <<EOF
{{- with secret "${github_secret}" }}
GITHUB_PERSONAL_ACCESS_TOKEN={{ .Data.data.pat }}
{{- end }}
EOF
        destination = "secrets/github.env"
        env         = true
      }
```

And configure the git credential helper in `setup.sh` before the clone:

```sh
# Configure git credential helper so token isn't embedded in URLs
git config --global credential.helper \
  '!f() { echo "username=x-access-token"; echo "password=$GITHUB_PERSONAL_ACCESS_TOKEN"; }; f'
```

**Step 8:** Update the prune script in start-hermes.sh

The repo structure has `skills/` as a subdirectory. Update the prune script:

```sh
if [ -d /opt/data/skills-library/skills ]; then
  find /opt/data/skills-library/skills -name SKILL.md \
    | sed -e 's|^/opt/data/skills-library/skills/||' -e 's|/SKILL.md$||' \
    | while IFS= read -r rel; do
        if [ -e "/opt/data/skills/$rel" ]; then
          echo "prune: /opt/data/skills/$rel (overridden by baseline)"
          rm -rf "/opt/data/skills/$rel"
        fi
      done
fi
```

### Task 2.3: Initialize `/opt/data/skills/` as a git repo at prestart

**Objective:** Set up `/opt/data/skills/` as a git repo tracking the `agent-sync` branch so the cron job can push changes.

Add to `setup.sh` after the baseline clone:

```sh
# ── Initialize writable scratchpad as git repo for agent-sync ──
SKILLS_REPO="https://github.com/JasperHG90/hermes-skills.git"
cd /opt/data/skills
if [ ! -d .git ]; then
  git init
  git remote add origin "$SKILLS_REPO"
  git fetch origin main --depth 1
  git checkout -b agent-sync
  git add -A
  git commit -m "agent-sync: initial state (bundled skills)" --allow-empty
else
  git remote set-url origin "$SKILLS_REPO" 2>/dev/null || git remote add origin "$SKILLS_REPO"
fi

# .gitignore for non-skill files
cat > /opt/data/skills/.gitignore <<'GITIGNORE'
__pycache__/
*.pyc
.DS_Store
*.log
GITIGNORE

# Git user for commits
git config user.name "Hermes Agent"
git config user.email "hermes@localstack"
```

### Task 2.4: Remove the `skills` volume mount line from prestart

In the prestart task's `config.volumes`, remove:

```hcl
          "local/skills-bundle.tsv:/tmp/hermes/skills-bundle.tsv:ro",
```

---

## Phase 3: Auto-Sync Cron Job

### Task 3.1: Create the sync script

Create `deployments/applications/services/hermes/scripts/sync-skills.sh`:

```bash
#!/bin/sh
# sync-skills.sh — Auto-sync Hermes writable skills to agent-sync branch.
# Run via Hermes cron. Silent when no changes (watchdog pattern).
set -e

SKILLS_DIR="/opt/data/skills"
cd "$SKILLS_DIR"

# Ensure we're on agent-sync
git checkout agent-sync 2>/dev/null || git checkout -b agent-sync

# Stage everything
git add -A

# Check if there are changes to commit
if git diff --cached --quiet; then
  exit 0
fi

# Commit and push
TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
git commit -m "agent-sync: $TIMESTAMP"
git push origin agent-sync --force

echo "skills-sync: pushed $TIMESTAMP"
```

```bash
chmod +x deployments/applications/services/hermes/scripts/sync-skills.sh
```

### Task 3.2: Register the cron job

Add to `register-cron.sh`:

```sh
send_cron '/cron add "0 */6 * * *" "Run the skills auto-sync script at /opt/data/scripts/sync-skills.sh to commit and push agent-created/modified skills to the agent-sync branch on JasperHG90/hermes-skills. The script is silent when there are no changes." --name "skills-auto-sync"'
```

Deploy the script via prestart template:

```hcl
      template {
        data = <<-EOT
#!/bin/sh
# (sync-skills.sh content here)
EOT
        destination = "local/sync-skills.sh"
        perms       = "0755"
      }
```

Add to setup.sh:

```sh
mkdir -p /opt/data/scripts
cp /tmp/hermes/sync-skills.sh /opt/data/scripts/sync-skills.sh
chmod +x /opt/data/scripts/sync-skills.sh
```

Add to volumes:

```hcl
          "local/sync-skills.sh:/tmp/hermes/sync-skills.sh:ro",
```

### Task 3.3: Credential security

**Decision: Git credential helper, not URL-embedded token.**

The git remote URL must NOT contain the token. Use a credential helper so error output (which may be delivered to Telegram via cron) never leaks the PAT.

```sh
# In sync-skills.sh, before push:
git -C "$SKILLS_DIR" config credential.helper \
  '!f() { echo "username=x-access-token"; echo "password=$GITHUB_PERSONAL_ACCESS_TOKEN"; }; f'
```

Remote URL is plain HTTPS: `https://github.com/JasperHG90/hermes-skills.git`

---

## Phase 4: Promotion Skill

### Task 4.1: Create the skill-promotion skill

Create `JasperHG90/hermes-skills/skills/devops/skill-promotion/SKILL.md`:

```markdown
---
name: skill-promotion
description: "Promote agent-created skills from agent-sync branch to baseline main."
version: 1.0.0
author: JasperHG90
tags: [devops, skills, git, promotion]
---

# Skill Promotion

## When to Use

When the user asks to "promote skills", "review agent changes", or "merge agent-sync". Run after the auto-sync cron has pushed agent-created/modified skills to the `agent-sync` branch on `JasperHG90/hermes-skills`.

## Workflow

1. **Fetch the diff**: Compare `agent-sync` against `main` on `JasperHG90/hermes-skills`:
   ```bash
   git clone https://github.com/JasperHG90/hermes-skills.git /tmp/skills-promo
   cd /tmp/skills-promo
   git fetch origin agent-sync
   git diff main..origin/agent-sync --stat
   ```

2. **Review each changed skill**: For each modified or new SKILL.md:
   - Read the full content
   - Verify frontmatter is valid (name, description, version, author)
   - Check the skill follows the SKILL.md format
   - Flag any issues (incomplete steps, hardcoded paths, sensitive data)

3. **Present findings to user**: List all changes with a recommendation:
   - ✅ Promote: well-formed, useful skill
   - ⚠️ Needs work: valid but incomplete or has issues
   - ❌ Reject: not useful or contains problems

4. **Create PR for approved skills**:
   ```bash
   git checkout -b promote/$(date +%Y-%m-%d)
   git merge origin/agent-sync
   # Resolve conflicts, keeping only approved skills
   git push origin promote/$(date +%Y-%m-%d)
   gh pr create --repo JasperHG90/hermes-skills \
     --title "Promote agent-created skills" \
     --body "Skills promoted from agent-sync branch."
   ```

5. **After merge**: The next deploy will `git clone` the updated `main` branch, making the promoted skills available as baseline.

## Pitfalls

- **Conflict resolution**: `agent-sync` may have diverged significantly from `main`. Consider cherry-picking individual skills instead of merging wholesale.
- **Bundled skill noise**: `agent-sync` contains ALL files in `/opt/data/skills/`, including bundled skills that ship with the image. Focus only on new or modified SKILL.md files.
- **Force push**: Auto-sync uses `--force` on `agent-sync`. History is linear and squashed. Promotion should cherry-pick or copy specific skills, not merge the branch.
```

Commit to `JasperHG90/hermes-skills`:

```bash
cd /tmp/hermes-skills-migration  # or clone fresh
git checkout main && git pull
mkdir -p skills/devops/skill-promotion
# Save the SKILL.md content above
git add skills/devops/skill-promotion/
git commit -m "feat: add skill-promotion skill for agent-sync promotion workflow"
git push origin main
```

---

## Phase 5: Deploy and Verify

### Task 5.1: Deploy and verify prestart clone

```bash
cd deployments/applications
terraform plan -var-file=vars/prod.tfvars -out skills.plan
terraform apply skills.plan
```

Verify:
```bash
nomad alloc logs -task config <alloc_id> | grep "baseline skills synced"
# Expected: hermes: baseline skills synced @ main

nomad alloc exec -task hermes <alloc_id> ls /opt/data/skills-library/skills/
# Expected: all 10 skill category directories
```

### Task 5.2: Verify auto-sync cron

```bash
# Check cron registration
/cron list
# Expected: skills-auto-sync with schedule 0 */6 * * *

# Manual trigger
nomad alloc exec -task hermes <alloc_id> sh /opt/data/scripts/sync-skills.sh
# Expected: silent (no changes) or "skills-sync: pushed <timestamp>"

# Verify branch on GitHub
gh api repos/JasperHG90/hermes-skills/branches/agent-sync --jq '.name'
# Expected: agent-sync
```

### Task 5.3: Test the full round-trip

1. Create a test skill in `/opt/data/skills/test-category/test-skill/SKILL.md`
2. Trigger sync manually
3. Verify on GitHub: `gh api repos/JasperHG90/hermes-skills/contents/skills/test-category/test-skill/SKILL.md?ref=agent-sync`
4. Promote via PR: `gh pr create --repo JasperHG90/hermes-skills --head agent-sync --base main --title "Promote test-skill" && gh pr merge --squash`
5. Redeploy and verify skill is in baseline
6. Clean up test skill

---

## Risk Assessment

| Risk | Impact | Mitigation |
|---|---|---|
| GitHub token leaks in cron output | High — credential exposure | Git credential helper, not URL-embedded token. stderr redirect. |
| `agent-sync` branch diverges wildly from `main` | Medium — noisy promotion | Cherry-pick promotion, not merge. |
| Bundled skills create noise in agent-sync | Low — cosmetic | `.gitignore` excludes non-skill files. PR review filters noise. |
| Prestart clone fails (network issue) | Medium — no baseline skills | Non-fatal: `setup.sh` continues with empty library. Hermes still has bundled skills. |
| Git not available in container | High — prestart fails | Task 2.1 ensures git is installed. Verified before deploy. |
| Skills directory structure mismatch | Medium — prune script breaks | Task 2.2 Step 8 updates prune path to account for `skills/` subdir. |
| Private repo clone requires auth | Medium — clone fails if token missing | Vault template provides PAT; credential helper configured before clone. |

## Migration Notes

- **No downtime required**: Prestart runs before the main hermes task. As long as the clone succeeds, the transition is seamless.
- **Rollback**: Revert `hermes.hcl` and `services.tf` changes and redeploy. The old TSV approach still works if the skills directory is restored.
- **Vault**: No new secrets needed — `GITHUB_PERSONAL_ACCESS_TOKEN` is already in Vault.
- **Image rebuild**: Required only if git is not already in the container image (Task 2.1).
- **Public repo**: `JasperHG90/skills` stays as-is, no longer referenced by the deployment. Can be archived or deleted later.
- **Private repo**: `JasperHG90/hermes-skills` created 2026-07-11, initialized with README.