verdict: pass-with-required-fixes
tree: 1aa0f3b6226644e7b3f501970b148449056aeefc
pass: adversarial
slug: F5-foundation-vault-nomad-secrets-engine
cycle: 2

# Adversarial re-review — F5 (Vault Nomad secrets engine), cycle 2

## Bottom line

The prior Major finding is **genuinely resolved**. The widened `deploy`
policy now carries namespace-level `host-volume-*` capabilities, and I
proved on the live cluster that a freshly minted `nomad/creds/deploy`
token lists and reads all 8 dynamic host volumes (previously ACL-filtered
to empty). Gates are green, scope is clean, and all 8 eval rows pass.

I return **pass-with-required-fixes** for one reason: the
operator-amended contract prose now contains a **provably false empirical
claim** about the `developer` policy, which the briefing explicitly asked
me to validate. The claim is inverted from the truth. The required fix is
a **wording correction to the contract** (the `.loop/plans` amendment +
requirement 3); **no code change is needed**, and the code diff at this
tree is correct and committable as-is.

## Verification performed (independent, live cluster)

Cluster: Nomad v2.0.3 (BuildDate 2026-06-09), reachable via
`.devcontainer/.env` (`VAULT_ADDR=http://192.168.2.30:8200`,
`NOMAD_ADDR=http://192.168.2.30:4646`). Gate `just pre_commit` re-run:
all hooks Passed (nomad fmt, terraform fmt -check, terraform validate per
root).

All 8 eval-marker rows re-run and PASS:
1. `nomad/` mount present, `type: nomad`. PASS.
2. `nomad/config/access` `.data.address` = `http://127.0.0.1:4646`. PASS.
3. `nomad/role/deploy` `.data.policies == ["deploy"]`, `type: client`,
   not management. PASS. (Role `ttl`/`max_ttl` null; effective lease from
   the mount `nomad/config/lease` ttl=1800/max_ttl=3600 — see Obs. A.)
4. `nomad/creds/deploy` mints `secret_id` + `accessor_id`,
   `lease_duration: 1800`, `lease_id` set, `renewable: true`. PASS.
5. Minted token `nomad job plan .../minio.hcl` renders (exit 1, plan with
   changes; no auth error). PASS.
6. NEW row — minted token `nomad volume status -type host` lists all 8
   volumes (memex_data, hermes_data, loki_data, postgres, grafana_data,
   nats_data, prometheus_data, minio_data), byte-for-byte matching the
   admin listing. NOT filtered to empty. PASS. Direct proof the prior
   Major finding is closed.
7. Guardrails — minted token denied on all three: `nomad node status`
   -> 403, `nomad operator raft list-peers` -> 403, `nomad alloc exec`
   -> Permission denied. PASS.
8. `nomad acl policy info developer` byte-identical to
   `bootstrap/roles/nomad_server/files/nomad_developer_policy.hcl`.
   Untouched. PASS.

Scope guards confirmed clean:
- Diff vs HEAD is exactly `bootstrap/roles/nomad_server/tasks/main.yml`
  (tracked) + untracked `deployments/infrastructure/nomad_deploy_role.tf`.
- Both `provider "nomad" {}` blocks untouched
  (`deployments/applications/providers.tf:30`,
  `deployments/infrastructure/providers.tf:26`).
- `.devcontainer/.env.example:2` `NOMAD_TOKEN=` untouched (0 diff lines).
- No dual ownership: `nomad_acl_policy "deploy"` has exactly one home
  (`deployments/infrastructure/nomad_deploy_role.tf:13`); no `deploy`
  policy reference anywhere in `bootstrap/`.
- Management token protected: `no_log: true` on the `nomad/config/access`
  task; token never committed.
- Mechanism is correct: the `host_volume` mount block (mount-readonly/
  mount-readwrite) governs a job mounting a volume, not managing it; the
  namespace `host-volume-*` caps govern CRUD on the volume resource. The
  `deploy` policy correctly uses the namespace caps and has no
  `host_volume` block. The `.tf` header comment
  (`nomad_deploy_role.tf:1-12`) is accurate and does NOT repeat the false
  claim below.

## Required fix (contract wording — no code change)

### [Major] The amendment's premise about `developer` is provably false

The amendment and revised requirement 3 justify the "not a strict subset"
re-framing on this claim:

> "`developer` has no namespace `host-volume-*` capabilities at all, so
> `developer` itself cannot manage dynamic host volumes."
> (plan amendment, lines 30-32)

> "it additionally holds the host-volume management capabilities
> `developer` lacks." (plan amendment lines 35-37, echoed in
> requirement 3, line 186)

This is empirically false. I created an ephemeral client token carrying
ONLY the `developer` policy (`nomad acl token create -policy=developer
-type=client`); it **listed and read all 8 dynamic host volumes**, then
I deleted the probe token. `developer`'s namespace block is coarse
`policy = "write"` (`nomad_developer_policy.hcl:5`), and on Nomad v2.0.3
the coarse `write` policy expands to include the `host-volume-*`
management capabilities (at minimum `host-volume-read`, proven directly;
create/register/write/delete follow from the coarse-policy expansion).
The amendment author read only `developer`'s *explicit* `capabilities =
[...]` list (which omits host-volume-*) and missed that `policy =
"write"` already grants them.

Consequence: `developer` **can** manage dynamic host volumes, and
`deploy` is in fact effectively a **strict subset** of `developer`'s
namespace grants — narrower on `list-jobs`, `dispatch-job`, `read-logs`,
`read-fs`, `alloc-exec`, `alloc-lifecycle`, `alloc-node-exec`, `node`,
`agent`, `operator`, and the `host_volume` mount policy, while
overlapping (not exceeding) on host-volume management. The original
"narrower than `developer`" framing was closer to correct; the amendment
inverted it into a falsehood.

Why this matters despite the code being correct: the false claim now
lives in the frozen decision record and would mislead F6 (the Consul
parallel) and F8. Correct the amendment + requirement 3 wording to state
that `developer`'s coarse `policy = "write"` already grants host-volume
management (proven), so `deploy` is a purpose-scoped near-subset of
`developer`, not a policy holding caps `developer` lacks. Contract-file
edit only; the committable code needs no change.

## Non-blocking findings

### [Minor] `host-volume-register` is speculative for this repo

The infra root contains 8 `nomad_dynamic_host_volume` (create-flavor)
resources and **zero** `nomad_dynamic_host_volume_registration` resources
(`deployments/infrastructure/services.tf:2,22,42,62,82,102,122,142`).
`host-volume-register` governs adopting pre-existing external volumes via
the registration resource, which this repo does not use. Per CLAUDE.md
section 2 and the ticket's own non-goal ("No speculative capabilities",
plan lines 149-152), `register` is a candidate over-grant;
`host-volume-write` (in-place updates) is a weaker candidate. NOT
blocking: the operator explicitly chose the broadest single-role option
and amended requirement 3 to enumerate all five caps (plan lines
177-178), so the implementation faithfully follows the operative
instruction. Flagged only so the tension between requirement 3 and the
"no speculative capabilities" non-goal is a conscious operator decision.

### [Observation A] Role TTL is satisfied at the mount, not the role

Eval 3's "role `ttl` <= 3600s" is met functionally, not literally: the
role's own `ttl`/`max_ttl` are null; the lease is bounded by
`nomad/config/lease` (ttl=1800/max_ttl=3600) configured in Ansible (the
"Configure Nomad secrets engine lease" task in `main.yml`). The minted
`lease_duration` is 1800s, in the required 30-60 min band. Legitimate
design (lease TTL is a mount property) and the task comment says so. No
change required.

## Confirmation

Prior Major finding CLOSED with live proof (8/8 volumes visible and
readable to the minted token). No over-grant beyond the
operator-authorized set. No scope regressions (provider blocks,
`.env.example`, `developer` policy all untouched; no dual ownership).
Gates green. The single required fix is a factual correction to contract
prose; the code diff at tree
1aa0f3b6226644e7b3f501970b148449056aeefc is correct.
