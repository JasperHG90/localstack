eval: D9-cli-service-one-row-per-job

**Definition of Done:** `localstack service` renders a job's routes adjacently
and blanks a `job`, `source` or `health` cell only when it repeats the cell
directly above it in the same group, so `minio` and `s3` read as one service
with two URLs. Rendering only: `join()`, `ServiceRow`, `find()`, `JobSource`
and `--json` are untouched.

**Why per-cell and not per-group.** The obvious rule, "print the job, source
and health once per group", was measured against the fixtures and rejected:
it blanks the `s3` row's `source`, which deletes `consul-tag` from the table
entirely, and blanks its `health`, rendering a group whose Consul check is
`passing` as `no check`. The two health values differ legitimately, because
`api/services.py:137` computes the `job-id` row's health from the job's
registered service names and `:168` computes the `consul-tag` row's from the
matched service name.

**The trap.** `api/services.py:52` writes the same `AGENT_ENDPOINT` text into
every rung-(b) row and `:51` the same `NOT_FOUND` into every unresolved one.
Grouping on the raw `job` field therefore collapses `vault`, `nomad` and
`consul` into one group and hides two services. Reproducible live today. Row
2 is that.

**History worth knowing.** Four earlier plan reviews failed this ticket, each
time because a design silently stopped a `JobSource` value from being
rendered: `consul-tag` twice, `no-route` once, and once because the test list
still encoded a rejected design after the requirements were fixed. Rows 1, 2
and 4 exist so that class of defect fails a test rather than a review.

| Behavior | Input | Expected | Scorer | Threshold |
| --- | --- | --- | --- | --- |
| **A job's routes read as one service** | `_grouped()` over the fixture join | `minio` and `s3` are on consecutive rows; the second row's `job` cell is blank because it repeats the first. Today they sit several rows apart with nothing tying them together, which is what makes one service read as two | deterministic check (adjacent; second `job` cell blank) | 100% |
| **Guardrail: the agent endpoints do not group** | `_grouped()` over the fixture join, reading the `vault`, `nomad` and `consul` rows | Each keeps its own `job` and `health` cells. They share the literal `AGENT_ENDPOINT` text rather than a real job, so a rule keyed on the raw `job` field merges all three and hides two services. Verified live: grouping on that field yields `no job (agent endpoint): [consul, nomad, vault]` | deterministic check (three separate rows, none blanked) | 100% |
| Two unresolved rows do not group | `_grouped()` over an edge config carrying two routes that match no job, no catalog name and no tag | Both render with their own `not found` cells. They share the `NOT_FOUND` text for the same reason the agent endpoints share theirs, and two unknowns are not one service. The fixture has one orphan route today, so this builds a second | deterministic check (two rows, neither blanked) | 100% |
| **Guardrail: no rendered value disappears** | `_grouped()` over the fixture join, reading the `minio` group | Both `source` values are present (`job-id` AND `consul-tag`) and both `health` values are present. This is the defect that failed four plan reviews: a per-group blanking rule retires `consul-tag` from the output one ticket after D8 shipped it, and hides a `passing` check behind the row above's `no check`. The existing test at `cli/tests/commands/test_read_commands.py:167-179` asserts `consul-tag` reaches the rendered table and must stay green | deterministic check (every distinct `source` and `health` value in the group still rendered) | 100% |
| **No row is lost or duplicated** | `_grouped()` over the fixture join | `len(_grouped(rows)) == len(rows)`, and no `name` cell is ever blanked, so every row stays identifiable. Counted off the built row list rather than rendered lines, because columns fold at `Console(width=120)` and live hostnames are longer than the fixtures'. Reordering is where rows go missing | deterministic check (row count preserved; no blank `name`) | 100% |
| **`--json` is provably untouched** | `localstack service --json` with no name argument | The list handed to `emit_json` is the same object `join()` returned. Scoped to the no-name path because `commands/service.py:56-61` rebinds `rows = [row]` when a name is given. The real guarantee is the early `return` at `:69`, which runs before the table is built at `:71`, so no grouping code executes on the JSON path at all. A machine consumer already has `job` to group on and must not have its shape changed for a reading aid | deterministic check (same list object; no grouping on the JSON path) | 100% |
| Ungrouped rows are unchanged | `_grouped()` over the fixture join, reading any single-route job | Identical cells to today. A change that improves the two-route case by altering every other row is a bigger change than the complaint warrants | deterministic check (single-route rows byte-identical to the pre-change rendering) | 100% |
| **Guardrail: the live premise still holds** | `cluster`-marked test: `_grouped()` over the live join | `minio` and `s3` are adjacent and the agent endpoints are not grouped. SKIPS rather than fails when Consul is not advertising `minio`: it stopped for about ten minutes during the planning review when a node left the catalog, and `s3` correctly rendered `unresolved` throughout. A live test that reds on ordinary churn gets ignored, and is then worth nothing when it reds for a real reason | deterministic check (adjacent when `minio` is advertised; agent endpoints separate; skip otherwise) | 100% |
