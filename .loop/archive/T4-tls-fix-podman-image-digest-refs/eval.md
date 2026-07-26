eval: T4-tls-fix-podman-image-digest-refs

**Definition of Done:** The three image references pin by digest alone, with
no tag component, so the podman driver can parse them. The dnsmasq allocation
reaches `running` on the operator's apply, and the certificate job's two tasks
carry the same corrected form. No image, digest, or other configuration
changes.

| Behavior | Input | Expected | Scorer | Threshold |
| --- | --- | --- | --- | --- |
| **Guardrail: no reference carries both a tag and a digest** | `grep -rnE 'image.*:.*@sha256:' deployments/*/services/*.hcl` | No matches. This is the exact form the driver rejects, and it is the whole defect | deterministic check (`grep` returns nothing) | 100% |
| All three references still pin the same images they did before | `grep -rhoE 'image\s+=\s+"[^"]+"' deployments/infrastructure/services/{acme,dnsmasq}.hcl`; compare each digest against the pre-change values `52e25fb2...` (dnsmasq), `f4fd80df...` (lego), `4e33b126...` (vault) | All three digests are byte-identical to before. A fix that silently changed which image runs would be a different and worse defect | deterministic check (digests unchanged) | 100% |
| Each digest still resolves to a real, multi-arch manifest | `docker buildx imagetools inspect docker.io/<repo>@sha256:<digest>` for all three | Each resolves, reports an image index, and reports the same digest it was asked for. A typo in a hex string fails here rather than at apply | deterministic check (all three resolve to the requested digest) | 100% |
| The pin stays legible to a human reading the jobspec | Read the three `image` lines | Each carries a comment naming the version the digest corresponds to (`2.90-r3` / dnsmasq 2.91, `v5.3.1`, `1.21`). A bare digest with no version is unmaintainable | model + rubric (adversarial review agent) | 4/5 |
| **Guardrail: nothing but the image lines changed** | `git diff` for the ticket | The diff touches only `image` lines and adjacent comments in the two jobspecs. No config directive, no argument, no env var, no policy, no firewall rule, no Terraform resource | deterministic check (`git diff` confined to image lines and comments) | 100% |
| The plan stays clean | `terraform -chdir=deployments/infrastructure plan` | Only the two `nomad_job` resources whose jobspec strings changed are affected. Nothing destroyed, nothing else modified | deterministic check (plan shows only the two expected job changes) | 100% |
| **The driver actually accepts the reference — the thing that failed** | Operator applies, then `nomad job status dnsmasq` | The allocation reaches `running` with no `invalid image reference` or `unsupported transport` in its events. This cannot be proven in the dev container, since podman is not available there, so it is the operator's check and it is the one that matters | human + rubric (operator observes after apply) | 100% |
| The certificate job's tasks are covered by the same proof | `nomad job status acme` after its first periodic run, or a manual dispatch | Both tasks pull their images without a reference error. The failure mode is in parsing and is identical across all three references, so dnsmasq reaching `running` is strong evidence for these two, but confirm on the first real run | human + rubric (operator observes on first run) | 100% |
