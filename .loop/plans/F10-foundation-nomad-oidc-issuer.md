---
epic = "foundation"
depends_on = []
priority = 44
summary = "Set server.oidc_issuer on the Nomad server so it serves an OIDC discovery document, not just JWKS. Nomad currently signs Workload Identity JWTs but advertises no /.well-known/openid-configuration, which is the single reason M1 cannot work and R1's machine bearer path has no owner."
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
- **The setting is absent.** `bootstrap/roles/nomad_server/templates/nomad.hcl.j2:11-14`
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
- **Single server.** `nomad server members`: one member, `firebat.global` at
  `192.168.2.30:4648`, `alive`, **leader**, build **1.11.3**,
  `bootstrap_expect = 1`. Restarting it is a brief control-plane outage.
  Running allocations keep running; scheduling and the API pause.
- **How it is applied.** `bootstrap/roles/nomad_server/tasks/main.yml:121-128`
  templates `nomad.hcl.j2` to `/etc/nomad.d/nomad.hcl` and carries
  `notify: Restart nomad`, so the handler restarts the service on change. This
  is an Ansible bootstrap run, not a Terraform apply.
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
   Ansible variable with a default, not a literal, matching how
   `nomad_server_ip_address` is already used in the same file.
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
- `bootstrap/roles/nomad_server/templates/nomad.hcl.j2:11-14` — add
  `oidc_issuer` to the existing `server` block.
- `bootstrap/roles/nomad_server/defaults/main.yml` **or** the inventory group
  vars — the new variable and its default. Confirm which the role already
  uses for `nomad_server_ip_address` and follow it; do not introduce a second
  convention.
- `bootstrap/roles/nomad_server/tasks/main.yml:121-128` — read only. The
  existing `notify: Restart nomad` already handles the restart; no new task.

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

## Subtickets (ordered)
1. Settle Q1 (the issuer URL value and scheme).
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
   hoc.
7. Adversarial review.

## Open questions
- **Q1 — What exactly is the issuer URL?** The candidates are the direct API
  address `http://192.168.2.30:4646`, or an edge hostname such as
  `https://nomad.lab.orangecluster.nl` if one is routed. Constraints: the URL
  must be reachable **by the clients that will validate tokens** (MinIO runs
  on 192.168.2.29, oauth2-proxy wherever L1 places it), the discovery document
  and JWKS must be fetchable from there, and MinIO compares `iss` literally.
  There is a real pull toward HTTPS: F2 settled that Vault's OIDC issuer must
  be HTTPS, and an HTTP issuer here is an inconsistency, though MinIO's STS
  path is machine-to-machine on a trusted LAN.

  **Settled by evidence, 2026-07-30: a Nomad hostname IS already routed at the
  edge.** `services/haproxy.hcl:101` carries
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

  One check the implementer still owns: confirm the discovery document Nomad
  generates advertises a `jwks_uri` under the SAME host, not the internal
  address. If Nomad derives `jwks_uri` from the request rather than from
  `oidc_issuer`, a client reaching it through the edge could be handed an
  unreachable internal URL. **Operator confirms the value before subticket 2.**

- **Q2 — Does Vault's `jwt-nomad` switch from `jwks_url` to
  `oidc_discovery_url` once discovery exists?** It is not required: JWKS trust
  works and is unaffected. *Recommendation:* leave it. Changing a working
  trust path for tidiness risks locking every workload out of Vault for no
  functional gain. Revisit only if a future ticket needs issuer validation.
