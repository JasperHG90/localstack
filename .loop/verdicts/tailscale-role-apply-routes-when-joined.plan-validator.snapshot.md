---
epic = "netsec"
depends_on = []
priority = 10
summary = """
The tailscale role applies `--advertise-routes` only inside `tailscale up`, and
skips `tailscale up` on a node that is already Running. So a re-run on a joined
manager never restores a lost subnet route and still reports success. Firebat
advertised no route in 2026-09 and remote tailnet clients lost the LAN. Add a
reconcile step that reads the node's prefs and runs `tailscale set` only when
they differ from the desired ones, with a real-ansible test against a fake
`tailscale` on PATH.
"""
tags = ["tailscale", "ansible", "bootstrap", "subnet-route", "idempotency"]
premise = { Q1 = "the repo has no Ansible test harness; the PATH ansible-playbook lacks ansible.posix", Q2 = "just pre_commit runs no pytest", Q3 = "only the manager runs the role today", Q7 = "a fresh node always needs admin-console approval once, so failing would break first runs" }
---

# Ticket: tailscale-role-apply-routes-when-joined

## 1. Title
Tailscale role: reconcile `AdvertiseRoutes`/`RouteAll` on an already-joined node, so a re-run restores the `192.168.2.0/24` subnet route instead of silently skipping it.

## 2. Size / Effort
S-M. The role change is small (one new task file, one include). The effort goes into
the first Ansible behavior test in the repo (fake `tailscale` shim, real
`ansible-playbook`) and wiring it into a gate that runs.

## 3. Triggered by
Live incident, 2026-09 (operator report): firebat advertised no routes. The admin
console said "This device does not expose any routes". On a remote Mac,
`.Peer[]|select(.HostName=="firebat")|.PrimaryRoutes` was null with RouteAll=true.
Remote clients could not reach `192.168.2.0/24` or `*.lab.orangecluster.nl`. The
operator fixed it by hand with `sudo tailscale set --advertise-routes=192.168.2.0/24`
and approved the route in the admin console.

## 4. Context
- `bootstrap/roles/tailscale/tasks/main.yml:50-55` reads `tailscale status --json` into `tailscale_status`.
- `bootstrap/roles/tailscale/tasks/main.yml:57-68`: the only task that sets routes is `tailscale up ... --advertise-routes=... --accept-routes`, and it runs only when `tailscale_status.rc != 0 or BackendState != "Running"`. On a Running node, route prefs are never compared or applied. The play still ends green.
- `bootstrap/roles/tailscale/tasks/main.yml:2-8`: IP forwarding sysctl, gated on `tailscale_advertise_routes is defined`.
- `bootstrap/playbooks/configure_tailscale.yml:40-47`: role applied to `manager` only, with `tailscale_advertise_routes: "192.168.2.0/24"`. `:49-58`: workers only stop `tailscaled`.
- `bootstrap/inventory/cluster.ini:1-3`: manager is `firebat`, `192.168.2.30`.
- `bootstrap/justfile:48`: `just bootstrap` runs `configure_tailscale.yml`.
- `docs/dns.md:31-34`, `docs/haproxy_reverse_proxy.md:71-73`: reaching the lab names from off-LAN depends on the Tailscale subnet route.
- `docs/credential-rotation.md:23`: says the role skips auth when `BackendState == "Running"`. That stays true. It does not mention routes.
- No test covers any Ansible role. No molecule. `just pre_commit` (`justfile:18-19`) runs pre-commit only, and `.pre-commit-config.yaml:1-65` (committed) has no pytest hook and no ansible-lint hook.

## 5. Non-goals / out of scope
- Approving routes: the role never approves, and adds no ACL or `autoApprovers` policy. The repo has none (P11). Approval stays a manual step in the admin console. The role only warns when a route is not approved (R12, Q7), and docs mention the step (Q4).
- Reconciling `--hostname`, auth key rotation, `--force-reauth` (`docs/credential-rotation.md:44`), or any other pref besides `AdvertiseRoutes` and `RouteAll`.
- Changing the `tailscale up` first-join path at `bootstrap/roles/tailscale/tasks/main.yml:57-68`.
- Worker behavior (`configure_tailscale.yml:49-58`).
- Running the playbook against the live cluster. The operator already fixed firebat by hand. The live check in §8 is a post-merge operator step, not a loop gate.
- The `get_url` rewrite of the install step at `bootstrap/roles/tailscale/tasks/main.yml:10-13` (Q5, follow-up ticket).
- Exit-node advertisement. `tailscale set --advertise-routes` would not preserve an exit-node route (`0.0.0.0/0`, `::/0`) the role does not know about. No host advertises one today.

## 6. Requirements & restrictions
- R1. On a node whose `BackendState` is Running, the role converges `AdvertiseRoutes` to `tailscale_advertise_routes` (comma-separated, compared as a set) and `RouteAll` to true. It runs `tailscale set --advertise-routes=<routes> --accept-routes` only when they differ. Source of truth for the desired state: `configure_tailscale.yml:47`. Producer of the observed state: `tailscale debug prefs` JSON keys `AdvertiseRoutes` and `RouteAll` (P5), read by the new task file in §7.
- R2. Idempotent reporting: the set task reports `changed` only when it runs. A second run against converged prefs reports `changed=0` for the reconcile tasks. Producer: the `ansible-playbook` recap line, read by the new test in §7.
- R3. Fail loudly if `tailscale debug prefs` output is not JSON or lacks either key. `tailscale debug` is "not a stable interface" (P5), so an upstream change must fail the play, not turn the reconcile into a silent no-op. Same failure class as the incident.
- R4. Under `--check`, a drifted node reports `changed` (recap `changed>=1`) and runs no `set`. A plain `command` task is skipped in check mode with `changed: false` (P13), so this needs its own task that reports the drift as changed in check mode. The prefs read uses `changed_when: false` and `check_mode: false`, matching the read-task style at `bootstrap/roles/tailscale/tasks/main.yml:50-55`. A converged node under `--check` reports `changed=0`. Producer: the recap line, read by the test in §7.
- R5. When `tailscale_advertise_routes` is undefined, leave `AdvertiseRoutes` alone and reconcile only `RouteAll` (Q3, resolved).
- R6. Use only `ansible.builtin` modules in the new task file, so the test runs with the pinned ansible-core dev dependency, which has no `ansible.posix` (P8, Q1).
- R12. After the reconcile, read `tailscale status --json` and warn when a route in `tailscale_advertise_routes` is missing from `.Self.PrimaryRoutes` (not approved, P14). The warning names the admin-console step. The play stays green (Q7, resolved). A missing `Self` or `PrimaryRoutes` key counts as "not approved", not an error, because upstream omits the key when empty. Producer: the play output, read by the test in §7.
- R7. The first-join path must not run `set` needlessly. After a fresh `tailscale up` with the right flags, the reconcile reads matching prefs and skips.
- R8. Every code change ships with a test. Tests run through `uv`, mirror the source tree, use `tmp_path` and `monkeypatch`, and do not mock what can run for real (`.claude/rules/python-testing.md`). Here "real" means real `ansible-playbook` with a fake `tailscale` binary as the external boundary. The precedent is `scripts/vault_mfa_test.sh:1-9,20-50` (fake `vault` on PATH).
- R9. Test code passes ruff, ruff-format and mypy strict. Those hooks cover `cli/` (`.pre-commit-config.yaml:37-65`).
- R10. Comments only where the code cannot say it (`.claude/rules/minimal-comments.md`). One is warranted: why prefs come from an unstable `debug` command. Docs and prose follow `.claude/rules/plain-language.md` and `.claude/rules/slop-scan-for-docs.md`.
- R11. Never skip or xfail the test when `ansible-playbook` is missing. Fail with a clear message (`.claude/rules/python-testing.md`, `.claude/rules/pre-existing-issues.md`).

## 7. Code surface
- `bootstrap/roles/tailscale/tasks/routes.yml` (new): read `tailscale debug prefs` with `changed_when: false` and `check_mode: false`, assert the JSON shape (R3), run the conditional `tailscale set` (R1, R2, R5), report drift as changed under `--check` (R4), then read `tailscale status --json` and warn on unapproved routes (R12). Builtin modules only (R6).
- `bootstrap/roles/tailscale/tasks/main.yml:57-68`: after the auth task, append `ansible.builtin.include_tasks: routes.yml`. Do not touch the auth task itself. Also `:10-13` (add `set -o pipefail`, and `executable: /bin/bash` if needed) and `:40-44` (rename `tailscaled_ready` to a role-prefixed name) per Q5.
- `cli/tests/test_tailscale_role.py` (new): writes a fake `tailscale` shim into `tmp_path/bin`. The shim logs argv and serves canned `debug prefs` and `status --json` JSON from files the test controls. The test writes a one-play playbook that runs `include_role: {name: tailscale, tasks_from: routes}` against `localhost` with `-c local`, sets `ANSIBLE_ROLES_PATH` to `<repo>/bootstrap/roles`, unsets `ANSIBLE_CONFIG` and runs with cwd `tmp_path` so `bootstrap/ansible.cfg` (become=True) is not loaded (P9), and asserts on the shim log, the recap line and the output. It runs the `ansible-playbook` next to `sys.executable` (the pinned dev dependency), never the one on PATH.
- `cli/pyproject.toml:25-34` and `cli/uv.lock`: `uv add --dev ansible-core` (`.claude/rules/uv-installer.md`, Q1).
- `.pre-commit-config.yaml` (after `:65`): a local hook runs `uv run --project cli pytest cli/tests/test_tailscale_role.py -q` with `files: '^(bootstrap/roles/tailscale/|cli/tests/test_tailscale_role\.py$|cli/pyproject\.toml$|cli/uv\.lock$)'` and `pass_filenames: false` (Q2). The lockfile and manifest are in `files:` so bumping ansible-core re-runs the test.
- `bootstrap/README.md` (new short section after `:24`) and `docs/credential-rotation.md:23` (Q4).

## 8. Tests & validation gates
Gates (`.loop/config.json` `gates`): `just pre_commit`, which runs `pre-commit run --all-files` (`justfile:18-19`). The hooks are check-yaml, ruff, ruff-format, and mypy strict over `cli/src cli/tests scripts` (`.pre-commit-config.yaml:9-10,37-65`). Pytest is NOT in the gate today (P10), so also run by hand: `uv run --project cli pytest cli/tests -q`. Baseline: 512 passed, 21 deselected.

Review passes: `adversarial` and `documentation` (`.loop/config.json`).

Tests to add, all in `cli/tests/test_tailscale_role.py`. Write the first one before the fix. It must fail on today's role, because `routes.yml` does not exist yet:
1. `test_running_node_without_routes_gets_set`: prefs `{"AdvertiseRoutes": null, "RouteAll": true}` and `{"AdvertiseRoutes": [], "RouteAll": true}` (parametrized, upstream can print either). Expects exactly one `set --advertise-routes=192.168.2.0/24 --accept-routes` in the shim log, and `changed=1`.
2. `test_converged_node_reports_no_change`: prefs `{"AdvertiseRoutes": ["192.168.2.0/24"], "RouteAll": true}`. Expects no `set` in the log and `changed=0` (R2). This is also the state right after a first-join `tailscale up` (R7).
3. `test_route_all_off_is_corrected`: prefs have the right routes but `"RouteAll": false`. Expects one `set`.
4. `test_prefs_missing_keys_fails_the_play`: prefs `{}`, and also non-JSON output. Expects a nonzero exit and no `set` (R3). Parametrize.
5. `test_multiple_routes_compared_as_set`: desired `"10.0.0.0/8,192.168.2.0/24"`, prefs hold the same two routes in the other order. Expects no `set`.
6. `test_undefined_routes_leaves_advertise_routes_alone`: no `tailscale_advertise_routes`, prefs hold a route and `"RouteAll": false`. Expects a `set` with `--accept-routes` and no `--advertise-routes` flag (R5).
7. `test_check_mode_reports_drift`: run with `--check`. Drifted prefs give `changed>=1` and no `set` in the log. Converged prefs give `changed=0` (R4).
8. `test_unapproved_route_warns`: status `Self.PrimaryRoutes` lacks the route, or the key is absent. Expects the play to exit 0 and the output to name the admin-console approval step. With the route present, expects no warning (R12).

Parametrize where cases share a shape. All test code meets R8, R9 and R11. Any comment or doc meets R10.

Also run by hand, not gated: `ansible-lint roles/tailscale` from `bootstrap/`. The new file must add no findings. Baseline: 3 pre-existing findings (P12).

Post-merge operator check (manual, live, not a loop gate): run `ansible-playbook playbooks/configure_tailscale.yml` twice. Both runs are green and the second shows `changed=0` for the reconcile. Then check firebat with `tailscale debug prefs | jq .AdvertiseRoutes`.

## 9. Risk assessment
- Blast radius: one host, firebat (the only role target, P2). A wrong `set` could withdraw the subnet route, which cuts remote tailnet access to the LAN. LAN access is unaffected. `tailscale set` touches only the flags named (P4), so auth, hostname and other prefs are safe.
- Reversibility: high. `sudo tailscale set --advertise-routes=192.168.2.0/24 --accept-routes` by hand, as the operator already did.
- Likely failures:
  - An upstream change to `tailscale debug prefs` output. R3 makes this fail loud rather than silent.
  - A string-vs-list compare bug that runs `set` on every play (reports a false `changed`). Test 2 and test 5 catch it.
  - Q3 answered wrong would clear routes on a host with no routes var. Only the manager runs the role today, so no host is exposed now.
  - The test picks up `bootstrap/ansible.cfg` and tries sudo. Mitigated by running from cwd `tmp_path` (P9).
- Re-advertising a prefix may still need approval in the admin console (P11, UNCERTAIN whether an earlier approval carries over). The node sees approval in `tailscale status --json` `.Self.PrimaryRoutes` (P14), so the role warns (R12). Approval may lag a fresh `set`, so a warning right after a `set` can be a false alarm; the warning text says to re-check.

## 10. Subtickets
One loop iteration, ordered steps (no separate plan files):
1. Add `cli/tests/test_tailscale_role.py` with test 1 and the shim harness. Show it fails red because `routes.yml` is missing.
2. Add `routes.yml` and the include in `main.yml`. Add tests 2-6 and make them green.
3. Check-mode drift task and approval warning (R4, R12), tests 7-8.
4. Gate wiring: `ansible-core` dev dependency and the pre-commit hook.
5. Docs (Q4). Lint fixes (Q5).

## 11. Open questions
All resolved by the operator on 2026-09-26 (Q1-Q3, Q7 by explicit choice; Q4-Q6 by accepting the recommendation).
- Q1. How to test the role. RESOLVED: a pytest in `cli/tests/` runs real `ansible-playbook` (`-i localhost, -c local`) on `include_role ... tasks_from: routes` against a fake `tailscale` shim (P7). `ansible-core` is pinned with `uv add --dev`, and the test runs the binary next to `sys.executable`. Rejected: a bash script like `scripts/vault_mfa_test.sh` (no ruff or mypy), a YAML shape test (cannot catch a wrong `when`), lint only (fails R8).
- Q2. Gate wiring. RESOLVED: a pre-commit hook scoped to this test file, also triggered by `cli/pyproject.toml` and `cli/uv.lock` (§7). Rejected: the whole cli suite (about 63 s, P10), and leaving it ungated.
- Q3. `tailscale_advertise_routes` undefined. RESOLVED: leave `AdvertiseRoutes` alone and reconcile only `RouteAll` (R5). The role cannot tell "no routes wanted" from "not managed here", and clearing could withdraw a route set by hand.
- Q4. Docs. RESOLVED: a short "Tailscale subnet route" section in `bootstrap/README.md` (what the role enforces, that approval is manual in the admin console, the check command), and amend `docs/credential-rotation.md:23` to say routes are reconciled even when auth is skipped.
- Q5. Pre-existing ansible-lint findings (P12). RESOLVED: fix the var rename and add pipefail here. The `get_url` rewrite of the install step goes to a follow-up ticket, because it cannot be tested without a real install.
- Q6. Epic. RESOLVED: `netsec`.
- Q7. Check route approval? RESOLVED: warn, do not fail (R12). A fresh node always needs one manual approval, so failing would break every first run. Leaving it out would have left today's incident invisible to the play.

## Premises / assumptions
- P1. The auth task is the only place routes get applied, and it is skipped on a Running node. Evidence: `bootstrap/roles/tailscale/tasks/main.yml:57-68`.
- P2. Only the manager (firebat) runs the role, and it runs with routes `192.168.2.0/24`. Evidence: `bootstrap/playbooks/configure_tailscale.yml:40-47`, `bootstrap/inventory/cluster.ini:1-3`.
- P3. Firebat had no advertised routes in 2026-09 while Running. Evidence: operator report (admin console text, and `.PrimaryRoutes == null` from a remote Mac), plus the manual `tailscale set` fix. UNCERTAIN on the root cause. `--advertise-routes` has been in the role since `a9b2f22` (2026-03-21, `git log -S"advertise-routes" -- bootstrap`), so the prefs were lost after the join by some unknown means. The fix does not depend on the cause. A direct read-only probe of firebat was denied to this planner.
- P4. `tailscale set` changes only the flags given ("Only settings explicitly mentioned will be set"). `--advertise-routes` takes a comma-separated list, and an empty string means "not advertise routes". `--accept-routes` maps to `Prefs.RouteAll`. By contrast, `tailscale up` on a running node with changed flags errors unless all non-default flags are named. Source: tailscale/tailscale `main` at commit `6b3a45f` (VERSION 1.103.0): https://github.com/tailscale/tailscale/blob/6b3a45f14ef6e12ff1856b67e48eec627a8486c6/cmd/tailscale/cli/set.go#L36-L40 (also L78, L85, L151, L218-L221, L300-L306) and https://github.com/tailscale/tailscale/blob/6b3a45f14ef6e12ff1856b67e48eec627a8486c6/cmd/tailscale/cli/up.go#L981.
- P5. `tailscale debug prefs` prints `json.MarshalIndent(prefs)`. `Prefs.RouteAll bool` and `Prefs.AdvertiseRoutes []netip.Prefix` have no JSON tags, so the keys are `RouteAll` and `AdvertiseRoutes`, and an empty list marshals as `null`. `tailscale debug` is documented as "not a stable interface". Source: same commit, https://github.com/tailscale/tailscale/blob/6b3a45f14ef6e12ff1856b67e48eec627a8486c6/cmd/tailscale/cli/debug.go#L68 (also L256-L259, L633-L644) and https://github.com/tailscale/tailscale/blob/6b3a45f14ef6e12ff1856b67e48eec627a8486c6/ipn/prefs.go#L81 (also L204). That `null` means empty matches the operator's Mac-side observation of the route being absent.
- P6. Firebat's installed tailscale supports `tailscale set`. Evidence: the operator ran it successfully in 2026-09. The exact version is UNCERTAIN (the live probe was denied), and so is the presence of `debug prefs` on that version. The implementer should not assume it. The operator's post-merge check in §8 confirms it.
- P7. A fake-shim run of real `ansible-playbook` works and gives the right counts. Probe: a scratch role with the same logic, run with `-i localhost, -c local` and a fake `tailscale` on PATH. Output: prefs `null` gave `ok=3 changed=1`, shim log `debug prefs`, `set --advertise-routes=192.168.2.0/24 --accept-routes`. Prefs `["192.168.2.0/24"]` gave `ok=2 changed=0 skipped=1`. Wall time 0.676 s.
- P8. The PATH `ansible-playbook` is ansible-core without `ansible.posix`. Probe: `ansible-playbook --syntax-check playbooks/configure_tailscale.yml`, run from `bootstrap/`, gave `couldn't resolve module/action 'ansible.posix.sysctl'` with rc=4. The `ansible` uv tool binary (`~/.local/share/uv/tools/ansible/bin/ansible-playbook`) gave rc=0. So a test of the full `main.yml` would also need the collection. `routes.yml` alone does not.
- P9. `bootstrap/ansible.cfg:10` sets `become = True`. Ansible loads that file only from cwd or `ANSIBLE_CONFIG`. Probe: the P7 run, from a scratch cwd with no sudo, passed.
- P10. The gate runs no pytest and no ansible-lint. Evidence: `justfile:18-19`, and `.pre-commit-config.yaml:1-65` has hooks for yaml, ruff, ruff-format, mypy, nomad and terraform only. Probe: `uv run --project cli pytest cli/tests -q` gave `512 passed, 21 deselected ... in 62.62s`.
- P11. The repo configures no route auto-approval. Probe: `grep -rniI "autoApprovers|tailscale_acl|approve"` across the repo (excluding `.git`, `.loop`, `.claude`) returned no matches.
- P12. ansible-lint on the role has 3 findings today. Probe: `ansible-lint roles/tailscale`, run from `bootstrap/`, reported `command-instead-of-module` and `risky-shell-pipe` at `bootstrap/roles/tailscale/tasks/main.yml:10`, and `var-naming[no-role-prefix]` at `bootstrap/roles/tailscale/tasks/main.yml:40`. Config: `bootstrap/.ansible-lint` skips `yaml` and `name`.
- P13. Under `--check`, a plain `ansible.builtin.command` task is skipped and the recap shows `changed=0`, so R4 needs a separate task to report drift. Probe: a one-task play (`ansible.builtin.command: /bin/true`) run with `env -u ANSIBLE_CONFIG ansible-playbook -i localhost, -c local --check play.yml`. Output: `skipping: [localhost]`, recap `ok=0 changed=0 ... skipped=1`, and with `-v` `"msg": "Command would have run if not in check mode"`.
- P14. A node sees its own approved routes in the stable `tailscale status --json` output as `.Self.PrimaryRoutes`. Source: tailscale/tailscale at `6b3a45f`, https://github.com/tailscale/tailscale/blob/6b3a45f14ef6e12ff1856b67e48eec627a8486c6/ipn/ipnstate/ipnstate.go#L266 (field, `omitempty`) and https://github.com/tailscale/tailscale/blob/6b3a45f14ef6e12ff1856b67e48eec627a8486c6/ipn/ipnlocal/local.go#L1564 (filled for self). UNCERTAIN on a live node: read from source only, not probed on firebat.
