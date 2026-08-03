---
epic = "cli"
depends_on = ["D1-cli-package-skeleton"]
priority = 43
summary = "`localstack breakglass` prints the recovery runbook for a cluster you cannot authenticate to or reach, and optionally runs read-only reachability probes to say which failure you are in. It handles no credentials: it never reads, caches, prints or exports the Vault root token or the unseal keys. Every address it prints carries its reachability class — edge, node-local over SSH, or LAN-conditional — so the runbook stays true when `N4-netsec-edge-only-service-access` closes the LAN ports. Tests pin every fact in the printed text against the repo file that states it, including the ufw rule that permits each address, so drift fails a gate instead of going stale silently."
tags = ["cli", "recovery", "runbook", "security"]
---

# Ticket: D5-cli-breakglass

## 1. Title
Add `localstack breakglass`, the command a developer runs when auth or
reachability to the cluster is broken. It prints a runbook, optionally probes
what is reachable, and handles no credential of any kind.

## 2. Size / Effort
**Medium.** One command, one text asset, a handful of read-only probes. The
size comes from the drift tests (every fact in the printed text pinned to the
repo file that states it) and from probe failure handling, not from line count.

## 3. Triggered by
Operator request, 2026-07-30, as part of the `cli` epic. The break-glass path
today is tribal knowledge: nothing in the repo tells a developer what to do
when Vault is sealed, the edge is down, or their token is dead.

### Operator decision, already settled — do NOT re-open
**The command prints the runbook and touches no credentials.** The CLI must
never read, cache, display, log or export the Vault root token, and never read
`/opt/vault/init.json`.

Two alternatives were offered and rejected: fetching the root token over SSH
into the caller's shell, and an unseal helper. Reason: a break-glass credential
passing through the CLI's code path and the developer's shell history is a
worse failure mode than typing a few commands by hand during an outage. The
operator does the privileged step deliberately, themselves.

This makes the command less convenient than it could be. That is intended. Any
argument for automating the privileged step belongs in Open Questions, not in
the implementation.

## 4. Context (today's state)

### Package
- D1-cli-package-skeleton is `done` and the CLI package is tracked. `cli/`
  holds `cli/pyproject.toml`, `cli/uv.lock`, and the `cli/src/localstack_cli/`
  src layout D1's plan specified. Python is pinned to 3.12
  (`.python-version:1`); the legacy `requirements.txt` (`httpx` at :3, `hvac`
  at :5) remains for the non-CLI scripts. Read
  `.loop/archive/D1-cli-package-skeleton/plan.md` §Code surface for the exact
  path, CLI framework, and HTTP client.
- This ticket writes `<pkg>` for the package root D1 established. Resolve
  `<pkg>` to `cli/src/localstack_cli` from D1's plan before writing any file.
- D5 depends on D1 alone. It handles no credentials and reads only local
  files, so it can land before `localstack login` exists.

### The cluster facts the runbook must carry
- **Single manager, `firebat` at `192.168.2.30`**
  (`bootstrap/inventory/cluster.ini:1-3`). Four workers follow (`:5-16`).
- **Vault is initialized and unsealed by Ansible.** `vault operator init` runs
  once and its JSON output is stored at `/opt/vault/init.json`, owner `vault`,
  mode `0600` (`bootstrap/roles/vault_server/tasks/main.yml:109-123`). Reading
  it needs root on the manager.
- **That one file holds both secrets.** The root token is read from it as
  `.root_token` (`bootstrap/roles/nomad_server/tasks/main.yml:189-196`, an
  Ansible `slurp` + `from_json`, not `jq`), and the unseal keys as
  `unseal_keys_b64[:3]`
  (`bootstrap/roles/vault_server/tasks/main.yml:153-160`). **The CLI reads
  neither.** The runbook names the path and the SSH target and stops there.
- **Three addresses per service, and they do not have equal lifespans.** The
  Vault listener binds `0.0.0.0:8200` plaintext
  (`bootstrap/roles/vault_server/templates/vault.hcl.j2:18-21`), so one service
  answers on three routes that fail for different reasons:
  - **Edge**, `https://vault.lab.orangecluster.nl` over TLS. Measured 200 on
    `/v1/sys/health` on 2026-07-31. Survives every planned change, and is the
    only route that needs neither SSH nor a LAN address.
  - **Node-local**, `http://127.0.0.1:8200`, reached by SSH to `firebat`. This
    is what Ansible itself uses on the manager
    (`bootstrap/roles/nomad_server/tasks/main.yml:203`,
    `bootstrap/playbooks/configure_tailscale.yml:22`). It crosses no firewall,
    so no firewall change can take it away. It is the recovery path.
  - **Direct LAN**, `http://192.168.2.30:8200`. Measured 200 on 2026-07-31, and
    conditional: it answers only because `configure_network.yml:18` allows 8200
    from `192.168.0.0/16`. N4 deletes that allow. See "Relationship to N4".

  The dev container's `VAULT_ADDR` is the direct address today
  (`.devcontainer/.env:9`; likewise `NOMAD_ADDR` :3 and `CONSUL_HTTP_ADDR` :6),
  and N4's R6 moves all three onto the edge hostnames. The `.env.example` still
  advertises the long-dead `localstack.local` hostnames
  (`.devcontainer/.env.example:3,7,11`), which is itself a drift instance worth
  not copying.
- **The LAN is not the tailnet, and only the manager is on the tailnet at
  all.** `bootstrap/playbooks/configure_network.yml` opens 8500 (`:13`), 8200
  (`:18`) and 4646 (`:21`) to `192.168.0.0/16` only, over a default incoming
  policy of `deny` (`bootstrap/roles/firewall/tasks/main.yml:7-13`). The tailnet
  CIDR `100.64.0.0/10` gets port 22 (`:11`) plus 80, 443 and 8404
  (`deployments/infrastructure/services.tf:188,190,192`), Grafana 3000 (`:222`)
  and 8080 (`:231`), but no API port. On top of that,
  `bootstrap/playbooks/configure_tailscale.yml:40-47` runs the tailscale role on
  `hosts: manager` only and stops `tailscaled` on every worker (`:49-58`), so
  workers have no tailnet address at all. **The runbook must never claim an API
  port is reachable from the tailnet.** A tailnet user gets SSH to `firebat` and
  the edge on 443, which is exactly the pair requirement 3 leads with. The
  direct LAN addresses that answer from this dev container answer because the
  dev container sits on `192.168.215.2/24`, inside `192.168.0.0/16`.
- **The edge is `https://vault.lab.orangecluster.nl`**, host-header routed by
  HAProxy to `192.168.2.30:8200` (`deployments/infrastructure/services/
  haproxy.hcl:100,111,133-134`). Nomad and Consul route the same way
  (`:101-102,112-113,136-140`).
- **"Edge down" and "Nomad down" share causes.** HAProxy is a Nomad job pinned
  by constraint to hostname `firebat` (`haproxy.hcl:6-9`), and Nomad runs a
  single server with `bootstrap_expect = 1`
  (`bootstrap/roles/nomad_server/templates/nomad.hcl.j2:31`). Consul is also
  single-server (`bootstrap/roles/consul_server/templates/consul.hcl.j2:17`).
  One box carries all three.
- **Sealed Vault takes the edge with it.** HAProxy renders its TLS PEM from
  Vault KV2 through a `vault {}` template with `change_mode = "restart"`
  (`haproxy.hcl:39,62-72`), and binds `*:443 ssl crt /secrets/haproxy.pem`
  (`:96`). A sealed Vault blocks that template, so a restarted HAProxy cannot
  serve TLS at all. This is why the direct addresses matter mid-outage.
- **Consul is Vault's storage backend**
  (`bootstrap/roles/vault_server/templates/vault.hcl.j2:11-15`) and the
  Terraform state backend for both roots
  (`deployments/infrastructure/backend.tf:2`,
  `deployments/applications/backend.tf:2`). Consul down means Vault down and
  Terraform unusable. Say so in the Consul section.
- **`just unseal_vault` exists and is the pointed-at path** (`justfile:33-34`
  running `scripts/unseal_vault.sh`). Two properties the runbook must state:
  - it requires `VAULT_UNSEAL_KEY_1..3`, `VAULT_ADDR` **and `VAULT_TOKEN`** in
    the environment or it refuses (`scripts/unseal_vault.sh:6-9`), even though
    `vault operator unseal` itself needs no token;
  - the root `justfile` has no `set dotenv-load` (contrast
    `bootstrap/justfile:3`), so those values come from the dev container's
    ambient env, injected by `--env-file .devcontainer/.env`
    (`.devcontainer/devcontainer.json:37-39`).
- **`vault`, `nomad` and `consul` CLIs are installed in the dev container**
  (`.devcontainer/Dockerfile:11-17`), so the runbook may name them directly.
- **A real SSH break-glass artifact already exists**:
  `rescue-ssh.nomad.hcl:1-30`,
  a `sysbatch` job that appends a public key to every node's
  `authorized_keys` via a `/home:/host-home` mount. It needs a working Nomad,
  so it belongs in the "SSH is dead but Nomad answers" branch and nowhere else.

### Relationship to N4, the ticket that deletes half this runbook

`N4-netsec-edge-only-service-access` exists to close 4646, 8200 and 8500 to the
LAN so `*.lab.orangecluster.nl` is the only way in. Read its plan before writing
a line of runbook text.

**Cite N4 by section name, never by line number.** N4 is under active revision:
it went from 408 to 588 lines on 2026-07-31 in two passes, and the D5 review
verdict's anchors into it were already stale by the time this section was
written. Anything with a colon and a number in it will rot faster than the claim
it supports. Its headings and its `R<n>` / `Q<n>` labels are stable, so use
those. Four parts of it bind D5 directly:

- **§Code surface**: narrow `from_ip` for 4646, 8200, 8500 and `20000:32000` in
  `configure_network.yml` on manager and workers.
- **R3**: the broad rule is **deleted, not shadowed**. After the run,
  `ufw status numbered` shows no `192.168.0.0/16` entry for any closed port, on
  any of the three provisioners' rules.
- **Q3, resolved**: **no devcontainer exception.** "Direct access is what the
  runbook's SSH path is for."
- **§Risk assessment**, the circular-dependency bullet: closing the ports makes
  the only route to Nomad's API a job that Nomad schedules. "The escape is SSH
  to
  firebat and `NOMAD_ADDR=http://127.0.0.1:4646`."

Two more shape it. Its **R4** carries the constraint behind the prelude: firebat
keeps 22 from both the LAN and the tailnet, the four workers keep 22 from the
LAN
only and have no tailscale, so off-LAN recovery reaches a worker only by hopping
through firebat. And its **R7** adopts D5's pinning rule by name. The edge ran
one way: N4 cited D5, D5 did not cite N4. This section closes that.

**D5 does not take a hard `depends_on` on N4.** Three reasons, and the third is
the one that matters:

1. N4 is the riskiest change in the repo. It is applied over SSH and can strand
   the operator, and it schedules its own runbook
   (`docs/edge-and-recovery.md`) as an early subticket, *before* the dangerous
   apply-to-the-manager step. Gating the break-glass command behind the outage
   it
   exists to survive inverts the order.
2. N4 is blocked behind `N3-netsec-converging-firewall-provisioner`, and N4's
   own §"The finding that reshapes this ticket" calls N3 "the only thing that
   makes the rest take effect": without it a narrowed rule adds a second rule
   beside the live broad one and closes nothing. N4 is not close.
3. **The runbook does not need to wait, because it is written so N4 cannot
   falsify it.** Requirement 3 prints every address with its reachability class,
   leads with the two routes N4 leaves standing, and marks the LAN address as
   conditional on a named ufw rule. Requirement 4 pins that address to
   `configure_network.yml`, so the day N4 narrows `from_ip` the drift test goes
   red and the conditional paragraph must be corrected before the gate passes.

That last point is the design. A runbook saying "the LAN address works because
of
this rule, and here is the SSH path for when it does not" is true before N4 and
true after it. A runbook saying "use `192.168.2.30:8200`" is true for a few
weeks
and then lies during an outage.

**What D5 must not do:** print `192.168.2.30:<port>` as an unqualified escape
hatch, probe only LAN addresses, or report "Vault unreachable" when the honest
finding is "the firewall no longer admits this host". Requirements 3, 4 and 9
and Q2 each carry one part of that correction.

### House style for this kind of page
`docs/tls-certificates.md:131` ("Recovering a failed renewal") is the in-`docs/`
precedent, and it is tracked, so a worktree implementer will actually have it.
Two habits the runbook copies are stated here rather than cited, because the
page
they came from (`tmp/F9-MIGRATION.md`) is gitignored (`.gitignore:1`) and
untracked, so `git worktree add` will not carry it into the implementation tree:

- **Every guard states the failure it prevents.** Not `test -s backup.hcl`, but
  `test -s backup.hcl || { echo "EMPTY BACKUP - STOP"; exit 1; }` followed by
  the
  sentence explaining that a failed read leaves an empty file and the rollback
  would then wipe the thing it was meant to restore. A guard with no stated
  reason gets deleted by the next reader.
- **A verification command carries its expected value, and one check is rarely
  enough.** `grep -c '^path'  # expect: 3` can fail; `grep -q path` cannot. A
  case-sensitive grep also returns 0 against surviving text in another case, so
  it passes green while the thing it guards is still there. That is the failure
  shape requirement 4's non-vacuous-parse rule exists to block.

### Why "keep it in sync" is not an answer
`docs/credential-rotation.md` is a "Proposed Changes" page (`:48`) that tells
the
reader to create `bootstrap/playbooks/rotate_secrets.yml` (`:50`) and to add
`rotate_tailscale` / `rotate_github` recipes to `bootstrap/justfile` (`:78-85`).
Neither was ever built: `bootstrap/playbooks/` has no `rotate_secrets.yml` and
`bootstrap/justfile` has no rotation recipe. So it is an unbuilt design shipped
as documentation, and nothing in the repo notices. That is the same rot, one
step earlier: a reader who skims past the "Proposed" heading walks away
believing
a rotation path exists. A1-audit-plan-premise-sweep exists
because the same failure hit thirteen plans, with the diagnosis that "the
anchors still resolve, it is the surrounding claims that went false"
(`.loop/archive/A1-audit-plan-premise-sweep/plan.md:39-40`). A printed runbook is
documentation embedded in code and will rot the same way unless a gate catches
it. See Requirement 4.

## 5. Non-goals / out of scope

**The credential boundary, stated hard.** The implementation must NOT:
- read, open, stat or shell out to anything that touches `/opt/vault/init.json`;
- read `VAULT_TOKEN`, `VAULT_UNSEAL_KEY_*`, `NOMAD_TOKEN` or `CONSUL_HTTP_TOKEN`
  from the environment, from a file, or from a keyring, for any purpose,
  including "just to check whether it is set";
- send any credential on any probe (no `X-Vault-Token`, no
  `X-Nomad-Token`, no `Authorization` header, no `-H` equivalent);
- write, cache, export or print a token, an unseal key, or any value derived
  from one;
- open an SSH connection, or run `ssh`, `ansible`, `ansible-playbook`,
  `terraform`, `vault`, `nomad` or `consul` as a subprocess.

Also out of scope:
- Invoking `just unseal_vault` (see Q1). Print the command; do not run it.
- Any write to the cluster. Every probe is a read.
- `localstack login`, token caching, or any auth flow. Separate ticket.
- Changing `scripts/unseal_vault.sh`, the root `justfile`, any Ansible role,
  any Nomad job, or any Terraform.
- Fixing `docs/credential-rotation.md` or `.devcontainer/.env.example`. Both
  are stale; both are other tickets.
- A TUI, an interactive wizard, a pager, or a browser launch.

## 6. Requirements & restrictions

1. **`localstack breakglass` prints a runbook and exits.** No credential path,
   per the operator decision above.
2. **Distinct sections per failure mode, not one wall of text.** Cover, each
   with its own heading and its own commands: sealed Vault; expired or revoked
   token; edge down but cluster up; Nomad unreachable; Consul unreachable; lost
   local token cache. Plus a short prelude on reaching the manager at all
   (tailnet, `.ssh/id_rsa`, user `firebat` per `cluster.ini:2-3`). The prelude
   states that only `firebat` is on the tailnet
   (`configure_tailscale.yml:40-47,49-58`) and that the tailnet carries SSH and
   443, not the API ports.
3. **Three addresses, each with its reachability class.** Any section naming a
   service names all three routes, in this order, and says which one to reach
   for
   when the others are suspect:
   1. **Edge** — `https://<svc>.lab.orangecluster.nl`, host-header routed by
      HAProxy (`haproxy.hcl:100-102` for the ACLs, `:133-140` for the backends).
      Reachable from the LAN and the tailnet. This is the default advice.
   2. **Node-local over SSH** — `ssh firebat@192.168.2.30`, then
      `http://127.0.0.1:<port>`. Crosses no firewall and needs no edge, so it is
      the route that works when the other two do not. N4 names this same path as
      its own escape (N4 §Risk assessment). This is the recovery advice, and it
      must appear in the sealed-Vault, Nomad-unreachable and Consul-unreachable
      sections at minimum, since those are the ones read mid-outage.
   3. **Direct LAN** — `http://192.168.2.30:<port>`, printed **with the
      condition that makes it work**: it answers only from `192.168.0.0/16` and
      only while `configure_network.yml` allows that port from that CIDR
      (`:13,18,21`). The runbook says so in the same breath as the address, and
      names `N4-netsec-edge-only-service-access` as the change that removes it.
      Never print this address as an unqualified escape hatch.

   The wrong shape here is "edge or direct, pick one". The edge and the direct
   LAN address share a failure: both die when `firebat` dies, and the LAN one
   also dies from a policy change that leaves the service perfectly healthy.
   Only
   the SSH plus loopback route is independent of both.
4. **Drift has to fail a gate, and the gate has to be pinned to the file that
   governs the claim.** Every fact-bearing token in the printed text is
   asserted,
   in a test, against the repo file that states it. At minimum:
   - the manager IP and username against `bootstrap/inventory/cluster.ini`;
   - the `unseal_vault` recipe name against the root `justfile`;
   - the `/opt/vault/init.json` path against
     `bootstrap/roles/vault_server/tasks/main.yml`;
   - each edge hostname against the `hdr(host) -i` ACLs in
     `deployments/infrastructure/services/haproxy.hcl:100-102`, and each
     `ip:port` backend against `:133-140`;
   - the Vault port against
     `bootstrap/roles/vault_server/templates/vault.hcl.j2`;
   - **every LAN address the runbook tells a developer to dial, against the ufw
     rule in `bootstrap/playbooks/configure_network.yml` that permits it**
     (`:13` for 8500, `:18` for 8200, `:21` for 4646). The test asserts both
     halves: the port appears in the playbook, **and** its `from_ip` is still
     `192.168.0.0/16`. When N4 narrows `from_ip`, the second half goes red.

   **Why `haproxy.hcl` alone is not enough, and this is the failure the previous
   version of this requirement could not see.** `haproxy.hcl:134` will still
   read
   `server vault1 192.168.2.30:8200` after N4 closes 8200 to the LAN, because
   haproxy dials that backend from `firebat` itself and nothing about N4 changes
   it. Pin the developer's address against `haproxy.hcl` and every assertion
   stays green while the advice goes false. That is A1's diagnosis word for
   word: "The anchors still resolve — it is the surrounding claims that went
   false"
   (`.loop/archive/A1-audit-plan-premise-sweep/plan.md:39-40`), reproduced by a plan
   written to prevent it. `haproxy.hcl` is authority for **how the edge reaches
   a backend**. `configure_network.yml` is authority for **whether a developer
   can reach it**. The runbook makes claims of the second kind, so it is pinned
   against the second file.

   Two consequences the implementer must honor:
   - **`.devcontainer/.env` cannot be an anchor.** It is gitignored
     (`.gitignore:2`), so it does not exist in a fresh checkout or a worktree.
   - **The loopback route needs no anchor of this kind**, because it crosses no
     rule. Pin its port only, against the same listener config as the edge.

   A test that only asserts "the text is non-empty" does not satisfy this
   requirement, and neither does one that pins only what cannot change.
5. **The runbook text is the single copy.** It lives inside the package as a
   markdown file loaded with `importlib.resources`, so an installed CLI outside
   a checkout still prints it. `docs/` gets a pointer to the command, never a
   second copy: two copies is how `docs/credential-rotation.md` happened.
   Rationale for package data over a repo-relative `docs/` path: a
   `uv tool install`ed CLI has no repo to read from.
6. **Prose gates apply to the printed text.** It is user-facing prose under
   `.claude/rules/plain-language.md`, and the markdown file is a doc under
   `.claude/rules/slop-scan-for-docs.md` (Layer 0 hallucination check: every
   backticked path, command and URL in it must resolve to a real thing, which
   requirement 4 partly automates).
7. **Tests are mandatory** (`.claude/rules/python-testing.md`): run through
   `uv run pytest`, mirror the source tree, no bare `pytest`. Any new
   dependency goes in via `uv add` (`.claude/rules/uv-installer.md`).
8. **Probes are read-only, credential-free, time-bounded and non-fatal.** No
   probe may raise out of the command, and a failed probe degrades to printing
   the whole runbook rather than to a stack trace or an empty screen.
9. **A probe reports what it observed, never a cause it cannot see.** The output
   distinguishes three findings, and the wording of each is part of the
   deliverable:
   - **the edge answers, the LAN addresses do not** — say "the direct LAN
     addresses did not answer but the edge did, so the services are up. This
     is what a firewall change looks like, not an outage" and point at
     requirement 3's SSH route. Post-N4 this becomes the everyday result;
   - **nothing answers, including the edge** — say the cluster or your own
     connectivity is the suspect, in that order of cheapness to check, and lead
     the reader to the prelude;
   - **a service answers and reports a bad state** (Vault sealed, Consul with no
     leader) — report the state, and name the section that treats it.

   The banned output is a bare "Vault unreachable". Three probes going dark at
   once while the edge answers is the signature of a policy change, and saying
   "unreachable" there sends the reader to fix a cluster that is fine.
10. **Adversarial review before done** (`.claude/rules/adversarial-reviews.md`).

## 7. Code surface

`<pkg>` = the CLI package root D1 creates. Resolve it from
`.loop/archive/D1-cli-package-skeleton/plan.md` before writing.

- `<pkg>/src/<module>/commands/breakglass.py` **(new)** — the command. Loads
  the runbook via `importlib.resources`, runs the probes (Q2), prints. Register
  it with whatever command-registration mechanism D1 established; do not invent
  a second one.
- `<pkg>/src/<module>/commands/breakglass_runbook.md` **(new)** — the canonical
  runbook text, shipped as package data. Sections per requirement 2, addresses
  per requirement 3, style per §"House style for this kind of page" (guards with
  stated reasons, verification commands with expected values).
- `<pkg>/pyproject.toml` — package-data / `include` entry so the markdown file
  ships in the wheel. Only this line; no other edit.
- `<pkg>/tests/commands/test_breakglass.py` **(new)** — output shape, section
  coverage, and the credential-boundary canary tests.
- `<pkg>/tests/commands/test_breakglass_runbook_facts.py` **(new)** — the
  requirement-4 drift tests, including the `configure_network.yml` reachability
  pins. Reads the repo files named there and asserts the runbook agrees. Needs
  the repo root: derive it from the test file's own path, and `pytest.skip` only
  if the repo files are genuinely absent (an installed wheel), never to dodge a
  mismatch. Read only tracked files: `.devcontainer/.env` is gitignored and is
  not available to pin against.
- `<pkg>/tests/commands/test_breakglass_probes.py` **(new)** — probe behavior
  under timeout, connection refused, non-2xx, and malformed response.
- `docs/breakglass.md` **(new, short)** — pointer page: what the command is,
  the credential boundary, and "the runbook itself lives in the CLI, run
  `localstack breakglass`". No duplicated steps.
- `README.md:30` — the line listing service docs in `docs/`. Add the pointer.

## 8. Tests & validation gates

### Repo gates (discovered, not assumed)
- **`just pre_commit`** (`justfile:17-19`, and the sole entry in
  `.loop/config.json` `gates`) must end all-Passed. Today's hooks
  (`.pre-commit-config.yaml`): `check-json`, `check-ast`,
  `check-merge-conflict`, `check-yaml --unsafe`, `debug-statements`,
  `detect-private-key`, `end-of-file-fixer`, plus local `nomad-fmt`,
  `terraform-fmt`, `terraform-validate`. Note `detect-private-key` runs over
  the runbook markdown, so no example key material may appear in it.
  `.pre-commit-config.yaml:1` excludes `^\.(claude|loop)/`, so this plan file
  is not linted; the CLI package is.
- **D1 landed the Python hooks.** `.pre-commit-config.yaml:37-72` now carries
  `ruff`, `ruff-format`, `mypy` (strict, `--config-file cli/pyproject.toml`)
  and `pytest`, all scoped `files: '^cli/'` and invoked through
  `uv run --project cli`. The runbook markdown is outside `^cli/` so ruff and
  mypy do not touch it, but `pytest` runs the CLI suite including this
  ticket's tests. `just pre_commit` runs all of them; do not add a duplicate.
- **`uv run --project cli pytest`** from the repo root, per
  `.claude/rules/python-testing.md`. D1 owns the pytest configuration
  (`cli/pyproject.toml`).

### Tests to add
In `test_breakglass.py`:
1. Every failure-mode section from requirement 2 appears in the output, by
   heading, asserted one per `pytest.mark.parametrize` case.
2. Every section that names a service names all three routes from requirement 3
   — the edge hostname, the SSH plus `127.0.0.1:<port>` route, and the LAN
   address — and the LAN address never appears without its condition. Assert
   the
   condition sentence, not just the three strings: a section may not contain
   `192.168.2.30:<port>` unless the same section also names
   `configure_network.yml` (or the wording the runbook standardizes on) and
   `N4-netsec-edge-only-service-access`.
3. **Credential canary (the guardrail test).** Set
   `VAULT_TOKEN=hvs.CANARYTOKEN`, `VAULT_UNSEAL_KEY_1=CANARYKEY1` (and 2, 3),
   `NOMAD_TOKEN=CANARYNOMAD`, `CONSUL_HTTP_TOKEN=CANARYCONSUL` with
   `monkeypatch.setenv`, run the command, and assert no canary appears in
   stdout, in stderr, or in any file the command wrote. Run it with probes on
   and probes off.
4. **No token-shaped string in the runbook text.** Assert the rendered output
   matches no `hvs\.`, `hvb\.`, `s\.[A-Za-z0-9]{24}` pattern.
5. **The command never opens the init file.** Assert `/opt/vault/init.json`
   appears in the output as literal text but that no filesystem read of it is
   attempted (monkeypatch `pathlib.Path.open` / `builtins.open` to raise on
   that path, or assert on a `unittest.mock` spy; a negative assertion here is
   `assert spy.mock_calls == []`, not `assert_not_called`, per the repo rule).
6. Exit code is stable and documented (Q4).

In `test_breakglass_runbook_facts.py`: one test per requirement-4 anchor.
Parse the source file, extract the value, assert the runbook contains it. Each
test must fail if the repo file changes, and each carries a self-check that the
parse found something, so a parser returning `None` cannot pass vacuously (the
guard-with-a-stated-reason habit from §"House style for this kind of page").

Two of these tests are the ones the previous version of this plan lacked, and
they are the reason requirement 4 changed:

- **The LAN reachability pin.** Parse
  `bootstrap/playbooks/configure_network.yml`
   for the entries covering 8200, 4646 and 8500 (`:13,18,21`). Assert each entry
   exists **and** that its `from_ip` is `192.168.0.0/16`. Then assert the
   runbook
   still prints the matching `192.168.2.30:<port>` address. When N4 narrows
   `from_ip` to node IPs, this test goes red and forces the runbook edit. Parse
   the YAML with the parser D1 standardized on rather than a regex, and fail
   loudly if the port is absent from the file entirely. An absent port and a
   narrowed port are both "the LAN route is gone" and both must fail.
- **The pin is not satisfiable by `haproxy.hcl` alone.** A test asserting that
   the LAN address appears in `haproxy.hcl` passes forever, because haproxy
   dials
   its backend from the same host N4 firewalls. Assert instead that the
   requirement-4 anchor set *contains* `configure_network.yml`, so a later
   simplification cannot quietly drop the only pin that can go red. State the
   reason in the failure message. Without it, the next reader deletes the test
   as
   redundant.

Every drift test's failure message says what it means and what to do: "N4 has
landed or the LAN rule changed — update the conditional LAN paragraph in
`breakglass_runbook.md`", not `AssertionError: False`. A failure message that
does not explain itself gets the test deleted, which is how the runbook goes
stale after all.

In `test_breakglass_probes.py`: for each probe, a timeout case, a
connection-refused case, a 503 case, a 200 case, and a garbage-body case.
Assert the command still prints the full runbook in every one. Plus the
requirement-9 rendering cases, which are the ones that matter post-N4:
edge 200 with all LAN probes refused must render the "this looks like a firewall
change" finding; everything refused including the edge must render the
"cluster or your own connectivity" finding; Vault 503 must render "reachable but
sealed". Mock at the HTTP boundary with the tool D1 standardized on; if D1 chose
`httpx` (already a repo dependency, `requirements.txt:3`), use `respx` per
`.claude/rules/python-testing.md`. Do not hand-roll patches and do not make a
live request.

### Doc gate
`docs/breakglass.md` and the runbook markdown both run the
`.claude/rules/slop-scan-for-docs.md` layers, Layer 0 (every backticked path,
command and URL resolves) first.

## 9. Risk assessment
- **Blast radius: near zero at runtime.** The command reads local package data
  and, optionally, makes unauthenticated GETs. It changes no cluster state and
  no repo state. Reversibility is deleting one command and one markdown file.
- **The real risk is a runbook that is wrong when it is needed.** A confidently
  printed wrong address or a command that fails at 3am is worse than no
  runbook, because it is trusted precisely when nobody has the patience to
  verify it. Requirement 4 exists for this and is the part most likely to be
  under-delivered as a token "the text is non-empty" test.
- **The named instance of that risk is N4.**
  `N4-netsec-edge-only-service-access`
  deletes the LAN route this runbook would otherwise lean on, and a plan review
  caught this ticket relying on that route in requirement 3, in three of four
  probes, and in a 100%-threshold eval row. The correction is spread across
  §"Relationship to N4", requirement 3's three-way address model,
  requirement 4's
  `configure_network.yml` pin, requirement 9's probe wording, and Q2. If any one
  of those is dropped during implementation, the ticket ships the original
  defect. Treat them as one change, not five.
- **A drift gate can be a spelling check.** Pinning a fact to a file that will
  never contradict it produces a permanently green test and zero information.
  `haproxy.hcl:134` is exactly such a file for the developer's LAN address.
  Every
  new anchor added later must answer: what change makes this go red? If nothing
  does, it is decoration.
- **Second risk: a credential leaking through a convenience.** The likeliest
  route is not a deliberate token read but an incidental one: passing
  `os.environ` into a subprocess, echoing the caller's env in a diagnostic
  dump, logging a request with headers, or including the caller's `VAULT_ADDR`
  in an error message that also carries a token-bearing URL. The canary test
  covers the observable surface; the non-goals list covers the rest.
- **Third risk: probes lie.** A probe that times out because the developer's
  own connectivity is down will report "Vault unreachable" and send them chasing
  the cluster. Post-N4 a second cause joins it: the LAN probes go dark because
  ufw stopped admitting the caller, with every service healthy. Requirement 9
  makes the output distinguish "probe failed", "firewall closed this route" and
  "service is down", and the prelude puts "check your own connectivity first"
  ahead of every other section.
- **Drift tests are load-bearing and coupled to repo layout.** A future ticket
  that moves `bootstrap/inventory/cluster.ini` or renames the `unseal_vault`
  recipe will fail these tests. That is the intended behavior, and the failure
  message must say so plainly, or the next person will delete the test.

## 10. Subtickets (ordered)
1. Runbook markdown: all sections from requirement 2, requirement 3's three-way
   address model throughout, no probes yet. Read
   `.loop/plans/N4-netsec-edge-only-service-access.md` first, per §"Relationship
   to N4". Style per §"House style for this kind of page".
2. `breakglass` command: load the package-data file, print it, register it.
   Plus the requirement-4 drift tests, including the `configure_network.yml`
   reachability pin. This is the first shippable state.
3. Credential-boundary tests: canaries, token-pattern scan, no-open assertion.
4. Probes (Q2 and Q6), edge-first, with the timeout / refused / non-2xx /
   garbage cases and requirement 9's three findings.
5. `docs/breakglass.md` pointer plus the `README.md:30` line. Slop scan.
6. Adversarial review (`.claude/rules/adversarial-reviews.md`).

## 11. Open questions

> **All questions in this section were resolved on 2026-07-31 in
> `## Forks resolved, 2026-07-31` at the end of this plan.** Each followed the
> recommendation recorded below, so these read as history rather than as
> pending decisions.


- **Q1 — May the command invoke `just unseal_vault`, given that unsealing is
  not the root token?** *Recommendation: no. Print the command, do not run it.*
  The reasoning is specific to this repo rather than general caution:
  `scripts/unseal_vault.sh:6-9` refuses unless `VAULT_TOKEN` is set alongside
  the three unseal keys, so invoking it requires the CLI to run in, and pass
  along, an environment holding the root token and every unseal key. That
  collides head-on with the credential boundary for a saving of one typed
  command. If the operator later wants this, the honest prerequisite is fixing
  the script's token guard first, which is out of scope here.
- **Q2 — Diagnose before printing, or print only?** *Recommendation: diagnose
  by default, with `--no-probe` to skip.* "Which of these is my problem" is the
  real question during an outage, and the probes are cheap, read-only and
  credential-free.

  **Probe the edge first, because the edge is the path that survives N4.** All
  unauthenticated, all with a ~3s timeout. Measured 2026-07-31 unless marked.

  *Tier 1, the edge — these three decide the headline finding:*
  - `GET https://vault.lab.orangecluster.nl/v1/sys/health` — 200 today, clean
    TLS. Vault answers 503 sealed and 501 uninitialized by documented default
    (`sealedcode`, `uninitcode`), so one call separates sealed from unreachable
    with no token. Treat any of the documented codes as "answered"; do not test
    for 200 exactly, since a standby returns 429 and is still reachable.
  - `GET https://nomad.lab.orangecluster.nl/v1/agent/health` — 200 today.
  - `GET https://consul.lab.orangecluster.nl/v1/status/leader` — 200 today,
    body `"192.168.2.30:8300"`. See Q6.

  *Tier 2, the direct LAN addresses — secondary, and interpreted, not reported
  raw:* the same three paths on `http://192.168.2.30:{8200,4646,8500}`. All 200
  today from this dev container. Their only job is to answer "is this the edge
  or
  the whole cluster", and after N4 they answer "the firewall no longer admits
  me". Requirement 9 governs how each combination is worded. Never let a tier-2
  failure alone produce the word "unreachable".

  The old probe set was tier 2 only, with a single TLS handshake against the
  edge. That is backwards: it made the surviving path the afterthought and the
  disappearing path the evidence.

  Diagnosis reorders and highlights sections. It never suppresses one, so a
  wrong diagnosis costs attention, not information.
- **Q3 — Should the runbook name `/opt/vault/init.json` as the location of the
  unseal keys as well as the root token?** *Recommendation: yes.* It is a path,
  not a secret, it is already public in this repo
  (`bootstrap/roles/vault_server/tasks/main.yml:116-123`), and during an
  outage with an empty dev-container env it is the only unseal path that
  works. Naming a file the operator must `sudo` to read does not cross the
  boundary; reading it would.
- **Q4 — Exit code?** *Recommendation: always 0.* The command is
  documentation. A non-zero exit invites a wrapper to treat it as a failure and
  swallow the output, which is the one thing that must not happen. If probes
  should influence the exit code, that is a deliberate opt-in flag, not the
  default.
- **Q5 — Does `docs/breakglass.md` need to exist at all, given requirement 5's
  single-copy rule?** *Recommendation: yes, as a pointer only, ten lines or
  fewer.* Someone browsing `docs/` on GitHub will not discover a CLI command
  otherwise. The rule it must not break is duplicating any step.
- **Q6 — Consul probe shape.** *Recommendation: send the HTTP GET, and fall
  back to a TCP connect only on 401 or 403.* This reverses the earlier
  recommendation, which rested on a premise that measurement disproved.

  The config reading was right and the behavioral conclusion was wrong. Consul
  ACLs are on with `default_policy = "deny"`
  (`bootstrap/roles/consul_server/templates/consul.hcl.j2:25-27`), so a 403 on
  an
  unauthenticated read looked likely. Measured 2026-07-31, it does not happen:
  `GET http://192.168.2.30:8500/v1/status/leader` returns **200** with the body
  `"192.168.2.30:8300"`, `GET /v1/agent/self` returns **200**, and the same call
  through the edge returns 200. The anonymous token evidently carries read
  policy.

  A TCP connect is safe but strictly weaker than the evidence available. It
  cannot tell "Consul answers and has a leader" from "Consul answers with no
  leader", and Consul is Vault's storage backend and both Terraform state
  backends (`vault.hcl.j2:11-15`, `deployments/infrastructure/backend.tf:2`),
  so a lost leader is the
  failure that explains everything else the reader is seeing. Discarding that
  signal to dodge a 403 that does not occur costs real diagnostic value during
  exactly the outage this command serves.

  The fallback still matters, because ACL policy can change without this repo
  changing: on 401 or 403 the probe degrades to "reachable, not authorized to
  read the leader" and reports that, rather than inventing an outage. Sending a
  token to get a nicer answer stays forbidden by the non-goals either way.
- **Q7 — D1's layout is settled.** D1 is `done` and `cli/pyproject.toml` is
  tracked, so every `<pkg>` anchor in §Code surface resolves to
  `cli/src/localstack_cli`. *Recommendation: the implementer confirms the
  path against D1's shipped tree as step 0 and raises
  `out-of-scope-fix-needed` if D1 chose a structure where these files have no
  natural home, rather than inventing a parallel one.*
- **Q8 — Should the runbook cover "I cannot reach the cluster at all" (tailnet
  down, DNS down)?** *Recommendation: yes, as the prelude, ahead of every
  service section.* Developers reach the cluster over Tailscale
  (`CLAUDE.md`, "Localstack public address"), and a dead tailnet presents
  exactly like a dead cluster. Two lines: confirm your own connectivity, then
  read on. The prelude must be precise about what the tailnet actually carries:
  SSH to `firebat` on 22 and the edge on 443, not the API ports, and only to the
  manager, since `configure_tailscale.yml:40-47` runs the role on
  `hosts: manager` and `:49-58` stops `tailscaled` on every worker.
- **Q9 — Does D5 depend on `N4-netsec-edge-only-service-access`?**
  *Recommendation: no hard `depends_on`; write the runbook so N4 cannot falsify
  it, and pin the LAN address so N4 landing turns a test red.* N4 closes 4646,
  8200 and 8500 to the LAN and resolved its own Q3 as "no devcontainer
  exception — direct access is what the runbook's SSH path is for"
  (N4 Q3, resolved), which makes D5's SSH plus loopback route N4's own
  recovery plan. Blocking a break-glass runbook behind the riskiest change in
  the
  repo, itself blocked behind N3, inverts the order: N4 wants this runbook
  written before its dangerous step, not after. The full argument and the three
  reasons are in §"Relationship to N4"; requirements 3, 4 and 9 and Q2 carry the
  implementation. If the operator prefers the hard edge instead, the change is
  small — add N4 to `depends_on` and delete requirement 3's conditional LAN
  paragraph outright — but the pinning in requirement 4 stays either way.

## Forks resolved, 2026-07-31

All nine resolve on their recorded recommendations. **Q2, Q6 and Q9 were
re-decided on 2026-07-31 after a plan review measured the cluster and falsified
the premises the first two rested on**; the recommendations above are the
re-decided ones, and this section states what changed. Two others are worth
restating because they are the security-shaped ones:

- **Q1 → no, print the command, never run it.** `scripts/unseal_vault.sh`
  refuses unless `VAULT_TOKEN` is set alongside the three unseal keys, so
  invoking it would require this CLI to hold an environment carrying the root
  token and every unseal key. That collides with the credential boundary that
  is this ticket's whole point, and it buys one typed command. If it is ever
  wanted, the honest prerequisite is fixing the script's token guard first.
- **Q3 → yes, name `/opt/vault/init.json`.** It is a path, not a secret, it is
  already in the repo at `bootstrap/roles/vault_server/tasks/main.yml:116-123`,
  and during an outage with an empty devcontainer environment it is the only
  unseal route that works. Naming a file the operator must `sudo` to read does
  not cross the boundary. Reading it would, and this ticket never does.

The three re-decided on measurement:

- **Q2 → diagnose by default with `--no-probe`, and probe the edge first.** The
  original set was three LAN probes plus one TLS handshake at the edge. N4
  deletes the LAN route on purpose, so that set made the disappearing path the
  primary evidence. The edge now carries tier 1 (all three verified 200 on
  2026-07-31, clean TLS), the LAN addresses drop to tier 2, and requirement 9
  governs how the combinations are worded so a closed firewall never reads as an
  outage.
- **Q6 → send the HTTP GET, and fall back to a TCP connect on 401 or 403.** The
  earlier answer was "TCP connect, because ACLs may 403 us". Measured, they do
  not: `/v1/status/leader` returns 200 with the leader address and
  `/v1/agent/self` returns 200, both unauthenticated, despite
  `default_policy = "deny"`. The earlier
  recommendation was safe but bought that safety by discarding the leader
  signal, and Consul losing its leader is the fact that explains a sealed Vault
  and a dead Terraform at once. The fallback survives for the day the ACL policy
  tightens.
- **Q9 → no hard `depends_on` on N4.** Instead the runbook is written so N4
  cannot falsify it, and requirement 4 pins the LAN address to the ufw rule that
  permits it, so N4 landing turns a test red and forces the runbook edit. This
  is
  the fix for the defect that failed the first plan review: D5 leaned on a LAN
  path that a higher-priority ticket exists to delete, and its drift gate was
  pinned only to files that N4 does not touch.

The rest as recommended: **Q4** always exit 0, because the command is
documentation and a non-zero exit invites a wrapper to swallow the output;
**Q5** keep `docs/breakglass.md` as a ten-line pointer that duplicates no step;
**Q8** open with the connectivity prelude, since a dead tailnet presents exactly
like a dead cluster — stating what the tailnet actually carries (SSH on 22 and
the edge on 443, manager only) rather than implying the API ports.

**Q7 → resolved.** D1 is `done` and `cli/pyproject.toml` is tracked: package
under `cli/`, src layout at `cli/src/localstack_cli`, `typer` at runtime.
Resolve the `<pkg>` anchors to that path at pickup, and raise
`out-of-scope-fix-needed` rather than inventing a parallel structure if they
do not fit.

## Premises / assumptions

- **P1.** `scripts/unseal_vault.sh` requires `VAULT_TOKEN` alongside the
  three unseal keys, so invoking it from the CLI would carry the root token
  through the CLI's code path.
  `Evidence: scripts/unseal_vault.sh:6-9` is a five-way `-z` guard including
  `VAULT_TOKEN`, exiting 1 at `:8`. The three `vault operator unseal` calls
  (`:11-13`) need no token. `justfile:33-34` runs the script; the root
  `justfile` has no `set dotenv-load`, so values come from ambient env via
  `--env-file .devcontainer/.env` (`.devcontainer/devcontainer.json:37-39`).

- **P2.** `/opt/vault/init.json` is the path where Ansible stores both the
  unseal keys and the root token, and naming it leaks nothing.
  `Evidence: bootstrap/roles/vault_server/tasks/main.yml:116-123` is the
  `Store Vault init keys` copy task writing `dest: /opt/vault/init.json`,
  `owner: vault`, `mode: '0600'`. The unseal keys are at `:158` and the root
  token via `bootstrap/roles/nomad_server/tasks/main.yml:191,196` (`slurp` +
  `from_json`). The path appears in six places across two tracked files.

- **P3.** An unauthenticated `GET /v1/sys/health` separates sealed (503) from
  uninitialized (501) from active (200), so one probe tells the runbook which
  failure the operator is in without a token.
  `probe: GET http://192.168.2.30:8200/v1/sys/health -> 200` measured
  2026-07-31, no token sent, full body returned. The 503-sealed and
  501-uninitialized codes are the documented `/sys/health` defaults
  (`sealedcode=503`, `uninitcode=501`); a standby returns 429, so the probe
  treats any documented code as "answered", not 200 exactly.

- **P4.** Nomad `/v1/agent/health` answers unauthenticated, so the probe can
  report Nomad's state without a token.
  `probe: GET http://192.168.2.30:4646/v1/agent/health -> 200` measured
  2026-07-31, body `{"client":{"ok":true},"server":{"ok":true}}`. Also 200
  through the edge: `https://nomad.lab.orangecluster.nl/v1/agent/health`.

- **P5.** Consul answers unauthenticated despite `default_policy = "deny"`,
  so an HTTP GET yields the leader address a TCP connect cannot.
  `probe: GET http://192.168.2.30:8500/v1/status/leader -> 200` body
  `"192.168.2.30:8300"` measured 2026-07-31;
  `GET /v1/agent/self -> 200`. Consul ACLs are on
  (`bootstrap/roles/consul_server/templates/consul.hcl.j2:25-27`), but the
  anonymous token carries read policy. The probe falls back to a TCP connect
  on 401 or 403 for the day the policy tightens.

- **P6.** A TLS handshake against the edge separates "edge down" from
  "cluster down", so the edge probe is the tier-1 signal.
  `probe: GET https://vault.lab.orangecluster.nl/v1/sys/health -> 200` with
  `ssl_verify_result=0` measured 2026-07-31. An unknown Host returns 307, not
  a fall-through to a backend. The edge proxies the API, not just the UI.

- **P7.** The anti-drift gate is mechanically testable and catches anchor
  drift, but cannot catch claim drift on its own.
  `UNCERTAIN.` Pinning a fact to a file that will not change produces a
  permanently green test. `haproxy.hcl:134` will still read
  `server vault1 192.168.2.30:8200` after N4 closes 8200 to the LAN, because
  haproxy dials its backend from the same host. Requirement 4 adds
  `configure_network.yml` as the second pin so N4 narrowing `from_ip` turns
  the test red, but the gate remains a spelling check for claims the firewall
  does not govern. `Evidence: .loop/archive/A1-audit-plan-premise-sweep/plan.md:39-40`
  — "the anchors still resolve, it is the surrounding claims that went false".

- **P8.** The direct `192.168.2.30:<port>` addresses do not survive
  `N4-netsec-edge-only-service-access`, so the runbook must not present them
  as an unqualified escape hatch.
  `Evidence: .loop/plans/N4-netsec-edge-only-service-access.md` §Code surface
  narrows `from_ip` for 4646, 8200, 8500; R3 deletes the broad rule; Q3
  resolved as "no devcontainer exception — direct access is what the
  runbook's SSH path is for"; §Risk assessment names
  `NOMAD_ADDR=http://127.0.0.1:4646` over SSH as the escape. Requirement 3's
  three-way address model and requirement 4's `configure_network.yml` pin
  carry this.

- **P9.** `tmp/F9-MIGRATION.md` is untracked, so a worktree implementer will
  not have it.
  `Evidence: tmp` is the first line of `.gitignore`; `git ls-files
  --error-unmatch tmp/F9-MIGRATION.md` errors. `git worktree add` checks out
  tracked files only. The two lessons the plan needs (the `test -s` guard and
  the non-vacuous assertion) are inlined in §"House style for this kind of
  page" so the implementer does not need the file.
