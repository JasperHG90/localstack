eval: D5-cli-breakglass

**Forks resolved 2026-07-31, then Q2, Q6 and Q9 re-decided the same day after a
plan review measured the cluster.** All nine open questions are settled, so the
rows below score a decided design. Four shape these rows: the command **prints**
the unseal command and never runs it (Q1); it **names** `/opt/vault/init.json`
without ever reading it (Q3); it probes the **edge first** and treats the LAN
addresses as a secondary signal (Q2); and it ships without waiting for
`N4-netsec-edge-only-service-access` by printing every address with the condition
that makes it work (Q9).

**Definition of Done:** `localstack breakglass` runs read-only, credential-free
reachability probes, then prints a recovery runbook with a distinct section per
failure mode. It **never** reads, caches, displays or exports a credential. The
runbook text lives once, inside the package, and every fact in it is asserted
against the repo file that states it.

**The address model is the part a review already broke once.** The first version
of this marker scored a 100%-threshold row requiring "BOTH the edge hostname and
the direct `192.168.2.30:<port>` address" in every service section.
`N4-netsec-edge-only-service-access` exists to close 4646, 8200 and 8500 to the
LAN, and resolved its Q3 as "no devcontainer exception — direct access is what
the runbook's SSH path is for". That row therefore scored
the command green for printing an address that N4 makes dead. Rows 4 and 6 below
are the replacement: three routes with their reachability classes, and a drift
pin against the ufw rule rather than against a file N4 cannot change.

**The credential boundary is the operator's decision and is load-bearing.**
Two alternatives were offered and rejected: fetching the root token over SSH,
and invoking `unseal_vault`. The reasoning is that a break-glass credential
passing through the CLI's code path and the developer's shell history is a
worse failure mode than typing a few commands by hand during an outage. Note
`scripts/unseal_vault.sh:6-9` refuses to run unless `VAULT_TOKEN` is set
alongside the three unseal keys, so "may the CLI invoke it" really means "may
the CLI hold the root token". Row 1 is the canary that makes the boundary
checkable rather than aspirational.

**The trap this command exists to avoid, and can itself become.** A printed
runbook is documentation embedded in code, and it goes stale silently. Rows 5,
6 and 7 are what make drift fail a gate. A test asserting only "the text is
non-empty" does not satisfy them, and neither does one pinned exclusively to
files the coming change cannot touch — see row 6.

| Behavior | Input | Expected | Scorer | Threshold |
| --- | --- | --- | --- | --- |
| **Canary: no credential can leak, ever** | Inject token-shaped values via `monkeypatch.setenv` into `VAULT_TOKEN`, `NOMAD_TOKEN`, `CONSUL_TOKEN`, `CONSUL_HTTP_TOKEN` and `VAULT_UNSEAL_KEY_1/2/3`; run every code path of the command; capture stdout, stderr and any file written | None of the injected values appears anywhere. This is the row that turns the operator's boundary into something a test can fail | deterministic check (no injected value in stdout, stderr or written files) | 100% |
| **Forbidden actions are absent from the source** | `grep -rnE "init\.json\|unseal\|VAULT_TOKEN\|subprocess\|paramiko\|\bssh\b" cli/src/localstack_cli/commands/breakglass.py cli/tests/commands/test_breakglass*.py` | No read of `/opt/vault/init.json`; no read of any token or unseal-key env var for any purpose; no SSH; no subprocess to `vault`, `nomad`, `ansible` or `terraform`; no credential attached to any probe. Mentions inside the runbook TEXT are expected and fine — this row is about executable code. **The row FAILS if the paths match no file.** D1 settles the layout as `cli/src/localstack_cli/` with a src layout (`D1-...md:113,183,185`), so the earlier placeholder `cli/localstack/breakglass*` matched nothing and would have scored a silent green on the credential boundary — the same vacuous-parse shape row 7 forbids. Resolve the paths against D1's shipped tree at pickup and correct them here if they moved | deterministic check (glob matches at least one file AND no credential access or shell-out in it) | 100% |
| Every failure mode gets its own section | Run the command; inspect the output headings | Distinct headings for: sealed Vault; expired or revoked token; edge down but cluster up; Nomad unreachable; Consul unreachable; lost local token cache. Plus a prelude on reaching the manager (tailnet, `.ssh/id_rsa`, user `firebat`). One wall of text fails: the question during an outage is "which of these is mine". The prelude must be accurate about the tailnet rather than hand-waving it: `100.64.0.0/10` gets port 22 (`configure_network.yml:11`) and 80/443/8404 (`services.tf:188,190,192`), never an API port, and only `firebat` is on the tailnet at all, since `configure_tailscale.yml:40-47` runs the role on `hosts: manager` and `:49-58` stops `tailscaled` on every worker. Any claim that a service API is reachable from the tailnet fails this row | deterministic check (all six sections plus prelude present; no tailnet-reaches-the-API claim) | 100% |
| **Three routes wherever a service is named, each with its reachability class** | Grep each section naming Vault, Nomad or Consul for all three routes, then grep every `192.168.2.30:<port>` occurrence for its condition | Every such section names (1) the edge hostname, (2) SSH to `firebat` plus `http://127.0.0.1:<port>`, and (3) the direct LAN address, and says which to reach for when the others are suspect. The LAN address NEVER appears without the condition that makes it work: it answers only from `192.168.0.0/16` and only while `configure_network.yml:13,18,21` allows it, and `N4-netsec-edge-only-service-access` removes that allow. The edge and the LAN address share a failure — both die with `firebat`, and the LAN one also dies from a policy change that leaves every service healthy — so only the SSH plus loopback route is independent, which is why N4's own §Risk assessment names it as the escape. Cite N4 by section rather than by line: it is under active revision and its line numbers have already moved twice | deterministic check (all three routes in each service-naming section; no unconditioned LAN address anywhere) | 100% |
| **Drift fails a gate** | Run the test that validates the runbook's facts; then deliberately change one asserted fact in the repo (for example the manager IP in `cluster.ini`) and re-run | Each fact-bearing token is asserted against the file that states it: manager IP and username against `bootstrap/inventory/cluster.ini`; the `unseal_vault` recipe name against the root `justfile`; the `/opt/vault/init.json` path against `bootstrap/roles/vault_server/tasks/main.yml`; every edge hostname against the `hdr(host) -i` ACLs at `haproxy.hcl:100-102` and every `ip:port` backend against `:133-140`; the Vault port against `vault.hcl.j2`. The test goes RED when the repo fact changes | deterministic check (test red after a deliberate repo-fact change) | 100% |
| **The drift gate can catch the change that is actually coming** | Change `from_ip` for 8200 in `bootstrap/playbooks/configure_network.yml:18` from `192.168.0.0/16` to a node IP — the edit N4 makes — and re-run the fact tests | The suite goes RED. Each LAN address the runbook tells a developer to dial is pinned to the ufw rule that permits it (`configure_network.yml:13,18,21`), asserting both that the port is present AND that its `from_ip` is still `192.168.0.0/16`. **Pinning to `haproxy.hcl` alone cannot satisfy this row:** `haproxy.hcl:134` still reads `server vault1 192.168.2.30:8200` after N4, because haproxy dials that backend from `firebat` itself, so every haproxy-pinned assertion stays green while the advice to the developer goes false. That is A1's diagnosis word for word: "The anchors still resolve — it is the surrounding claims that went false" (`A1-...md:39-40`) — and a gate pinned only to files the coming change does not touch is a spelling check, not a truth check | deterministic check (fact suite red after the `from_ip` edit; anchor set contains `configure_network.yml`) | 100% |
| **The drift test cannot pass vacuously** | Inspect the test: make its parser return nothing and re-run | The test FAILS when its own extraction finds no tokens to check. A parser that silently returns an empty set makes every assertion trivially true — this repo has shipped exactly that shape more than once, including a `grep -c` that returned 0 against surviving text and a guardrail scored by a hook that could not match the content it guarded | deterministic check (test red when parser yields nothing) | 100% |
| One copy of the runbook, loadable outside a checkout | `grep -rn "breakglass" docs/`; then run the command from a directory outside the repo | The text lives once inside the package and is loaded with `importlib.resources`, so a `uv tool install`ed CLI with no repo still prints it. `docs/` contains a pointer to the command, never a second copy. Two copies is precisely how `docs/credential-rotation.md` came to describe a `rotate_secrets.yml` that does not exist | deterministic check (single source; prints from outside the repo) | 100% |
| **Probes never take the command down** | Run with all three services unreachable; then with DNS failing; then with a probe target hanging past its timeout | The command exits 0 having printed the full runbook every time. Probes are read-only, credential-free, time-bounded and non-fatal; a failed probe degrades to printing everything rather than a stack trace or an empty screen. The command is most needed exactly when everything is broken | deterministic check (exit 0 and full runbook in all three cases) | 100% |
| Probes diagnose without asserting more than they know | Run with Vault sealed but reachable, and with Vault unreachable | The output distinguishes "reachable but sealed" from "not reachable", and presents its finding as a probe result rather than a diagnosis of root cause. `GET /v1/sys/health` needs no token — measured 200 unauthenticated on 2026-07-31, direct and through the edge — which is why seal state is probeable at all. Vault answers 503 sealed and 501 uninitialized by documented default, and 429 on standby, so the probe treats any documented code as "answered" rather than testing for 200 exactly. (`/v1/sys/seal-status` also answers 200 unauthenticated; the plan and this marker both standardize on `/v1/sys/health` so the scored row and Q2 name the same endpoint) | deterministic check (two distinct outcomes rendered) | 100% |
| **A closed firewall never reads as an outage** | Run three ways: edge 200 with all LAN probes refused; everything refused including the edge; Vault 503 through the edge | Three distinct findings, worded so the reader acts on the right thing. Edge up and LAN dark renders the sentence requirement 9 specifies verbatim — "the direct LAN addresses did not answer but the edge did, so the services are up. This is what a firewall change looks like, not an outage" — and points at the SSH plus loopback route. Score the plan's string, not a paraphrase: if the plan and this row disagree, the plan wins and this row is corrected. Everything dark: your own connectivity and then the cluster, in that order, leading to the prelude. Vault 503: "reachable but sealed", naming the sealed-Vault section. A bare "Vault unreachable" FAILS this row. Three probes going dark at once while the edge answers is the signature of a policy change, and after N4 it becomes the everyday result — the command would otherwise send the reader to fix a cluster that is fine, during an outage, which is the exact failure this ticket exists to prevent | deterministic check (three distinct findings rendered; the string "unreachable" absent from the edge-up case) | 100% |
| **The Consul probe keeps the leader signal** | Run the Consul probe against a reachable Consul; then against one returning 403 | Reachable: the probe sends `GET /v1/status/leader` and reports the leader address. Measured 2026-07-31: 200 with body `"192.168.2.30:8300"`, unauthenticated, direct and through the edge, despite `default_policy = "deny"` at `consul.hcl.j2:25-27` — the anonymous token carries read policy, so the 403 the earlier design defended against does not occur here. On 401 or 403 the probe degrades to a TCP connect and reports "reachable, not authorized to read the leader", never an outage. No token is sent on either path. This matters because Consul is Vault's storage backend and both Terraform state backends (`vault.hcl.j2:11-15`, `backend.tf:2`), so "Consul has no leader" is the one finding that explains everything else the reader is seeing | deterministic check (leader address rendered on 200; TCP fallback and "not authorized" wording on 403; no credential on either request) | 100% |
| The printed text meets the prose gates | Run `.claude/rules/slop-scan-for-docs.md` layers over the markdown source | Layer 0 clean: every backticked path, command and URL resolves to a real thing (requirement 4's test partly automates this). No identity leaks, no bare TODO. Sentence-level: em dashes within budget, no tier-1 slop, American spellings, prose wrapped at 80 | model + rubric (adversarial review agent) | 4/5 |
| The repo gate passes | `just worktree_setup <path>` (`justfile:41`), then `just pre_commit` (`justfile:18`, the sole entry in `.loop/config.json` gates) | All Passed. Hooks today (`.pre-commit-config.yaml`): `check-json`, `check-ast`, `check-merge-conflict`, `check-yaml`, `debug-statements`, `detect-private-key`, `end-of-file-fixer`, `nomad-fmt`, `terraform-fmt`, `terraform-validate`, plus D1's `ruff`, `ruff-format`, `mypy` (strict) and `pytest` scoped to `^cli/` (`:37-72`). `just pre_commit` runs all of them, including the CLI suite that covers this ticket's tests. Any new dependency landed via `uv add` in `cli/pyproject.toml` and `cli/uv.lock` | deterministic check (`just pre_commit` all Passed) | 100% |

**Revised 2026-07-31** after `plan-validator` returned `fail`. Changed: the
address row now scores three routes with their reachability classes instead of
"both addresses"; a new row requires the drift gate to go red on the
`configure_network.yml` edit N4 makes; a new row requires a closed firewall to
read as a closed firewall rather than an outage; a new row keeps the Consul
leader signal, since the 403 the old Q6 defended against was measured not to
happen; the section row now bounds what the tailnet actually carries; the probe
row standardizes on `/v1/sys/health` to match Q2; and the gate row no longer
claims `just pre_commit` runs ruff, mypy or pytest, because D1 landed all three at `.pre-commit-config.yaml:37-72`; and
row 2's grep target moved from the placeholder `cli/localstack/breakglass*`,
which matches no file, to D1's settled `cli/src/localstack_cli/` layout, with a
clause failing the row when the glob is empty. The rows these replaced scored
the ticket green for advice N4 makes false, and row 2 scored the credential
boundary green against a path that does not exist.

**The previous sign-off (JasperHG90, 2026-07-31) is deliberately removed**, not
carried over. It covered the rows this revision replaced, and the verdict
escalated D5 to `fail` rather than `pass-with-required-fixes` precisely because
operator-signed artifacts encoded facts the review falsified. Leaving the
signature in place would let the gate report `valid` over four rows the operator
has not seen. The operator re-signs the rows above, or this marker does not
pass.

signed-off-by: jasperginn@gmail.com 2026-08-03

signed-off-by: jasperginn@gmail.com 2026-08-03
