---
verdict: pass
tree: 395322fe9bc7fb75b06eff43aae2bc152a04a6d8
---

# Documentation freshness: D3-cli-read-commands (cycle 3, final)

All three cycle-2 required fixes landed, and they are the only prose changes
since that review. The new denial branch in `commands/_session.py` does not
falsify `docs/cli-read-commands.md` for any state the shipped `deploy` token
can produce, so it is recorded below rather than required. Nothing else
drifted.

## Scope of this cycle

Diffed the cycle-2 tree against the one I am binding to:

    git diff b44e0523 395322fe --stat
    ROADMAP.md                                  | 12 +++---
    cli/src/localstack_cli/commands/_session.py | 17 ++++---
    cli/src/localstack_cli/commands/secret.py   |  1 -
    cli/tests/commands/test_read_commands.py    | 42 ++++++++++++++

`docs/cli-read-commands.md`, `docs/cli-login.md`, `docs/monitoring.md` and
`README.md` are byte-identical to what I passed at cycle 2. Blob hashes for
the three files I re-read match the fingerprint I was given, so the review is
bound to the right tree.

## Cycle-2 required fixes: all three verified

### 1. `ROADMAP.md:84` heading — fixed

Now `## Shipped since the last re-review round`. The body under it (`:86-87`)
says six of the eight shipped and the two left are not waiting on a re-review.
Heading and body now agree.

The related note about "the eight" is resolved in practice: `:86` names the
six (D2, D3, D4, D5, D6 and G2) and the table at `:89-92` carries the other
two, so a reader can check the arithmetic on the page.

### 2. `ROADMAP.md:49` "Same." — fixed

The N4 row now reads "No plan-validator verdict has ever run. Highest blast
radius on the board." It stands on its own with no deleted antecedent. The
claim matches the ledger: `N4-netsec-edge-only-service-access` is `planning`
in `.loop/ledger.json`.

### 3. `ROADMAP.md:343-347` D3 bullet — fixed

It now records that G2 landed and D3 shipped as written, and holds the reason
the scope was right anyway. Every part of that reason checks out:

- `login` brokers `nomad/creds/deploy`: `cli/src/localstack_cli/auth/broker.py:25`
  pins `NOMAD_CREDS_PATH = "nomad/creds/deploy"`.
- That policy grants neither `list-jobs` nor node read:
  `deployments/infrastructure/nomad_deploy_role.tf:17-29` lists `submit-job`,
  `read-job` and the five `host-volume-*` capabilities and nothing else.
- `nomad/creds/manage` exists as the successor path:
  `deployments/infrastructure/developer_group.tf:122-135`.
- `G2-nomad-ui-oidc-login` is `done` and `F8` is `blocked` in the ledger,
  matching the rest of the section.

No line anywhere in `ROADMAP.md` now tells a reader to defer D3.

## The `_session.py` change against the doc's closing paragraph

`commands/_session.py:100-115`: `nomad_reads_a_known_job` now returns `True`
or `None` and never `False`, so a failed Nomad probe produces the neutral
third message at `:71-72` ("denied `<capability>`. That comes from ...")
instead of "the token does not authenticate". Pinned by
`cli/tests/commands/test_read_commands.py:514-535`.

`docs/cli-read-commands.md:102-104` says every refusal picks a side:

> When a read is refused, the message says which of the two problems you have.
> A dead session says to log in. A missing grant names the capability and says
> that logging in again will not help, because it will not.

I walked every path that can reach `explain` from the four commands:

| State | Message | Doc's claim |
| --- | --- | --- |
| 401, or 403 whose body carries a dead-token marker (`_http.py:50-64`) | "no usable session. Run `localstack login`." | holds |
| Vault 403 that names no capability, `lookup-self` also refused | "the token does not authenticate. Run `localstack login`." | holds |
| Nomad 403 on `list-jobs` while `read-job` on `haproxy` works | "the session is live but the token lacks `list-jobs` ... will not change it." | holds |
| Probe cannot be put at all | "denied `<capability>`. That comes from ..." | says neither |

The last row is the one the change widened, and it is not reachable with the
credentials the CLI brokers. The Vault side is guarded before the call
(`commands/vault.py:49-51` exits when the session has no Vault token). The
Nomad side needs the `haproxy` single-job read to fail, and the `deploy`
policy grants `read-job` across namespace `default`, which is the only
namespace these commands read (`api/nomad.py` sends no namespace parameter).
The live shape is pinned the other way at
`test_read_commands.py:396-419`: the probe answers, and the message
discriminates.

So the doc is accurate for every state this cluster can produce today. It is a
simplification of a three-way branch, not a wrong statement about the shipped
behavior, and the branch it omits fires only when the cluster is already
degraded (the edge job missing or renamed). Recorded as advisory, below.

## Advisory (not required, carried for the record)

- **`docs/cli-read-commands.md:102`** states the discrimination as absolute.
  Whoever next edits that file could add one clause covering the neutral case,
  for example: when the probe cannot be put, the message names the capability
  and claims nothing about the session. Not required at this cycle: no token
  the CLI brokers reaches that branch. Same item I raised at cycle 2; the
  `_session.py` change widened the branch's class without making it reachable.
- **`docs/cli-read-commands.md:99`** still slightly over-credits the
  `developer` policy: `secret` also needs Nomad `read-job`
  (`commands/secret.py:44`), which comes from the brokered `deploy` token.
  Harmless, since both are held.
- **`vault grants` warns about unfillable variables**
  (`commands/vault.py:82-88`) and the doc does not mention it. A reader meeting
  `{{...}}` in a column labeled "resolved path" has nothing to explain it.
- **`ROADMAP.md:3` and `:20-22` are stale and were before this diff.** Line 3
  still says "Today: F11, then D1" with both `done`. Pre-existing, outside
  D3's surface.
- **`docs/cli-read-commands.md:104`**, "because it will not", is still an
  emphasis crutch under `.claude/rules/plain-language.md` rule 3. Judgment
  call, carried from cycle 1.

## Slop scan on what changed

`ROADMAP.md`, changed lines only (`:49`, `:84`, `:86-87`, `:343-347`): zero em
dashes, zero ` -- `, zero semicolon splices, zero tier-1 slop, zero
self-narration, zero hedging seesaw, zero "not just" / "not only", zero smart
quotes, zero British spellings, zero bare stubs, zero spatial copula, zero
prose arrows. Every backticked identifier resolves (`nomad/creds/deploy`,
`nomad/creds/manage`, `list-jobs`, `status`, `service`, `login`, `D3`, `G2`).
One changed line exceeds 80 chars (`:49`, 118), a markdown table row, which
cannot wrap. The eleven em dashes and the other long lines in the file are all
outside the changed region and predate this ticket.

`docs/cli-read-commands.md` did not change since cycle 2, where it scored 6/6
on document economy and came back clean on every mechanical check.

## Verdict

**pass.** Every documented surface this change touches was updated in step:
the four commands and their flags in `docs/cli-read-commands.md`, the command
list in `README.md:26`, and the three `ROADMAP.md` lines this ticket
falsified. Nothing left is a defect a reader would be misled by. The one open
item, the closing paragraph's three-way simplification, is an item for the
record: the branch it omits cannot fire under the credentials `localstack
login` brokers, and the doc's claim is true for every state the live cluster
produces.
