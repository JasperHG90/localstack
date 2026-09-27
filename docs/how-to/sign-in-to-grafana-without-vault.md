# How to sign in to Grafana without Vault

## Introduction

When Vault is down, Grafana's Vault SSO button cannot work. The local admin
account still works.

Read `default/grafana/admin` before you need it. If Vault is sealed you cannot
fetch the password from Vault, and Grafana is the tool you want open while you
diagnose why. When Vault will not answer at all, `localstack breakglass` prints
the runbook for getting it back. It names `/opt/vault/init.json` on firebat as
where the unseal keys live, and deliberately never opens it: you read that
file yourself, as root on the manager.

## Prerequisites

- The Grafana admin password, read from Vault KV2 at `default/grafana/admin`
  while Vault was still up.

## Directions

### Step 1: Sign in as admin

Go to `https://grafana.lab.orangecluster.nl/login`, skip the Vault button, and
sign in as `admin` with the password from Vault KV2 at `default/grafana/admin`.

## Additional resources

- [How to sign in to Grafana](sign-in-to-grafana.md)
- [Monitoring stack reference](../reference/monitoring.md)
- [`localstack breakglass` reference](../reference/cli-breakglass.md)
