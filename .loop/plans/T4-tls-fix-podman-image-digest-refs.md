---
epic = "tls"
depends_on = []
priority = 80
---

# T4 — Fix the three image references the podman driver cannot parse

## Title
Three images are pinned as `name:tag@sha256:...`. The podman driver rejects a
reference carrying both a tag and a digest, so the dnsmasq allocation fails at
apply and the certificate job would fail the same way on its first run. Pin by
digest alone.

## Size / Effort
**Small.** Three one-line changes and a comment on each. No behavior change:
each digest resolves to the same image the tag did.

## Triggered by
Operator hit it on the first apply:

```
Driver Failure: rpc error: code = Unknown desc = failed to create image:
docker.io/4km3/dnsmasq:2.90-r3@sha256:52e25fb2...: invalid image reference
...: unsupported transport docker.io/4km3/dnsmasq
```

## Context (today's state)
- Three references use the `tag@digest` form, all added in the two TLS
  tickets. Nothing else in the repo does:
  - `deployments/infrastructure/services/dnsmasq.hcl` — `4km3/dnsmasq`
  - `deployments/infrastructure/services/acme.hcl` — `goacme/lego` and
    `hashicorp/vault`
- Every pre-existing image in both deployment layers uses a plain tag
  (`docker.io/library/haproxy:3.1-alpine`, `docker.io/prom/prometheus:v3.2.1`,
  and so on). There was no digest-pinned precedent in the repo, which is why
  the form went unchallenged through review: `terraform validate`,
  `nomad fmt`, and even `nomad job validate` all accept the string. Only the
  driver rejects it, and only at run time.
- **Why it fails.** The driver tries `alltransports.ParseImageName` on the raw
  string, which reads everything before the first colon as a transport name
  and fails. It then retries as `docker://<ref>`, and containers/image rejects
  a docker reference carrying both a tag and a digest. The first error is the
  one surfaced, which is why the message says "unsupported transport" rather
  than naming the real problem.
- **The digest alone is sufficient and identical.** Verified with
  `docker buildx imagetools inspect`: `4km3/dnsmasq@sha256:52e25fb2...` and
  `4km3/dnsmasq:2.90-r3` resolve to the same manifest-list digest. Dropping
  the tag loses only human readability, which a comment restores.
- Only the dnsmasq allocation has failed so far. The certificate job is
  periodic and has not run yet, so both of its tasks carry the same latent
  failure.

## Non-goals / out of scope
- Changing which images or versions are used. Same images, same digests.
- Converting the repo's other images to digest pins. They work and are not
  this ticket's business.
- Any change to the dnsmasq config, the ACME invocation, the Vault policy, or
  the firewall rules.
- Re-running the apply. The operator applies.

## Requirements & restrictions
1. All three references pin by digest ALONE: `docker.io/<repo>@sha256:<hex>`,
   no tag component.
2. Each carries a comment naming the human-readable version the digest
   corresponds to, so the pin stays legible.
3. The digests do not change. Verify each still resolves to the same manifest
   before and after.
4. Nothing else in either jobspec changes.
5. `.claude/rules/adversarial-reviews.md`: adversarial review before done.

## Code surface
- `deployments/infrastructure/services/dnsmasq.hcl` — the `image` line in the
  `dnsmasq` task.
- `deployments/infrastructure/services/acme.hcl` — the `image` lines in the
  `issue` and `store` tasks.

## Tests & validation gates
### Repo gate
- **Command:** `just pre_commit` -> all Passed.
- **Worktree prerequisite:** `just worktree_setup <path>`.
- **Command:** `terraform -chdir=deployments/infrastructure plan` -> the only
  changes are the two `nomad_job` resources whose jobspec strings changed.
  Nothing else moves, nothing is destroyed.

### Evals — the authoritative set is
`.loop/evals/T4-tls-fix-podman-image-digest-refs.md`.

## Risk assessment
- **Blast radius: two jobs, both currently broken or unrun.** dnsmasq is
  failing now; the certificate job has never run. Neither can regress
  something that works.
- **The real risk is an unverifiable fix.** podman is not available in the dev
  container, so the reference form cannot be proven locally the way the
  earlier failures were reproduced. The evidence is the digest resolving
  identically plus every working image in the repo using a form without the
  tag-and-digest combination. Final proof is the operator's apply.
- **Reversibility: total.** Three string edits.

## Subtickets (ordered)
1. Change the three references and add the version comments.
2. Confirm each digest still resolves to the same manifest.
3. Gate, review, commit.

## Open questions
- **Q1 — Pin by digest at all, or fall back to plain tags like the rest of the
  repo?** *Recommendation:* keep the digest pins. They are the reason the
  cluster gets exactly the image that was reviewed, and the repo's plain tags
  are a weaker convention rather than a deliberate one. If the operator would
  rather match the surrounding style, plain tags work and this ticket becomes
  three even simpler edits.
- **Q2 — Should the certificate job's images be verified by an actual run
  before this closes?** They cannot be, without applying. *Recommendation:*
  no. The dnsmasq allocation reaching `running` proves the reference form for
  all three, since the failure is in parsing and is identical across them.
