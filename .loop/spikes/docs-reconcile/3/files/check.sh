#!/usr/bin/env bash
# Does kmctl v0.10.0 check enforce its own docs sections (or source paths)
# once a docs page has front matter? Exit 0 when it enforces no sections.
set -u
KM="uvx --from git+https://github.com/JasperHG90/kmctl@v0.10.0 kmctl"
W=$(mktemp -d); trap 'rm -rf "$W"' EXIT; git clone -q --no-local . "$W/repo"; cd "$W/repo"
echo "== baseline check"; $KM check; base=$?; echo "exit $base"
add() { # file, sources-yaml
  { printf -- '---\ndescription: Spike page.\nstale_after: 2027-01-15\nsources:\n%s\n---\n' "$2"; cat "$1"; } > "$1.new" && mv "$1.new" "$1"; }
H=docs/how-to/log-in-to-vault.md
R=$(ls docs/reference/*.md | grep -v README | head -1)
E=docs/explanation/cluster-roles.md
add "$H" "  - justfile"
add "$R" "  - deployments/infrastructure/identity.tf"
add "$E" "  - does/not/exist.tf"
echo "== pages: $H $R $E"; grep -h '^## ' "$H" "$R" "$E" | sort -u
echo "== check --fix (regenerates folder indexes from new descriptions)"; $KM check --fix >/dev/null 2>&1
echo "== check with front matter"; out=$($KM check 2>&1); rc=$?; echo "$out"; echo "exit $rc"
echo "== section findings:"; echo "$out" | grep -E "Before you start|Steps|Check it worked|Details|The question|How it works|Why it is this way|\\bsections?\\b" || echo none
echo "== missing-source finding:"; echo "$out" | grep -i "does/not/exist" || echo none
echo "== review due:"; $KM review due 2>&1 | grep -E "log-in-to-vault|cluster-roles|$(basename "$R")|exist" || echo none
[ $rc -eq 0 ] && ! echo "$out" | grep -qE "Before you start|Steps|Check it worked|Details|The question|How it works|Why it is this way|\\bsections?\\b"
