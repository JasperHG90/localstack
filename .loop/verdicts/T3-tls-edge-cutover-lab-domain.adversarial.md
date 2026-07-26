---
verdict: pass-with-required-fixes
tree: c6c5223a06bae9ec8967724b3d92a3e70de94892
---

# Adversarial review: T3-tls-edge-cutover-lab-domain — cycle 3 (cap)

Plainly, since this is the last cycle: **the infrastructure change is
committable and safe to apply. One line of prose is not, and it is the same
defect for the third time.**

Cycle 2's findings 2 and 3 are closed. Finding 1 is closed at six of its
seven sites. The seventh — `.loop/plans/F1-...:113-114` — still asserts the
opposite of the code it cites, and the hand-off states it was fixed. It was
fixed at the *other* F1 site, 150 lines further down, which now contradicts
it. That is the required fix and it is a one-line edit.

## Premise

Holds, re-measured read-only on this tree. `curl -sS -o /dev/null -w
'%{http_code}\n' https://grafana.lab.orangecluster.nl/` exits 60 with
`SSL certificate problem: self-signed certificate in certificate chain`,
code `000`. The edge still serves F3's leaf. The reason this ticket exists
is still true.

## Gates I re-ran myself

**`just pre_commit`** from the repo root: every hook `Passed`, including
Terraform Validate (per root), Terraform Format and Nomad Format.

**`terraform plan`** in `deployments/infrastructure` after `just init`, with
`-var-file=./vars/prod.tfvars`: `Plan: 1 to add, 1 to change, 9 to destroy`,
matching the briefing. Resource set:

```
nomad_job.haproxy                          updated in-place
vault_mount.pki                            destroyed
vault_pki_secret_backend_root_cert.root    destroyed
vault_pki_secret_backend_config_urls.urls  destroyed
vault_pki_secret_backend_role.haproxy      destroyed
vault_policy.haproxy_pki                   destroyed
vault_jwt_auth_backend_role.haproxy        destroyed
nomad_job.dnsmasq                          destroyed  (inherited, N2)
null_resource.firewall["dnsmasq"]          destroyed  (inherited, N2)
null_resource.firewall["prometheus"]       replaced   (inherited, N1)
```

`vault_mount.kvv2` does not appear. No backend and no other Vault resource
is touched. The `services.tf` hunk touches only the `nomad_job.haproxy`
block (`deployments/infrastructure/services.tf:311-325`).

**Offline HAProxy validation, reproduced from scratch.** I did not reuse
cycle 1's or cycle 2's run. Extracted the config heredoc from
`deployments/infrastructure/services/haproxy.hcl:76-168`, substituted
`${openfang_password}`, asserted no `${` survived, read
`secret/default/haproxy/tls` read-only, and rendered the cert template at
`haproxy.hcl:62-72` with faithful Go-template semantics
(`"\n" + certificate + "\n" + private_key + "\n\n"`). Then `haproxy -c` in
`docker.io/library/haproxy:3.1-alpine`:

| Case | Result |
|---|---|
| Rendered config + real PEM | `Configuration file is valid`, exit 0 |
| No `/secrets/haproxy.pem` | exit 1, `unable to stat SSL certificate` |
| `bogus_keyword_here` in `defaults` | exit 1, `unknown keyword` |
| Blank PEM (the `.Data.data` trap) | exit 1, `unable to load certificate ... no start line` |
| Certificate with no key | exit 1, `No Private Key found` |

The check discriminates on all four negative controls, including the two
that matter: the blank PEM is exactly what `{{ .Data.certificate }}` would
have produced against KV2, and the key-less PEM is what dropping
`private_key` would produce. Both fail loudly.

The certificate: `subject=CN = *.lab.orangecluster.nl`, `issuer=C = US,
O = Let's Encrypt, CN = YE2`, SANs `*.lab.orangecluster.nl` and
`lab.orangecluster.nl`, valid Jul 26 to Oct 24 2026. The private key's
public half MD5-matches the leaf's. The KV entry carries `certificate`,
`issuer_chain`, `private_key`; `certificate` holds 4 PEM blocks, so the
decision not to append `issuer_chain` (`haproxy.hcl:41-44`) is right.

**Bare `vault {}`, checked against the live policy.** `vault policy read
nomad-workloads` grants read on
`secret/data/{{...nomad_namespace}}/{{...nomad_job_id}}/*`. For
`job_id=haproxy` in `default` that is `secret/data/default/haproxy/*`,
covering the `.../tls` the template reads. `services.tf:323` passes
`"${var.secret_mount}/data/default/haproxy/tls"` and `secret_mount` is
`"secret"` (`vars/prod.tfvars:1`). Requirement 6 holds.

**Config shape.** Twelve ACLs (`haproxy.hcl:98-109`), twelve `use_backend`
(`:111-122`), twelve backends (`:131-168`), all twelve renamed. The last
diff hunk ends at new line 109; `backend minio` starts at 131, so eval row
6 passes statically. The doc's hostname table
(`docs/haproxy_reverse_proxy.md:12-25`) matches all twelve backends and
ports exactly, and the three basic-auth backends it names (phoenix, mlflow,
bifrost) match `haproxy.hcl:147,163,167`.

## Finding 1 (MAJOR, required) F1's "single most useful sentence" says the opposite of the code it now cites

`.loop/plans/F1-foundation-nomad-wi-jwt-trust.md:111-117`:

> **One task holds exactly one Vault token.** A task has a single `vault`
> block and performs a single JWT login, so naming a dedicated role
> REPLACES `nomad-workloads` rather than adding to it — `acme.tf:87` sets
> `token_policies` to the dedicated policy alone. [...] This is the single
> most useful sentence this document can contain, and every consumer (M1,
> S2/R3, F5/F6) will need it.

`deployments/infrastructure/acme.tf:87` is:

```hcl
  token_policies         = ["nomad-workloads", vault_policy.acme_tls_write.name]
```

Both, not one. The anchor was retargeted from `pki.tf:113` to `acme.tf:87`
(the diff shows exactly that substitution) and the predicate was left
describing the deleted file. This is the third recurrence of the blind
path-substitution defect, and the hand-off lists it as fixed.

Three things make this worse than the six sites that were fixed:

- **The same file now contradicts itself.** `.loop/plans/F1-...:264-267`
  says "Note `token_policies` (`acme.tf:87`) lists BOTH `nomad-workloads`
  and the dedicated policy". `.loop/plans/F9-...:59-62` says the same. So
  does `.loop/evals/F1-...:25`, which requires the doc F1 ships to state
  "the rule that a dedicated role REPLACES `nomad-workloads` so a job
  needing both must list both policies". Line 113-114 is the lone outlier
  against three corrected statements.
- **It is the sentence F1 flags as load-bearing** (`:116-117`), so it is
  the one an F1 implementer copies verbatim into `docs/workload-identity.md`.
- **It teaches the exact failure `acme.tf:56-61` exists to prevent**: "With
  only acme-tls-write attached, the job could write the cert but could not
  read the TransIP credential it needs to obtain one, and its template would
  block forever."

Fix: replace "sets `token_policies` to the dedicated policy alone" with the
wording already used at `:265-267`. One line.

## Finding 2 (MINOR, required) The plan's own repo gate still tells the operator to confirm something false

`.loop/plans/T3-...:199-202`:

> **Command:** `terraform -chdir=deployments/infrastructure plan` -> updates
> `nomad_job.haproxy` in place; DESTROYS the six `pki.tf` resources. Confirm
> it destroys no KV mount, no backend, **no firewall rule**, and does not
> touch `vault_mount.kvv2`.

The plan I ran destroys `null_resource.firewall["dnsmasq"]` and replaces
`null_resource.firewall["prometheus"]`. An operator running this gate as
written sees two firewall entries move and concludes something is wrong.

I flagged this exact sentence in cycle 2 finding 2. Eval row 7 was fixed and
is now correct and scoreable; this narrative twin was not touched. Give it
the same treatment row 7 got: name the three inherited resources and say the
firewall movement is expected.

## Finding 3 (MINOR, advisory) A claim labeled "Verified live" is only true after the apply

`.loop/plans/F1-...:100-101`: "Verified live: `vault list auth/jwt-nomad/role`
returns `acme` and `nomad-workloads`." Run right now against the cluster it
returns `acme`, `haproxy`, `nomad-workloads`; `haproxy` disappears only when
this plan is applied.

This is the post-apply-tense convention the rest of the sweep uses and which
I accepted in cycle 2 (finding 5), so I am not requiring a change. But
"Verified live" claims more than the convention supports — it invites a
reader to re-run the command and get a different answer. `.loop/plans/C1-...:80`
("T3 has landed") and `docs/tls-certificates.md:66` ("was removed", while
`nomad_job.dnsmasq` is still deployed and this very plan destroys it) are the
same class.

## Finding 4 (MINOR, advisory) The new wildcard-depth sentence is ambiguous in the direction that defeats it

`docs/haproxy_reverse_proxy.md`, new paragraph: "it was issued for
`*.localstack`, and a wildcard has to sit at least two labels above the
root." Counting labels from the root, the `*` in `*.localstack` *is* two
labels above it, so read literally the rule does not explain the failure it
is offered to explain. The plan states the same rule unambiguously
(`.loop/plans/T3-...:23-24`: "a wildcard requires >=2 labels after the
`*`"). Borrow that phrasing.

The rest of that rewrite is right, and it is a genuine correction: the
earlier text blamed label depth for F3's failure, and `grafana.localstack`
was indeed already flat. The separated-facts version now matches the plan's
own "Triggered by" section and the `openssl`/`curl` errors recorded there.
The paragraph above it (TLS wildcard matches one label, DNS wildcard matches
at any depth, so `a.b.lab.orangecluster.nl` resolves and the edge answers it
while the cert fails) is correct — I confirmed
`dig +short @1.1.1.1 anything.lab.orangecluster.nl` returns `192.168.2.30`.

## Finding 5 (MINOR, advisory) Eval row 11's Expected still names two files that cannot match

`.loop/evals/T3-...:31` Expected: "Only historical records match: the `F3-*`
and `F4-*` files, ...". Under the row's own grep root
(`.loop/plans .loop/evals`) those files cannot match, because they live in
`.loop/archive`. I ran the command; the matches are `A1-*` (plan and eval),
`N2-*` (eval), T3's own plan and eval, and `F2-*`, `G1-*`, `L1-*`, `L2-*`,
`M2-*`. I read every one of the last five and each is a historical statement
about F3 or F4, which the Expected column's closing clause covers.

The Scorer column no longer contradicts Expected — cycle 2's required fix
landed — and the row is scoreable as written, because the phantom F3/F4
entry is a superset expectation rather than a missed match. Dropping it
would still be right.

## Findings I raised in cycle 2 and am not re-raising as required

`.loop/evals/R1-...` and `.loop/evals/L2-...` still test
`curl -sI http://mlflow.lab.orangecluster.nl/` and
`http://dash.lab.orangecluster.nl/`. Port 80 has 301-redirected since F3, so
those rows return 301, not the 302/401/200 they assert. Pre-existing, raised
in cycles 1 and 2, still pre-existing. Same class: `.loop/plans/F2-...:66`
says "Vault is reachable at `http://vault.lab.orangecluster.nl`" and its
`haproxy.hcl:53,66,84-85,91` anchors have been stale since F3 shifted the
file (ACLs are now at 98-109, backends at 131-168).

## Cycle-2 findings I confirmed closed

- **The other six retarget sites.** `F1:101-106` (now names
  `vault_policy.acme_tls_write` / `vault_jwt_auth_backend_role.acme`, cites
  `services/acme.hcl:73-75`, and credits F3's deleted `pki.tf` as the first
  instance); `F1:261-272`; `F1:517-518`; `F9:55-62` (no dangling fragment,
  "proven twice" dropped, "F3's" corrected to the acme job's); `F9:104-106`;
  `S2:253-254`. Every anchor re-opened and read: `acme.tf:41` is
  `vault_policy "acme_tls_write"`, `acme.tf:66` is
  `vault_jwt_auth_backend_role "acme"`, the block ends at `:90`, and
  `services/acme.hcl:73-75` is `vault { role = "${vault_role}" }`.
- **The fabricated verbatim quote.** `S2:175-180` no longer claims
  `acme.tf:41-49` "states the case verbatim". It now cites `acme.tf:50-65`
  and paraphrases. The comment at `acme.tf:51-54` does make that argument
  ("This is a SECOND role on that mount, selected per-job via
  `vault { role }`, leaving every other workload on the default role
  untouched"), and the paraphrase is faithful. Nit: the span opens on the
  blank line 50; `51-65` is exact.
- **Eval row 7.** Now enumerates the six PKI resources by name, states the
  three inherited ones and the total of nine, and asks for confirmation that
  no KV mount, backend or other Vault resource moves. I checked it against
  the real plan output line by line. Scoreable exactly as written.
- **Eval row 11's Scorer.** No longer contradicts Expected, no longer claims
  F3/F4 match. Scoreable (see finding 5 for the residue).
- **The 30-day window.** `.loop/plans/T3-...:110-111` and
  `.loop/evals/T3-...:32` now both say 30 days, agreeing with
  `docs/tls-certificates.md:132`. Verified at source: `services/acme.hcl:65`
  is `args = ["run", "--renew-days", "30"]` on the daily cron at `:11`
  (`crons = ["0 4 * * *"]`).
- **The deferral rationale.** Checkable and true. `grep` for
  `blackbox|probe_ssl|ssl_earliest` across every `.hcl`, `.yaml`, `.tf`
  returns nothing; `deployments/infrastructure/services/prometheus.hcl` has
  no `scheme` directive, so nothing is scraped over HTTPS. Requirement 11 is
  struck through, marked NOT delivered, dated, attributed to the operator,
  and states the open risk. Row 12 is struck with threshold `n/a`. This is
  honest bookkeeping, not a lowered bar.

## New errors introduced this cycle

I looked specifically. Finding 1 is a survival, not a new error — the line
was already wrong in cycle 2 and I under-scoped my own finding to the two
F1 sites I quoted. Findings 3 and 4 are the only genuinely new prose, and
both are advisory. Every file path backticked in the changed doc lines
resolves. The `docs/monitoring.md` corrections are right at source:
`http_in` to `https_in` matches `haproxy.hcl:95`, and the prometheus/grafana
backend IPs `192.168.2.30` to `192.168.2.47` match `haproxy.hcl:154,157`.
`docs/tls-certificates.md:83` names `acme_lego_state`, matching
`acme.tf:14` and `services/acme.hcl:26-28`.

## Doc commands, spot-checked live

`docs/dns.md:91-94` — all four `dig` results match their comments exactly
(`192.168.2.30` for the host, apex and wildcard; `37.97.254.29` for
`orangecluster.nl`). `dig +short CAA lab.orangecluster.nl` returns
`0 issue "letsencrypt.org"`, matching `docs/tls-certificates.md`'s public-
surface section. `docs/tls-certificates.md:104` and `:114` work. `:125`
exits 60 with `000`, the pre-apply state the eval marker itself predicts.

## Scope

Clean. Every changed line traces to the plan's Code surface, to the sweep it
mandates, or to the concurrent documentation pass. `.loop/config.json`'s
`review_passes[2].enabled = true` is requirement 10; `max_review_cycles`
4 to 3 is not, but N1's commit message (`5ebccb8`) ends "max_review_cycles
goes 3 to 4 in this commit. [...] It should go back to 3", so it is that
author's instruction being honored. Cycles 1 and 2 accepted it; so do I.

## Rows this tree cannot satisfy

Rows 1-5, 8 and 10 need the apply. Row 9 is human-scored by operator
decision. Row 12 is deferred and not scored. Row 6 I verified statically:
the `haproxy.hcl` diff's last changed line is 109 and `backend minio` starts
at 131, so nothing below the first `backend` line moved. Row 7 I verified
against the real plan output. Row 11 I verified by running its grep and
reading every match. Nothing in the marker is unsatisfiable for a reason
this tree could fix.

## Verdict

`pass-with-required-fixes`.

**The apply is safe and the tree is committable once finding 1 is fixed.**
The template renders, the config validates against the real certificate,
four negative controls discriminate, the `nomad-workloads` grant covers the
KV path, and the plan destroys the six PKI resources plus only the three
inherited from N1 and N2. Nothing about the edge change is blocked.

What blocks the commit is one sentence of prose in a downstream plan that
states the opposite of the code it cites, contradicts three corrected
statements in the same tree, and is flagged by its own document as the
sentence future tickets will copy. It is a one-line edit. Finding 2 is a
second short edit I would take in the same pass. Findings 3, 4 and 5 are
advisory and I would ship without them.
