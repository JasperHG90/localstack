# Break-glass recovery

You cannot authenticate to the cluster, or the cluster is not answering.
This page walks every failure mode to its fix. It never holds a credential:
no token, no unseal key, no password. Read it from any machine with the CLI
installed.

## Check your own connectivity first

The cluster is reached over Tailscale. Only the manager, `firebat`
(`192.168.2.30`, SSH user `firebat`), is on the tailnet, and the tailnet
carries SSH on port 22 and the edge on 443, never an API port. The four
workers have no tailnet address at all. If you cannot reach the manager,
nothing below will help until that is fixed:

    ssh firebat@192.168.2.30 echo ok   # expect: ok

If that fails, your own connectivity is the suspect, not the cluster. Check
Tailscale (`tailscale status`), then read on.

Every service has three routes. Use the first one that answers:

1. **Edge:** `https://<svc>.lab.orangecluster.nl` over TLS. Reachable from
   the LAN and the tailnet. The default.
2. **Node-local over SSH:** `ssh firebat@192.168.2.30`, then
   `http://127.0.0.1:<port>`. Crosses no firewall, so no firewall change can
   take it away. The recovery path.
3. **Direct LAN:** `http://192.168.2.30:<port>`. Answers only from
   `192.168.0.0/16` and only while `configure_network.yml` allows the port
   from that CIDR. The change `N4-netsec-edge-only-service-access` removes
   that allow, so this route is conditional, not guaranteed. Never treat it
   as an unqualified escape hatch.

The edge and the direct LAN address share a failure: both die when `firebat`
dies. The LAN address also dies from a policy change that leaves the service
healthy. Only the SSH plus loopback route is independent of both.

## Vault is sealed

A sealed Vault refuses every read and write. Vault was initialized and
unsealed by Ansible once. The init output (root token and three unseal keys)
is stored at `/opt/vault/init.json` on the manager, owner `vault`, mode
`0600`. Reading it needs root on the manager. The CLI does not read it for
you.

Routes to check Vault is sealed, not gone:

- **Edge:** `https://vault.lab.orangecluster.nl/v1/sys/health`. A sealed
  Vault answers 503, not nothing.
- **Node-local:** `ssh firebat@192.168.2.30`, then
  `curl http://127.0.0.1:8200/v1/sys/health` (expect 503).
- **Direct LAN:** `http://192.168.2.30:8200/v1/sys/health` (expect 503).
  Answers only from `192.168.0.0/16` and only while `configure_network.yml`
  allows 8200 from that CIDR. `N4-netsec-edge-only-service-access` removes
  that allow.

To unseal, the unseal keys come from the environment, not the CLI. The CLI
prints the command and never runs it, because the script that runs it
requires the root token alongside the three unseal keys:

    # On the manager, with the three unseal keys and the root token exported:
    sudo cat /opt/vault/init.json   # root on the manager; the CLI never does this
    just unseal_vault

`scripts/unseal_vault.sh` exits 1 unless `VAULT_UNSEAL_KEY_1`,
`VAULT_UNSEAL_KEY_2`, `VAULT_UNSEAL_KEY_3`, `VAULT_ADDR` and `VAULT_TOKEN`
are all set. The three `vault operator unseal` calls need no token, but the
script's guard does, so running it through the CLI would carry the root
token through the CLI's code path. That crosses the credential boundary
this command exists to hold.

## Your token is expired or revoked

`localstack whoami` reports the token's identity and remaining TTL. A 403
from Vault means the token is gone: re-login.

    localstack login          # re-authenticate with userpass
    localstack whoami         # confirm: expect your username, not "expired"

If you have no token at all (`not logged in`), the session cache is empty,
not the cluster. See "Lost local token cache" below.

Vault, Nomad and Consul all use brokered tokens from the same `localstack
login` session. One login refreshes all three:

    eval "$(localstack env)"  # load the refreshed tokens into this shell

## Edge down, cluster up

The edge is HAProxy on the manager, terminating TLS on 443 and routing by
host header. If the edge answers nothing but the cluster is healthy, the
manager's HAProxy is down or the TLS cert is gone.

Confirm the cluster is up over SSH, the route that crosses no firewall:

    ssh firebat@192.168.2.30
    # On the manager:
    curl http://127.0.0.1:8200/v1/sys/health   # expect: 200
    curl http://127.0.0.1:4646/v1/agent/health  # expect: 200
    curl http://127.0.0.1:8500/v1/status/leader  # expect: 200, leader address

If those answer, the cluster is fine and the edge is the problem. Check
HAProxy:

    ssh firebat@192.168.2.30 'systemctl status haproxy'

The cert lives in Vault KV2 and is fetched by HAProxy at startup. A failed
renewal (the `T5-tls-certificate-expiry-alert` ticket exists to catch this)
leaves a stale cert that eventually expires and takes all twelve routed
hostnames down at once.

## Nomad is unreachable

Nomad runs on the manager at `4646`.

- **Edge:** `https://nomad.lab.orangecluster.nl/v1/agent/health` (expect
  200).
- **Node-local:** `ssh firebat@192.168.2.30`, then
  `curl http://127.0.0.1:4646/v1/agent/health` (expect 200, body with
  `server.ok: true`).
- **Direct LAN:** `http://192.168.2.30:4646/v1/agent/health` (expect 200).
  Answers only from `192.168.0.0/16` and only while `configure_network.yml`
  allows 4646 from that CIDR. `N4-netsec-edge-only-service-access` removes
  that allow.

Nomad is the scheduler. If it is down, no jobs move, but already-running
jobs keep running. The recovery path is the SSH plus loopback route above,
because after `N4-netsec-edge-only-service-access` closes 4646 to the LAN,
the only way to reach the Nomad API from off the manager is a job that
Nomad itself schedules. SSH to the manager and use loopback is the escape
that survives the firewall change.

    ssh firebat@192.168.2.30
    export NOMAD_ADDR=http://127.0.0.1:4646
    nomad node status
    nomad job status

## Consul is unreachable

Consul runs on the manager at `8500` and is Vault's storage backend and
both Terraform state backends. A Consul with no leader explains everything
else you are seeing: a sealed Vault and a dead Terraform at once.

- **Edge:** `https://consul.lab.orangecluster.nl/v1/status/leader` (expect
  200, body a quoted leader address).
- **Node-local:** `ssh firebat@192.168.2.30`, then
  `curl http://127.0.0.1:8500/v1/status/leader` (expect 200).
- **Direct LAN:** `http://192.168.2.30:8500/v1/status/leader` (expect 200).
  Answers only from `192.168.0.0/16` and only while `configure_network.yml`
  allows 8500 from that CIDR. `N4-netsec-edge-only-service-access` removes
  that allow.

Consul ACLs are on (`default_policy = "deny"`), but the anonymous token
carries read policy, so an unauthenticated GET returns the leader address.
On 401 or 403 the probe degrades to "reachable, not authorized to read the
leader" rather than calling it an outage. Send no token on either path.

    ssh firebat@192.168.2.30
    export CONSUL_HTTP_ADDR=http://127.0.0.1:8500
    consul members
    consul raft list-peers

## Lost local token cache

The session cache lives under your XDG config home
(`~/.config/localstack/session.json` by default). If it is gone or
corrupt, `localstack whoami` says `not logged in`, but the cluster is
unaffected: the cache is local state, not cluster state.

    localstack login          # re-authenticate; rebuilds the cache
    localstack whoami         # confirm
    eval "$(localstack env)"  # load tokens into the shell

If `localstack login` itself fails, the problem is upstream: Vault is
sealed (see above), the edge is down (see above), or your connectivity is
down (see the prelude).
