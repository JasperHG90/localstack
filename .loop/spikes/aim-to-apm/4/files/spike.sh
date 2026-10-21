#!/usr/bin/env bash
# Spike aim-to-apm risk 2: does `just check-install` pass on a clean clone once
# step 8 widens the pre-commit exclude and the tracked APM files equal what
# `apm install --frozen` + `kmctl plugin patch` write, with `prek run
# --all-files` run in between? Exit 0 only when (b) ends with a clean tree.
set -u
S=/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/spike-apm5
mkdir -p "$S/home" "$S/xdg" "$S/uvcache" "$S/prek"
export HOME=$S/home UV_CACHE_DIR=$S/uvcache XDG_CACHE_HOME=$S/xdg/cache \
  XDG_CONFIG_HOME=$S/xdg/config XDG_DATA_HOME=$S/xdg/data PREK_HOME=$S/prek \
  GIT_CONFIG_GLOBAL=/dev/null
R=$(mktemp -d "$S/clone.XXXX")
git clone -q /home/vscode/workspace "$R"; cd "$R"
echo "=== clone HEAD $(git rev-parse --short HEAD)"

echo "=== (a) just check-install on clean clone"
just check-install > a.log 2>&1; echo "check-install exit=$?"; tail -40 a.log
echo "--- (a) changed files:"; git status --porcelain
echo "--- (a) diff stat:"; git diff --stat | tail -40
echo "--- (a) diff (first 120 lines):"; git diff | head -120

echo "=== (b) apply step-8 exclude, commit what install-frozen writes"
sed -i "1s#.*#exclude: '^(\\\\.(claude|loop|agents|opencode)/|opencode\\\\.json\$|\\\\.mcp\\\\.json\$|apm\\\\.lock\\\\.yaml\$)'#" .pre-commit-config.yaml
head -1 .pre-commit-config.yaml
rm -f a.log
git add -A && git -c user.name=spike -c user.email=spike@x commit -qm "spike: step 8 + frozen install output" && echo committed
git show --stat HEAD | tail -40

echo "=== (b) prek run --all-files"
prek run --all-files > b1.log 2>&1; echo "prek exit=$?"; cat b1.log | tail -60
echo "--- after prek:"; git status --porcelain -- . ':!b1.log'
git diff --stat | tail -20

echo "=== (b) just check-install again"
rm -f b1.log
just check-install > b2.log 2>&1; rc=$?; echo "check-install exit=$rc"; tail -20 b2.log; rm -f b2.log
echo "--- final git status --porcelain:"; out=$(git status --porcelain); printf '%s\n' "$out"
git diff | head -80
[ -z "$out" ] && { echo "RESULT clean"; exit 0; }
echo "RESULT dirty"; exit 1
