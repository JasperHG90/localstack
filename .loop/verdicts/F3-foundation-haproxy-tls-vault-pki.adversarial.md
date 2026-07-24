---
verdict: pass
tree: 207d3a05f8ce94e9821517c0bfb9afcd279b7129
---

# Adversarial review — F3-foundation-haproxy-tls-vault-pki (cycle 2)

Supersedes my cycle-1 verdict, which was bound to a now-stale tree. This
one is bound to `207d3a05f8ce94e9821517c0bfb9afcd279b7129`, matching
`.loop/stamp.json` in this worktree. All three source files carry mtimes
earlier than the stamp (20:39:27 / 20:39:34 / 20:39:41 vs 20:39:54), so
the code I read is the code the gates certified; only the harness ledger
moved afterwards.

Reviewed surface, unchanged from cycle 1:
`deployments/infrastructure/pki.tf` (new, untracked),
`deployments/infrastructure/services.tf`,
`deployments/infrastructure/services/haproxy.hcl`, `.loop/ledger.json`.

## Gates, re-run by me

- `just pre_commit` — every hook `Passed`. Since `pki.tf` is untracked
  and therefore skipped by the per-file hooks under `--all-files`, I
  also ran `pre-commit run --files pki.tf` separately: also clean, and
  it rewrote nothing (`git status` identical afterwards, so the stamped
  tree survives the check).
- `terraform plan -var-file=./vars/prod.tfvars` — still
  `Plan: 7 to add, 1 to change, 1 to destroy`, identical in shape to
  cycle 1. The single destroy remains
  `null_resource.firewall["haproxy"]`, replaced because `triggers.rules`
  gained the two 443 lines and nothing else. No KV mount, auth backend,
  other firewall entry, or backend job is destroyed, and
  `nomad_job.haproxy` is still an in-place update.
- `nomad job validate` on the freshly rendered jobspec (rendered through
  `terraform console` so the real `templatefile` semantics apply):
  `Job validation successful` against the live cluster.

## Fix 1 — root CA ordering: verified fixed

The claim is that `depends_on = [vault_pki_secret_backend_root_cert.root]`
at `deployments/infrastructure/services.tf:325-329` closes the race. I did
not take the code at face value; I re-ran `terraform graph` and the edge
is now materially present:

```
nomad_job.haproxy -> vault_pki_secret_backend_root_cert.root
vault_pki_secret_backend_root_cert.root -> vault_mount.pki
```

I also re-confirmed the authorization chain was not disturbed by the new
edge — `nomad_job.haproxy -> vault_jwt_auth_backend_role.haproxy ->
vault_policy.haproxy_pki -> vault_pki_secret_backend_role.haproxy ->
vault_mount.pki` is intact. So the job now sits downstream of both the
grant and the CA, and the first-apply window where the template could
fire against a rootless mount is gone.

The accompanying comment is accurate about the underlying mechanic. I
had verified exactly that on a throwaway dev Vault in cycle 1: a PKI
mount with no root accepts `config/urls` and `roles/*` writes but
rejects `issue`.

## Fix 2 — `allow_localhost = false`: verified fixed, no regression

`deployments/infrastructure/pki.tf:52`, with the adjacent comment at
lines 48-50 now naming the default it is overriding. The plan reflects
it: `allow_localhost = false` alongside `allow_bare_domains = false`,
`allow_ip_sans = false`, `allow_subdomains = true`,
`allow_wildcard_certificates = true`.

The interesting question is not whether the flag is set but whether
setting it broke the thing the ticket actually needs, since Vault's
localhost branch and its allowed-domains branch sit in the same
validation loop. I rebuilt the mount, root CA and role byte-for-byte
from the current `pki.tf` on a throwaway `vault server -dev` and issued
against it:

- `common_name=*.localstack ttl=72h` — still succeeds. Leaf comes back
  `subject=CN = *.localstack`, `issuer=CN = localstack Root CA`,
  `X509v3 SAN: DNS:*.localstack`, validity 72h plus the 30s
  `not_before_duration`.
- `common_name=localhost` — now rejected, where it succeeded under the
  cycle-1 role.

So the tightening bites exactly where intended and nowhere else.

## Fix 3 — renewal cadence documented rather than changed: correct call

You asked whether a comment is an insufficient response. It is
sufficient, and it is the only response available. My cycle-1 finding
was explicitly informational, not a defect: the 85-95% fraction lives
in consul-template, not in any argument this repo sets. The only lever
in the diff is the template's requested `ttl`, and shortening it to hit
Q5's 48h would trade a documented, harmless discrepancy for more
frequent edge restarts, which Q4 was trying to minimize. Recording the
verified reality next to the template is the right outcome, because the
failure mode it prevents is a future reader trusting the plan's ~48h
over the implementation.

I re-verified the numbers behind the comment on the fresh dev issuance:
`lease_id = ""`, `lease_duration = 0`, `expiration` present. The leaf
genuinely carries no Vault lease, and Nomad's vendored consul-template
has the lease-less certificate fallback compiled in (the debug string
`[DEBUG] Found certificate and set lease duration to %d seconds` is
present in the binary). ~61-68h for a 72h leaf is right.

One hair-splitting caveat for the record, not a finding: the comment
attributes the fallback specifically to the response's `expiration`
field. Depending on the vendored version, consul-template may instead
parse the certificate's `NotAfter`. Both yield the same number, so the
stated cadence is correct either way; only the named field is more
specific than my evidence strictly supports.

Eval row 6 (model + rubric, threshold 4/5) — **4/5**, unchanged from
cycle 1. The comment records the mechanism, it does not alter it. The
design is sound: renewal fires with hours of slack, and a failed
renewal cannot degrade into a silently stale cert, because HAProxy
reads the PEM only at startup and a missing or unreadable PEM is a
fatal config error (I reproduced both, exit 1). The point off is purely
that a 72h cycle cannot be observed inside this ticket. Post-apply, the
cheap confirmation is to set the template's `ttl=10m` once — the role's
72h `max_ttl` is a ceiling, not a floor, so `pki.tf` needs no edit —
watch the alloc restart roughly nine minutes later with a new serial,
then revert.

## Fix 4 — stale docs left alone: I agree, no pushback

Not actioning `docs/haproxy_reverse_proxy.md` and `docs/monitoring.md`
is the right call, and I would have flagged the alternative as scope
creep. The ticket's Code surface names `haproxy.hcl`, `services.tf` and
the new PKI `.tf` only; `docs/` appears nowhere in it. I confirmed the
documentation review pass is disabled in `.loop/config.json`
(`review_passes` reads `[('adversarial', True), ('architectural',
False), ('documentation', False)]`). And the one consequence an
operator could misread as a failure — the browser trust warning — is
already recorded in-code at `pki.tf:3-6`, which satisfies the ticket's
own instruction to "note it as a follow-up". Surfacing the rest to the
operator is the correct disposition.

## Regression and scope check for this cycle

- Still zero deleted lines anywhere: `git diff --numstat` reads
  `14 0` for `services.tf` and `46 0` for `haproxy.hcl`. The ACL block
  and all twelve backends remain untouched context rather than a
  retyped move, and the `stats` frontend is unchanged.
- The cycle-2 delta is exactly the three claimed edits and nothing else:
  `+6` lines in `services.tf` (the `depends_on` plus its comment),
  `+6` in `haproxy.hcl` (the renewal comment block), and in `pki.tf`
  the `allow_localhost` line plus two comment lines. Every other byte
  of `pki.tf` is identical to what I reviewed in cycle 1.
- `git diff --name-only` lists only `.loop/ledger.json`,
  `services.tf` and `haproxy.hcl`; untracked adds are `pki.tf` and this
  verdict. `bootstrap/` and `docs/` are untouched, so the shared
  `nomad-workloads` policy and role are still exactly as Q1 required.
- Ledger movement is harness bookkeeping only (`review_cycles` 0 to 1,
  stage and verdict path).
- No provider version moved; `providers.tf` is not in the diff and
  `hashicorp/vault ~>5.3.0` stands, per restriction 7.

## Re-verified end to end after the edits

The `haproxy.hcl` change is comment-only, but comments sitting next to a
heredoc in a jobspec are exactly the sort of thing that silently breaks
rendering, so I re-ran the full chain rather than assuming:

- Rendered jobspec: `vault { role = "haproxy" }`, template writing
  `secrets/haproxy.pem`, `bind *:443 ssl crt /secrets/haproxy.pem`, and
  the `$${attr.unique.hostname}` escape correctly collapsing to
  `${attr.unique.hostname}`. `nomad job validate` passes.
- `haproxy -c -f` on the rendered config in `haproxy:3.1-alpine`
  (3.1.17) with the newly issued leaf: exit 0.
- Live run of the proxy against that leaf: `:80` returns `HTTP/1.1 301`
  with `location: https://mlflow.localstack/a?b=1`, preserving path and
  query; `:443` completes the handshake presenting the `*.localstack`
  leaf issued by `localstack Root CA`; an unrouted host over `:443`
  falls through to 503, proving the ACLs are live on the HTTPS frontend
  rather than orphaned.

## Verdict

Pass, with no open findings. Both fixes do what the hand-off claims,
verified independently rather than read off the diff: the graph edge to
the root CA is real, and `allow_localhost = false` blocks localhost
while leaving wildcard issuance intact. The two non-code responses
(documenting the renewal cadence, deferring the docs) are the right
calls and I am not asking for either to be revisited. Gates are green
when I run them, the plan destroys only the firewall null_resource it
must replace, and TLS termination, the 301, and routing are reproduced
against the real HAProxy binary and a real Vault-issued leaf. Q1
through Q6 are all honored. Nothing blocks the commit.
