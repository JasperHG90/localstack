eval: F3-foundation-haproxy-tls-vault-pki

**Definition of Done:** TLS terminates at the HAProxy edge on `:443` with a
Vault-PKI-issued leaf that chains to the Vault PKI CA and covers every
`*.localstack` host, plain HTTP `:80` 301-redirects to HTTPS, cert renewal
reloads HAProxy, and every existing static backend still routes unchanged over
the new HTTPS frontend.

| Behavior | Input | Expected | Scorer | Threshold |
| --- | --- | --- | --- | --- |
| A PKI role scoped to the lab domain exists and issues leaves for `*.localstack` | `vault read pki/roles/<role>` | Role returns; `allowed_domains` contains `localstack` and `allow_subdomains` is `true` | deterministic check (`vault read pki/roles/<role>`) | 100% |
| The HAProxy edge job is running and healthy after the rewrite (no stuck alloc from a missing PKI grant) | `nomad job status haproxy` | `Status = running`, latest deployment `successful`, alloc `healthy` (not `pending`/`failed`) | deterministic check (`nomad job status haproxy`) | 100% |
| HTTPS is served at the edge and the routed backend answers over TLS | `curl -kv --resolve grafana.localstack:443:<edge-host> https://grafana.localstack/` | TLS handshake succeeds and Grafana answers (HTTP 200/302), proving `:443 ssl` is live | deterministic check (`curl -kv https://<edge>:443`) | 100% |
| The served leaf chains to the Vault PKI CA and its SAN covers the routed hosts | `openssl s_client -connect <edge-host>:443 -servername grafana.localstack </dev/null 2>/dev/null \| openssl x509 -noout -issuer -subject -ext subjectAltName` | `issuer=` equals the CA issuer CN from `vault read pki/cert/ca`; SAN covers `*.localstack`/`grafana.localstack` | deterministic check (`openssl s_client \| openssl x509 -issuer`) | 100% |
| Plain HTTP at the edge redirects to HTTPS with no cleartext service response | `curl -sI --resolve grafana.localstack:80:<edge-host> http://grafana.localstack/` | `HTTP/1.1 301` with `Location: https://grafana.localstack/`; no routed service answers 200 over cleartext | deterministic check (`curl -sI http://<edge>:80` returns 301) | 100% |
| On cert renewal the template re-renders and HAProxy reloads to serve the fresh leaf, not a stale one | Trigger/observe a leaf renewal at ~2/3 of the role TTL; inspect the Nomad `template` `change_mode` behavior and the served cert before and after reload | Renewal fires the configured reload (`change_mode`), the alloc stays healthy, and the edge serves the new leaf with no stale-cert window | model + rubric (adversarial review agent) | 4/5 |
| Existing routed services still answer through HTTPS with no regression — static backends verbatim, basic-auth intact, no consul-template introduced | `curl -sk -o /dev/null -w '%{http_code}\n' --resolve mlflow.localstack:443:<edge-host> https://mlflow.localstack/`; confirm backends (`haproxy.hcl:84-121`) unchanged and no consul-template added | `401` from the `openfang_users` basic-auth backend over HTTPS (routing + auth preserved); static `server <ip>:<port>` backends unchanged; no consul-template dependency introduced | deterministic check (`curl -sk https://mlflow.localstack/` returns 401) | 100% |
