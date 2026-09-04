# embark deployment files

What each file here is, and the one thing this repo cannot do for you.

| File | Role |
|---|---|
| `models.json` | Served name to ModelKit reference. The single source of truth for which models exist. |
| `config.toml` | embark's settings. Rendered into the job and named by `EMBARK_CONFIG_FILE`. |
| `pull.sh` | Prestart script: unpacks each ModelKit from the cluster registry. |
| `Dockerfile.embark` | The Jetson image: the published portable image plus the GPU wheel. |
| `justfile` | Builds and pushes that image. |

## You build and push the Jetson image

**The image this job runs is not built by CI. Building and pushing it is an
operator step.**

`config.toml` asks for `CUDAExecutionProvider`. Point the job at the portable
image embark's release workflow publishes, which carries the CPU onnxruntime
wheel, and the provider is not there to load.

**Naming a provider does not guarantee you get it.** embark checks that a
requested provider is *available*, which is a check on the wheel, not on the
device. Deploying this job without the GPU env vars below produced exactly
that: onnxruntime listed `CUDAExecutionProvider`, failed `cudaSetDevice` with
CUDA error 35, fell back to CPU, and served correct embeddings at a tenth of
the speed with `/healthz` green the whole time. Verify the GPU after any
change to the image or the jobspec; do not infer it from a healthy job.

`Dockerfile.embark` builds that image, and the `justfile` beside it drives the
build:

```console
$ just show      # which tags this would act on
$ just build     # portable image + the GPU wheel
$ just verify    # does the wheel import, and which providers does it carry
$ just push      # to ghcr.io
$ just release   # build and push
```

Both tags come from the single `embark_image` line in
`deployments/applications/services.tf`, so what gets built and what Terraform
deploys cannot drift. Change the version there, not here.

A trailing `-<number>` on the Jetson tag is a build revision of the base, not
an upstream version: `v0.1.0-1` means "base `v0.1.0` plus the layers here".
The justfile strips it to find the base, so bump it whenever this directory
changes without the base moving.

Nodes already authenticate to `ghcr.io` via
`bootstrap/playbooks/configure_podman.yml`, so no per-job pull credential is
needed.

### How the GPU reaches the container

Three things in `services/embark.hcl`, and the job serves from CPU if any one
is missing:

| What | Supplies |
|---|---|
| `NVIDIA_VISIBLE_DEVICES=all`, `NVIDIA_DRIVER_CAPABILITIES=compute,utility` | `libcuda.so.1` and `/dev/nvhost-*`, injected by nvidia-container-runtime |
| nine `volumes` bind mounts | the CUDA toolkit and cuDNN, which the runtime does not inject |
| `LD_LIBRARY_PATH=/usr/local/cuda/lib64` | puts those mounts on the linker's search path |

The first two were measured on `jetson-orin-nano`: without them the container
has no `libcuda.so.1` and no device nodes. `memex.hcl` carries the same three,
which is where they came from.

To check a running job, look for `Falling back to ['CPUExecutionProvider']` in
`embark.stdout` on the node. Absent, and with `Memcpy nodes are added ... for
CUDAExecutionProvider` present, the model is on the GPU.

### Why not embark's own Dockerfile.jetson

That one starts from `nvcr.io/nvidia/l4t-jetpack`, which needs NGC access and
a multi-gigabyte pull, and embark's release workflow does not build it for
exactly that reason. `Dockerfile.embark` takes memex's route instead
(`docker/memex/Dockerfile.jetson`): layer `onnxruntime-gpu` onto the ordinary
image with `pip install --no-deps`. That reduces the build to a single wheel
swap an ordinary arm64 builder can produce, emulated or native.

TensorRT is the open question. embark's deployment notes give a reason for the
heavier base: the TensorRT execution provider loads TensorRT *from the image*,
and a base without it falls short. The host carries TensorRT 10.3 and the
wheel reports the provider, but the pair has not been run here, so
`config.toml` requests CUDA alone. If enabling it fails at startup, that
assumption is what broke, and the l4t-jetpack base is the fallback.

## Adding or changing a model

Edit `models.json`. One entry per served name:

```json
{
  "embedding": "embeddinggemma-q8:latest",
  "reranker": "mmarco-minilm:v1"
}
```

The value is a reference inside the cluster registry, and `services.tf`
prefixes the registry host. That one file drives both what `pull.sh` fetches
and what embark is told to serve, so the two cannot drift.

**Pin a digest rather than a moving tag.** embark's own documentation calls an
unpinned model reference "the single most load-bearing rule in the
configuration": when a tag moves, every vector the model produces changes,
embeddings stored last week stop matching ones computed today, retrieval
quality drops, and nothing errors. `:latest` above is a placeholder, not a
recommendation.

A model is re-pulled only when its reference changes. `pull.sh` records what it
fetched in `.ref` beside the artifact and skips the download when that still
matches, so a restart does not re-fetch hundreds of megabytes already on the
volume.

## Editing pull.sh

It is injected into a Nomad jobspec heredoc, which is parsed by Nomad's HCL
first and consul-template second. Neither a dollar sign followed by a brace nor
a doubled brace may appear anywhere in the file, comments included. Both are
template actions to those parsers. Plain `$name` and `$(command)` are fine.
