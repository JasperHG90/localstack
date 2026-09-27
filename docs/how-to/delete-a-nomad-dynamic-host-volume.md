# How to delete a Nomad dynamic host volume

## Introduction

Use this when a dynamic host volume is no longer needed and you want Nomad to
remove it. You look up the volume's ID, then delete it through the Nomad HTTP
API.

Most volumes on this cluster are `nomad_dynamic_host_volume` resources in
`deployments/infrastructure/services.tf`. Remove one of those from Terraform
instead, because the next `terraform apply` recreates a volume deleted by hand.

## Prerequisites

- A shell on a cluster node where the Nomad API answers on
  `http://localhost:4646`.
- `NOMAD_TOKEN` set to a Nomad ACL token allowed to delete host volumes.

## Directions

### Step 1: Find the volume ID

`nomad volume status`

```
Dynamic Host Volumes
ID        Name           Namespace  Plugin ID  Node ID   Node Pool  State
17c94af2  config         default    mkdir      9ec2b8c5  default    ready
45279fad  media          default    mkdir      0aaa7eaf  default    ready
af506823  data           default    mkdir      9ec2b8c5  default    ready
e57fd087  cool-host-vol  default    mkdir      9ec2b8c5  default    ready

Container Storage Interface
```

The listing shortens IDs, and the API needs the full one. Run
`nomad volume status -type host -verbose` and copy the full `ID` of the volume
you want to delete.

### Step 2: Delete the volume

`curl -H "X-Nomad-Token: ${NOMAD_TOKEN}" --request DELETE http://localhost:4646/v1/volume/host/<VOLUME_ID>`

Run `nomad volume status` again. The volume should be gone from the list.

## Additional resources

- [Nomad volumes HTTP API](https://developer.hashicorp.com/nomad/api-docs/volumes)
