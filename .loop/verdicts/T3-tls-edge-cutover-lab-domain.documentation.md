---
verdict: pass
tree: c6c5223a06bae9ec8967724b3d92a3e70de94892
---

# Documentation review: T3-tls-edge-cutover-lab-domain (cycle 3, final)

**The docs are committable as they stand.** Cycle 2's RF1 is discharged: both
wildcard paragraphs are now true, I verified each one empirically rather than
by reading, and they do not contradict each other, the ticket plan, or the
archived T1 record. Nothing else in the four changed docs or in the rest of
`docs/` describes the pre-cutover world. There are no required fixes and
nothing blocking.

## 1. The two wildcard paragraphs — both true, verified

`docs/haproxy_reverse_proxy.md:93-100` (the rule) and `:102-106` (F3's
history) now carry different claims and are correctly separated.

I generated two throwaway self-signed certificates and ran OpenSSL's own
hostname verifier, which is the code path `curl` uses:

```
*.localstack            vs grafana.localstack                -> error 62 hostname mismatch
*.lab.orangecluster.nl  vs grafana.lab.orangecluster.nl      -> OK
*.lab.orangecluster.nl  vs deep.staging.lab.orangecluster.nl -> error 62 hostname mismatch
```

That settles all three load-bearing statements:

- **Paragraph 1's TLS half** ("A TLS wildcard matches a single label ... it does
  **not** cover `myservice.staging.lab.orangecluster.nl`") is confirmed by the
  third line.
- **Paragraph 1's DNS half** ("the DNS wildcard matches at any depth, so a
  two-label name resolves and the edge answers it") is confirmed live:
  `dig +short @1.1.1.1 deep.staging.lab.orangecluster.nl` and
  `a.b.lab.orangecluster.nl` both return `192.168.2.30`.
- **Paragraph 2** ("it was issued for `*.localstack`, and a wildcard has to sit
  at least two labels above the root. `grafana.localstack` was already flat and
  still no client would accept it") is confirmed by the first line, which
  reproduces the exact `error 62` the ticket plan cites at
  `.loop/plans/T3-tls-edge-cutover-lab-domain.md:23-25`. The flat name was
  rejected. The reason was the certificate's own position, not the depth of the
  request.

No contradiction between them. Paragraph 2 opens by saying it is "a different
reason", scopes its claim to the certificate rather than the hostname, and
closes with "Flat names are necessary, not sufficient", which points back at
paragraph 1's advice instead of overriding it. The wrong lesson cycle 2 caught
("`*.localstack` would have worked had the names stayed flat") is gone, and the
correct lesson a reader takes away is: keep names one label deep **and** put
them under a real domain a public CA will issue for.

Carried nit, unchanged and still advisory: `:93` binds the one-label condition
to DNS as well as to the certificate ("No DNS record **and** no certificate
change is needed, as long as..."), while `:97-98` two sentences later correctly
says DNS matches at any depth. The paragraph untangles itself, and the
operational advice it lands on is right, so no reader takes a wrong action from
it. Precision, not a defect.

## 2. The 30-day figure is consistent everywhere it appears

| Location | Text | Agrees |
|---|---|---|
| `deployments/infrastructure/services/acme.hcl:65` | `args = ["run", "--renew-days", "30"]` | source of truth |
| `docs/tls-certificates.md:25-28` | `lego run --renew-days 30`, "the full 30 days of margin survives" | yes |
| `docs/tls-certificates.md:133` | "The 30-day margin means a failure is not urgent, but it is silent" | yes |
| `.loop/plans/T3-...md:110-111` | "the gap ... is 30 days, not the 90-day life of the leaf" | yes |
| `.loop/evals/T3-...md:32` | "with a daily run at `--renew-days 30` the window ... is 30 days" | yes |

The only surviving `90` are the leaf's own lifetime (`acme.hcl:91`, the eval's
struck-through row title), which is a different and correct fact. Docs and
ticket artifacts agree.

## 3. Nothing from the adversarial pass broke a doc or a cross-reference

Every retargeted anchor in `F1-*`, `F9-*` and `S2-*` resolves on this tree, and
the rewritten prose around them is true, not just the paths:
`vault_policy.acme_tls_write` is at `deployments/infrastructure/acme.tf:41`,
`vault_jwt_auth_backend_role.acme` at `:66`, `token_policies` listing BOTH
`nomad-workloads` and the dedicated policy at `:87` (which is what the F9 prose
now claims), and the consumer `vault { role = "${vault_role}" }` is at
`deployments/infrastructure/services/acme.hcl:73-75` exactly as cited.

No file under `docs/`, `deployments/` or `README.md` references `pki.tf`,
`haproxy_pki`, or `pki/issue` any more. The only remaining mentions are T3's own
eval (correctly describing the deletion) and the archived F3 verdict.

Eval rows 7 and 11 read cleanly now; row 11's two halves agree, which closes the
cycle-2 advisory on it.

## 4. `docs/` sweep — clean

All fifteen markdown files plus `docs/openfang/`, `docs/architecture/`,
`docs/notes/` and `README.md` re-swept. Surviving `localstack` strings, none of
them an edge hostname:

- `docs/riscv-integration.md:108` — the Nomad datacenter name (`haproxy.hcl:2`
  still declares `datacenters = ["localstack"]`).
- `docs/gcs-backups.md:37` — a GCP service account name.
- `docs/nats.md:24` — a NATS CLI context name.
- `.consul` service names in `docs/nats.md`, `docs/nats-postgres-cdc-bridge.md`,
  already documented as broken and assigned elsewhere at `docs/dns.md:105-121`.
- `README.md:2` — the logo filename.
- `docs/haproxy_reverse_proxy.md:103-104` — the deliberate historical mention
  reviewed above.

Verified against the running config: the twelve-row hostname table at
`docs/haproxy_reverse_proxy.md:15-26` matches `haproxy.hcl:98-168` on hostname,
node, address and port in all twelve rows; the three basic-auth backends named
at `:28-29` are exactly the three carrying `http-request auth`
(`haproxy.hcl:147,163,167`); the node names in the table match the Nomad
`unique.hostname` constraints across `deployments/`, including `ubuntu` for
`192.168.2.47`, where the Ansible inventory calls the same box
`raspberry_pi_4b`.

Also verified the doc's port story against the job: `frontend http_in` binds
`*:80` and does nothing but a 301 (`haproxy.hcl:91-93`), `frontend https_in`
binds `*:443 ssl crt` and holds every ACL (`:95-122`), `frontend stats` binds
`*:8404` outside TLS (`:124`). Dropping the old "mapped to 8080 inside the
container" note was right: the job runs `network_mode = "host"` with
`NET_BIND_SERVICE`, so the `to = 8080` mapping is inert and the old sentence was
misleading.

## 5. Cross-document consistency holds

`docs/dns.md`, `docs/monitoring.md`, `docs/tls-certificates.md` and
`docs/haproxy_reverse_proxy.md` agree on the record set (`*.lab` + bare `lab`
A records plus CAA, `dns.md:10-27` ≡ `tls-certificates.md:61-72`), on the
RFC1918 reasoning and what it does and does not expose, on the Tailscale
subnet-route caveat, on which backends carry basic auth, and on how the PEM is
assembled (all agree `issuer_chain` is not appended, matching
`haproxy.hcl:62-72`). `tls-certificates.md:53-57` and
`haproxy_reverse_proxy.md:51-60` cross-reference each other on the
issuance/serving split without duplicating or disagreeing.

The one register divergence carried from cycle 2 remains:
`haproxy_reverse_proxy.md:3-6` asserts the trusted-cert edge flatly while
`monitoring.md:39-41` scopes it to the pending apply. Both are defensible in a
repo whose docs describe declared state, and `monitoring.md` sets that
convention for itself at `:8-11` for N1's firewall rules, so the file is
internally consistent. Not a defect.

## 6. Every backticked path, identifier, command and volume name resolves

Re-checked individually: `acme_lego_state` (`acme.tf:14-15`, consumed at
`services/acme.hcl:28`), `/acme-state` (`acme.hcl:70,150`),
`/acme-state/staging` and `/acme-state/production` (`acme.tf:121`),
`secret/default/haproxy/tls` (`tls_secret` at `services.tf:325` with
`secret_mount = "secret"` in `vars/prod.tfvars:1`, so the KV2 API path is
`secret/data/default/haproxy/tls` as `tls-certificates.md:38` states and the
CLI path is the bare form the `vault kv get` at `:104` uses),
`secret/data/default/acme/transip` (`acme.tf:100-102`), `var.acme_server` with
its production default (`variables.tf:49`), the `acme` job name
(`acme.hcl:1`), `LEGO_DNS_RESOLVERS` (`acme.hcl:104`), the 04:00
Europe/Amsterdam cron (`acme.hcl:11-12`), `https_in` / `http_in` /
`frontend stats` / `prometheus-exporter` / `openfang_users`, `just apply` from
`deployments/infrastructure/` (`justfile:11-13`), and the four inter-doc
references. The `dig` block at `docs/dns.md:90-95` reproduces exactly, apex
included (`orangecluster.nl -> 37.97.254.29`).

## 7. Slop scan, all four layers, on the four changed docs

- **Layer 0.** No identity leaks. No `TODO`/`FIXME`/`XXX`/`HACK`. No
  hallucinated identifier, path or command (section 6), and the one factual
  attribution that failed last cycle now checks out empirically (section 1).
- **Layer 1.** `haproxy_reverse_proxy.md` leads with its takeaway and every
  section earns its place; the rewritten DNS, TLS and PostgreSQL sections are
  each shorter than what they replaced. `tls-certificates.md`'s two edited
  passages replace vaguer text with the same or fewer words.
  `monitoring.md`'s new paragraph is shorter than the one it replaced.
- **Layer 2.** Zero tier-1 slop terms. Zero "not only"/"not just", zero hedging
  seesaws, zero throat-clearing openers, zero three-fragment bursts, zero
  significance-cluster phrases, zero British spellings, zero smart quotes.
  Em dashes: 0 in `monitoring.md`, `tls-certificates.md` and
  `riscv-integration.md`; 2 in `haproxy_reverse_proxy.md`, both the pre-existing
  list separator in the Files section (`:110,112`), inside budget. Every ` -- `,
  every prose `->` and every line over 80 characters that this diff touched is
  a pre-existing line the diff only substituted a hostname into
  (`monitoring.md:364-365`, `riscv-integration.md:190`), which is correct under
  CLAUDE.md §3. The single prose semicolon (`tls-certificates.md:140`) is on an
  untouched line. `necessary, not sufficient` at `:105` is a contrastive
  negation by pattern but a canonical logic idiom, load-bearing here; surfaced,
  not required.
- **Layer 3.** The only quality claim is "publicly-trusted", backed by the
  production ACME endpoint being the default (`variables.tf:49`) and by eval
  row 2, which proves it with an unflagged `curl`.

## 8. A reader who has never seen this ticket gets to a working result

`docs/dns.md` tells them nothing needs configuring, names the one failure mode
(rebind filtering) and gives four `dig` commands that reproduce.
`docs/haproxy_reverse_proxy.md` gives the twelve routes, the ports, which are
authenticated, the add-a-service runbook, and the wildcard rule they need
before inventing a hostname. `docs/tls-certificates.md` covers issuance, the
stored field shape, the checks and the recovery path. The two cross-reference
each other on the split. I found nothing they would carry away wrong.

## Advisories — none blocking, none required

1. **The history marker at `docs/monitoring.md:155-158`.** Not acting on it is
   acceptable. Three blocks below the marker are now deliberately current (2g at
   `:318-341`, verification steps 3-4 at `:364-365`) while their neighbors are
   genuinely stale (2d still provisions the Grafana datasource at
   `http://192.168.2.30:9090` at `:289`, where `services/grafana.hcl:94` really
   says `192.168.2.47:9090`; the Placement Decision at `:166` still puts both on
   firebat). The marker therefore tells a reader to distrust content that is
   correct. Nobody is led to a wrong action, which is why it does not block, but
   a future doc pass should add the one clause naming the exceptions.
2. **The aging tense at `docs/monitoring.md:39-41` and the self-referential tail
   at `:41-42`.** Acceptable. The paragraph is honest on this tree, and the file
   already uses the declared-vs-applied register at `:8-11`, so it is internally
   consistent rather than an outlier. It will read oddly after the apply; that
   is cosmetic and reversible.
3. **Outside `docs/`, for whoever owns the eval.**
   `.loop/evals/T3-tls-edge-cutover-lab-domain.md:30` still instructs that the
   claim "names resolve on the LAN only" is "already TRUE and must not be
   'corrected'". N2 removed the local resolver and published the A records, so
   that sentence is now false on both counts, and this diff rewrote it correctly
   at `docs/tls-certificates.md:65-72`. A scorer following row 10 literally would
   mark the correct doc as wrong. Row 9 and the Definition of Done likewise still
   credit T2 with network-wide resolution. The docs are right; the acceptance
   artifact lags them.
4. **Pre-existing, unowned.** `docs/nats-postgres-cdc-bridge.md:236` uses
   `registry.localstack:5000` as an image reference. That name never routed
   through HAProxy (there is no registry ACL before or after this change), so
   T3 neither broke nor should fix it, but with the resolver gone nothing
   resolves it either. It belongs with the other NATS-doc corrections
   `docs/dns.md:120-121` already assigns elsewhere.

## Verdict

pass. Every documented surface this change touches was updated in step, the
wildcard passage that blocked cycle 2 is now correct under direct verification,
the 30-day margin agrees across code, docs, plan and eval, and no doc in the
tree describes the pre-cutover edge. Commit it.
