eval: N1-netsec-restrict-prometheus-loki-to-cluster

**Definition of Done:** Prometheus (`192.168.2.47:9090`) and Loki
(`192.168.2.47:3100`) accept connections only from cluster nodes and the
HAProxy edge. A non-cluster LAN device cannot reach either. Grafana is
unchanged and still reachable, log shipping still works from every node, and
the superseded broad ufw rules are actually gone rather than merely
superseded in Terraform.

**The two ways this ticket fails while looking done:** the old `ufw allow`
lines survive on the host, because the provisioner only ever adds (rows 1 and
6); or a node is missing from Loki's allow-list and its promtail stops
shipping silently, with no error anywhere (row 4).

| Behavior | Input | Expected | Scorer | Threshold |
| --- | --- | --- | --- | --- |
| **Guardrail: a LAN device that is not a cluster node cannot query Prometheus** | From the dev container, which is on the LAN and is NOT a cluster node: `curl -sS --max-time 5 'http://192.168.2.47:9090/api/v1/query?query=up'` | Connection refused or timed out. Before this ticket the same command returns `{"status":"success",...}` with real metric data, so the contrast is the proof. A 200 here means the change did not take effect | deterministic check (curl from a non-cluster LAN host fails to connect) | 100% |
| **Guardrail: the same device cannot query Loki** | From the dev container: `curl -sS --max-time 5 http://192.168.2.47:3100/loki/api/v1/labels` | Connection refused or timed out. Returns 200 today | deterministic check (curl from a non-cluster LAN host fails to connect) | 100% |
| **Guardrail: the superseded broad rules are gone from the host, not just from Terraform** | On `192.168.2.47`: `sudo ufw status numbered` | No rule allowing `192.168.0.0/16` to 9090 or 3100, and no `100.64.0.0/10` rule for 9090. `null_resource.firewall` runs `ufw allow` and has NO destroy provisioner, so narrowing the Terraform list leaves the old permissive rule in place and the change is cosmetic. Rows 1 and 2 cannot pass while a broad rule survives, so this row explains a failure rather than adding coverage | deterministic check (`ufw status` shows no broad rule for either port) | 100% |
| **Grafana's dashboards still render, so the datasource path survived** | Open a dashboard that queries both Prometheus and Loki, or from `192.168.2.47`: `curl -s 'http://192.168.2.47:9090/api/v1/query?query=up'` and the Loki labels endpoint | Both return data. Grafana's datasources dial the node address rather than loopback, so omitting `192.168.2.47` from its own allow-list breaks every dashboard | deterministic check (both datasource endpoints answer from the Grafana node) | 100% |
| **Guardrail: log shipping still works from EVERY node, checked per node** | promtail is a `system` job, so it runs on all five. For each of firebat, orangepi4a, jetson-orin-nano, ubuntu, radxa-dragon-q6a, query Loki for a recent entry from that host | Every one of the five is still shipping. **Check per node, never in aggregate**: a missing node produces no error, no failed allocation, and no alert — logs from that host simply stop arriving and the cluster looks quiet. This is the most likely silent failure in the ticket | deterministic check (recent log lines present for all 5 node labels) | 100% |
| **Browser access through the edge is unaffected** | Through HAProxy rather than directly: request the Prometheus and Loki hostnames at the edge | Both answer. Narrowing is meant to remove the direct path, not the proxied one, and HAProxy on `192.168.2.30` stays on the allow-list. If this breaks, the edge address was omitted | deterministic check (both hostnames answer through the edge) | 100% |
| **Guardrail: Grafana's own reachability is untouched** | `curl -s -o /dev/null -w '%{http_code}' http://192.168.2.47:3000` from the dev container, and confirm its `firewall_rules` entry is unchanged in the diff | Still answers (302 to login) from a non-cluster LAN host, and `git diff` shows no change to the `grafana` entry. Operator decision: Grafana keeps its current reach because it has its own authentication | deterministic check (Grafana still answers AND its rule is unchanged in the diff) | 100% |
| **Nothing outside the two firewall entries changed** | `git diff` for the ticket across both Terraform roots | Only the `prometheus` entry in the infrastructure root and the `loki` entry in the applications root, plus any doc correction. No jobspec, no scrape config, no promtail change, no Consul rule | deterministic check (`git diff` confined to the two `firewall_rules` entries and docs) | 100% |
