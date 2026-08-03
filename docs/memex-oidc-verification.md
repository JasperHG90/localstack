# Verifying memex workload OIDC

hermes authenticates to memex with a Nomad Workload Identity JWT instead of
a static admin key. This runbook holds the checks that prove it, including
the two denials. Run them after a deploy that touches the memex auth config,
the hermes `identity` stanza, or the hermes image.

Most failure modes here are **silent**: the request still returns `200`
because hermes falls back to its API key, which is deliberately still
present. So several checks below assert on a log line, or on the absence of
one, rather than on a status code.

That fallback is narrower than it looks. It applies only when the bearer
fails to resolve at all (no token file, or config that will not validate).
Once a bearer resolves, the client sends it and nothing else, so a token
memex rejects is a hard failure with no second credential behind it.

Addresses: memex is `http://192.168.2.46:8000`; the issuer is
`https://nomad.lab.orangecluster.nl`.

## S1: the server loaded exactly one provider

```
nomad alloc logs <memex-alloc> memex | grep -i 'authentication enabled'
```

Expect both lines, and expect the count to be `1`:

```
OIDC bearer-token authentication enabled (1 provider(s)).
API key authentication enabled (3 key(s) configured, 3 exempt path(s)).
```

`1`, not `2`. A second provider would mean the human-login path leaked in
from `R6-rollout-memex-human-oidc`. A **missing** OIDC line means the JSON in
`MEMEX_SERVER__AUTH__OIDC` failed to parse and the provider was dropped
silently. That is the cheapest failure to catch, which is why this check
runs first.

## S2: API-key access still works

```
curl -s -o /dev/null -w '%{http_code}\n' http://192.168.2.46:8000/api/v1/vaults
curl -s -o /dev/null -w '%{http_code}\n' -H 'Authorization: Bearer garbage' http://192.168.2.46:8000/api/v1/vaults
curl -s -o /dev/null -w '%{http_code}\n' -H "X-API-Key: $MEMEX_ADMIN_KEY" http://192.168.2.46:8000/api/v1/vaults
```

`MEMEX_ADMIN_KEY` is the `admin_key` field of the memex auth secret in Vault
(written by `vault_kv_secret_v2.memex_auth_keys`,
`deployments/applications/secrets.tf:79-86`):

```
export MEMEX_ADMIN_KEY=$(vault kv get -field=admin_key secret/default/memex/auth)
```

(`secret` here is `var.secret_mount`. The real `vars/prod.tfvars` is
gitignored; `deployments/applications/vars/prod.tfvars.example:1` shows the
value. Substitute if yours differs.)

Expect `401` / `403` / `200`, unchanged from before the rollout. Run this
again at the end: it is the regression check, and the static keys are meant
to keep working.

## W1: a hermes token is accepted

W1 decodes the JWT Nomad wrote and presents it to memex by hand. It proves
the token itself is good, independently of whether the hermes client is
wired up.

**There is no "before the client config" window, so do not look for one.**
The `identity` stanza and the three `MEMEX_OIDC__*` vars all render from one
`templatefile` into one `nomad_job.hermes`, so any apply that touches hermes
lands them together. `-target` separates memex from hermes; it cannot
separate hermes from itself.

That changes what a W1 failure costs. Once the bearer **resolves**, the
client sends only `Authorization` and never falls back to `X-API-Key`, so a
403 here is an outage, not a free probe. (The fallback survives only where
the bearer does NOT resolve at all, which is precisely what H2 hunts for.)
Two consequences:

- **Apply memex first and let it come up**, then hermes:
  `just apply true nomad_job.memex` (the two arguments are positional,
  `refresh` then `target`; the recipe wraps the tfvars and Consul token that
  a bare `terraform apply` here lacks), then a full
  `just apply`. The two jobs share no Terraform dependency edge, so an
  untargeted apply sends them in parallel, and hermes will 403 against the
  old memex alloc until the new one is healthy.
- **Run W1 immediately after the hermes apply**, as the first thing you
  check. It isolates "is the token good" from "is the client wired up",
  which is what makes H1 and H2 readable afterwards. If W1 fails, hermes has
  already lost memex access, so treat it as a rollback signal rather than a
  diagnostic step.

```
nomad alloc exec -task hermes <hermes-alloc> \
  /opt/hermes/.venv/bin/python -c "import base64,json,pathlib;\
p=pathlib.Path('/secrets/nomad_memex.jwt').read_text().split('.')[1];\
print(json.dumps(json.loads(base64.urlsafe_b64decode(p + '=' * (-len(p) % 4))), indent=2))"
```

(Decode in python, not `base64 -d`. A JWT segment is unpadded base64url, so
`base64 -d` errors with `invalid input` for three of every four payload
lengths.)

Decode, do not assume. Assert `iss` is `https://nomad.lab.orangecluster.nl`,
`aud` contains `memex`, and `nomad_job_id` is `hermes`. Then, from the same
alloc:

```
curl -s -o /dev/null -w '%{http_code}\n' \
  -H "Authorization: Bearer $(cat /secrets/nomad_memex.jwt)" \
  http://192.168.2.46:8000/api/v1/vaults
```

Expect `200`.

## D1: a token for another audience is refused

Register a throwaway job carrying a second identity:

```hcl
identity {
  name     = "vault_default"
  aud      = ["vault.io"]
  file     = true
  filepath = "secrets/nomad_vault_default.jwt"
}
```

Present that token to memex. Expect `403`, **and** the memex log to carry:

```
OIDC token rejected for issuer ...
```

(`nomad job validate` warns "identity called vault_default but no vault
block" on this shape. Expected and harmless.)

## D2: a token from another job is refused

From the same throwaway job, present its `aud = ["memex"]` token.

Expect `403`, but from the **authorization** path, not the signature path.
The token verifies, matches no `grant_rule`, and `default_policy` is unset.

**Assert this on the server log, not the response.** memex renders "bad
signature" and "valid token that maps to no policy" as the identical
`403 {"detail": "Invalid API key or bearer token."}`, so the response cannot
tell you which one you got. The discriminator:

- D1 emits `OIDC token rejected for issuer ...`
- D2 emits **nothing**

A silent `403` is the pass here. A log line means the wrong failure fired.

This is the check that proves every other job in the cluster is not
implicitly a memex admin, so do not skip it.

Tear the throwaway job down afterward.

## H1: the client sends the bearer, not the key

```
nomad alloc exec -task hermes <hermes-alloc> \
  /opt/hermes/.venv/bin/python -c "import asyncio;\
from memex_common.config import MemexConfig;\
from memex_common.auth_client import resolve_client_headers;\
print(asyncio.run(resolve_client_headers(MemexConfig())))"
```

Expect `{'Authorization': 'Bearer eyJ...'}`. An `X-API-Key` key in that dict
means the bearer did not resolve and hermes silently stayed on the key.

Use the venv interpreter, not a bare `python`. The memex wheels install into
`/opt/hermes/.venv`.

## H2: no silent downgrade

Two greps, kept separate on purpose (a single alternation written with an
escaped pipe matches nothing under `grep -E`, which would make this check
vacuous):

```
nomad alloc logs <hermes-alloc> hermes | grep -i 'workload token file'
nomad alloc logs <hermes-alloc> hermes | grep -i 'Falling back to X-API-Key'
```

Expect **no output from either**. They come from different faults:

- `Could not read workload token file ...`: `MEMEX_OIDC__TOKEN_FILE` points
  somewhere the file is not.
- `Falling back to X-API-Key client (shared memex config unusable): ...`:
  the OIDC config is present but fails validation.

Either line means hermes is back on the API key while requests still return
`200`.

## H3: both sandboxes get the credential

Through the hermes agent, run the H1 one-liner twice: once via the terminal
tool, once via code_execution. Both `env_passthrough` lists must carry the
three `MEMEX_OIDC__*` names; updating only one is silent.

Expect `{'Authorization': 'Bearer ...'}` in **both**. Checking `env | grep
MEMEX_OIDC` is necessary but not sufficient. The vars can be present while
the token file is unreadable to that subprocess, which is the same silent
shape as H2.

## Then re-run S2

The static keys must still work. They are what makes a *misconfiguration*
recoverable: if the bearer never resolves, hermes keeps running on the key.
They do not rescue a bearer that resolves and is then rejected, so S2 is a
regression check on the keys themselves, not a safety net for the checks
above.
