eval: F4-foundation-dnsmasq-localstack-dns

**Definition of Done:** A dnsmasq Nomad job on firebat answers the whole
`.localstack` TLD with `192.168.2.30` (one wildcard record), forwards every
other query to the Cloudflare upstream, and serves both UDP and TCP on
port 53 (bound via host networking + `NET_BIND_SERVICE`, the HAProxy
precedent). Port 53 is opened on firebat to the LAN and Tailscale ranges, so
any device pointed at firebat as its resolver gets network-wide `*.localstack`
resolution while keeping working public DNS. Router-DHCP hand-off and TLS
trust are out of scope.

| Behavior | Input | Expected | Scorer | Threshold |
| --- | --- | --- | --- | --- |
| The dnsmasq alloc is running and healthy (no stuck alloc from port 53 already bound on firebat — Q2) | `nomad job status dnsmasq` | `Status = running`, latest deployment `successful`, alloc `healthy` (not `pending`/`failed`) | deterministic check (`nomad job status dnsmasq`) | 100% |
| A known `.localstack` name resolves to firebat, queried from a LAN host other than firebat (proves resolution AND that the firewall opened 53) | `dig @192.168.2.30 minio.localstack +short` (run from a LAN client, not on-box) | `192.168.2.30` | deterministic check (`dig @192.168.2.30 minio.localstack +short`) | 100% |
| An arbitrary, never-configured `.localstack` name also resolves, proving a wildcard record and not a per-name list | `dig @192.168.2.30 anyrandom.localstack +short` | `192.168.2.30` | deterministic check (`dig @192.168.2.30 anyrandom.localstack +short`) | 100% |
| A public name still resolves, proving `no-resolv` + Cloudflare upstream forwarding so clients keep internet DNS | `dig @192.168.2.30 example.com +short` | a real public A record: non-empty and NOT `192.168.2.30` | deterministic check (`dig @192.168.2.30 example.com +short`) | 100% |
| TCP transport answers on port 53, not only UDP (large responses / TCP-only clients) | `dig +tcp @192.168.2.30 minio.localstack +short` | `192.168.2.30` | deterministic check (`dig +tcp @192.168.2.30 minio.localstack +short`) | 100% |
| End-to-end: the resolved name reaches the real service through HAProxy | `curl -s -o /dev/null -w '%{http_code}\n' --resolve grafana.localstack:80:192.168.2.30 http://grafana.localstack/` | `200` or `302` — the name maps to firebat and HAProxy routes to Grafana | deterministic check (`curl -sI` via `--resolve` to firebat) | 100% |
| No regression to existing edge routing — the dnsmasq job adds only a :53 listener and does not touch HAProxy routing, backends, or any other job | `nomad job status haproxy`; `curl -sI --resolve grafana.localstack:80:192.168.2.30 http://grafana.localstack/` compared to the pre-apply baseline | HAProxy stays `running`/`healthy` and Grafana returns the same status line as before the F4 apply; `services.tf` diff adds only the `dnsmasq` job + firewall entry | deterministic check (`nomad job status haproxy` + baseline `curl` match) | 100% |
