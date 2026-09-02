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

`config.toml` asks for `TensorrtExecutionProvider` and
`CUDAExecutionProvider`, and **embark refuses to start when a requested
provider is missing.** Point the job at the portable image embark's release
workflow publishes, which carries the CPU onnxruntime wheel, and it will not
run. That refusal is deliberate on embark's part: onnxruntime otherwise falls
through to CPU silently, and a Jetson serving from CPU at a tenth of the speed
reports itself healthy with nothing in the log.

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

Nodes already authenticate to `ghcr.io` via
`bootstrap/playbooks/configure_podman.yml`, so no per-job pull credential is
needed.

### Why not embark's own Dockerfile.jetson

That one starts from `nvcr.io/nvidia/l4t-jetpack`, which needs NGC access and
a multi-gigabyte pull, and embark's release workflow does not build it for
exactly that reason. `Dockerfile.embark` takes memex's route instead
(`docker/memex/Dockerfile.jetson`): layer `onnxruntime-gpu` onto the ordinary
image with `pip install --no-deps` and let `nvidia-container-runtime` inject
CUDA at runtime. That reduces the build to a single wheel swap an ordinary
arm64 builder can produce, emulated or native.

One caveat worth testing on the hardware before trusting it. embark's own
deployment notes give a reason for the heavier base: the TensorRT execution
provider loads TensorRT *from the image*, and a base without it falls short.
The memex route assumes the container runtime supplies TensorRT along with
CUDA. If `just verify` shows the providers but the Jetson refuses them at
startup, that assumption is the thing that broke, and the l4t-jetpack base is
the fallback.

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
