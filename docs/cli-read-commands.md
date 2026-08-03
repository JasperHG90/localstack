# Reading the cluster

Four commands that answer questions no single native CLI can, by joining
Vault, Nomad, Consul and the edge. They only read. Nothing here writes.

They do not restate `nomad job status` or `vault kv list`. Reach for those
when you want one system's own view.

```bash
localstack status                  # all three systems at once
localstack service                 # what the edge serves, and what runs it
localstack service memex --open    # one row, and open its URL
localstack secret hermes           # which Vault paths a job wants
localstack vault grants memex      # which paths that job may read
```

`--json` works on all four and emits the command's own data, so the JSON
cannot drift from the table.

## `status`

Vault's seal state, node readiness, job health and failing Consul checks, in
one view. The four reads run at once, each with its own timeout.

A source that fails renders as `ERROR` naming the reason, and the command
exits non-zero. That is the point: three green rows produced by a swallowed
timeout would be worse than no command.

Vault's `sys/health` needs no token of its own, so that row answers even when
Vault is the thing refusing everyone else. It does not survive a dead
session: like every command here, `status` loads the session first and exits
if there is none. Run `localstack login` first.

## `service`

An outer join over the edge's routes and Nomad's jobs, with Consul health as
a column. The disagreements are the output, so nothing is dropped:

| `source` | Meaning |
| --- | --- |
| `job-id` | A route whose name matches a Nomad job. The common case. |
| `consul-name` | No such job, but a Consul service by that name. `vault`, `nomad` and `consul` resolve this way: they are agent endpoints. |
| `unresolved` | A routed hostname with nothing behind it. `s3` is the live example. The row still renders, with its backend. |
| `no-route` | A job the edge does not serve. Thirteen exist. |

Health comes from each job's own registered service names, read off the job
rather than guessed from its id. A job with no check reads `no check`, never
`passing`.

Routes come from the running haproxy job's `local/haproxy.cfg` template, not
from `deployments/infrastructure/services/haproxy.hcl`. That file is a
Terraform input full of unrendered `${...}`, and two live jobs have no file
in this repo at all, so anything repo-derived under-reports.

`--open` prints the URL before it tries to launch a browser, and exits zero
either way. In a container the launch is the part that fails.

## `secret <service>`

The Vault paths a job's templates reference, and whether each one is there.

Four states, and the third one matters:

- `present`
- `missing`
- `denied`, which is never folded into `missing`. Being told a secret does
  not exist when you merely cannot see it sends you to write one that is
  already there.
- `unknown`, for a reference the job computes at render time rather than
  writing down.

Existence comes from `secret/metadata/`. That endpoint returns versions and
timestamps and no `data` field, so no value is read and none can be printed.

## `vault grants <job>`

The `nomad-workloads` policy grants each workload its own secrets by
templating the path on the caller's identity. Read raw it tells you nothing
about your job, so this substitutes the job id and namespace and shows both
the raw line and the resolved one.

Use `--namespace` for a namespace other than `default`.

It renders policy text. It is not an authorization decision: Vault resolves
these templates per request against the calling entity, and this resolves
them from arguments. The output says so.

## What the token can and cannot read today

`localstack login` brokers `nomad/creds/deploy`, whose policy deliberately
withholds `list-jobs` and node read. Until the CLI also brokers
`nomad/creds/manage`:

- `status` renders its Nomad rows as `ERROR` and exits non-zero. The Vault
  and Consul rows still fill.
- `service` cannot build its join at all, so it exits with the denial rather
  than printing a half table.

`secret` and `vault grants` work now, on grants the `developer` policy
already carries.

When a read is refused, the message says which of the two problems you have.
A dead session says to log in. A missing grant names the capability and says
that logging in again will not help, because it will not.

Consul data is read with no token, so it shows whatever the agent's own
default identity can see. Consul narrows this list by ACL silently and never
errors when it is short, so every view carrying Consul data says so in a
footer.
