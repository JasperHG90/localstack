---
verdict: pass
plan: 3a576dae12ca9006c3f5bdf0f5658364a1e6d136cd332d99f4dacfb0e2af4270
bound_paths: front-matter, 5, 6, 7, 8, 9, 10, premises
scope: 2e5ac12087d73396a805a2ecfec853eaba3d7ad15fcd583271f7326978fc369a
citations:
  cli/src/localstack_cli/auth/broker.py:25 = NOMAD_CREDS_PATH = "nomad/creds/deploy"
  cli/src/localstack_cli/auth/broker.py:31-34 = _FIELDS = {\n    "nomad": (NOMAD_CREDS_PATH, "secret_id", "accessor_id"),\n    "consul": (CONSUL_CREDS_PATH, "token", "accessor"),\n}
  cli/src/localstack_cli/auth/broker.py:41-48 = def _denied_message(...): ... "  The grant lives in F11-foundation-human-read-role, which binds " "`developer` to the two creds paths through an identity group."
  cli/src/localstack_cli/auth/broker.py:150-166 = refreshed: dict[str, Credential | None] = {}\n    for service in ("nomad", "consul"): ... replace(session, vault=vault_entry, nomad=refreshed["nomad"], consul=refreshed["consul"])
  cli/src/localstack_cli/auth/session.py:20 = SCHEMA_VERSION = 1
  cli/src/localstack_cli/auth/session.py:60-74 = @dataclass(frozen=True)\nclass Session: ... def credential(self, service: str) -> Credential | None:
  cli/src/localstack_cli/auth/session.py:131-142 = body = json.dumps({ "version": session.version, ... "consul": _encode(session.consul), }, indent=2,)
  cli/src/localstack_cli/auth/session.py:180-185 = if version != SCHEMA_VERSION: raise SessionError(... "Run `localstack logout` and log in again." )
  cli/src/localstack_cli/auth/session.py:191-199 = return Session( method=..., nomad=_decode(data.get("nomad"), "nomad"), consul=_decode(data.get("consul"), "consul"), version=SCHEMA_VERSION,)
  cli/src/localstack_cli/commands/status.py:34 = nomad_entry = session.credential("nomad")
  cli/src/localstack_cli/commands/service.py:41 = entry = session.credential("nomad")
  cli/src/localstack_cli/commands/monitor.py:44 = entry = session.credential("nomad")
  cli/src/localstack_cli/commands/logout.py:63 = for name in ("vault", "nomad", "consul"):
  cli/src/localstack_cli/commands/login.py:108-115 = session = Session( ... nomad=broker("nomad", addr, vault_credential.token), consul=broker("consul", addr, vault_credential.token), )
  cli/src/localstack_cli/commands/env.py:37 = "NOMAD_TOKEN": session.nomad.token,
  cli/src/localstack_cli/commands/_session.py:25-30 = GRANTED_BY = { ... nomad.LIST_JOBS: "brokering `nomad/creds/manage` (D2)", nomad.NODE_READ: "brokering `nomad/creds/manage` (D2)", }
  cli/src/localstack_cli/commands/whoami.py:62 = for name in ("vault", "nomad", "consul"):
  cli/src/localstack_cli/commands/config.py: (session block) = "expires_at": {name: entry.expires_at.isoformat() for name in ("vault", "nomad", "consul") if (entry := session.credential(name)) is not None}
  cli/src/localstack_cli/commands/token.py:26 = SERVICES = ("vault", "nomad", "consul")
  cli/src/localstack_cli/commands/secret.py:39 = nomad_entry = session.credential("nomad")
  cli/src/localstack_cli/api/nomad.py:28-30 = LIST_JOBS = "list-jobs"\nNODE_READ = "node:read"\nREAD_JOB = "read-job"
  cli/src/localstack_cli/auth/vault.py:155-162 = def read_creds(addr: str, token: str, path: str) -> dict[str, Any]: ... return _request(addr, path, token=token)
  deployments/infrastructure/nomad_deploy_role.tf:1-5 = ### Nomad ACL policy for the Terraform deployer. ... no alloc-node-exec, no list-jobs / dispatch-job / read-logs / read-fs, and no node / agent / operator access.
  deployments/infrastructure/nomad_deploy_role.tf:21-50 = resource "nomad_acl_policy" "deploy" { ... capabilities = ["submit-job","read-job","host-volume-create", ...] }
  deployments/infrastructure/nomad_deploy_role.tf:56-61 = resource "vault_nomad_secret_role" "deploy" { backend = "nomad" role = "deploy" type = "client" policies = [nomad_acl_policy.deploy.name] }
  deployments/infrastructure/nomad_oidc.tf:16-17 = ### The DEFAULT `nomad` provider is untouched. It is bare (providers.tf:26) and\n### reads NOMAD_TOKEN from the environment, which today is the bootstrap token.
  deployments/infrastructure/nomad_oidc.tf:74-79 = resource "vault_nomad_secret_role" "manage" { backend = "nomad" role = "manage" type = "management" global = true }
  deployments/infrastructure/developer_group.tf:122-125 = # brokered. Two are intended: `deploy` and, since G2, `manage`.\npath "nomad/creds/deploy" { capabilities = ["read"] }
  deployments/infrastructure/developer_group.tf:140-142 = path "nomad/creds/manage" { capabilities = ["read"] }
  deployments/infrastructure/providers.tf:26 = provider "nomad" {}
  justfile:18-19 = pre_commit:\n    pre-commit run --all-files
  .pre-commit-config.yaml:37-72 = - id: ruff ... - id: pytest ... files: '^cli/'
  cli/pyproject.toml:41-44 = markers = [\n"cluster: hits the live cluster (network, real Vault/Nomad/Consul)",\n]\naddopts = "-m 'not cluster'"
  cli/pyproject.toml:63 = strict = true
  .loop/archive/D4-cli-cluster-tui/plan.md:604-613 = The existing `deploy` role cannot list jobs or read nodes ... **Resolved 2026-07-31: D2 brokers `nomad/creds/manage`** ... Option (b), a narrow `nomad_read_role.tf`, is **rejected**
  .loop/archive/D4-cli-cluster-tui/plan.md:763-769 = **Recorded honestly**: a management token is full Nomad access, not read-only. Brokering it to a read-only TUI is a privilege widening the operator accepted ... relayed to D2 ... a small but real follow-up to its `broker.py` (a new creds path)
  .loop/archive/D3-cli-read-commands/eval.md:72 = ... Nomad `list-jobs` plus node read from D4's `nomad_read_role.tf` ...
  .loop/ledger.json:1007 = "stage": "done",
  .loop/ledger.json:1041 = "stage": "done",
  cli/tests/fixtures/cluster.py:52-58 = NOMAD_CREDS = { "lease_id": ..., "data": {"secret_id": "nomad-secret-id", "accessor_id": "nomad-accessor-id"}, }
  cli/tests/fixtures/cluster.py:70-79 = HEALTHY_ROUTES: dict[str, tuple[int, bytes]] = { ... "/v1/nomad/creds/deploy": (200, json.dumps(NOMAD_CREDS).encode()), ... }
  cli/tests/fixtures/cluster.py:123-124 = status, reply = server.routes.get(self.path, (404, b"no such route"))
  cli/tests/auth/test_broker.py:20-43 = def session_at(cluster_addr: str, nomad_minutes: int, consul_minutes: int) -> Session: return Session( ...)
  cli/tests/auth/test_broker.py:46 = def test_the_two_engines_use_different_field_names(cluster_addr: str) -> None:
  cli/tests/auth/test_broker.py:75 = def test_a_403_names_the_path_the_policies_and_the_ticket(
  cli/tests/auth/test_broker.py:145 = def test_ensure_fresh_rebrokers_only_the_stale_one(cluster_addr: str, cluster...
  cli/tests/auth/test_session.py:37-45 = return Session( method="userpass", ... vault=Credential( token="vault-token", ...
  cli/tests/auth/test_session.py:112-114 = def test_a_wrong_schema_version_says_how_to_recover(tmp_path: Path) -> None: path.write_text(json.dumps({"version": 99, "vault": {}}))
  cli/tests/auth/test_session.py:160-165 = def test_credential_lookup_by_service_name() -> None: session = a_session() ... assert session.credential("postgres") is None
  cli/tests/auth/test_live_login.py:104-115 = def test_the_brokered_tokens_are_real(live_session: Path) -> None: ... assert "client" in nomad.stdout
  cli/tests/commands/test_read_commands.py:38-56 = class _Credential: ... class _Session: def credential(self, service: str) -> Any: return _Credential(f"a-{service}-token") ... @pytest.fixture(autouse=True)\ndef session(...)
  cli/tests/commands/test_monitor_command.py:88-90 = class _FakeSession:\ndef credential(self, service: str) -> Any:\nreturn _FakeCredential() if service == "nomad" else None
  cli/tests/commands/test_auth_commands.py:27-46 = @pytest.fixture\ndef logged_in(cluster_addr: str) -> Session: ... nomad=Credential("nomad-tok", "nomad-acc", now + timedelta(minutes=25), True), consul=Credential(...) ...
  cli/tests/commands/test_auth_commands.py:210 = def test_logout_prints_the_accessors_when_revocation_fails(
  cli/tests/commands/test_auth_commands.py:243 = def test_login_writes_the_session_and_the_token_file(cluster_addr: str) -> None:
  cli/tests/commands/test_auth_commands.py:255 = def test_login_brokers_eagerly(cluster_addr: str, cluster: FakeCluster) -> None:
  cli/tests/commands/test_auth_commands.py:323 = assert set(body["session"]["expires_at"]) == {"vault", "nomad", "consul"}
  cli/tests/commands/test_token_command.py:20-32 = def logged_in(cluster_addr: str) -> Session: ... nomad=Credential("nomad-tok", "na", now + timedelta(minutes=25), True), consul=Credential("consul-tok", "ca", now + timedelta(minutes=25), True), )
---

## Deterministic floor

`loopctl verify-plan D10-cli-broker-nomad-manage` (run via `PYTHONPATH=.claude/plugins/aim-ef9f6a17bd3105b7/loop-harness/src python3 -m loop_harness.cli verify-plan D10-cli-broker-nomad-manage`, since no installed `loopctl` binary was on PATH — the package is stdlib-only per its `pyproject.toml`, so this is equivalent to the CLI entry point):

```
valid: warn: ambiguous file basename 'providers.tf' (matches several files); warn: symbol 'respx' cited at test_read_commands.py:38-56 is off those lines
```

Exit 0, `valid`, no hard-fail. Both flags are advisory and I checked both directly: (1) the plan's citation is the fully-qualified `deployments/infrastructure/providers.tf:26`, not a bare basename — three `providers.tf` files exist in the repo but the plan never cites the bare name, so the ambiguity warning is a false positive against this plan's actual citation style; (2) `test_read_commands.py:38-56` is cited for the `_Credential`/`_Session` stub classes, which are exactly what sits at those lines (the heuristic flagged the unrelated word "respx", imported at line 13, not present at 38-56 — the plan never claims `respx` is on those lines). Clean floor; proceeding to falsification.

## Premise verdict

SOUND.

## Per-assumption findings

- **P1 — UNCERTAIN (as the plan itself states).** `deployments/infrastructure/nomad_oidc.tf:74-79`
  > resource "vault_nomad_secret_role" "manage" {
  >   backend = "nomad"
  >   role    = "manage"
  >   type    = "management"
  >   global  = true
  > }
  The claim is that `nomad/creds/manage`'s response carries the same `data.secret_id`/`data.accessor_id` field names as `deploy`'s, and the plan itself marks this UNCERTAIN, disclaiming a live probe. I did not force a probe (no live cluster is reachable from this environment either), consistent with the rule that a self-disclaimed premise stays UNCERTAIN. I did check a source outside the repo: the public Vault Nomad secrets engine API docs (`https://developer.hashicorp.com/vault/api-docs/secret/nomad`, fetched with `curl`) list `secret_id`/`accessor_id` as the generic `creds/<role>` response fields, not role-specific ones, which corroborates the plan's "documented to be uniform across role types" claim without proving it for this specific role. The mitigations the plan cites are real: `broker.py:79-82` raises a named `BrokerError` rather than silently returning an empty token (verified by reading `broker.py:73-82`), and `cli/tests/auth/test_live_login.py:104-115` is a genuine existing live-cluster test (`pytestmark = pytest.mark.cluster`, excluded by `cli/pyproject.toml:44`'s `addopts = "-m 'not cluster'"`) whose pattern (`assert "client" in nomad.stdout` from `nomad acl token self`) is exactly what the plan says a mirrored `nomad_manage` assertion would check against `"management"`. UNCERTAIN, honestly bounded, with a legible failure mode rather than a silent one.

- **P2 — HOLDS.** `deployments/infrastructure/nomad_deploy_role.tf:1-5`
  > ### Nomad ACL policy for the Terraform deployer.
  > ### Scoped to exactly what deploying this repo's nomad_job and
  > ### nomad_dynamic_host_volume resources needs, and no more: no alloc-exec,
  > ### no alloc-node-exec, no list-jobs / dispatch-job / read-logs / read-fs,
  > ### and no node / agent / operator access.
  And `nomad_deploy_role.tf:26-37`:
  > capabilities = [
  >   "submit-job",
  >   "read-job",
  >   "host-volume-create",
  >   "host-volume-register",
  >   "host-volume-read",
  >   "host-volume-write",
  >   "host-volume-delete",
  > ]
  Matches the plan's Context quote and P2's claim verbatim (the plan drops the leading "no alloc-exec," clause but keeps the rest intact and accurate).

- **P3 — HOLDS.** `deployments/infrastructure/nomad_oidc.tf:74-79` (quoted under P1). `role = "manage"`, `type = "management"` are literal. HOLDS.

- **P4 — HOLDS.** `deployments/infrastructure/developer_group.tf:122-125`
  > # brokered. Two are intended: `deploy` and, since G2, `manage`.
  > path "nomad/creds/deploy" {
  >   capabilities = ["read"]
  > }
  And `developer_group.tf:140-142`:
  > path "nomad/creds/manage" {
  >   capabilities = ["read"]
  > }
  Both `read` grants exist today, live, exactly as claimed.

- **P5 — HOLDS.** `.loop/ledger.json:1007` and `:1041`
  > "stage": "done",
  Both `D2-cli-login-broker-tokens` and `D3-cli-read-commands` entries carry `"stage": "done"`. And `cli/src/localstack_cli/commands/_session.py:28-29`:
  > nomad.LIST_JOBS: "brokering `nomad/creds/manage` (D2)",
  > nomad.NODE_READ: "brokering `nomad/creds/manage` (D2)",
  Matches exactly.

- **P6 — HOLDS, exhaustively verified.** `probe: grep -rn "Session(" cli/src cli/tests` returns exactly 15 matches (verified by running the identical command), 2 of which are `_FakeSession()`/`_Session()` test doubles at `test_monitor_command.py:65` and `test_read_commands.py:52`. I read all 13 remaining real `Session(...)` construction sites directly (`session.py:191`, `login.py:108`, `test_session.py:37`, `test_broker.py:21,170,191,212,232`, `test_token_command.py:22,64,91`, `test_auth_commands.py:30,83`) and every one uses keyword-only arguments — no positional call exists. `cli/tests/auth/test_broker.py:230-240`:
  > session = Session(
  >     method="userpass",
  >     vault_addr=cluster_addr,
  >     username="operator",
  >     vault=Credential(
  This is representative of all 13; none deviate. P6 HOLDS with full coverage, not a sample.

- **P7 — HOLDS.** `.loop/config.json:2-4`
  > "gates": [
  >   "just pre_commit"
  > ],
  `justfile:18-19`:
  > pre_commit:
  >     pre-commit run --all-files
  `.pre-commit-config.yaml:37-72` defines the `ruff`, `ruff-format`, `mypy`, `pytest` hooks, all `files: '^cli/'`; `cli/pyproject.toml:63` has `strict = true` under the mypy config, confirming "mypy --strict". No CI workflow was found referencing these gates (checked via the plan's own claim, not independently re-derived — the ticket's own §8 states "No CI; these are local-only gates", and I found no `.github/workflows` invocation of them). HOLDS.

- **P8 — HOLDS, and the repo itself independently confirms it.** `cli/src/localstack_cli/commands/env.py:37`
  > "NOMAD_TOKEN": session.nomad.token,
  `deployments/infrastructure/providers.tf:26`
  > provider "nomad" {}
  And, stronger than the plan's own citation, `deployments/infrastructure/nomad_oidc.tf:16-17` states this directly as a design comment written by a different author on a different ticket:
  > ### The DEFAULT `nomad` provider is untouched. It is bare (providers.tf:26) and
  > ### reads NOMAD_TOKEN from the environment, which today is the bootstrap token.
  This is repo-internal corroboration of the exact claim P8 makes, independent of the plan's own reasoning. HOLDS strongly.

## Implicit premises checked beyond the plan's own list

- **`vault.read_creds` is fully generic over the path argument, not hardcoded to `deploy`.** `cli/src/localstack_cli/auth/vault.py:155-162`
  > def read_creds(addr: str, token: str, path: str) -> dict[str, Any]:
  >     ...
  >     return _request(addr, path, token=token)
  Confirms adding a third creds path is a pure data change (a new `_FIELDS` row and a new call site), not a code-path change — supports the plan's stated Size/Effort reasoning.

- **Nomad's `X-Nomad-Token` header is type-agnostic (a management token authenticates the same way a client token does).** `cli/src/localstack_cli/api/nomad.py:25,28-30,127,142`
  > TOKEN_HEADER = "X-Nomad-Token"
  > LIST_JOBS = "list-jobs"
  > NODE_READ = "node:read"
  > READ_JOB = "read-job"
  Every Nomad API call in `api/nomad.py` uses the same `TOKEN_HEADER` regardless of token type, confirming no `api/nomad.py` change is needed — consistent with the plan's Code Surface (§7) not touching that file.

- **A missing `/v1/nomad/creds/manage` route in the fake cluster would break the whole login-dependent test suite, as claimed.** `cli/tests/fixtures/cluster.py:123-124`
  > status, reply = server.routes.get(self.path, (404, b"no such route"))
  Confirmed: an unregistered route 404s, which `broker()` (`broker.py:71`) turns into a `BrokerError`, which `login()` (`login.py:116-124`) catches and turns into a hard command failure — validating §7's and §10's claim that `cli/tests/fixtures/cluster.py`'s `HEALTHY_ROUTES` edit is the highest-leverage, sequence-first change.

- **No test asserts a fixed count or membership on `broker.py`'s `_FIELDS` dict or `_denied_message`'s exact wording.** Checked via `grep -rn "_FIELDS" cli/tests` (no matches) and reading `test_broker.py:75-89` (`test_a_403_names_the_path_the_policies_and_the_ticket`, `test_a_403_still_reports_when_the_policy_lookup_also_fails`) — neither asserts the "two creds paths" substring. The `_denied_message` wording fix (§6) has a code producer in §7 but no dedicated new test; this is a cosmetic string correction with no behavior to test, not a hygiene failure (the create-ticket contract requires a producer in §7, which exists, not a dedicated test per requirement).

- **The `SCHEMA_VERSION` bump does not silently break existing version tests.** `cli/tests/auth/test_session.py:112-114` and `:12`
  > SCHEMA_VERSION,
  > def test_a_wrong_schema_version_says_how_to_recover(tmp_path: Path) -> None:
  >     path.write_text(json.dumps({"version": 99, "vault": {}}))
  The existing mismatch test uses a literal sentinel (`99`) and other tests reference the `SCHEMA_VERSION` symbol rather than a hardcoded `1`, so bumping to `2` is safe without touching this file — confirms the requirement is reachable by an existing measurement, not just a new one.

## Contract hygiene

- **Non-goals (§5):** present and substantive (no `deployments/**`/`bootstrap/**` change, no `nomad_read_role.tf`, no export via `env`/`token`, no surfacing in `whoami`/`config`, `secret.py`/`vault.py` untouched). Verified `token.py:26`'s `SERVICES = ("vault", "nomad", "consul")` and `test_auth_commands.py:323`'s fixed-tuple assertion `{"vault", "nomad", "consul"}` both back the stated non-goal reasoning.
- **Tests homed in code surface:** every named test in §8 has an explicit file in §7 (`test_read_commands.py` for the three new read-command tests; `test_broker.py` for the three new broker tests; `test_session.py` and `test_auth_commands.py` for the extended existing tests). No orphan test names.
- **Requirements reachable by a measurement (§6 → §7/§8):** each §6 requirement maps to a §7 code-surface producer; the ones with new observable behavior (manage-credential routing, deploy-credential retention, round-trip/lookup) have dedicated §8 tests; the wording fix and the SCHEMA_VERSION bump have producers with no dedicated NEW test but are covered by existing version-agnostic tests (`test_a_wrong_schema_version_says_how_to_recover`) or are non-behavioral string changes — no `unmeasurable-requirement` Open Question is needed because nothing here is actually unmeasurable, it is simply covered by pre-existing tests rather than new ones.
- **Forks surfaced:** §11 carries two Open Questions, each with an explicit recommendation, matching the contract.
- **Gates discovered, not assumed:** confirmed against `.loop/config.json`, `justfile`, `.pre-commit-config.yaml`, `cli/pyproject.toml` directly, not taken on faith.

## Most dangerous assumption

P1: whether `nomad/creds/manage`'s Vault response uses the same `secret_id`/`accessor_id` field names as `deploy`'s. If wrong, `localstack login` fails for every user until fixed. The plan itself flags this UNCERTAIN rather than asserting it, and backs it with a real, already-existing mechanism that turns a wrong guess into a named `BrokerError` (not silent corruption or a wrong-but-plausible token) and a concrete, already-scoped live-cluster test extension to close the gap during implementation. That is the correct posture for an assumption that cannot be settled from this planning environment: honestly flagged, not laundered into a `HOLDS`, with a bounded blast radius and a stated path to resolving it.

## Result

No required fixes. The plan's every explicit premise (P2-P8) resolves to an exact, verbatim-matching anchor in the live repo, several independently corroborated by comments written on unrelated tickets (`nomad_oidc.tf`'s NOMAD_TOKEN comment, `developer_group.tf`'s grant comments). P1 is the one genuinely unresolved premise and the plan already treats it honestly, with real mitigations rather than a hand-wave. Contract hygiene (non-goals, test homing, requirement-to-producer mapping, discovered gates, surfaced forks) is clean.
