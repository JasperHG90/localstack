# Skills Single Source of Truth — Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** Eliminate skill drift between the Terraform-managed baseline and the Hermes writable scratchpad by making `JasperHG90/skills` the single git-based source of truth, with auto-sync of agent-created skills to an `agent-sync` branch and PR-based promotion.

**Architecture:** Replace the current TSV-base64-templating + tarball-pull approach with a single `git clone` at prestart. Initialize `/opt/data/skills/` as a git repo tracking the same remote, so a cron job can auto-commit and push agent changes to an `agent-sync` branch. Promotion is a PR from `agent-sync` → `main`, guided by a Hermes skill.

**Tech Stack:** Nomad, Terraform, Podman, git, GitHub, Hermes cron, shell scripts

---

## Current State (what exists today)

| Component | Location | Source |
|---|---|---|
| IaC-managed skills | `deployments/applications/services/hermes/skills/` in `localstack` repo | Templated into TSV via `services.tf` `fileset` → decoded at prestart to `/opt/data/skills-library/` |
| External public skills | `JasperHG90/skills` repo | Tarball download at prestart to `/opt/data/skills-library-jasperhg90/skills` |
| Writable scratchpad | `/opt/data/skills/` | Hermes entrypoint copies bundled skills here; agent can create/modify |
| Prune script | `hermes.hcl` start-hermes.sh | Removes bundled skills that collide with IaC library |

**Problems:**
1. Two separate baseline sources (TSV template + tarball) with no unified versioning
2. Agent-created skills in `/opt/data/skills/` are lost on redeploy (volume is persistent but `rm -rf` + rebuild is not applied to `/opt/data/skills/`)
3. No mechanism to promote proven agent skills back to baseline
4. Skill content embedded in Terraform HCL as base64 — unreadable, unreviewable

## Target State

```
JasperHG90/skills repo (single source of truth)
├── main branch
│   └── skills/
│       ├── architecture/
│       ├── development/
│       ├── documentation/
│       ├── learning/
│       ├── ops/
│       ├── tools/
│       ├── devops/          ← migrated from localstack
│       ├── knowledge/       ← migrated from localstack
│       ├── productivity/    ← migrated from localstack
│       └── research/        ← migrated from localstack
└── agent-sync branch
    └── skills/
        └── (agent-created/modified skills, auto-synced)

Hermes container filesystem:
├── /opt/data/skills-library/     ← git clone of JasperHG90/skills@main (read-only baseline)
└── /opt/data/skills/             ← git repo tracking agent-sync branch (writable scratchpad)
```

**Data flow:**
1. **Deploy:** prestart `git clone` → `/opt/data/skills-library/` (baseline, read-only)
2. **Runtime:** agent creates/modifies skills in `/opt/data/skills/`
3. **Sync:** cron job `git add -A && git commit && git push origin agent-sync --force` every 6h
4. **Promotion:** user reviews `agent-sync` branch, opens PR to `main`, merges proven skills
5. **Next deploy:** prestart re-clones `main` → new baseline includes promoted skills

---

## Phase 1: Consolidate Baseline Skills into `JasperHG90/skills`

### Task 1.1: Audit IaC-managed skills in localstack

**Objective:** Enumerate all skills currently in `deployments/applications/services/hermes/skills/` to know what needs migrating.

**Files:**
- Read: `deployments/applications/services/hermes/skills/` (all `**/SKILL.md`)

**Step 1:** List all skills in the localstack repo

```bash
# From localstack repo root
find deployments/applications/services/hermes/skills -name SKILL.md | sort
```

Expected: skills in `devops/`, `knowledge/`, `productivity/`, `research/` directories.

**Step 2:** List all skills already in `JasperHG90/skills` repo

```bash
# From skills repo root (clone if needed)
git clone https://github.com/JasperHG90/skills.git /tmp/skills-audit
find /tmp/skills-audit/skills -name SKILL.md | sort
```

Expected: skills in `architecture/`, `development/`, `documentation/`, `learning/`, `ops/`, `tools/` directories.

**Step 3:** Check for name collisions between the two sets

```bash
# Extract relative skill paths from both repos and compare
comm -12 \
  <(find deployments/applications/services/hermes/skills -name SKILL.md | sed 's|.*/skills/||' | sort) \
  <(find /tmp/skills-audit/skills -name SKILL.md | sed 's|.*/skills/||' | sort)
```

Expected: empty (no collisions) or a list of collisions to resolve.

### Task 1.2: Migrate IaC-managed skills into `JasperHG90/skills`

**Objective:** Move all skills from `deployments/applications/services/hermes/skills/` into `JasperHG90/skills/skills/`, preserving directory structure.

**Files:**
- Create: `JasperHG90/skills/skills/devops/**` (migrated from localstack)
- Create: `JasperHG90/skills/skills/knowledge/**` (migrated from localstack)
- Create: `JasperHG90/skills/skills/productivity/**` (migrated from localstack)
- Create: `JasperHG90/skills/skills/research/**` (migrated from localstack)
- Delete: `deployments/applications/services/hermes/skills/` (after migration confirmed)

**Step 1:** Clone `JasperHG90/skills` locally

```bash
git clone https://github.com/JasperHG90/skills.git /tmp/skills-migration
cd /tmp/skills-migration
git checkout -b feat/consolidate-baseline
```

**Step 2:** Copy skill directories from localstack into skills repo

```bash
# From localstack repo root
for dir in devops knowledge productivity research; do
  cp -r deployments/applications/services/hermes/skills/$dir /tmp/skills-migration/skills/$dir
done
```

**Step 3:** Verify all SKILL.md files are valid frontmatter

```bash
cd /tmp/skills-migration
find skills -name SKILL.md -exec sh -c 'head -1 "$1" | grep -q "^---" && echo "OK: $1" || echo "BAD: $1"' _ {} \;
```

Expected: all OK

**Step 4:** Commit and push

```bash
cd /tmp/skills-migration
git add skills/
git commit -m "feat: consolidate IaC-managed skills from localstack repo

Moved devops/, knowledge/, productivity/, research/ skill categories
from localstack Terraform repo into this repo to establish a single
source of truth for Hermes agent skills."
git push origin feat/consolidate-baseline
```

**Step 5:** Open PR and merge

```bash
gh pr create --title "Consolidate IaC-managed skills from localstack" \
  --body "Migrates skills from localstack repo to establish single source of truth."
# After review, merge
gh pr merge --squash
```

**Step 6:** Delete skills directory from localstack repo

```bash
# In localstack repo
git checkout -b chore/remove-iac-skills
rm -rf deployments/applications/services/hermes/skills/
git add -A
git commit -m "chore: remove IaC-managed skills (migrated to JasperHG90/skills)

Skills now live in JasperHG90/skills repo. The TSV template approach
is replaced by git clone at prestart (see hermes.hcl changes)."
git push origin chore/remove-iac-skills
gh pr create --title "Remove IaC-managed skills (migrated to JasperHG90/skills)" \
  --body "Skills have been consolidated into JasperHG90/skills repo."
```

---

## Phase 2: Replace TSV Templating with Git Clone

### Task 2.1: Add git to the Hermes container image

**Objective:** Ensure the Hermes container image has `git` installed so prestart can clone the repo.

**Files:**
- Modify: `deployments/applications/services/hermes/Dockerfile`

**Step 1:** Check if git is already in the image

```bash
# Run the current image and check
podman run --rm ghcr.io/jasperhg90/hermes:0.12.0-memex-v1.0.1 which git
```

Expected: either a path (git exists) or empty (git missing).

**Step 2:** If git is missing, add to Dockerfile

```dockerfile
# Add to existing RUN layer or create a new one
RUN apt-get update && apt-get install -y --no-install-recommends git && rm -rf /var/lib/apt/lists/*
```

**Step 3:** Rebuild and push image

```bash
cd deployments/applications/services/hermes/
# Build and push with the existing tag or a new one
podman build -t ghcr.io/jasperhg90/hermes:0.12.0-memex-v1.0.1 .
podman push ghcr.io/jasperhg90/hermes:0.12.0-memex-v1.0.1
```

**Step 4:** Verify git is available

```bash
podman run --rm ghcr.io/jasperhg90/hermes:0.12.0-memex-v1.0.1 git --version
```

Expected: `git version 2.x.x`

### Task 2.2: Replace TSV template with git clone in prestart

**Objective:** Replace the base64 TSV approach with a `git clone` of `JasperHG90/skills` into `/opt/data/skills-library/`.

**Files:**
- Modify: `deployments/applications/services/hermes.hcl` (prestart `setup.sh` template and `skills-bundle.tsv` template block)
- Modify: `deployments/applications/services.tf` (remove `skills` map from `templatefile` call)

**Step 1:** Remove the `skills` map from `services.tf`

In `deployments/applications/services.tf`, find the `resource "nomad_job" "hermes"` block and remove:

```hcl
      skills = {
        for f in fileset("${path.module}/services/hermes/skills", "**/SKILL.md") :
        trimsuffix(f, "/SKILL.md") => file("${path.module}/services/hermes/skills/${f}")
      }
```

Also remove `soul_md` is kept — only the `skills` map goes.

**Step 2:** Remove the `skills-bundle.tsv` template block from `hermes.hcl`

Find and remove this entire template block:

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

Also remove the volume mount for skills-bundle.tsv:

```hcl
          "local/skills-bundle.tsv:/tmp/hermes/skills-bundle.tsv:ro",
```

**Step 3:** Replace the TSV decode section in `setup.sh` with git clone

Find this block in the `setup.sh` template inside `hermes.hcl`:

```sh
# IaC-managed read-only skill library. Refreshed from scratch every deploy
# so removed skills are pruned. Wired into config.yaml via
# skills.external_dirs; the agent cannot modify files here (enforced by
# Hermes: skill_manage refuses writes outside HERMES_HOME/skills).
# Writable agent skills live in /opt/data/skills/ and are never touched here.
if [ -f /tmp/hermes/skills-bundle.tsv ]; then
  rm -rf /opt/data/skills-library
  mkdir -p /opt/data/skills-library
  while IFS='|' read -r path_b64 body_b64; do
    [ -n "$path_b64" ] || continue
    skill_path=$(printf '%s' "$path_b64" | base64 -d)
    mkdir -p "/opt/data/skills-library/$skill_path"
    printf '%s' "$body_b64" | base64 -d > "/opt/data/skills-library/$skill_path/SKILL.md"
  done < /tmp/hermes/skills-bundle.tsv
fi
```

Replace with:

```sh
# ── Baseline skill library: git clone of JasperHG90/skills ──
# Single source of truth. Refreshed from scratch every deploy so removed
# skills are pruned. Read-only by convention; Hermes enforces this via
# skill_manage refusing writes outside HERMES_HOME/skills.
# Writable agent skills live in /opt/data/skills/ and are never touched here.
SKILLS_REF="${skills_repo_ref}"
rm -rf /opt/data/skills-library
if git clone --depth 1 --branch "$SKILLS_REF" \
     "https://${github_token}@github.com/JasperHG90/skills.git" \
     /opt/data/skills-library 2>/dev/null; then
  rm -rf /opt/data/skills-library/.git
  echo "hermes: baseline skills synced @ $SKILLS_REF"
else
  echo "hermes: WARN failed to clone JasperHG90/skills@$SKILLS_REF (continuing)"
  mkdir -p /opt/data/skills-library
fi
```

**Step 4:** Replace the external tarball pull with a no-op (it's now redundant)

Find this block in `setup.sh`:

```sh
# External read-only library: JasperHG90/skills (public, refresh per deploy).
EXT_JG_REF="${external_skills_jasperhg90_ref}"
rm -rf /opt/data/skills-library-jasperhg90
mkdir -p /opt/data/skills-library-jasperhg90
if curl -fsSL "https://github.com/JasperHG90/skills/archive/$EXT_JG_REF.tar.gz" \
   | tar xz -C /opt/data/skills-library-jasperhg90 --strip-components=1 2>/dev/null; then
  echo "hermes: external skills jasperhg90@$EXT_JG_REF synced"
else
  echo "hermes: WARN failed to fetch external skills jasperhg90@$EXT_JG_REF (continuing)"
fi
```

Replace with:

```sh
# External tarball pull removed — baseline clone above now covers JasperHG90/skills.
# Clean up stale directory from previous deploys.
rm -rf /opt/data/skills-library-jasperhg90
```

**Step 5:** Update `config.yaml` template to remove the jasperhg90 external_dir

Find in `hermes.hcl` config.yaml template:

```yaml
skills:
  external_dirs:
    - /opt/data/skills-library
    - /opt/data/skills-library-jasperhg90/skills
```

Replace with:

```yaml
skills:
  external_dirs:
    - /opt/data/skills-library
```

**Step 6:** Update `services.tf` templatefile variables

In `deployments/applications/services.tf`, replace:

```hcl
      external_skills_jasperhg90_ref = "main"
```

with:

```hcl
      skills_repo_ref = "main"
      github_token    = "<from-vault-or-env>"
```

Note: The GitHub token is already available as `GITHUB_PERSONAL_ACCESS_TOKEN` from the Vault secret template. For the prestart task, we need to pass it as an env var or template it in. The cleanest approach is to add it to the prestart task's env block.

**Step 7:** Add `GITHUB_PERSONAL_ACCESS_TOKEN` to the prestart task

In `hermes.hcl`, add to the prestart `config` task's `env` block (or as a template):

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

**Step 8:** Update the prune script in start-hermes.sh

The prune script in the hermes task currently prunes bundled skills that collide with `/opt/data/skills-library`. Since the directory structure is the same (skills are now at `/opt/data/skills-library/skills/` but `external_dirs` points to `/opt/data/skills-library`), verify the prune logic still works.

The current prune script finds SKILL.md under `/opt/data/skills-library/` and strips the prefix. If the repo structure has `skills/` as a subdirectory, the relative paths will be `skills/devops/my-skill/SKILL.md` instead of `devops/my-skill/SKILL.md`. We need to account for this.

Update the prune script:

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

**Files:**
- Modify: `deployments/applications/services/hermes.hcl` (setup.sh prestart template)

**Step 1:** Add git init logic to `setup.sh` in the prestart template

After the baseline clone and before the final ownership pass, add:

```sh
# ── Initialize writable scratchpad as git repo for agent-sync ──
# /opt/data/skills/ is the writable directory where Hermes creates/modifies
# skills. We init it as a git repo pointing at JasperHG90/skills so the
# auto-sync cron can push changes to the agent-sync branch.
SKILLS_REPO="https://${github_token}@github.com/JasperHG90/skills.git"
cd /opt/data/skills
if [ ! -d .git ]; then
  git init
  git remote add origin "$SKILLS_REPO"
  git fetch origin main --depth 1
  git checkout -b agent-sync
  # Add all existing (bundled) skills as the initial commit
  git add -A
  git commit -m "agent-sync: initial state (bundled skills)" --allow-empty
else
  # Repo already exists from previous deploy — just update the remote
  git remote set-url origin "$SKILLS_REPO" 2>/dev/null || git remote add origin "$SKILLS_REPO"
fi
```

**Step 2:** Add a `.gitignore` to exclude non-skill files

```sh
# Create .gitignore so we don't sync logs, caches, etc.
cat > /opt/data/skills/.gitignore <<'GITIGNORE'
__pycache__/
*.pyc
.DS_Store
*.log
GITIGNORE
```

**Step 3:** Ensure git user is configured for commits

```sh
git -C /opt/data/skills config user.name "Hermes Agent"
git -C /opt/data/skills config user.email "hermes@localstack"
```

### Task 2.4: Remove the `skills` volume mount line from prestart

**Objective:** Clean up the volume mount for `skills-bundle.tsv` since it no longer exists.

**Files:**
- Modify: `deployments/applications/services/hermes.hcl`

**Step 1:** In the prestart task's `config.volumes`, remove this line:

```hcl
          "local/skills-bundle.tsv:/tmp/hermes/skills-bundle.tsv:ro",
```

**Step 2:** Verify the remaining volumes are correct:

```hcl
        volumes = [
          "local/hermes.env:/tmp/hermes/hermes.env",
          "local/config.yaml:/tmp/hermes/config.yaml",
          "local/SOUL.md:/tmp/hermes/SOUL.md",
          "local/setup.sh:/tmp/setup.sh",
          "local/model-providers:/tmp/hermes/model-providers:ro",
        ]
```

---

## Phase 3: Auto-Sync Cron Job

### Task 3.1: Create the sync script

**Objective:** Create a shell script that commits and pushes `/opt/data/skills/` changes to the `agent-sync` branch.

**Files:**
- Create: `deployments/applications/services/hermes/scripts/sync-skills.sh`

**Step 1:** Create the sync script

```bash
#!/bin/sh
# sync-skills.sh — Auto-sync Hermes writable skills to agent-sync branch.
#
# Run via Hermes cron. Commits all changes in /opt/data/skills/ and force-pushes
# to the agent-sync branch on JasperHG90/skills. Silent on success when there
# are no changes (exit 0, no output) to avoid spamming the cron delivery channel.

set -e

SKILLS_DIR="/opt/data/skills"
cd "$SKILLS_DIR"

# Ensure we're on agent-sync
git checkout agent-sync 2>/dev/null || git checkout -b agent-sync

# Stage everything
git add -A

# Check if there are changes to commit
if git diff --cached --quiet; then
  # No changes — silent exit (cron watchdog pattern)
  exit 0
fi

# Commit and push
TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
git commit -m "agent-sync: $TIMESTAMP"
git push origin agent-sync --force

echo "skills-sync: pushed $TIMESTAMP"
```

**Step 2:** Make it executable

```bash
chmod +x deployments/applications/services/hermes/scripts/sync-skills.sh
```

### Task 3.2: Register the cron job

**Objective:** Register the auto-sync as a Hermes cron job via `register-cron.sh`.

**Files:**
- Modify: `deployments/applications/services/hermes/register-cron.sh`

**Step 1:** Add the sync cron registration to `register-cron.sh`

Append a new `send_cron` call:

```sh
send_cron '/cron add "0 */6 * * *" "Run the skills auto-sync script at /opt/data/scripts/sync-skills.sh to commit and push agent-created/modified skills to the agent-sync branch on JasperHG90/skills. The script is silent when there are no changes." --name "skills-auto-sync"'
```

**Step 2:** Add the script to the container's persistent volume

The script needs to be available inside the container. Two options:
- (a) Bake it into the Docker image (preferred for stability)
- (b) Copy it to `/opt/data/scripts/` at prestart

Option (b) is more flexible. Add to `setup.sh`:

```sh
mkdir -p /opt/data/scripts
cp /tmp/hermes/sync-skills.sh /opt/data/scripts/sync-skills.sh
chmod +x /opt/data/scripts/sync-skills.sh
```

And add a template + volume mount for it in the prestart task:

```hcl
      template {
        data = <<-EOT
#!/bin/sh
# (script content here — same as sync-skills.sh above)
EOT
        destination = "local/sync-skills.sh"
        perms       = "0755"
      }
```

Add to volumes:

```hcl
          "local/sync-skills.sh:/tmp/hermes/sync-skills.sh:ro",
```

### Task 3.3: Handle the Hermes cron vs system cron decision

**Objective:** Decide whether the sync runs as a Hermes cron job (agent-driven) or as a Nomad periodic task (system-driven).

**Decision: Hermes cron job.**

Rationale:
- The Hermes cron system (`/cron add`) is already wired up via `register-cron.sh`
- The script runs inside the Hermes container with access to `/opt/data/skills/` and `GITHUB_PERSONAL_ACCESS_TOKEN`
- A Nomad periodic task would require a separate task block and volume mount
- The Hermes cron approach keeps all cron jobs in one place

However, there's a subtlety: the Hermes cron runs `sh /opt/data/scripts/sync-skills.sh` via the terminal toolset, which means it runs as the `hermes` user inside the container. The `GITHUB_PERSONAL_ACCESS_TOKEN` env var is already available to the hermes process.

**Pitfall:** The git remote URL contains the token. If the cron output is delivered to Telegram, the token could leak in error messages. Mitigation: redirect stderr to `/dev/null` in the push command, or use a git credential helper instead of embedding the token in the URL.

**Step 1:** Update the sync script to use a credential helper instead of embedding the token

```sh
# Instead of embedding token in URL, use credential helper
git -C "$SKILLS_DIR" config credential.helper \
  '!f() { echo "username=x-access-token"; echo "password=$GITHUB_PERSONAL_ACCESS_TOKEN"; }; f'
```

And update the remote URL to use HTTPS without the token:

```sh
git remote set-url origin https://github.com/JasperHG90/skills.git
```

This way, even if `git push` fails, the error output won't contain the token.

---

## Phase 4: Promotion Skill

### Task 4.1: Create the skill-promotion skill

**Objective:** Create a Hermes skill that guides the promotion workflow — reviewing agent-sync changes and opening PRs to merge proven skills into main.

**Files:**
- Create: `JasperHG90/skills/skills/devops/skill-promotion/SKILL.md`

**Step 1:** Create the skill file

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

When the user asks to "promote skills", "review agent changes", or "merge agent-sync". Run after the auto-sync cron has pushed agent-created/modified skills to the `agent-sync` branch.

## Workflow

1. **Fetch the diff**: Compare `agent-sync` against `main` on `JasperHG90/skills`:
   ```bash
   git clone https://github.com/JasperHG90/skills.git /tmp/skills-promo
   cd /tmp/skills-promo
   git fetch origin agent-sync
   git diff main..origin/agent-sync --stat
   ```

2. **Review each changed skill**: For each modified or new SKILL.md:
   - Read the full content
   - Verify frontmatter is valid (name, description, version, author)
   - Check the skill follows the SKILL.md format (overview, when-to-use, steps)
   - Flag any issues (incomplete steps, hardcoded paths, sensitive data)

3. **Present findings to user**: List all changes with a recommendation:
   - ✅ Promote: well-formed, useful skill
   - ⚠️ Needs work: valid but incomplete or has issues
   - ❌ Reject: not useful or contains problems

4. **Create PR for approved skills**:
   ```bash
   git checkout -b promote/$(date +%Y-%m-%d)
   git merge origin/agent-sync
   # Resolve any conflicts, keeping only approved skills
   git push origin promote/$(date +%Y-%m-%d)
   gh pr create --title "Promote agent-created skills" \
     --body "Skills promoted from agent-sync branch."
   ```

5. **After merge**: The next deploy will `git clone` the updated `main` branch, making the promoted skills available as baseline.

## Pitfalls

- **Conflict resolution**: The `agent-sync` branch may have diverged significantly from `main` if many bundled skills were committed. Use `git merge` with care — consider cherry-picking individual skills instead of merging wholesale.
- **Bundled skill noise**: The `agent-sync` branch contains ALL files in `/opt/data/skills/`, including bundled skills that ship with the image. These are noise — focus only on new or modified SKILL.md files.
- **Force push**: The auto-sync uses `--force` on `agent-sync`. This means the branch history is linear and squashed. Promotion should cherry-pick or copy specific skills, not merge the branch.
```

**Step 2:** Commit to `JasperHG90/skills` repo

```bash
cd /tmp/skills-migration  # or clone fresh
git checkout main
git pull
mkdir -p skills/devops/skill-promotion
# Save the SKILL.md content above
git add skills/devops/skill-promotion/
git commit -m "feat: add skill-promotion skill for agent-sync promotion workflow"
git push origin main
```

---

## Phase 5: Deploy and Verify

### Task 5.1: Deploy and verify prestart clone

**Objective:** Run `terraform apply` and verify the prestart git clone works correctly.

**Step 1:** Apply the Terraform changes

```bash
cd deployments/applications
terraform plan -var-file=vars/prod.tfvars -out skills.plan
terraform apply skills.plan
```

**Step 2:** Verify the prestart task completed

```bash
# Check Nomad allocation
nomad alloc logs -task config <alloc_id> | grep "baseline skills synced"
```

Expected: `hermes: baseline skills synced @ main`

**Step 3:** Verify skills-library is populated

```bash
nomad alloc exec -task hermes <alloc_id> ls /opt/data/skills-library/skills/
```

Expected: all skill category directories present.

**Step 4:** Verify skills are loaded by Hermes

```bash
# Send a message to Hermes asking for skills list
curl -s -X POST http://127.0.0.1:8642/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"default","messages":[{"role":"user","content":"List all available skills"}],"max_tokens":500}'
```

Expected: all skills from both the former IaC set and the public set.

### Task 5.2: Verify auto-sync cron

**Objective:** Confirm the auto-sync cron job is registered and functional.

**Step 1:** Check cron registration

```bash
# Via gateway API
curl -s -X POST http://127.0.0.1:8642/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"default","messages":[{"role":"user","content":"/cron list"}],"max_tokens":500}'
```

Expected: `skills-auto-sync` appears in the list with schedule `0 */6 * * *`.

**Step 2:** Manually trigger the sync and verify

```bash
nomad alloc exec -task hermes <alloc_id> sh /opt/data/scripts/sync-skills.sh
```

Expected: either silent (no changes) or `skills-sync: pushed <timestamp>`.

**Step 3:** Verify the agent-sync branch on GitHub

```bash
gh api repos/JasperHG90/skills/branches/agent-sync --jq '.name'
```

Expected: `agent-sync`

### Task 5.3: Test the full round-trip

**Objective:** Create a skill as the agent, verify it syncs, promote it, and verify it appears in the next deploy baseline.

**Step 1:** Create a test skill

```bash
nomad alloc exec -task hermes <alloc_id> mkdir -p /opt/data/skills/test-category/test-skill
nomad alloc exec -task hermes <alloc_id> sh -c 'cat > /opt/data/skills/test-category/test-skill/SKILL.md << EOF
---
name: test-skill
description: "Test skill for round-trip verification"
version: 1.0.0
---
# Test Skill
This is a test.
EOF'
```

**Step 2:** Trigger sync manually

```bash
nomad alloc exec -task hermes <alloc_id> sh /opt/data/scripts/sync-skills.sh
```

**Step 3:** Verify on GitHub

```bash
gh api repos/JasperHG90/skills/contents/skills/test-category/test-skill/SKILL.md?ref=agent-sync
```

Expected: file exists.

**Step 4:** Promote via PR

```bash
gh pr create --repo JasperHG90/skills \
  --head agent-sync --base main \
  --title "Promote test-skill" \
  --body "Test skill for round-trip verification"
gh pr merge --squash
```

**Step 5:** Redeploy and verify

```bash
terraform apply -var-file=vars/prod.tfvars
# After deploy, check the skill is in baseline
nomad alloc exec -task hermes <alloc_id> ls /opt/data/skills-library/skills/test-category/test-skill/SKILL.md
```

Expected: file exists in baseline.

**Step 6:** Clean up test skill

```bash
# Remove from repo
gh api -X DELETE repos/JasperHG90/skills/contents/skills/test-category/test-skill/SKILL.md \
  --field message="chore: remove test skill" \
  --field sha="$(gh api repos/JasperHG90/skills/contents/skills/test-category/test-skill/SKILL.md --jq '.sha')"
```

---

## Risk Assessment

| Risk | Impact | Mitigation |
|---|---|---|
| GitHub token leaks in cron output | High — credential exposure | Use git credential helper, not URL-embedded token. Redirect stderr to /dev/null. |
| `agent-sync` branch diverges wildly from `main` | Medium — noisy promotion | Promotion uses cherry-pick, not merge. The skill guides selective promotion. |
| Bundled skills create noise in agent-sync | Low — cosmetic | `.gitignore` excludes known non-skill files. PR review filters noise. |
| Prestart clone fails (network issue) | Medium — no baseline skills | Non-fatal: `setup.sh` continues with empty library. Hermes still has bundled skills. |
| Git not available in container | High — prestart fails | Task 2.1 ensures git is installed. Verified before deploy. |
| Skills directory structure mismatch | Medium — prune script breaks | Task 2.2 Step 8 updates prune path to account for `skills/` subdir. |

## Migration Notes

- **No downtime required**: The prestart task runs before the main hermes task. As long as the clone succeeds, the transition is seamless.
- **Rollback**: If issues arise, revert the `hermes.hcl` and `services.tf` changes and redeploy. The old TSV approach still works if the skills directory is restored.
- **Vault**: No new secrets needed — `GITHUB_PERSONAL_ACCESS_TOKEN` is already in Vault.
- **Image rebuild**: Required only if git is not already in the container image (Task 2.1).