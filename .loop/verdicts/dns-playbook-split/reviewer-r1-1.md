---
type: verdict
title: 'Verdict: dns-playbook-split reviewer round 1'
description: 'reviewer verdict for round 1 of dns-playbook-split: fix.'
tags:
- verdict
- review
generated:
  by: claude-opus/5.5
  at: '2026-11-24T07:09:09+00:00'
slug: dns-playbook-split
pass: reviewer
round: 1
body_schema: verdict/1
---

## Summary

The move is correct. The play in `configure_dns.yml` matches the block from
4ae98ed7 byte for byte, apart from the blank separator line. `configure_network.yml`
is back to its state at 4ae98ed7^1. `just bootstrap` runs the new playbook last.
ADR 0033 changes only in its sources line and the appended Correction. One page
the change made false was missed: the host-firewall component still calls
`configure_network.yml` the last step of `just bootstrap`. It is a one-cell
doc fix, so the label is fix.

## Checked

- `loopctl gate stamp` from the worktree: stamp green
  10112637a4a72980727af9aea8bea2deab4b0a047f125721d208359456bd70ca. pre_commit,
  cli_tests and rows r1 to r5 all pass.
- Move fidelity: diffed lines 47 onward of `4ae98ed7:configure_network.yml`
  against lines 2 onward of `configure_dns.yml`. The only difference is the
  blank line that separated the play from the firewall plays. The header
  comment still reads right on its own: it names the two hosts, why, the
  `searches=home` trap and the Bifrost restart, and it never refers to the
  firewall file. The new file opens with `---` like every other playbook.
- r1: `cli/tests/test_bootstrap_dns_fallback.py` reads `PLAYBOOK`, which now
  points at `configure_dns.yml`. `dns_play()` asserts exactly one play writes
  the drop-in, and the three tests pin hosts, server order, options and
  `searches=home`. If the file is missing or the play is gone, the test fails.
- r2 and r3: reran by the stamp. r3's grep keeps only task lines, so a second
  task would fail the string compare.
- r4: justfile line 50 runs `configure_dns.yml` after `configure_network.yml`.
- r6 (judgment): `git diff main` on ADR 0033 shows one hunk at line 11 (the
  sources resource) and one hunk that only adds lines after the old last line
  (line 56). The Decision paragraph still names `configure_network.yml`. That
  is right for a stable record, and the Correction explains the move.
- Leftover references: grepped `.okf`, `docs`, `bootstrap`, `cli` and README
  for `configure_network`, "network playbook", playbook counts, `90-dns-fallback`
  and "last step". Every other `configure_network.yml` mention is about ufw
  ports (deployment-layers, firebat, jetson, ubuntu, the radxa and orangepi
  firewall tables, placement, tailscale-subnet-router, the breakglass runbook
  and its tests). Those stay true. `docs/` and `bootstrap/README.md` hold no
  reference. The bootstrap component's "ten playbooks" matches the ten files
  and the ten justfile lines. Nothing still refers to the old source id
  `network-playbook`.

## Findings

- f1: `.okf/components/host-firewall.md:35`, the Runs column of the Ansible
  `firewall` row, says "`configure_network.yml`, the last step of `just
  bootstrap`". That was true on main and is false now, because
  `configure_dns.yml` runs after it. The fix is to drop "the last step" or
  replace it with "step 9 of `just bootstrap`". Not blocking because the fix is
  plain text, but the operator asked for no stale references, so fix it before
  commit.

## Notes

- The radxa and orangepi node pages still cite `configure_network.yml` in
  their firewall tables, but no longer list it as a source. That matches their
  state before dns-fallback, so `kmctl review due` would not flag them when
  firewall ports change. This is not a regression from this ticket.
