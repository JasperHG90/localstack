---
type: decision
title: "ADR 0032: Summarize OpenViking content with inkling-2-small"
description: "OpenViking writes image and text summaries with ollama/inkling-2-small, thinking off, instead of gemini-3.5-flash-lite or gemma4:31b."
tags: [decision]
generated:
  by: process:kmctl/0.14.0
  at: 2026-11-23T21:34:55Z
status: stable
---

# ADR 0032: Summarize OpenViking content with inkling-2-small

## Context

OpenViking's `vlm` block writes every summary it stores: image descriptions,
per-file summaries, and each directory's `.overview.md` (L1) and
`.abstract.md` (L0). It ran on `gemini/gemini-3.5-flash-lite`, which billed
per token, ran out of quota, and may not be called for now. The operator
asked whether a cheaper Ollama Cloud model would hold up.

[The OpenViking summary model prototype](/prototypes/openviking-summary-model/README.md)
measured the candidates on real images and five real OpenViking directories,
with OpenViking's own prompts and a blind grader.

## Decision

`vlm.model` is `ollama/inkling-2-small`, with
`extra_request_body: {"reasoning_effort": "none"}` to turn thinking off.
OpenViking sends its own `reasoning_effort` only to OpenAI model names, and
Bifrost drops `think: false`, so that key is the one that reaches the model.

Rejected:

- `ollama/gemma4:31b`: about 15% faster on images and about 3.5 times cheaper
  in output tokens on text, but it misread identifiers in images and wrote
  thin summaries, under the prompt's 400-word floor in four of five
  directories. It lost to inkling in all five blind comparisons.
- Keeping `gemini/gemini-3.5-flash-lite`: out of quota, and its stored L0s
  graded last in all five directories.
- `inkling-2-mini`: Ollama Cloud does not serve it, and no node here can hold
  its 20 GB.

## Consequences

- Summaries go through the Ollama Cloud subscription, so their cost is the
  flat plan rather than per token. Inkling's longer output may press on that
  plan's usage limits. A burst of 50 calls hit none, but a full ingest runs
  far longer.
- If `extra_request_body` is dropped, ingest gets about five times slower
  with nothing reporting it. `scripts/check_openviking_config.py` does not
  assert the key.
- `gemma4:31b` stays in `VISION_MODELS` as the measured fallback.
- Existing summaries keep the flash-lite text until their directories are
  reindexed.

## Correction, 2026-11-24

`scripts/check_openviking_config.py` now asserts the key. `THINKING_MODELS`
lists `ollama/inkling-2-small`, and `failures()` reports a `vlm` block whose
model is in that set and whose `extra_request_body.reasoning_effort` is not
`"none"`. Dropping the key is now caught by that check, not found by a slow
ingest.
