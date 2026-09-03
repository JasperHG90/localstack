job "registry" {
  datacenters = ["localstack"]
  type        = "service"
  namespace   = "default"

  group "registry" {
    # The registry holds no local state -- every blob lives in the `registry`
    # MinIO bucket and there is no host volume -- so placement is purely a
    # capacity question. firebat, the obvious choice for being HAProxy's own
    # node, is committed to ~3100 MHz by Postgres and HAProxy and the
    # scheduler refused to place there. Colocating with MinIO buys nothing
    # either: every blob byte crosses the wire once regardless of which of
    # the two ends the registry sits on.
    constraint {
      attribute = "$${attr.unique.hostname}"
      value     = "ubuntu"
    }

    network {
      port "http" {
        static = 5000
      }
      # The debug listener serves /debug/health unauthenticated. The main
      # port cannot be health-checked: with htpasswd on, /v2/ answers 401
      # and Consul reads anything outside 2xx as critical.
      port "debug" {
        static = 5001
      }
    }

    task "registry" {
      driver = "podman"

      ### KEEPS `vault {}`, unlike loki: the htpasswd below is a second Vault
      ### use that outlives the MinIO key.
      vault {}

      ### Keyless MinIO access. Field-by-field rationale is in
      ### docs/workload-identity.md; only what is specific to registry is here.
      ### The task sets no `user`, so Nomad leaves the JWT readable.
      identity {
        name        = "minio"
        aud         = ["minio"]
        file        = true
        filepath    = "secrets/nomad_minio.jwt"
        ttl         = "1h"
        change_mode = "noop"
      }

      ### Same shape as loki: aws-sdk-go v1 cannot be pointed at a non-AWS
      ### STS, so the SDK runs local/minio-creds.sh and re-runs it on expiry.
      ###
      ### AWS_CONFIG_FILE is NOT optional. Without it the SDK reads
      ### $HOME/.aws/config, which does not exist here, and every request
      ### fails with NoCredentialProviders. AWS_WEB_IDENTITY_TOKEN_FILE must
      ### stay unset: it is checked before the shared config and would
      ### pre-empt the helper.
      env {
        AWS_SDK_LOAD_CONFIG = "1"
        AWS_CONFIG_FILE     = "/local/aws-config"
        AWS_REGION          = "us-east-1"
      }

      service {
        name = "registry"
        port = "http"
        tags = ["http", "registry"]

        check {
          name     = "registry health"
          type     = "http"
          port     = "debug"
          path     = "/debug/health"
          method   = "GET"
          interval = "15s"
          timeout  = "3s"
        }
      }

      config {
        image        = "docker.io/library/registry:3.1.1"
        args         = ["/secrets/config.yml"]
        ports        = ["http", "debug"]
        network_mode = "host"
      }

      ### The credential_process helper. Contract imposed by the SDK, not by
      ### us: "Version":1 is mandatory, stdout is capped at 8 KiB and the run
      ### at 60s, it is invoked through `sh -c`, and a non-zero exit surfaces
      ### as ProcessProviderExecutionError. So it prints the JSON and nothing
      ### else, and fails loudly rather than emitting a half-document.
      ###
      ### No RoleArn in the request: MinIO resolves the policy from the
      ### token's nomad_job_id claim, which is what makes the `registry` policy
      ### apply to registry alone.
      template {
        data        = <<-EOF
        #!/bin/sh
        set -eu
        jwt=$(cat /secrets/nomad_minio.jwt)
        body=$(wget -q -O - --post-data='' \
          "http://${minio_host}:9000/?Action=AssumeRoleWithWebIdentity&Version=2011-06-15&WebIdentityToken=$${jwt}")
        field() {
          printf '%s' "$${body}" | sed -n "s:.*<$1>\([^<]*\)</$1>.*:\1:p"
        }
        ak=$(field AccessKeyId)
        sk=$(field SecretAccessKey)
        st=$(field SessionToken)
        ex=$(field Expiration)
        if [ -z "$${ak}" ] || [ -z "$${sk}" ] || [ -z "$${st}" ] || [ -z "$${ex}" ]; then
          echo "minio-creds: STS response missing a credential field" >&2
          exit 1
        fi
        printf '{"Version":1,"AccessKeyId":"%s","SecretAccessKey":"%s","SessionToken":"%s","Expiration":"%s"}\n' \
          "$${ak}" "$${sk}" "$${st}" "$${ex}"
        EOF
        destination = "local/minio-creds.sh"
        perms       = "0755"
      }

      ### Points the SDK at the helper. The path here and AWS_CONFIG_FILE above
      ### must stay identical.
      template {
        data        = <<-EOF
        [default]
        credential_process = /local/minio-creds.sh
        EOF
        destination = "local/aws-config"
      }

      # This file no longer carries a secret. The MinIO keys are gone, because
      # omitting accesskey/secretkey is what sends the S3 driver down the AWS
      # credential chain to the helper above, and the htpasswd line below is a
      # literal path, not a rendered value: the Vault render is the separate
      # template further down. The destination stays secrets/ only because
      # moving it is not this ticket's business.
      template {
        data = <<-EOF
        version: 0.1
        log:
          level: info

        storage:
          s3:
            regionendpoint: http://192.168.2.29:9000
            # Required on v3 whenever regionendpoint is set.
            forcepathstyle: true
            # MinIO here is plain HTTP.
            secure: false
            # Required field; MinIO ignores the value.
            region: us-east-1
            bucket: registry
          # Needed for `registry garbage-collect` to reclaim MinIO space;
          # deleting a tag alone never frees blobs.
          delete:
            enabled: true

        http:
          addr: 0.0.0.0:5000
          # Emit relative Location headers on the chunked upload flow.
          # Without this the registry builds absolute URLs from the scheme it
          # sees, which is http behind HAProxy's TLS termination. The client
          # then follows a redirect back to https, and every correct HTTP
          # client DROPS Authorization on a scheme change because that is a
          # different origin -- so the retried PATCH arrives anonymous and
          # the push dies with "authentication required". Small blobs survive
          # (single monolithic POST, no Location followed); anything large
          # enough to chunk fails. A relative Location is resolved against
          # the origin the client is already on, so the scheme never changes.
          relativeurls: true
          debug:
            addr: 0.0.0.0:5001

        auth:
          htpasswd:
            realm: localstack
            path: /secrets/htpasswd
        EOF

        destination = "secrets/config.yml"
        change_mode = "restart"
      }

      template {
        data = <<-EOF
        {{- with secret "${registry_auth_secret}" }}
        {{ .Data.data.htpasswd }}
        {{- end }}
        EOF

        destination = "secrets/htpasswd"
        change_mode = "restart"
      }

      # Deliberately small. The registry is I/O-bound -- it streams blobs to
      # MinIO rather than computing -- and ubuntu already carries the whole
      # observability stack (~3050 MHz and ~2.7 GB committed). A CPU
      # reservation is a scheduling commitment and a relative cgroup weight,
      # not a ceiling, so a low number still lets it use idle cycles.
      resources {
        cpu        = 100
        memory     = 256
        memory_max = 512
      }
    }
  }
}
