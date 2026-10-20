#!/usr/bin/env bash
# Does APM 0.33.0 install caveman (pinned e2c09c9) as an enabled Claude Code plugin?
# Exit 0 only if .claude/settings.json gets an enabledPlugins entry for caveman
# backed by a marketplace, like aim's install.
set -u
S=/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/spike-apm3
W=$(mktemp -d "$S/run.XXXX")
export HOME=$W/home XDG_CACHE_HOME=$W/home/.cache XDG_CONFIG_HOME=$W/home/.config \
  XDG_DATA_HOME=$W/home/.local/share UV_CACHE_DIR=$S/uvcache
mkdir -p "$HOME" "$W/proj/.claude"
cd "$W/proj" && git init -q .
cat > apm.yml <<'YML'
name: spike
version: 0.0.1
targets: [claude]
dependencies:
  apm:
    - juliusbrussee/caveman#e2c09c9a7e66d6bb30cadb5f955bd8a36b0e8d9a
YML
echo '{}' > .claude/settings.json
uvx --from apm-cli==0.33.0 apm install --target claude -v 2>&1 | tail -60
echo "== apm exit: ${PIPESTATUS[0]}"
echo "== files written (excluding apm_modules, .git, home):"
find . -path ./apm_modules -prune -o -path ./.git -prune -o -type f -print | sort
echo "== .claude/settings.json:"; cat .claude/settings.json
echo "== apm.lock.yaml:"; cat apm.lock.yaml 2>/dev/null | head -40
echo "== caveman source plugin layout (apm_modules):"
find apm_modules -maxdepth 4 \( -name plugin.json -o -name marketplace.json -o -name hooks.json \) 2>/dev/null
python3 - <<'PY'
import json,sys
d=json.load(open(".claude/settings.json"))
ep={k:v for k,v in d.get("enabledPlugins",{}).items() if "caveman" in k}
mk=d.get("extraKnownMarketplaces",{})
print("== enabledPlugins caveman:",ep,"marketplaces:",list(mk))
sys.exit(0 if ep and any(ep.values()) and mk else 1)
PY
