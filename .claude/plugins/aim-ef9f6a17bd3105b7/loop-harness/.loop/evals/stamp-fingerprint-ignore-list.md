eval: stamp-fingerprint-ignore-list

Definition of Done: generated and unrelated working-tree files stop
staling an otherwise-unchanged evidence stamp, without ever letting a
real code change commit ungated.

| Behavior | Input | Expected | Scorer | Threshold |
|----------|-------|----------|--------|-----------|
| A real source edit still stales the stamp when an ignore-list is set (guardrail) | `fingerprint_ignore: ["docs/assets/"]`; stamp, then edit `src/loop_harness/stamp.py` | `verify_stamp` returns `STALE` | Deterministic (`test_*`) | 100% |
| Generated-artifact churn no longer stales the stamp | Same config; stamp, then add `docs/assets/new.png` | `verify_stamp` returns `OK` | Deterministic (`test_*`) | 100% |
| Absent key preserves today's whole-tree behavior | No `fingerprint_ignore`; stamp, then add `docs/assets/new.png` | `verify_stamp` returns `STALE` | Deterministic (`test_*`) | 100% |
| Every caller fingerprints identically | Same config and tree; fingerprint via the commit-gate hook vs `verify_stamp` | Byte-identical fingerprint | Deterministic (`test_*`) | 100% |
| Malformed config fails loud, no green stamp (guardrail) | `fingerprint_ignore: "docs/"` (bare string), and a list with a non-string element | `load_config` raises `ConfigError` | Deterministic (`test_*`) | 100% |
| Mis-authored pattern under-ignores, never over-ignores (fail-safe) | `fingerprint_ignore: ["*.lock"]`; add `aim.lock.toml` (pathspec `*` does not cross `.`) | File still stales the stamp; the pattern does not match it | Deterministic (`test_*`) | 100% |
| Over-broad pattern that shadows real source is caught | An ignore pattern that matches a `src/**.py` file | Reviewer flags it; git pathspec semantics are documented so an operator cannot shadow source unknowingly | Human (adversarial review) | Must flag |
