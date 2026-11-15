#!/bin/bash
# Spike ov-sync-consumer risk 4. Inside a privileged Ubuntu jammy container
# (orangepi4a's OS, so apt podman 3.4.4), run a Nomad 2.0.4 dev agent with
# nomad-driver-podman 0.6.4. Task a listens on 127.0.0.1:9000; poststart
# sidecar b uses network_mode "task:a". Check b reaches a on loopback and
# reaches an off-namespace address, restart task a alone, check again.
# Exit 0 only if every check passes after the restart.
set -u
D=/tmp/claude-1000/-home-vscode-workspace/39954680-d360-4c77-9baf-bede6c6eafa0/scratchpad/spike-ovc4
C=ovc4-nomad
W=$(mktemp -d)
trap 'docker rm -f $C >/dev/null 2>&1; rm -rf $W' EXIT
docker rm -f $C >/dev/null 2>&1

cat >$W/Dockerfile <<'EOF'
FROM ubuntu:22.04
RUN apt-get update -qq && DEBIAN_FRONTEND=noninteractive apt-get install -y -qq podman crun curl iproute2 iptables >/dev/null \
 && printf '[storage]\ndriver = "vfs"\ngraphroot = "/var/lib/containers/storage"\nrunroot = "/run/containers/storage"\n' > /etc/containers/storage.conf
EOF
docker build -q -t ovc4-podman:jammy $W >/dev/null || exit 2

cat >$W/job.hcl <<'EOF'
job "ns" {
  datacenters = ["dc1"]
  type        = "service"
  group "g" {
    task "a" {
      driver = "podman"
      config {
        image   = "docker.io/library/busybox:1.36"
        command = "sh"
        args    = ["-c", "mkdir -p /w && date +%s > /w/index.html && exec httpd -f -p 127.0.0.1:9000 -h /w"]
      }
    }
    task "b" {
      driver = "podman"
      lifecycle {
        hook    = "poststart"
        sidecar = true
      }
      config {
        image        = "docker.io/library/busybox:1.36"
        network_mode = "task:a"
        command      = "sleep"
        args         = ["infinity"]
      }
    }
  }
}
EOF

cat >$W/inner.sh <<'EOF'
set -u
# cgroup v2 refuses controllers on a cgroup that holds processes, so move
# this container's processes into a leaf before Nomad sets up its own.
mkdir -p /sys/fs/cgroup/init
for p in $(cat /sys/fs/cgroup/cgroup.procs); do echo $p > /sys/fs/cgroup/init/cgroup.procs 2>/dev/null; done
mkdir -p /run/podman /plugins
mv /opt/nomad-driver-podman /plugins/
podman system service -t 0 unix:///run/podman/podman.sock >/var/log/podman.log 2>&1 &
sleep 2
cat >/etc/nomad.hcl <<'H'
plugin_dir = "/plugins"
plugin "nomad-driver-podman" {
  config { socket_path = "unix:///run/podman/podman.sock" }
}
H
/opt/nomad agent -dev -bind 0.0.0.0 -config /etc/nomad.hcl >/var/log/nomad.log 2>&1 &
export NOMAD_ADDR=http://127.0.0.1:4646
for i in $(seq 60); do /opt/nomad node status 2>/dev/null | grep -q ready && break; sleep 1; done
podman version --format 'podman {{.Server.Version}}'
/opt/nomad version | head -1
/opt/nomad node status -self -verbose | grep -E 'driver.podman(\.version|\.health)? '
podman pull -q docker.io/library/busybox:1.36 >/dev/null
/opt/nomad job run -detach /opt/job.hcl >/dev/null
HOSTIP=$(hostname -I | awk '{print $1}')
ALLOC=
for i in $(seq 90); do
  ALLOC=$(/opt/nomad job allocs -t '{{range .}}{{if eq .ClientStatus "running"}}{{.ID}}{{end}}{{end}}' ns 2>/dev/null)
  [ -n "$ALLOC" ] && podman ps --format '{{.Names}}' | grep -q "^b-$ALLOC" && break; sleep 1
done
echo "alloc=$ALLOC hostip=$HOSTIP"
podman ps --format '{{.Names}} {{.Status}}'
check() {
  echo "--- $1"
  echo "a id:      $(podman inspect a-$ALLOC --format '{{.Id}}' 2>&1)"
  echo "a netns:   $(podman exec a-$ALLOC readlink /proc/1/ns/net 2>&1)"
  echo "b netns:   $(podman exec b-$ALLOC readlink /proc/1/ns/net 2>&1)"
  echo "b netmode: $(podman inspect b-$ALLOC --format '{{.HostConfig.NetworkMode}}' 2>&1)"
  echo "b interfaces: $(podman exec b-$ALLOC ip -o -4 addr 2>&1 | awk '{print $2, $4}' | tr '\n' ' ')"
  R=$(podman exec b-$ALLOC wget -T 3 -qO- http://127.0.0.1:9000/ 2>&1) && L=ok || L=fail
  echo "b -> 127.0.0.1:9000: $L ($R)"
  podman exec b-$ALLOC wget -T 3 -qO- http://$HOSTIP:4646/v1/agent/health >/dev/null 2>&1 && O=ok || O=fail
  echo "b -> $HOSTIP:4646 (off-namespace): $O"
  eval "${1}_L=$L; ${1}_O=$O; ${1}_R='$R'"
}
check before
echo "=== nomad alloc restart $ALLOC a"
timeout 120 /opt/nomad alloc restart $ALLOC a; echo "restart command exit=$?"
for i in $(seq 60); do
  S=$(/opt/nomad alloc status -json $ALLOC 2>/dev/null | python3 -c 'import json,sys;d=json.load(sys.stdin);print(d["TaskStates"]["a"]["State"],d["TaskStates"]["a"]["Restarts"],d["TaskStates"]["b"]["State"])' 2>/dev/null)
  case "$S" in "running 1 "*) break;; esac; sleep 1
done
sleep 3
echo "task a state/restarts, task b state: $S"
/opt/nomad alloc status $ALLOC | sed -n '/^Task "a"/,$p' | grep -E 'Task "|^20[0-9][0-9]-'
podman ps -a --format '{{.Names}} {{.Status}}'
echo "why the old a container stays: $(podman rm a-$ALLOC 2>&1 | tail -1)"
echo "job allocs now:"; /opt/nomad job allocs ns | tail -n +2
check after
echo "=== driver warnings and errors"
grep -E '\[(WARN|ERROR)\]' /var/log/nomad.log | grep -iE 'podman|task' | tail -10
echo "RESULT before: loopback=$before_L outbound=$before_O; after: loopback=$after_L outbound=$after_O; a served '$before_R' then '$after_R'"
[ "$before_L" = ok ] && [ "$before_O" = ok ] && [ "$after_L" = ok ] && [ "$after_O" = ok ] && [ "$before_R" != "$after_R" ]
EOF

docker run -d --name $C --privileged ovc4-podman:jammy sleep infinity >/dev/null || exit 2
for f in nomad nomad-driver-podman; do docker cp $D/dl/$f $C:/opt/$f >/dev/null; done
docker cp $W/job.hcl $C:/opt/job.hcl >/dev/null
docker cp $W/inner.sh $C:/opt/inner.sh >/dev/null
docker exec $C bash /opt/inner.sh
