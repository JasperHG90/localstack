job "rescue-ssh" {
  datacenters = ["localstack"]
  type        = "sysbatch"

  group "rescue" {
    task "inject-key" {
      driver = "podman"

      config {
        image   = "docker.io/library/alpine:3"
        command = "/bin/sh"
        args = ["-c", <<-SCRIPT
        PUBLIC_KEY='ssh-rsa xxxxxxxxxxx'

        for auth_keys in /host-home/*/.ssh/authorized_keys; do
          [ -f "$auth_keys" ] || continue
          if ! grep -qF "$PUBLIC_KEY" "$auth_keys"; then
            echo "$PUBLIC_KEY" >> "$auth_keys"
            echo "Injected key into $auth_keys"
          else
            echo "Key already present in $auth_keys"
          fi
        done
        SCRIPT
        ]
        volumes = ["/home:/host-home"]
      }
    }
  }
}
