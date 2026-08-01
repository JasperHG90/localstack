---
slug: B1-bifrost-native-auth-and-virtual-keys
blockers: []
friction: [other:ephemeral-cannot-flow-into-state-persisted-attr, other:worktree-gitignored-file-breaks-validate, other:reviewer-transient-429, other:loop-commit-gate-rejects-long-message]
worked: [eval-scorer-as-iac-test, data-source-for-synced-creds, concurrent-review-fanout]
harness_change: ""
---

## What worked

- Treating the deterministic grep/parse scorer as the IaC "test" mapped the
  tests-first rule onto a change with no runnable code; 9/9 green before the
  stamp, and the adversarial reviewer re-ran it independently.
- The synced-creds copy uses a `data "vault_kv_secret_v2"` (not ephemeral)
  so the value can persist in state via `data_json`; the applications-layer
  ephemeral read feeds the provider block only. Matches the acme.tf pattern.
- Dispatching both review passes concurrently against one shared tree
  fingerprint kept the re-review to a single batch after the doc fixes.

## What worked less well

- `other:ephemeral-cannot-flow-into-state-persisted-attr` — the plan
  specified an ephemeral read for the infra synced copy, but terraform
  forbids ephemeral values in `data_json` (not write-only). Caught at
  `terraform validate`, not by the plan. Fix: data source. A plan-premise
  audit of terraform-ephemeral constraints would have caught this earlier.
- `other:worktree-gitignored-file-breaks-validate` — the pre-existing
  `null_resource.firewall` `file("${path.root}/../../.ssh/id_rsa")` fails
  `terraform validate` in the worktree because `.ssh` is gitignored and not
  checked out. Resolved with the project's own `worktree_setup` symlink
  (gitignored, environment shim only). The gate would otherwise red on a
  file this ticket never touches.
- `other:reviewer-transient-429` — both review subagents hit an ollama
  usage-limit 429 on the first dispatch; the adversarial pass wrote no
  verdict. Re-dispatching on the next tree cleared it. No retry/backoff
  guidance in the skill for a reviewer that dies before writing.
- `other:loop-commit-gate-rejects-long-message` — the PreToolUse commit
  gate rejected `git commit -m "<long multi-line body with parens/slashes>"`
  four times with "cannot determine the commit's target repo," then accepted
  a bare `git commit -m "<short single-line subject>"`. The repo-resolution
  parser chokes on complex `-m` content; a short subject (body via separate
  `-m` or a HEREDOC) avoids it.