---
description: What `localstack breakglass` prints and probes, and what it never touches.
stale_after: 2027-01-19
sources:
  - resource: cli/src/localstack_cli/commands/breakglass.py
  - resource: cli/src/localstack_cli/commands/breakglass_runbook.md
---

# Break-glass recovery

Run `localstack breakglass` to print the recovery runbook for a cluster you
cannot authenticate to or reach. The command runs read-only, credential-free
reachability probes by default and prints a diagnosis plus the full
runbook. Use `--no-probe` to skip the probes and print the runbook only. It
always exits 0, even when a probe fails, so a wrapper never swallows the text.

The runbook opens with a check of your own connectivity, then covers six
failure modes: sealed Vault, expired or revoked token, edge down with the
cluster up, Nomad unreachable, Consul unreachable, and a lost local token
cache. Each section names all three routes to the service (edge, SSH plus
loopback, direct LAN) and which to reach for when the others are suspect.

The credential boundary is load-bearing. The command never reads, caches,
prints, or exports a token, an unseal key, or any value derived from one. It
names `/opt/vault/init.json` as the location of the unseal keys and the
root token, but it never opens the file. It never runs `ssh`, `vault`,
`nomad`, `consul`, `ansible`, or `terraform` as a subprocess.

The runbook is `cli/src/localstack_cli/commands/breakglass_runbook.md`,
shipped inside the CLI package and loaded with `importlib.resources`, so an
installed CLI with no repo checkout still prints it. This page is a pointer.
It duplicates no steps. Run the command for the full text.
