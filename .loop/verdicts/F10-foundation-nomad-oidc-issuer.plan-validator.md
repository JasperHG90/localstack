---
verdict: pass-with-required-fixes
plan: 35036bcfbd10042777d22a0cf5ff35327125442025b5677dbe21ff0e784cdea7
---

# Plan review: F10-foundation-nomad-oidc-issuer (re-review)

Fingerprint computed locally with `sha256sum` before binding. The value in my
briefing (`...1eaf2a1e8b5cf6a1e2f5b1f8`) was wrong; the real one is bound above.

## Did the prior verdict's required fixes land?

Yes, and in response, not incidentally. The plan carries explicit
`CORRECTED 2026-07-30 (plan review)` and `MOVED 2026-07-30 (plan review)`
annotations that map one-to-one onto the prior verdict's numbered fixes, and the
eval carries a matching `Corrected 2026-07-30` note plus two new rows.

| Prior fix | State |
| --- | --- |
| 1. Variable location, drop "with a default" | APPLIED. Requirement 1 (`plan:111-116`) and Code surface (`plan:134-137`) now name `configure_hashistack_server.yml:41-44`; "with a default" is gone. |
| 2. Correct the blast radius | APPLIED. New Context bullet (`plan:58-75`) and Risk bullet (`plan:176-181`) name the server+client node, the haproxy pin, and the circularity. |
| 3. Fix the haproxy path | PARTIAL. Fixed in Context (`plan:65-66`) and Code surface (`plan:140`). Q1 still says `services/haproxy.hcl:101` and `:136-137` (`plan:214,216`), which does not resolve from the repo root. |
| 4. Relay F1 Q7 first | APPLIED as an annotation (`plan:195-199`), still printed as item 6. |
| 5. Record P9 settled | APPLIED (`plan:230-240`). |
| Eval row 8 rewrite | APPLIED (now the `variable, not a literal` row). |
| Eval: add a minted-`iss` row | APPLIED (new row). Plus an unrequested edge-survival row. |
| Eval: Q1 answer hard-coded in the scorer | NOT APPLIED. See below; the eval is now signed with the value in it. |

## Premise verdict: PARTIALLY SOUND

The central mechanism is sound and I verified it harder than the plan does,
against the version the cluster actually runs. What breaks is the plan's
snapshot of the world: the config file and the Nomad version both moved after
the plan was committed, and the plan's one settled technical citation points at
source for a version that is no longer deployed.

## Per assumption

### P1 — `nomad.hcl.j2:11-14` is the bare `server` block: BREAKS (stale anchor)
The file changed after the plan was written. Commit `c744b92`
("pin nomad advertise addresses…", 2026-07-31 09:55:32 +0200) inserted an
18-line `advertise` block. The plan was committed 2026-07-31 07:31:35, 2.4 hours
earlier. Every `nomad.hcl.j2` anchor in the plan is off by 18 lines:

| Plan says | Actual |
| --- | --- |
| `:11-14` bare `server` block | `:29-32` |
| `:20` `client { enabled = true }` | `:38-39` |
| `:37-46` `default_identity` | `:55-64` is the `vault` stanza; `default_identity` is `:60-63` |

An implementer opening `:11-14` lands mid-comment in the advertise block.

### P2 — no `oidc_issuer` anywhere in the repo: HOLDS
`grep -rn oidc_issuer bootstrap/ deployments/` exits 1, no matches.

### P3 — live: discovery disabled, JWKS populated: HOLDS
`http://192.168.2.30:4646/.well-known/openid-configuration` returns HTTP 404,
body `OIDC Discovery endpoint disabled`. `/.well-known/jwks.json` returns HTTP
200 with a 3-key set. The gap the ticket exists to close is real today.

### P4 — "build 1.11.3": BREAKS
`nomad server members` reports Build **2.0.4**. All five clients report 2.0.4
(`nomad node status -json`). `bootstrap/inventory/group_vars/all.yml:12` pins
`nomad: 2.0.4-1`, so pin and installed agree. The CLI in this container is
v2.0.3.

This matters because Q1's SETTLED paragraph (`plan:230-240`) is the plan's only
settled technical citation and it reads "in Nomad's source at the deployed tag…
v1.11.3, `nomad/structs/keyring.go:621`, `nomad/encrypter.go:339`". That tag is
not deployed. The conclusion survives (P5, P6), but the citation is wrong.

Side effect worth recording: because the pin matches what is installed,
`install_dependencies.yml` is a no-op for Nomad. There is no hidden upgrade
riding on this run.

### P5 — setting `oidc_issuer` produces a discovery document: HOLDS, re-verified at 2.0.x
This is the whole premise and I tested it empirically rather than by reading
docs. Throwaway `nomad agent -dev` (v2.0.3, isolated data-dir and ports, since
torn down) with `server { oidc_issuer = "https://nomad.example.test" }`:

- Startup log: `nomad: issuer set; OIDC Discovery endpoint for workload
  identities enabled: issuer=https://nomad.example.test`
- `GET /.well-known/openid-configuration` → HTTP 200:
  `{"id_token_signing_alg_values_supported":["RS256","EdDSA"],"issuer":"https://nomad.example.test","jwks_uri":"https://nomad.example.test/.well-known/jwks.json","response_types_supported":["code"],"subject_types_supported":["public"]}`
- `jwks_uri` derives from the configured issuer, **not** the request host: I
  fetched over `127.0.0.1:24646` and was handed back the `example.test` host.
  That settles Q1's mechanism at the right version.
- `GET /v1/agent/self` → `config.Server.OIDCIssuer` = the configured value. The
  field name is unchanged at 2.0.x, so eval row 2's scorer path is valid.
- The 2.0.3 binary carries `hcl:"oidc_issuer"` and
  `Error using server.oidc_issuer = "%s" as a base URL: %s`, plus the warning
  `is not using https. Many OIDC implementations require https.`, which endorses
  the plan's HTTPS choice.

### P6 — the minted `iss` equals the discovery `issuer`: HOLDS, decoded not assumed
Submitted a throwaway batch job with `identity { name = "default" env = true }`
to the dev agent, wrote `$NOMAD_TOKEN` to the alloc dir, base64-decoded the
payload: `iss = 'https://nomad.example.test'`, byte-identical to the discovery
`issuer`. The eval's headline row will pass on a correct implementation.

### P7 — `bound_issuer: ""` makes the `iss` change safe: HOLDS
`vault read auth/jwt-nomad/config` live: `bound_issuer n/a` (empty),
`jwks_url http://127.0.0.1:4646/.well-known/jwks.json`, `oidc_discovery_url n/a`,
`default_role nomad-workloads`, `jwks_pairs []`. Vault does not assert `iss`.

Worth adding to the plan: Vault fetches JWKS over **loopback on the server**, so
Vault is insulated from the haproxy coupling the plan worries about. The coupling
binds M1 and R1, not Vault.

### P8 — `tasks/main.yml:121-128` templates with `notify: Restart nomad`: HOLDS
Byte-exact. `:121` is `- name: Template Nomad configuration`, `:128` is
`notify: Restart nomad`.

### P9 — `configure_hashistack_server.yml:41-44` is the `nomad_server` vars block: HOLDS
Byte-exact: `- role: nomad_server` / `vars:` /
`nomad_server_ip_address: "192.168.2.30"` / `nomad_server_consul_token_secret`.

### P10 — "There is nowhere to put a default; no role has a `defaults/` directory": BREAKS in part
The `defaults/` half holds: `find bootstrap/roles -type d -name defaults` returns
nothing. The absolute claim does not.
**`bootstrap/inventory/group_vars/all.yml` now exists** (458 B), holding
`hashistack_versions`, and it is consumed by `install_dependencies.yml:118-121`
and `:138`. So a group-vars home is available today. The prior verdict's finding
("There is no group-vars directory") was true when written and is now stale, and
the plan hardened it into a settled correction.

This is not fatal: the playbook `vars:` block is still a defensible home, and
F10's variable is server-role-scoped rather than fleet-wide. But the plan asserts
a falsehood as verified fact, and eval row 9's justification ("neither of which
exists in this repo") is now half-wrong.

### P11 — haproxy routes the Nomad hostname over HTTPS: HOLDS on content, path still wrong in Q1
Anchors byte-exact in `deployments/infrastructure/services/haproxy.hcl`: `:6-9`
constraint `attr.unique.hostname == firebat`; `:101` `acl is_nomad hdr(host) -i
nomad.lab.orangecluster.nl`; `:112` `use_backend nomad if is_nomad`; `:136-137`
`backend nomad` / `server nomad1 192.168.2.30:4646 check`. Live: health 200 via
`https://nomad.lab.orangecluster.nl`, JWKS 200 through the edge, HTTP form 301s
to HTTPS, DNS resolves to 192.168.2.30. The haproxy alloc is running on
`firebat`, confirming the blast-radius correction. Q1 still cites the truncated
path (prior fix 3 only half-applied).

### P12 — MinIO is on 192.168.2.29: HOLDS
The `minio` alloc runs on node `orangepi4a`, whose address is 192.168.2.29. Eval
row 4 names the right machine.

### P13 — the restart is one role against one node: UNCERTAIN, and the applied scope is understated
Two gaps, and this is now the operational risk the plan does not cover.

- **The advertise block may ride along.** `c744b92` is in the repo template but I
  could not confirm it is deployed on the manager: ssh to 192.168.2.30 returns
  `Permission denied (publickey)`, so I could not read `/etc/nomad.d/nomad.hcl`.
  If it is not yet applied, F10's run pushes **two** config changes in one
  restart. Eval row 10 ("only the `oidc_issuer` line added") scores a `git diff`,
  not the deployed config, so it passes either way and cannot catch this.
- **No command is given, and the obvious one is far wider.** Subticket 3 says
  "Operator runs the bootstrap role against the Nomad server" with no invocation.
  The only task-runner recipe is `just bootstrap` (`bootstrap/justfile:40-49`),
  which runs nine playbooks including `configure_hashistack_clients.yml`. The
  client role also templates with `notify: Restart nomad`
  (`bootstrap/roles/nomad_client/tasks/main.yml:56,65`) and its template also
  gained an advertise block in `c744b92`, so `just bootstrap` restarts **all five
  agents**, not one. The narrow path is
  `ansible-playbook playbooks/configure_hashistack_server.yml`, which the plan
  never names.

Mitigating, and worth stating in the plan: the advertise pin exists precisely
because an unattended restart on 2026-07-31 advertised the podman bridge and
dropped four of five nodes (template comment, `nomad.hcl.j2:18-22`). Once
deployed it makes this restart safer than the plan assumes.

### P14 — "the single reason M1 cannot work": BREAKS as stated; the non-goals hedge correctly
Ledger, read via `loopctl ledger`:

- **M1** is `blocked`, `deps: F1-foundation-nomad-wi-jwt-trust,
  A1-audit-plan-premise-sweep (1 unmet)`. F1 is itself `blocked`
  ("Re-plan against the 3-block policy before implementing"). F10 removes one of
  M1's two blockers. M1 does not become pickable.
- **R1** is `blocked` for reasons F10 does not touch: "mlflow#10922 closed
  not_planned 19 days before authoring, S3 citation refers to a spike that never
  ran, MLflow now ships an SSO plugin", plus `L1` unmet. R1's oauth2-proxy
  approach may not survive its own replan, so "R1 needs oauth2-proxy's bare-JWKS
  fallback" (`plan:31-34`) is a premise R1's own review already doubts.

The frontmatter `summary` ("the single reason M1 cannot work") and "Triggered by"
overstate. Non-goals (`plan:92-94`) hedge honestly: "both are blocked on their
own defects beyond this one". Fix the overstatement, keep the hedge.

### P15 — repo gate: HOLDS, with one loose claim
`justfile:18-19` is `pre_commit: pre-commit run --all-files`; `:30-32` is the
`worktree_setup path:` recipe and its two lines. Both byte-exact. `nomad-fmt` has
`files: '\.hcl$'` and `types: [hcl]`, so `nomad.hcl.j2` does not match. But
`pre-commit run --all-files` passes every file in the repo, so the
`types: [terraform]` hooks (`terraform-fmt`, `terraform-validate`) **do** run
against the existing `.tf` files. "terraform-* hooks will skip" (`plan:151-152`)
is wrong; the `worktree_setup` prerequisite the plan already lists is what makes
them pass.

### P16 — the Nomad ACL management-token constraint: does not apply, correctly
F10 touches no Nomad ACL object: no auth-method, no binding-rule, no policy. It
edits a Jinja template and a playbook `vars:` block, applied over ssh as root.
The constraint that pushed G2 and F8 out of Terraform does not bite here, and
F10 is already in Ansible. `nomad_acl_policy.deploy` at
`deployments/infrastructure/nomad_deploy_role.tf:13` is untouched by this ticket.

## Most dangerous assumption

**P1 with P4.** The plan's Context is a snapshot of a file and a Nomad version
that both moved after it was committed. The mechanism survives — I re-verified it
end to end at 2.0.x — so this does not sink the approach. It sinks the plan's
credibility as a map: every `nomad.hcl.j2` line number is wrong, and the one
citation the plan calls SETTLED points at source for a version the cluster no
longer runs. P13 is the close second, because it is the one that can actually
hurt the cluster.

## Eval review (`.loop/evals/F10-foundation-nomad-oidc-issuer.md`, signed 2026-07-31)

The marker is operator-signed, so I am stating plainly what cannot run rather
than assuming it is fine. **No row fails a correct implementation.** One row's
stated procedure cannot be executed as written, and the signature has silently
closed an open plan question.

- **Row 14 (minted `iss`): its first suggested method cannot be executed.**
  "read one from a running alloc's `secrets/` dir" does not work.
  `nomad alloc fs <id> t/secrets/nomad_token` returns
  `Reading secret file prohibited: t/secrets/nomad_token`. I hit this on the dev
  agent at 2.0.3. The row is still passable via its second route (a throwaway job
  with `identity { env = true }`, writing `$NOMAD_TOKEN` to the alloc dir), which
  is how I proved P6. Correct the parenthetical or the operator burns time.
- **Row 2 needs a token and does not say so.** `GET /v1/agent/self` on this
  cluster is ACL-gated; unauthenticated it returns a non-JSON error. The field
  path `config.Server.OIDCIssuer` is correct at 2.0.x (verified). Add the token
  requirement.
- **The signed eval decides an open plan question.** The Definition of Done and
  rows 1, 3 and 4 hard-code `https://nomad.lab.orangecluster.nl`, while plan Q1
  is still filed under Open questions and ends "Operator still confirms the value
  itself before subticket 2" (`plan:239-240`). Since the operator signed the
  marker, the fork is in practice settled at that value. The plan must be brought
  into line; as it stands an operator who follows the plan and picks a different
  value fails four 100% rows.
- **Row 9's justification is now half-false.** "neither of which exists in this
  repo" — `bootstrap/inventory/group_vars/all.yml` exists (P10). The row still
  passes a correct implementation that uses the playbook `vars:` block.
- **Row 10 cannot catch P13.** It scores a `git diff`, so an advertise block
  already pending in the template rides into the deployed config invisibly.
- Rows 5, 7 and 15 are the strongest in the set. Row 7's T+10min re-check and
  row 15's edge-survival check are both genuinely load-bearing.

## Required fixes

1. **Re-anchor every `nomad.hcl.j2` citation (P1).** `server` block is `:29-32`,
   not `:11-14`; `client { enabled = true }` is `:38-39`, not `:20`;
   `default_identity` is `:60-63` inside the `vault` stanza at `:55-64`, not
   `:37-46`. Cause: commit `c744b92`, 2026-07-31 09:55, 2.4 h after the plan was
   committed.
2. **Correct the version and the Q1 citation (P4).** The cluster runs Nomad
   **2.0.4** (`nomad server members`; all five nodes 2.0.4;
   `group_vars/all.yml:12` pins `2.0.4-1`), not 1.11.3. Replace the v1.11.3
   source citation in Q1 with the re-verification at 2.0.x recorded under P5 and
   P6 above: discovery serves, `jwks_uri` derives from the configured issuer and
   not the request host, and the minted `iss` is byte-identical to the discovery
   `issuer`.
3. **Fix the P10 falsehood.** Drop "There is nowhere to put one" from
   Requirement 1. `bootstrap/inventory/group_vars/all.yml` exists and is read by
   `install_dependencies.yml:118-121,138`. Keep the playbook `vars:` block as the
   choice if that is the intent, but justify it as a choice rather than as the
   absence of an alternative. Update eval row 9's parenthetical to match.
4. **State the apply scope and name the command (P13).** Subticket 3 must give
   `ansible-playbook playbooks/configure_hashistack_server.yml`, and the risk
   section must say that `just bootstrap` (`bootstrap/justfile:40-49`) instead
   runs nine playbooks and restarts all five Nomad agents, because
   `nomad_client/tasks/main.yml:56,65` also carries `notify: Restart nomad`.
5. **Resolve the pending advertise change before the run (P13).** Confirm whether
   `c744b92`'s advertise block is already deployed in `/etc/nomad.d/nomad.hcl` on
   192.168.2.30. I could not: ssh returns `Permission denied (publickey)`. If it
   is not deployed, say so in the risk section — the run then applies two config
   changes in one restart, and eval row 10 cannot detect it. Note the mitigation
   too: that block exists to stop a restart advertising the podman bridge
   (`nomad.hcl.j2:18-22`), so once applied it makes this restart safer.
6. **Close Q1 in the plan to match the signed eval.** The marker is signed with
   `https://nomad.lab.orangecluster.nl` in the DoD and rows 1, 3 and 4. Mark Q1
   settled at that value and delete "Operator still confirms the value itself
   before subticket 2", or the plan invites a choice the eval will fail.
7. **Fix the last haproxy path (prior fix 3, half-applied).** Q1 at `plan:214`
   and `:216` still says `services/haproxy.hcl`; it is
   `deployments/infrastructure/services/haproxy.hcl`. Line numbers are correct.
8. **Correct row 14's procedure in the eval.** `nomad alloc fs` refuses to read
   `secrets/`: `Reading secret file prohibited`. Point the row at the throwaway
   job with `identity { env = true }` route. Add to row 2 that
   `/v1/agent/self` needs an ACL token.
9. **Downgrade the M1/R1 claim (P14).** The frontmatter `summary` and "Triggered
   by" say this is "the single reason M1 cannot work". M1 also has `F1` unmet and
   F1 is itself blocked; R1 is blocked on grounds F10 does not touch and its
   oauth2-proxy premise is under doubt. Keep the honest Non-goals hedge and make
   the summary match it.

## Contract hygiene

- **Code surface with resolved anchors:** three stale `nomad.hcl.j2` anchors and
  one truncated haproxy path. Everything else (`tasks/main.yml:121-128`,
  `configure_hashistack_server.yml:41-44`, `haproxy.hcl:6-9,101,112,136-137`,
  `justfile:18-19,30-32`) resolves byte-exact.
- **Discovered, not assumed, gates:** correct, with the loose "terraform-* will
  skip" claim noted under P15. The plan is honest that there is no CI and no
  Ansible test harness.
- **Explicit non-goals:** present and strong. Declining to set `bound_issuer` in
  the same ticket remains the right call.
- **Tests homed in the code surface:** yes; the eval names real paths and
  commands, and row 4 names the correct MinIO host.
- **Forks surfaced, not silently decided:** Q1 and Q2 carry recommendations, but
  Q1's answer is now pre-committed in a signed eval while the plan still calls it
  open. Required fix 6.

## Method

All repo and cluster work was read-only. No mutating git command was run. The
only process I started was a throwaway `nomad agent -dev` on isolated ports
(24646/24647/24648) with its own scratch data-dir; its two test jobs were purged
and the agent stopped, confirmed by `pgrep`. The live cluster's Nomad, Vault,
Consul and HAProxy were only read. No token value appears in this verdict.
