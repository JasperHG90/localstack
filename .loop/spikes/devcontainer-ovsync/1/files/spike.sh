#!/usr/bin/env bash
# Risk 1: with ~/.openviking read-only and ovcli.conf -> unreachable URL, do
# ov (0.5.0) and ovsync (v0.3.0) fail only on the network, never on a write
# under ~/.openviking? Exit 0 only when no write is attempted there and every
# server-touching command fails with a connection error.
set -u
SCRATCH=/tmp/claude-1000/-home-vscode-workspace/bb29ac4a-7b6b-458a-a055-0c05909aba19/scratchpad/spike-devcontainer-ovsync
OVSYNC=$SCRATCH/bin/ovsync
OV=/home/vscode/.local/bin/ov
W=$(mktemp -d "$SCRATCH/run.XXXX")
export HOME=$W/home XDG_CONFIG_HOME= OPENVIKING_CLI_CONFIG_FILE=
unset XDG_CONFIG_HOME OPENVIKING_CLI_CONFIG_FILE
mkdir -p "$HOME/.openviking" "$W/notes"
echo '{"url": "http://127.0.0.1:9", "api_key": "dummy"}' > "$HOME/.openviking/ovcli.conf"
echo '# hello' > "$W/notes/a.md"
fail=0
trap 'chmod -R u+w "$W"; rm -rf "$W"' EXIT

# Case: settings file absent vs present (host ~/.openviking normally carries it).
run() { # name, [VAR=val...] cmd...
  local name=$1; shift
  echo "=== $name: $*"
  timeout 60 strace -f -qq -e trace=openat,mkdir,mkdirat,rename,renameat,renameat2,unlink,unlinkat,creat \
    -o "$W/$name.trace" env "$@" > "$W/$name.out" 2>&1
  local rc=$?
  echo "exit $rc"; tail -n 4 "$W/$name.out"
  local writes
  writes=$(grep -F "$HOME/.openviking" "$W/$name.trace" \
    | grep -E 'O_WRONLY|O_RDWR|O_CREAT|mkdir|rename|unlink|creat\(' || true)
  if [ -n "$writes" ]; then echo "WRITE ATTEMPT under ~/.openviking:"; echo "$writes"; fail=1; fi
  if grep -qiE 'read-only|permission denied|EACCES|EROFS' "$W/$name.out"; then
    echo "WRITE ERROR in output"; fail=1; fi
  echo "$rc" > "$W/$name.rc"
}
expect_net() {
  # `ov status` exits 0 and reports "Unreachable"; others exit non-zero.
  if ! grep -qiE 'connect|refused|unreachable|cannot reach|could not reach|network' "$W/$1.out"; then
    echo "NOT a network failure: $1"; fail=1; fi
}

chmod -R a-w "$HOME/.openviking"
if touch "$HOME/.openviking/probe" 2>/dev/null; then echo "dir is writable, spike invalid"; exit 2; fi
echo "touch under ~/.openviking refused: ok"
find "$HOME" -printf '%P %s %T@\n' | sort > "$W/before.txt"

# 1. No settings file, no OPENVIKING_LANG: ov asks for a language first.
run ov_nolang "$OV" status
# 2. OPENVIKING_LANG=en does not stand in for the settings file (informational:
#    ov refuses before any network or write, so only the write check applies).
run ov_status_env OPENVIKING_LANG=en "$OV" status
# 3. ovsync: status is offline, run hits the server.
run ovsync_status "$OVSYNC" status "$W/notes" --root-uri viking://user/jasper/resources/x
run ovsync_run OV_SYNC_SYNC__ROOT_URI=viking://user/jasper/resources/x "$OVSYNC" run "$W/notes" --root-uri viking://user/jasper/resources/x
expect_net ovsync_run
find "$HOME" -printf '%P %s %T@\n' | sort > "$W/after.txt"

# 4. Settings file present in the read-only dir, as on a host that ran `ov language`.
chmod u+w "$HOME/.openviking"; printf '{\n  "language": "en"\n}' > "$HOME/.openviking/ovcli.settings.conf"; chmod -R a-w "$HOME/.openviking"
run ov_status_settings "$OV" status;      expect_net ov_status_settings
run ov_ls_settings     "$OV" ls viking:// ; expect_net ov_ls_settings

# 5. Informational: with OPENVIKING_CLI_CONFIG_FILE elsewhere and a settings
#    file beside it, does ov still look for settings only in ~/.openviking?
mkdir -p "$W/alt"; cp "$HOME/.openviking/ovcli.conf" "$HOME/.openviking/ovcli.settings.conf" "$W/alt/"
mkdir -p "$W/home2"
HOME=$W/home2 OPENVIKING_CLI_CONFIG_FILE=$W/alt/ovcli.conf strace -f -qq -e trace=statx,newfstatat,openat \
  -o "$W/alt.trace" "$OV" health > "$W/alt.out" 2>&1
echo "=== override case: $(head -1 "$W/alt.out")"
grep -o '"[^"]*ovcli.settings.conf"' "$W/alt.trace" | sort -u

echo "=== HOME diff (excluding the settings file added on purpose)"
diff "$W/before.txt" "$W/after.txt" && echo "no change in HOME across cases 1-3"
[ -s "$W/notes/.ov-sync.db" ] && echo "ovsync state: $W/notes/.ov-sync.db (in the synced folder)"
ls -la "$HOME/.openviking"
echo "fail=$fail"
exit $fail
