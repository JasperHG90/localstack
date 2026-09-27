---
type: component
title: embark, the embedding and rerank server
description: "How embark serves the embedding and rerank models on the Jetson's GPU: models pulled as KitOps ModelKits from the cluster registry by a prestart task, one models.json driving both pull and serve, the three settings that put the GPU in the container, and the unified-memory, Redis-lease and firewall traps."
tags: [embark, embeddings, rerank, gpu, jetson, kitops, registry, models]
status: stable
generated:
  by: claude-opus/5.5
  at: 2026-09-27
sources:
  - id: embark-jobspec
    resource: git:3ec5d1e:deployments/applications/services/embark.hcl
  - id: embark-config
    resource: git:3ec5d1e:deployments/applications/services/embark/config.toml
  - id: embark-models
    resource: git:3ec5d1e:deployments/applications/services/embark/models.json
  - id: embark-pull
    resource: git:3ec5d1e:deployments/applications/services/embark/pull.sh
  - id: embark-readme
    resource: git:3ec5d1e:deployments/applications/services/embark/README.md
  - id: embark-dockerfile
    resource: git:3ec5d1e:deployments/applications/services/embark/Dockerfile.embark
  - id: app-services
    resource: git:3ec5d1e:deployments/applications/services.tf
  - id: app-secrets
    resource: git:3ec5d1e:deployments/applications/secrets.tf
  - id: infra-database
    resource: git:3ec5d1e:deployments/infrastructure/database.tf
  - id: infra-services
    resource: git:3ec5d1e:deployments/infrastructure/services.tf
  - id: embedder-swap
    resource: git:d2cf84d
---

# embark, the embedding and rerank server

embark is an OpenAI-compatible server for two ONNX models, an embedder and a
cross-encoder reranker, on `jetson-orin-nano` (192.168.2.46), port 8000. It
took the node memex held: the memex job is commented out in
`deployments/applications/services.tf` because the two do not fit together.
Almost nothing calls embark directly. OpenViking and the other agents reach it
through [Bifrost](/components/bifrost.md) as `embark/embedding` and
`embark/reranker`. [driftwatch](/components/driftwatch.md) is the one direct
caller.

## The pieces

| Piece | Where |
|---|---|
| Job, two tasks | `deployments/applications/services/embark.hcl` |
| Which models are served | `deployments/applications/services/embark/models.json` |
| embark's own settings | `deployments/applications/services/embark/config.toml` |
| The prestart pull script | `deployments/applications/services/embark/pull.sh` |
| The Jetson image and its build | `Dockerfile.embark` and `justfile` in the same directory |
| Terraform wiring | `local.embark_*` and `nomad_job.embark` in `deployments/applications/services.tf` |
| API key and its copies | `deployments/applications/secrets.tf` |
| Model and cache volume | `nomad_dynamic_host_volume.embark_data`, `deployments/infrastructure/services.tf` |
| Redis cache credential | `vault_database_secret_backend_role.cache` in `deployments/infrastructure/database.tf`, JWT role in `machine_roles.tf` |

The volume is pinned to `jetson-orin-nano` in the infrastructure root and the
job to the same host through `embark_hostname` in the applications root. The
two are a pair with no Terraform edge between them. Apply infrastructure first.

## Model delivery

Models are not in the image. Each is a KitOps ModelKit in the cluster registry
at `registry.lab.orangecluster.nl`. `models.json` maps a served name to a
registry reference, and `services.tf` turns that one file into two inputs:

- `EMBARK_MODELS`, a JSON env var pointing each served name at
  `/var/lib/embark/artifacts/<name>`, rendered as a single-quoted env file
  because its double quotes cannot go in an HCL `env` block. It merges with
  `config.toml` per key and cannot unset a key the file declares.
- `models.txt`, one `<name> <reference>` per line, which `pull.sh` reads.

So what is pulled and what is served cannot drift. `models.json` is
round-tripped through `jsondecode` so a syntax error fails the plan.
`config.toml` cannot be, because Terraform has no TOML decoder, so a typo
there reaches embark and fails at its own startup check. `[models]` is kept
out of it for two reasons recorded in the source: `config.toml`'s header says a
second copy of the model list would drift from the one the pull task reads,
and the `services.tf` comment adds that JSON gets the plan-time check TOML
cannot.

The `model-pull` prestart task runs the `kitops` image and `kit unpack`s each
reference. It writes a `.ref` marker after a complete unpack and skips any
model whose marker matches, so a restart does not re-fetch. It deletes the
marker before unpacking, so an interrupted pull is retried. Three traps are
recorded in `pull.sh` and the jobspec:

- `--config` points at `/secrets/kit`, a 1 MiB tmpfs that is kit's whole
  storage root. This is safe only because `unpack` streams from the registry.
  A `kit pull` would fill it.
- Registry credentials are rendered as a Docker-style auth file, so the
  password is never a process argument and there is no `kit login`. They come
  from embark's own copy at `default/embark/registry`, because the
  `nomad-workloads` role lets a job read only its own prefix.
- `pull.sh` is pasted into a heredoc that Nomad's HCL and consul-template both
  parse. A dollar sign followed by a brace, or a doubled brace, anywhere in it,
  comments included, is eaten before the shell sees it.

Changing the embedder changes every stored vector. The swap to
`granite-embedding-97m-r2` at 384 dimensions (`d2cf84d`) touched embark,
OpenViking's `dimension` and the config guard together. A future swap also
needs OpenViking's collection re-embedded and driftwatch's baseline reset, in
that order, per `docs/how-to/reseed-the-driftwatch-baseline.md`.

## The GPU, and how it silently goes missing

The image `ghcr.io/jasperhg90/embark-jetson` is not the one embark's release
workflow publishes. That one carries the CPU onnxruntime wheel.
`Dockerfile.embark` layers `onnxruntime-gpu==1.23.0` from NVIDIA's Jetson index
onto the portable image, plus embark's redis extra. It is built and pushed by
hand with the `justfile`, which reads the tag from the `embark_image` line in
`services.tf` and derives the base by stripping `-jetson` and a trailing
`-<n>` build revision. Why not embark's own `Dockerfile.jetson` is in the
service README.

`config.toml` asks for `CUDAExecutionProvider` only. That request checks that
the wheel carries the provider, not that a device is present. Measured on the
Jetson: without the GPU env vars, onnxruntime listed CUDA, failed
`cudaSetDevice` with error 35, fell back to CPU, and served correct results at
a tenth of the speed with `/healthz` green. Three things in `embark.hcl` put
the GPU in the container, and each is required:

1. `NVIDIA_VISIBLE_DEVICES` and `NVIDIA_DRIVER_CAPABILITIES`, which make
   nvidia-container-runtime inject `libcuda.so.1` and the device nodes.
2. Nine bind mounts of the host's CUDA 12.6 and cuDNN libraries, which the
   runtime does not inject.
3. `LD_LIBRARY_PATH=/usr/local/cuda/lib64`, which puts those mounts on the
   linker's path.

`security_opt = ["seccomp=unconfined", "label=disable"]` is also needed,
because seccomp blocks the Jetson GPU ioctls. The health check probes
`/healthz`, not `/readyz`: readiness waits for every model to warm, and a check
on it would kill the task mid-warm forever. TensorRT is deferred and untested
here, and its commented config waits in `config.toml`.

## Memory

The Orin Nano has 7619 MB of unified memory. There is no separate VRAM, so
every CUDA arena is charged to the task's cgroup, and running out shows as
`NvMapMemAllocInternalTagged ... error 12`. The task has `memory = 5632` and no
`memory_max`. Memory oversubscription is off at the Nomad server, so the client
sets the cgroup from `memory` alone. With `memory_max = 5120` the kernel showed
a 4096 MiB cap, measured through podman inspect. 5632 is the figure after
OpenViking's rerank calls started invoking the reranker, which had been loaded
but idle, so both sessions now hold CUDA arenas at once. 6144 would leave the
host about 460 MB, which moves the OOM onto the host. The next lever is
`rerank_batch_size` in `config.toml`, already halved to 4.

## Auth, metrics and the firewall

Auth ships on and embark refuses to start with no keys, so one `read` key
(`random_id.embark_api_key`) is rendered from `default/embark/auth` as an env
file. The same value is copied to `default/bifrost/embark` and
`default/driftwatch/embark`, because each consumer can read only its own
prefix.

`/metrics` is left unguarded (`EMBARK_AUTH__GUARD_METRICS = "false"`) so the
shared `consul_services` scrape can read it through the `prometheus` tag. The
guard's only other option was an `admin` key, which outranks `read` and would
also open the model routes. The ufw rule on port 8000 is what protects it: it
admits radxa (Bifrost and driftwatch), the Jetson itself (its Consul agent's
check) and `ubuntu` (Prometheus). Rules only add, so a wider rule for port 8000
outranks every narrow one. memex left exactly such a rule on this host and port
for a fortnight. Check `ufw status numbered` on the node before trusting the
list in `local.firewall_rules.embark`.

Spans go to the node-local Alloy at `127.0.0.1:4319`, and Alloy forwards them to
Tempo. See [the observability pipeline](/components/observability-pipeline.md).

## The Redis response cache

embark caches responses in Redis on radxa, keyed on a fingerprint of the served
model artifact. The credential is a dynamic user from Vault's Redis engine at
`redis/creds/cache-embark`, scoped to the `~embark:*` keyspace. Naming the
`redis-cache-embark` JWT role replaces `nomad-workloads` rather than adding to
it, so that policy is attached alongside in `machine_roles.tf`. The job id must
stay `embark`, since the role binds to it.

`max_ttl` is 720h. At 1h, each forced re-mint changed the rendered password,
and `change_mode = "restart"` restarted a GPU service with a roughly 25 second
model reload every hour: 17 restarts in 15 hours. The cost of 720h is that
dynamic users live only in Redis's memory, so a Redis restart wipes them while
Vault still holds valid leases. embark then logs "cache backend unavailable"
and serves uncached until someone runs `nomad job restart embark`.

## Invariants and what enforces them

| Must stay true | Enforced by |
|---|---|
| Pulled models equal served models | one `models.json` feeding both |
| `models.json` parses | `jsondecode` at plan time |
| The GPU is in use | nothing automatic. Grep `embark.stdout` for `Falling back to ['CPUExecutionProvider']` |
| Volume node equals job node | nothing, and a mismatch leaves the job unplaced |
| Image built equals image deployed | the `justfile` reading the `embark_image` line |
| Embedding dimension equals OpenViking's `dimension` | `scripts/check_openviking_config.py` asserts 384 on the OpenViking side only |

## History

The job landed undeployed in `da5e3d5` and moved onto the GPU behind Bifrost in
`db51630`, both 2026-09. The embedder went from embeddinggemma to granite at
384 dimensions in `d2cf84d`. The reranker went from mxbai (`022f79a`) to a QAT
build (`c5cba06`) to today's mMiniLM model, which arrived inside the unrelated
commit `bafb562`. The
memory and batch figures above came with OpenViking's rerank path in
`528ef7f` and `cb2854d`.

## Related

- [The container registry](/components/container-registry.md)
- [Redis cache](/components/redis.md)
- [Host volumes](/components/host-volumes.md)
- [The host firewall](/components/host-firewall.md)
