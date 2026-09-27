# Pinned CLIs and PATH shims

`localstack deps` installs `vault`, `nomad` and `consul` at the versions this
cluster runs, and can install the shims that let a bare `nomad`, `consul` or
`vault` command use your `localstack login` session.

## Where the versions come from

`bootstrap/inventory/group_vars/all.yml`. The apt pin on the cluster nodes
and the Ansible install task read the same file, so moving a version is one
edit and your laptop cannot drift from the nodes while both look pinned. The
CLI carries no copy of the numbers. If it cannot find that file it fails and
says so. It never falls back to a built-in list.

It looks for the checkout in four places, first hit wins:

1. `--repo-root PATH`
2. `LOCALSTACK_REPO_ROOT`
3. walking up from the working directory
4. walking up from the installed module

Step 4 is what makes `just install_cli` work from any directory. It fails for
a copy of the CLI outside a checkout, which is when you pass `--repo-root`.

## Commands

```bash
localstack deps                  # report installed against pinned
localstack deps --install        # fetch and place anything that differs
localstack deps --with-shims     # also write the three shims
localstack deps --remove-shims   # delete the shims, keep the binaries
```

Reporting is the default because installing is the side effect. Any run
exits non-zero when the versions still disagree once it is done, `--install`
included, so a script can tell drift from agreement. Re-running `--install`
when everything matches downloads nothing.

Archives come from `releases.hashicorp.com`. Each one is hashed and checked
against the published `SHA256SUMS` before anything is written, so a
mismatched download never reaches your PATH.

## Two directories, and the difference matters

```
~/.localstack/bin      the pinned binaries
~/.localstack/shims    the shims
```

PATH runs shims, then bin, then the system. Put both in one directory and
`--with-shims` overwrites the pinned `nomad` with a script that runs the
unpinned system one, which is the drift this command exists to remove. Two
directories also mean `--remove-shims` can clear one without endangering the
other.

Set `LOCALSTACK_HOME` to move both.

## What a shim does

Each shim asks `localstack token <tool>` for a token and execs the pinned
binary with the right variable set for that one call: `NOMAD_TOKEN`,
`CONSUL_HTTP_TOKEN` or `VAULT_TOKEN`.

It falls through to the unmodified binary when `localstack token` fails, and
also when it succeeds but prints nothing. An empty token would clear one you
already had in the environment, which looks like success and is worse than a
failure. A broken CLI degrades to the behavior you had before the shim, never
to a dead command.

All three tools need a shim:

| CLI | Why |
| --- | --- |
| `nomad` | Reads no credential file. There is no other way in. |
| `consul` | The `_FILE` form of `CONSUL_HTTP_TOKEN` outranks the variable, and a stale or missing file breaks `consul` outright. Nothing writes that file, so the shim exports the token instead. |
| `vault` | Reads `~/.vault-token`, but the devcontainer sets `VAULT_TOKEN`, which outranks it. Without the shim a bare `vault` runs as the injected root token. |

Shims are opt-in on a laptop because they shadow commands on your PATH. The
devcontainer passes `--with-shims` when it is created, since that container
is disposable. Creating it is what triggers the install, so after a version
moves in `group_vars` you re-run `localstack deps --install` yourself. A
restart alone fetches nothing.
