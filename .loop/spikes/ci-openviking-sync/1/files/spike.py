"""Spike: does SeaweedFS 4.48 STS trust Vault identity tokens and scope a role to a prefix?

Dev Vault 2.0.3 (the cluster's version) mints identity tokens with a literal
ci_repository claim and audience `seaweedfs`. SeaweedFS 4.48 trusts Vault's
identity issuer as a second OIDC provider beside a Nomad one, with roles
ci-a-x and ci-b-y pinned by StringEquals on oidc:ci_repository and policies on
arn:aws:s3:::ov-sync/<owner>/<repo>/*. aws-cli 2.27.0 does the STS swap and the
S3 calls. Everything runs on a throwaway docker network (containers sync1-*).
Exits 0 only when every required check holds.
"""
import base64, json, os, subprocess, sys, tempfile, time

VAULT_IMG, SWFS_IMG, AWS_IMG = "hashicorp/vault:2.0.3", "chrislusf/seaweedfs:4.48", "amazon/aws-cli:2.27.0"
NET, VAULT, SWFS = "sync1-net", "sync1-vault", "sync1-swfs"
VAULT_HOST = f"http://{VAULT}:8200"
ISSUER = f"{VAULT_HOST}/v1/identity/oidc"
S3 = f"http://{SWFS}:8333"
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


def setup_vault():
    sh("docker", "run", "-d", "--name", VAULT, "--network", NET, "--cap-add", "IPC_LOCK",
       "-e", "VAULT_DEV_ROOT_TOKEN_ID=root", VAULT_IMG, "server", "-dev", "-dev-listen-address=0.0.0.0:8200")
    for _ in range(30):
        if sh("docker", "exec", "-e", "VAULT_ADDR=http://127.0.0.1:8200", VAULT, "vault", "status", check=False).returncode == 0:
            break
        time.sleep(1)
    print(vault("version").strip())
    # Bare host, as oidc.tf does; Vault appends /v1/identity/oidc itself.
    vault("write", "identity/oidc/config", f"issuer={VAULT_HOST}")
    vault("write", "identity/oidc/key/identity-tokens", "algorithm=RS256", "allowed_client_ids=seaweedfs,openviking")
    for name, repo, aud in (("ci-a-x", "a/x", "seaweedfs"), ("ci-b-y", "b/y", "seaweedfs"),
                            ("ci-a-x-wrongaud", "a/x", "openviking")):
        vault("write", f"identity/oidc/role/{name}", "key=identity-tokens", f"client_id={aud}", "ttl=15m",
              "template=" + json.dumps({"ci_repository": repo}))
    # identity tokens need an entity; the root token has none, so log in as a user.
    sh("docker", "exec", "-i", "-e", "VAULT_ADDR=http://127.0.0.1:8200", "-e", "VAULT_TOKEN=root", VAULT,
       "vault", "policy", "write", "mint", "-", inp='path "identity/oidc/token/*" { capabilities = ["read"] }\n')
    vault("auth", "enable", "userpass")
    vault("write", "auth/userpass/users/ci", "password=pw", "policies=mint")
    tok = json.loads(vault("write", "-format=json", "auth/userpass/login/ci", "password=pw"))["auth"]["client_token"]
    toks = {}
    for name in ("ci-a-x", "ci-b-y", "ci-a-x-wrongaud"):
        toks[name] = json.loads(vault("read", "-format=json", f"identity/oidc/token/{name}", token=tok))["data"]["token"]
    claims = json.loads(base64.urlsafe_b64decode(toks["ci-a-x"].split(".")[1] + "=="))
    print("ci-a-x token claims:", json.dumps(claims))
    return toks


def policy(prefix):
    return {"Version": "2012-10-17", "Statement": [{
        "Effect": "Allow", "Action": ["s3:GetObject", "s3:PutObject", "s3:DeleteObject"],
        "Resource": [f"arn:aws:s3:::ov-sync/{prefix}/*"]}]}


def trust(repo):
    return {"Version": "2012-10-17", "Statement": [{
        "Effect": "Allow", "Principal": {"Federated": "vault"},
        "Action": "sts:AssumeRoleWithWebIdentity",
        "Condition": {"StringEquals": {"oidc:ci_repository": repo}}}]}


def iam_config():
    # Same shape as local.seaweedfs_iam in services.tf, plus the Vault provider.
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
                     {"name": "ci-b-y", "document": policy("b/y")}],
        "roles": [{"roleName": r, "roleArn": ROLE(r), "trustPolicy": trust(repo), "attachedPolicies": [r]}
                  for r, repo in (("ci-a-x", "a/x"), ("ci-b-y", "b/y"))],
    }


def setup_swfs(tmp):
    p = os.path.join(tmp, "iam.json")
    json.dump(iam_config(), open(p, "w"), indent=1)
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
            for d in ("a/x", "b/y"):
                sh("docker", "exec", SWFS, "sh", "-c",
                   f"echo seed-{d} > /tmp/seed.txt && weed filer.copy /tmp/seed.txt http://127.0.0.1:8888/buckets/ov-sync/{d}/")
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
        toks = setup_vault()
        setup_swfs(tmp)
        ax, by, wrong = toks["ci-a-x"], toks["ci-b-y"], toks["ci-a-x-wrongaud"]

        c_ax, d = assume(ax, "ci-a-x")
        record("1 a/x token -> ci-a-x issues creds", True, c_ax is not None, d)
        c, d = assume(ax, "ci-b-y")
        record("2 a/x token -> ci-b-y REFUSED", True, c is None, d)
        c_by, d = assume(by, "ci-b-y")
        record("3 control: b/y token -> ci-b-y issues creds (refusal in 2 is the claim condition)", True, c_by is not None, d)
        c, d = assume(wrong, "ci-a-x")
        record("4 a/x token with aud=openviking -> ci-a-x REFUSED", True, c is None, d)

        if c_ax:
            for verb, key in (("put", "a/x/docs/f.md"), ("get", "a/x/docs/f.md"), ("put", "a/x/.okf/index.md"),
                              ("get", "a/x/seed.txt"), ("delete", "a/x/docs/f.md")):
                res = op(c_ax, verb, key)
                record(f"5 ci-a-x {verb} ov-sync/{key} OK", True, res == "OK", res)
            for verb, key in (("put", "b/y/evil.md"), ("delete", "b/y/seed.txt"), ("get", "b/y/seed.txt"),
                              ("put", "a/xx/evil.md"), ("put", "a/evil.md"), ("put", "evil.md")):
                res = op(c_ax, verb, key)
                record(f"6 ci-a-x {verb} ov-sync/{key} denied", True, res == "AccessDenied", res)
            rc, out = aws("s3api", "get-object", "--bucket", "ov-sync", "--key", "a/x/_state/manifest.json", "/dev/stdout", creds=c_ax)
            record("7 ci-a-x get missing a/x/_state/manifest.json (info: which error a missing manifest gives)", False, rc != 0,
                   out.splitlines()[-1][:200] if out else rc)
            rc, out = aws("s3api", "list-objects-v2", "--bucket", "ov-sync", creds=c_ax)
            record("7 ci-a-x list bucket denied (info: policy grants no List)", False, rc != 0, out.splitlines()[-1][:200] if out else rc)
        if c_by:
            res = op(c_by, "get", "b/y/seed.txt")
            record("8 b/y seed survived ci-a-x's delete attempt (read with ci-b-y)", True, res == "OK", res)
            res = op(c_by, "put", "a/x/evil.md")
            record("8 ci-b-y put ov-sync/a/x/evil.md denied", True, res == "AccessDenied", res)
    finally:
        logs = sh("docker", "logs", SWFS, check=False)
        print("\n== seaweedfs log tail (oidc/sts lines)")
        for line in (logs.stdout + logs.stderr).splitlines():
            if any(w in line.lower() for w in ("oidc", "sts", "provider", "jwks", "trust")):
                print(line[:300])
        cleanup()

    failed = [r for r in results if r[1] and not r[2]]
    print(f"\nrequired checks: {sum(1 for r in results if r[1])}, failed: {len(failed)}")
    sys.exit(1 if failed or not results else 0)


main()
