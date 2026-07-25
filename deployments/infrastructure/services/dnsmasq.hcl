job "dnsmasq" {
  datacenters = ["localstack"]
  type        = "service"
  namespace   = "default"

  group "dnsmasq" {
    constraint {
      attribute = "$${attr.unique.hostname}"
      value     = "firebat"
    }

    network {
      port "dns" {
        static = 53
      }
    }

    task "dnsmasq" {
      driver = "podman"

      config {
        ### The tag reads 2.90-r3 but the binary is 2.91. The version floor is
        ### 2.86: below it, a query inside an `address=` domain that does not
        ### match the record type returns NODATA instead of being forwarded
        ### upstream, which would break the ACME client's zone lookup and
        ### silently stop certificate renewal.
        image        = "docker.io/4km3/dnsmasq:2.90-r3@sha256:52e25fb2601156ab66f6a0872c180b285df7cafaa41267d8d65689f066490641"
        network_mode = "host"
        cap_add      = ["NET_BIND_SERVICE"]
        args         = ["--conf-file=/local/dnsmasq.conf"]
      }

      template {
        data        = <<-EOH
# Answer the lab zone locally. One line covers the domain and every name
# under it, including names that do not exist yet, so adding a service needs
# no DNS change. Nothing here is published: there is no public A record for
# this zone, only a CAA record and the ACME client's transient TXT records.
address=/${lab_domain}/${edge_ip}

# Bind ONLY the LAN address. The host runs systemd-resolved, which already
# holds 127.0.0.53:53 and 127.0.0.54:53; binding the wildcard would collide
# with it and dnsmasq would exit at startup. Restricting to the LAN address
# leaves the host's own resolution untouched.
listen-address=${edge_ip}
bind-interfaces

# Ignore the container's /etc/resolv.conf and use these upstreams for
# everything not matched above. This includes ${public_domain} itself, whose
# apex and mail records must keep resolving from public DNS.
no-resolv
server=1.1.1.1
server=1.0.0.1

# No `.consul` forward here, deliberately. Consul hands out the container
# bridge address for bridge-networked services (nats resolves to 10.88.0.83,
# minio to 10.88.0.4), which is unroutable from the LAN. Forwarding .consul
# would replace an honest NXDOMAIN with an answer that fails slowly at
# connect instead of fast at resolution.
#
# Do not add `local=` for the lab zone. It restores pre-2.86 behavior, in
# which a non-matching name inside the zone returns NODATA rather than being
# forwarded, and certificate renewal depends on that forwarding.
        EOH
        destination = "local/dnsmasq.conf"
        change_mode = "restart"
      }

      service {
        name = "dnsmasq"
        port = "dns"
        tags = ["dns"]

        check {
          name     = "dnsmasq health"
          type     = "tcp"
          interval = "10s"
          timeout  = "2s"
        }
      }

      resources {
        cpu    = 100
        memory = 64
      }
    }
  }
}
