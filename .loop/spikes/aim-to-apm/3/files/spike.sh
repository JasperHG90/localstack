#!/usr/bin/env bash
# Spike aim-to-apm risk 1 (revised): does APM 0.33.0 deploy .instructions.md
# rules and .agent.md agents from jasperhg90/skills@1c3dd31 where Claude Code
# loads them (.claude/rules/*.md, .claude/agents/*.md, front matter usable),
# pinned in apm.lock.yaml and restored byte for byte by `apm install --frozen`?
# OpenCode placement is reported, not gated.
set -u
S=/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/spike-apm4
export HOME=$S/home UV_CACHE_DIR=$S/uvcache XDG_CACHE_HOME=$S/xdg/cache \
  XDG_CONFIG_HOME=$S/xdg/config XDG_DATA_HOME=$S/xdg/data
apm() { uvx --from apm-cli==0.33.0 apm "$@"; }
C=1c3dd312537694aeea9710c0cc545d0e07d5422c
A=516c105a9d8260c80a9d1fd8cb4004fe22a74225
UP=$(mktemp -d "$S/up.XXXX"); git clone -q https://github.com/jasperhg90/skills "$UP"
P=$(mktemp -d "$S/proj.XXXX"); cd "$P"
RULES="plain-language adversarial-reviews docs-layout"
AGENTS="feature-planner adversarial-reviewer"
FAIL=0
{ echo "name: spike"; echo "version: 0.0.1"; echo "targets: [claude, opencode]"
  echo "dependencies:"; echo "  apm:"
  for r in $RULES; do echo "    - jasperhg90/skills/rules/$r.instructions.md#$C"; done
  for a in $AGENTS; do echo "    - jasperhg90/skills/agents/$a.agent.md#$C"; done
  echo "    - jasperhg90/skills/skills/tools/generate-art#$A"
} > apm.yml
echo "=== apm.yml"; cat apm.yml
apm install > install.log 2>&1; rc=$?; echo "=== install exit=$rc"; grep -E '\[!\]|rror|integrated|Installed|opencode' install.log
[ $rc -eq 0 ] || exit 1
echo "=== deployed files"; find . -type f -not -path './apm_modules/*' -not -name '*.log' | sort

body() { awk 'NR==1&&/^---$/{f=1;next} f&&/^---$/{f=0;next} !f' "$1" | sed '/./,$!d'; }
fm() { awk 'NR==1&&/^---$/{f=1;print;next} f{print} f&&/^---$/{exit}' "$1"; }

echo "=== rules (claude): body must equal upstream body; front matter shown"
for r in $RULES; do
  f=.claude/rules/$r.md; u=$(mktemp); git -C "$UP" show "$C:rules/$r.instructions.md" > "$u"
  [ -f "$f" ] || { echo "MISSING $f"; FAIL=1; continue; }
  echo "--- $r upstream front matter:"; fm "$u"
  echo "--- $r deployed front matter:"; fm "$f"; echo "(end)"
  diff <(body "$u") <(body "$f") >/dev/null && echo "body identical: $f" || { echo "BODY DIFFERS: $f"; diff <(body "$u") <(body "$f") | head; FAIL=1; }
done

echo "=== agents: claude copy must be byte-identical and carry name/description/tools"
for a in $AGENTS; do
  u=$(mktemp); git -C "$UP" show "$C:agents/$a.agent.md" > "$u"
  for t in claude opencode; do f=.$t/agents/$a.md
    if [ ! -f "$f" ]; then echo "MISSING $f"; [ $t = claude ] && FAIL=1; continue; fi
    cmp -s "$u" "$f" && echo "byte-identical: $f" || { echo "DIFFERS: $f"; diff "$u" "$f" | head; [ $t = claude ] && FAIL=1; }
  done
  for k in name description tools model color; do printf '  %s: %s\n' "$k" "$(fm .claude/agents/$a.md | grep -m1 "^$k:")"; done
  for k in name description; do fm .claude/agents/$a.md | grep -q "^$k:" || { echo "no $k in claude agent"; FAIL=1; }; done
done

echo "=== opencode rules (informational)"; ls .opencode 2>/dev/null; ls AGENTS.md 2>/dev/null || echo "no AGENTS.md written (apm says run 'apm compile')"

echo "=== lockfile pins"
for n in $RULES $AGENTS generate-art; do
  pin=$(awk -v n="$n" '/^- repo_url/{blk=""} {blk=blk"\n"$0} /resolved_commit/{c=$2} /virtual_path:/ && index($0,n){print c}' apm.lock.yaml | head -1)
  echo "  $n -> ${pin:-NONE}"; [ -n "$pin" ] || FAIL=1
done

echo "=== frozen: delete deployed files, apm install --frozen, compare sha256"
find .claude .opencode .agents -type f | sort | xargs sha256sum > before.sha
rm -rf .claude .opencode .agents apm_modules
apm install --frozen > frozen.log 2>&1; frc=$?; echo "frozen exit=$frc"; [ $frc -eq 0 ] || { tail -5 frozen.log; FAIL=1; }
find .claude .opencode .agents -type f 2>/dev/null | sort | xargs sha256sum > after.sha
diff before.sha after.sha && echo "frozen restored $(wc -l < before.sha) files byte for byte" || FAIL=1

echo "RESULT FAIL=$FAIL"; exit $FAIL
