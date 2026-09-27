---
okf_version: "0.2"
---

# localstack

Durable knowledge for the homelab cluster this repository deploys: why
choices went the way they did, what was learned the hard way, and what was
planned but not built. Seeded by hand from `docs/` pages that were not user
docs. User docs are in `docs/`, starting at `docs/README.md`.

# Sections

* [Architecture](architecture/) - The boundaries between the layers that deploy the cluster, and the rules for crossing them. (1 concepts)
* [Decisions](decisions/) - Append-only records of choices that rejected a real alternative, never written over. (12 concepts)
* [Components](components/) - How a part of the cluster was built or is shaped inside, for someone changing this repository. (33 concepts)
* [Practices](practices/) - Lessons learned the hard way here, with the measurement or incident that taught each one. (7 concepts)
* [Nodes](nodes/) - One concept per physical device in the cluster, and how jobs are placed across them. (6 concepts)
* [Proposals](proposals/) - Designs and plans that were not built, or were superseded, kept with their reasoning. (6 concepts)

# Bundle files

* [Update log](log.md) - dated history of what changed in this bundle and why.
