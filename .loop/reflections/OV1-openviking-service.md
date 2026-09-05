---
slug: OV1-openviking-service
blockers: []
friction: [prek-first-pass-rewrite, other:fix-introduced-new-defect, other:readme-vs-tag-drift, other:deployment-blocked-by-permission]
worked: [mutation-tested-review, planted-failure-proves-guard, measured-not-inferred]
cycles: 3
gates_red: 0
harness_change: every review dispatch this session omitted the scope digest, so all eight verdicts fell back to whole-tree binding; the fan-out briefing should carry it or say plainly that it is optional.
---

## What worked

**The reviewers broke things rather than reading them, and that is what caught
the real defects.** Three findings would have shipped under a reading-based
review. The image could not have been built at all (a git URL fragment valid
for `main` but not for the pinned tag). A proxy setting I believed forwarded
the ID token actually returns it to the browser. And a runbook check sent no
token while printing the exact result it promised. Each was settled by running
something: `uv pip install --dry-run` both ways, upstream's own flag
documentation, and a header-echo server behind a shim reproducing ssh's argv
join.

**Planting the failure is the only way to prove a guard.** R13 needs two edits
that each look sufficient alone: the jobspec in `JOBSPECS` and the filename in
the hook's `files:` pattern. Reading either one passes. Planting a skip-auth
key in the new jobspec and watching the guard exit 1, then removing it and
watching it exit 0, is what shows both landed.

**The checker caught a bug in itself before any reviewer saw it.** An unscoped
`_value(text, "backend")` read `agfs.backend` rather than the vectordb one, so
it would have approved any vector backend. The self-test passed while the real
run failed, because the fixture had one `backend` key where the real file has
two. Rebuilding the fixture to mirror the real nesting gave it a positive
control, verified by reverting the scoping and watching the self-test fail.

## What worked less well

**`other:fix-introduced-new-defect`, three times, and this is the lesson.** The
`/ready` fix introduced the ssh quoting bug. Removing `SET_AUTHORIZATION_HEADER`
stranded a sentence saying "the two settings". Fixing DOC-17 corrected one of
two twin comments. A fix is a change, and changes need the same scrutiny as the
code they correct; treating them as free is what cost this ticket two review
cycles. The reviewers found each one because I asked them to hunt for that
pattern specifically after the second occurrence.

**`other:readme-vs-tag-drift`.** The `ov-postgres` README documents the
monorepo install form, correct for `main` and wrong for every existing tag,
because the repository restructured after `ov-postgres-v0.2.0` was cut. The
plan's own P12 predicted the failing line verbatim and I still wrote it: I read
the README instead of the tag. When a pin and its documentation disagree, the
pin is the artifact.

**A credential invented and defended with a false claim.** I added a
`root_api_key` justified by "OpenViking refuses to start bound to a non-loopback
host without one." That guard lives in `DevAuthPlugin` and is unreachable under
`auth_mode: "oidc"`. Two resources outside the declared surface minted a live,
unused root credential, which is exactly the "reads as live, grants nothing"
shape Q1 exists to prevent. The prose that justified it is what should have
raised the alarm: the loop's own rule says a rationale in source is the sentence
most likely to be false.

**`other:deployment-blocked-by-permission`.** Nothing is deployed. The image is
not built and no apply has run, so every runtime eval row is unscored and R15's
runtime half stands as a labelled proxy. The code is complete and reviewed; the
service does not exist.

## Notes for the next ticket

Three paths sit outside section 7: `storage.tf`, `docs/haproxy_reverse_proxy.md`
and `docs/workload-identity.md`. All three are prose this diff falsified, and
the adversarial pass ruled the scope acceptable under
`.claude/rules/minimal-comments.md`'s "leave them be unless your change makes
them wrong". Section 7's docs bullet under-listed rather than the diff
over-reaching; a future plan touching a service's edge should name the route
table and the keyless doc up front.

Open advisories, none blocking: `openviking_base_image` is an unreferenced
templatefile variable (the justfile greps the line, so the pin works);
`/api/v1/collections` has no producer in this repo; `secrets.tf:260` still
counts "the two proxies" where nothing it says became false.
