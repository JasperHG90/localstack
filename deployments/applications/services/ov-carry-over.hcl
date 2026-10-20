### Copies the clips, blogs, leo and blog-scraper trees from the old
### `openviking` bucket into `openviking-v2`, blog-scraper into blogs/. Run it
### with `nomad job dispatch ov-carry-over`. Every copy skips a key the target
### already holds, so a re-run only adds missing keys and never puts an old
### sidecar back over one the new instance has regenerated since.
###
### Exit codes say what failed, because the operator token cannot read alloc
### logs: 1 a copy, 2 the hash check, 3 a directory missing on the new side,
### 4 a listing, 5 a tree outside the four, 6 a sidecar missing at its new
### key, 7 `blog-scraper/` text left under blogs/, 8 the sidecar rewrite.
###
### blogs copies before blog-scraper, so the keys both trees hold keep the
### blogs version. blog-scraper's `.abstract.md` and `.overview.md` skip its
### copy and go through the rewrite alone, which points their URIs at blogs/.
### Copied first, they would make the rewrite skip every one as present.
###
### The hash check leaves out every sidecar: the rewrite changes some, and the
### re-index regenerates others. Sidecars are checked by presence instead.
### `rclone check` passes with every directory marker missing, so the one-way
### directory listing restore-s3 uses runs last
### (spike:seaweedfs-cutover-openviking/2).
### No listing pipes into another command: without pipefail the pipe's exit
### status would be the last command's, and a failed listing would pass.
job "ov-carry-over" {
  datacenters = ["localstack"]
  type        = "batch"
  namespace   = "default"

  parameterized {}

  group "copy" {
    constraint {
      attribute = "$${attr.unique.hostname}"
      value     = "radxa-dragon-q6a"
    }

    reschedule {
      attempts  = 0
      unlimited = false
    }

    restart {
      attempts = 0
      mode     = "fail"
    }

    task "copy" {
      driver = "podman"

      config {
        image        = "docker.io/rclone/rclone:1.75.2"
        network_mode = "host"
        entrypoint   = ["/bin/sh", "-c"]
        args = [<<-EOT
          set -u
          conf="--config /secrets/rclone.conf"
          old="seaweedfs:openviking/lab/user/jasper/resources"
          new="seaweedfs:openviking-v2/lab/user/jasper/resources"
          sidecars="--include .abstract.md --include .overview.md"
          trees="blogs clips leo blog-scraper"
          tmp=$(mktemp -d)
          target() {
            case "$1" in
              blogs|clips|leo) echo "$1" ;;
              blog-scraper) echo blogs ;;
              *) return 1 ;;
            esac
          }
          for t in $trees; do
            target "$t" > /dev/null || { echo "$t is not a tree this job carries"; exit 5; }
          done
          for t in $trees; do
            to=$(target "$t")
            skip=""
            if [ "$t" = blog-scraper ]; then skip="--exclude .abstract.md --exclude .overview.md"; fi
            rclone mkdir "$new/$to" --s3-directory-markers $conf || exit 1
            rclone copy "$old/$t/" "$new/$to/" --ignore-existing --create-empty-src-dirs --s3-directory-markers $skip $conf || exit 1
          done
          rclone copy "$old/blog-scraper/" "$tmp/sidecars" $sidecars $conf || exit 8
          find "$tmp/sidecars" -type f -exec sed -i 's#viking://user/jasper/resources/blog-scraper/#viking://user/jasper/resources/blogs/#g' {} + || exit 8
          rclone copy "$tmp/sidecars" "$new/blogs/" --ignore-existing $conf || exit 8
          for t in $trees; do
            to=$(target "$t")
            rclone check "$old/$t/" "$new/$to/" --one-way --exclude .abstract.md --exclude .overview.md $conf || exit 2
            rclone lsf -R --files-only $sidecars "$old/$t/" $conf > "$tmp/src-sidecars" || exit 4
            rclone lsf -R --files-only $sidecars "$new/$to/" $conf > "$tmp/dst-sidecars" || exit 4
            sort -o "$tmp/src-sidecars" "$tmp/src-sidecars"
            sort -o "$tmp/dst-sidecars" "$tmp/dst-sidecars"
            missing=$(comm -23 "$tmp/src-sidecars" "$tmp/dst-sidecars")
            if [ -n "$missing" ]; then
              echo "sidecars from $t missing under $to:"
              echo "$missing"
              exit 6
            fi
          done
          rclone cat "$new/blogs/" $conf > "$tmp/blogs.txt" || exit 4
          if grep -q "viking://user/jasper/resources/blog-scraper" "$tmp/blogs.txt"; then
            echo "a key under blogs/ still names blog-scraper/"
            exit 7
          fi
          for t in $trees; do
            to=$(target "$t")
            rclone lsf -R --dirs-only --s3-directory-markers "$old/$t/" $conf > "$tmp/src-dirs" || exit 4
            rclone lsf -R --dirs-only --s3-directory-markers "$new/$to/" $conf > "$tmp/dst-dirs" || exit 4
            sort -o "$tmp/src-dirs" "$tmp/src-dirs"
            sort -o "$tmp/dst-dirs" "$tmp/dst-dirs"
            missing=$(comm -23 "$tmp/src-dirs" "$tmp/dst-dirs")
            if [ -n "$missing" ]; then
              echo "directories from $t missing under $to:"
              echo "$missing"
              exit 3
            fi
          done
          echo "carried $trees"
          EOT
        ]
      }

      vault {}

      template {
        data = <<EOF
[seaweedfs]
type = s3
provider = SeaweedFS
access_key_id = {{ with secret "${seaweedfs_secret}" }}{{ .Data.data.access_key }}{{ end }}
secret_access_key = {{ with secret "${seaweedfs_secret}" }}{{ .Data.data.secret_key }}{{ end }}
endpoint = http://${seaweedfs_host}:8333
EOF

        destination = "secrets/rclone.conf"
      }

      resources {
        cpu    = 1000
        memory = 512
      }
    }
  }
}
