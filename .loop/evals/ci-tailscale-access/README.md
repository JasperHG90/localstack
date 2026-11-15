---
type: eval
title: 'Eval: ci-tailscale-access'
description: 'Definition of done for ci-tailscale-access: 8 row(s).'
tags:
- eval
generated:
  by: process:loopctl/2.2.2.dev1+gd84319696
  at: '2026-11-15T21:58:39+00:00'
slug: ci-tailscale-access
signoff:
  signer: delegated:jasperginn@gmail.com/claude-opus-5-5
  hash: a5384c356b07c5f257da29767084416d4ce4fa8a71aeab7ce33c6aa2b3953886
  at: '2026-11-15T21:58:39+00:00'
verified: null
---

Rows: rows.json; the fields each row takes: loopctl schema eval-rows.

- r1: every jwt-github caller role binds repository, ref, environment and workflow_ref through bound_claims, with bound_audiences [vault.io] and a token TTL of minutes
  Fails when: a caller role lacks any of the four bound claims, lacks the vault.io audience, or has a TTL of an hour or more
- r2: no workflow that uses the lab-auth action triggers on pull_request or pull_request_target, and each sets environment, explicit permissions with id-token write, and a timeout
  Fails when: such a workflow has a pull_request or pull_request_target trigger, or lacks environment, permissions or timeout-minutes
- r3: the lab-auth action joins with tailscale/github-action@v4 using only oauth-client-id, audience and tags (defaulting to the federated identity's client id and audience and tag:ci) with args left empty, logs in at auth/<vault-mount>/login with the job's OIDC token for audience vault.io, masks the token and exports VAULT_ADDR and VAULT_TOKEN
  Fails when: the action reads a Tailscale or Vault secret input, passes --accept-routes in args, requests a different audience, or does not mask and export the token
- r4: the default caller list holds only this repository's lab-auth-check workflow on refs/heads/main in the lab environment
  Fails when: the default list holds another repository, ref, environment or workflow
- r5: the repo gates pass, Terraform formatted and valid
  Fails when: just pre_commit exits non-zero
- r6 (judgment): after the operator applies and pushes, a workflow_dispatch run of lab-auth-check on main joins as an ephemeral tag:ci node, gets a Vault token from the OIDC token alone, reaches vault, openviking-api and s3 on 443 and times out on 192.168.2.30:22, 192.168.2.30:8200, 192.168.2.50:1933, 192.168.2.29:8333 and firebat's tailnet address on 8200; a dispatch from a throwaway branch is refused at the Vault login
  Fails when: any of those is not shown in the run logs
- r7 (judgment): no Tailscale or Vault credential is in a committed file or a repository-level secret
  Fails when: a credential appears in the diff or the action needs a stored secret
- r8 (judgment): the decision record, the tailscale-subnet-router and vault-identity component pages (with a read-only copy of the saved policy), the how-to (per the how-to skeleton, naming the extra federated identity a repo with the immutable OIDC subject needs) and the GitHub Actions reference inputs table describe what was built
  Fails when: a page is missing, disagrees with the action or the policy, or the how-to leaves out the immutable-subject step
