---
verdict: pass
tree: c3cdfecc27a76fd4a9e98ef3ad6bfba229ba84ca
---

# F10 documentation review (re-run after comment fix)

## Scope

Re-run after the comment in
`bootstrap/roles/nomad_server/templates/nomad.hcl.j2:40-41` was reworded.
The prior pass was PASS with one non-blocking nit (F2): the old phrasing
("F1's docs/workload-identity.md points M1 at this URL") was loose, since
F1's doc points M1 at the JWKS URL, not the discovery URL. This re-run
confirms the reworded claim is accurate and the nit is resolved.

Changed doc surfaces (unchanged from the prior pass except the comment text):
- `bootstrap/roles/nomad_server/templates/nomad.hcl.j2:33-41` (comment + `oidc_issuer`)
- `.loop/plans/M1-minio-poc-service-account.md:368-380` (relayed Q1 resolution)
- `bootstrap/playbooks/configure_hashistack_server.yml:43` (one var, no doc surface)

`loopctl verify` returns `ok` against tree
`c3cdfecc27a76fd4a9e98ef3ad6bfba229ba84ca`.

## Findings

### F2 (resolved) — reworded F1 doc pointer in the comment

The comment at `nomad.hcl.j2:40-41` now reads:

> F1's docs/workload-identity.md defers discovery to F10; this is the URL
> F10 owns and M1 points MinIO's config_url at.

Checked against `docs/workload-identity.md`:
- `:179-180`: "F1 does **not** deliver an OIDC discovery document: the
  discovery endpoint is disabled cluster-wide." — supports "defers
  discovery to F10."
- `:187-191`: "Enabling discovery means setting `server { oidc_issuer = ... }`
  ... That is owned by `F10-foundation-nomad-oidc-issuer`, not F1. F1's
  scope is JWKS only." — supports "defers discovery to F10" and "this is
  the URL F10 owns."
- `:35`: "This is the URL M1 points MinIO's `identity_openid` at" refers
  to the JWKS URL, not the discovery URL. The reworded comment correctly
  does not claim F1 points M1 at the discovery URL; it says F1 *defers*
  discovery to F10, and F10 owns the issuer URL M1's `config_url` derives
  from.

Cross-checked against `.loop/plans/M1-minio-poc-service-account.md:368-380`:
the relayed Q1 resolution derives M1's `config_url`
(`https://nomad.lab.orangecluster.nl/.well-known/openid-configuration`)
from the `oidc_issuer` F10 sets, and states "F1 delivers JWKS only and
does NOT enable discovery; F10 is the owner." Consistent with the comment.

The nit from the prior pass is resolved. The new phrasing is accurate.
One precision note (non-blocking): "M1 points MinIO's config_url at" the
issuer URL is shorthand for "at the discovery document derived from the
issuer." M1's `config_url` is the `/.well-known/openid-configuration` path,
not the bare issuer. A reader following the pointer to the doc and the M1
plan finds the exact derivation, so this is not misleading.

### F1, F3, F4, F5 — unchanged from prior pass

- F1 (haproxy.hcl:101 citation): verified accurate.
- F3 (M1 relay text): all claims grounded.
- F4 (slop scan): re-ran on the reworded comment. Em dashes: 0.
  Double-dash prose: none. Tier-1 slop words: none. Identity leaks: none.
  British spellings: none. Bare TODO/FIXME: none. All cited paths and URLs
  resolve.
- F5 (docs/workload-identity.md freshness): F10 landing the setting does
  not change any claim in F1's doc. No update needed.

## Verdict

PASS. The reworded comment resolves the prior non-blocking nit: it
accurately states that F1's doc defers discovery to F10 and that F10 owns
the issuer URL M1's `config_url` derives from. The slop scan is clean, the
M1 relay is consistent, and `docs/workload-identity.md` needs no update.
Nothing blocks merge.