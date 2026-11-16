---
type: plan
title: 'Plan: tf-validate-partial-init'
description: 'scripts/tf_validate.sh removes the .terraform its own failed init leaves, so the next run inits again instead of failing until someone deletes it.'
tags:
- plan
generated:
  by: process:loopctl/2.2.2.dev1+gd84319696
  at: '2026-11-16T14:51:05+00:00'
slug: tf-validate-partial-init
epic: null
depends_on: []
priority: null
---

# tf-validate-partial-init

Relayed from: remove-hermes-interactive, its first stamp went red because a
failed provider download left a partial `.terraform/` that later runs trusted.

## Intent

`scripts/tf_validate.sh` runs `terraform init -backend=false` only when a root
has no `.terraform/` directory. When an init dies partway (a provider download
broke off with "unexpected EOF"), it leaves `.terraform/` behind with missing
providers. Every later run skips init and fails "Missing required provider"
until someone deletes the directory by hand.

When the script runs init itself (the root had no `.terraform/`) and init
fails, it removes the `.terraform/` that init left and exits non-zero. The
next run then finds no `.terraform/` and inits again. A root that already had
`.terraform/` is never removed, so a developer root initialized with its
Consul backend is left alone, and the script still never touches that
backend.

Healing a broken `.terraform/` that already exists is out of scope.
`terraform providers schema -json` reads remote state on a root initialized
with its backend (spike:tf-validate-partial-init/1), and so does
`terraform init -backend=false` on such a root, which also means Terraform
1.16.5's wording for a missing provider cannot drive a retry offline
(spike:tf-validate-partial-init/3). A broken directory left by an earlier
script version is deleted by hand once.

The test is `new:cli/tests/test_tf_validate.py`. It runs the script against a
stub `terraform` on `PATH` that records its calls and can make init fail after
creating `.terraform/`, in the style of `cli/tests/test_seed_worktree.py`.

Outcome: after a failed init the script exits non-zero and the root has no
`.terraform/`. A root with an existing `.terraform/` is validated without init
and keeps its directory, even when validate fails. The gates pass.

## Could invalidate this plan

- none
