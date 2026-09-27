# How to sign in to Nomad with Vault

## Introduction

Sign in to the Nomad UI, or the Nomad CLI, with your Vault login instead of a
Nomad token someone hands you.

**What signing in grants is stated in
[Human login to Vault](../reference/vault-human-auth.md#what-the-operator-can-do-the-developer-group)**,
under "What the operator can do: the `developer` group" — a shell as root
inside any container and write on every host volume. It belongs there rather
than here, because that is the section someone reads when asking what
membership buys.

## Prerequisites

- A Vault login in a group the Nomad client's assignment admits, which is
  `developer` ([How to log in to Vault](log-in-to-vault.md)).
- For the terminal route, the Nomad CLI.

## Directions

### Step 1: Log in to the Vault UI first

Log in to the Vault UI in the same browser before you click the Nomad
sign-in button.

The redirect sends you to a Vault **UI** path
(`/ui/vault/identity/oidc/provider/lab/authorize`), not an API endpoint, so
your browser must already hold a Vault UI session. If it does not, the first
attempt can fail with a generic "Failed to sign in with SSO" and leave you an
Anonymous Token. Retrying after logging into the Vault UI succeeds. Observed
2026-08-02, not yet root-caused.

### Step 2: Use the sign-in button

Click the SSO sign-in button in the Nomad UI.

A genuine refusal looks different and says so:
`error=access_denied&error_description=identity entity not authorized by client
assignment`. If you see that, you are not in a group the client's assignment
admits, and retrying will not help.

### Step 3: Sign in from a terminal instead, if you need a CLI token

From a terminal, `nomad login -method=vault` needs `xdg-open` to launch a
browser. Without it the command prints the URL and waits, which works fine —
paste it into any browser. **Its default output prints the issued token's Secret
ID in full**, so treat that output as a secret. A script can select fields
instead, with `nomad login -method=vault -t '{{ .AccessorID }}'`. `nomad login`
also takes `-json`, but that marshals the whole token object and has not been
checked here for whether it includes the Secret ID, so prefer `-t`. Note
`nomad acl token self` takes neither flag; both fail there before any network
call.

## Additional resources

- [Human login to Vault](../reference/vault-human-auth.md)
- [How to add a service that logs people in through Vault](add-a-vault-oidc-client.md)
