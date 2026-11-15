#!/usr/bin/env bash
# Spike: does prek run a local language: golang hook with no system Go,
# in a main checkout and in a git worktree, and fail when a test fails?
set -u
fail=0
echo "prek: $(prek --version)"; echo "system go: $(command -v go || echo none)"
W=$(mktemp -d); export PREK_HOME=$W/prek-home   # cold cache to time the fetch
R=$W/repo; mkdir -p $R/applications/demo; cd $R
git init -q -b main; git config user.email s@x; git config user.name s
cat > applications/demo/go.mod <<'G'
module example.com/demo

go 1.22
G
cat > applications/demo/demo.go <<'G'
package demo

func Add(a, b int) int { return a + b }
G
cat > applications/demo/demo_test.go <<'G'
package demo

import "testing"

func TestAdd(t *testing.T) {
	if Add(2, 3) != 5 {
		t.Fatal("bad")
	}
}
G
cat > .pre-commit-config.yaml <<'G'
repos:
  - repo: local
    hooks:
      - id: go-gates
        name: go vet and go test (applications/demo)
        language: golang
        entry: bash -c 'cd applications/demo && go version && go vet ./... && go test ./...'
        pass_filenames: false
        files: ^applications/demo/
G
git add -A; git commit -qm init
echo "== run 1: cold cache, main checkout"
t0=$(date +%s); prek run --all-files --verbose; rc=$?; t1=$(date +%s)
echo "rc=$rc seconds=$((t1-t0))"; [ $rc -eq 0 ] || fail=1
echo "== cache contents"; ls $PREK_HOME; du -sh $PREK_HOME/* 2>/dev/null
find $PREK_HOME -maxdepth 4 -name 'bin' -path '*go*' 2>/dev/null | head
echo "== run 2: warm cache"
t0=$(date +%s); prek run --all-files; rc=$?; t1=$(date +%s); echo "rc=$rc seconds=$((t1-t0))"
echo "== run 3: failing test must fail the hook"
sed -i 's/return a + b/return a - b/' applications/demo/demo.go
out=$(prek run --all-files --verbose 2>&1); rc=$?; echo "$out" | tail -20; echo "rc=$rc"
if [ $rc -eq 0 ] || ! echo "$out" | grep -q -- '--- FAIL: TestAdd'; then echo "FAILING VARIANT DID NOT FAIL"; fail=1; fi
git checkout -q -- applications/demo/demo.go
echo "== run 4: fresh git worktree, shared cache"
git worktree add -q $W/wt main --detach
cd $W/wt; t0=$(date +%s); prek run --all-files --verbose; rc=$?; t1=$(date +%s)
echo "rc=$rc seconds=$((t1-t0))"; [ $rc -eq 0 ] || fail=1
echo "== result fail=$fail"
exit $fail
