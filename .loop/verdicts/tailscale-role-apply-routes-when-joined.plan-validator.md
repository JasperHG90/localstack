---
verdict: pass-with-required-fixes
plan: f9d89ff58fab51a1d7361261d53ff190fa2ea236d7e107b9840cfb773fdce475
bound_paths: front-matter, 5, 6, 7, 8, 9, 10, premises
scope: 1fe9e1c697f9d94214fee19045c4c93290287f8ad69bc34177d24abb68d430da
fix_sections: 6, 7, 9
citations:
  bootstrap/roles/tailscale/tasks/main.yml:50 = - name: Check if already authenticated
  bootstrap/roles/tailscale/tasks/main.yml:54 = changed_when: false
  bootstrap/roles/tailscale/tasks/main.yml:55 = failed_when: false
  bootstrap/roles/tailscale/tasks/main.yml:65 = when: >
  bootstrap/roles/tailscale/tasks/main.yml:67 = (tailscale_status.stdout | from_json).BackendState != "Running"
  bootstrap/roles/tailscale/tasks/main.yml:63 = {% if tailscale_advertise_routes is defined %}--advertise-routes={{ tailscale_advertise_routes }}{% endif %}
  bootstrap/playbooks/configure_tailscale.yml:41 = hosts: manager
  bootstrap/playbooks/configure_tailscale.yml:47 = tailscale_advertise_routes: "192.168.2.0/24"
  bootstrap/inventory/cluster.ini:2 = firebat ansible_host=192.168.2.30
  bootstrap/ansible.cfg:10 = become = True
  justfile:19 = pre-commit run --all-files
  bootstrap/justfile:48 = ansible-playbook playbooks/configure_tailscale.yml
  .pre-commit-config.yaml:58 = entry: uv run --project cli mypy --config-file cli/pyproject.toml cli/src cli/tests scripts
  cli/pyproject.toml:5 = requires-python = ">=3.12"
  docs/credential-rotation.md:23 = | Notes | Once authenticated, the key isn't needed unless re-authentication is required. The tailscale role skips auth when `BackendState == "Running"`. |
  docs/haproxy_reverse_proxy.md:72 = Tailscale's subnet route (`192.168.2.0/24`). Resolving from elsewhere returns
---

# Plan review: tailscale-role-apply-routes-when-joined (plan-validator, full re-review)

Deterministic floor: `loopctl verify-plan tailscale-role-apply-routes-when-joined`
printed `valid`, exit 0.

Scratch created at
`.loop/scratch/tailscale-role-apply-routes-when-joined.plan-validator/`. Scratch
removed at end of pass.

## Premise verdict

PARTIALLY SOUND. The core premise holds, and I demonstrated it end to end: a
Running node never gets its routes re-applied, `tailscale set` plus a prefs read
reconciles them, a fake shim drives real `ansible-playbook`, R4's check-mode
drift task works, and R12's warning works. One claim breaks. R4 says the prefs
read "match[es] the read-task style at `main.yml:50-55`", but that task has no
`check_mode: false`. Because of that gap, a real `--check` run of the role
fails before it ever reaches `routes.yml`. R4 holds only in the `tasks_from:
routes` test harness, never on the live playbook.

## Per-assumption findings

- **P1: HOLDS.** `bootstrap/roles/tailscale/tasks/main.yml:63-67`
  > {% if tailscale_advertise_routes is defined %}--advertise-routes={{ tailscale_advertise_routes }}{% endif %}
  > ...
  > when: >
  >   tailscale_status.rc != 0 or
  >   (tailscale_status.stdout | from_json).BackendState != "Running"

  This is the only place in the role that passes `--advertise-routes`, and it
  is gated on the node not being Running.

- **P2: HOLDS.** `bootstrap/playbooks/configure_tailscale.yml:41,47`,
  `bootstrap/inventory/cluster.ini:2`
  > hosts: manager
  > tailscale_advertise_routes: "192.168.2.0/24"
  > firebat ansible_host=192.168.2.30

- **P3: UNCERTAIN (as the plan itself marks it).** This is an operator report,
  and I cannot check it from the repo. The fix does not depend on the root
  cause.

- **P4: HOLDS (upstream source).** `cmd/tailscale/cli/set.go` @6b3a45f, near L36
  > Only settings explicitly mentioned will be set. There are no default values.

- **P5: HOLDS (upstream source).** `cmd/tailscale/cli/debug.go` L68 and
  `ipn/prefs.go` L81 and L204 @6b3a45f
  > LongHelp:   hidden + `"tailscale debug" contains misc debug facilities; it is not a stable interface.`,
  > RouteAll bool
  > AdvertiseRoutes []netip.Prefix

  Neither field has a JSON tag, so the key names hold.

- **P6: UNCERTAIN (as the plan itself marks it).** The live probe was denied.
  The post-merge operator check covers it.

- **P7: HOLDS (demonstrated).** I ran a scratch role that implements §7's
  design (prefs read, `from_json`, assert, set-difference compare, conditional
  `set`, check-mode drift `debug`, status read, warning `debug`) with real
  `ansible-playbook [core 2.21.4]`, `-i localhost, -c local`, `env -u
  ANSIBLE_CONFIG`, and a fake `tailscale` on PATH. Captured output:
  ```
  prefs null, normal     rc=0 changed=1  log: set --advertise-routes=192.168.2.0/24 --accept-routes;
  prefs converged        rc=0 changed=0  log: (no set)
  prefs null, --check    rc=0 changed=1  log: (no set)
  converged, --check     rc=0 changed=0  log: (no set)
  status {"Self":{}}     rc=0 changed=0  warn: 1
  status {}              rc=0 changed=0  warn: 1
  prefs {}               rc=2 failed=1   log: (no set)
  prefs "not json"       rc=2 failed=1   log: (no set)
  ```
  This covers tests 1, 2, 4, 7, and 8 as the plan specifies them, and R1 to R4
  and R12 inside the harness.

- **P8: HOLDS in substance.** `ansible.posix` is used at `main.yml:3`
  (`ansible.posix.sysctl:`), and the PATH `ansible-playbook` is ansible-core.
  I did not rerun the syntax-check probe. `uv pip compile --python-version 3.12`
  resolves `ansible-core==2.21.4`, so the dev dependency is installable for
  `cli/` (`requires-python = ">=3.12"`, `cli/pyproject.toml:5`).

- **P9: HOLDS.** `bootstrap/ansible.cfg:10`
  > become = True

  All my probe runs used `env -u ANSIBLE_CONFIG` from a scratch cwd, and none
  tried sudo.

- **P10: HOLDS.** `justfile:18-19` and `.pre-commit-config.yaml:58`
  > pre-commit run --all-files
  > entry: uv run --project cli mypy --config-file cli/pyproject.toml cli/src cli/tests scripts

  No pytest hook exists. Note that the working tree has an uncommitted
  `openviking-config` hook at `:67-81`. The plan places its new hook "after
  `:65`", which still works. P10's "yaml, ruff, ruff-format, mypy, nomad and
  terraform only" is true of HEAD (65 lines) but not of the working tree. That
  is advisory only.

- **P11, P12: not re-probed.** These are grep and ansible-lint results. They
  do not bear on the premise, and I have no contrary evidence.

- **P13: HOLDS (demonstrated).** A one-task `command: /bin/true` play under
  `--check`:
  ```
  skipping: [localhost]
  localhost : ok=0 changed=0 unreachable=0 failed=0 skipped=1 ...
  ```

- **P14: HOLDS (upstream source).** `ipn/ipnstate/ipnstate.go` L266 and
  `ipn/ipnlocal/local.go` L1564 and L1678-1680 @6b3a45f
  > PrimaryRoutes *views.Slice[netip.Prefix] `json:",omitempty"`
  > if sn := nm.SelfNode; sn.Valid() { peerStatusFromNode(ss, sn)
  > if n.PrimaryRoutes().Len() != 0 { ... ps.PrimaryRoutes = &v

  `omitempty` confirms R12's rule that a missing key counts as not approved.

- **Implicit P15 (added): "R4's check-mode behavior is reachable through the
  role as `configure_tailscale.yml` runs it." BREAKS.**
  `bootstrap/roles/tailscale/tasks/main.yml:50-55`
  > - name: Check if already authenticated
  >   ansible.builtin.command:
  >     cmd: tailscale status --json
  >   register: tailscale_status
  >   changed_when: false
  >   failed_when: false

  The task has no `check_mode: false`, so R4's phrase "matching the read-task
  style at `main.yml:50-55`" is false. I ran the demonstration with verbatim
  `main.yml:40-68` followed by `include_tasks: routes.yml`, under `--check`,
  with a Running shim. It was deterministic across two runs:
  ```
  TASK [ts2 : Check if already authenticated]  skipping: [localhost]
  TASK [ts2 : Authenticate with Tailscale]
  fatal: [localhost]: FAILED! => {"msg": "Task failed: A 'when' expression failed: The filter plugin 'ansible.builtin.from_json' failed: Expecting value: line 1 column 1 (char 0)"}
  ok=0 changed=0 failed=1 skipped=2
  ```
  With only `check_mode: false` added to that read task (the auth task is
  untouched), the same run gave `rc=0 ... changed=1`, the shim log showed
  `debug prefs`, and no `set` ran. So a real `ansible-playbook --check
  playbooks/configure_tailscale.yml` fails today before `routes.yml`. Test 7
  exercises only `tasks_from: routes`, so it would pass green while the
  operator-facing `--check` stays broken.

- **Implicit P16 (added): "the post-set status read works under `--check`."
  HOLDS, conditionally.** It works only if that read also carries `check_mode:
  false`. Without it, `from_json` on an empty stdout fails the play. §7 states
  `check_mode: false` for the prefs read only. Test 7, run with a routes var,
  would catch the omission, so this is advisory rather than required.

- **R12 placement (as asked).** Reading status after the `set` is the right
  order for the steady state. Right after a `set`, `PrimaryRoutes` may lag
  control-plane approval. §9 already names this false alarm and makes the
  warning say "re-check", and the play stays green, so the ordering is
  acceptable.

## Most dangerous assumption

P15: that R4's `--check` drift report is something the operator can actually
use. The unit harness proves it only for `routes.yml` in isolation. The live
role dies under `--check` at `main.yml:65-67` because of the `main.yml:50-55`
gap that R4 wrongly calls the style it matches.

## Contract hygiene

- Anchors resolve and say what the plan claims (`justfile:18-19`,
  `bootstrap/justfile:48`, `configure_tailscale.yml:40-47,49-58`,
  `docs/credential-rotation.md:23,44`, `docs/haproxy_reverse_proxy.md:71-73`,
  `scripts/vault_mfa_test.sh:1`). The exception is the R4 `:50-55` "style"
  claim above.
- The gates come from `.loop/config.json` (`just pre_commit`). The non-goals
  are explicit. All tests are homed in `cli/tests/test_tailscale_role.py`, and
  the forks Q1 to Q7 are resolved.
- Every requirement has a producer: the recap line, the shim log, or the play
  output from the §7 test. R4's producer measures `routes.yml` only (see
  P15).
- Advisory: `bootstrap/README.md:24` is the last row (`GITHUB_PAT`) of an
  env-var table. A new `##` section inserted there would separate that section
  from its `### GitHub Container Registry` subsection at `:26`. Pick a spot
  after that subsection.

## Required fixes

1. **§6 R4 and §7 (sections 6, 7).** Remove the false claim that the prefs read
   matches `main.yml:50-55`. Then make R4 true for the live role, or scope it
   honestly. The operator picks one:
   - (a) Add `check_mode: false` to the read task at
     `bootstrap/roles/tailscale/tasks/main.yml:50-55` and list it in §7. This
     is a read task, outside the `:57-68` auth task that the §5 non-goal
     protects. I demonstrated it: live-shaped `--check` then goes green with
     `changed=1` and no `set`.
   - (b) State in R4 that the check-mode report is guaranteed for `routes.yml`
     only, and that a full-role `--check` fails today at `main.yml:65-67`.
     Record that as a known limitation.
2. **§9 (section 9).** Add the failure mode "`--check` on the full playbook
   fails at the auth task's `from_json`" under option (b), or its mitigation
   under option (a).

Advisory (not blocking): in §7, state `check_mode: false` and `changed_when:
false` for the post-set `status --json` read too (P16). In P10, note the
uncommitted `openviking-config` hook. Move the README insertion point.
