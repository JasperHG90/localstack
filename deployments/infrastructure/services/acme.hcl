job "acme" {
  datacenters = ["localstack"]
  type        = "batch"
  namespace   = "default"

  ### Daily, not every-60-days. `run --renew-days 30` no-ops until the leaf is
  ### inside its renewal window, so a failed day simply retries tomorrow and
  ### the full 30-day margin survives. A 60-day cron spends the whole margin on
  ### a single failure nobody sees.
  periodic {
    crons            = ["0 4 * * *"]
    time_zone        = "Europe/Amsterdam"
    prohibit_overlap = true
  }

  group "acme" {
    constraint {
      attribute = "$${attr.unique.hostname}"
      value     = "ubuntu"
    }

    ### Holds the ACME account key and the issued bundle between periodic
    ### children. Each child gets a fresh alloc dir, so without this lego has
    ### no account to renew against and re-registers and re-issues on every
    ### run, which exhausts the CA's per-identifier-set weekly limit in days.
    volume "acme_state_volume" {
      type            = "host"
      source          = "acme_state"
      access_mode     = "single-node-writer"
      attachment_mode = "file-system"
    }

    ### Two tasks because the lego image cannot write to Vault: it is a busybox
    ### userland with /lego and nothing else. The store task carries the vault
    ### CLI instead.
    task "issue" {
      driver = "podman"

      lifecycle {
        hook    = "prestart"
        sidecar = false
      }

      config {
        ### Pinned by digest ALONE (tag v5.3.1). A reference carrying both a
        ### tag and a digest is rejected by the podman driver at run time.
        image        = "docker.io/goacme/lego@sha256:f4fd80df0ef94d2f536cc2e7fb5bdbd090fb0aa81b3595226b9fe814bb9a2bfe"
        network_mode = "host"

        ### `run` is the only issuance command in lego v5 and handles both
        ### first issuance and renewal. With --renew-days it skips issuance
        ### when the leaf still has more than 30 days left, which is what makes
        ### a daily schedule safe; --renew-force exists precisely because
        ### not-due is otherwise a no-op.
        ###
        ### It does still contact the CA on a not-due night: the directory is
        ### fetched before the expiry check, so a night when DNS or the CA is
        ### unreachable fails this allocation even though nothing was due.
        ### That is noise, not risk (a directory fetch is not rate-limited
        ### issuance), but it means a red run does not imply a renewal problem.
        ###
        ### Everything else is passed as LEGO_* environment variables below, so
        ### no shell wrapper is needed and nothing here has to survive two
        ### layers of template escaping.
        args = ["run", "--renew-days", "30"]
      }

      volume_mount {
        volume      = "acme_state_volume"
        destination = "/acme-state"
      }

      vault {
        role = "${vault_role}"
      }

      ### lego reads the TransIP key from a FILE path, not a value, so it must
      ### be rendered to disk. The account name is the TransIP login username,
      ### not the email address on the account.
      template {
        data        = <<-EOH
{{ with secret "${transip_secret}" }}{{ .Data.data.private_key }}{{ end }}
        EOH
        destination = "secrets/transip.key"
      }

      ### LEGO_PATH is namespaced by ACME environment on purpose. lego
      ### namespaces accounts by server host but names certificate files after
      ### the domain alone, so a staging and a production bundle would collide.
      ### Sharing one directory means that after flipping to production the
      ### staging leaf is still ~90 days from expiry, so `run` finds it not due,
      ### skips issuance, and the store task cheerfully republishes an
      ### untrusted certificate.
      template {
        data        = <<-EOH
TRANSIP_ACCOUNT_NAME="{{ with secret "${transip_secret}" }}{{ .Data.data.account_name }}{{ end }}"
TRANSIP_PRIVATE_KEY_PATH="/secrets/transip.key"
LEGO_ACCEPT_TOS="true"
LEGO_EMAIL="${acme_email}"
LEGO_SERVER="${acme_server}"
LEGO_PATH="${acme_path}"
LEGO_DOMAINS="*.${acme_domain},${acme_domain}"
LEGO_DNS="transip"
LEGO_DNS_RESOLVERS="1.1.1.1:53"
        EOH
        destination = "secrets/lego.env"
        env         = true
      }

      resources {
        cpu    = 100
        memory = 128
      }
    }

    ### Reads what the issue task left on the shared volume and puts it in KV2
    ### for the edge proxy to template. Runs only if issue succeeded, since a
    ### failed prestart task fails the allocation.
    ###
    ### `key=@file` rather than assembling JSON: this image ships /bin/vault
    ### but no jq, and escaping multi-line PEMs into JSON by hand in `sh` is
    ### how a stored-but-unloadable certificate happens.
    ###
    ### The filename is discovered, not assumed. lego names the bundle after
    ### the first --domains value with the wildcard sanitized, so the file is
    ### not literally "*.<domain>.crt". Globbing means a change in that
    ### convention fails loudly here rather than silently storing nothing.
    task "store" {
      driver = "podman"

      config {
        ### Pinned by digest ALONE (tag 1.21), same driver constraint.
        image        = "docker.io/hashicorp/vault@sha256:4e33b126a59c0c333b76fb4e894722462659a6bec7c48c9ee8cea56fccfd2569"
        network_mode = "host"
        entrypoint   = ["/bin/sh", "-c"]

        ### Two template layers eat dollars here, so this uses `basename`
        ### rather than a brace expansion. Terraform renders the file, then
        ### Nomad parses the result and interpolates braces of its own; a shell
        ### brace expansion has to survive both, and the escape that satisfies
        ### one does not satisfy the other. Command substitution and plain
        ### variable references pass through untouched.
        args = [
          "set -e; cd ${acme_path}/certificates; CRT=$(ls -1 *.crt 2>/dev/null | grep -v '\\.issuer\\.crt$' | head -1); [ -n \"$CRT\" ] || { echo 'no certificate found under ${acme_path}/certificates'; exit 1; }; BASE=$(basename \"$CRT\" .crt); vault kv put -mount=${secret_mount} ${tls_path} certificate=@\"$BASE.crt\" private_key=@\"$BASE.key\" issuer_chain=@\"$BASE.issuer.crt\" > /dev/null; echo \"stored $BASE to ${secret_mount}/${tls_path}\""
        ]
      }

      volume_mount {
        volume      = "acme_state_volume"
        destination = "/acme-state"
        read_only   = true
      }

      vault {
        role = "${vault_role}"
      }

      ### The vault CLI reads VAULT_TOKEN from the environment; Nomad's vault
      ### block supplies it. VAULT_ADDR is the direct listener, not the edge:
      ### routing this through the proxy would make certificate renewal depend
      ### on the certificate it renews.
      env {
        VAULT_ADDR = "http://192.168.2.30:8200"
      }

      resources {
        cpu    = 50
        memory = 128
      }
    }
  }
}
