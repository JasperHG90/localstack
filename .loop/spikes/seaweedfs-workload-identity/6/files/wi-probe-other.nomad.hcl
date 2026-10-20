# Throwaway probe for seaweedfs-workload-identity. Exchanges this job's
# workload identity for the wi-probe role. Exit 0 means the expected outcome
# (deny); the alloc's exit code is the result, since logs are not readable.
job "wi-probe-other" {
  datacenters = ["localstack"]
  type        = "batch"

  group "probe" {
    reschedule {
      attempts  = 0
      unlimited = false
    }
    restart {
      attempts = 0
      mode     = "fail"
    }

    task "probe" {
      driver = "podman"

      identity {
        name     = "seaweedfs"
        aud      = ["seaweedfs"]
        file     = true
        filepath = "secrets/nomad_seaweedfs.jwt"
        ttl      = "1h"
      }

      config {
        image      = "docker.io/curlimages/curl:8.11.1"
        entrypoint = ["/bin/sh", "-c"]
        args = [<<-EOT
          set -u
          ep=http://192.168.2.29:8333
          tok=$(cat /secrets/nomad_seaweedfs.jwt)
          resp=$(curl -s -o /tmp/sts.xml -D - -X POST "$ep/?Action=AssumeRoleWithWebIdentity&Version=2011-06-15&RoleArn=arn:aws:iam::role/wi-probe&RoleSessionName=wi-probe-other&WebIdentityToken=$tok" | head -1 | cut -d' ' -f2)
          echo "sts http $resp"
          if [ "deny" = deny ]; then
            [ "$resp" = 403 ] && exit 0 || exit 1
          fi
          [ "$resp" = 200 ] || exit 2
          ak=$(sed -n 's:.*<AccessKeyId>\(.*\)</AccessKeyId>.*:\1:p' /tmp/sts.xml)
          sk=$(sed -n 's:.*<SecretAccessKey>\(.*\)</SecretAccessKey>.*:\1:p' /tmp/sts.xml)
          st=$(sed -n 's:.*<SessionToken>\(.*\)</SessionToken>.*:\1:p' /tmp/sts.xml)
          put=$(curl -s -o /dev/null -D - --aws-sigv4 "aws:amz:us-east-1:s3" --user "$ak:$sk" -H "x-amz-security-token: $st" -X PUT --data-binary "written by wi-probe-other" "$ep/wi-probe/from-wi-probe-other" | head -1 | cut -d" " -f2)
          echo "put http $put"
          [ "$put" = 200 ] || exit 3
          EOT
        ]
      }

      resources {
        cpu    = 100
        memory = 64
      }
    }
  }
}
