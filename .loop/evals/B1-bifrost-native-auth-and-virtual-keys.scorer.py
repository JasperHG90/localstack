#!/usr/bin/env python3
"""Eval scorer for B1-bifrost-native-auth-and-virtual-keys.

Static-config guardrail checks (9 scenarios) against the rendered HCL/TF.
No live infra interaction. Exit 0 only if every scenario passes.
Run from the repo root (the ticket worktree).
"""
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]  # worktree/.loop/evals/<file> -> worktree root
APP = ROOT / "deployments" / "applications"
INF = ROOT / "deployments" / "infrastructure"
BIFROST_HCL = APP / "services" / "bifrost.hcl"
HERMES_HCL = APP / "services" / "hermes.hcl"
APP_SERVICES = APP / "services.tf"
APP_PROVIDERS = APP / "providers.tf"
APP_SECRETS = APP / "secrets.tf"
HAPROXY_HCL = INF / "services" / "haproxy.hcl"
PROM_HCL = INF / "services" / "prometheus.hcl"
INF_SERVICES = INF / "services.tf"
INF_SECRETS = INF / "secrets.tf"
BOOTSTRAP_POLICY = (
    ROOT / "bootstrap" / "roles" / "nomad_server" / "templates"
    / "vault_nomad_workloads.hcl.j2"
)


def read(p: Path) -> str:
    return p.read_text()


def block(text: str, start: str) -> str:
    """Return the text from `start` to the closing brace at the same depth."""
    i = text.find(start)
    if i < 0:
        return ""
    depth = 0
    out = []
    for ch in text[i:]:
        out.append(ch)
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                break
    return "".join(out)


results = []


def check(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, ok, detail))
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" :: {detail}" if detail and not ok else ""))


# 1. Bifrost config.json enables native auth + gates inference.
cfg = read(BIFROST_HCL)
s1 = (
    "governance" in cfg
    and "auth_config" in cfg
    and re.search(r'"is_enabled"\s*:\s*true', cfg) is not None
    and "env.BIFROST_ADMIN_USERNAME" in cfg
    and "env.BIFROST_ADMIN_PASSWORD" in cfg
    and re.search(r'"enforce_auth_on_inference"\s*:\s*true', cfg) is not None
)
check("1. bifrost governance.auth_config + enforce_auth_on_inference enabled", s1)

# 2. Admin creds come from Vault, not inlined.
s2 = (
    "BIFROST_ADMIN_USERNAME" in cfg
    and "BIFROST_ADMIN_PASSWORD" in cfg
    and "bifrost_credentials_secret" in cfg
    and "default/bifrost/credentials" in read(APP_SERVICES)
    and "bifrost_credentials_secret" in read(APP_SERVICES)
)
check("2. admin creds rendered from Vault default/bifrost/credentials", s2)

# 3. Hermes uses the issued key, not the hardcoded value; explicit depends_on.
hermes = read(HERMES_HCL)
app_svc = read(APP_SERVICES)
hermes_block = block(app_svc, 'resource "nomad_job" "hermes"')
s3 = (
    "hermes-local" not in hermes
    and "BIFROST_API_KEY" in hermes
    and "bifrost_key_secret" in hermes
    and "vault_kv_secret_v2.bifrost_hermes_key" in hermes_block
)
check("3. hermes reads BIFROST_API_KEY from Vault + depends_on the key secret", s3)

# 4. Hermes virtual key is allow-all for ollama + gemini (no deny-all footgun).
vk_match = re.search(
    r'resource\s+"bifrost_virtual_key"\s+"hermes"\s*\{', app_svc + read(APP_SECRETS)
)
vk_text = vk_match.group(0) if vk_match else ""
vk_block = block(app_svc + read(APP_SECRETS), 'resource "bifrost_virtual_key" "hermes"') if vk_text else ""
s4 = (
    bool(vk_block)
    and '"ollama"' in vk_block
    and '"gemini"' in vk_block
    and 'key_ids' in vk_block
    and '"*"' in vk_block
    and 'allowed_models' in vk_block
)
check("4. bifrost_virtual_key.hermes allow-all (ollama+gemini, key_ids/allowed_models=['*'])", s4)

# 5. Virtual key stored under Hermes's own Vault prefix.
sec = read(APP_SECRETS)
s5 = (
    'resource "vault_kv_secret_v2" "bifrost_hermes_key"' in sec
    and "default/hermes/bifrost" in sec
    and "API_KEY" in sec
    and "bifrost_virtual_key.hermes.value" in sec
)
check("5. vault_kv_secret_v2.bifrost_hermes_key at default/hermes/bifrost (API_KEY)", s5)

# 6. HAProxy no longer gates Bifrost (but still gates phoenix/mlflow).
def haproxy_stanza(text: str, name: str) -> str:
    """Slice a haproxy `backend <name>` / `use_backend <name>` directive's
    own stanza: from the `backend <name>` line to the next top-level stanza
    or the heredoc terminator. Matches the standalone `backend` directive,
    not `use_backend`."""
    needle = f"\nbackend {name}\n"
    i = text.find(needle)
    if i < 0:
        return ""
    rest = text[i + len(needle):]
    # stanza ends at the next blank-line-separated directive or heredoc end
    m = re.search(r"\n(?:backend |frontend |userlist |defaults |global |        EOH)", rest)
    return rest[: m.start()] if m else rest


hap = read(HAPROXY_HCL)
bifrost_backend = haproxy_stanza(hap, "bifrost")
s6 = (
    "http-request auth" not in bifrost_backend
    and "userlist openfang_users" in hap
    and hap.count("http-request auth") >= 2  # phoenix + mlflow remain
)
check("6. haproxy backend bifrost has no http-request auth; phoenix/mlflow keep theirs", s6, bifrost_backend.strip()[:120])

# 7. Prometheus scrapes /metrics with basic_auth via a dedicated job.
prom = read(PROM_HCL)
tags_match = re.search(r'tags\s*=\s*\[[^\]]*\]', cfg)
s7 = (
    "job_name: bifrost" in prom
    and "basic_auth" in prom
    and "bifrost_admin_secret" in prom
    and re.search(r'vault\s*\{', prom) is not None
    and (tags_match is None or '"prometheus"' not in tags_match.group(0))
)
check("7. prometheus dedicated bifrost job with basic_auth; bifrost tag dropped; vault{} added", s7)

# 8. Synced admin-creds copy in the infra layer.
inf_sec = read(INF_SECRETS)
inf_svc = read(INF_SERVICES)
prom_block = block(inf_svc, 'resource "nomad_job" "prometheus"')
s8 = (
    'data "vault_kv_secret_v2" "bifrost_admin"' in inf_sec
    and "default/bifrost/credentials" in inf_sec
    and "default/prometheus/bifrost-admin" in inf_sec
    and "username" in inf_sec
    and "password" in inf_sec
    and "bifrost_admin_secret" in prom_block
)
check("8. infra synced copy default/prometheus/bifrost-admin + prometheus var", s8)

# 9. Bootstrap Vault policy untouched.
diff = subprocess.run(
    ["git", "diff", "main", "--", str(BOOTSTRAP_POLICY.relative_to(ROOT))],
    cwd=ROOT, capture_output=True, text=True,
)
s9 = diff.stdout.strip() == "" and diff.returncode == 0
check("9. bootstrap vault_nomad_workloads.hcl.j2 unchanged vs main", s9, diff.stdout[:200])

passed = sum(1 for _, ok, _ in results if ok)
print(f"\n{passed}/{len(results)} scenarios passed")
sys.exit(0 if passed == len(results) else 1)