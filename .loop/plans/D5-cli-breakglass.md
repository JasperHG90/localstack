---
epic = "cli"
depends_on = ["D1-cli-package-skeleton"]
priority = 43
summary = "`localstack breakglass` prints the recovery runbook for a cluster you cannot authenticate to or reach, and optionally runs read-only reachability probes to say which failure you are in. It handles no credentials: it never reads, caches, prints or exports the Vault root token or the unseal keys. Tests pin every fact in the printed text against the repo file that states it, so drift fails a gate instead of going stale silently."
tags = ["cli", "recovery", "runbook", "security"]
---

# D5 — `localstack breakglass`: print the recovery runbook, touch no credentials

## Title
Add `localstack breakglass`, the command a developer runs when auth or
reachability to the cluster is broken. It prints a runbook, optionally probes
what is reachable, and handles no credential of any kind.

## Size / Effort
**Medium.** One command, one text asset, a handful of read-only probes. The
size comes from the drift tests (every fact in the printed text pinned to the
repo file that states it) and from probe failure handling, not from line count.

## Triggered by
Operator request, 2026-07-30, as part of the `cli` epic. The break-glass path
today is tribal knowledge: nothing in the repo tells a developer what to do
when Vault is sealed, the edge is down, or their token is dead.

## Operator decision, already settled — do NOT re-open
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

## Context (today's state)

### Package
- D1-cli-package-skeleton creates the CLI package. **No `pyproject.toml`,
  `uv.lock` or test tree exists anywhere in the repo today** (verified: `find`
  over the repo root finds none outside `.cache/` and `.loop/worktrees/`).
  Python deps today are a bare `requirements.txt` (`httpx` at :3, `hvac` at
  :5), Python pinned to 3.12 (`.python-version:1`).
- This ticket writes `<pkg>` for the package root D1 establishes. Read
  `.loop/plans/D1-cli-package-skeleton.md` §Code surface for the real path,
  the CLI framework, and the HTTP client before writing any file.
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
- **Two Vault addresses, both live.** The listener binds `0.0.0.0:8200`
  plaintext (`bootstrap/roles/vault_server/templates/vault.hcl.j2:18-21`), so
  `http://192.168.2.30:8200` works from the tailnet with no edge involved.
  Ansible uses `http://127.0.0.1:8200` on the manager itself
  (`bootstrap/roles/nomad_server/tasks/main.yml:203`). The dev container's own
  `VAULT_ADDR` is already the direct address, `http://192.168.2.30:8200`
  (`.devcontainer/.env:9`; likewise `NOMAD_ADDR` :3 and `CONSUL_HTTP_ADDR` :6).
  The `.env.example` still advertises the long-dead `localstack.local`
  hostnames (`.devcontainer/.env.example:3,7,11`), which is itself a drift
  instance worth not copying.
- **The edge is `https://vault.lab.orangecluster.nl`**, host-header routed by
  HAProxy to `192.168.2.30:8200` (`deployments/infrastructure/services/
  haproxy.hcl:100,111,133-134`). Nomad and Consul route the same way
  (`:101-102,112-113,136-140`).
- **"Edge down" and "Nomad down" share causes.** HAProxy is a Nomad job pinned
  by constraint to hostname `firebat` (`haproxy.hcl:6-9`), and Nomad runs a
  single server with `bootstrap_expect = 1`
  (`bootstrap/roles/nomad_server/templates/nomad.hcl.j2:13`). Consul is also
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
- **`just unseal_vault` exists and is the pointed-at path** (`justfile:21-23`
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
- **A real SSH break-glass artifact already exists**: `rescue-ssh.nomad.hcl:1-30`,
  a `sysbatch` job that appends a public key to every node's
  `authorized_keys` via a `/home:/host-home` mount. It needs a working Nomad,
  so it belongs in the "SSH is dead but Nomad answers" branch and nowhere else.

### House style for this kind of page
`/home/vscode/workspace/tmp/F9-MIGRATION.md` (uncommitted, written 2026-07-30)
is the quality bar. Note specifically: a `test -s` guard against an empty
backup (`:73`) with the reason it exists spelled out (`:78-81`), assertions
with expected values that can actually fail (`:100-105`), and an explanation of
why one check is not enough (`:107-111`). `docs/tls-certificates.md:131`
("Recovering a failed renewal") is the in-`docs/` precedent.

### Why "keep it in sync" is not an answer
`docs/credential-rotation.md` describes `bootstrap/playbooks/rotate_secrets.yml`
(`:50`) and `just rotate_tailscale` / `just rotate_github`
(`:78-85`) in the present tense. Neither exists: `bootstrap/playbooks/` has no
`rotate_secrets.yml`, and `bootstrap/justfile` has no rotation recipe. That
page went stale with nothing catching it. A1-audit-plan-premise-sweep exists
because the same failure hit thirteen plans, with the diagnosis that "the
anchors still resolve, it is the surrounding claims that went false"
(`.loop/plans/A1-audit-plan-premise-sweep.md:39-40`). A printed runbook is
documentation embedded in code and will rot the same way unless a gate catches
it. See Requirement 4.

## Non-goals / out of scope

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

## Requirements & restrictions

1. **`localstack breakglass` prints a runbook and exits.** No credential path,
   per the operator decision above.
2. **Distinct sections per failure mode, not one wall of text.** Cover, each
   with its own heading and its own commands: sealed Vault; expired or revoked
   token; edge down but cluster up; Nomad unreachable; Consul unreachable; lost
   local token cache. Plus a short prelude on reaching the manager at all
   (tailnet, `.ssh/id_rsa`, user `firebat` per `cluster.ini:2-3`).
3. **Both addresses, every time.** Any section naming a service names the edge
   hostname and the direct `192.168.2.30:<port>` address, and says which one to
   reach for when the other is suspect (`haproxy.hcl:133-140` for the mapping).
4. **Drift has to fail a gate.** Every fact-bearing token in the printed text
   is asserted, in a test, against the repo file that states it. At minimum:
   the manager IP and username against `bootstrap/inventory/cluster.ini`; the
   `unseal_vault` recipe name against the root `justfile`; the
   `/opt/vault/init.json` path against
   `bootstrap/roles/vault_server/tasks/main.yml`; each edge hostname and each
   `ip:port` backend against `deployments/infrastructure/services/haproxy.hcl`;
   the Vault port against
   `bootstrap/roles/vault_server/templates/vault.hcl.j2`. A test that only
   asserts "the text is non-empty" does not satisfy this requirement.
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
9. **Adversarial review before done** (`.claude/rules/adversarial-reviews.md`).

## Code surface

`<pkg>` = the CLI package root D1 creates. Resolve it from
`.loop/plans/D1-cli-package-skeleton.md` before writing.

- `<pkg>/src/<module>/commands/breakglass.py` **(new)** — the command. Loads
  the runbook via `importlib.resources`, runs the probes (Q2), prints. Register
  it with whatever command-registration mechanism D1 established; do not invent
  a second one.
- `<pkg>/src/<module>/commands/breakglass_runbook.md` **(new)** — the canonical
  runbook text, shipped as package data. Sections per requirement 2. Style bar:
  `/home/vscode/workspace/tmp/F9-MIGRATION.md` (guards with stated reasons,
  assertions with expected values).
- `<pkg>/pyproject.toml` — package-data / `include` entry so the markdown file
  ships in the wheel. Only this line; no other edit.
- `<pkg>/tests/commands/test_breakglass.py` **(new)** — output shape, section
  coverage, and the credential-boundary canary tests.
- `<pkg>/tests/commands/test_breakglass_runbook_facts.py` **(new)** — the
  requirement-4 drift tests. Reads the repo files named there and asserts the
  runbook agrees. Needs the repo root: derive it from the test file's own path,
  and `pytest.skip` only if the repo files are genuinely absent (an installed
  wheel), never to dodge a mismatch.
- `<pkg>/tests/commands/test_breakglass_probes.py` **(new)** — probe behavior
  under timeout, connection refused, non-2xx, and malformed response.
- `docs/breakglass.md` **(new, short)** — pointer page: what the command is,
  the credential boundary, and "the runbook itself lives in the CLI, run
  `localstack breakglass`". No duplicated steps.
- `README.md:29` — the line listing service docs in `docs/`. Add the pointer.

## Tests & validation gates

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
- **There is no ruff or mypy hook and no CI workflow gating Python today.** If
  D1 added either, run it too; do not add one in this ticket.
- **`uv run pytest`** from the CLI package root, per
  `.claude/rules/python-testing.md`. D1 owns the pytest configuration.

### Tests to add
In `test_breakglass.py`:
1. Every failure-mode section from requirement 2 appears in the output, by
   heading, asserted one per `pytest.mark.parametrize` case.
2. Every section that names a service names both the edge hostname and the
   direct address.
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
test must fail if the repo file changes; add a self-check that the parse found
something, so a parser returning `None` cannot pass vacuously (the
`test -s` lesson from `tmp/F9-MIGRATION.md:73,78-81`).

In `test_breakglass_probes.py`: for each probe, a timeout case, a
connection-refused case, a 503 case, a 200 case, and a garbage-body case.
Assert the command still prints the full runbook in every one. Mock at the HTTP
boundary with the tool D1 standardized on; if D1 chose `httpx` (already a repo
dependency, `requirements.txt:3`), use `respx` per
`.claude/rules/python-testing.md`. Do not hand-roll patches and do not make a
live request.

### Doc gate
`docs/breakglass.md` and the runbook markdown both run the
`.claude/rules/slop-scan-for-docs.md` layers, Layer 0 (every backticked path,
command and URL resolves) first.

## Risk assessment
- **Blast radius: near zero at runtime.** The command reads local package data
  and, optionally, makes unauthenticated GETs. It changes no cluster state and
  no repo state. Reversibility is deleting one command and one markdown file.
- **The real risk is a runbook that is wrong when it is needed.** A confidently
  printed wrong address or a command that fails at 3am is worse than no
  runbook, because it is trusted precisely when nobody has the patience to
  verify it. Requirement 4 exists for this and is the part most likely to be
  under-delivered as a token "the text is non-empty" test.
- **Second risk: a credential leaking through a convenience.** The likeliest
  route is not a deliberate token read but an incidental one: passing
  `os.environ` into a subprocess, echoing the caller's env in a diagnostic
  dump, logging a request with headers, or including the caller's `VAULT_ADDR`
  in an error message that also carries a token-bearing URL. The canary test
  covers the observable surface; the non-goals list covers the rest.
- **Third risk: probes lie.** A probe that times out because the developer's
  own tailnet is down will report "Vault unreachable" and send them chasing the
  cluster. The output must distinguish "probe failed" from "service is down",
  and the prelude must put "check your own connectivity first" ahead of every
  other section.
- **Drift tests are load-bearing and coupled to repo layout.** A future ticket
  that moves `bootstrap/inventory/cluster.ini` or renames the `unseal_vault`
  recipe will fail these tests. That is the intended behavior, and the failure
  message must say so plainly, or the next person will delete the test.

## Subtickets (ordered)
1. Runbook markdown, all sections from requirement 2, both addresses
   throughout, no probes yet. Style bar: `tmp/F9-MIGRATION.md`.
2. `breakglass` command: load the package-data file, print it, register it.
   Plus the requirement-4 drift tests. This is the first shippable state.
3. Credential-boundary tests: canaries, token-pattern scan, no-open assertion.
4. Probes (Q2 and Q6), with the timeout / refused / non-2xx / garbage cases and
   the "probe failed vs service down" distinction.
5. `docs/breakglass.md` pointer plus the `README.md:29` line. Slop scan.
6. Adversarial review (`.claude/rules/adversarial-reviews.md`).

## Open questions

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
  credential-free. Proposed set, all unauthenticated, all with a ~3s timeout:
  `GET http://192.168.2.30:8200/v1/sys/health` (Vault returns 503 sealed, 501
  uninitialized, 200 active, so this separates "sealed" from "unreachable" with
  no token at all); `GET http://192.168.2.30:4646/v1/agent/health` (Nomad);
  a TCP connect to `192.168.2.30:8500` (Consul, see Q6); and a TLS handshake
  against `https://vault.lab.orangecluster.nl` to separate "edge down" from
  "cluster down". Diagnosis reorders and highlights sections; it never
  suppresses one, so a wrong diagnosis costs attention, not information.
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
- **Q6 — Consul probe shape.** Consul ACLs are enabled cluster-wide, so an
  unauthenticated `GET /v1/status/leader` may return 403 rather than a leader.
  *Recommendation: probe with a TCP connect and treat any HTTP response,
  including 403, as "reachable".* Sending a token to get a nicer answer is
  forbidden by the non-goals.
- **Q7 — D1's layout is unknown at authoring time.** No `pyproject.toml` exists
  in the repo yet and `D1-cli-package-skeleton` is not in
  `.loop/ledger.json`. Every `<pkg>` anchor in §7 is therefore a shape, not a
  resolved path. *Recommendation: the implementer resolves them from D1's plan
  and its shipped tree as step 0, and raises `out-of-scope-fix-needed` if D1
  chose a structure where these files have no natural home, rather than
  inventing a parallel one.*
- **Q8 — Should the runbook cover "I cannot reach the cluster at all" (tailnet
  down, DNS down)?** *Recommendation: yes, as the prelude, ahead of every
  service section.* Developers reach the cluster over Tailscale
  (`CLAUDE.md`, "Localstack public address"), and a dead tailnet presents
  exactly like a dead cluster. Two lines: confirm your own connectivity, then
  read on.
