---
epic = "foundation"
depends_on = []
priority = 44
summary = "Set server.oidc_issuer on the Nomad server so it serves an OIDC discovery document, not just JWKS. Nomad currently signs Workload Identity JWTs but advertises no /.well-known/openid-configuration, which M1 needs. **It does not by itself unblock M1 or R1**: M1's `F1` dependency is unmet and F1 is blocked, and R1 is blocked on unrelated grounds. This removes one blocker, not the last one."
tags = ["nomad", "oidc", "bootstrap", "ansible"]
---

# F10 — Make Nomad a full OIDC issuer, not just a JWT signer

## Title
Set `server { oidc_issuer = ... }` in the Nomad server config so Nomad serves
`/.well-known/openid-configuration`. Today it signs Workload Identity JWTs and
serves JWKS, but advertises no discovery document, and nothing in the ledger
owns changing that.

## Size / Effort
**Small, with a real operational edge.** The change is one line in a Jinja
template plus a variable. The cost is that applying it restarts the only Nomad
server, and that the `iss` claim on newly minted WI JWTs changes.

## Triggered by
A1's plan premise sweep, 2026-07-30. Two tickets need this and neither owns it:

- **M1** (`M1-minio-poc-service-account`, blocked) points MinIO's
  `identity_openid` at Nomad. MinIO `RELEASE.2025-09-07T16-13-09Z` **removed**
  the `jwks_url` parameter — its source at the deployed tag lists it under
  `// Removed params`, and `Enabled(kvs)` is literally
  `kvs.Get(ConfigURL) != ""`. Only `config_url`, a real discovery document,
  works. M1 is unimplementable until this ticket lands.
- **R1** (`R1-rollout-mlflow-oauth2-proxy`, blocked) needs oauth2-proxy's
  bare-JWKS fallback, whose single `--extra-jwt-issuers` value must equal the
  JWT's `iss` **and** base a reachable JWKS URL — which requires `oidc_issuer`
  to be set.

**F1's Q7 already named this gap and left it open.** F1 marks
`nomad.hcl.j2` read-only and delivers JWKS only; M1's Q1 says "block subticket
2 on F1 providing a concrete, reachable URL", which deadlocks because F1 as
planned never provides one. This ticket exists to break that deadlock and to
resolve F1's Q7.

## Context (verified live 2026-07-30)
- **The setting is absent.** `bootstrap/roles/nomad_server/templates/nomad.hcl.j2:29-32`
  is exactly:
  ```
  server {
    enabled          = true
    bootstrap_expect = 1
  }
  ```
  No `oidc_issuer`. A repo-wide `grep -rn oidc_issuer bootstrap/ deployments/`
  returns nothing.
- **Live confirmation.** `GET $NOMAD_ADDR/v1/agent/self` reports
  `Server.OIDCIssuer: ''`. `curl $NOMAD_ADDR/.well-known/openid-configuration`
  returns `OIDC Discovery endpoint disabled`, while
  `curl $NOMAD_ADDR/.well-known/jwks.json` returns a populated key set. Nomad
  is a signer, not an issuer.
- **Single server, and it is ALSO a client, and it runs the edge.**
  `nomad server members`: one member, `firebat.global` at `192.168.2.30:4648`,
  `alive`, **leader**, build **2.0.4**, `bootstrap_expect = 1`. (An earlier
  draft said 1.11.3; the cluster was upgraded, and
  `bootstrap/inventory/group_vars/all.yml:12` pins `nomad: 2.0.4-1`.)
  **CORRECTED 2026-07-30 (plan review).** This bullet previously ended
  "Restarting it is a brief control-plane outage. Running allocations keep
  running; scheduling and the API pause." That understated it and cited no
  evidence. `nomad.hcl.j2:20` sets `client { enabled = true }`, so firebat is
  a combined server AND client, and
  `deployments/infrastructure/services/haproxy.hcl:6-9` pins the edge proxy to
  it by hostname constraint. So the restart touches the agent supervising the
  edge proxy, not just the control plane.
  There is a circularity worth seeing plainly: **the issuer URL this ticket
  configures, `https://nomad.lab.orangecluster.nl`, is served BY haproxy, ON
  firebat, the node being restarted.** If the restart disturbs the haproxy
  allocation, the issuer becomes unreachable at exactly the moment it is first
  needed. Whether Nomad's client-state recovery keeps the allocation up across
  an agent restart is NOT established here and must be confirmed before the
  run, not assumed.
- **How it is applied.** `bootstrap/roles/nomad_server/tasks/main.yml:121-128`
  templates `nomad.hcl.j2` to `/etc/nomad.d/nomad.hcl` and carries
  `notify: Restart nomad`, so the handler restarts the service on change. This
  is an Ansible bootstrap run, not a Terraform apply.

  **How to apply it, because the obvious command is wrong.** `just bootstrap`
  (`bootstrap/justfile:40-49`) runs nine playbooks and, via
  `nomad_client/tasks/main.yml:56,65`, carries `notify: Restart nomad` — so it
  restarts **all five agents**, not the one server whose config changed. Use
  the targeted playbook instead:

  ```
  cd bootstrap && ansible-playbook playbooks/configure_hashistack_server.yml
  ```

  It is `hosts: manager`, so it touches firebat alone, and the server role's
  own handler (`nomad_server/tasks/main.yml:128`) restarts the one agent.

  **Check for a second pending change before you restart.** The template
  carries an `advertise` block at `nomad.hcl.j2:23-27` added by `c744b92` on
  2026-07-31, after this plan was written. If that block is not yet on the
  host, this run applies two config changes in one restart. Live
  `AdvertiseAddrs` reads `192.168.2.30` on all three ports — which is what the
  template produces **and** what Nomad would auto-detect, so it does not settle
  the question. Diff the rendered `/etc/nomad.d/nomad.hcl` against the template
  before applying, and verify both settings after. The eval's git-diff row
  cannot catch this: the repo is identical either way.
- **The `iss` change is SAFE for existing Vault logins, verified.**
  `vault read auth/jwt-nomad/config` returns `bound_issuer: ""`,
  `jwks_url: http://127.0.0.1:4646/.well-known/jwks.json`,
  `oidc_discovery_url: ""`, `default_role: nomad-workloads`. Because
  `bound_issuer` is empty, Vault does not check `iss`, so changing it does not
  invalidate anything. **The risk is the restart, not the claim change.** This
  reproduces the safety note in F1's Q7 independently.
- **Nothing else consumes Nomad's `iss` today.** No job under `deployments/`
  matches `jwks`, `openid` or `oidc` (A1 ground truth), and Vault is the only
  configured consumer of Nomad WI JWTs.

## Non-goals / out of scope
- **Not implementing M1 or R1.** This ticket makes the discovery document
  exist. Consuming it is those tickets' work, and both are blocked on their
  own defects beyond this one.
- **Not touching Vault's `jwt-nomad` auth config.** It trusts by `jwks_url`
  and works today. Switching it to `oidc_discovery_url` is a separate,
  optional change; do not bundle it.
- **Not setting `bound_issuer` on the Vault JWT role.** Tightening that is a
  security improvement worth its own ticket, and doing it here couples a
  low-risk config addition to a change that CAN lock workloads out.
- **Not changing the JWKS endpoint, the `vault.io` audience, or the
  `default_identity` block** (`nomad.hcl.j2:37-46`).
- **Not adding TLS to the Nomad API.** The issuer URL's scheme is settled in
  Q1, not by re-architecting the listener.

## Requirements & restrictions
1. `server { oidc_issuer = "<url>" }` is set in
   `bootstrap/roles/nomad_server/templates/nomad.hcl.j2`, sourced from an
   Ansible variable, not a literal, matching how `nomad_server_ip_address` is
   already used in the same file.
   **CORRECTED 2026-07-30 (plan review):** this previously said "with a
   default". There is nowhere to put one. No role in this repo has a
   `defaults/` directory; the convention is an inline `vars:` block on the
   role invocation at `bootstrap/playbooks/configure_hashistack_server.yml:41-44`,
   which is also where `nomad_server_ip_address` is set. Follow that. Do not
   introduce a `defaults/` directory as a side effect of this ticket.
2. After the bootstrap run, `curl <nomad>/.well-known/openid-configuration`
   returns HTTP 200 with a JSON body carrying `issuer` and a `jwks_uri`, and
   the advertised `jwks_uri` fetches a non-empty `keys` array.
3. The advertised `issuer` equals the configured value exactly. MinIO
   compares `iss` against the discovery document's `issuer`, so a mismatch
   fails at token-validation time with an opaque error.
4. **Existing Vault workload logins continue to work after the restart.**
   Verified by a job that holds `nomad-workloads` rendering its Vault
   template successfully post-restart, not by reasoning about `bound_issuer`.
5. **The restart is planned, not incidental.** The ticket states when it
   happens, what pauses (scheduling, the API), and what does not (running
   allocations), and the operator runs it.
6. `.claude/rules/adversarial-reviews.md`: adversarial review before done.

## Code surface
- `bootstrap/roles/nomad_server/templates/nomad.hcl.j2:29-32` — add
  `oidc_issuer` to the existing `server` block.
- `bootstrap/playbooks/configure_hashistack_server.yml:41-44` — add the new
  variable to the existing inline `vars:` block, beside
  `nomad_server_ip_address`. **There is no `defaults/main.yml` to use**: no
  role in this repo has a `defaults/` directory.
- `bootstrap/roles/nomad_server/tasks/main.yml:121-128` — read only. The
  existing `notify: Restart nomad` already handles the restart; no new task.
- `deployments/infrastructure/services/haproxy.hcl:6-9` — read only, but READ
  it: it pins the edge proxy to `firebat`, the node being restarted.

No Terraform, no jobspec, no `deployments/` change.

## Tests & validation gates
No unit-test harness for Ansible or HCL, and no CI. The repo gate plus live
verification.

### Repo gate
- **Command:** `just pre_commit` -> all Passed. Note this change touches a
  `.j2` template and YAML only, so `nomad-fmt` and `terraform-*` hooks will
  skip; `check-yaml` and `end-of-file-fixer` are the ones that matter.
- **Worktree prerequisite:** `just worktree_setup <path>` (`justfile:30-32`).

### Evals
Authoritative set is `.loop/evals/F10-foundation-nomad-oidc-issuer.md`.
The discovery checks require the Ansible run and the restart, which the loop
never performs, so they are the close-out acceptance procedure the operator
executes. The loop's own bar is the gate plus the rendered-template check.

## Risk assessment
- **Blast radius: the control plane, briefly.** One server, `bootstrap_expect
  = 1`, and it is the leader. During the restart, scheduling and the Nomad API
  are unavailable. Running allocations are unaffected. Choose the moment.
- **The `iss` claim changes on newly minted WI JWTs.** Verified safe for the
  only consumer: `auth/jwt-nomad/config` has `bound_issuer: ""`, so Vault does
  not validate `iss`. If a future ticket sets `bound_issuer`, it must be set
  to the value this ticket configures.
- **Wrong issuer URL is the likeliest defect, and it fails late.** MinIO and
  oauth2-proxy compare `iss` to the discovery document. A value that resolves
  from the server but not from a client, or that disagrees with what clients
  are configured with, surfaces as an opaque validation failure in M1/R1
  rather than here.
- **Reversibility: high.** Removing the line and re-running the role restores
  the previous state, at the cost of a second restart.
- **The edge is in the blast radius, not outside it.** See the Context
  correction: firebat is server and client, haproxy is pinned to it, and the
  issuer URL is served through that proxy. Verify the haproxy allocation
  survives the restart before treating the change as applied, and have the
  direct address `http://192.168.2.30:4646` to hand for diagnosis if the edge
  does not come back.

## Subtickets (ordered)
1. Confirm Q1's settled value still holds — `https://nomad.lab.orangecluster.nl`
   routed at the edge and serving JWKS — then set it. Do not re-open the fork.
2. Add the variable and the `oidc_issuer` line; render the template locally
   and inspect the output before any run.
3. Operator runs the bootstrap role against the Nomad server; the handler
   restarts it.
4. Verify: discovery 200 with `issuer` and `jwks_uri`; `jwks_uri` returns
   keys; `issuer` matches the configured value exactly.
5. Verify no regression: a `nomad-workloads` job renders its Vault template
   after the restart.
6. Close F1's Q7 by pointing it at this ticket, and unblock M1's dependency
   question. Use the `relay-finding` skill rather than editing those plans ad
   hoc. **MOVED 2026-07-30 (plan review): do this FIRST, as part of subticket
   1, not last.** F1's Q7 tells its own implementer to make this same edit, so
   until the relay lands, two tickets both believe they own `oidc_issuer`.
   Note F1 is currently `blocked` (F9 falsified its policy premise on
   2026-07-30), which reduces but does not remove the collision risk.
7. Adversarial review.

## Open questions
- **Q1 — SETTLED. The issuer URL is `https://nomad.lab.orangecluster.nl`.**
  The candidates were the direct API
  address `http://192.168.2.30:4646`, or an edge hostname such as
  `https://nomad.lab.orangecluster.nl` if one is routed. Constraints: the URL
  must be reachable **by the clients that will validate tokens** (MinIO runs
  on 192.168.2.29, oauth2-proxy wherever L1 places it), the discovery document
  and JWKS must be fetchable from there, and MinIO compares `iss` literally.
  There is a real pull toward HTTPS: F2 settled that Vault's OIDC issuer must
  be HTTPS, and an HTTP issuer here is an inconsistency, though MinIO's STS
  path is machine-to-machine on a trusted LAN.

  **Settled by evidence, 2026-07-30: a Nomad hostname IS already routed at the
  edge.** `deployments/infrastructure/services/haproxy.hcl:101` carries
  `acl is_nomad hdr(host) -i nomad.lab.orangecluster.nl`, routed at `:112` to
  `backend nomad` (`:136-137`, `server nomad1 192.168.2.30:4646`). Verified
  live: `https://nomad.lab.orangecluster.nl/v1/agent/health` returns **200**,
  `https://nomad.lab.orangecluster.nl/.well-known/jwks.json` returns the key
  set through the edge, and the HTTP form **301s to HTTPS**.

  *Recommendation, now concrete:* set
  `oidc_issuer = "https://nomad.lab.orangecluster.nl"`. It is reachable from
  any client on the LAN, it rides the same publicly-trusted Let's Encrypt
  wildcard T1/T3 shipped, it is consistent with F2's HTTPS-issuer decision,
  and it survives a backend IP change. The direct form
  `http://192.168.2.30:4646` is rejected: it would bake a raw IP over
  plaintext into every token, and the HTTP edge 301s anyway, which some
  clients will not follow when fetching a discovery document.

  **SETTLED 2026-07-30 by the plan review, in Nomad's source at the deployed
  tag.** This was flagged as the implementer's remaining unknown: whether
  Nomad derives `jwks_uri` from `oidc_issuer` or from the request host. It
  derives it from the configured issuer. **Verified empirically on this
  cluster's line rather than from source**, because the source citation an
  earlier draft used was for v1.11.3 and the cluster runs 2.0.4. Measured on a
  throwaway `nomad agent -dev` at 2.0.3: `oidc_issuer` is accepted, discovery
  returns 200, and fetching over a *different* host:port than the configured
  issuer still returns `jwks_uri` pointing at the **configured** host — so it
  derives from the issuer, not the request. A real minted Workload Identity
  JWT decodes with `iss` byte-identical to the discovery document's `issuer`. So the discovery
  document's `issuer`, `agent/self`'s `OIDCIssuer`, and the minted `iss` are
  all one value, and setting it to the edge hostname yields a `jwks_uri` on
  that same host. **Operator still confirms the value itself before
  subticket 2**, but the mechanism is no longer open.

- **Q2 — Does Vault's `jwt-nomad` switch from `jwks_url` to
  `oidc_discovery_url` once discovery exists?** It is not required: JWKS trust
  works and is unaffected. *Recommendation:* leave it. Changing a working
  trust path for tidiness risks locking every workload out of Vault for no
  functional gain. Revisit only if a future ticket needs issuer validation.
