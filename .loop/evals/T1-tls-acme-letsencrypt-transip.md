eval: T1-tls-acme-letsencrypt-transip

**Definition of Done:** A periodic Nomad job obtains a publicly-trusted Let's
Encrypt wildcard for `*.lab.orangecluster.nl` via DNS-01 against TransIP,
persists its ACME account and certificate state across runs, and writes the
cert, key and chain to Vault KV2 at `secret/data/default/haproxy/tls`. Nothing
consumes it yet and HAProxy is untouched. Idempotency is proven on the
STAGING endpoint before any production issuance.

**Rate-limit guard (operator decision, 2026-07-25):** production issuance is
BLOCKED until row 4 passes against
`https://acme-staging-v02.api.letsencrypt.org/directory`. Let's Encrypt allows
5 certificates per exact identifier set per 7 days, so a job that re-issues
every run exhausts the budget in under a week and locks out T3.

| Behavior | Input | Expected | Scorer | Threshold |
| --- | --- | --- | --- | --- |
| The renewal job runs to completion on its own, without an operator | `nomad job status acme`, then inspect the latest periodic child's allocation | The latest batch alloc is `complete` with exit 0. An alloc stuck `pending` means the Vault template is blocked, which is the signature of a missing or mis-scoped policy | deterministic check (`nomad job status acme` shows a complete alloc, exit 0) | 100% |
| **Guardrail: the job keeps its ACME state between runs, so `lego renew` does not hard-fail** | After two scheduled runs, inspect the mounted host volume | `.lego/accounts/` and `.lego/certificates/` both exist and are non-empty. `lego renew` calls `log.Fatalf` when the account is unregistered or no certificate exists in `--path`, and a periodic child gets a fresh alloc dir, so without persistent state every run fails | deterministic check (both directories present on the host volume) | 100% |
| The issued certificate covers the whole lab zone and is publicly trusted | `vault kv get -field=certificate secret/default/haproxy/tls \| openssl x509 -noout -issuer -subject -ext subjectAltName -dates` | Issuer is a Let's Encrypt intermediate, SAN covers BOTH `*.lab.orangecluster.nl` and `lab.orangecluster.nl` (a wildcard does not match the bare name), validity is ~90 days | deterministic check (`openssl x509` output matches) | 100% |
| **Guardrail: re-running the job does not burn Let's Encrypt rate-limit budget** | Against `acme-staging-v02.api.letsencrypt.org`: run the job, record the cert serial, run it again, record again | The serial is UNCHANGED on the second run — `lego renew --days 30` no-ops outside the renewal window. **This must pass on staging before the production endpoint is configured at all** | deterministic check (cert serial identical across two consecutive runs) | 100% |
| The chain validates against the system trust store, with no private CA involved | `openssl verify -untrusted <chain-from-KV> <leaf-from-KV>` with NO `-CAfile` argument | `OK`. This is the entire point of leaving the Vault PKI approach: any need for `-CAfile` or `-k` means the cert is not publicly trusted and T3 must not proceed | deterministic check (`openssl verify` returns OK without `-CAfile`) | 100% |
| The KV2 payload has the field shape T3 will template against | `vault kv get -format=json secret/default/haproxy/tls \| jq '.data.data \| keys'` | Exactly the agreed fields (`certificate`, `private_key`, `issuer_chain` per plan Q3), each non-empty and PEM-formatted. T3's HAProxy template is written against these names, so a mismatch breaks the cutover | deterministic check (`jq` key list matches the agreed contract) | 100% |
| **Guardrail: no private key reaches the logs, which ship to Loki** | `nomad alloc logs <alloc-id>` and `nomad alloc logs -stderr <alloc-id>` for a completed run | No `BEGIN ... PRIVATE KEY` and no TransIP key material anywhere in stdout or stderr. Promtail ships these logs to Loki, so a leak here is durable | deterministic check (`grep -c 'BEGIN.*PRIVATE KEY'` returns 0) | 100% |
| **Guardrail: the ACME job cannot read or write outside what it needs** | With a token minted from the `acme` JWT role: attempt `vault kv get secret/default/grafana/admin`, then `vault kv put secret/data/default/haproxy/tls ...` | The grafana read is DENIED (403). The haproxy/tls write SUCCEEDS. The role must also retain `nomad-workloads` (or re-grant `secret/data/default/acme/*`) or the job cannot read its own TransIP credential — one task holds exactly one token | deterministic check (403 on the out-of-scope read, success on the in-scope write) | 100% |
| HAProxy is untouched — T1 changes nothing a user can see | `nomad job status haproxy` and `git diff` for the ticket | The haproxy job's `modify_index` is unchanged by this ticket, no file under `services/haproxy.hcl` is modified, and `pki.tf` still exists. The edge keeps serving its current cert until T3 | deterministic check (`git diff` touches no haproxy or pki file) | 100% |
