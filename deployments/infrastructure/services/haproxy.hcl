job "haproxy" {
  datacenters = ["localstack"]
  type        = "service"

  group "haproxy" {
    constraint {
      attribute = "$${attr.unique.hostname}"
      value     = "firebat"
    }

    network {
      port "http" {
        static = 80
        to     = 8080
      }
      port "https" {
        static = 443
      }
      port "stats" {
        static = 8404
      }
    }

    task "haproxy" {
      driver = "podman"

      config {
        image        = "docker.io/library/haproxy:3.1-alpine"
        args         = ["-f", "/local/haproxy.cfg"]
        network_mode = "host"
        cap_add      = ["NET_BIND_SERVICE"]
      }

      ### Bare `vault {}`: the job lands on the default `nomad-workloads` role,
      ### whose policy already grants a read on this job's own KV prefix, which
      ### is exactly where the certificate is stored. No dedicated role or
      ### policy is needed, and adding one back would widen the grant for no
      ### gain.
      vault {}

      ### Leaf + issuing chain + key concatenated into the single PEM HAProxy's
      ### `crt` argument expects. `certificate` already carries the leaf AND
      ### its chain, so `issuer_chain` is deliberately not appended: it repeats
      ### the intermediate, which is harmless but pointless.
      ###
      ### KV2 nests the payload one level deeper than a PKI issue response did,
      ### hence `.Data.data.x` rather than `.Data.x`. Getting that wrong renders
      ### blank lines, HAProxy cannot parse `crt`, and every routed service goes
      ### down at once.
      ###
      ### The certificate is renewed by the acme job rather than issued here, so
      ### this template re-renders when the stored secret changes.
      ### `change_mode = "restart"` reloads HAProxy with it, because
      ### haproxy:3.1-alpine has no confirmed hitless reload under podman and a
      ### brief restart on a ~60-day renewal cycle is acceptable here.
      ###
      ### perms 0644, not 0600: this image runs as USER haproxy (uid 99), while
      ### Nomad renders template files as the agent user. A 0600 file would be
      ### unreadable to the process that must load it and the alloc would fail
      ### to start. The key's protection is the per-alloc secrets/ tmpfs, which
      ### is private to this task and torn down with the alloc — not the mode.
      template {
        data        = <<-EOH
{{ with secret "${tls_secret}" }}
{{ .Data.data.certificate }}
{{ .Data.data.private_key }}
{{ end }}
        EOH
        destination = "secrets/haproxy.pem"
        perms       = "0644"
        change_mode = "restart"
      }

      template {
        data        = <<-EOH
global
    log stdout format raw local0

defaults
    log     global
    mode    http
    option  httplog
    timeout connect 5s
    timeout client  300s
    timeout server  300s
    timeout tunnel  3600s

userlist openfang_users
    user admin insecure-password ${openfang_password}

frontend http_in
    bind *:80
    http-request redirect scheme https code 301 unless { ssl_fc }

frontend https_in
    bind *:443 ssl crt /secrets/haproxy.pem

    acl is_minio      hdr(host) -i minio.lab.orangecluster.nl
    acl is_s3         hdr(host) -i s3.lab.orangecluster.nl
    acl is_vault      hdr(host) -i vault.lab.orangecluster.nl
    acl is_nomad      hdr(host) -i nomad.lab.orangecluster.nl
    acl is_consul     hdr(host) -i consul.lab.orangecluster.nl
    acl is_phoenix    hdr(host) -i phoenix.lab.orangecluster.nl
    acl is_memex      hdr(host) -i memex.lab.orangecluster.nl
    acl is_prometheus hdr(host) -i prometheus.lab.orangecluster.nl
    acl is_grafana    hdr(host) -i grafana.lab.orangecluster.nl
    acl is_loki       hdr(host) -i loki.lab.orangecluster.nl
    acl is_mlflow     hdr(host) -i mlflow.lab.orangecluster.nl
    acl is_bifrost    hdr(host) -i bifrost.lab.orangecluster.nl

    use_backend minio      if is_minio
    use_backend s3         if is_s3
    use_backend vault      if is_vault
    use_backend nomad      if is_nomad
    use_backend consul     if is_consul
    use_backend phoenix    if is_phoenix
    use_backend memex      if is_memex
    use_backend prometheus if is_prometheus
    use_backend grafana    if is_grafana
    use_backend loki       if is_loki
    use_backend mlflow     if is_mlflow
    use_backend bifrost    if is_bifrost

frontend stats
    bind *:8404
    http-request use-service prometheus-exporter if { path /metrics }
    stats enable
    stats uri /
    stats refresh 10s

backend minio
    server minio1 192.168.2.29:9001 check

backend s3
    server s3_1 192.168.2.29:9000 check

backend vault
    server vault1 192.168.2.30:8200 check

backend nomad
    server nomad1 192.168.2.30:4646 check

backend consul
    server consul1 192.168.2.30:8500 check

backend phoenix
    http-request auth unless { http_auth(openfang_users) }
    server phoenix1 192.168.2.29:6006 check

backend memex
    server memex1 192.168.2.46:8000 check

backend prometheus
    server prometheus1 192.168.2.47:9090 check

backend grafana
    server grafana1 192.168.2.47:3000 check

backend loki
    server loki1 192.168.2.47:3100 check

backend mlflow
    http-request auth unless { http_auth(openfang_users) }
    server mlflow1 192.168.2.50:5050 check

backend bifrost
    http-request auth unless { http_auth(openfang_users) }
    server bifrost1 192.168.2.50:8080 check
        EOH
        destination = "local/haproxy.cfg"
      }

      service {
        name = "haproxy"
        port = "http"
        tags = ["http", "proxy"]

        check {
          name     = "haproxy health"
          type     = "tcp"
          interval = "10s"
          timeout  = "2s"
        }
      }

      service {
        name = "haproxy-stats"
        port = "stats"
        tags = ["http", "monitoring"]
      }

      resources {
        cpu    = 500
        memory = 128
      }
    }
  }
}
