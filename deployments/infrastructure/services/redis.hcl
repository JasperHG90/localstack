job "redis" {
  datacenters = ["localstack"]
  type        = "service"
  namespace   = "default"

  group "redis" {
    constraint {
      attribute = "$${attr.unique.hostname}"
      value     = "radxa-dragon-q6a"
    }

    network {
      port "cache" {
        static = 6379
        to     = 6379
      }
    }

    task "redis" {
      driver = "podman"

      service {
        name = "redis"
        port = "cache"
        tags = ["cache", "redis"]

        check {
          type     = "tcp"
          interval = "10s"
          timeout  = "2s"
        }
      }

      config {
        image = "docker.io/library/redis:7-alpine"
        args  = ["redis-server", "/secrets/redis.conf"]
        ports = ["cache"]
      }

      vault {}

      ### Only the `default` user's password is templated here: it is what
      ### Vault's redis-database-plugin authenticates with
      ### (redis_secrets_engine.tf) to mint and revoke the short-lived ACL
      ### users every caller actually uses. No caller is ever handed this
      ### password. Rendered to `secrets/`, not `local/`: every other
      ### credential-bearing template in this repo (haproxy.hcl's TLS key,
      ### postgres.hcl's admin password) uses the per-alloc tmpfs, which is
      ### private to this task and torn down with the alloc.
      ###
      ### `save ""` + `appendonly no`: this is a cache, not a store. A
      ### restart is a cold cache, not a data-loss incident, and skipping
      ### snapshotting avoids disk I/O this node doesn't need to pay for.
      ###
      ### `maxmemory` + `allkeys-lru`, capped below the task's memory limit:
      ### without it Redis grows unbounded and Nomad OOM-kills the task
      ### instead of evicting, which is a much worse failure mode for a
      ### cache than dropping its coldest keys.
      ###
      ### Every Vault-minted ACL user (redis_secrets_engine.tf) lives only
      ### in Redis's memory — there is no `aclfile` — so ANY restart of this
      ### task (OOM, reschedule, node reboot, `nomad job restart`, not just
      ### a config change) wipes every outstanding user while Vault still
      ### considers their leases valid. The dynamic role's default_ttl is
      ### kept short (15m, not the usual 1h) so a caller's own lease
      ### renewal — which re-authenticates and re-mints — recovers within
      ### minutes rather than up to an hour of silent auth failures.
      template {
        data        = <<EOH
requirepass {{ with secret "${redis_admin_secret}" }}{{ .Data.data.password }}{{ end }}
save ""
appendonly no
maxmemory 96mb
maxmemory-policy allkeys-lru
EOH
        destination = "secrets/redis.conf"
      }

      resources {
        cpu    = 200
        memory = 128
      }
    }
  }
}
