eval: D5-cli-breakglass

**Definition of Done:** `localstack breakglass` runs read-only, credential-free
reachability probes, then prints a recovery runbook with a distinct section per
failure mode. It **never** reads, caches, displays or exports a credential. The
runbook text lives once, inside the package, and every fact in it is asserted
against the repo file that states it.

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
runbook is documentation embedded in code, and it goes stale silently. Row 5
is what makes drift fail a gate. A test asserting only "the text is non-empty"
does not satisfy it.

| Behavior | Input | Expected | Scorer | Threshold |
| --- | --- | --- | --- | --- |
| **Canary: no credential can leak, ever** | Inject token-shaped values via `monkeypatch.setenv` into `VAULT_TOKEN`, `NOMAD_TOKEN`, `CONSUL_TOKEN`, `CONSUL_HTTP_TOKEN` and `VAULT_UNSEAL_KEY_1/2/3`; run every code path of the command; capture stdout, stderr and any file written | None of the injected values appears anywhere. This is the row that turns the operator's boundary into something a test can fail | deterministic check (no injected value in stdout, stderr or written files) | 100% |
| **Forbidden actions are absent from the source** | `grep -rnE "init\.json\|unseal\|VAULT_TOKEN\|subprocess\|paramiko\|\bssh\b" cli/localstack/breakglass*` | No read of `/opt/vault/init.json`; no read of any token or unseal-key env var for any purpose; no SSH; no subprocess to `vault`, `nomad`, `ansible` or `terraform`; no credential attached to any probe. Mentions inside the runbook TEXT are expected and fine — this row is about executable code | deterministic check (no credential access or shell-out in code) | 100% |
| Every failure mode gets its own section | Run the command; inspect the output headings | Distinct headings for: sealed Vault; expired or revoked token; edge down but cluster up; Nomad unreachable; Consul unreachable; lost local token cache. Plus a prelude on reaching the manager (tailnet, `.ssh/id_rsa`, user `firebat`). One wall of text fails: the question during an outage is "which of these is mine" | deterministic check (all six sections plus prelude present) | 100% |
| **Both addresses appear wherever a service is named** | Grep each section for the edge hostname and the direct address | Any section naming Vault, Nomad or Consul names BOTH the edge hostname and the direct `192.168.2.30:<port>` address, and says which to reach for when the other is suspect. This matters because the edge is itself a Nomad job pinned to the manager (`haproxy.hcl:6-9`), so "the edge is down" and "Nomad is down" have overlapping causes and the direct address is the escape hatch | deterministic check (both forms present in each service-naming section) | 100% |
| **Drift fails a gate** | Run the test that validates the runbook's facts; then deliberately change one asserted fact in the repo (for example the manager IP in `cluster.ini`) and re-run | Each fact-bearing token is asserted against the file that states it: manager IP and username against `bootstrap/inventory/cluster.ini`; the `unseal_vault` recipe name against the root `justfile`; the `/opt/vault/init.json` path against `bootstrap/roles/vault_server/tasks/main.yml`; every edge hostname and `ip:port` backend against `haproxy.hcl`; the Vault port against `vault.hcl.j2`. The test goes RED when the repo fact changes | deterministic check (test red after a deliberate repo-fact change) | 100% |
| **The drift test cannot pass vacuously** | Inspect the test: make its parser return nothing and re-run | The test FAILS when its own extraction finds no tokens to check. A parser that silently returns an empty set makes every assertion trivially true — this repo has shipped exactly that shape more than once, including a `grep -c` that returned 0 against surviving text and a guardrail scored by a hook that could not match the content it guarded | deterministic check (test red when parser yields nothing) | 100% |
| One copy of the runbook, loadable outside a checkout | `grep -rn "breakglass" docs/`; then run the command from a directory outside the repo | The text lives once inside the package and is loaded with `importlib.resources`, so a `uv tool install`ed CLI with no repo still prints it. `docs/` contains a pointer to the command, never a second copy. Two copies is precisely how `docs/credential-rotation.md` came to describe a `rotate_secrets.yml` that does not exist | deterministic check (single source; prints from outside the repo) | 100% |
| **Probes never take the command down** | Run with all three services unreachable; then with DNS failing; then with a probe target hanging past its timeout | The command exits 0 having printed the full runbook every time. Probes are read-only, credential-free, time-bounded and non-fatal; a failed probe degrades to printing everything rather than a stack trace or an empty screen. The command is most needed exactly when everything is broken | deterministic check (exit 0 and full runbook in all three cases) | 100% |
| Probes diagnose without asserting more than they know | Run with Vault sealed but reachable, and with Vault unreachable | The output distinguishes "reachable but sealed" from "not reachable", and presents its finding as a probe result rather than a diagnosis of root cause. `GET /v1/sys/seal-status` needs no token, which is why seal state is probeable at all | deterministic check (two distinct outcomes rendered) | 100% |
| The printed text meets the prose gates | Run `.claude/rules/slop-scan-for-docs.md` layers over the markdown source | Layer 0 clean: every backticked path, command and URL resolves to a real thing (requirement 4's test partly automates this). No identity leaks, no bare TODO. Sentence-level: em dashes within budget, no tier-1 slop, American spellings, prose wrapped at 80 | model + rubric (adversarial review agent) | 4/5 |
| The repo gate passes | `just worktree_setup <path>`, then `just pre_commit` | All Passed, including ruff, mypy and pytest. Any new dependency landed via `uv add` in `cli/pyproject.toml` and `cli/uv.lock` | deterministic check (`just pre_commit` all Passed) | 100% |

signed-off-by: PENDING
