# Why monitoring is not behind the edge

Prometheus, Loki and Tempo serve their query APIs with no authentication, and
none of them is routed through the edge proxy. Who may reach each one is in
the [monitoring stack reference](../reference/monitoring.md).

Narrowing the firewall alone would not have made these services private.
HAProxy has to be on the allow-list for any hostname it proxies, so a routed
`prometheus.lab.orangecluster.nl` would have fetched metrics for anyone who
asked it, over a publicly-trusted certificate, with no password. The
`prometheus` and `loki` backends carried no `http-request auth` line. The one
backend that did carry one was `phoenix`, and it went with the phoenix job.

The ACLs and backends were removed rather than given a password. Nothing
needed them: Grafana's datasources dial the node directly and Alloy pushes
directly, so the only consumer of those routes was a human typing the URL.
Adding authentication would have protected a door with nothing behind it.

The cost is Prometheus's own web UI. Reach it with an SSH tunnel when you
need it, as
[How to reach Prometheus or Loki directly](../how-to/reach-prometheus-or-loki-directly.md)
shows.
