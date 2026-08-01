---
verdict: pass
tree: aebdbe00f6445156d3fb8422e308d5b6499d1b57
---

# Documentation-freshness review: B1-bifrost-native-auth-and-virtual-keys

## Summary

The change replaces HAProxy `http-request auth` gating of the Bifrost LLM
gateway with Bifrost's native `governance.auth_config`, gates inference via
`client.enforce_auth_on_inference: true`, provisions a Hermes virtual key
through a new `bifrost` Terraform provider, stores it in Vault at
`default/hermes/bifrost`, and moves Prometheus `/metrics` scraping of
bifrost to a dedicated `basic_auth` job using synced admin creds at
`default/prometheus/bifrost-admin`. HAProxy no longer gates bifrost (still
gates phoenix/mlflow).

All three previously-identified doc-drift findings are fixed in this tree,
and a full scan of `docs/` and `AGENTS.md`/`CLAUDE.md` found no new drift.

## Prior findings — verified fixed

1. **`docs/haproxy_reverse_proxy.md`** — previously said "`phoenix`,
   `mlflow` and `bifrost` sit behind HTTP basic auth." Now reads
   `docs/haproxy_reverse_proxy.md:26-28`:
   "`phoenix` and `mlflow` sit behind HTTP basic auth. `bifrost`
   authenticates with its own native `governance.auth_config` (admin
   creds from Vault), so HAProxy no longer gates it." Matches the new
   behavior in `deployments/infrastructure/services/haproxy.hcl` (the
   `http-request auth` line was removed from the `bifrost` backend) and
   `deployments/applications/services/bifrost.hcl` (governance.auth_config
   enabled). Fixed.

2. **`docs/monitoring.md`** — previously contrasted "unlike `phoenix`,
   `mlflow` and `bifrost`." Now reads `docs/monitoring.md:35-36`:
   "`prometheus` and `loki` backends carried no `http-request auth` line,
   unlike `phoenix` and `mlflow` in the same file." bifrost dropped from
   the contrast, consistent with HAProxy no longer gating bifrost. Fixed.

3. **`AGENTS.md`** (which `CLAUDE.md` symlinks to) — the "Terraform
   providers" list previously omitted `bifrost`. Now reads
   `AGENTS.md:125` / `CLAUDE.md:125`:
   "Nomad, Vault, Consul, MinIO, PostgreSQL, Bifrost — all configured in
   respective `providers.tf` files." Matches the new provider registered
   in `deployments/applications/providers.tf`. Fixed.

## Scan for new drift — none found

- **Bifrost as HAProxy-basic-auth-gated elsewhere**: `grep -rni bifrost`
  across `docs/` returns only the route table entry
  (`docs/haproxy_reverse_proxy.md:24`, unchanged, still a valid route) and
  the fixed prose at line 26. No other doc describes bifrost as
  HAProxy-gated.

- **New `bifrost` Terraform provider omitted from docs**: only
  `AGENTS.md:125` lists providers, and it now includes Bifrost. No other
  doc enumerates the provider set.

- **Prometheus scraping bifrost without basic_auth**: the only doc that
  describes Prometheus scrape targets is `docs/monitoring.md`. Its
  "Scrape Targets" table (`docs/monitoring.md:216-225`) sits inside the
  section explicitly labeled as history: "The rest of this document is
  the original build plan for the stack. It predates the move of
  Prometheus and Grafana from firebat to `ubuntu` ... so treat the
  addresses and file lists below as history rather than as current
  state." (`docs/monitoring.md:200-204`). It never listed bifrost, so the
  new dedicated `basic_auth` scrape job in
  `deployments/infrastructure/services/prometheus.hcl` does not
  contradict any current-state doc claim. The current-state section
  (`docs/monitoring.md:1-198`) covers Prometheus/Loki firewall and edge
  routing, not the bifrost scrape, so it is not stale.

- **Old hardcoded `BIFROST_API_KEY=hermes-local`**: `grep -rni
  'hermes-local\|BIFROST_API_KEY'` across all `*.md` outside `.loop/`
  returns no matches. The hardcoded value was removed from
  `deployments/applications/services/hermes.hcl` and replaced with a
  Vault template reading `default/hermes/bifrost`; no doc ever described
  the hardcoded value, so no doc is stale.

- **Hermes virtual key / Vault path `default/hermes/bifrost`**: no doc
  describes Hermes' bifrost credential path, so the new Vault secret and
  provider resource introduce no documented surface that drifted.

- **`enforce_auth_on_inference` / `governance.auth_config`**: no doc
  described Bifrost's auth model before this change, so the new config
  keys introduce no previously-documented surface that drifted. The one
  doc that now mentions the model
  (`docs/haproxy_reverse_proxy.md:26-28`) accurately names
  `governance.auth_config`.

## Verdict

pass. Every documented user-facing surface the change touches — the
HAProxy basic-auth gating prose, the monitoring contrast, and the
Terraform provider list — was updated in the same diff. No remaining doc
describes bifrost as HAProxy-gated, omits the `bifrost` provider,
describes a bifrost scrape without basic_auth, or references the old
hardcoded `BIFROST_API_KEY=hermes-local`.