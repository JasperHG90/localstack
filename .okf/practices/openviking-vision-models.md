---
type: practice
title: Measure a vision model before OpenViking uses it
description: Being in Bifrost's catalog does not mean a model accepts an image, and OpenViking hides the failure behind a normal-looking summary. Measure a model before adding it to VISION_MODELS.
tags: [openviking, bifrost, vlm, ollama, silent-failure]
status: stable
generated:
  by: claude-opus/5.5
  at: 2026-09-26
sources:
  - id: openviking
    resource: git:3ec5d1e:docs/openviking.md
    last_modified: 2026-09-12
---

# Measure a vision model before OpenViking uses it

Image summaries route through Bifrost to ollama, as recorded in
`docs/reference/openviking.md`.

Being in Bifrost's catalog is not enough. Of the models tried, only
`glm-5.3-flash` accepted an image; plain `glm-5.3`, `glm-5.2`, `glm-5.1` and
both `deepseek-v4` variants are cataloged, answer text, and refuse an image
with `this model does not support image input`. `gemma4:31b`, `kimi-k3`,
`minimax-m3` and `qwen3.5:397b` also work.

Picking a blind model is not a loud failure, which is why
`scripts/check_openviking_config.py` pins the list. OpenViking catches the
error and returns a normal-looking summary:

```python
except Exception as e:
    logger.error(...)
    return {"name": file_name, "summary": "Image summary generation failed"}
```

That string is then embedded as the image's content. The ingest reports
success, every image gets the same vector, and they become each other's
nearest neighbors in the collection. Measure a model before adding it to
`VISION_MODELS`, by POSTing an image to Bifrost and reading the answer back.
