# embark deployment files

What each file here is, and the one thing this repo cannot do for you.

| File | Role |
|---|---|
| `models.json` | Served name to ModelKit reference. The single source of truth for which models exist. |
| `config.toml` | embark's settings. Rendered into the job and named by `EMBARK_CONFIG_FILE`. |
| `pull.sh` | Prestart script: unpacks each ModelKit from the cluster registry. |

## You build and push the Jetson image

**The image this job runs is not built by CI, and nothing in this repo builds
it. Building and pushing it is an operator step.**

embark's release workflow builds `Dockerfile`, the portable image, for amd64
and arm64. It does not build `Dockerfile.jetson`, whose base is
`nvcr.io/nvidia/l4t-jetpack` and which carries `onnxruntime-gpu` from the
Jetson AI Lab index rather than the CPU wheel from the lock.

That matters here because `config.toml` asks for `TensorrtExecutionProvider`
and `CUDAExecutionProvider`, and **embark refuses to start when a requested
provider is missing.** Point this job at the portable image and it will not
run. That refusal is deliberate on embark's part: onnxruntime otherwise falls
through to CPU silently, and a Jetson serving from CPU at a tenth of the speed
reports itself healthy with nothing in the log.

Build it on the device and push it to `ghcr.io`, following the naming memex
already uses (`ghcr.io/jasperhg90/memex-jetson`):

```console
$ docker build -t ghcr.io/jasperhg90/embark-jetson:<version> -f Dockerfile.jetson .
$ docker push ghcr.io/jasperhg90/embark-jetson:<version>
```

Then set that tag as `embark_image` in
`deployments/applications/services.tf`. Nodes already authenticate to
`ghcr.io` via `bootstrap/playbooks/configure_podman.yml`, so no per-job pull
credential is needed.

Worth knowing: memex's own `docker/memex/Dockerfile.jetson` takes a different
route and CI *can* build it. That one layers `onnxruntime-gpu` onto the
ordinary memex image with `pip install --no-deps` and lets
`nvidia-container-runtime` inject CUDA at runtime, so it needs no CUDA base
image. If embark adopted that shape its Jetson image could be built in CI
too, and this manual step would go away. That is a change to the embark
repository, not to this one.

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
