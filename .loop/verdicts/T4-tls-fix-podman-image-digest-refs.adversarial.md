---
verdict: pass
tree: 8d438deb8108326bd5169da911eb919d995233a8
---

# T4 — Fix the three image references the podman driver cannot parse

**Verdict: pass.** The diagnosis is correct and I proved it executably rather
than by argument. The fix is the right one, the digests are unchanged, the
diff is confined to the three image lines and their comments, and both gates
pass. No blocking findings, no required fixes. Three notes for the operator
below.

---

## 1. Premise: is digest-only actually the right fix?

**Yes, and it is now proven, not reasoned.** This was the crux the hand-off
flagged as unverifiable ("podman is not available in the dev container").
podman and skopeo are indeed absent here, but the failing code path is not
podman's — it is the Nomad driver's own pre-flight parse, which is plain Go
over `github.com/containers/image/v5`. Go 1.26.5 is available, so I ran it.

### The failure chain, from the operator's error string back to source

The operator's message is `failed to create image: <ref>: invalid image
reference <ref>: unsupported transport docker.io/4km3/dnsmasq`. Every link
resolves to real upstream source:

- `nomad-driver-podman` `driver.go:1038` — `fmt.Errorf("failed to create
  image: %s: %w", createOpts.Image, createErr)`
- `driver.go:1333` — `fmt.Errorf("invalid image reference %s: %w", image, err)`
- `driver.go:1505` `parseImage` — `strings.SplitN(image, ":", 2)` takes
  everything before the FIRST colon as the transport name. For
  `docker.io/4km3/dnsmasq:2.90-r3@sha256:...` that is
  `docker.io/4km3/dnsmasq`, which matches no case, so the `default:` branch
  retries the whole string through the docker transport and, on failure,
  returns `fmt.Errorf("unsupported transport %s", transport)`.
- `containers/image/v5/docker/docker_transport.go:104-105` `newReference` —
  ```go
  if isTagged && isDigested {
      return dockerReference{}, errors.New("Docker references with both a tag and digest are currently not supported")
  }
  ```

The inner error is discarded by the driver's `default:` branch, which is
exactly why the surfaced message names the transport instead of the real
cause. The plan's account of this is accurate.

### Executable proof

I reproduced `parseImage` verbatim against the real `containers/image v5.36.2`
and ran the six actual references plus controls:

```
FAIL docker.io/4km3/dnsmasq:2.90-r3@sha256:52e25fb2...
  [inner: Docker references with both a tag and digest are currently not supported]
  -> unsupported transport docker.io/4km3/dnsmasq
FAIL docker.io/goacme/lego:v5.3.1@sha256:f4fd80df...    -> unsupported transport docker.io/goacme/lego
FAIL docker.io/hashicorp/vault:1.21@sha256:4e33b126... -> unsupported transport docker.io/hashicorp/vault
OK   docker.io/4km3/dnsmasq@sha256:52e25fb2...
  -> transport=docker dockerRef=docker.io/4km3/dnsmasq@sha256:52e25fb2...
OK   docker.io/goacme/lego@sha256:f4fd80df...          -> transport=docker
OK   docker.io/hashicorp/vault@sha256:4e33b126...      -> transport=docker
OK   docker.io/library/haproxy:3.1-alpine              -> transport=docker   (control: existing repo form)
```

The three old references fail with byte-identical text to the operator's
error. The three new ones parse, land on the `docker` transport, and
round-trip `DockerReference().String()` to the same digest string the jobspec
carries. That string is what `createImage` then hands to
`podmanClient.ImageInspectID` / the pull (`driver.go:1335`), so no further
parsing stands between the jobspec and the registry.

### The fix is version-robust

I checked `parseImage` at `v0.5.2`, `v0.6.0`, `v0.6.1`, `v0.6.2`, `v0.6.3`
and `main` — byte-identical in all six. The driver is installed unpinned from
the HashiCorp apt repo (`bootstrap/playbooks/install_dependencies.yml:100`),
so version drift on the node cannot invalidate this.

### Is `docker.io/` safe in front of a digest?

Yes. `reference.ParseNormalizedNamed` splits domain from path before looking
at the tag/digest suffix, so an explicit `docker.io/` domain is a no-op
normalization. My probe confirms `docker.io/4km3/dnsmasq@sha256:...` and the
bare `4km3/dnsmasq@sha256:...` produce the identical `DockerReference()`
string. `TagNameOnly` does not inject `:latest` here either, because a
digested reference is not name-only — which is what would have re-created the
tag-plus-digest condition. Keeping the prefix matches the repo's convention
and costs nothing.

### Q1 (digest pins vs. plain tags): the plan's recommendation is right

Keep the digest pins. Plain tags would also work, but the argument for
retreating to them was "digest pinning is what introduced the failure" — that
premise is now false. `tag@digest` introduced the failure; digest-alone is a
form the driver handles on the same code path as every working image in this
repo. Retreating would surrender the pin for no correctness gain.

---

## 2. Decision-record / repo-convention conformance

No `DECISIONS.md` in this tree. Against the standing rules:

- `.claude/rules/pre-existing-issues.md` — nothing skipped; the pre-existing
  `vault_kv_secret_v2` deprecation warning in the plan output predates this
  ticket and is out of its surface.
- `CLAUDE.md` §3 "Surgical Changes" — honored, see §4.
- Comment style (`###` in jobspecs) matches both files' existing usage
  (`acme.hcl:49`, `dnsmasq.hcl:22`).
- No test framework applies (Terraform-rendered HCL, no Python/test surface);
  `.claude/rules/python-testing.md` is not engaged. The eval marker's
  deterministic checks are the substitute and I re-ran them independently.

---

## 3. Correctness of the diff

**Claim 1 — no reference carries both a tag and a digest.** Confirmed.
`grep -rnE 'image.*:.*@sha256:' deployments/*/services/*.hcl` exits 1 with no
output. Repo-wide, the only surviving `tag@digest` strings are two prose
citations in the archived plan `.loop/plans/F4-foundation-dnsmasq-localstack-dns.md:139,266`.
Historical planning records, not live config — leave them.

**Claim 2 — digests unchanged.** Confirmed byte-for-byte against `HEAD`:
`52e25fb2601156ab66f6a0872c180b285df7cafaa41267d8d65689f066490641`,
`f4fd80df0ef94d2f536cc2e7fb5bdbd090fb0aa81b3595226b9fe814bb9a2bfe`,
`4e33b126a59c0c333b76fb4e894722462659a6bec7c48c9ee8cea56fccfd2569`
(`dnsmasq.hcl:32`, `acme.hcl:47`, `acme.hcl:133`).

**Claim 3 — each digest still resolves.** Confirmed independently via
`docker buildx imagetools inspect --raw` on all three digest-only references.
Each returned the digest it was asked for.

**Claim 4 (manifest lists) — not broken.** All three resolve to a multi-arch
index, not a single-arch manifest:

| Reference | Media type | Platforms |
| --- | --- | --- |
| `4km3/dnsmasq@52e25fb2` | `oci.image.index.v1+json` | linux/amd64, linux/arm64, linux/arm/v7 |
| `goacme/lego@f4fd80df` | `oci.image.index.v1+json` | linux/amd64, linux/arm64, linux/arm/v6, linux/arm/v7 |
| `hashicorp/vault@4e33b126` | `distribution.manifest.list.v2+json` | linux/386, linux/amd64, linux/arm64 |

A digest is a content address: pointing at an index digest yields the index,
and podman resolves it to the host platform exactly as a tag would. No
`arch`/`os`/`variant` override is set in either jobspec, so the host-platform
default applies. Both jobs are constrained to `firebat`
(`dnsmasq.hcl:7-10`, `acme.hcl:17-20`), and all three indexes carry both
amd64 and arm64, so the pull resolves whichever firebat is. Behavior is
identical to the previous tag.

---

## 4. Scope

**Claim 5 — nothing else changed.** Confirmed from the strongest available
vantage: the rendered `terraform plan` diff, which shows the final template
output rather than the source file. Every changed line inside both jobspec
strings is one of the three `image` lines or an adjacent `###` comment. No
config directive, arg, env var, policy, template, service block or resource
stanza moved.

**Claim 6 — the plan is clean.** Re-ran
`terraform plan -var-file=./vars/prod.tfvars` against the live Consul backend:
`Plan: 0 to add, 2 to change, 0 to destroy`, the two being
`nomad_job.acme` and `nomad_job.dnsmasq`, both updated in place.

**Gate.** Re-ran `just pre_commit`: all ten hooks Passed (JSON, YAML, AST,
merge conflicts, private key, EOF, `nomad fmt -recursive`,
`terraform fmt -check -recursive`, `terraform validate` per root).

The `.loop/ledger.json`, plan and eval files in the diff are harness
bookkeeping and were flagged as expected in the hand-off.

---

## 5. Notes (non-blocking, no action required)

**N1 — `podman pull` with the old form would have worked, which may confuse
debugging.** `containers/common` `libimage.Runtime.Pull` calls
`normalizeTaggedDigestedString`, which strips the tag when both are present
(Docker compat). So `podman pull docker.io/4km3/dnsmasq:2.90-r3@sha256:...`
on the node succeeds. The rejection is entirely in the Nomad driver's
`parseImage`, which runs before podman ever sees the string. If anyone tries
to reproduce the original failure with a bare `podman pull`, they will not.
This corroborates the fix; it does not weaken it.

**N2 — reaching `running` may still expose an unrelated second failure.**
The dnsmasq allocation died at image creation, so nothing downstream of the
pull has ever executed on this cluster. The port 53 / systemd-resolved bind
interplay that `dnsmasq.hcl:46-51` anticipates is untested in practice. If
the next apply fails differently, that is a new problem, not this fix failing.
Eval row "the driver actually accepts the reference" is satisfied by the
absence of `invalid image reference` / `unsupported transport` in the alloc
events, which is a narrower and better signal than "reaches running".

**N3 — comment weight.** The five-line driver-internals explanation at
`dnsmasq.hcl:27-31` sits directly above a pre-existing five-line version-floor
comment, so the `image` line now carries ten lines of preamble. It is
accurate and the ticket asked for a comment, so this is taste, not a finding.
The two-line and one-line forms in `acme.hcl` are better calibrated.

---

## Evidence index

- `deployments/infrastructure/services/dnsmasq.hcl:27-32`
- `deployments/infrastructure/services/acme.hcl:45-47`, `acme.hcl:132-133`
- `bootstrap/playbooks/install_dependencies.yml:100` (driver installed unpinned)
- `hashicorp/nomad-driver-podman` `driver.go:1038`, `:1331-1335`, `:1505-1531`
  (identical v0.5.2 through main)
- `containers/image/v5` `docker/docker_transport.go:56-76` (ParseReference),
  `:90-112` (newReference, tag-plus-digest rejection)
- Gates re-run independently: `just pre_commit` (10 Passed),
  `terraform -chdir=deployments/infrastructure plan -var-file=./vars/prod.tfvars`
  (0 add / 2 change / 0 destroy)
