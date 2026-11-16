---
type: verdict
title: 'Verdict: bifrost-router-priorities plan-reviewer round 1'
description: 'plan-reviewer verdict for round 1 of bifrost-router-priorities: pass.'
tags:
- verdict
- plan
generated:
  by: claude-opus/5.5
  at: '2026-11-16T15:00:41+00:00'
slug: bifrost-router-priorities
pass: plan-reviewer
round: 1
body_schema: verdict/1
---

## Summary

No open risk could break this plan. I checked Bifrost 2.3.1 source (tag
transports/v2.3.1). Lower priority runs first, so 10-13 run after the
hand-made 0-3. The duplicate-priority check looks only within one (scope,
scope_id), and global rules have scope_id NULL. In split mode the
config.json sync merges by id and deletes no store-only rule, so the four
Claude Code rules stay. The only other uniqueness rule is on (name, scope,
scope_id), and the router's names are not the hand-made ones.

## Checked

- Order: plugins/routing/rules/store.go:95,144,253 sort rules by Priority
  ascending ("0 is highest"), and tables/routingrules.go:40 says "Lower =
  evaluated first within scope". Rules 10-13 come after 0-3. The Claude Code
  rules do not mention complexity_tier, so engine.go never computes the tier
  for them (spike bifrost-decision-router/4).
- Priority check: framework/configstore/rdb.go SyncRoutingRules (about lines
  6435-6455) runs one deferred GROUP BY priority HAVING COUNT>1 query per
  scope it touched, filtered on `scope = ?` and `scope_id IS NULL` for global.
  It runs against the final rows (store plus file), which is why 0-3 clashed.
  With 10-13 the only global priorities are 0-3 and 10-13, so nothing clashes.
  config.go:~3935 forces ScopeID to nil for file rules with scope global. The
  operator's error shows the hand-made rules also matched `scope_id IS NULL`.
- Pruning: config.go routingRulePruneCandidates (~4701) returns nil unless
  `isConfigJSONSourceOfTruth()`, and normalizeSourceOfTruth (~439) maps an
  empty value to split. bifrost.hcl sets no source_of_truth (its comment at
  line 44 says it defaults to split). So routingRulesToDelete is empty. The
  in-memory snapshot is `governanceConfig.RoutingRules` (loaded from the
  store) plus the rules to add (config.go:4141), so the hand-made rules keep
  routing.
- Other constraints: TableRoutingRule's ID is the primary key, and Name has
  a unique index with Scope and ScopeID (idx_routing_rule_scope_name). The
  router ids and names (`not-router-passthrough`, `router-simple`,
  `router-medium`, `router-complex`) do not match the hand-made rules ("haiku
  rule" and so on, with store-made ids). In Postgres, NULL scope_id rows do
  not collide under that index anyway.
- The failed boot ran deletes and SyncRoutingRules in one transaction. That
  transaction rolled back, so the router rules did not land at 0-3, and the
  next boot inserts them as new.

## Findings

None.

## Notes

- Not risks, just stale text the build should catch:
  deployments/applications/services.tf:1050 says "priority-0 passthrough
  rule", and ADR 0029 may say the same. Once the rules move to 10-13 those
  lines are wrong.
- The passthrough at 10 still matches every non-router key, including
  requests with no virtual key. That is unchanged from the decided design.
