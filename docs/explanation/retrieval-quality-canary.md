# The retrieval-quality canary

driftwatch is a daily canary that runs a fixed set of questions through the
embedding and rerank models. What it reports is in
[Retrieval quality](../reference/retrieval-quality.md). This page is why it is
built the way it is, and where it stops.

## Why driftwatch dials embark directly

Bifrost drops `input_type`, and that field picks the model's query prefix over
its document prefix. A bi-encoder embedded with the wrong one retrieves worse
and reports nothing.

The gateway path is still measured, from the other side:
`openviking_embedding_call_duration_seconds` is the same models through
Bifrost, so the gap between the two dashboards is what the gateway costs.

## What a canary cannot tell you

It ranks a fixed corpus that always contains the answer, so it cannot see a
live query finding nothing. That is what the zero-result panels on
`/d/localstack-openviking` are for, and they measure the corpus rather than
the model.

But a zero result is frequently the right answer. Nobody ingested anything
that answers the question, and retrieval correctly said so. Nothing in
Prometheus can tell that apart from retrieval failing to surface something
that is there, so `OpenVikingZeroResults` watches the change against the
trailing fortnight rather than any absolute level.

`OpenVikingNoCandidates` is the half that is unambiguous.
`openviking_vector_scanned_total` counts what each descent step handed back,
so a populated store returns candidates that then score badly, while an empty
or wrongly-scoped one returns none. Under one candidate per retrieval is not a
content gap, it is searching the wrong place. The likeliest cause here is
account scoping: an `ov_account` that was never created answers 200 over an
empty tree.

Neither can tell you that content was deleted, because no metric here records
an ingest. A canary that stays green while zero results climb narrows it to
the corpus, and the funnel narrows it again, but the last step is looking.
