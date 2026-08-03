---
verdict: pass
plan: 9c097d322e02d7064115997d3fdaf76381e584f0f2905367353654ae6110c696
---

# Plan review verdict: D5-cli-breakglass (second pass)

Pass id: `plan-validator`. Fingerprint verified against
`.loop/plans/D5-cli-breakglass.md` (sha256 matches the briefing).

This is the second review pass. The first pass returned
`pass-with-required-fixes` with four required fixes. All four have been
applied and are re-verified below as holding. The premise is now SOUND and
the contract hygiene is clean.

## Deterministic floor

`loopctl verify-plan D5-cli-breakglass` returned `valid` with one warn:
20/24 Context/Requirements claims carry no `path:line` anchor. That is the
harness's anchor-count heuristic, not a hard fail. The un-anchored claims
are prose-dense by design: the N4 section is cited by section name on
purpose ("Cite N4 by section name, never by line number", plan `:149-153`),
and the house-style lessons are inlined rather than anchored to the
gitignored `tmp/F9-MIGRATION.md`. No hard-fail. Proceeded to
falsification.

## Premise verdict: SOUND

All four previously-required fixes hold, and all nine stated premises hold
against the repo and the live cluster.

### The four fixes re-verified

1. **Gates claim (the most dangerous one last time).** HOLDS.
   `.pre-commit-config.yaml:37-72` carries `ruff` (`:37-45`),
   `ruff-format` (`:46-51`), `mypy` strict with
   `--config-file cli/pyproject.toml` (`:52-65`), and `pytest`
   (`:66-73`), all `files: '^cli/'` and invoked through
   `uv run --project cli`. Section 8 (`:425-430`) and the Q7 resolution
   (`:746-750`) now state D1 landed these and no longer claim "no
   ruff/mypy hook". `cli/pyproject.toml` confirms `strict = true` under
   `[tool.mypy]`.

2. **justfile anchor for `unseal_vault`.** HOLDS. `justfile:33-34` reads
   `unseal_vault:` / `bash scripts/unseal_vault.sh`. The plan cites
   `justfile:33-34` at P1 (`:759`) and Context (`:126`).

3. **Stale "no pyproject.toml".** HOLDS. `git ls-files --error-unmatch
   cli/pyproject.toml` succeeds; the package tree
   `cli/src/localstack_cli/` is tracked (40 files under `cli/`). Package
   section (`:44-52`) and Q7 (`:663-668`, `:746-750`) now say D1 is done
   and `<pkg>` resolves to `cli/src/localstack_cli`. Ledger:
   `D1-cli-package-skeleton` `stage=done`.

4. **README docs-listing line.** HOLDS. `README.md:30` is the
   "Service-level docs are in `docs/` ..." line. The plan cites
   `README.md:30` at `:411` and `:568`.

### Per-assumption findings

- **P1 — `unseal_vault.sh` requires `VAULT_TOKEN` alongside the three
  unseal keys.** HOLDS. `scripts/unseal_vault.sh:6-9` is a five-way `-z`
  guard over `VAULT_UNSEAL_KEY_1..3`, `VAULT_ADDR`, `VAULT_TOKEN`, exit 1
  at `:8`. The three `vault operator unseal` calls (`:11-13`) take no
  token. `justfile:33-34` runs the script; the root `justfile` has no
  `set dotenv-load` (contrast `bootstrap/justfile:3`), so values come
  from ambient env via `--env-file .devcontainer/.env`
  (`.devcontainer/devcontainer.json:37-39`). Q1's "print, never run"
  reasoning follows from this.

- **P2 — `/opt/vault/init.json` holds both secrets; naming the path
  leaks nothing.** HOLDS.
  `bootstrap/roles/vault_server/tasks/main.yml:116-123` is the `Store
  Vault init keys` copy to `dest: /opt/vault/init.json`, `owner: vault`,
  `mode: '0600'`. Unseal keys read back at `:135-158` (`slurp` +
  `from_json`, `unseal_keys_b64[:3]` at `:158`). Root token read at
  `bootstrap/roles/nomad_server/tasks/main.yml:189-196` (`slurp` +
  `from_json`, `.root_token` at `:196`). The path, not its contents, is
  what the runbook prints.

- **P3 — unauthenticated `GET /v1/sys/health` separates sealed/uninit/
  active.** HOLDS. Live probe
  `GET http://192.168.2.30:8200/v1/sys/health` returned 200 (no token
  sent). Edge
  `GET https://vault.lab.orangecluster.nl/v1/sys/health` returned 200.
  The 503/501/429 documented codes are the `/sys/health` defaults; the
  plan treats any documented code as "answered", not 200 exactly.

- **P4 — Nomad `/v1/agent/health` answers unauthenticated.** HOLDS.
  Live `GET http://192.168.2.30:4646/v1/agent/health` returned 200;
  edge `GET https://nomad.lab.orangecluster.nl/v1/agent/health`
  returned 200.

- **P5 — Consul answers unauthenticated despite
  `default_policy = "deny"`.** HOLDS. Live
  `GET http://192.168.2.30:8500/v1/status/leader` returned 200 with
  body `"192.168.2.30:8300"`. Edge
  `GET https://consul.lab.orangecluster.nl/v1/status/leader` returned
  200 with the same body.
  `bootstrap/roles/consul_server/templates/consul.hcl.j2:25-27`
  confirms `acl { enabled = true; default_policy = "deny" }`. The
  anonymous token carries read policy. Q6's 401/403 fallback
  (`:636-662`) is the right belt-and-braces for the day that tightens.

- **P6 — edge TLS handshake separates edge-down from cluster-down.**
  HOLDS. Live `GET https://vault.lab.orangecluster.nl/v1/sys/health`
  returned 200 (clean TLS). The edge proxies the API, not just a UI.

- **P7 — the anti-drift gate is mechanically testable but cannot catch
  claim drift on its own.** HOLDS, and the plan labels it `UNCERTAIN`
  itself. `haproxy.hcl:134` reads
  `server vault1 192.168.2.30:8200 check` and will keep reading it
  after N4 closes 8200 to the LAN, because haproxy dials from `firebat`
  itself. Requirement 4's second pin against `configure_network.yml` is
  the one that can go red, and the plan states this explicitly
  (`:324-337`, P7 at `:803-810`). The A1 diagnosis it cites is real:
  `.loop/archive/A1-audit-plan-premise-sweep/plan.md:39-40` reads "The
  anchors still resolve — it is the surrounding claims that went
  false".

- **P8 — direct `192.168.2.30:<port>` addresses do not survive N4.**
  HOLDS. `.loop/plans/N4-netsec-edge-only-service-access.md` §Code
  surface (`:418`) narrows `from_ip` for 4646, 8500 and
  `20000:32000`; R3 (`:352`) deletes the broad rule; Q3 resolved as
  "no devcontainer exception" (`:663`, `:707`); §Risk assessment
  (`:466-467`) names `NOMAD_ADDR=http://127.0.0.1:4646` over SSH as the
  escape. Requirement 3's three-way address model and requirement 4's
  `configure_network.yml` pin carry this.

- **P9 — `tmp/F9-MIGRATION.md` is untracked, so a worktree implementer
  will not have it.** HOLDS. `git ls-files --error-unmatch
  tmp/F9-MIGRATION.md` errors ("did not match any file(s) known to
  git"); `.gitignore:1` is `tmp`. The two lessons (the `test -s` guard
  with stated reason, and the non-vacuous-parse rule) are inlined in
  §"House style for this kind of page" (`:215-225`).

### Implicit load-bearing assumptions checked

- **D1 is done and the CLI package is real.** HOLDS. Ledger:
  `D1-cli-package-skeleton` `stage=done`. `cli/pyproject.toml` tracked
  with `typer>=0.27.0`, `rich>=15.0.0`, `click>=8.0` at runtime;
  `mypy`, `pytest`, `ruff` in dev. `cli/src/localstack_cli/` already
  has commands (`login`, `logout`, `whoami`, `env`, `token`, `config`),
  so the registration mechanism D1 established exists for breakglass to
  join.

- **D5 takes no hard `depends_on` on N4 — sound.** HOLDS. Ledger:
  `N4-netsec-edge-only-service-access` `stage=planning`,
  `dependencies=['N3-netsec-converging-firewall-provisioner']`; N3 is
  `stage=blocked`. N4 is not close. Gating a break-glass runbook behind
  the riskiest change in the repo, itself blocked behind N3, would
  invert the order. The plan's design (write the runbook so N4 cannot
  falsify it, pin the LAN address so N4 landing turns a test red) is
  sound and is the fix for the defect that failed the first review.

- **Three-way address model is true today.** HOLDS. Vault listener
  binds `0.0.0.0:8200` plaintext
  (`bootstrap/roles/vault_server/templates/vault.hcl.j2:18-21`), so one
  service answers on edge (HAProxy `haproxy.hcl:100,111,133-134`),
  loopback (`127.0.0.1:8200`, used by Ansible at
  `bootstrap/roles/nomad_server/tasks/main.yml:203` and
  `bootstrap/playbooks/configure_tailscale.yml:22`), and direct LAN
  (`192.168.2.30:8200`, permitted by
  `bootstrap/playbooks/configure_network.yml:18` from
  `192.168.0.0/16`). Firewall default-incoming-deny at
  `bootstrap/roles/firewall/tasks/main.yml:7-13`. Tailnet gets 22
  (`configure_network.yml:11`) plus 80/443/8404
  (`deployments/infrastructure/services.tf:188,190,192`), Grafana 3000
  (`:222`) and 8080 (`:231`), no API port.
  `configure_tailscale.yml:40-47` runs the role on `hosts: manager`
  only; `:49-58` stops `tailscaled` on workers.

- **HAProxy is a Nomad job pinned to `firebat`, single Nomad/Consul
  server.** HOLDS. `haproxy.hcl:6-9` constraint on hostname `firebat`;
  `nomad.hcl.j2:31` `bootstrap_expect = 1`;
  `consul.hcl.j2:17` `bootstrap_expect = 1`. Sealed Vault takes the
  edge: `haproxy.hcl:39,62-72` `vault {}` template with
  `change_mode = "restart"`, `:96` binds `*:443 ssl crt
  /secrets/haproxy.pem`.

- **Consul is Vault's storage and both Terraform backends.** HOLDS.
  `vault.hcl.j2:11-15` `storage "consul"`;
  `deployments/infrastructure/backend.tf:2` and
  `deployments/applications/backend.tf:2` both `backend "consul" {}`.

- **`docs/credential-rotation.md` is an unbuilt "Proposed Changes"
  page.** HOLDS. `:48` is `## Proposed Changes`; `:50` says create
  `bootstrap/playbooks/rotate_secrets.yml`; `bootstrap/justfile` has no
  `rotate` recipe (grep returns 0); the playbook file does not exist
  (`ls` errors). The plan's "keep it in sync is not an answer"
  argument (`:228-242`) is grounded.

- **`rescue-ssh.nomad.hcl` exists and needs working Nomad.** HOLDS.
  `rescue-ssh.nomad.hcl:1-12` is a `sysbatch` job. The plan places it
  in the "SSH dead but Nomad answers" branch only (`:137-141`).

- **CLIs installed in dev container.** HOLDS.
  `.devcontainer/Dockerfile:11-17` installs `nomad vault consul`.

- **`requirements.txt` httpx at :3, hvac at :5.** HOLDS. Confirmed.
  The plan's note that `httpx` is already a repo dependency (`:505`)
  is correct. `respx` is not yet in `cli/pyproject.toml` or
  `cli/uv.lock`, so the implementer must add it via `uv add` if D1
  chose httpx as the HTTP client. The plan says this at `:505-507`
  ("if D1 chose httpx ... use respx"). D1's plan names `typer` at
  runtime but does not commit an HTTP client for D5; the implementer
  resolves this at pickup. Minor implementation detail, not a premise
  break.

- **`.devcontainer/.env` is gitignored.** HOLDS. `.gitignore:2` is
  `.devcontainer/.env`. Requirement 4 forbids pinning against it
  (`:340-342`). `.devcontainer/.env.example` still advertises
  `localstack.local` hostnames (`:3,7,11`), confirming the drift
  instance the plan warns against copying (`:88-90`).

## Most dangerous assumption

P8 (the direct LAN addresses do not survive N4). If wrong, the runbook
could safely lean on `192.168.2.30:<port>` as an unqualified escape
hatch and the three-way address model, the `configure_network.yml` pin,
and requirement 9's probe wording would all be unnecessary machinery.
It is not wrong: N4's plan §Code surface, R3, Q3, and §Risk assessment
all confirm N4 exists to close those ports, and N4's own escape is the
same SSH-plus-loopback route D5 leads with. The plan's design — write
the runbook so N4 cannot falsify it — is the correct response and is
itself the fix that the first review demanded.

## Contract hygiene

- **Real code surface with resolved anchors.** Every `path:line` the
  plan cites was opened and confirmed: `haproxy.hcl:100-102,133-140`,
  `vault.hcl.j2:18-21`, `nomad_server/tasks/main.yml:189-196,203`,
  `vault_server/tasks/main.yml:116-123,153-160`,
  `consul.hcl.j2:25-27`, `configure_network.yml:13,18,21`,
  `firewall/tasks/main.yml:7-13`, `cluster.ini:1-3`,
  `configure_tailscale.yml:40-47,49-58`, `justfile:33-34`,
  `scripts/unseal_vault.sh:6-9,11-13`, `devcontainer.json:37-39`,
  `Dockerfile:11-17`, `services.tf:188,190,192,222,231`,
  `backend.tf:2` (both roots), `README.md:30`,
  `.pre-commit-config.yaml:37-72`, `cli/pyproject.toml` (strict mypy,
  typer, ruff, pytest), `requirements.txt:3,5`, `.gitignore:1-2`,
  `docs/credential-rotation.md:48,50,78-85`,
  `docs/tls-certificates.md:131`, `rescue-ssh.nomad.hcl:1-12`, A1 plan
  `:39-40`.

- **Discovered, not assumed, gates.** Section 8 matches the repo:
  `.loop/config.json` `gates = ['just pre_commit']`;
  `justfile:17-19` runs `pre-commit run --all-files`;
  `.pre-commit-config.yaml:1` excludes `^\.(claude|loop)/`;
  `:37-72` carries the four Python hooks scoped `^cli/`. The plan does
  not add a duplicate gate.

- **Explicit non-goals.** Section 5 lists the credential boundary hard
  (five prohibitions) and six further out-of-scope items.

- **Tests homed in the code surface.** Three test files named with
  their paths under `<pkg>/tests/commands/` (`:397-407`), plus
  `docs/breakglass.md` and `README.md:30`.

- **Forks surfaced.** All nine Q1-Q9 resolved in §"Forks resolved,
  2026-07-31" (`:693-750`), with Q2/Q6/Q9 marked as re-decided on
  measurement.

## Verdict

pass. The premise is SOUND. All four previously-required fixes hold.
All nine stated premises hold against the repo and the live cluster
(six probes returned 200, Consul leader body matches). The implicit
load-bearing assumptions — D1 done, N4 blocked behind N3, the
three-way address model, the single-box topology, the
credential-rotation staleness — hold. The most dangerous assumption
(P8) is confirmed by N4's own plan. Contract hygiene is clean. No
required fixes.