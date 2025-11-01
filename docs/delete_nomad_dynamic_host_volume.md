`nomad volume status`

Dynamic Host Volumes
ID        Name           Namespace  Plugin ID  Node ID   Node Pool  State
17c94af2  config         default    mkdir      9ec2b8c5  default    ready
45279fad  media          default    mkdir      0aaa7eaf  default    ready
af506823  data           default    mkdir      9ec2b8c5  default    ready
e57fd087  cool-host-vol  default    mkdir      9ec2b8c5  default    ready

Container Storage Interface

`curl -H "X-Nomad-Token: ${NOMAD_TOKEN}" --request DELETE http://localhost:4646/v1/volume/host/<VOLUME_ID>`
