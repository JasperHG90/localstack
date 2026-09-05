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
    acl is_grafana    hdr(host) -i grafana.lab.orangecluster.nl
    acl is_bifrost    hdr(host) -i bifrost.lab.orangecluster.nl
    acl is_dash       hdr(host) -i dash.lab.orangecluster.nl
    acl is_registry   hdr(host) -i registry.lab.orangecluster.nl
    acl is_registryui hdr(host) -i registry-ui.lab.orangecluster.nl
    acl is_openviking hdr(host) -i openviking.lab.orangecluster.nl

    use_backend minio      if is_minio
    use_backend s3         if is_s3
    use_backend vault      if is_vault
    use_backend nomad      if is_nomad
    use_backend consul     if is_consul
    use_backend phoenix    if is_phoenix
    use_backend memex      if is_memex
    use_backend grafana    if is_grafana
    use_backend bifrost    if is_bifrost
    use_backend dash       if is_dash
    use_backend registry   if is_registry
    use_backend registryui if is_registryui
    use_backend openviking if is_openviking

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

backend grafana
    server grafana1 192.168.2.47:3000 check

# The registry runs on ubuntu, not here: it is stateless (blobs live in
# MinIO) and firebat had no CPU headroom left. It carries its own auth
# (htpasswd), so no `http-request auth` here: podman and docker cannot
# answer HAProxy's challenge, and the registry's own 401 is what drives
# `docker login`.
#
# The default 300s `timeout server` is an INACTIVITY timer, so a streaming
# push resets it and is safe. What is not safe is the silence while the
# registry finalizes a multi-GB multipart upload into MinIO, which is one
# long server-side pause. 1800s covers a model-sized layer.
backend registry
    timeout server 1800s
    # Tell the registry it is fronted by TLS. It is otherwise blind to that
    # and builds absolute URLs with the scheme it sees on the wire (http),
    # which breaks chunked blob uploads. The registry also sets
    # `relativeurls: true`, which fixes this independently; both are here
    # because the header is correct for any proxied backend and the
    # relative-URL setting is what actually carries the guarantee.
    http-request set-header X-Forwarded-Proto https
    server registry1 192.168.2.47:5000 check

backend bifrost
    server bifrost1 192.168.2.50:8080 check

backend dash
    server dash1 192.168.2.50:4180 check

backend registryui
    server registryui1 192.168.2.50:4181 check

backend openviking
    server openviking1 192.168.2.50:4182 check
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
