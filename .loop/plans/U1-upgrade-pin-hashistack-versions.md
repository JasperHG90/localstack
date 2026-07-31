---
epic = "upgrade"
depends_on = []
priority = 49
summary = "Declare and pin the Vault, Nomad, Consul and nomad-driver-podman versions the cluster already runs, so the apt install stops being 'whatever the repo had on first provision' and the U2-U4 upgrades become deliberate one-line moves. Pins to today's installed versions: no version changes."
tags = ["bootstrap", "ansible", "versioning", "hashistack"]
---

# U1 — Pin the HashiStack versions to what is installed today

## Title
Make the installed Vault, Nomad, Consul and nomad-driver-podman versions
declared in this repo and enforced on every node, pinned to the versions
running today, so U2/U3/U4 can move one variable instead of hoping apt does
the right thing.

## Size / Effort
**Small change, medium verification.** One playbook file, one template or
task block, one docs table. The work is not the diff: it is proving the pin
holds against the `upgrade: dist` task that runs earlier in the same
playbook, and proving a re-run on a live node changes nothing.

## Triggered by
Prerequisite carved out of the U2 (Vault), U3 (Nomad), U4 (Consul) upgrade
work. Those three cannot be reviewed or repeated while the repo has no
opinion about which version is installed.

## Context (today's state)

### The install path has no version control at all
`bootstrap/playbooks/install_dependencies.yml:94-104` installs `consul`,
`vault`, `nomad` and `nomad-driver-podman` from the HashiCorp apt repo with
`state: present` and no version. `state: present` means install-if-absent
and never upgrade, so every host froze at whatever the repo served on the
day it was first provisioned. Nothing in the repo records what that was.

The repo pins everything else it depends on:
- Ansible collections, `bootstrap/requirements.yml:3-8` (`containers.podman`
  1.18.0, `community.general` 11.4.0, `ansible.posix` 2.1.0).
- CNI plugins, `install_dependencies.yml:117` (`v1.1.1`, hardcoded in the
  download URL).

The HashiStack is the exception, and it is the part that matters most.

### Verified installed versions, 2026-07-31
Read over SSH with `dpkg-query -W` on each node. All reachable nodes are
uniform:

| Node | Address | OS / arch | consul | vault | nomad | nomad-driver-podman |
| --- | --- | --- | --- | --- | --- | --- |
| firebat (manager) | 192.168.2.30 | noble / amd64 | 1.22.6-1 | 1.21.4-1 | 1.11.3-1 | 0.6.4-1 |
| jetson_nano | 192.168.2.46 | jammy / arm64 | 1.22.6-1 | 1.21.4-1 | 1.11.3-1 | 0.6.4-1 |
| raspberry_pi_4b | 192.168.2.47 | noble / arm64 | 1.22.6-1 | 1.21.4-1 | 1.11.3-1 | 0.6.4-1 |
| radxa | 192.168.2.50 | noble / arm64 | 1.22.6-1 | 1.21.4-1 | 1.11.3-1 | 0.6.4-1 |
| orange_pi_4a | 192.168.2.29 | unknown | **not verified** | | | |

`orange_pi_4a` refused the SSH connection: the host key changed
(`REMOTE HOST IDENTIFICATION HAS CHANGED`, ED25519
`SHA256:0nEJP5I9NNKlMrH3Z2tnJWxbU2epaDNr+xfWJCAwISE`). Its versions are
unconfirmed and must be read before the pin lands. The node is listed under
`[worker]` at `bootstrap/inventory/cluster.ini:6-7`.

Running services agree with the packages: Consul reports `"Version":"1.22.6"`
on `http://192.168.2.30:8500/v1/agent/self`, Vault reports
`"version":"1.21.4"` on `/v1/sys/health`.

### What apt would install instead
`apt-cache policy` on firebat, same day:

| Package | Installed | Candidate |
| --- | --- | --- |
| vault | 1.21.4-1 | 2.0.3-1 |
| nomad | 1.11.3-1 | 2.0.4-1 |
| consul | 1.22.6-1 | 2.0.2-1 |
| nomad-driver-podman | 0.6.4-1 | 0.6.5-1 |

All three servers are a major version behind. `apt-mark showhold` on firebat
is empty, and `/etc/apt/preferences.d/` holds only the two Ubuntu Pro ESM
files, so nothing currently stops apt from taking the candidate.

### Correction to the premise this ticket was written from
The brief said all three are also behind within their own line. Only Consul
is. `apt-cache madison` on firebat lists, per package, the newest 1.x in the
HashiCorp apt repo:
- vault: `1.21.4-1` (equals installed)
- nomad: `1.11.3-1` (equals installed)
- consul: `1.22.7-1` (installed is `1.22.6-1`, one patch behind)

Post-2.0 patches to the 1.x lines exist only as Enterprise builds. The
HashiCorp releases API for July 2026 lists `vault 1.21.8+ent`,
`nomad 1.11.8+ent` and `consul 1.22.10+ent` with no matching community
release. So the community 1.x lines are done: staying on 1.x means no
further patches, which is the argument for U2/U3/U4 but not for this ticket.
The single free patch available on 1.x today is consul `1.22.7-1`, and this
ticket does not take it.

### The live hazard the pin must survive
`install_dependencies.yml:8-13` runs `apt upgrade: dist` against `hosts:
all` before the HashiStack play, and notifies a reboot handler
(`:34-38`). On a first provision that is harmless, because the HashiCorp
repo does not exist yet. On an already-provisioned node the repo file
persists (`/etc/apt/sources.list.d/hashicorp.list`, confirmed on firebat),
so the next `just bootstrap` (`bootstrap/justfile:40-41`) dist-upgrades
vault, nomad and consul straight to 2.x, reboots the node, and never reaches
the install task. That is a live footgun today, independent of this ticket.
It also means a pin expressed only as a version in the `name:` list at
`:94-104` does not hold: the dist-upgrade wins because it runs first.

### Why a restart is not free here
Upgrading these deb packages restarts their systemd units. On this cluster:
- Vault seals on restart. Recovery is `just unseal_vault` (`justfile:21-23`,
  `scripts/unseal_vault.sh`).
- Vault stores its data in Consul (`vault.hcl.j2:11-15`), so a Consul
  restart on firebat interrupts Vault storage.
- Terraform state also lives in that Consul (`backend.tf:1-3`).
- Nomad on firebat is the only server (`bootstrap_expect = 1`,
  `nomad.hcl.j2:11-14`) and is also a client (`:20-30`), registers with
  Consul (`:32-35`) and uses Vault workload identity (`:37-46`).
- The edge proxy is constrained to firebat (`haproxy.hcl:6-9`), so a Nomad
  outage there takes public routing with it.

This coupling is why U2/U3/U4 need an order. This ticket does not choose it;
it records the constraint so those tickets can.

## Non-goals / out of scope
- **Upgrading anything.** The pins equal the versions already installed.
  A correct implementation changes zero bytes on any node.
- Taking consul `1.22.7-1`, even though it is available and is a patch
  within the running line. That is a version move; it belongs to U4.
- Deciding the U2/U3/U4 upgrade order, or their pre-upgrade backups.
- Pinning the devcontainer CLIs (`.devcontainer/Dockerfile:11-17`). See Q5.
- Pinning the non-HashiCorp packages at `install_dependencies.yml:17-32` and
  `:46-58` (podman, crun, ufw and the rest), or the CNI plugin version.
- Fixing the `upgrade: dist` behavior itself, beyond making the four
  HashiStack packages immune to it. The reboot-on-upgrade handler stays.
- Adding an ansible-lint pre-commit hook or any CI. The repo has neither.
- Adding `defaults/` directories to roles, or a `group_vars/` tree, unless
  Q2 is answered that way.
- Any change to the role task files or templates under `bootstrap/roles/`.

## Requirements & restrictions
1. The four package versions are declared in exactly one place in the repo
   and referenced from there. No version string appears twice.
2. The declared versions equal the versions read from the live nodes on the
   day of implementation. Verify; do not copy the table above.
3. The pin must survive `install_dependencies.yml:8-13` (`upgrade: dist`).
   A pin that only appears in the install task at `:94-104` is insufficient.
   Prove this, do not assert it.
4. A full `just bootstrap` run (`bootstrap/justfile:40-49`) after this change
   must not change the version of vault, nomad, consul or
   nomad-driver-podman on any node, and must not restart their units for a
   version reason.
5. Moving a pin later must be a one-variable edit. Write down the procedure.
6. Follow the existing convention for variables: playbooks pass vars inline
   on the role invocation (`configure_hashistack_server.yml:5-9`, `:31-35`,
   `:41-44`) and **no role in this repo has a `defaults/` directory**
   (`bootstrap/roles/*` contain only `tasks/`, `templates/`, `files/`,
   `handlers/`, and one `vars/`). Do not invent a layout; see Q2.
7. The version strings must resolve on both suites in use. The apt suite is
   `{{ ansible_distribution_release }}` (`:88-92`), which is `noble` on
   three nodes and `jammy` on jetson_nano, across amd64 and arm64. All four
   current versions were confirmed present in the noble amd64, noble arm64
   and jammy arm64 indexes.
8. `nomad-driver-podman` is pinned alongside Nomad, and its current version
   (`0.6.4-1`) is recorded, because it constrains U3.
9. Downgrade must not happen silently. If a node's installed version is
   ahead of the pin, the run reports it rather than quietly rolling Vault
   back. See Q3.
10. Ansible module use stays inside the pinned collections
    (`requirements.yml:3-8`) or `ansible.builtin`. Do not add a collection.
11. `.claude/rules/adversarial-reviews.md`: adversarial review before done.
12. `.claude/rules/plain-language.md` applies to the docs table and any
    comment added to the playbook.

## Code surface
- `bootstrap/playbooks/install_dependencies.yml` — the whole change lives
  here.
  - `:71-81` the HashiStack play header. Add the four version variables to
    this `vars:` block, next to the existing `hashicorp_arch_map`, if Q2
    resolves to play-level vars.
  - `:94-104` the install task. Replace the bare package names with
    versioned names built from the variables, keeping `state: present`.
  - `:8-13` the dist-upgrade task. This is the ordering problem from
    requirement 3. Either a hold/preference task lands before it (new task
    or new play ahead of this one, in this same file) or the pin does not
    hold. Do not delete or reorder the dist-upgrade itself.
  - `:83-92` the GPG key and repo tasks. Unchanged, cited because the apt
    suite is derived here and Q6 depends on it.
- `bootstrap/templates/hashicorp.pref.j2` **(new, only if Q1 resolves to
  apt preferences)** — the pin file rendered to
  `/etc/apt/preferences.d/hashicorp.pref`. Note that
  `bootstrap/playbooks/` has no sibling `templates/` directory today, so
  this introduces one; the alternative (`ansible.builtin.copy` with inline
  `content:`) avoids that and is the lighter fit for a five-line file.
- `bootstrap/README.md` — new section recording the pinned versions, the
  read-only command that produces the census, and the procedure for moving a
  pin. This is the home for the verification commands named in §8. The file
  is currently prerequisites-only (`:1-3` intro, `:5-24` env vars), so
  append rather than restructure.
- `bootstrap/inventory/cluster.ini:1-16` — read only. The five nodes the
  census must cover.
- Not touched, cited so the implementer does not wander into them:
  `bootstrap/roles/*/tasks/main.yml`, `bootstrap/roles/*/handlers/main.yml`
  (each holds a `Restart <service>` handler), and every template under
  `bootstrap/roles/*/templates/`.

## Tests & validation gates
The repo has no test harness for Ansible, no CI, and no ansible-lint hook.
`.pre-commit-config.yaml` is the only gate. Every check below is a command;
its written home is the new section of `bootstrap/README.md` listed in §7.

### Repo gate
- **Command:** `just pre_commit` (`justfile:18-19`) to all Passed. This
  change is YAML plus markdown, so `check-yaml` with `--unsafe`
  (`.pre-commit-config.yaml:9-10`) and `end-of-file-fixer` (`:13`) are the
  hooks that bite. The nomad/terraform hooks are file-type scoped and will
  skip.
- **Worktree prerequisite:** `just worktree_setup <path>` (`justfile:30-32`)
  before the first gate run in a loop worktree, or the terraform hooks fail
  on missing gitignored inputs unrelated to this change.
- **Optional, not a gate:** run `ansible-lint` over the changed playbook.
  The config exists at `bootstrap/.ansible-lint:1-4` (skips `yaml` and
  `name`) and the tool is installed in the devcontainer, but no hook runs
  it. Run it; do not wire it in.

### Live checks, in order
1. **Census before.** Read every node, including orange_pi_4a once its host
   key is resolved:
   `ansible all -m ansible.builtin.command -a 'dpkg-query -W consul vault nomad nomad-driver-podman'`
   Read-only. Its output is what the pins must equal. Record it in the
   README table.
2. **Negative control on the pin.** Before the change, `apt-cache policy
   vault` on a node shows `Candidate: 2.0.3-1`. After the change is applied
   to that node, the same command must show the pinned version as the
   candidate (preferences route) or the package listed by `apt-mark
   showhold` (hold route). A check that cannot tell the two states apart is
   not a check.
3. **Dry run.** `ansible-playbook playbooks/install_dependencies.yml --check
   --diff --limit radxa` from `bootstrap/`. Expect the HashiStack install
   task to report no change. Caveats to read the output with: the
   dist-upgrade task at `:8-13` reports changed in check mode regardless,
   and the `shell` tasks with `creates:` guards (`:60-63`, `:83-86`) skip.
4. **Real run on one worker.** Re-run the same play with `--limit radxa`
   (a worker with no server role, so the blast radius is one Nomad client),
   then repeat the census on that node. All four versions unchanged.
   `systemctl show -p ActiveEnterTimestamp nomad consul` on that node must
   show the units were not restarted by the run.
5. **Cluster still healthy.** `consul members` shows all nodes alive,
   `nomad node status` shows the worker ready, and
   `curl -s http://192.168.2.30:8200/v1/sys/health` still reports
   `"sealed":false`.
6. **The dist-upgrade proof.** On the same worker, `apt-get -s dist-upgrade`
   must not list vault, nomad, consul or nomad-driver-podman. This is
   requirement 3 and is the one check that distinguishes a real pin from a
   decorative one.

## Risk assessment
- **Blast radius: every node, via a playbook that runs with `become: true`
  against `hosts: all` (`ansible.cfg:9-12`).** The file change itself is
  inert until someone runs the playbook, which is the safe part. The unsafe
  part is that running it is exactly how the change gets verified.
- **The worst outcome is an accidental upgrade.** A pin that is malformed,
  or that lands after the dist-upgrade in play order, converts the next
  `just bootstrap` into an unplanned 1.x to 2.x jump on Vault, Nomad and
  Consul at once, on a single-server cluster where Vault's storage is Consul
  and the edge proxy is pinned to the Nomad server. Vault has no supported
  downgrade after a storage-format bump, so that outcome is not reversible
  by re-running anything.
- **Second worst is a silent downgrade**, if a node is already ahead of the
  pin and the apt task is given `allow_downgrade: true`. Requirement 9 and
  Q3 exist to prevent this.
- **Reversibility of the change itself: high.** Revert the commit; the
  packages are untouched. The one residue is state written on a node (an
  `/etc/apt/preferences.d/hashicorp.pref` file, or a dpkg hold), which the
  revert will not remove. Say so in the README so a reverted pin does not
  leave a mystery hold behind.
- **Likeliest failure modes, ranked.** (1) The pin is written into the
  install task only and the dist-upgrade at `:8-13` still moves the
  packages. (2) A version string valid on noble is absent from the jammy
  index on jetson_nano and the apt task fails there mid-run. (3) The apt
  module refuses a downgrade on a drifted node and the play stops partway,
  leaving that node half-configured. (4) orange_pi_4a turns out to run
  different versions and the single declared pin is wrong for it.

## Subtickets (ordered)
1. **Census.** Resolve the orange_pi_4a SSH host key, then read all four
   package versions on all five nodes. Record the table. If any node differs
   from the other four, stop and raise it: a non-uniform cluster changes the
   shape of the pin (Q4).
2. **Declare the versions** in one place (Q2) and reference them from the
   install task at `:94-104`.
3. **Make the pin survive `upgrade: dist`** (Q1), ordered ahead of `:8-13`.
   Prove it with check 6.
4. **Verify on one worker** (checks 3 to 5), then on the manager only after
   the worker run is clean.
5. **Document** the table, the census command, and the pin-move procedure in
   `bootstrap/README.md`.
6. **Adversarial review** per `.claude/rules/adversarial-reviews.md`.

## Open questions

- **Q1 — apt preferences file, dpkg hold, or both?**
  *Recommendation: an `/etc/apt/preferences.d/hashicorp.pref` file rendered
  from the version variables, applied in a task that runs before
  `:8-13`.* A preferences file states the wanted version declaratively, is
  visible on the node, constrains dist-upgrade, and moves when the variable
  moves. `dpkg_selections: hold` also blocks dist-upgrade but expresses
  "never change" rather than "this version", so a later pin move needs an
  unhold/install/hold dance that is easy to get wrong. Both together is
  belt-and-braces and defensible; pick one and say why in a comment.

- **Q2 — where do the four version variables live?**
  *Recommendation: the `vars:` block of the HashiStack play,
  `install_dependencies.yml:71-81`, alongside `hashicorp_arch_map`.* It is
  the existing convention (`configure_hashistack_server.yml:41-44` does the
  same inline thing) and it keeps the declaration next to its only consumer.
  The alternative, a new `bootstrap/inventory/group_vars/all.yml`, is the
  more conventional Ansible answer and would let U2/U3/U4 edit one small
  file, but it introduces a directory the repo does not have. If the pin
  ends up needed in two plays (Q1 may force this), `group_vars` wins.

- **Q3 — what happens when a node's installed version differs from the
  pin?** *Recommendation: report always, upgrade when the pin is ahead,
  refuse when the pin is behind.* Set `allow_downgrade: false` on the apt
  task so a downgrade fails loudly instead of rolling Vault back, and print
  the installed-versus-pinned comparison from the census task on every run.
  Upgrading when the pin is ahead is safe by construction: the pin only
  moves when someone edits the variable, which is what U2/U3/U4 are.
  The alternative, failing on any difference, is stricter but would make
  U2/U3/U4 unable to use this playbook at all.

- **Q4 — what if the census shows nodes on different versions?**
  *Recommendation: stop and ask.* One variable per package assumes a uniform
  cluster. Four nodes are confirmed uniform and the fifth is unread. If the
  fifth differs, the choice is between per-group variables and levelling
  that node first, and levelling is a version move, which is out of scope
  here.

- **Q5 — devcontainer CLIs: in scope or deferred?**
  *Recommendation: defer, and say so in the README.*
  `.devcontainer/Dockerfile:16` installs `nomad vault consul` unpinned, and
  the image currently carries Vault 2.0.3, Nomad 2.0.3 and Consul 2.0.1
  against 1.x servers. That skew
  is real and the CLIs drift on every image rebuild, but pinning them means
  rebuilding the devcontainer, which puts the loop's own environment at risk
  in the middle of a ticket whose whole point is changing nothing. It also
  wants its own decision: match the server version, or stay ahead
  deliberately. Worth its own ticket in this epic.

- **Q6 — jetson_nano runs jammy while the rest run noble.** The four current
  versions exist in both suites today, so nothing blocks this ticket.
  *Recommendation: record the constraint in the README and let U2/U3/U4
  check suite availability before moving a pin*, rather than building a
  per-suite version map now for a problem that has not happened.

- **Q7 — orange_pi_4a's SSH host key changed.** *Recommendation: treat it as
  a prerequisite, not a side quest.* The node may have been reimaged. It is
  in the `[worker]` group, so `just bootstrap` targets it. Confirm the new
  key out of band and update the known_hosts entry before subticket 1;
  `ansible.cfg:4` sets `host_key_checking = False`, so Ansible will connect
  regardless, which makes this easy to overlook and worse to discover
  later.
