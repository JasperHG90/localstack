# Break-glass recovery

Run `localstack breakglass` to print the recovery runbook for a cluster you
cannot authenticate to or reach. The command runs read-only, credential-free
reachability probes by default and prints a diagnosis plus the full
runbook. Use `--no-probe` to skip the probes and print the runbook only.

The runbook covers six failure modes: sealed Vault, expired or revoked
token, edge down with the cluster up, Nomad unreachable, Consul unreachable,
and a lost local token cache. Each section names all three routes to the
service (edge, SSH plus loopback, direct LAN) and which to reach for when
the others are suspect.

The credential boundary is load-bearing. The command never reads, caches,
prints, or exports a token, an unseal key, or any value derived from one. It
names `/opt/vault/init.json` as the location of the unseal keys and the
root token, but it never opens the file. It never runs `ssh`, `vault`,
`nomad`, `consul`, `ansible`, or `terraform` as a subprocess.

The runbook itself lives inside the CLI package, loaded with
`importlib.resources`, so an installed CLI with no repo checkout still
prints it. This page is a pointer; it duplicates no steps. Run the command
for the full text.
