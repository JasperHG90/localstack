"""Spike: does SeaweedFS 4.48 refuse a StringEquals trust condition on a claim the token lacks?

Adapted from spike:ci-openviking-sync/1. Dev Vault 2.0.3 mints identity tokens
(aud `seaweedfs`) for two userpass entities: `operator` and `other`. SeaweedFS
4.48 trusts Vault's issuer beside a Nomad provider, as local.seaweedfs_iam does,
with two roles:
  ci-a-x         StringEquals oidc:ci_repository = a/x
  local-ov-sync  StringEquals oidc:local_ov_sync = JasperHG90/local
                 and oidc:sub = <operator entity id>
Tokens: ci (ci_repository only), local (local_ov_sync only, operator and other
entity), none (an unrelated claim only). Exits 0 only when every required
check holds. Containers and network are named ovsq-*.
"""
import base64, json, os, subprocess, sys, tempfile, time

VAULT_IMG, SWFS_IMG, AWS_IMG = "hashicorp/vault:2.0.3", "chrislusf/seaweedfs:4.48", "amazon/aws-cli:2.27.0"
NET, VAULT, SWFS = "ovsq-net", "ovsq-vault", "ovsq-swfs"
VAULT_HOST = f"http://{VAULT}:8200"
ISSUER = f"{VAULT_HOST}/v1/identity/oidc"
S3 = f"http://{SWFS}:8333"
LOCAL = "JasperHG90/local"
ROLE = lambda n: f"arn:aws:iam::role/{n}"
results = []


def sh(*a, check=True, inp=None):
    r = subprocess.run(a, capture_output=True, text=True, input=inp)
    if check and r.returncode:
        raise RuntimeError(f"{a}: {r.stdout}\n{r.stderr}")
    return r


def record(tid, required, ok, detail):
    results.append((tid, required, ok))
    print(f"[{'PASS' if ok else 'FAIL'}]{'' if required else ' (info)'} {tid}: {detail}", flush=True)


def vault(*args, token="root"):
    return sh("docker", "exec", "-e", "VAULT_ADDR=http://127.0.0.1:8200", "-e", f"VAULT_TOKEN={token}",
              VAULT, "vault", *args).stdout


def cleanup():
    sh("docker", "rm", "-f", VAULT, SWFS, check=False)
    sh("docker", "network", "rm", NET, check=False)


def claims(tok):
    return json.loads(base64.urlsafe_b64decode(tok.split(".")[1] + "=="))


def setup_vault():
    sh("docker", "run", "-d", "--name", VAULT, "--network", NET, "--cap-add", "IPC_LOCK",
       "-e", "VAULT_DEV_ROOT_TOKEN_ID=root", VAULT_IMG, "server", "-dev", "-dev-listen-address=0.0.0.0:8200")
    for _ in range(30):
        if sh("docker", "exec", "-e", "VAULT_ADDR=http://127.0.0.1:8200", VAULT, "vault", "status", check=False).returncode == 0:
            break
        time.sleep(1)
    print(vault("version").strip())
    vault("write", "identity/oidc/config", f"issuer={VAULT_HOST}")
    vault("write", "identity/oidc/key/identity-tokens", "algorithm=RS256", "allowed_client_ids=seaweedfs")
    for name, tmpl in (("ci", {"ci_repository": "a/x"}), ("local", {"local_ov_sync": LOCAL}),
                       ("none", {"unrelated": "x"})):
        vault("write", f"identity/oidc/role/{name}", "key=identity-tokens", "client_id=seaweedfs", "ttl=15m",
              "template=" + json.dumps(tmpl))
    sh("docker", "exec", "-i", "-e", "VAULT_ADDR=http://127.0.0.1:8200", "-e", "VAULT_TOKEN=root", VAULT,
       "vault", "policy", "write", "mint", "-", inp='path "identity/oidc/token/*" { capabilities = ["read"] }\n')
    vault("auth", "enable", "userpass")
    toks = {}
    for user in ("operator", "other"):
        vault("write", f"auth/userpass/users/{user}", "password=pw", "policies=mint")
        tok = json.loads(vault("write", "-format=json", f"auth/userpass/login/{user}", "password=pw"))["auth"]["client_token"]
        for role in ("ci", "local", "none"):
            toks[(user, role)] = json.loads(vault("read", "-format=json", f"identity/oidc/token/{role}", token=tok))["data"]["token"]
    for k in (("operator", "ci"), ("operator", "local"), ("operator", "none"), ("other", "local")):
        print(f"{k} claims:", json.dumps(claims(toks[k])))
    return toks, claims(toks[("operator", "local")])["sub"]


def policy(prefix):
    return {"Version": "2012-10-17", "Statement": [{
        "Effect": "Allow", "Action": ["s3:GetObject", "s3:PutObject", "s3:DeleteObject"],
        "Resource": [f"arn:aws:s3:::ov-sync/{prefix}/*"]}]}


def trust(cond):
    return {"Version": "2012-10-17", "Statement": [{
        "Effect": "Allow", "Principal": {"Federated": "vault"},
        "Action": "sts:AssumeRoleWithWebIdentity",
        "Condition": {"StringEquals": cond}}]}


def iam_config(op_sub):
    return {
        "sts": {"tokenDuration": "1h", "maxSessionLength": "12h", "issuer": "seaweedfs-sts",
                "signingKey": base64.b64encode(os.urandom(32)).decode()},
        "policy": {"defaultEffect": "Deny"},
        "providers": [
            {"name": "nomad", "type": "oidc", "enabled": True,
             "config": {"issuer": "https://nomad.lab.invalid", "clientId": "seaweedfs"}},
            {"name": "vault", "type": "oidc", "enabled": True,
             "config": {"issuer": ISSUER, "clientId": "seaweedfs"}},
        ],
        "policies": [{"name": "ci-a-x", "document": policy("a/x")},
                     {"name": "local-ov-sync", "document": policy(LOCAL)}],
        "roles": [
            {"roleName": "ci-a-x", "roleArn": ROLE("ci-a-x"),
             "trustPolicy": trust({"oidc:ci_repository": "a/x"}), "attachedPolicies": ["ci-a-x"]},
            {"roleName": "local-ov-sync", "roleArn": ROLE("local-ov-sync"),
             "trustPolicy": trust({"oidc:local_ov_sync": LOCAL, "oidc:sub": op_sub}),
             "attachedPolicies": ["local-ov-sync"]},
        ],
    }


def setup_swfs(tmp, op_sub):
    p = os.path.join(tmp, "iam.json")
    json.dump(iam_config(op_sub), open(p, "w"), indent=1)
    sh("docker", "create", "--name", SWFS, "--network", NET, SWFS_IMG,
       "server", "-dir=/data", "-s3", "-s3.port=8333", "-s3.iam.config=/iam.json",
       "-s3.iam.readOnly=false", "-master.volumeSizeLimitMB=32", "-volume.max=8")
    sh("docker", "cp", p, f"{SWFS}:/iam.json")
    sh("docker", "start", SWFS)
    for _ in range(60):
        time.sleep(2)
        sh("docker", "exec", SWFS, "sh", "-c", "echo 's3.bucket.create -name ov-sync' | weed shell 2>&1", check=False)
        ls = sh("docker", "exec", SWFS, "sh", "-c", "echo s3.bucket.list | weed shell 2>&1", check=False).stdout
        if "ov-sync" in ls:
            for d in ("a/x", LOCAL):
                sh("docker", "exec", SWFS, "sh", "-c",
                   f"echo seed > /tmp/seed.txt && weed filer.copy /tmp/seed.txt http://127.0.0.1:8888/buckets/ov-sync/{d}/")
            return
    raise RuntimeError("seaweedfs did not come up:\n" + sh("docker", "logs", SWFS, check=False).stderr[-3000:])


def aws(*args, creds=None):
    env = ["-e", "AWS_DEFAULT_REGION=us-east-1"]
    if creds:
        env += ["-e", f"AWS_ACCESS_KEY_ID={creds['AccessKeyId']}", "-e", f"AWS_SECRET_ACCESS_KEY={creds['SecretAccessKey']}",
                "-e", f"AWS_SESSION_TOKEN={creds['SessionToken']}"]
    else:
        env += ["-e", "AWS_ACCESS_KEY_ID=x", "-e", "AWS_SECRET_ACCESS_KEY=x"]
    r = sh("docker", "run", "--rm", "--network", NET, *env, AWS_IMG, "--endpoint-url", S3, *args, check=False)
    return r.returncode, (r.stdout + r.stderr).strip()


def assume(tok, role):
    rc, out = aws("sts", "assume-role-with-web-identity", "--role-arn", ROLE(role),
                  "--role-session-name", "spike", "--web-identity-token", tok, "--output", "json")
    if rc:
        return None, out.splitlines()[-1][:300]
    return json.loads(out)["Credentials"], "creds issued"


def op(creds, verb, key):
    if verb == "put":
        rc, out = aws("s3api", "put-object", "--bucket", "ov-sync", "--key", key, "--body", "/etc/hostname", creds=creds)
    elif verb == "get":
        rc, out = aws("s3api", "get-object", "--bucket", "ov-sync", "--key", key, "/dev/stdout", creds=creds)
    else:
        rc, out = aws("s3api", "delete-object", "--bucket", "ov-sync", "--key", key, creds=creds)
    if rc == 0:
        return "OK"
    return "AccessDenied" if "AccessDenied" in out else "ERR " + out.splitlines()[-1][:200]


def main():
    cleanup()
    tmp = tempfile.mkdtemp()
    sh("docker", "network", "create", NET)
    try:
        toks, op_sub = setup_vault()
        setup_swfs(tmp, op_sub)
        ci, loc, none, loc_other = (toks[("operator", "ci")], toks[("operator", "local")],
                                    toks[("operator", "none")], toks[("other", "local")])

        c, d = assume(ci, "ci-a-x")
        record("1 control: ci token -> ci-a-x issues creds", True, c is not None, d)
        c_loc, d = assume(loc, "local-ov-sync")
        record("2 control: operator local token -> local-ov-sync issues creds", True, c_loc is not None, d)
        c, d = assume(loc, "ci-a-x")
        record("3 local token (no ci_repository claim) -> ci-a-x REFUSED", True, c is None, d)
        c, d = assume(ci, "local-ov-sync")
        record("4 ci token (no local_ov_sync claim, right sub) -> local-ov-sync REFUSED", True, c is None, d)
        c, d = assume(none, "ci-a-x")
        record("5 token with neither claim -> ci-a-x REFUSED", True, c is None, d)
        c, d = assume(none, "local-ov-sync")
        record("5 token with neither claim (right sub) -> local-ov-sync REFUSED", True, c is None, d)
        c, d = assume(loc_other, "local-ov-sync")
        record("6 local token, other entity's sub -> local-ov-sync REFUSED", True, c is None, d)

        if c_loc:
            for verb, key in (("put", f"{LOCAL}/notes/f.md"), ("get", f"{LOCAL}/notes/f.md"),
                              ("get", f"{LOCAL}/seed.txt"), ("delete", f"{LOCAL}/notes/f.md")):
                res = op(c_loc, verb, key)
                record(f"7 local-ov-sync {verb} ov-sync/{key} OK", True, res == "OK", res)
            for verb, key in (("put", "JasperHG90/localx/evil.md"), ("put", "JasperHG90/evil.md"),
                              ("put", "a/x/evil.md"), ("delete", "a/x/seed.txt"), ("put", "evil.md")):
                res = op(c_loc, verb, key)
                record(f"8 local-ov-sync {verb} ov-sync/{key} denied", True, res == "AccessDenied", res)
    finally:
        logs = sh("docker", "logs", SWFS, check=False)
        print("\n== seaweedfs log tail (oidc/sts/trust lines)")
        for line in (logs.stdout + logs.stderr).splitlines():
            if any(w in line.lower() for w in ("oidc", "sts", "provider", "jwks", "trust", "condition")):
                print(line[:300])
        cleanup()

    failed = [r for r in results if r[1] and not r[2]]
    print(f"\nrequired checks: {sum(1 for r in results if r[1])}, failed: {len(failed)}")
    sys.exit(1 if failed or not results else 0)


main()
