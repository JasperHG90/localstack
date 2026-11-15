#!/bin/bash
# Spike ov-sync-consumer risk 4, owner reversed. Inside a privileged Ubuntu
# jammy container (podman 3.4.4), run a Nomad 2.0.4 dev agent with
# nomad-driver-podman 0.6.4. Prestart sidecar r owns the netns and publishes
# group static port 18333 -> 8333. Main task a (SeaweedFS stand-in) joins
# with network_mode "task:r" and listens on 0.0.0.0:8333.
# Checks: reach a via host:18333 from another docker container, r -> a on
# 127.0.0.1, a -> off-namespace address; restart a alone, check again; then
# restart r alone and record what happens (not part of the exit code).
# Exit 0 only if every check passes before and after restarting a.
set -u
D=/tmp/claude-1000/-home-vscode-workspace/39954680-d360-4c77-9baf-bede6c6eafa0/scratchpad/spike-ovc4
C=ovc5-nomad
CL=ovc5-client
W=$(mktemp -d)
trap 'docker rm -f $C $CL >/dev/null 2>&1; rm -rf $W' EXIT
docker rm -f $C $CL >/dev/null 2>&1

cat >$W/Dockerfile <<'EOF'
FROM ubuntu:22.04
RUN apt-get update -qq && DEBIAN_FRONTEND=noninteractive apt-get install -y -qq podman crun curl iproute2 iptables python3 >/dev/null \
 && printf '[storage]\ndriver = "vfs"\ngraphroot = "/var/lib/containers/storage"\nrunroot = "/run/containers/storage"\n' > /etc/containers/storage.conf
EOF
docker build -q -t ovc5-podman:jammy $W >/dev/null || exit 2

cat >$W/job.hcl <<'EOF'
job "ns" {
  datacenters = ["dc1"]
  type        = "service"
  group "g" {
    network {
      port "s3" {
        static = 18333
        to     = 8333
      }
    }
    task "r" {
      driver = "podman"
      lifecycle {
        hook    = "prestart"
        sidecar = true
      }
      config {
        image   = "docker.io/library/busybox:1.36"
        ports   = ["s3"]
        command = "sleep"
        args    = ["infinity"]
      }
    }
    task "a" {
      driver = "podman"
      config {
        image        = "docker.io/library/busybox:1.36"
        network_mode = "task:r"
        command      = "sh"
        args         = ["-c", "mkdir -p /w && date +%s%N > /w/index.html && exec httpd -f -p 0.0.0.0:8333 -h /w"]
      }
    }
  }
}
EOF

cat >$W/inner.sh <<'EOF'
set -u
export NOMAD_ADDR=http://127.0.0.1:4646
N=/opt/nomad
HOSTIP=$(hostname -I | awk '{print $1}')
alloc() { cat /opt/alloc 2>/dev/null; }
state() { $N alloc status -json $(alloc) 2>/dev/null | python3 -c 'import json,sys;d=json.load(sys.stdin);t=d["TaskStates"];print(d["ClientStatus"],"a="+t["a"]["State"]+"/"+str(t["a"]["Restarts"]),"r="+t["r"]["State"]+"/"+str(t["r"]["Restarts"]))' 2>/dev/null; }
case "$1" in
setup)
  mkdir -p /sys/fs/cgroup/init
  for p in $(cat /sys/fs/cgroup/cgroup.procs); do echo $p > /sys/fs/cgroup/init/cgroup.procs 2>/dev/null; done
  mkdir -p /run/podman /plugins
  mv /opt/nomad-driver-podman /plugins/
  podman system service -t 0 unix:///run/podman/podman.sock >/var/log/podman.log 2>&1 &
  sleep 2
  printf 'plugin_dir = "/plugins"\nplugin "nomad-driver-podman" {\n  config { socket_path = "unix:///run/podman/podman.sock" }\n}\n' >/etc/nomad.hcl
  nohup $N agent -dev -bind 0.0.0.0 -network-interface eth0 -config /etc/nomad.hcl >/var/log/nomad.log 2>&1 &
  for i in $(seq 60); do $N node status 2>/dev/null | grep -q ready && break; sleep 1; done
  podman version --format 'podman {{.Server.Version}}'
  $N version | head -1
  $N node status -self -verbose | grep -E 'driver.podman(\.version|\.health)? '
  podman pull -q docker.io/library/busybox:1.36 >/dev/null
  $N job run -detach /opt/job.hcl >/dev/null
  A=
  for i in $(seq 90); do
    A=$($N job allocs -t '{{range .}}{{if eq .ClientStatus "running"}}{{.ID}}{{end}}{{end}}' ns 2>/dev/null)
    [ -n "$A" ] && podman ps --format '{{.Names}}' | grep -q "^a-$A" && break; sleep 1
  done
  echo $A >/opt/alloc
  echo "alloc=$A hostip=$HOSTIP state: $(state)"
  $N alloc status $A | grep -E 'Task "|^20[0-9][0-9]-' | head -20
  podman ps --format '{{.Names}} {{.Status}} {{.Ports}}'
  echo "a netmode: $(podman inspect a-$A --format '{{.HostConfig.NetworkMode}}' 2>&1)"
  echo "r id:      $(podman inspect r-$A --format '{{.Id}}' 2>&1)"
  echo "r ports:   $(podman inspect r-$A --format '{{json .HostConfig.PortBindings}}' 2>&1)"
  echo "a ports:   $(podman inspect a-$A --format '{{json .HostConfig.PortBindings}}' 2>&1)"
  ;;
check)
  A=$(alloc)
  echo "--- check $2 (state: $(state))"
  echo "r netns: $(podman exec r-$A readlink /proc/1/ns/net 2>&1)  a netns: $(podman exec a-$A readlink /proc/1/ns/net 2>&1)"
  echo "a container: $(podman inspect a-$A --format '{{.Id}} {{.State.StartedAt}}' 2>&1)"
  R=$(podman exec r-$A wget -T 3 -qO- http://127.0.0.1:8333/ 2>&1) && echo "r -> 127.0.0.1:8333 ok ($R)" || echo "r -> 127.0.0.1:8333 FAIL ($R)"
  podman exec a-$A wget -T 3 -qO- http://$HOSTIP:4646/v1/agent/health >/dev/null 2>&1 && echo "a -> $HOSTIP:4646 (off-namespace) ok" || echo "a -> $HOSTIP:4646 (off-namespace) FAIL"
  ;;
restart)
  A=$(alloc)
  echo "=== nomad alloc restart $A $2"
  timeout 120 $N alloc restart $A $2; echo "restart command exit=$?"
  for i in $(seq 40); do S=$(state); case "$S" in "running a=running/1 r=running/0"|"running a=running/0 r=running/1"|failed*|complete*) break;; esac; sleep 1; done
  sleep 4
  echo "after restart $2: $(state)"
  $N alloc status $A | sed -n '/^Task "/,$p' | grep -E 'Task "|^20[0-9][0-9]-' | head -30
  podman ps -a --format '{{.Names}} {{.Status}}'
  echo "job allocs:"; $N job allocs ns | tail -n +2
  echo "driver warnings/errors:"; grep -E '\[(WARN|ERROR)\]' /var/log/nomad.log | grep -iE 'podman|driver' | grep -v logmon | tail -6
  ;;
probe)
  A=$(alloc)
  echo "--- probe: podman create with --network container:r and -p (what a task:r container with ports would ask for)"
  podman create --name ovc5-probe --network container:r-$A -p 18334:8333 docker.io/library/busybox:1.36 true 2>&1 | tail -1
  podman rm -f ovc5-probe >/dev/null 2>&1
  ;;
esac
EOF

docker run -d --name $C --privileged ovc5-podman:jammy sleep infinity >/dev/null || exit 2
docker run -d --name $CL busybox:1.36 sleep infinity >/dev/null || exit 2
for f in nomad nomad-driver-podman; do docker cp $D/dl/$f $C:/opt/$f >/dev/null; done
docker cp $W/job.hcl $C:/opt/job.hcl >/dev/null
docker cp $W/inner.sh $C:/opt/inner.sh >/dev/null
IP=$(docker inspect $C --format '{{.NetworkSettings.IPAddress}}')
inn() { docker exec $C bash /opt/inner.sh "$@"; }
ext() {
  R=$(docker exec $CL wget -T 3 -qO- http://$IP:18333/ 2>&1) && echo "outside ($CL) -> $IP:18333 ok ($R)" || echo "outside ($CL) -> $IP:18333 FAIL ($R)"
}

inn setup
inn probe
inn check before | tee $W/before; ext | tee -a $W/before
inn restart a
inn check after_a | tee $W/after; ext | tee -a $W/after
inn restart r
inn check after_r; ext

okc() { [ "$(grep -c ' ok' $1)" = 3 ] && grep -q "$2" $1; }
okc $W/before 'a=running/0 r=running/0'; B=$?
okc $W/after 'a=running/1 r=running/0'; Af=$?
BA=$(grep -o 'ok ([0-9]*)' $W/before | head -1); AA=$(grep -o 'ok ([0-9]*)' $W/after | head -1)
echo "RESULT before_ok=$((B==0)) after_a_ok=$((Af==0)) a served '$BA' then '$AA'"
[ $B = 0 ] && [ $Af = 0 ] && [ -n "$AA" ] && [ "$BA" != "$AA" ]
