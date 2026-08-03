---
verdict: pass
tree: c3cdfecc27a76fd4a9e98ef3ad6bfba229ba84ca
---

# F10-foundation-nomad-oidc-issuer — adversarial review (re-run after comment fix)

Deterministic floor: `loopctl verify-eval-substance F10-foundation-nomad-oidc-issuer`
returned `valid` (clean). Proceeded to the semantic pass.

`loopctl verify` returns `ok`. The working-tree code files
(`bootstrap/roles/nomad_server/templates/nomad.hcl.j2`,
`bootstrap/playbooks/configure_hashistack_server.yml`) are byte-identical to
the fingerprint tree `c3cdfecc27a76fd4a9e98ef3ad6bfba229ba84ca` (diff exit 0
for both).

## What changed since the prior pass

Exactly one change between the old tree `a8a9964b...` and the new tree
`c3cdfecc...`: the comment in `bootstrap/roles/nomad_server/templates/nomad.hcl.j2`
was reworded. The `oidc_issuer = "{{ nomad_oidc_issuer }}"` line and the
playbook var are unchanged. No other file under `bootstrap/`, `docs/`, or
`deployments/` moved.

Old comment (line 37):
  `# cluster node. F1's docs/workload-identity.md points M1 at this URL.`

New comment (lines 37-38):
  `# cluster node. F1's docs/workload-identity.md defers discovery to F10;`
  `# this is the URL F10 owns and M1 points MinIO's config_url at.`

## Requirement 1: comment accuracy against docs/workload-identity.md — PASS

The prior pass flagged the old comment as a MINOR non-blocking finding: it
said F1's doc "points M1 at this URL" (the oidc_issuer value), but F1's doc
points M1 at the JWKS URL and explicitly disclaims the discovery URL. The
reword addresses that finding precisely.

`docs/workload-identity.md:178-191` states: "F1 delivers the **JWKS URL**
(`http://192.168.2.30:4646/.well-known/jwks.json`) M1 points MinIO's
`identity_openid` at. F1 does **not** deliver an OIDC discovery document ...
That is owned by `F10-foundation-nomad-oidc-issuer`, not F1. F1's scope is
JWKS only."

- "F1's docs/workload-identity.md defers discovery to F10" — accurate. The
  doc says discovery is "owned by F10-foundation-nomad-oidc-issuer, not F1."
- "this is the URL F10 owns" — accurate. `oidc_issuer` is the setting F10
  owns, and F1 disclaims it.
- "M1 points MinIO's config_url at" — accurate. M1's plan
  (`.loop/plans/M1-minio-poc-service-account.md:370-380`) confirms M1 points
  MinIO's `identity_openid` `config_url` at the discovery URL F10 produces,
  and names F10 as the owner.

Both clauses of the reworded comment are grounded in the cited doc and the
M1 plan. The prior finding is resolved.

## Requirement 2: oidc_issuer still sourced from the variable — PASS

`nomad.hcl.j2:41` sets `oidc_issuer = "{{ nomad_oidc_issuer }}"`, unchanged.
`configure_hashistack_server.yml:45` sets
`nomad_oidc_issuer: "https://nomad.lab.orangecluster.nl"` in the inline
`vars:` block beside `nomad_server_ip_address` (line 43), unchanged. The
variable sourcing required by plan requirement 1 and eval row 10 holds.

## Requirement 3: no scope creep, no non-goal touched — PASS

The diff between old and new trees touches only the comment text. The
`oidc_issuer` line, the playbook var, the `default_identity`/`vault` stanza,
`bootstrap_expect`, `aud`, `ttl`, `bootstrap/roles/vault_server/`, and
`deployments/` are all unchanged. No non-goal was touched.

## Gate — PASS

`just pre_commit` re-run: all hooks Passed. The relevant hooks for this
change (`check-yaml`, `end-of-file-fixer`, `nomad-fmt`) all green. The
`terraform validate` failure observed during the first run was a
pre-existing environment artifact: `just worktree_setup` created a
self-referential `.ssh` symlink (`.ssh -> <worktree>/.ssh`), which broke
`file("../../.ssh/id_rsa")` in `services.tf:290`. Pointing the symlink at the
real `/home/vscode/workspace/.ssh` made `terraform validate` pass, confirming
the failure is environmental, not a defect of this change. The symlink was
restored to its original state after the gate run.

## Verdict

PASS. The comment fix is accurate against `docs/workload-identity.md` and the
M1 plan, the `oidc_issuer` variable sourcing is unchanged, nothing else
regressed, and the gate is green. The prior pass's one MINOR finding is
resolved.