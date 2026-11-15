job "seaweedfs" {
  datacenters = ["localstack"]
  type        = "service"

  group "seaweedfs" {
    constraint {
      attribute = "$${attr.unique.hostname}"
      value     = "orangepi4a"
    }

    volume "seaweedfs_data" {
      type            = "host"
      source          = "seaweedfs_data"
      access_mode     = "single-node-writer"
      attachment_mode = "file-system"
    }

    ### Only S3 and metrics leave the host. Master, volume and filer bind to
    ### loopback inside the container (`-ip.bind`), and the filer's IAM gRPC
    ### has no auth, so mapping any of their ports would expose it: the
    ### worker base rule already opens 20000:32000 to the LAN. The S3 gRPC
    ### port (8333 + 10000) follows `-s3.ip.bind` and cannot be turned off,
    ### so it is never mapped here.
    network {
      port "s3" {
        static = 8333
      }
      port "metrics" {
        static = 9327
      }
    }

    ### An in-place SeaweedFS restart costs one failed start before it comes
    ### back, because the podman driver cannot remove the old container at
    ### once (spike:ov-sync-consumer/11). The service default of two attempts
    ### would leave one for the real fault.
    restart {
      attempts = 3
      interval = "30m"
      delay    = "15s"
      mode     = "fail"
    }

    ### The ov-sync receiver. The filer webhook can only reach a loopback
    ### listener in SeaweedFS's own network namespace, because `-ip=127.0.0.1`
    ### pins its source address (spike:ov-sync-consumer/4 and /5).
    ###
    ### The receiver OWNS the namespace and SeaweedFS joins it, not the
    ### reverse. Then SeaweedFS restarts alone and the alloc keeps running
    ### (spike:ov-sync-consumer/11). With the receiver joining SeaweedFS,
    ### every SeaweedFS restart failed the alloc (spike:ov-sync-consumer/9).
    ### A receiver restart still fails the alloc and Nomad reschedules both,
    ### so the receiver never exits on a fault outside it and stays small.
    ###
    ### It holds the ports and the service: a task that joins another's
    ### namespace reports no address to Nomad. The check still reaches
    ### SeaweedFS through the shared namespace.
    task "receiver" {
      driver = "podman"

      lifecycle {
        hook    = "prestart"
        sidecar = true
      }

      vault {}

      ### noop: a restart of this task fails the whole alloc. The receiver
      ### reads the file on every request, so a rotated token still takes
      ### effect when this re-renders.
      template {
        data        = <<-EOH
        {{ with secret "${webhook_secret}" }}{{ .Data.data.token }}{{ end }}
        EOH
        destination = "secrets/webhook_token"
        change_mode = "noop"
      }

      env {
        NATS_URL            = "${nats_url}"
        RECEIVER_ADDR       = "127.0.0.1:20500"
        RECEIVER_TOKEN_FILE = "/secrets/webhook_token"
        GOMEMLIMIT          = "40MiB"
      }

      service {
        name = "seaweedfs"
        port = "s3"
        tags = ["http", "s3"]

        check {
          name     = "seaweedfs health check"
          type     = "http"
          port     = "s3"
          path     = "/healthz"
          method   = "GET"
          interval = "10s"
          timeout  = "5s"
        }
      }

      config {
        image = "${ov_sync_consumer_image}"
        args  = ["receiver"]
        ports = ["s3", "metrics"]
      }

      ### GOMEMLIMIT holds the Go heap well under this limit. The rest is
      ### headroom, because an OOM kill here takes S3 down with it.
      resources {
        cpu    = 100
        memory = 96
      }
    }

    task "seaweedfs" {
      driver = "podman"

      vault {}

      template {
        data        = <<-EOH
        {"identities":[{"name":"admin","credentials":[{"accessKey":"{{ with secret "${seaweedfs_secret}" }}{{ .Data.data.access_key }}{{ end }}","secretKey":"{{ with secret "${seaweedfs_secret}" }}{{ .Data.data.secret_key }}{{ end }}"}],"actions":["Admin","Read","Write","List","Tagging"]}]}
        EOH
        destination = "secrets/s3.json"
      }

      ### The default growth of 7 volumes per collection filled every slot
      ### after four buckets (spike:seaweedfs-service/3). S3 makes each
      ### bucket its own collection.
      template {
        data        = <<-EOH
        [master.volume_growth]
        copy_1 = 2
        EOH
        destination = "local/master.toml"
      }

      ### Workload identity: the OIDC provider, one role and policy per keyless
      ### job, and `defaultEffect: Deny`, from `local.seaweedfs_iam` in
      ### services.tf. Only the STS signing key comes from Vault.
      template {
        data        = <<-EOH
        {{ with secret "${sts_secret}" }}{"sts":{"tokenDuration":"1h","maxSessionLength":"12h","issuer":"seaweedfs-sts","signingKey":"{{ .Data.data.signing_key }}"},${iam_members}}{{ end }}
        EOH
        destination = "secrets/iam.json"
      }

      ### Filer events under the ov-sync bucket go to the receiver on
      ### loopback. Nothing else is sent.
      template {
        data        = <<-EOH
        [notification.webhook]
        enabled = true
        endpoint = "http://127.0.0.1:20500/events"
        bearer_token = "{{ with secret "${webhook_secret}" }}{{ .Data.data.token }}{{ end }}"
        path_prefixes = ["/buckets/ov-sync/"]
        EOH
        destination = "secrets/notification.toml"
      }

      config {
        image        = "docker.io/chrislusf/seaweedfs:4.48"
        network_mode = "task:receiver"
        args = [
          "server",
          "-dir=/data",
          "-s3",
          "-s3.port=8333",
          "-s3.config=/secrets/s3.json",
          "-s3.iam.config=/secrets/iam.json",
          ### Terraform manages users through the embedded IAM API, which
          ### refuses every write while this is true (the default).
          "-s3.iam.readOnly=false",
          "-s3.port.iceberg=0",
          "-s3.port.lance=0",
          "-ip=127.0.0.1",
          "-ip.bind=127.0.0.1",
          "-s3.ip.bind=0.0.0.0",
          "-metricsIp=0.0.0.0",
          "-metricsPort=9327",
          "-volume.max=0",
          "-master.volumeSizeLimitMB=1024",
          "-master.volumePreallocate=false",
        ]
        volumes = [
          "local/master.toml:/etc/seaweedfs/master.toml",
          "secrets/notification.toml:/etc/seaweedfs/notification.toml",
        ]
      }

      volume_mount {
        volume      = "seaweedfs_data"
        destination = "/data"
      }

      resources {
        cpu    = 1000
        memory = 512
      }
    }
  }
}
