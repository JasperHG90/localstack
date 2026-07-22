# The eval is the spec

The Definition of Done for an AI feature is not a paragraph of prose. It
is an eval: a set of concrete input/output scenarios, each scored
against a rubric, that together define what good looks like. The eval is
the contract, the changelog, and the definition of done. It is written
before the code and it survives every refactor, because it binds to
intent rather than to a tree.

This reference condenses two sources and adapts them to the loop
harness, where the eval gates one ticket into implementation:

- falkster, *The eval is the spec* (handbook)
- falkster, *The five-row eval template* (blog)

## Why an eval, not a PRD

A product requirements document is a single opinion, written once,
verified never. It was a coping mechanism for when the author could not
test the feature themselves. An eval replaces it with something
concrete and repeatable: instead of debating whether a change is good,
you read the eval scores by scenario, the diff since last week, and the
regressions. The judgment moves from argument to measurement.

In the harness this is sharper still. The eval is authored before the
implementer starts, so it is the spec the implementer builds toward and
the acceptance layer the reviewer judges against, not a document that
drifts from the code the moment either changes.

## The five columns

Each scenario is one row with five columns. The first three say what to
test; the last two say how it is judged, which is what turns a wish into
a check.

1. **Behavior**: the observable thing the system does, in the user's
   frame. "Flags a low-confidence input", not "returns
   `confidence < 0.5`". Describe the action a user would notice.
2. **Input**: a specific, concrete test case: an actual string, file,
   or situation. Never an abstract category. "An empty config file"
   beats "missing configuration". Concreteness is what lets someone
   else run the row.
3. **Expected**: what good looks like for this input, stated as
   structural requirements rather than one fixed output. List the
   properties the output must have ("names the segment, includes a
   baseline metric, names a hypothesis") so a range of correct answers
   can pass while wrong ones fail.
4. **Scorer**: who or what judges the output. Three kinds:
   - a deterministic check (string or value match, an assertion) for
     rows with one right answer;
   - a different model applying a rubric, for rows where correctness is
     structural but not exact;
   - a human applying a rubric, for taste, tone, or emotional
     resonance the other two miss.
   Naming a human scorer is how the eval covers what automation cannot,
   without abandoning the eval.
5. **Threshold**: the pass bar. A hard 100% for a guardrail, a numeric
   rubric score (4/5), a percentage of cases (90% of high-signal
   inputs), or a baseline the new version must beat. Without a
   threshold, "good enough" is never settled.

## Building the set

The construction process, scaled to a single ticket:

1. **Gather real inputs.** Draw the Input column from actual cases the
   feature will face, not invented ones.
2. **Label the desired output.** Write the Expected column as the
   properties of a good answer.
3. **Include failure modes.** Add adversarial and guardrail rows: the
   inputs designed to trip the feature, and the invariants it must not
   weaken. Roughly one in five rows should be one of these.
4. **Score per slice.** Pick the Scorer that fits each row; do not force
   one method across all of them. Guardrails get a deterministic scorer
   at a 100% threshold.
5. **Run it.** In the harness, the marker is checked for shape by
   `loopctl eval <slug>` and gates pickup when `require_eval` is set.
   The larger practice runs the full set daily in CI; a ticket eval is
   the small, pre-implementation seed of that set.

Production eval sets run from 30 to 200 pairs. A per-feature set is 20
to 30 cases and a few hours to draft. A ticket eval in this harness is
smaller again: about 5 rows for a narrow change, 10 to 15 when the
behavior is wide, because its job is to pin one ticket's Definition of
Done, not to benchmark a whole product.

## Worked example

Two rows from a 24-row eval for an agent that analyzes customer calls:

| Behavior | Input | Expected | Scorer | Threshold |
|----------|-------|----------|--------|-----------|
| Agent returns a structured opportunity for high-signal input | Three tagged segments from a tier-1 account | Output names the segment, includes a baseline metric, and names a hypothesis | Human PM, 1-5 rubric | 4/5 on 90% of high-signal cases |
| Agent flags low-confidence input | A tagged segment with conflicting sentiment | Output includes a "low confidence" flag explaining the conflict | Deterministic (string match) | 100% |

The first row is judged by a human on a rubric because "a good
opportunity" is a matter of structure and taste. The second is a
guardrail with one right answer, so it is deterministic at 100%. Same
template, different scorers and thresholds, chosen to fit the row.
