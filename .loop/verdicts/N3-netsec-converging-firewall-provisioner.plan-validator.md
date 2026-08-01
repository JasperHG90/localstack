---
verdict: fail
---

# N3-netsec-converging-firewall-provisioner — plan review (pass: plan-validator)

Plan: `/home/vscode/workspace/.loop/plans/N3-netsec-converging-firewall-provisioner.md`
Fingerprint supplied: `eeefe34f5ed69d9985f8a5ecc4a96b9f7a658f09515c2d3bbe14e95e5150597a`.
Recomputed here and it matches. This is a `fail`, so the contract omits the
`plan:` line and this verdict authorizes no flip to `ready`.

**What I ran.** Read-only SSH to all five nodes (`sudo ufw status numbered`,
`sudo grep '^### tuple ###' /etc/ufw/user.rules`, `sudo iptables -S
ufw-user-input`, and reads of ufw's own Python source on the rpi4b). No ufw
rule was added, deleted or reloaded; no reconcile was run; nothing was
restarted. Two Terraform probes ran in a scratch directory against the local
null provider with `local-exec` only, so no probe touched the cluster.
`terraform state list` against the real Consul backend was denied (no token in
this environment), noted under P15.

## Premise verdict: BROKEN

The plan's headline claim is true and I confirmed it live. Three of the things
it builds on top of that claim are not true, and each one on its own stops the
ticket: the reconcile can never run on a plain apply, the first-apply migration
errors before it deletes anything, and the prune scope as defined deletes
nothing at all. The drift the plan and the eval marker point at as motivation
no longer exists on any host, while two declared rules really are missing and
the plan does not know about them.

## Per assumption

**P1 — neither Terraform provisioner removes a rule. HOLDS.**
`deployments/infrastructure/services.tf:279-295` and
`deployments/applications/services.tf:85-102` each carry one create-time
`remote-exec` with `inline = [for rule in each.value.rules : "sudo ufw
${rule}"]` (`:293`, `:100`) and no `when = destroy`. Live corroboration on
radxa: `8642/tcp ALLOW IN 192.168.0.0/16` is still rule `[10]` while the map
declares only `192.168.2.30` and `192.168.2.46`
(`applications/services.tf:46-47`). The superseded broad rule outlived the
narrowing exactly as claimed.

**P2 — the plan covers every rule source. HOLDS.**
`grep -rn 'resource "null_resource" "firewall"'` returns exactly two blocks
(`infrastructure/services.tf:279`, `applications/services.tf:85`). A `grep -rl
ufw` excluding `.git`, `.terraform`, `.loop` and `.graveyard` returns the
Ansible role, both `services.tf`, `docs/monitoring.md`, `ROADMAP.md`, and an
alert description. There is no third provisioner. The "third block at
`applications/services.tf:22-102`" from the N4 verdict is this same
applications locals plus resource, which N4's plan had missed and which N3
does name in both its Context (`:41-43`) and its Code surface (`:107-108`).
This attack does not land on N3.

**P3 — "the Ansible half already converges correctly". BREAKS.**
`bootstrap/roles/firewall/tasks/main.yml:15-22` is a bare `rule: allow` loop
over `firewall_ufw_ports` with no `delete` branch. `community.general.ufw` is
idempotent on add and never prunes, so dropping a port from
`configure_network.yml` leaves it open on the host, which is the same defect
the ticket exists to fix. Live orphans that no map or playbook declares:
jetson `6006/tcp`, `4317/tcp` and `8100/tcp`; radxa `9119/tcp` from
`192.168.0.0/16` and from `192.168.2.30`. `grep -rn '9119\|8100'` across the
repo returns nothing. Keeping the role out of scope is still a reasonable
non-goal, but the Context states a property the role does not have, and the
docs subticket would repeat it.

**P4 — the reconcile runs on every apply (Requirement 2). BREAKS, and this is
the one that sinks the plan.**
`null_resource` provisioners run at create and replace only. With `triggers`
unchanged there is no diff, so no provisioner runs and nothing connects to any
host. Probed: after applying the model config, a second `terraform apply` with
no config change printed "No changes. Your infrastructure matches the
configuration. ... 0 added, 0 changed, 0 destroyed." The plan diagnoses the
cause correctly at `:44-48` ("`null_resource` has no `Read`, so drift is
structurally invisible") and then asserts Requirement 2 at `:81-82` ("If a
declared rule is missing from the host, the next apply restores it, without
needing the map to change") with no mechanism to make the reconcile fire. The
Code surface says only "replace the create-only `inline` with the reconcile"
(`:104-106`), which changes what runs, not when. Nothing in the plan closes
this gap.

**P5 — a destroy provisioner may reference only `self`, so `host` and
`ssh_user` must be in `triggers`. HOLDS, with a useful extra.**
Confirmed by probe. Also confirmed, against the stricter reading someone might
take from Requirement 5: `path.root` and `file()` ARE legal inside a
destroy-time `connection` block. A config with `private_key =
file("${path.root}/../../.ssh/id_rsa")` under `when = destroy` returned
"Success! The configuration is valid." Record this, because the wrong reading
pushes the private key into `triggers` and therefore into state.

**P6 — "the first apply replaces all 20 resources ... every declared rule is
deleted and then re-added" (Risk, `:150-155`). BREAKS.**
It does not get that far. Modelled the exact migration (old state with
`triggers = {rules}`, new config adding `host` and `ssh_user` plus a
`when = destroy` provisioner reading `self.triggers["ssh_user"]`). `plan`
shows the replacement, and `apply` fails at the destroy step:

    Error: Invalid index
    self.triggers is map of string with 1 element
    The given key does not identify an element in this collection value.

The destroy provisioner is taken from configuration, but `self` is the prior
state object, which has only `rules`. Nothing is destroyed and the apply
errors. Subticket 1 as written ("Add `host` and `ssh_user` to `triggers` in
both roots and add the `when = destroy` provisioner", `:167-169`) therefore
cannot be applied at all. A `lookup(self.triggers, "host", "")` fallback lets
the apply proceed but yields an empty host, which for `remote-exec` means an
SSH connection to nowhere: probed, the destroy step printed
`user=NONE host=NONE`. The safe shape is two applies, first the `triggers`
change alone, then the destroy provisioner once every instance in state
carries the keys. The plan needs to say so.

**P7 — "only `(port, source, proto)` tuples that this map has declared may be
considered for deletion" (Requirement 3, `:83-88`). BREAKS as a definition.**
At reconcile time the only tuples the map has declared are exactly the desired
ones, and every desired tuple must exist. Under that predicate the delete set
is empty by construction: the prune is a no-op, Requirement 1 is carried
entirely by the destroy provisioner, and eval row 3's negative control ("a
fixture where a rule genuinely IS in scope and should be deleted") has no
satisfying input. It also fails the plan's own motivating case: radxa's
`8642/tcp` from `192.168.0.0/16` is not a declared tuple, so a tuple-scoped
prune leaves it, and "N1's narrowing left the superseded broad rules live"
(`:27-28`) stays unfixed on the reconcile path.

The predicate that works is ownership by `(host, port)`: delete a live rule
whose port this entry declares on this host and whose source this entry does
not. I checked that reading is safe today and it is, for two reasons that both
need stating and guarding:

- No port in either Terraform map collides with an Ansible-owned port. Ansible
  owns 22, 8200, 8201, 8300, 8301, 8500, 8600, 4646, 4647, 4648 and the range
  `20000:32000` (`configure_network.yml:10-25`, `:35-46`). Terraform declares
  5432, 9000, 9001, 80, 443, 8404, 5000, 5001, 9090, 3000, 8080, 9100, 9187,
  4222, 8222, 7777, 6006, 4317, 8000, 8642, 3100, 5050. Disjoint, and no
  Terraform port falls inside 20000-32000. That is a fact about today's
  numbers, not a property of the design, so it needs a check in the script.
- Map entries that share a host declare disjoint ports. Five infra entries
  target `192.168.2.30` (5432 / 80,443,8404 / 5000,5001 / 9100 / 9187), four
  plus one applications entry target `192.168.2.47` (9090 / 3000 / 8080 / 9100
  / 3100), and so on. Were they not disjoint, two entries on one host would
  each delete the other's rules on every apply. The plan never mentions that
  several entries share a host.

**P8 — the port 22 guard is real and expressible. HOLDS.**
No `firewall_rules` entry in either root declares 22, and 22 is Ansible-owned
(`configure_network.yml:10-11` manager, `:35` worker). `22 ALLOW IN
192.168.0.0/16` is present on all five hosts, plus `100.64.0.0/10` on firebat
only. A refusal list containing 22 is a one-line filter, independent of the
map, exactly as Requirement 4 describes.

**P9 — ufw normalizes on read, so an unnormalized matcher thrashes. HOLDS,
with two corrections the script has to absorb.**
Confirmed live: `allow from 192.168.2.47 to any port 9090 proto tcp` reads
back as `9090/tcp ALLOW IN 192.168.2.47`, with no `/32`, while `iptables -S`
shows `-s 192.168.2.47/32`. Corrections: a proto-less rule is a single line in
`ufw status` with no suffix (`22 ALLOW IN 192.168.0.0/16`, `8301`, `8600`,
`4647`); the tcp-plus-udp doubling the plan and eval row 7 describe appears in
the iptables chain, not in `ufw status`. And the range renders as
`20000:32000/tcp`, which a parser doing `int(port)` will not survive. Every
Terraform-declared rule carries `proto tcp`, so the proto-less and range forms
only ever arrive from the Ansible-owned side, which is precisely the side the
matcher must not mis-scope.

**P10 — `ufw allow` is idempotent and `ufw delete` on a missing rule is a
no-op exiting 0. HOLDS.**
Read from ufw 0.36.2 source on `192.168.2.47`:
`/usr/lib/python3/dist-packages/ufw/backend_iptables.py:1071-1081` returns the
strings "Could not delete non-existent rule" and "Skipping adding existing
rule" rather than raising, and `/usr/sbin/ufw:159` ends at `sys.exit(0)`. One
consequence to record: the exit code carries no information either way, so the
reconcile must parse the message if it wants to report what it changed.

**P11 — `ufw --dry-run` prints the projected ruleset and mutates nothing.
HOLDS.**
`backend_iptables.py:811-813` sets `fd = sys.stdout.fileno()` under dryrun
instead of the temp rules file, and `:1105` guards the live-chain work with
`if self.is_enabled() and not self.dryrun`. Caveat for Requirement 6
(`:94-96`): the output is the whole `iptables-restore` payload, not a list of
what would be added and deleted. The add/delete view is the script's own diff,
and the plan reads as though `--dry-run` supplies it.

**P12 — drift between ufw's database and the live chain on `192.168.2.47`
(3000, 9100) and `192.168.2.30` (9187). BREAKS. Refuted on all five hosts.**
Tuple counts and chain counts agree everywhere once the proto-less rules'
udp twins are accounted for: `.47` 23 tuples / 27 chain lines, `.30` 21 / 26,
`.29` 14 / 18, `.46` 14 / 18, `.50` 20 / 24. On `.47`, 3000 and 9100 are in
both the database and the chain. On `.30`, 9187 is in neither.
`docs/monitoring.md:105-107` and `:129-130` record the divergence as measured
2026-07-26 and `:151-158` gives the `-replace` remedy; the remedy evidently
ran. The condition the plan cites as motivation, and that eval row 9 scores,
is gone.

**P13 — Q3's duplicate rules on `192.168.2.47` for 3000 and 9100. BREAKS.**
`.47` carries exactly one 9100 rule and two 3000 rules with different sources,
`100.64.0.0/10` and `192.168.0.0/16`, both declared
(`infrastructure/services.tf:221-222`). No host carries an exact duplicate.
Q3's recommendation solves a problem that is not there.

**P14 — real drift the plan does not know about. Not in the plan at all.**
Firebat is missing two rules its own map declares: `5000/tcp` from
`192.168.0.0/16` (`infrastructure/services.tf:200`, the registry entry, whose
sibling 5001 IS present) and `9187/tcp` from `192.168.2.47`
(`:264`, postgres_exporter). Both are absent from `user.rules` and from the
chain. This is a better and live instance of the ticket's premise than the
stale divergence it cites, and it changes what eval rows 5 and 8 will see.

**P15 — "`terraform state show` returns an `id` and `triggers.rules` and
nothing about the host" (`:44-48`). HOLDS by construction, not by direct
read.** The real state is behind the Consul backend and my read was refused
("Permission denied: token ... lacks permission 'key:read' on
'terraform/infrastructure'"), so I did not read the cluster's state. The null
provider's schema has only `id` and `triggers`, and my sandbox
`terraform state show` printed exactly that shape.

**P16 — parallelism. Missing, and the repo's own docs say it matters.**
`docs/monitoring.md:160-164` states that concurrent ufw writes against one
host can lose each other's rules because ufw reads the rule set before taking
`/run/ufw.lock`. I confirmed the ordering: `/usr/sbin/ufw:114-120` builds
`UFWFrontend`, which parses `user.rules`, and `:129` calls `create_lock` after
that. Five infra entries target `192.168.2.30` and five entries across the two
roots target `192.168.2.47`, and Terraform's default parallelism is 10. The
plan's subticket 4 says apply per host with `-target` (`:174`) and never
mentions `-parallelism=1`, which the existing runbook already requires for a
much smaller change. A read-modify-write reconcile turns "an add can be lost"
into "a sibling entry's rule can be deleted".

**P17 — scale and anchors. HOLDS.**
14 infra entries, 6 applications entries, five hosts, all counted. Anchors
resolve: `configure_network.yml:9` and `:34`, `services.tf:282-284` and
`:88-91`, `:290` and `applications/services.tf:97`, `providers.tf:1-24` in the
infrastructure root, `docs/monitoring.md` "Applying a change to these rules"
at `:90`. One trivial slip: the applications resource spans 85-102, not
85-101.

## Most dangerous assumption

**P4.** Requirement 2 asks a create-time provisioner on a `null_resource` to
run when nothing has changed, and it cannot. Every line of correct reconcile
logic sits behind a trigger that never fires. It takes the drift half of the
ticket with it, and it silently converts eval row 5 into a failure and eval
row 7 into a row that passes because nothing happened.

## Eval marker findings

`/home/vscode/workspace/.loop/evals/N3-netsec-converging-firewall-provisioner.md`,
operator-signed 2026-08-01, so I have not edited it. Stating plainly what
cannot pass, cannot fail, or scores from config:

- **Row 5 (a declared rule missing from a host is restored) cannot pass** under
  the planned design. "Apply without changing any Terraform" is a no-op apply
  (P4). Separately, it need not manufacture a subject: firebat is already
  missing 5000 and 9187 (P14).
- **Row 7 (stable, not thrashing) is unexecutable as written.** Its input says
  "Capture the reconcile's output both times", and on the second apply the
  reconcile does not run, so there is no output. "Zero additions and zero
  deletions" is then satisfied by nothing having happened, which is the exact
  vacuous pass the row was written to prevent. It must require evidence that
  the reconcile ran and reported an empty diff.
- **Row 9 (database and chain agree) cannot fail.** They already agree on all
  five hosts (P12), before any code change. Its rationale names a divergence
  that no longer exists.
- **Row 3's negative control has no satisfying input** while Requirement 3
  defines scope by declared tuple (P7). Fix the ownership predicate first, or
  row 3 cannot be built, and rows 1 and 2 keep the vacuity that row 3 exists
  to catch.
- **Row 8 contradicts row 5.** "The only differences are rules this ticket
  intends to remove" fails on firebat the moment the reconcile works, because
  it must ADD 5000 and 9187. Reword to permit additions of declared-but-missing
  rules, and say what happens to the orphans no map owns: radxa `8642` from
  `192.168.0.0/16` plus `9119` twice, jetson `6006`, `4317`, `8100`. A
  port-scoped prune removes the first and leaves the rest.
- **Rows 1, 2, 4, 6 are sound.** They probe the artifact or a socket rather
  than reading config. Row 6 names all five hosts and the hostnames are exact:
  `firebat`, `orangepi4a`, `jetson-orin-nano`, `ubuntu`, `radxa-dragon-q6a`,
  all confirmed. Row 4's socket probe is the right shape for the primary
  deliverable.
- **Row 10 is executable** without stopping a node: blocking SSH from the
  applying host is enough, and that is the cheaper reading.
- **Rows 11 and 12** score a scope guard and documentation, where reading the
  diff and the prose is the correct method.

## Required fixes before this plan leaves PLANNING

1. **Answer P4 explicitly.** State how the reconcile runs when the map has not
   changed, and accept the cost. A `timestamp()` trigger replaces all 20
   resources on every apply and drags the destroy step with it. `terraform_data`
   has the same create-time semantics. `-replace` per resource is manual. If no
   option is acceptable, drop Requirement 2 and say the ticket fixes removal
   only, and waive eval rows 5 and 7 with the reason recorded.
2. **Re-sequence subticket 1 into two applies**: `triggers` first, the
   `when = destroy` provisioner second, once every instance in state carries
   `host` and `ssh_user`. Quote the probed error so the implementer does not
   rediscover it. Correct the Risk paragraph at `:150-155`, which describes a
   deletion window that the failure prevents from ever opening.
3. **Redefine the prune scope** from "declared tuple" to ownership by
   `(host, port)`, or whatever predicate makes the delete set non-empty, and
   carry the two facts that make it safe today: no Terraform port collides with
   an Ansible-owned port or the `20000:32000` range, and entries sharing a host
   declare disjoint ports. Add a startup assertion for both rather than relying
   on the current numbers.
4. **Say that several map entries share a host** (five on `192.168.2.30`, five
   across both roots on `192.168.2.47`) and that each entry owns only its own
   ports there, so two entries cannot delete each other's rules.
5. **Add the parallelism constraint.** `-parallelism=1` for any apply that
   touches ufw, with the reason from `docs/monitoring.md:160-164` and
   `/usr/sbin/ufw:114-129`.
6. **Replace the drift citations.** Drop the `.47` 3000/9100 and `.30` 9187
   database-versus-chain divergence, which is healed, and put in its place the
   two declared rules actually missing from firebat, 5000 and 9187 (P14). Drop
   Q3 or restate it: there are no duplicates.
7. **Correct the Context claim about Ansible** (`:35-43`, `:72-73`). The role
   is idempotent on add and never deletes; it leaks removed rules the same way.
   Keeping it out of scope is fine, saying it converges is not.
8. **Correct the normalization detail** in Risk (`:156-161`): the tcp/udp
   doubling is in the chain, not in `ufw status`; a proto-less rule is one
   suffix-less line; the range prints as `20000:32000/tcp`. Add both forms to
   the offline fixture, which the eval's row 1 already gestures at.
9. **Note that `path.root` and `file()` are legal in a destroy-time
   connection**, so the SSH key stays out of `triggers` and out of state.
10. **State that `ufw --dry-run` prints a full projected ruleset**, not an
    add/delete list, so Requirement 6's operator-readable diff is the script's
    own output.
11. **Fix eval rows 3, 5, 7, 8 and 9** per the section above. The marker is
    operator-signed, so this needs the operator, not an edit in passing.

## Contract hygiene (checked, secondary)

Non-goals are explicit and specific (`:65-75`). Forks live in Open Questions
with recommendations, and Q3's factual basis is wrong (P13). The gate command
`just pre_commit` exists (root `justfile:18`). There is no unit-test harness
for HCL, and the plan says so and homes its checks in the offline fixture and
the eval marker, which is right for this ticket. The code surface is real and
its anchors resolve (P17). What the surface is missing is not a file but the
answer to P4.

## Bottom line

The premise that motivates the ticket is true and I watched it on radxa. The
design that follows from it does not work: the reconcile never runs on a
routine apply, the migration errors on its first step, and the prune as scoped
has an empty delete set. The evidence it cites as urgent has been repaired,
while two rules it declares are missing from firebat and it does not know.
Stays at `PLANNING`.
