# Update Log

## 2026-09-26

- **Bundle created** (`index.md`): Adopted the Open Knowledge Format so decisions, lessons and unbuilt plans stop sitting in `docs/` beside user guides, where a reader could not tell a current instruction from a record of intent. Recorded as [ADR 0001](/decisions/0001-durable-knowledge-lives-in-an-okf-bundle.md).
- **docs/ sorted by reader intent** (`decisions/0002-docs-are-sorted-by-reader-intent.md`): Split the 29 flat pages in `docs/` into how-to, reference and explanation, keeping their wording, and moved everything aimed at people working on the repository into this bundle.
- **Decisions carved out of docs** (`decisions/0003` to `0012`): Wrote retrospective records for the choices the old pages already argued with a named rejected alternative: public lab DNS, no `.consul` forwarding, Vault-minted Postgres users and per-job JWT roles, OpenViking's static MinIO key, Bifrost rerank and missing browser surface, and three Login MFA choices. Numbered in the order the choices were made.
- **Proposals kept, not deleted** (`proposals/`): The credential-rotation and RISC-V plans, the Postgres-to-NATS bridge and the Postgres dynamic-credentials follow-up were never built, and the OpenViking dashboard was superseded. Each says what state it is in, so a reader does not mistake it for current behavior.
- **Monitoring build plan** (`components/monitoring-stack.md`): Kept the original build plan as history and recorded that git shows the stack on `ubuntu` from its first commit, which contradicts the plan's claim that it moved there from firebat.

## 2026-09-27

- **Components filled in** (`components/`): Added 31 concepts, one per subsystem, covering how each part of the cluster is put together across both Terraform roots, the jobspecs, Ansible and the CLI, and the traps that shaped it. Written from the code, its `###` comment blocks and the archived loop tickets, because that is where this repository's build reasoning was kept and `docs/` never held it.
- **Nodes section added** (`nodes/`): One page per device, so a reader can see what a node carries, why each job is pinned there and what breaks when it goes down, without assembling it from five jobspecs and two Terraform roots. The cross-node placement rules moved here from `components/cluster-nodes.md`, now [Node placement](/nodes/placement.md).
- **Deployment layers** (`architecture/deployment-layers.md`): Wrote down what Ansible, the infrastructure root and the applications root each own, because the rule for the infrastructure-applications line was stated nowhere, and the written Ansible rule ("no management token in Terraform") has been false since G2 brokered one into the infrastructure root.
