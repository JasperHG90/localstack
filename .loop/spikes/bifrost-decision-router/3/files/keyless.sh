#!/usr/bin/env bash
# Runs the two keyless decide.sh cases: bare-string choices (expect 400) and
# object choices with no key (expect 401 with the decisions route resolved).
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
"$HERE/decide.sh" bare-strings | grep -q "HTTP 400"
"$HERE/decide.sh" no-key | grep "HTTP 401" | grep -q "\"request_type\":\"decisions\""
cat "$HERE/results.txt"
