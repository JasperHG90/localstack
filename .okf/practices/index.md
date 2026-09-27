# Practices

Lessons learned the hard way here, with the measurement or incident that taught each one.

* [Edge certificate names must be flat and under a real domain](edge-certificate-names.md) - The edge's earlier `*.localstack` wildcard failed in every client even for flat names, because a wildcard has to sit at least two labels above the root.
* [Flashing a Jetson Orin Nano](jetson-orin-nano-flashing.md) - Scratch notes from setting up the Jetson Orin Nano: firmware version, links for flashing to NVMe after SD card setup, holding the snap, and outside network access.
* [Measure a vision model before OpenViking uses it](openviking-vision-models.md) - Being in Bifrost's catalog does not mean a model accepts an image, and OpenViking hides the failure behind a normal-looking summary. Measure a model before adding it to VISION_MODELS.
* [Plan premise sweep, 2026-07](plan-premise-sweep.md) - Audit of thirteen loop ticket plans that had never had a plan-level review: what each loop-plan-reviewer verdict found against the repo and the live cluster, what was corrected, and the forks left for the operator.
* [Terraform write-only credential chains](terraform-write-only-credentials.md) - Three defects that pass terraform validate and cost real time in the Postgres spike: ephemeral values differ across applies, vault_kv_secret_v2 reads the secret back into state, and postgresql_role strips memberships granted by postgresql_grant_role.
* [ufw rules outside user.rules](ufw-rules-outside-user-rules.md) - Any ufw write rebuilds the ufw-user-input chain from /etc/ufw/user.rules, so a live rule missing from that file vanishes on the next write, and narrowing a rule through Terraform never removes the old one. Measured on 2026-07-26 while narrowing the Prometheus and Loki rules.
* [Traps in Vault TOTP enrollment](vault-totp-enrollment.md) - Vault 2.0.3's Login MFA API behaviors measured while building scripts/vault_mfa.sh: silent admin-generate on an enrolled entity, no enrollment listing, the challenge nested in auth, secrets active on issue, and vault list printing {}.
