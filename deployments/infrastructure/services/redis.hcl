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
      ### cache than dropping its coldest keys. The gap between the two
      ### absorbs Redis's own overhead and jemalloc fragmentation, which
      ### `used_memory` does not count and `maxmemory` therefore does not
      ### bound.
      ###
      ### Raised from 96mb/128 after OpenViking's reranker started serving.
      ### That path had sent embark zero requests since the service went up,
      ### so every rerank call is new `mget` traffic against this cache and
      ### the working set it was sized for no longer holds. Deleting
      ### oauth2-proxy-openviking freed 128 on this node, so the net
      ### reservation change here is +256, not +384.
      ###
      ### radxa-dragon-q6a's reservations now sum to ~6.7 GB steady state,
      ### plus ~1.3 GB transient while the 02:00 and 03:00 backups run. That
      ### sum is read off the jobspecs, NOT measured on the node: unlike
      ### embark.hcl's Jetson figures, nothing here has checked what the host
      ### actually has. Confirm with `free -m` before raising anything else.
      ###
      ### Every Vault-minted ACL user (redis_secrets_engine.tf) lives only
      ### in Redis's memory — there is no `aclfile` — so ANY restart of this
      ### task (OOM, reschedule, node reboot, `nomad job restart`, not just
      ### a config change) wipes every outstanding user while Vault still
      ### considers their leases valid. Nothing recovers that on its own: a
      ### lease RENEWAL does not re-run creation_statements (renew_statements
      ### is empty), so only a re-mint rebuilds the user, and the role's
      ### max_ttl is 720h. Restart the affected consumer by hand -- for
      ### embark, `nomad job restart embark` -- which re-reads the secret and
      ### mints a new user. Until then that consumer logs its own cache
      ### warning and serves uncached.
      template {
        data        = <<EOH
requirepass {{ with secret "${redis_admin_secret}" }}{{ .Data.data.password }}{{ end }}
save ""
appendonly no
maxmemory 384mb
maxmemory-policy allkeys-lru
EOH
        destination = "secrets/redis.conf"
      }

      ### cpu 500, raised from 200. Nothing sets `cpu_hard_limit`, here or in
      ### bootstrap/roles/nomad_client/templates/nomad.hcl.j2, so this is a
      ### SHARE and not a ceiling: it decides who waits when the node is busy,
      ### not how much Redis may use. radxa-dragon-q6a's shares sum to ~7350
      ### (hermes 2300, openviking 1000, prometheus 1000, bifrost 600, nats
      ### 550, the rest smaller), so 200 gave Redis under 3% of the node when
      ### it is contended.
      ###
      ### That is a plausible read of `Timeout reading from 192.168.2.50:6379`
      ### in embark's log: Redis has not restarted since 21 Aug, so it was not
      ### OOM-killed, and an eviction is a miss rather than a timeout. A
      ### healthy server that is simply not scheduled in time looks exactly
      ### like this from the client.
      ###
      ### Redis executes commands on one thread, so a bigger share cannot cost
      ### more than one core no matter what else is idle. UNVERIFIED against
      ### the node: whether radxa is actually contended is what would confirm
      ### this, and node-exporter already carries the answer.
      resources {
        cpu    = 500
        memory = 512
      }
    }
  }
}
