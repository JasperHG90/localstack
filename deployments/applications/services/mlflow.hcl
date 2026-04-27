job "mlflow" {
  datacenters = ["localstack"]
  type        = "service"

  group "mlflow" {
    constraint {
      attribute = "$${attr.unique.hostname}"
      value     = "firebat"
    }

    network {
      port "http" {
        static = 5050
      }
    }

    task "mlflow" {
      driver = "podman"

      service {
        name    = "mlflow"
        port    = "http"
        address = "${mlflow_host}"

        tags = ["http", "ml", "tracking"]

        check {
          type     = "http"
          path     = "/health"
          interval = "30s"
          timeout  = "3s"
        }
      }

      config {
        image   = "ghcr.io/mlflow/mlflow:v${mlflow_version}"
        command = "/bin/sh"
        args = [
          "-c",
          "pip install --quiet --no-cache-dir psycopg2-binary boto3 && exec mlflow server --host 0.0.0.0 --port 5050 --backend-store-uri \"$BACKEND_URI\" --artifacts-destination s3://mlflow-artifacts/ --serve-artifacts",
        ]
        network_mode = "host"
      }

      vault {}

      template {
        data = <<EOF
BACKEND_URI=postgresql://{{ with secret "${mlflow_postgres_secret}" }}{{ .Data.data.username }}:{{ .Data.data.password }}{{ end }}@${postgres_host}:5432/mlflow
MLFLOW_S3_ENDPOINT_URL=http://${minio_host}:9000
{{ with secret "${mlflow_minio_secret}" }}
AWS_ACCESS_KEY_ID={{ .Data.data.access_key }}
AWS_SECRET_ACCESS_KEY={{ .Data.data.secret_key }}
{{ end }}
AWS_DEFAULT_REGION=us-east-1
EOF

        destination = "secrets/file.env"
        env         = true
      }

      resources {
        cpu    = 500
        memory = 768
      }
    }
  }
}
