---
verdict: fail
---

# Plan review — D5-cli-breakglass (pass `plan-validator`)

Plan reviewed: `.loop/plans/D5-cli-breakglass.md`
Fingerprint of the reviewed content: `b15c9911419a769b2596aa08c9faacfcd8778c699082a0d174dbe59ef8e8e500`
(no `plan:` header line, because this is a `fail` and a failing verdict must
not authorize the flip to `ready`).

## Premise verdict: PARTIALLY SOUND — failing on severity

The credential boundary, which is this ticket's reason to exist, holds under
attack: every load-bearing claim behind Q1 and Q3 checks out against the repo.
The plan fails on its *address model*. Every direct address the runbook is
required to print, and three of the four probes it is required to run, target
a LAN path that `N4-netsec-edge-only-service-access` exists to close. D5 does
not mention N4, does not depend on it, and its anti-drift gate is structurally
incapable of noticing when N4 lands. The plan would ship a runbook that is
correct today and silently wrong during the exact outage N4 creates.

Two operator-signed artifacts (the plan's `## Forks resolved, 2026-07-31` and
the eval marker `.loop/evals/D5-cli-breakglass.md`, signed today) encode facts
I falsified. That puts the fix above what an implementer may apply from a
review note, so this is a `fail` rather than `pass-with-required-fixes`.

## Assumptions attacked

### P1 — `scripts/unseal_vault.sh` refuses unless `VAULT_TOKEN` is set alongside the three unseal keys — **HOLDS**

Verbatim, `scripts/unseal_vault.sh:6`:

```sh
if [ -z "$VAULT_UNSEAL_KEY_1" ] || [ -z "$VAULT_UNSEAL_KEY_2" ] || [ -z "$VAULT_UNSEAL_KEY_3" ] || [ -z "$VAULT_ADDR" ] || [ -z "$VAULT_TOKEN" ]; then
```

The guard is a five-way `-z` chain, `VAULT_TOKEN` included, exiting 1 at `:8`.
The script then runs three bare `vault operator unseal` calls (`:11-13`) that
need no token. So Q1's reasoning is exact: invoking the recipe would require
the CLI to carry the root token for a guard that the unseal operation itself
does not need. `justfile:22-23` runs `bash scripts/unseal_vault.sh` and the
root `justfile` has no `set dotenv-load` (contrast `bootstrap/justfile:3`), so
the values come from ambient env, injected by `--env-file .devcontainer/.env`
(`.devcontainer/devcontainer.json:37-39`). Every element of Q1's premise
verified. The Q1 → "print, never run" resolution is sound.

### P2 — `/opt/vault/init.json` is the right path and is already public in the repo — **HOLDS**

`bootstrap/roles/vault_server/tasks/main.yml:116-123` is the `Store Vault init
keys` copy task writing `dest: /opt/vault/init.json`, `owner: vault`, `mode:
'0600'`. The cited `:109-123` range starts exactly at `- name: Initialize Vault
if not already done`. Both secrets come out of that one file: the unseal keys
at `:158` (`loop: "{{ vault_init.unseal_keys_b64[:3] }}"`) and the root token
via `bootstrap/roles/nomad_server/tasks/main.yml:191,196` (`slurp` +
`from_json`, not `jq`, as the plan says). The path appears in six places across
two tracked files. Naming it leaks nothing. Q3 is sound, and its drift anchor
(requirement 4, "the `/opt/vault/init.json` path against
`bootstrap/roles/vault_server/tasks/main.yml`") resolves.

### P3 — an unauthenticated `GET /v1/sys/health` separates sealed (503) from uninitialized (501) from active (200) — **HOLDS**, partly by documentation

Measured from this devcontainer just now:

```
GET http://192.168.2.30:8200/v1/sys/health -> 200
{"initialized":true,"sealed":false,"standby":false,...,"version":"2.0.3",...}
```

No token sent, full body returned. The 503-sealed and 501-uninitialized codes
are the documented `/sys/health` defaults (`sealedcode=503`, `uninitcode=501`)
and I could not produce a sealed Vault to observe them, so those two are
documentation-backed rather than measured. Note the plan omits `standbycode=429`;
moot here on a single server (`nomad.hcl.j2` / single Vault), but the probe
should treat "any 2xx-or-known-code" rather than "200 exactly" as reachable.
`GET /v1/sys/seal-status` also answers 200 unauthenticated — worth noting
because the eval marker names `/v1/sys/seal-status` while plan Q2 names
`/v1/sys/health`. Reconcile them; both work.

### P4 — Nomad `/v1/agent/health` answers unauthenticated — **HOLDS**

```
GET http://192.168.2.30:4646/v1/agent/health -> 200
{"client":{"message":"ok","ok":true},"server":{"message":"ok","ok":true}}
```

Also 200 through the edge: `https://nomad.lab.orangecluster.nl/v1/agent/health`.

### P5 — Consul may 403 unauthenticated, so a TCP connect is the right probe — **BREAKS**

The stated reason is false against this cluster. Measured:

```
GET http://192.168.2.30:8500/v1/status/leader -> 200  "192.168.2.30:8300"
GET http://192.168.2.30:8500/v1/agent/self    -> 200
```

Consul ACLs *are* enabled with `default_policy = "deny"`
(`bootstrap/roles/consul_server/templates/consul.hcl.j2:25-27`), so the plan's
config reading is right and its behavioral conclusion is wrong — the anonymous
token evidently carries read policy. Q6's recommendation (TCP connect, treat
any response as reachable) is *safe*, but it is now strictly weaker than the
available evidence: a real HTTP GET that returns the leader address separates
"Consul answers and has a leader" from "Consul answers with no leader", which a
TCP connect cannot. Since Consul-down means Vault-down and Terraform-unusable
(the plan's own point, `vault.hcl.j2:11-15`, `backend.tf:2`), losing the leader
signal costs real diagnostic value during exactly the outage this command
serves. Q6 was resolved today on a premise I measured false.

### P6 — the TLS-handshake probe against the edge separates "edge down" from "cluster down" — **HOLDS**

`https://vault.lab.orangecluster.nl/v1/sys/health` returns 200 with
`ssl_verify_result=0`. An unknown Host returns 307, not a fall-through to a
backend. The edge proxies the API, not just the UI, so it is a viable probe
target.

### P7 — the runbook's facts-pinned-to-repo requirement is testable — **HOLDS mechanically, BREAKS on what it can catch**

Mechanically, all five requirement-4 anchors are parseable from tracked files:
`bootstrap/inventory/cluster.ini:2-3` yields `192.168.2.30` and `firebat`; the
root `justfile:22` yields `unseal_vault:`; `haproxy.hcl:100-102` yields the
`hdr(host) -i <name>` hostnames and `:134,137,140` the `server <n> <ip:port>`
backends; `vault.hcl.j2:20` yields `address = "0.0.0.0:8200"`;
`vault_server/tasks/main.yml:119` yields the init path. A drift test over these
is straightforward and the plan's vacuous-parse guard is the right shape.

What it cannot catch is the failure that will actually occur. The plan quotes
A1's diagnosis at `.loop/plans/A1-audit-plan-premise-sweep.md:39-40` — "the
anchors still resolve, it is the surrounding claims that went false" — and then
builds its entire anti-drift defense out of anchor resolution. `haproxy.hcl`
will still say `server vault1 192.168.2.30:8200` after N4 closes 8200 to the
LAN, because haproxy reaches its backend from the same host. Every requirement-4
test stays green while the runbook's advice to the *developer* becomes false.
The gate is a spelling check, not a truth check, and the plan does not say so.

Note also that `.devcontainer/.env` is gitignored (`.gitignore:2`), so the only
tracked source the direct address can be pinned against is `haproxy.hcl`, the
one source guaranteed not to change under N4.

### P8 — `http://192.168.2.30:8200` "works from the tailnet with no edge involved" — **BREAKS**

`bootstrap/playbooks/configure_network.yml` opens 8200 (`:18`), 4646 (`:21`)
and 8500 (`:13`) to `192.168.0.0/16` only. The tailnet CIDR `100.64.0.0/10`
gets **port 22 alone** on the manager (`:11`), plus 80/443/8404/3000/8080 from
`deployments/infrastructure/services.tf:188-192,222,231`. Default incoming
policy is `deny`.

The manager is itself the subnet router (`configure_tailscale.yml:40-47`
advertises `192.168.2.0/24` from `hosts: manager`; workers have `tailscaled`
stopped and disabled, `:50-59`). Tailscale's subnet-route SNAT applies to
forwarded traffic, not to packets destined for the router's own address, so a
tailnet client dialing `192.168.2.30:8200` arrives on INPUT with a `100.x`
source and ufw denies it. I could not test from a tailnet-only host, so I mark
the mechanism UNCERTAIN — but the ufw rule set alone makes the plan's claim
unsupported, and `CLAUDE.md` says users reach the cluster over Tailscale. My
own reachability (all three ports, 200) comes from `192.168.215.2/24`, inside
`192.168.0.0/16` — a LAN path, not a tailnet path.

The plan asserts a reachability property it never verified, for the audience
(tailnet users) most likely to be reading the runbook.

### P9 — the direct `192.168.2.30:<port>` addresses survive as the escape hatch — **BREAKS. This is the most dangerous assumption.**

`N4-netsec-edge-only-service-access` (`.loop/plans/N4-...md`) is a planned
ticket at priority 50 against D5's 43, and it exists specifically to delete
this path:

- Code surface `:191-192`: "narrow `from_ip` for 4646, 8200, 8500 on manager
  and workers".
- R3 `:161-164`: after the run, `ufw status numbered` shows **no**
  `192.168.0.0/16` entry for the closed ports.
- Q3, resolved `:313-317`: "**no devcontainer exception.** It moves to the edge
  like everything else. Direct access is what the runbook's SSH path is for."
- R6 `:171-175`: `.devcontainer/.env` moves to the edge hostnames, killing the
  plan's own Context claim at D5 `:72-74` that the dev container's `VAULT_ADDR`
  is the direct address.
- Risk `:213-218`: after the change "the only route to Nomad's API is haproxy,
  and haproxy is a job Nomad schedules... The escape is SSH to firebat and
  `NOMAD_ADDR=http://127.0.0.1:4646`."

What this costs D5, concretely:

1. **Requirement 3 becomes an instruction to print a dead address.** "Both
   addresses, every time... names the edge hostname and the direct
   `192.168.2.30:<port>` address, and says which one to reach for when the
   other is suspect" (D5 `:169-171`). Post-N4 the honest second address is
   `http://127.0.0.1:<port>` reached over SSH, which appears nowhere in D5
   except as an aside about what Ansible does (`:71`). The word "loopback" does
   not occur in the plan.
2. **Three of the four Q2 probes stop working** from the developer's machine:
   `192.168.2.30:8200`, `192.168.2.30:4646`, and the TCP connect to
   `192.168.2.30:8500`. They will time out or be refused, and the command —
   correctly, per requirement 8 — will degrade to "unreachable", telling the
   operator the cluster is down when the firewall is simply doing its job. That
   is the plan's own third risk (`:301-305`, "probes lie") realized by design.
3. **The drift gate cannot see it** (see P7). N4 touches
   `configure_network.yml`, which requirement 4 does not pin against.
4. **The eval marker bakes it in.** `.loop/evals/D5-cli-breakglass.md` scores a
   100%-threshold row requiring "BOTH the edge hostname and the direct
   `192.168.2.30:<port>` address" in every service-naming section. Post-N4 the
   ticket passes its eval by printing wrong advice.

N4 knows about D5 — its R7 (`:176-180`) says "Follow `D5-cli-breakglass`'s rule:
facts in the runbook are pinned to the repo file that states them", and its
subticket 2 writes `docs/edge-and-recovery.md` *before* the dangerous step. D5
does not know about N4: `grep -in "n4|firewall|ufw|netsec|127\.0\.0\.1|loopback"`
over the plan returns one hit, the incidental `127.0.0.1` at `:71`. The
dependency is one-directional and pointed the wrong way.

Scheduling does not rescue this. `.loop/ledger.json` has N4 at `planning`,
blocked behind `N3-netsec-converging-firewall-provisioner` (`ready`, priority
10), while D5 sits at priority 43 — so D5 plausibly lands first and is right
for a while. That is worse, not better: a runbook that is correct on the day it
ships and wrong when it is needed, with no gate in between, is the precise
failure mode the plan was written to prevent (`:123-133`).

### P10 — Context hygiene claims — **HOLDS**, with two nits

Verified as stated: `cluster.ini:1-3` and `:5-16`; `vault.hcl.j2:11-15` (Consul
storage) and `:18-21` (`0.0.0.0:8200`, `tls_disable = true`);
`haproxy.hcl:6-9` (constraint `value = "firebat"`), `:39`, `:62-72`
(`change_mode = "restart"` at `:71`), `:96` (`bind *:443 ssl crt
/secrets/haproxy.pem`), `:100-102`, `:111-113`, `:133-140`;
`consul.hcl.j2:17` (`bootstrap_expect = 1`); `backend.tf:2` in both roots;
`.devcontainer/.env:3,6,9` and `.env.example:3,7,11`;
`.devcontainer/Dockerfile:11-17` (installs `nomad vault consul`);
`devcontainer.json:37-39`; `rescue-ssh.nomad.hcl:3,15,26` (30 lines,
`sysbatch`, `/home:/host-home`); `docs/tls-certificates.md:131`
("## Recovering a failed renewal"); `README.md:29`; `requirements.txt:3,5`;
`.python-version:1`; `.pre-commit-config.yaml` (hook list and the
`^\.(claude|loop)/` exclude at `:1`); `.loop/config.json` gates == `["just
pre_commit"]`; `justfile:17-19`; no ruff/mypy hook and no CI workflow.
`bootstrap/playbooks/` has no `rotate_secrets.yml` and `bootstrap/justfile` has
no rotation recipe, as claimed.

Nits:

- **`nomad.hcl.j2:13` is wrong.** `bootstrap_expect = 1` is at **line 31**;
  line 13 is a comment about podman0 address advertisement. The claim holds,
  the anchor does not.
- **"No `pyproject.toml` ... exists anywhere in the repo today" is false as
  written.** `find` turns up several under `apm_modules/` and
  `.claude/plugins/`. Both trees are gitignored (`.gitignore:22`,
  `.claude/plugins` via the harness), so the substantive point — the CLI package
  has none, D1 creates it — stands. Reword rather than re-verify.
- **`docs/credential-rotation.md` is overcharacterized.** `:50` reads "### 1.
  Create `bootstrap/playbooks/rotate_secrets.yml`" and `:78-85` "Add two
  recipes after `shutdown`". That is a how-to-implement page, not a page
  claiming the playbook exists. It is still an unbuilt design shipped as docs,
  so the moral survives, but "describes ... in the present tense" is not what
  the file says.

### P11 — the style bar `tmp/F9-MIGRATION.md` is reachable by the implementer — **BREAKS**

`tmp` is the first line of `.gitignore` and the file is untracked
(`git ls-files --error-unmatch` errors). The plan cites it three times as the
quality bar, including a specific lesson at `:73,78-81` that a test must
implement. `git worktree add` checks out tracked files only — the root
`justfile:25-28` comment documents exactly this bite for the SSH key and
tfvars. An implementer working in `.loop/worktrees/D5-cli-breakglass` will not
have the file. The plan discloses that it is uncommitted but not that it will
be absent where the work happens.

## Most dangerous assumption

**P9.** If the direct `192.168.2.30:<port>` path does not survive, requirement
3, the Q2 probe set, and one 100%-threshold eval row all instruct the
implementer to build a command that confidently prints an unreachable address
and misdiagnoses a firewall as an outage — during the outage. N4 is written,
scored, and higher-priority, and it deletes that path on purpose. The plan's
own risk section names this exact failure as the one that matters
(`:290-294`): "a confidently printed wrong address ... is worse than no
runbook, because it is trusted precisely when nobody has the patience to verify
it."

## Required fixes before this plan can go `ready`

1. **Settle D5's relationship to N4 with the operator.** Either add
   `N4-netsec-edge-only-service-access` to `depends_on` and write the runbook
   against the post-N4 world, or state explicitly in Context that D5 ships
   pre-N4 and name N4 as the ticket that must update it. Silence is not an
   option: the two tickets contradict each other and only one of them knows it.
2. **Rewrite requirement 3's address model.** Replace "the edge hostname and
   the direct `192.168.2.30:<port>` address" with a three-way model that
   survives N4: the edge hostname; `http://127.0.0.1:<port>` reached over SSH
   to `firebat` (N4 `:216` names this as the escape); and the direct LAN
   address flagged as conditional on the firewall. Update the corresponding
   eval row in `.loop/evals/D5-cli-breakglass.md`, which currently scores the
   direct address at a 100% threshold.
3. **Re-scope the Q2 probe set.** Probe the edge first, since it is the path
   that survives (verified 200 over TLS today). Keep the direct probes only as
   a secondary signal, and make the output distinguish "firewalled" from
   "service down" — three of four probes going dark simultaneously is the
   signature of a policy change, not an outage.
4. **Add `bootstrap/playbooks/configure_network.yml` to requirement 4's pinned
   anchors.** Pin each address the runbook tells a developer to dial against
   the ufw rule that permits it (`:13,18,21`), so the day N4 narrows `from_ip`
   the drift test goes red. Without this, requirement 4 is a spelling check and
   the plan repeats A1's diagnosis verbatim.
5. **Re-decide Q6 on measured behavior.** `/v1/status/leader` and
   `/v1/agent/self` both return 200 unauthenticated today despite
   `default_policy = "deny"` (`consul.hcl.j2:25-27`). Prefer the HTTP GET,
   which yields the leader address, and fall back to a TCP connect on a 403.
   The current resolution discards diagnostic value for a risk that does not
   exist here.
6. **Delete or verify the tailnet claim at `:69-70`.** ufw permits 8200 from
   `192.168.0.0/16` only; `100.64.0.0/10` gets port 22 and the edge ports.
   Either verify from a tailnet-only host and record the result, or drop the
   phrase "works from the tailnet".
7. **Fix `nomad.hcl.j2:13` → `:31`**, reword the "no `pyproject.toml` anywhere"
   claim, and soften the `docs/credential-rotation.md` characterization.
8. **Resolve the `tmp/F9-MIGRATION.md` reference.** Either commit it, inline
   the two lessons the plan actually needs (the `test -s` guard and the
   non-vacuous assertion), or drop it. As written it points a worktree
   implementer at a file that will not be there.

## Contract hygiene (checked, largely clean)

Non-goals are explicit and unusually good — the credential boundary is stated
as five prohibitions, not a slogan. Gates are discovered rather than assumed
and match `.loop/config.json` and `.pre-commit-config.yaml` exactly, including
the correct observation that no ruff/mypy hook or CI workflow gates Python
today. Every named test has its file (`test_breakglass.py`,
`test_breakglass_runbook_facts.py`, `test_breakglass_probes.py`). The negative
assertion guidance (`assert spy.mock_calls == []`, not `assert_not_called`)
matches `.claude/rules/python-testing.md`. Q7's `<pkg>` deferral is honest and
D1's plan does settle it (`D1-...md:110,121,161,168`: `cli/`, src layout,
`cli/pyproject.toml`, `typer`); note `cli/` does not exist on disk yet, so the
"resolve at pickup" instruction is load-bearing and correct.

One hygiene gap: the eval marker names `GET /v1/sys/seal-status` while plan Q2
names `GET /v1/sys/health`. Both work unauthenticated; pick one so the scored
row and the plan agree.
