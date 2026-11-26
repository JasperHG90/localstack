---
type: prototype
title: "OpenViking summary model"
description: "Benchmarks of inkling-2-small, gemma4:31b and the stored flash-lite summaries on real images and OpenViking documents, run 2026-11-23."
tags: [prototype]
generated:
  by: process:kmctl/0.14.0
  at: 2026-11-23T21:35:01Z
---

# OpenViking summary model

## Question

Which model reachable through Bifrost should OpenViking's `vlm` block use,
now that `gemini/gemini-3.5-flash-lite` is out of quota? The block writes
image descriptions and every text summary (per-file summaries, each
directory's `.overview.md` and `.abstract.md`), so both kinds were measured.

## Method

Every call went through Bifrost at `192.168.2.50:8080` with OpenViking's own
virtual key, using the prompts shipped in OpenViking 0.4.17.1 at
temperature 0.

- `probe.py`: which thinking switch reaches each model through Bifrost.
- `bench.py`, `ovbench.py`, `bench_ov.py`: eight real diagrams and
  screenshots from the operator's repositories. One call per image, then 50
  calls at 8 in parallel. `ovbench.py` uses the `vision.image_understanding`
  prompt and checks the reply parses as the JSON OpenViking expects.
- `fetch.py`: reads L2 (each file), L1 and L0 for five OpenViking
  directories (a blog post, two clip folders, a 26 KB project doc, a
  handoff).
- `gen.py`: rebuilds L1 and L0 from L2 with `semantic.document_summary`, then
  `semantic.overview_generation`, as OpenViking does.
- `blind.py`: shuffles the three versions per directory. A separate agent
  graded them against the source without the key.

Images and document content are private and git-ignored (`.gitignore`).
`ovbench.py`'s and `bench_ov.py`'s summary lines and the gemma `gen.py` run
were transcribed from the session output into the results files.

## Results

- `inkling-2-mini` is not served by Ollama Cloud: `/api/chat` returns 404.
  `inkling-2-small` is.
- Thinking: `reasoning_effort: "none"` turns it off for both models. Bifrost
  drops `think: false`. With thinking on, `inkling-2-small` ran 22 images a
  minute against 46 with it off, and once spent its 4000-token budget
  without answering (`results-image-raw.txt`).
- Images (`results-image-ov-prompt.txt`): both models returned valid JSON
  8/8. Under load, inkling did 111 images a minute and gemma 131, with no
  errors from either. Gemma misread a GCP project (`neurips-lm-eff`) and an
  MLflow run ID; inkling read both exactly. Gemma reports about 330 input
  tokens per image whatever its size, inkling 400 to 3300.
- Text (`results-summary-gen.txt`, `results-blind-grading.txt`): inkling won
  all five directories, gemma came second in all five, flash-lite last.
  Gemma's L1 fell under the prompt's 400-word floor four times out of five.
  Every stored flash-lite L0 was 15 to 35 words of hedging. Inkling took
  64 s and 12,242 output tokens for 13 calls, gemma 18 s and 4,419.

## Conclusion

Use `ollama/inkling-2-small` with thinking off. It reads identifiers exactly
and keeps the names and numbers search depends on. It costs about 3.5 times
gemma's output tokens on text, which may count against the Ollama Cloud
quota. `gemma4:31b` is the fallback. ADR 0032 records the choice.
