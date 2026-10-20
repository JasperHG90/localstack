#!/usr/bin/env bash
# Spike for aim-to-apm risk 1: can APM 0.33.0 install single files and
# folders from repos without apm.yml, pinned to commits, and does
# `apm install --frozen` reproduce them byte for byte?
# Exit 0 only if all four install pinned and frozen reproduces them.
set -u
S=/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/spike-apm1
export HOME=$S/home UV_CACHE_DIR=$S/uvcache XDG_CACHE_HOME=$S/xdg/cache \
  XDG_CONFIG_HOME=$S/xdg/config XDG_DATA_HOME=$S/xdg/data
W=$(mktemp -d "$S/run.XXXX")
apm() { uvx --from apm-cli==0.33.0 apm "$@"; }
FAIL=0

SK=https://github.com/jasperhg90/skills
NM=https://github.com/athola/claude-night-market
# name|repo|path|sha|expected destinations (space separated, relative to project)
DEPS=(
  "rule-plain-language|$SK|rules/plain-language.md|d0f02626629875a5dd57ddbc611ba129cdb4092b|.claude/rules/plain-language.md"
  "rule-slop-scan|$NM|.claude/rules/slop-scan-for-docs.md|b226e39776d69a4b16faebd78d5d2973679df198|.claude/rules/slop-scan-for-docs.md"
  "skill-generate-art|$SK|skills/tools/generate-art|516c105a9d8260c80a9d1fd8cb4004fe22a74225|.claude/skills/generate-art .agents/skills/generate-art"
  "agent-feature-planner|$SK|agents/feature-planner.md|7e0ee1b4260c1bbe9b4c917ccc6a6aa5e169609c|.claude/agents/feature-planner.md .opencode/agents/feature-planner.md"
)

manifest() { # $1 dir, rest: dep lines
  local d=$1; shift
  { echo "name: spike"; echo "version: 0.0.1"; echo "targets: [claude, opencode]"
    echo "dependencies:"; echo "  apm:"
    for l in "$@"; do IFS='|' read -r _ repo path sha _ <<<"$l"
      printf '    - git: %s\n      path: %s\n      ref: %s\n' "$repo" "$path" "$sha"; done
  } > "$d/apm.yml"
}

upstream() { # repo sha -> clone dir
  local dir="$W/up/$(basename "$1")-$2"
  if [ ! -d "$dir" ]; then
    git clone -q --filter=blob:none --no-checkout "$1" "$dir" && git -C "$dir" checkout -q "$2"
  fi
  echo "$dir"
}

same_bytes() { # src dst ; file or dir, byte compare
  if [ -d "$1" ]; then diff -r -q "$1" "$2"; else cmp "$1" "$2"; fi
}

echo "=== A. all four in one apm.yml (jasperhg90/skills at three commits) ==="
mkdir -p "$W/all"; manifest "$W/all" "${DEPS[@]}"; cat "$W/all/apm.yml"
(cd "$W/all" && apm install >"$W/all.log" 2>&1); echo "exit=$?"; tail -25 "$W/all.log"
[ -f "$W/all/apm.lock.yaml" ] && echo "lockfile written" || { echo "no lockfile written"; FAIL=1; }

echo; echo "=== B. each dependency alone: install, byte-compare, delete, --frozen, compare ==="
for l in "${DEPS[@]}"; do
  IFS='|' read -r name repo path sha dests <<<"$l"
  d="$W/$name"; mkdir -p "$d"; manifest "$d" "$l"
  echo "--- $name ($path @ ${sha:0:12})"
  (cd "$d" && apm install >"$W/$name.install.log" 2>&1); rc=$?
  echo "install exit=$rc"; grep -E 'Failed|failed|error|Error' "$W/$name.install.log" | head -3
  echo "deployed files:"; (cd "$d" && find . -type f -not -path './apm_modules/*' -not -name 'apm.yml' -not -name 'apm.lock.yaml' | sort | sed 's/^/  /')
  [ $rc -eq 0 ] || { FAIL=1; continue; }
  grep -n -E "resolved_commit|$sha" "$d/apm.lock.yaml" | head -3
  grep -q "$sha" "$d/apm.lock.yaml" || { echo "lock does not record the pin"; FAIL=1; }
  up=$(upstream "$repo" "$sha")
  for dst in $dests; do
    if [ ! -e "$d/$dst" ]; then echo "MISSING $dst"; FAIL=1; continue; fi
    same_bytes "$up/$path" "$d/$dst" && echo "identical to upstream: $dst" || { echo "DIFFERS from upstream: $dst"; FAIL=1; }
  done
  (cd "$d" && rm -rf .claude .agents .opencode apm_modules && apm install --frozen >"$W/$name.frozen.log" 2>&1); frc=$?
  echo "frozen exit=$frc"; [ $frc -eq 0 ] || { tail -5 "$W/$name.frozen.log"; FAIL=1; }
  for dst in $dests; do
    [ -e "$d/$dst" ] && same_bytes "$up/$path" "$d/$dst" && echo "frozen identical: $dst" || { echo "frozen MISSING/DIFFERS: $dst"; FAIL=1; }
  done
done

echo; echo "=== C. one repo at two commits (two skill folders from jasperhg90/skills) ==="
mkdir -p "$W/twocommits"
manifest "$W/twocommits" \
  "x|$SK|skills/tools/generate-art|516c105a9d8260c80a9d1fd8cb4004fe22a74225|" \
  "y|$SK|skills/architecture/manifesto|7e0ee1b4260c1bbe9b4c917ccc6a6aa5e169609c|"
(cd "$W/twocommits" && apm install >"$W/two.log" 2>&1); echo "exit=$?"; tail -3 "$W/two.log"
grep -n -E "516c105a9d82|7e0ee1b4260c" "$W/twocommits/apm.lock.yaml" 2>/dev/null
ls "$W/twocommits/.claude/skills" 2>/dev/null

echo; echo "=== D. string shorthand for a plain .md file ==="
mkdir -p "$W/short"
printf 'name: s\nversion: 0.0.1\ntargets: [claude]\ndependencies:\n  apm:\n    - jasperhg90/skills/rules/plain-language.md#d0f02626629875a5dd57ddbc611ba129cdb4092b\n' > "$W/short/apm.yml"
(cd "$W/short" && apm install 2>&1 | grep -v '^\s*$' | tail -6)

echo; echo "RESULT FAIL=$FAIL"
exit $FAIL
