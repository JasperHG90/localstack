#!/usr/bin/env bash
# Does APM 0.33.0 (as the justfile's kmctl-install / kmctl-install-frozen
# recipes call it) leave an unlisted .claude/skills/onboard-repo/ alone?
# Runs in a copy of the committed tree; exits 0 only if the sentinel survives
# apm install, apm install --frozen and apm prune unchanged.
set -uo pipefail
APM="uvx --from apm-cli==0.33.0 apm"
src=$(pwd)
work=$(mktemp -d)
cp -a "$src/." "$work/"
cd "$work"
rm -rf apm_modules
mkdir -p .claude/skills/onboard-repo .agents/skills/onboard-repo
s=.claude/skills/onboard-repo/SKILL.md
printf -- '---\nname: onboard-repo\ndescription: sentinel\n---\nSENTINEL-7f3a onboard-repo\n' > $s
cp $s .agents/skills/onboard-repo/SKILL.md
want=$(sha256sum $s | cut -d' ' -f1)
fail=0
check() {
  for f in .claude/skills/onboard-repo/SKILL.md .agents/skills/onboard-repo/SKILL.md; do
    if [ -f "$f" ] && [ "$(sha256sum "$f" | cut -d' ' -f1)" = "$want" ]; then
      echo "AFTER $1: $f intact"
    else
      echo "AFTER $1: $f MISSING OR CHANGED"; fail=1
    fi
  done
  echo "AFTER $1: skills in .claude/skills: $(ls .claude/skills | wc -l)"
}
for step in "install --frozen" "install" "prune"; do
  echo "=== apm $step"
  $APM $step </dev/null 2>&1 | tail -25
  rc=${PIPESTATUS[0]}; echo "apm $step exit: $rc"; [ "$rc" = 0 ] || fail=1
  check "apm $step"
done
echo "--- git status of .claude/skills and .agents/skills after all steps"
git status --porcelain -- .claude/skills .agents/skills apm.lock.yaml | head -20
exit $fail
