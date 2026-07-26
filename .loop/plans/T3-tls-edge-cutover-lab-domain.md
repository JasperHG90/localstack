---
epic = "tls"
depends_on = ["T1-tls-acme-letsencrypt-transip", "T2-tls-dnsmasq-lab-zone-dns"]
priority = 140
relay_block_nonfork = true
summary = "Flag-day edge cutover: HAProxy serves the publicly-trusted Let's Encrypt cert from Vault KV2, all twelve routed hostnames rename to <svc>.lab.orangecluster.nl in a single apply, and F3's Vault PKI apparatus is deleted. After this apply no .localstack name is served."
tags = ["tls", "haproxy", "dns", "vault"]
---

# T3 — Cut the edge over to `*.lab.orangecluster.nl` with the Let's Encrypt cert

## Title
HAProxy serves the publicly-trusted cert from Vault KV2, all twelve routed
hostnames rename to `<svc>.lab.orangecluster.nl` in a single apply, and F3's
Vault PKI apparatus is deleted. Supersedes F3.

## Size / Effort
**Medium.** Mechanically small (one template source swap, twelve ACL renames,
one file deleted), but it is the flag-day change: after this apply no
`.localstack` name is served. Effort is in verification and docs, not HCL.

## Triggered by
F3's `*.localstack` leaf is unusable — a wildcard requires >=2 labels after
the `*`, so no client accepts it (`curl: (60) SSL: no alternative certificate
subject name matches target host name`, `openssl verify error:num=62`). The
operator's requirement is that everyone on the network, mobile included,
reaches the cluster over HTTPS with nothing installed per-device. T1 provides
the trusted cert, T2 the resolution; this ticket flips the edge.

## Context (today's state)
- **Anchors below were authored against a moving file. Re-open every one**
  before relying on it: F3 shifted `haproxy.hcl` line numbers, and the
  `services.tf` HAProxy resource is at `:315-330` (not `:308-327`; 308 is
  MinIO's closing brace).
- Post-F3 edge (`services/haproxy.hcl`): `https` port at `:16-18`, cert
  template at `:44-72` sourcing `pki/issue/haproxy`, `frontend http_in` at
  `:90-92` doing only `http-request redirect scheme https code 301`,
  `frontend https_in` at `:94-95` binding `:443 ssl crt
  /secrets/haproxy.pem`, twelve ACLs at `:97-108`, twelve `use_backend` at
  `:110-121`, backends at `:130-166`. **Re-read for current line numbers.**
- F3's PKI apparatus: `deployments/infrastructure/pki.tf` (mount, root cert,
  config URLs, role, `vault_policy.haproxy_pki`,
  `vault_jwt_auth_backend_role.haproxy`), wired at `services.tf:308-327` via
  `pki_issue_path` / `vault_role` template vars and a `depends_on`.
- **Internal service-to-service routing does NOT use these hostnames.**
  Verified 2026-07-25 by scanning every live Nomad job and the whole Vault KV
  tree: hermes reaches memex at `http://192.168.2.46:8000`, talat-consumer
  likewise, prometheus scrapes `192.168.2.46:9100`, bifrost is
  `192.168.2.50:8080`, minio `192.168.2.29:9000`. Zero KV values reference a
  `.localstack` host. **The rename touches the edge only** — no consumer
  migration is required. Re-verify with the commands in §8 rather than
  trusting this note, since jobs change.
- The scan's one other hit, `talat-shim`'s Consul `Meta { haproxy_host =
  "talat.localstack" }`, is explicitly out of scope (see Non-goals). Nothing
  routes it — HAProxy has no talat ACL or backend.
- HAProxy reading `secret/data/default/haproxy/*` needs no custom grant: the
  shared `nomad-workloads` policy
  (`bootstrap/.../vault_nomad_workloads.hcl_j2:1-7`) already grants a workload
  read on its own job prefix. T1's cert lands exactly there, so a bare
  `vault {}` suffices here and F3's dedicated role becomes dead weight.

## Non-goals / out of scope
- Obtaining or renewing certs (T1) and LAN resolution (T2).
- Dynamic consul-template ingress. Backends stay static `server <ip>:<port>`.
- Backend/upstream TLS. Edge termination only.
- Adding `dash.localstack` / any L1 hostname. L1 owns that against the renamed
  frontend.
- Tearing down the Vault `pki` MOUNT itself (Q2 decides; the Terraform
  resources go either way).
- Changing backends, the `stats` frontend, or the `openfang_users` basic-auth
  userlist.
- **`talat-shim`'s `haproxy_host` Consul meta.** Operator-excluded
  (2026-07-25): its jobspec is not in this repo and nothing routes it today.
  Leaving it naming `talat.localstack` is not a regression. Do not chase it,
  and do not relay it.

## Requirements & restrictions
1. HAProxy loads cert + key + chain from Vault KV2
   `secret/data/default/haproxy/tls` (field names per T1 Q4), rendered to a
   single concatenated PEM. HAProxy requires cert, key, and intermediates in
   one file.
2. **`perms = "0644"`, not `0600`.** `haproxy:3.1-alpine` runs as `USER
   haproxy` (uid 99) while Nomad renders templates as the agent user; a 0600
   file is unreadable to the process and the alloc fails to start. Verified in
   F3; do not "harden" this back. The key is protected by the per-alloc
   `secrets/` tmpfs.
3. `change_mode = "restart"` retained so a renewed cert is picked up.
4. All twelve hostnames rename to `<svc>.lab.orangecluster.nl` in ONE apply
   (operator decision, 2026-07-25). No transition period, no dual ACLs.
5. Every backend and its routing keeps working unchanged; basic-auth on
   phoenix/mlflow/bifrost still enforced. `CLAUDE.md` §3 Surgical Changes:
   every changed line traces to this ticket.
6. `pki.tf` deleted in full and its wiring removed from `services.tf`
   (`pki_issue_path`, `vault_role`, `depends_on`). HAProxy reverts to a bare
   `vault {}`. Leaving a dedicated JWT role that nothing uses is a
   least-privilege regression, not a harmless leftover.
7. **Docs are in scope and gate this ticket** (see §7 and §8). F3 shipped
   stale docs and had to relay them to L1; that relay is discharged here.
8. Terraform providers pinned at `providers.tf:1-24`. Do not bump.
9. `.claude/rules/adversarial-reviews.md`: adversarial review before done.
10. Before starting, enable the `documentation` review pass in
    `.loop/config.json` (`review_passes[2].enabled = true`) so the doc-freshness
    verdict gates this commit. Re-disable afterward only if the operator asks.
11. **Add a certificate-expiry alert** to
    `services/grafana/alert-rules.yaml`. Deferred out of T1 deliberately:
    before this ticket a silent non-renewal costs nothing, but once HAProxy
    serves the Let's Encrypt cert an unnoticed renewal failure takes all
    twelve routed services down simultaneously, ~60 days after the fact and
    with no warning. Alert on days-to-expiry, not on job success, so it fires
    regardless of which link in the chain broke.

## Code surface
- `deployments/infrastructure/services/haproxy.hcl` — cert template: swap
  source from `pki/issue/...` to the KV2 path; keep destination, perms,
  `change_mode`. Replace `vault { role = "${vault_role}" }` with `vault {}`.
  **NOT a literal source swap: KV2 nests the payload.** The current template
  reads `{{ .Data.certificate }}` (correct for a PKI issue response); KV2
  requires `{{ .Data.data.certificate }}` (compare `backup-minio.hcl:35`,
  `{{ .Data.data.access_key }}`). Getting this wrong renders three blank
  lines, HAProxy fails to parse `crt`, and the alloc crash-loops with all
  twelve services down on flag day.
- `deployments/infrastructure/services/haproxy.hcl` — rename twelve `acl
  is_<svc> hdr(host) -i <svc>.localstack` to `<svc>.lab.orangecluster.nl`.
  `use_backend` lines and all backends unchanged.
- `deployments/infrastructure/pki.tf` — **delete the file.**
- `deployments/infrastructure/services.tf` — drop `pki_issue_path`,
  `vault_role`, and the `depends_on` from `nomad_job.haproxy`; add the KV2
  secret path as a template var (pattern `services.tf:294-306`).
- `docs/haproxy_reverse_proxy.md:9-13,24-37,47` — hostname table, the
  `/etc/hosts` section (now obsolete: T2 resolves network-wide), and the
  add-a-service example. **Relayed from F3 as L1 requirement 10.**
- `docs/monitoring.md:170-171,206-207` — ACL example and the "Visit
  prometheus.localstack / grafana.localstack" steps. **Relayed from F3.**
- `docs/tls-certificates.md` (already exists) — add the serving half: how
  HAProxy consumes the cert and what a renewal looks like from the edge.

  **RELAYED FINDING** *(from T1-tls-acme-letsencrypt-transip, surfaced by its
  adversarial review, re-verified live 2026-07-26. Constraint, not a fork:
  the doc must describe reality, and there is no decision open.)*

  The doc describes this cutover in the present tense, because it was written
  before the cutover existed. Two statements are still false as of the
  re-verification and this ticket is what makes them true:

  1. Line ~53, "The edge proxy templates these into a single PEM file and
     reloads when they change." HAProxy does not read this secret yet.
  2. Line ~117, the verification `curl -sS -o /dev/null -w '%{http_code}\n'
     https://grafana.lab.orangecluster.nl/`. Measured today it exits **000**:
     the name now resolves, but the edge still serves the old `*.localstack`
     leaf, so TLS verification fails. An operator following the doc right now
     debugs a certificate that is fine.

  **Do NOT touch the third statement.** Line ~63, "There is no public A record
  for the lab zone. Names resolve on the LAN only, from the local resolver",
  was also false when this finding was first raised and has since become TRUE:
  the resolver was applied and answers. Re-read all three before editing
  rather than trusting these line numbers.

  While editing, note the field shape, confirmed against the live certificate:
  `certificate` holds the leaf AND its issuing chain (4 PEM blocks on the
  current production leaf), and `issuer_chain` repeats that intermediate on
  its own. The HAProxy PEM therefore needs only `certificate` plus
  `private_key`; appending `issuer_chain` sends the intermediate twice, which
  is harmless but pointless.
- `.loop/plans/L1-landing-oauth2-proxy.md` — update requirements 10 and 11,
  which currently name `.localstack` and tell the implementer no PKI work
  follows. Plan files are excluded from the tree fingerprint.
- **Sweep every downstream plan and eval that hardcodes an old hostname.**
  Eval rows are literal acceptance commands: after the flip they hit a 503 and
  the owning ticket fails its own scorer for reasons unrelated to its work.
  Enumerate with `grep -rln '\.localstack' .loop/plans .loop/evals` and rename
  all of them EXCEPT the historical records `F3-*` and `F4-*`, which document
  what was true at the time and must not be rewritten. As of 2026-07-25 the
  live set is: `R1-*` and `R4-*` (plan + eval), `L1-*` and `L2-*` (plan +
  eval), `M2-minio-poc-human-tiers`, `S3-spike-oidc-version-claims`, and
  `F2-foundation-vault-oidc-provider` (11 references, including the OIDC
  issuer URL — F2's front-matter was already retargeted from F3 to T3 for
  exactly this reason). Re-run the grep rather than trusting this list.
- `docs/riscv-integration.md:190` — `nats.localstack`. Note
  `docs/haproxy_reverse_proxy.md:37` advertises `postgres.localstack`, which
  is already wrong today (HAProxy runs in HTTP mode and has no postgres
  backend); correct or delete it rather than renaming it.

## Tests & validation gates
No unit-test harness for infra HCL, no CI. Repo gate plus live evals.

### Repo gate
- **Command:** `just pre_commit` -> all Passed.
- **Worktree note:** `just worktree_setup <path>` first (`3c12c7a`).
- **Command:** `terraform -chdir=deployments/infrastructure plan` -> updates
  `nomad_job.haproxy` in place; DESTROYS the six `pki.tf` resources. Confirm it
  destroys no KV mount, no backend, no firewall rule, and does not touch
  `vault_mount.kvv2`.

### Offline pre-apply check (do this; F3 proved its value)
- Render the config template, substitute vars, generate a throwaway PEM, run
  `haproxy -c -f` in `docker.io/library/haproxy:3.1-alpine`. Exit 0.
- Run negative controls (missing cert path, bogus keyword) and confirm both
  exit 1, so the check is known to discriminate.

### Re-verify the no-consumer claim before flipping (Context may have aged)
- `for j in $(nomad job status | awk 'NR>1{print $1}'); do nomad job inspect
  $j | grep -oE '[a-z0-9-]+\.localstack'; done` -> only haproxy and
  talat-shim.
- Vault KV scan for `.localstack` in any value -> zero matches.

### Evals — the authoritative set is `.loop/evals/T3-tls-edge-cutover-lab-domain.md`
The marker is the acceptance contract; the rows below are its narrative form.
Its row 9 (a phone shows a valid padlock with nothing installed) is
**human-scored at 100%** by operator decision, 2026-07-25. F3 shipped a
certificate that passed every machine check available at the time and was
still unusable by every client, so this ticket does not close on machine
checks alone.
1. Alloc healthy: `nomad job status haproxy` -> deployment successful, 1
   healthy.
2. **Cert is publicly trusted with NO `-k` and NO `--cacert`** — the failure
   F3 shipped: `curl -sS -o /dev/null -w '%{http_code}'
   https://grafana.lab.orangecluster.nl/` -> 200/302, exit 0. Any need for
   `-k` is a FAIL.
3. Hostname matching holds for a second host:
   `openssl s_client -connect 192.168.2.30:443 -servername
   mlflow.lab.orangecluster.nl -verify_hostname mlflow.lab.orangecluster.nl`
   -> `Verify return code: 0 (ok)`.
4. Redirect: `curl -sI http://grafana.lab.orangecluster.nl/` -> 301 to the
   https URL, path and query preserved.
5. Routing and auth intact: grafana -> 200 (with `-L`), mlflow -> 401,
   phoenix -> 401, bifrost -> 401, minio -> 200.
6. Old names are gone: `curl -sk --resolve
   grafana.localstack:443:192.168.2.30 https://grafana.localstack/` -> 503 or
   no matching backend, confirming the flag-day flip is complete.
7. **The motivating requirement:** a phone on the wifi opens
   `https://grafana.lab.orangecluster.nl` and shows a valid padlock with
   nothing installed. Operator-observed.

## Risk assessment
- **Blast radius: the entire edge, deliberately.** Flag-day rename of all
  twelve services. A wrong ACL, an unrenderable template, or a missing KV
  field takes every routed service down at once.
- **Ordering.** T1 and T2 are hard `depends_on`. Applying with the cert
  missing blocks the template and the alloc never starts; applying before
  dnsmasq leaves the new names unresolvable.
- **The 0600 trap.** Documented in requirement 2 because it is exactly the
  kind of thing a reviewer "hardens" and breaks. Eval 1 catches it.
- **Rate limits.** If the cert must be re-issued during this ticket, Let's
  Encrypt's 5 duplicate certs/week applies. Do not loop on issuance here; T1
  owns issuance.
- **Reversibility: moderate.** `git revert` plus re-apply restores the F3
  edge, but F3's cert was never client-valid, so reverting returns to
  click-through warnings, not to a good state. Forward-fix is usually right.
- **Bookmarks and muscle memory** break for the operator on flip. Accepted
  explicitly by the single-apply decision.

## Subtickets (ordered)
1. Enable the `documentation` review pass in `.loop/config.json`.
2. Swap the cert template source to KV2; bare `vault {}`; offline
   `haproxy -c` check.
3. Rename the twelve ACLs.
4. Re-run the consumer scans in §8 to confirm the no-consumer claim still
   holds. Only haproxy and the out-of-scope talat-shim meta should match.
5. Delete `pki.tf` and its `services.tf` wiring.
6. Apply; run evals 1-6. Operator runs eval 7.
7. Docs: `haproxy_reverse_proxy.md`, `monitoring.md`, `tls-certificates.md`,
   and L1's plan requirements 10-11.
8. Adversarial review.

## Open questions
- **Q1 — Does the `lab.orangecluster.nl` apex need routing?** The wildcard
  cert covers it if T1 includes it as a SAN, but no ACL routes it.
  *Recommendation:* no ACL in this ticket; a bare-apex landing page is L2's
  concern.
- **Q2 — Keep or destroy the Vault `pki` mount?** The Terraform resources go
  regardless. *Recommendation:* leave the MOUNT in place, unmanaged, as a
  parked internal CA for future service-to-service mTLS. Destroying it is a
  one-line `vault secrets disable pki` later and forecloses nothing.
- **Q3 — Does anything outside the repo hit `*.localstack`?** The scans cover
  this repo, live Nomad jobs, and Vault KV only. Laptop scripts, browser
  bookmarks, and other repos are invisible here. *Recommendation:* accept as
  the known cost of the flag-day decision; the operator was explicit.
