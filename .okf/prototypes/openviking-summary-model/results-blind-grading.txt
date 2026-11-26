# Blind grading, 2026-11-23

A separate agent graded blind/caseN/{A,B,C}.md against SOURCE.md without the
key. Scores 1-5: faithfulness / coverage / L0 retrieval value / format.
Models filled in afterwards from blind_key.json.

| Case | inkling-2-small | gemma4:31b | flash-lite (stored) | Winner |
|---|---|---|---|---|
| 1 CVD timelines blog | 4/5/3/4 | 5/3/3/3 | 5/3/1/1 | inkling |
| 2 Bamba clips, 3 files | 5/5/5/4 | 4/3/4/5 | 3/2/1/1 | inkling |
| 3 Slate clips, 2 files | 5/5/5/5 | 4/3/3/4 | 5/2/1/1 | inkling |
| 4 DLX project doc | 4/3/4/4 | 5/2/3/3 | 5/2/1/1 | inkling |
| 5 Tado handoff | 4/5/5/5 | 5/3/5/4 | 5/2/1/2 | inkling |

Errors the grader quoted:
- inkling: overstated Xebia's role (case 4), reversed the firewall rule's
  traffic direction in L0 (case 5), called one new scope item unchanged
  (case 1).
- gemma: "installing the necessary package" for a pip comment (case 2); never
  names Slate (case 3).
- flash-lite: "a slight drop" for GSM8K 49.96 to 36.77 and an unstated
  "maintaining strong retrieval" (case 2). Every L0 was 15-35 words, under
  the prompt's 50-word floor.

The stored flash-lite versions came from the live ingest, which may have fed
the model different context (their "sampled" wording suggests so), so that
column is not a strict like-for-like comparison.
