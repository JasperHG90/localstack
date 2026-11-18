#!/usr/bin/env bash
# Does APM 0.33.0 (as the justfile's kmctl-install / kmctl-install-frozen
# recipes call it) leave an unlisted .claude/skills/onboard-repo/ alone?
# Each of apm install and apm install --frozen runs in its own fresh copy of
# the committed tree (no apm_modules/, as on a clone), followed by apm prune.
# A second install in the same tree trips an APM case-duplicate error on
# apm_modules/JasperHG90 vs jasperhg90, so steps are not chained.
# Exits 0 only if every apm step succeeds and the sentinel survives unchanged.
set -uo pipefail
APM="uvx --from apm-cli==0.33.0 apm"
src=$(pwd)
fail=0
for first in "install" "install --frozen"; do
  work=$(mktemp -d)
  cp -a "$src/." "$work/"
  cd "$work"; rm -rf apm_modules
  mkdir -p .claude/skills/onboard-repo .agents/skills/onboard-repo
  s=.claude/skills/onboard-repo/SKILL.md
  printf -- '---\nname: onboard-repo\ndescription: sentinel\n---\nSENTINEL-7f3a onboard-repo\n' > $s
  cp $s .agents/skills/onboard-repo/SKILL.md
  want=$(sha256sum $s | cut -d' ' -f1)
  for step in "$first" "prune"; do
    echo "=== [$first tree] apm $step"
    $APM $step </dev/null 2>&1 | grep -E '^\[[*x+>]\]|Installed|orphan|Removed|Deleted'
    rc=${PIPESTATUS[0]}; echo "apm $step exit: $rc"; [ "$rc" = 0 ] || fail=1
    for f in .claude/skills/onboard-repo/SKILL.md .agents/skills/onboard-repo/SKILL.md; do
      if [ -f "$f" ] && [ "$(sha256sum "$f" | cut -d' ' -f1)" = "$want" ]; then
        echo "  $f intact"
      else
        echo "  $f MISSING OR CHANGED"; fail=1
      fi
    done
    echo "  dirs in .claude/skills: $(ls .claude/skills | wc -l); tracked skill files changed: $(git status --porcelain -- .claude/skills .agents/skills | grep -vc onboard-repo)"
  done
  cd "$src"
done
exit $fail
