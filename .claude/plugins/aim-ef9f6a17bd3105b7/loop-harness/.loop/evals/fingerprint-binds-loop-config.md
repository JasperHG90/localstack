eval: fingerprint-binds-loop-config

Definition of Done: a change to the verification contract in
`.loop/config.json` stales a green stamp and forces a re-stamp plus
re-review, while churny loop state never stales it and a missing config
stays safe.

| Behavior | Input | Expected | Scorer | Threshold |
|----------|-------|----------|--------|-----------|
| Weakening a gate stales the stamp | Real gates in `.loop/config.json`; `write_stamp` green; then append `\|\| true` to a gate command | `verify_stamp` returns `STALE` | Deterministic (`test_*`) | 100% |
| `fingerprint_ignore` cannot exclude config (guardrail) | `fingerprint_ignore: [".loop/config.json"]` (and a parametrized `".loop/"`); stamp green; edit a gate in config | Fingerprint still changes; `verify_stamp` returns `STALE` | Deterministic (`test_*`) | 100% |
| Churny loop state still never stales (guardrail) | After a green stamp, write `.loop/ledger.json`, `.loop/stamp.json`, `.loop/HALT`, and a new `.loop/history/x.jsonl` and `.loop/reflections/x.md` | `verify_stamp` stays `OK` | Deterministic (`test_*`) | 100% |
| Missing config preserves today's behavior (fail-safe) | No `.loop/config.json`; stamp, then make a non-`.loop` source edit | `verify_stamp` returns `STALE`; no crash in `tree_fingerprint`/`write-tree` | Deterministic (`test_*`) | 100% |
| Unchanged config does not falsely stale | Green stamp; no config edit; re-verify | `verify_stamp` returns `OK` | Deterministic (`test_*`) | 100% |
| Every caller fingerprints identically | Same tree and config; fingerprint via `write_stamp` vs `verify_stamp` vs the commit-gate hook | Byte-identical fingerprint | Deterministic (`test_*`) | 100% |
| A weakening config edit is caught at re-review (guardrail) | The re-stamp's diff shows a real gate replaced by `true` | The architectural/adversarial reviewer flags the weakened gate rather than accepting it | Human (review pass) | Must flag |
