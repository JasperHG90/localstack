eval: <slug>

<one-line Definition of Done: the single outcome this ticket must produce>

| Behavior | Input | Expected | Scorer | Threshold |
|----------|-------|----------|--------|-----------|
| <observable behavior in the user's frame> | <a concrete input: actual string, file, or situation> | <what good looks like, as structural requirements> | <deterministic check / model + rubric / human + rubric> | <the pass bar: 100%, an N/5 score, a % of cases, or a baseline to beat> |
| <guardrail: a behavior the system must refuse or an invariant it must not weaken> | <the input that would tempt the violation> | <the refusal or the preserved invariant> | <deterministic check> | 100% |

<!--
Copy this file to .loop/evals/<slug>.md, replace <slug> in the header
with the ticket slug, fill the Definition of Done, and write one row per
scenario. Delete these comments and the angle-bracket placeholders.

Worked example (from the falkster five-row template, a customer-call
agent):

| Behavior | Input | Expected | Scorer | Threshold |
|----------|-------|----------|--------|-----------|
| Agent returns a structured opportunity for high-signal input | Three tagged segments from a tier-1 account | Output names the segment, includes a baseline metric, and names a hypothesis | Human PM, 1-5 rubric | 4/5 on 90% of high-signal cases |
| Agent flags low-confidence input | A tagged segment with conflicting sentiment | Output includes a "low confidence" flag explaining the conflict | Deterministic (string match) | 100% |

Validate the shape with `loopctl eval <slug>` once written.
-->
