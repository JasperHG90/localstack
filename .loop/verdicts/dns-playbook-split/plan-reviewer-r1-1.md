---
type: verdict
title: 'Verdict: dns-playbook-split plan-reviewer round 1'
description: 'plan-reviewer verdict for round 1 of dns-playbook-split: fail.'
tags:
- verdict
- plan
generated:
  by: claude-opus/5.5
  at: '2026-11-24T07:02:35+00:00'
slug: dns-playbook-split
pass: plan-reviewer
round: 1
body_schema: verdict/1
---

## Summary

The approach works and the scope is right. The play is one self-contained
block appended after the two firewall plays, `git diff 4ae98ed7^1 HEAD` on
`configure_network.yml` shows only that block added, so the move and the
restore are mechanical. Running both playbooks from `just bootstrap` changes
no host state. One finding: the plan edits ADR 0033 in place, which the
bundle's rule for stable records forbids. The rule's own form for this case is
an appended Correction section, not a new record.

## Checked

- Plan front matter and facts: one problem, one goal, O1 behaviour (playbook,
  justfile, test), O2 support needing O1 (bundle pages). They match the prose.
  `touches` covers every file the prose names.
- `bootstrap/playbooks/configure_network.yml` against `4ae98ed7^1`: the only
  difference is the DNS block (comment header, play, handler) at the end.
  The play has its own tasks and handlers and no shared vars, so it stands
  alone in a new file.
- `bootstrap/ansible.cfg` sets the inventory, and `bootstrap/inventory/cluster.ini`
  defines hosts `radxa` and `orange_pi_4a`, so `hosts: radxa:orange_pi_4a`
  resolves the same from the new file.
- `bootstrap/justfile` `bootstrap` runs `configure_network.yml` last.
  dns-fallback never touched the justfile, so adding a line is all it needs.
- `cli/tests/test_bootstrap_dns_fallback.py` reads one `PLAYBOOK` constant;
  repointing it is enough. `cli/tests/commands/test_breakglass_runbook_facts.py`
  pins `configure_network.yml` for firewall ports only and is unaffected by
  removing the DNS play.
- Every other `configure_network.yml` mention under `.okf/` and `docs/`
  (host-firewall, deployment-layers, tailscale-subnet-router, placement, the
  other node pages, breakglass runbook) is about the firewall and stays right.
  No `docs/` page mentions the DNS fallback.
- `git show 4ae98ed7` on the two node pages: dns-fallback added the
  `network-playbook` source entry and the "DNS falls back past the router"
  bullet. Those are what the plan repoints; the firewall rows predate it.
- ADR 0033 is `status: stable`; `.claude/rules/okf-bundle.md` lines 92-101.

## Findings

- p1: ADR 0033 is stable, and the bundle rule says a stable record gets an
  appended `## Correction, YYYY-MM-DD` section rather than a rewrite. The
  operator's reading (not a reversal, so no new record) is right, but in-place
  editing is not the third option the rule allows. Revise O2 to append a
  Correction section and update the `sources` entry. That keeps the record
  honest about what dns-fallback shipped and stays within the rule.

## Notes

- Build details, not findings: each touched concept needs a line in
  `.okf/log.md`; `.okf/summary.md` `checked.against` names ADR 0033, so
  `kmctl check` may ask for `kmctl summary ack` after the ADR changes; the
  test's module docstring says "The network playbook" and should name the DNS
  playbook.
- Splitting is not needed: two outcomes, one cause.
