# How to narrow the monitoring firewall rules

## Introduction

Use this when you narrow who may connect to Prometheus, Loki or another
monitoring port, as the table in the
[monitoring stack reference](../reference/monitoring.md) records.

`null_resource.firewall` runs `ufw allow` and has no destroy provisioner, so
narrowing a rule in Terraform does not remove the old permissive one. The
broad rule must be deleted by hand or the change is cosmetic while looking
applied.

## Prerequisites

- `sudo` on `192.168.2.47` and `192.168.2.30`.
- A shell that can run `terraform apply` in `deployments/infrastructure` and
  `deployments/applications`, with `CONSUL_TOKEN` set.
- A non-cluster LAN device, for the check in step 5.

## Directions

### Step 1: Check for rules missing from ufw's database

**Before running any ufw command that writes a rule, check for rules that
exist in the live chain but not in ufw's database.** Both `ufw allow` and
`ufw delete` emit an `iptables-restore` payload that re-declares
`ufw-user-input` and rebuilds it from `/etc/ufw/user.rules`, so a rule
missing from that file is dropped by the next write of any kind. This is not
a delete-only hazard: a plain `terraform apply` of a neighboring rule is
enough to lose it, silently and with no error.

Measured on 2026-07-26, `192.168.2.47` had two such rules: Grafana's LAN
access on 3000, and node-exporter on 9100. Applying the narrowed
Prometheus rule would have dropped both from the chain.

Only one of them matters, and it is the dangerous one. **Losing Grafana's
3000 rule takes Grafana down by every route, tailnet included.** `ubuntu`
has no tailscale interface (`lo`, `eth0`, `wlan0`, `podman0`, `veth0`), so
the `100.64.0.0/10` rule beside it is already dead at the interface level and
is not a fallback. Tailnet users arrive at `grafana.lab.orangecluster.nl`,
which resolves to `192.168.2.30` and is reachable over Tailscale's subnet
route, and HAProxy then dials `192.168.2.47:3000` from `192.168.2.30`, a LAN
source admitted by the LAN rule. Everyone depends on the rule that would
vanish, and nothing announces it.

Losing the 9100 rule, by contrast, breaks nothing. Its source and its host
are the same machine, `.47` to `.47` routes over `lo`
(`ip route get 192.168.2.47`), and ufw accepts loopback in
`ufw-before-input` (`-A ufw-before-input -i lo -j ACCEPT`) before the user
chain is consulted. The scrape keeps working and `NodeDown`
(`services/grafana/alert-rules.yaml`) stays quiet. The same is true of the
`192.168.2.47` entries added for 9090 and 3100: they are
belt-and-braces, matching the shape of the neighboring rules, not load
bearing.

`192.168.2.30` has one diverged rule of its own, `9187` from `192.168.2.47`.
That one is between different machines, so it is real.

Check it, and preview the result, without changing anything. `--dry-run`
prints the payload and touches neither the chain nor `user.rules`:

```bash
# rules that are live but absent from ufw's database
sudo iptables -S ufw-user-input | grep ACCEPT
sudo grep '^### tuple ###' /etc/ufw/user.rules

# the exact chain the next write would leave behind
sudo ufw --dry-run allow from 192.168.2.47 to any port 9090 proto tcp
```

### Step 2: Apply the infrastructure root, re-asserting what is missing

Re-assert anything missing in the **same** apply that narrows the rules,
rather than in a separate pass beforehand. Every `ufw allow` writes its rule
to `user.rules` before rebuilding the chain from it, so once all the writes
have run the database holds everything and the order among them does not
matter. Both diverged rules are already declared in Terraform, so adding
`-replace` for their resources restores them through the normal path:

```bash
cd deployments/infrastructure
CONSUL_HTTP_TOKEN=${CONSUL_TOKEN} terraform apply \
  -var-file=./vars/prod.tfvars \
  -parallelism=1 \
  -replace='null_resource.firewall["grafana"]' \
  -replace='null_resource.firewall["node_exporter_ubuntu"]'
```

`-parallelism=1` matters here: this apply drives three separate `ufw` writes
against one host, and concurrent writes can lose each other's rules. ufw does
take an exclusive lock on `/run/ufw.lock`, but it reads the rule set before
acquiring it, so two overlapping invocations can each start from the same
pre-write state and the second then writes a file missing the first's rule.
Serialized invocations are safe, which is why the order among them does not
matter above. Check the plan
before confirming. It also carries whatever else is pending in this root. At
the time of writing (2026-07-26) that includes the dnsmasq removal, which is
expected rather than a surprise.

### Step 3: Apply the applications root

Then the applications root, for Loki:

```bash
cd deployments/applications
CONSUL_HTTP_TOKEN=${CONSUL_TOKEN} terraform apply -var-file=./vars/prod.tfvars
```

### Step 4: Delete the superseded broad rules

Last, delete the superseded broad rules on `192.168.2.47`. Nothing in
Terraform does this, and skipping it leaves the change cosmetic:

```bash
sudo ufw delete allow from 192.168.0.0/16 to any port 9090 proto tcp
sudo ufw delete allow from 100.64.0.0/10 to any port 9090 proto tcp
sudo ufw delete allow from 192.168.0.0/16 to any port 3100 proto tcp
```

Delete by rule spec rather than by index: `ufw status numbered` renumbers
after every deletion, so a list of index numbers goes stale as you work
through it.

### Step 5: Confirm from a non-cluster LAN device

Confirm afterwards from a non-cluster LAN device, since a rule
still listed in `ufw status` is the whole failure this page exists to
prevent:

```bash
curl -sS --max-time 5 'http://192.168.2.47:9090/api/v1/query?query=up'  # must fail
curl -sS --max-time 5 http://192.168.2.47:3100/loki/api/v1/labels       # must fail
curl -s -o /dev/null -w '%{http_code}\n' http://192.168.2.47:3000       # must stay 302
```

## Additional resources

- [Monitoring stack reference](../reference/monitoring.md)
- [Why monitoring is not behind the edge](../explanation/why-monitoring-is-not-behind-the-edge.md)
