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

      service {
        name = "seaweedfs"
        port = "s3"
        tags = ["http"]

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
        image = "docker.io/chrislusf/seaweedfs:4.48"
        args = [
          "server",
          "-dir=/data",
          "-s3",
          "-s3.port=8333",
          "-s3.config=/secrets/s3.json",
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
        ports   = ["s3", "metrics"]
        volumes = ["local/master.toml:/etc/seaweedfs/master.toml"]
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
