---
type: practice
title: Measure a vision model before OpenViking uses it
description: Being in Bifrost's catalog does not mean a model accepts an image, and OpenViking hides the failure behind a normal-looking summary. Measure a model before adding it to VISION_MODELS.
tags: [openviking, bifrost, vlm, ollama, silent-failure]
status: stable
generated:
  by: claude-opus/5.5
  at: 2026-09-26
stale_after: 6m
sources:
  - id: check-openviking-config
    resource: scripts/check_openviking_config.py
  - id: ov-conf
    resource: deployments/applications/services/openviking/ov.conf.json
---

# Measure a vision model before OpenViking uses it

Image summaries route through Bifrost. The `vlm` block in
`deployments/applications/services/openviking/ov.conf.json` names
`gemini/gemini-3.5-flash-lite`, picked in commit `66bed3c` (2026-09-11).
Before that it was `ollama/glm-5.3-flash`.

Being in Bifrost's catalog is not enough. Of the ollama models tried, only
`glm-5.3-flash` of the GLM line accepted an image. Plain `glm-5.3`,
`glm-5.2`, `glm-5.1` and both `deepseek-v4` variants are cataloged and answer
text, but refuse an image with `this model does not support image input`.
`gemma4:31b`, `kimi-k3`, `minimax-m3` and `qwen3.5:397b` also work.
`gemini/gemini-3.5-flash-lite` was measured on 2026-09-12: a 64x64 red PNG
sent to `/v1/chat/completions` came back as "Red".

Picking a blind model is not a loud failure, which is why
`scripts/check_openviking_config.py` pins the list as `VISION_MODELS` and fails
when `vlm.model` is not in it. That check caught its own gap: `66bed3c`
switched `ov.conf.json` to the Gemini model without adding it to the set, and
the check stayed red until the model was measured and added. OpenViking
catches the error and returns a normal-looking summary:

```python
except Exception as e:
    logger.error(...)
    return {"name": file_name, "summary": "Image summary generation failed"}
```

That string is then embedded as the image's content. The ingest reports
success, every image gets the same vector, and they become each other's
nearest neighbors in the collection. Measure a model before adding it to
`VISION_MODELS`, by POSTing an image to Bifrost and reading the answer back.
