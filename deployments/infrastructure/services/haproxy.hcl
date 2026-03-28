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

    acl is_minio   hdr(host) -i minio.localstack
    acl is_s3      hdr(host) -i s3.localstack
    acl is_vault   hdr(host) -i vault.localstack
    acl is_nomad   hdr(host) -i nomad.localstack
    acl is_consul  hdr(host) -i consul.localstack
    acl is_phoenix hdr(host) -i phoenix.localstack
    acl is_memex    hdr(host) -i memex.localstack
    acl is_openfang hdr(host) -i openfang.localstack

    use_backend minio    if is_minio
    use_backend s3       if is_s3
    use_backend vault    if is_vault
    use_backend nomad    if is_nomad
    use_backend consul   if is_consul
    use_backend phoenix  if is_phoenix
    use_backend memex    if is_memex
    use_backend openfang if is_openfang

frontend stats
    bind *:8404
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

backend openfang
    http-request auth unless { http_auth(openfang_users) }
    option forwardfor
    timeout tunnel 3600s
    timeout server 3600s
    server openfang1 192.168.2.47:50051 check
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
