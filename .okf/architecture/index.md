# Architecture

The boundaries between the layers that deploy the cluster, and the rules for crossing them.

* [The three deployment layers](deployment-layers.md) - The cluster is deployed in three layers applied in order: Ansible under bootstrap/, then the Terraform root deployments/infrastructure, then deployments/applications. Says what each layer owns, the rule behind each boundary, how a later layer finds what an earlier one made without any state link, what breaks when the order is broken, and which file a new node, job, Vault role, bucket, port or HashiStack setting goes in.
