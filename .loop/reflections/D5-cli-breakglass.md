---
slug: D5-cli-breakglass
blockers: []
friction: [other:gitignored-artifacts-block-verify-plan, other:commit-gate-parses-piped-commands, other:reviewer-caught-doc-hallucination]
worked: [other:reuse-status-py-probe-pattern, other:real-http-server-not-mocks, other:drift-test-simulation-verified]
harness_change:
---

## What worked

Reusing status.py's probe pattern: the breakglass probes use the same
stdlib urllib.request + treat-HTTP-error-as-answer approach status.py
already established, so no new HTTP dependency (httpx/respx) was needed.
This kept the change surgical and matched the repo's real-server-not-mocks
test convention.

Real HTTP server for tests: the FakeCluster ThreadingHTTPServer fixture
from conftest.py handled every probe test case by pointing the EDGE/LAN
address dicts at it or at a closed port. No mocking library added.

Drift test simulation: the adversarial reviewer verified the drift tests
actually go red by editing configure_network.yml's from_ip in a scratch
copy and re-running. This is the non-vacuous-parse guarantee the plan's
requirement 4 demands.

## What worked less well

gitignored-artifacts-block-verify-plan: .devcontainer/.env and
.ssh/id_rsa are gitignored, so a fresh worktree has neither, and terraform
validate (plan-validator's deterministic floor and the stamp gate) fails
on the missing file reference. Fix was copying them into the worktree by
hand, a hidden dependency the skill does not mention. The plan itself
says .devcontainer/.env cannot be an anchor, but verify-plan's resolver
still chases the citation.

commit-gate-parses-piped-commands: the PreToolUse commit gate splits the
command on shell sequencing operators to find the git commit. A command
piped to tail or with a multi-line heredoc body fails to resolve the
target repo and blocks with a confusing error. The fix is a bare
single-line git commit with no pipe. Learned the hard way on U5.

reviewer-caught-doc-hallucination: the documentation reviewer caught that
the runbook named the session cache at ~/.config/localstack-cli/
session.json (the distribution name) when the real path is
~/.config/localstack/session.json (the import package name). This is
exactly the drift the breakglass command exists to prevent, and it was in
the breakglass runbook itself. The review pass earned its keep.