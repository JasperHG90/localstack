# How to verify the workload identity chain

## Introduction

This proves the chain end to end. It writes a throwaway probe secret, runs a
scratch job that reads it keylessly, captures the WI JWT, and checks the
positive and negative policy results. Purge the secret and stop the job
afterward so nothing is left running.

## Prerequisites

- An operator Vault token and a Nomad token, with `NOMAD_ADDR` set.
- A checkout of this repo, for `tests/wi-vault-probe.nomad.hcl`.

## Directions

### Step 1: Check the trust chain exists

```
# JWKS reachable (>= 1 key)
curl -s "$NOMAD_ADDR/.well-known/jwks.json" | jq '.keys | length'

# jwt-nomad auth method exists
vault auth list -format=json | jq -e '."jwt-nomad/"'

# role binds the expected audience and policy
vault read -format=json auth/jwt-nomad/role/nomad-workloads | \
  jq '{bound_audiences: .data.bound_audiences, token_policies: .data.token_policies}'
```

### Step 2: Write the probe secret

Write the probe secret by hand (operator token; no Terraform state):

```
vault kv put -mount=secret default/wi-test/probe \
  key=wi-test-value nonce=probe
```

### Step 3: Run the scratch job

Run the scratch job (`tests/wi-vault-probe.nomad.hcl`):

```
nomad job run tests/wi-vault-probe.nomad.hcl
nomad job status -short wi-test      # status: running
```

### Step 4: Read the job's output

The job prints the WI JWT, the rendered probe secret, and its byte count to
stdout (the secret files under `secrets/` are read-protected, so read them
through `nomad alloc logs`, not `nomad alloc fs`):

```
alloc=$(nomad job allocations wi-test | awk 'NR==2{print $1}')
nomad alloc logs "$alloc" probe
```

Expected: `---JWT---` is a non-empty `eyJ...` string; `---PROBE-LEN---` is
non-zero; `---PROBE---` shows `PROBE_KEY=wi-test-value` and
`PROBE_NONCE=probe`. The non-empty probe proves the keyless read succeeded.

### Step 5: Prove the login leg

Prove the login leg directly with the captured JWT:

```
jwt=$(nomad alloc logs "$alloc" probe | awk '/^eyJ/{print; exit}')
vault write -format=json auth/jwt-nomad/login role=nomad-workloads jwt="$jwt" | \
  jq '.auth.policies'
```

Expected: `policies` includes `nomad-workloads`.

### Step 6: Check the negative cases

Using the WI token minted above:

```
witoken=$(vault write -format=json auth/jwt-nomad/login \
  role=nomad-workloads jwt="$jwt" | jq -r '.auth.client_token')

# Another job's secret VALUE is denied
VAULT_TOKEN="$witoken" vault kv get -mount=secret default/other-job/probe
# -> Code: 403, permission denied

# The bootstrap mount is closed to workload tokens
VAULT_TOKEN="$witoken" vault kv get -mount=bootstrap github
# -> Code: 403, permission denied

# But another job's secret PATH is enumerable (namespace-wide list survives)
VAULT_TOKEN="$witoken" vault kv list -mount=secret default
# -> exit 0, lists every job's path in the default namespace
```

The first two are [the narrowed policy](../explanation/workload-identity.md#threat-model-narrowed-but-not-per-job) working. The third is the surviving
gap: any workload in the `default` namespace can enumerate every other job's
secret paths (not values).

### Step 7: Tear down

```
nomad job stop -purge wi-test
vault kv metadata delete -mount=secret default/wi-test/probe
```

## Additional resources

- [Workload identity](../explanation/workload-identity.md): the chain this proves.
