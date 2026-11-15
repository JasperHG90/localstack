---
type: eval
title: 'Eval: okf-design-spikes'
description: 'Definition of done for okf-design-spikes: 6 row(s).'
tags:
- eval
generated:
  by: process:loopctl/2.2.2.dev1+gd84319696
  at: '2026-11-15T20:08:04+00:00'
slug: okf-design-spikes
signoff:
  signer: delegated:jasperginn@gmail.com/claude-opus-5-5
  hash: 2d9b0341e1c04cfd86cd3936f4441b48a8d15f798a712dcc9c35a2813510331a
  at: '2026-11-15T20:08:04+00:00'
verified: null
---

Rows: rows.json; the fields each row takes: loopctl schema eval-rows.

- r1: nats-results.txt, written by nats.sh, holds the JetStream messages from the filer, including an ov-sync a.md create and a.md delete
  Fails when: the results file is missing, or holds no message naming a.md, or fewer than two such messages
- r2: webhook-results.txt holds three labelled variants: default args delivers ov-sync events with the bearer header; production args with an off-container listener delivers nothing and logs the dial error; production args with a same-namespace listener delivers ov-sync events with the bearer header; no variant delivers a loki event
  Fails when: a variant label is missing, the default or same-namespace variant shows no ov-sync event or no bearer header, the off-container variant shows a delivered event or no dial error, or any variant shows a loki event
- r3: decide.sh keyed refuses to run without its key env var, and decide.sh rejects an unknown case
  Fails when: decide.sh keyed with the env var unset exits 0 or sends a request, or an unknown case exits 0
- r4 (judgment): each SeaweedFS script reruns cleanly from a clean Docker host: it writes its results file with the recorded outcomes and leaves no container or network behind
  Fails when: a rerun by the reviewer fails, gives results that disagree with the README, or leaves a container or network running
- r5 (judgment): the clef-via-bifrost README and results.txt record the 400 (bare-strings), 401 (no-key) and 403 model_blocked (keyed, Hermes key) outcomes, each tied to the decide.sh case that produces it
  Fails when: an outcome is missing, or is not tied to a decide.sh case
- r6: the knowledge bundle stays valid with the new prototypes section, its index, log lines and summary update or ack
  Fails when: kmctl check reports an error
