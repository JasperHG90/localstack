---
type: plan
title: 'Plan: okf-design-spikes'
description: Re-create three lost design spikes (SeaweedFS filer to NATS, SeaweedFS webhook, clef through Bifrost) as rerunnable OKF prototypes.
tags:
- plan
generated:
  by: process:loopctl/2.2.2.dev1+gd84319696
  at: '2026-11-15T19:47:53+00:00'
slug: okf-design-spikes
epic: null
depends_on: []
priority: null
---

# okf-design-spikes

<!-- This template was registered in planning. To capture an idea as a stub
instead (intent for later, promoted by the operator), write the plan with
`status: draft` in its front matter before running loopctl ticket register.
A hand-written plan's front matter needs type: plan, title, description and
slug; loopctl ticket register fills in generated. Optional: epic, depends_on,
priority, status, strictness and blocking. -->

Relayed from: none
<!-- When this ticket carries a finding raised while building another ticket,
replace "none" with that ticket's slug and the finding, in one line (ADR 0001). -->

## Intent

Re-create, as rerunnable OKF prototypes, three spikes from the session
recorded in the handoff `bifrost-decision-models-ci-lab-auth-and-openviking-doc-sync-design`
("Where it stands"), whose scripts sat in a scratch folder that is gone. This
follows the `prototypes-hold-their-scripts` constraint in
`.claude/rules/docs-layout.md` and the prototype shape in
`.claude/rules/okf-bundle.md`. No product code changes.

Two prototypes, each made with `kmctl new prototype` (the first creates the
section and the `.okf/prototypes/` index):

- `new:.okf/prototypes/seaweedfs-filer-notifications/README.md`: compares
  the two SeaweedFS filer notification paths, one script and one raw results
  file per run.
  - `new:.okf/prototypes/seaweedfs-filer-notifications/nats.sh`: on a
    throwaway Docker network, starts nats:2.11-alpine -js,
    chrislusf/seaweedfs:4.48_full with `[notification.gocdk_pub_sub]
    topic_url = "nats://seaweedfs.filer.events"` and
    `NATS_SERVER_URL=nats://nats:4222`, creates stream `SWFS` on
    `seaweedfs.filer.events` with natsio/nats-box:0.17.0, runs
    amazon/aws-cli:2.27.0 against `http://swfull:8333` (mb `ov-sync`, cp
    `a.md` to ov-sync/JasperHG90/localstack/docs/a.md, rm), writes the
    stream's messages to
    `new:.okf/prototypes/seaweedfs-filer-notifications/nats-results.txt`,
    and removes containers and network on exit.
  - `new:.okf/prototypes/seaweedfs-filer-notifications/webhook.sh`: same
    shape with standard chrislusf/seaweedfs:4.48, `[notification.webhook]`
    endpoint `http://hook:9000/events`, `bearer_token = "spike-token"`,
    `path_prefixes = ["/buckets/ov-sync/"]`, and a small python:3.12-alpine
    HTTP server that logs the Authorization header and body; writes to both
    a `loki` and the `ov-sync` bucket; output to
    `new:.okf/prototypes/seaweedfs-filer-notifications/webhook-results.txt`.
    It runs three variants in one go, each labelled in the results file:
    default args with the listener in another container (delivers);
    the production job's args from
    `deployments/infrastructure/services/seaweedfs.hcl`, `-ip=127.0.0.1`
    included, with the listener in another container (delivers nothing,
    `dial tcp 127.0.0.1:0->...: connect: invalid argument`); and the
    production args with the listener on loopback in the SeaweedFS
    container's network namespace (delivers). The README says the webhook
    reaches only a listener sharing that namespace under the production
    args, and cites spike:ov-sync-consumer/4 and spike:ov-sync-consumer/5.
  - The README also records the two findings that need no run: the standard
    `4.48` image lacks the `gocdk` build tag, and gocloud `natspubsub` v0.46
    is core NATS, not JetStream.
- `new:.okf/prototypes/clef-via-bifrost/README.md` and
  `new:.okf/prototypes/clef-via-bifrost/decide.sh`: `POST
  https://bifrost.lab.orangecluster.nl/v1/decisions` with the
  `ollama/clef:cloud` `tier` choice body. It takes a case argument so every
  recorded outcome has a script that produces it: `bare-strings` sends the
  choices as bare strings (400 "Invalid request payload"), `no-key` sends
  no `x-bf-vk` header (401 `virtual_key_required`, with provider ollama and
  request_type decisions resolved), and `keyed` sends the object-choice body
  with `x-bf-vk` read from an env var, refusing to run without it (403
  `model_blocked` on the Hermes key). The operator runs it and appends each
  response to `new:.okf/prototypes/clef-via-bifrost/results.txt`; the README
  records the three outcomes already seen as those raw results.

`.okf/summary.md` is updated or acked and `.okf/log.md` gets the lines the
bundle rule asks for.

Outcome: running each SeaweedFS script reproduces the recorded results into
its folder (NATS: about 10 messages, `.system` paths plus `a.md` create and
delete as gocloud envelopes around protobuf; webhook: nothing for `loki`
in any variant, `ov-sync` create, update and delete as JSON with the bearer
header in the default and same-namespace variants, nothing delivered in the
production-args off-container variant), `decide.sh bare-strings` and
`decide.sh no-key` reproduce the 400 and 401 without a key, and
`kmctl check` passes.

## Could invalidate this plan

- none
