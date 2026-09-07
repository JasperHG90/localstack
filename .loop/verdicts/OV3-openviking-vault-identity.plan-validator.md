---
verdict: pass-with-required-fixes
plan: 84cbb09395a0a396dbe82d3962b55066bbe23ca6bd6eacea35c5542cb36990de
bound_paths: front-matter, 5, 6, 7, 8, 9, 10, premises
scope: 227079232244f8f79b16e84a6b35c69d2ed09ab59f0d3a1966342c188eacbbb2
fix_sections: 5, 6, 7, premises
citations: deployments/infrastructure/identity.tf:173 =     path "identity/*" {
  deployments/infrastructure/identity.tf:254 =   member_entity_ids = [vault_identity_entity.operator.id]
  deployments/infrastructure/identity.tf:405 = ### `policies = []` on every one, deliberately. These groups carry no Vault
  deployments/infrastructure/identity.tf:432 =     "app-memex-admins" = [vault_identity_entity.operator.id]
  deployments/infrastructure/oidc.tf:28 = ### THE KEY needs no edit here: allowed_client_ids is deliberately NOT set
  deployments/infrastructure/oidc.tf:141 =   member_entity_ids = [vault_identity_entity.operator.id]
  deployments/infrastructure/oidc.tf:331 = ### A client's id_token_ttl may not exceed the verification_ttl of THE KEY IT
  deployments/infrastructure/oidc.tf:377 = ### API key with every request still returning 200 — silent, and exactly the
  deployments/infrastructure/oidc.tf:395 =   id_token_ttl     = 2592000 # 30d; must be <= the key's verification_ttl
  deployments/infrastructure/variables.tf:62 =   description = "Host the Vault OIDC provider advertises as its issuer. Baked into every issued token and into each consumer's client config, so changing it later means re-issuing everywhere. Uses the edge hostname, not the backend IP, so it survives a backend change."
  deployments/applications/secrets.tf:283 =   openviking_people = toset(["jasper", "veerle"])
  deployments/applications/secrets.tf:288 =   openviking_accounts = { for user in local.openviking_people : user => user }
  deployments/applications/services.tf:460 =       ov_conf = local.openviking_ov_conf
  deployments/applications/services.tf:502 = resource "null_resource" "openviking_users" {
  deployments/applications/services.tf:509 =     jobspec = sha1(nomad_job.openviking.jobspec)
  deployments/applications/services.tf:552 =         # creates the account, makes admin_user_id its first user with role
  deployments/applications/services/openviking/ov.conf.json:67 =     "auth_mode": "api_key",
  deployments/applications/services/openviking.hcl:70 =         network_mode = "host"
  scripts/check_openviking_config.py:42 = EXPECTED_AUTH_MODE = "api_key"
  scripts/check_openviking_config.py:288 =         "auth_mode": (_mutate(("server", "auth_mode"), "oidc"), "auth_mode"),
  cli/src/localstack_cli/commands/login.py:76 =     who = username or os.environ.get(USERNAME_ENV) or "operator"
  cli/tests/commands/test_auth_commands.py:252 =     assert session.username == "operator"
  cli/tests/commands/test_auth_commands.py:279 =     assert "logged in as operator" in stderr
  cli/tests/fixtures/cluster.py:85 =     "/v1/auth/userpass/login/operator": (200, json.dumps(LOGIN_RESPONSE).encode()),
  cli/tests/auth/test_live_login.py:43 =     return vault_cli("kv", "get", "-field=password", "secret/default/vault/operator")
  docs/cli-login.md:38 = The `operator` password lives in Vault at `secret/default/vault/operator`,
  docs/vault-human-auth.md:47 = - `secret/default/vault/operator`: the operator's username and password.
  .loop/scratch/OV3-openviking-vault-identity.plan-validator/vault_identity_store_oidc.go:537 = 	c.effectiveIssuer += "/v1/" + ns.Path + issuerPath
  .loop/scratch/OV3-openviking-vault-identity.plan-validator/vault_identity_store_oidc.go:473 = 				"invalid issuer, which must include only a scheme, host, "
  .loop/scratch/OV3-openviking-vault-identity.plan-validator/vault_identity_store_oidc.go:99 = 	Subject         string `json:"sub"`       // Entity ID
  .loop/scratch/OV3-openviking-vault-identity.plan-validator/vault_identity_store_oidc.go:361 = 					Default:     "24h",
  .loop/scratch/OV3-openviking-vault-identity.plan-validator/vault_oidc_provider.go:1504 = 	provider.effectiveIssuer += "/v1/" + ns.Path + "identity/oidc/provider/" + name
  .loop/scratch/OV3-openviking-vault-identity.plan-validator/openviking_server_auth_plugins_oidc.py:144 =         return ResolvedIdentity(role=Role.USER, account_id=account_id, user_id=user_id)
  .loop/scratch/OV3-openviking-vault-identity.plan-validator/openviking_server_auth_plugins_oidc.py:245 =             discovery_url = f"{self._config.issuer}{_DISCOVERY_PATH}"
  .loop/scratch/OV3-openviking-vault-identity.plan-validator/openviking_server_auth_plugins_api_key.py:279 =                 "Use a user/admin API key for data access, or trusted mode for upstream "
  .loop/scratch/OV3-openviking-vault-identity.plan-validator/trusted.py:104 =             if not hmac.compare_digest(api_key, configured_root_api_key):
  .loop/scratch/OV3-openviking-vault-identity.plan-validator/openviking_server_routers_admin.py:283 = @require_auth_root
---

rebound-by: JasperHG90 2026-09-07T04:33:09Z (reason: Applied the four required fixes from the plan-validator verdict, all inside its declared fix_sections (5, 6, 7, premises): corrected the section 5 non-goal that wrongly called the openviking_users provisioner unused when its jobspec trigger re-runs it on the config flip; rewrote P10 and P15 so the uninitialized-tree question is stated as unprobeable against the LIVE server only, with a local trusted-mode run of the pinned image named as the probe; added the six missed code-surface rows for R1's operator blast radius including the three default-run cli test lines; re-anchored R2's verification_ttl constraint from oidc.tf:377 to :331 and :395. Also took four of the reviewer's recommendations, same sections: P3 now cites the separate-field mechanism in identity_store_oidc_provider.go rather than inferring independence from the strings differing, P14 is promoted to demonstrated with the no-path issuer requirement stated, and R4 names the explicit jwks_uri shape. loopctl verify-plan returns valid.)

# Plan review: OV3-openviking-vault-identity

## Premise verdict

**PARTIALLY SOUND.**

The design's load-bearing chain holds and is now demonstrated rather than
asserted: Vault's identity-token `iss` really is `api_addr + /v1/identity/oidc`,
Q4 option (b) really produces the string the plan says to write into
`ov.conf.json`, the named OIDC provider really cannot be moved by that write,
and OpenViking really performs no account lookup and always resolves
`Role.USER`. Three things break underneath that: a §5 claim that the Terraform
provisioner can stay in place unused, a premise that the uninitialized-tree
question cannot be probed before the flip, and a §7 code surface that misses
five files the `operator` rename reaches.

Deterministic floor: `loopctl verify-plan OV3-openviking-vault-identity` returns
`valid`. Scratch created at
`.loop/scratch/OV3-openviking-vault-identity.plan-validator/`.

## Per-assumption findings

### The plan's stated premises

- **P1 — HOLDS.** The plan's own probe output is corroborated by Vault's source.
  `.loop/scratch/OV3-openviking-vault-identity.plan-validator/vault_identity_store_oidc.go:99`
  > 	Subject         string `json:"sub"`       // Entity ID

  Fetched with `gh api repos/hashicorp/vault/contents/vault/identity_store_oidc.go?ref=v1.18.3`.
  Lines 133-134 of the same file list `iat, aud, exp, iss, sub, namespace, nonce`
  as claims a template may not set, so the entity name can only ride a custom
  claim. The plan's decoded token and its template are consistent with both.

- **P2 — HOLDS.** Demonstrated from Vault's source, not merely measured.
  `.loop/scratch/OV3-openviking-vault-identity.plan-validator/vault_identity_store_oidc.go:532-537`
  > 	c.effectiveIssuer = c.Issuer
  > 	if c.effectiveIssuer == "" {
  > 		c.effectiveIssuer = i.redirectAddr
  > 	}
  >
  > 	c.effectiveIssuer += "/v1/" + ns.Path + issuerPath

  With `issuerPath = "identity/oidc"` (line 149) and no configured issuer, `iss`
  is `api_addr` + `/v1/identity/oidc`, which is exactly the
  `http://192.168.2.30:8200/v1/identity/oidc` the plan measured. The claim is
  structural, so it does not depend on re-reaching the cluster.

- **P3 — HOLDS, but the plan's stated reasoning is a non-sequitur.** The plan
  argues the provider issuer "is measured to be a different string already
  (P3), so setting `identity/oidc/config` cannot move it". Being different today
  does not entail being independent; both could be recomputed from one root with
  different suffixes. The conclusion survives for a better reason:
  `.loop/scratch/OV3-openviking-vault-identity.plan-validator/vault_oidc_provider.go:1499-1504`
  > 	provider.effectiveIssuer = provider.Issuer
  > 	if provider.effectiveIssuer == "" {
  > 		provider.effectiveIssuer = i.redirectAddr
  > 	}
  >
  > 	provider.effectiveIssuer += "/v1/" + ns.Path + "identity/oidc/provider/" + name

  The named provider reads its OWN `Issuer` (from `issuer_host` + `https_enabled`)
  and falls back to `redirectAddr`, never to `identity/oidc/config`. Writing the
  config issuer therefore cannot move `provider/lab`. Worth recording the real
  reason in the premise, because the fallback is `api_addr`: if `issuer_host` were
  ever dropped from `deployments/infrastructure/oidc.tf:118`, the provider would
  land on the raw IP rather than on the new config issuer.

- **P4 — HOLDS on the repo half.** `grep -rn vault_identity_oidc_role deployments/`
  returns nothing (empty output, exit 1). The live half (`vault list
  identity/oidc/role` returning "No value found") is not re-measurable from this
  sandbox; the plan records captured output for it.

- **P5 — UNCERTAIN — not independently verifiable here.** The container-side
  reachability probe needs the cluster. The plan carries captured stdout, which
  meets its own evidence bar. One gap worth noting inside the premise: the
  recorded edge result is a bare `edge https: 200` with no URL, while Q4 leans on
  it for "both routes are measured reachable". Under option (b) the URL that must
  answer is `https://vault.lab.orangecluster.nl/v1/identity/oidc/.well-known/openid-configuration`
  followed by the `jwks_uri` that document returns, because upstream builds the
  discovery URL from the configured issuer:
  `.loop/scratch/OV3-openviking-vault-identity.plan-validator/openviking_server_auth_plugins_oidc.py:245`
  > 	            discovery_url = f"{self._config.issuer}{_DISCOVERY_PATH}"

  Naming that exact URL in P5 costs one line and removes the ambiguity.

- **P6 — HOLDS on the repo half.** `deployments/infrastructure/identity.tf:173`
  > 	    path "identity/*" {

  The grant is on the cited line. The live `vault token capabilities` result is
  not re-measurable here.

- **P7 — UNCERTAIN — not independently verifiable here.** Needs the live server
  and the root key. The plan carries captured output.

- **P8 — HOLDS.** Demonstrated against upstream at the pinned tag.
  `.loop/scratch/OV3-openviking-vault-identity.plan-validator/openviking_server_auth_plugins_oidc.py:144`
  > 	        return ResolvedIdentity(role=Role.USER, account_id=account_id, user_id=user_id)

  `resolve_identity` maps both ids at lines 126-127, sanitizes them at 131-132
  with `_ALLOWED_IDENTIFIER_CHARS = re.compile(r"[^a-zA-Z0-9_.@-]")` (line 33),
  and returns without consulting any account store. Downstream,
  `openviking/server/auth/__init__.py:110-119` builds the `RequestContext`
  straight from the resolved identity. The sanitizer leaves `jasper` and `veerle`
  untouched, so the dispatcher's worry about mangled identifiers does not
  materialize for this repo's names.

- **P9 — HOLDS.**
  `.loop/scratch/OV3-openviking-vault-identity.plan-validator/openviking_server_routers_admin.py:282-283`
  > @router.post("/accounts")
  > @require_auth_root

- **P10 — BREAKS on its second half.** The first half is right, and the quoted
  denial is real:
  `.loop/scratch/OV3-openviking-vault-identity.plan-validator/openviking_server_auth_plugins_api_key.py:277-280`
  > 	            raise PermissionDeniedError(
  > 	                "ROOT API keys cannot access tenant-scoped data APIs in api_key mode. "
  > 	                "Use a user/admin API key for data access, or trusted mode for upstream "
  > 	                "identity assertion."
  > 	            )

  The plan quotes this message but stops one clause short of the sentence that
  refutes its own conclusion. Upstream names `trusted` mode as the mechanism for
  exactly this, and the trusted plugin gates on the root key and then takes the
  account and user from headers or the URL with no existence check:
  `.loop/scratch/OV3-openviking-vault-identity.plan-validator/trusted.py:104`
  > 	            if not hmac.compare_digest(api_key, configured_root_api_key):

  followed by `effective_account_id = explicit_account_id or x_openviking_account`
  (line 127) and a `get_request_context_checks` (lines 228-240) that only asserts
  the two values are PRESENT. The plan already knows this: R8 states it almost
  verbatim while correcting `docs/openviking.md:88`. So "cannot be probed today"
  is false as written. What is true is the narrower "cannot be probed against the
  live server without changing its auth_mode": the pinned image can be run
  locally in `trusted` mode with a root key, handed
  `X-OpenViking-Account: never-created`, and asked for a read and a write.

- **P11 — HOLDS.** `openviking/server/auth/plugins/api_key.py:97` at the pinned
  tag:
  > 	        # Silently ignore identity assertion headers in api_key mode.

  The stripping itself is the list comprehension at lines 50-52.

- **P12 — HOLDS.** `openviking/server/auth/oidc_config.py:32`
  > 	    model_config = {"extra": "forbid"}

  `identity_mapping.py:70` carries `fallback: Optional[str] = "default"` on
  `AccountMappingConfig` and `:89` carries `fallback: Optional[str] = None` on
  `UserMappingConfig`, both with `extra: forbid` at `:74` and `:93`. The mapper
  applies the fallback at `:190-191` and `map_account_id` raises `ValueError` at
  `:251-256` when the result is still `None`, which `oidc.py:133-135` converts to
  `UnauthenticatedError`. R4's `fallback: null` is therefore genuinely
  fail-closed, exactly as claimed.

- **P13 — HOLDS.** Probe against the pinned binary at
  `deployments/infrastructure/.terraform/providers/registry.terraform.io/hashicorp/vault/5.3.0/linux_arm64/terraform-provider-vault_v5.3.0_x5`:

      vault_identity_oidc_role         PRESENT
      vault_identity_oidc_key          PRESENT
      vault_identity_oidc              PRESENT

  `deployments/infrastructure/.terraform.lock.hcl:88` pins `version = "5.3.0"`.
  The mixing prohibition is real, fetched from the provider's own docs at tag
  v5.3.0 (`website/docs/r/identity_oidc_key.html.md:25-27`):
  > At this time you cannot use an OIDC Named Key inline list of Allowed Client IDs
  > in conjunction with any Allowed Client ID resources. Doing so will cause
  > a conflict of the list of Allowed Client IDs for the named Key.

  The new key's inline list is safe because no standalone resource will point at
  it, and R2's static `client_id` also avoids the Terraform cycle that
  `deployments/infrastructure/oidc.tf:31` warns about. Worth a sentence in R2,
  since the repo comment gives the cycle as its reason and the plan quotes only
  the registration half.

- **P14 — HOLDS, and is now demonstrated rather than documented.** The premise
  disclaims measurement; Vault's source settles it without one.
  `.loop/scratch/OV3-openviking-vault-identity.plan-validator/vault_identity_store_oidc.go:361`
  > 					Default:     "24h",

  and `:473-474`
  > 				"invalid issuer, which must include only a scheme, host, " +
  > 					"and optional port (e.g. https://example.com:8200)"

  and `:478-481`
  > 			Warnings: []string{`If "issuer" is set explicitly, all tokens must be ` +
  > 				`validated against that address, including those issued by secondary ` +
  > 				`clusters. Setting issuer to "" will restore the default behavior of ` +
  > 				`using the cluster's api_addr as the issuer.`},

  Three consequences the plan gets right and can now assert instead of hedging:
  the write must carry `https://vault.lab.orangecluster.nl` with NO path (Vault
  rejects a path outright), the resulting `iss` is that plus `/v1/identity/oidc`,
  which is byte for byte the string Q4 (b) tells the implementer to configure,
  and `""` restores the default. The reconciliation the dispatcher asked about
  works: OpenViking builds discovery from the configured issuer (`oidc.py:245`),
  reads `jwks_uri` out of that document (`:258`), and validates with
  `verify_iss: True, issuer=self._config.issuer` (`:211-213`), so one string
  drives all three and there is no second place for it to drift.

- **P15 — UNCERTAIN on the answer, BREAKS on the reason.** The answer is
  genuinely unknown and the plan is right to refuse to infer it. The reason it
  gives ("It cannot be probed today (P10)") is the part that fails, per P10 above.

- **P16 — UNCERTAIN, correctly.** The plan asks for the check rather than
  asserting the outcome, which is the right shape. One pointer for the
  implementer: `openviking/server/auth/plugins/oidc.py:355-358` returns `False`
  from `requires_api_key_manager()`, which is where the answer starts.

- **P17 — HOLDS.** `grep -rn veerle deployments/` returns exactly one line:
  `deployments/applications/secrets.tf:283`
  > 	  openviking_people = toset(["jasper", "veerle"])

### Implicit premises the plan does not state

- **P18 (added) — BREAKS. The seed and key apparatus cannot "stay in place,
  unused".** §5 says the key-reconcile arm of `openviking_users` stays in place,
  unused, so the change is one revert away from working. It does not stay unused.
  `deployments/applications/services.tf:509`
  > 	    jobspec = sha1(nomad_job.openviking.jobspec)

  and `deployments/applications/services.tf:460`
  > 	      ov_conf = local.openviking_ov_conf

  R4 edits `ov.conf.json`, so `local.openviking_ov_conf` changes, so the jobspec
  changes, so this trigger changes and the `null_resource` is recreated. It has
  `depends_on = [nomad_job.openviking]` (`:578`) and the job registers with
  `detach = false` (`:446`), so the provisioner runs against a server that is
  already in `oidc` mode. Both curl arms are guarded (`case "$code" in 200|201|409)
  ;; *) ... exit 1`), so the apply fails.

  §7 and §9 already know this ("Q1 decides its fate"; "that call fails and takes
  the apply with it"), which makes §5 the odd one out rather than the whole plan
  wrong. But an implementer following §5 literally ships a step 3 that cannot
  apply, and Q1's sub-options only fire "If the probe shows an uninitialized tree
  fails" while the probe itself is deferred until after a flip that this
  provisioner prevents. That is a small circle, and §5 is where it closes.

  Precision note in the same area: §7's row for `:502` says the call "403s under
  `oidc`". It 401s. The provisioner sends `X-API-Key` and no `Authorization`
  header, so `_extract_token` (`oidc.py:154-175`) finds no bearer token, the root
  key has no dots so the JWT fallback at `:171` misses, and `:104-105` raises
  `UnauthenticatedError("Missing OIDC JWT token")`. The 403 the plan names is
  what a VALID token would get from `require_auth_role` once
  `api_key_manager` is absent. Both fail the apply; only one is the message an
  operator will see in the log.

- **P19 (added) — BREAKS. §7's code surface does not cover R1's blast radius.**
  Q5's recommended rename makes the `operator` entity and its KV path disappear.
  Five files name one or the other and none is in §7 or excluded in §5:

  `deployments/infrastructure/oidc.tf:141`
  > 	  member_entity_ids = [vault_identity_entity.operator.id]

  A third holder of the entity id, beside the two §7 rows. §9 risk 1 gestures at
  "the OIDC assignments" but the table homes no anchor for it. (This one fails
  loudly at `terraform validate` rather than silently, which is worth correcting
  in §9 risk 1 too: a missed `vault_identity_entity.operator.id` reference is a
  reference to an undeclared resource, not a silent tier loss. The silent case is
  the `admin` group's `external_member_entity_ids = true` at `:383`, which the
  risk also names and which is the real hazard.)

  `cli/tests/commands/test_auth_commands.py:252`
  > 	    assert session.username == "operator"

  `cli/tests/commands/test_auth_commands.py:279`
  > 	    assert "logged in as operator" in stderr

  `cli/tests/fixtures/cluster.py:85`
  > 	    "/v1/auth/userpass/login/operator": (200, json.dumps(LOGIN_RESPONSE).encode()),

  These three are in the DEFAULT pytest run (no marker), and §8 explicitly says
  "the `login.py:76` edit must keep the suite green". Changing the default
  username turns them red, and the edits that fix them have no home in §7. Note
  also that `cli/src/localstack_cli/commands/login.py:60` carries the same default
  in its help text, so the §7 row's `:76` anchor is one of two lines to change in
  a file the table does list.

  `cli/tests/auth/test_live_login.py:43`
  > 	    return vault_cli("kv", "get", "-field=password", "secret/default/vault/operator")

  Marked `cluster` and excluded from the default run, so no gate catches it. That
  is the case for listing it, not against.

  `docs/cli-login.md:38`
  > The `operator` password lives in Vault at `secret/default/vault/operator`,

  `docs/vault-human-auth.md:47`
  > - `secret/default/vault/operator`: the operator's username and password.

  R8 rewrites `docs/openviking.md` only. These two documents describe the human
  login path R1 rewrites and go stale in the same commit.

- **P20 (added) — HOLDS, and is worth stating.** Under `oidc` the OIDC plugin is
  the only authenticator, so the root key stops being a credential on every
  route, not just the data routes. `oidc.py:355-358` returns `False` from
  `requires_api_key_manager()`, and `require_auth_role` raises before it ever
  reads a role when the manager is absent
  (`openviking/server/auth/__init__.py:306-308`). The plan's Q3 and its §5
  "Server-side admin under OIDC" non-goal are honest about the consequence.

## Most dangerous assumption

**P18 — that the provisioner can stay in place, unused.** Every other finding
here is a citation to sharpen or a file to add. This one decides whether the
ticket's own step 3 can apply at all. If the implementer reads §5 as written and
leaves `null_resource.openviking_users` alone, the flip's apply fails on the
first account POST, and the runtime probe Q1 defers to "implementation time"
never gets to run, because it needs the flip that the provisioner blocks.

## Required fixes

1. **§5.** Correct the non-goal. The seed and key apparatus can stay, but the
   `openviking_users` provisioner does not stay "unused": its `jobspec` trigger
   (`deployments/applications/services.tf:509`) changes with `ov_conf`
   (`:460`), so it re-runs on the flip and its guarded curls fail the apply. Say
   what the diff does about it, or move that decision into §6 as a requirement.
   Section 7's row for `:502` and §10's step 3 already point at it; §5 must stop
   contradicting them.

2. **Premises.** Rewrite P10's second half and P15's reason. "Cannot be probed
   today" is refuted by upstream's own denial message
   (`api_key.py:277-280`) and by `trusted.py:98-150`, which asserts an arbitrary
   account and user behind a constant-time root-key compare with no existence
   check. The accurate premise is that the question cannot be probed against the
   LIVE server without changing its `auth_mode`, and that a local run of the
   pinned image in `trusted` mode probes it before the flip.

3. **§7.** Add rows for `deployments/infrastructure/oidc.tf:141`,
   `cli/tests/commands/test_auth_commands.py:252` and `:279`,
   `cli/tests/fixtures/cluster.py:85`, `cli/tests/auth/test_live_login.py:43`,
   `docs/cli-login.md:38` and `:44`, and `docs/vault-human-auth.md:20` and `:47`
   — or state in §5 that the docs and the cluster-marked test are deliberately
   deferred. The three default-run cli test lines cannot be deferred, because §8
   commits to keeping that suite green. Also fix the `:502` row's "403s under
   `oidc`" to "401s: the provisioner sends no bearer token".

4. **§6, R2.** Re-anchor the `verification_ttl` constraint.
   `deployments/infrastructure/oidc.tf:377`
   > ### API key with every request still returning 200 — silent, and exactly the

   That line is about `access_token_ttl` caching and does not support the claim
   attached to it. The constraint is recorded at `:331`
   > ### A client's id_token_ttl may not exceed the verification_ttl of THE KEY IT

   and at `:395`
   >   id_token_ttl     = 2592000 # 30d; must be <= the key's verification_ttl

## Recommended, not required

- **P3.** Replace the "different string already" inference with the real reason
  (`identity_store_oidc_provider.go:1499-1504`: separate field, separate
  fallback). The current wording would license the same inference in a case where
  it is false.
- **P14 and Q4.** Both can be promoted from "documented, not probed" to
  demonstrated, using the two Vault source anchors above. In particular the
  issuer write must carry NO path, which the current phrasing ("the edge base
  URL") implies but does not state, and which Vault rejects outright.
- **R4 / Q4.** Upstream supports an explicit `jwks_uri` that takes precedence
  over discovery (`oidc.py:237-238`). That gives Q4 a third option the fork does
  not name: leave the issuer unset and point `jwks_uri` at the edge, keeping the
  key fetch on TLS without a cluster-wide Vault write. Worth one line even if the
  recommendation stays (b).
- **P5.** Name the exact edge URL the `edge https: 200` result came from, since
  Q4 (b) depends on the discovery path specifically.
- **§9 risk 1.** Split the two cases. A missed `vault_identity_entity.operator.id`
  reference fails `terraform validate` loudly; the silent loss is the `admin`
  group's `external_member_entity_ids = true` (`identity.tf:383`).

## Contract hygiene

- **Anchors.** Every §5 through §10 anchor was opened. All resolve. One does not
  support its claim (`oidc.tf:377`, fix 4); the rest do, including the ones most
  likely to have drifted (`identity.tf:405`, `services.tf:418`,
  `check_openviking_config.py:288`, `.pre-commit-config.yaml:68`, `justfile:18`).
- **Gates.** Discovered, not assumed. `.loop/config.json` `gates` is
  `['just pre_commit']`; `justfile:18` is `pre_commit:`; every hook id §8 names is
  at the line it names.
- **Non-goals.** Explicit, and §5 is unusually clear about Hermes breaking. On the
  dispatcher's fourth question: the plan is honest rather than hand-waving. The
  front matter says "Hermes BREAKS the moment auth_mode flips", §5 repeats it in
  bold, §9 lists it as failure mode 3, and R8 requires it be written into the
  docs. Shipping this ticket alone does leave the cluster part-broken, and the
  plan says so in four places instead of hiding it. That is a decision for the
  operator, not a defect in the plan.
- **Tests homed.** The seven new mutants all live in
  `scripts/check_openviking_config.py`, which §7 lists and marks as their home.
  The gap is the cli tests §8 commits to keeping green (fix 3).
- **Forks surfaced.** Q1 through Q6 each carry options and a recommendation, and
  Q1 carries the `unmeasurable-requirement` tag with all four contract options
  named. The runtime requirement genuinely has no producer in the repo, and the
  plan says so and recommends `widen-surface`. Correct handling.
- **Requirements reachable.** R4 and R5 name `scripts/check_openviking_config.py`
  as producer; R1 is reachable through the `terraform plan` step §8 names; R2, R3
  and the end-to-end claim fall under Q1's declared unmeasurability. R6, R7 and R8
  have no producer and §8 says plainly that no hook checks them and the reviewer
  does. That is a declared proxy stated in the open, not a silent gap.
- **Advisory, reverse direction.** `.pre-commit-config.yaml` sits in §7 with
  "Touch only if a path moves", so no requirement reaches it. Observation only.

Scratch removed at end of pass, except the findings ledger and the fetched
upstream sources, which are left under
`.loop/scratch/OV3-openviking-vault-identity.plan-validator/` for the next cycle.
