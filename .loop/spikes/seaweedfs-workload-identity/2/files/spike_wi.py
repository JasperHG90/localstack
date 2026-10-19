# /// script
# requires-python = ">=3.11"
# dependencies = ["pyjwt[crypto]", "boto3"]
# ///
"""Spike: can SeaweedFS bind an STS role to one Nomad job's identity?

Fake OIDC issuer (python http.server container) + SeaweedFS 4.48 on a
throwaway docker network. Exits 0 only if every security check holds.
"""
import base64, json, os, subprocess, sys, tempfile, time, urllib.error, urllib.parse, urllib.request

import boto3, jwt
from botocore.config import Config
from botocore.exceptions import ClientError
from cryptography.hazmat.primitives.asymmetric import rsa

IMAGE = "chrislusf/seaweedfs:4.48"
NET, OIDC, SWFS = "spike-wi-1-net", "spike-oidc-wi-1", "spike-swfs-wi-1"
ISSUER = f"http://{OIDC}:8080"
S3 = "http://127.0.0.1:18333"
ROLE = lambda n: f"arn:aws:iam::role/{n}"
results = []  # (id, required, ok, detail)


def sh(*a, check=True):
    r = subprocess.run(a, capture_output=True, text=True)
    if check and r.returncode:
        raise RuntimeError(f"{a}: {r.stderr}")
    return r


def record(tid, required, ok, detail):
    results.append((tid, required, ok, detail))
    print(f"[{'PASS' if ok else 'FAIL'}]{'' if required else ' (info)'} {tid}: {detail}", flush=True)


def b64u(n):
    return base64.urlsafe_b64encode(n.to_bytes((n.bit_length() + 7) // 8, "big")).rstrip(b"=").decode()


key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
rogue = rsa.generate_private_key(public_exponent=65537, key_size=2048)
pub = key.public_key().public_numbers()
jwks = {"keys": [{"kty": "RSA", "kid": "nomad-1", "use": "sig", "alg": "RS256", "n": b64u(pub.n), "e": b64u(pub.e)}]}


def token(job, aud="seaweedfs", signer=key, ns="default"):
    now = int(time.time())
    claims = {
        "iss": ISSUER, "aud": [aud], "sub": f"global:{ns}:{job}:{job}:{job}",
        "nomad_namespace": ns, "nomad_job_id": job, "nomad_task": job,
        "nomad_allocation_id": "0b6c3a6e-1111-2222-3333-444455556666",
        "iat": now, "nbf": now, "exp": now + 3600,
    }
    return jwt.encode(claims, signer, algorithm="RS256", headers={"kid": "nomad-1"})


def trust(job):
    return {"Version": "2012-10-17", "Statement": [{
        "Effect": "Allow", "Principal": {"Federated": "nomad"},
        "Action": "sts:AssumeRoleWithWebIdentity",
        "Condition": {"StringEquals": {"oidc:nomad_job_id": job},
                      "StringLike": {"oidc:sub": f"global:default:{job}:*"}}}]}


def bucket_policy(b):
    return {"Version": "2012-10-17", "Statement": [{
        "Effect": "Allow", "Action": ["s3:*"],
        "Resource": [f"arn:aws:s3:::{b}", f"arn:aws:s3:::{b}/*"]}]}


def iam_config(policy_claim):
    oidc_cfg = {"issuer": ISSUER, "clientId": "seaweedfs"}
    if policy_claim:
        oidc_cfg["policyClaim"] = "nomad_job_id"
    return {
        "sts": {"tokenDuration": "1h", "maxSessionLength": "12h", "issuer": "seaweedfs-sts",
                "signingKey": base64.b64encode(os.urandom(32)).decode()},
        "policy": {"defaultEffect": "Deny"},
        "providers": [{"name": "nomad", "type": "oidc", "enabled": True, "config": oidc_cfg,
                       "roleMapping": {"rules": [
                           {"claim": "nomad_job_id", "value": "tempo", "role": ROLE("TempoRole")},
                           {"claim": "nomad_job_id", "value": "loki", "role": ROLE("LokiRole")},
                           # deliberately wrong mapping: the trust policy must still refuse it
                           {"claim": "nomad_job_id", "value": "evil", "role": ROLE("TempoRole")}]}}],
        "policies": [{"name": "tempo", "document": bucket_policy("tempo")},
                     {"name": "loki", "document": bucket_policy("loki")}],
        "roles": [
            {"roleName": "TempoRole", "roleArn": ROLE("TempoRole"), "trustPolicy": trust("tempo"), "attachedPolicies": ["tempo"]},
            {"roleName": "LokiRole", "roleArn": ROLE("LokiRole"), "trustPolicy": trust("loki"), "attachedPolicies": ["loki"]},
            # control: no claim condition, so any valid token may assume it
            {"roleName": "OpenRole", "roleArn": ROLE("OpenRole"), "attachedPolicies": ["tempo"],
             "trustPolicy": {"Version": "2012-10-17", "Statement": [{"Effect": "Allow", "Principal": {"Federated": "nomad"},
                                                                    "Action": "sts:AssumeRoleWithWebIdentity"}]}}],
    }


def assume(tok, role=None):
    form = {"Action": "AssumeRoleWithWebIdentity", "Version": "2011-06-15",
            "WebIdentityToken": tok, "RoleSessionName": "spike"}
    if role:
        form["RoleArn"] = role
    req = urllib.request.Request(S3 + "/", data=urllib.parse.urlencode(form).encode(), method="POST",
                                 headers={"Content-Type": "application/x-www-form-urlencoded"})
    try:
        body = urllib.request.urlopen(req, timeout=20).read().decode()
    except urllib.error.HTTPError as e:
        import re
        body = e.read().decode()
        m = re.search("<Code>([^<]*)</Code><Message>([^<]*)</Message>", body)
        return None, f"HTTP {e.code} " + (f"{m.group(1)}: {m.group(2)}" if m else body[:200])
    import re
    g = lambda t: re.search(f"<{t}>([^<]+)</{t}>", body).group(1)
    return (g("AccessKeyId"), g("SecretAccessKey"), g("SessionToken")), "HTTP 200"


def s3(creds):
    return boto3.client("s3", endpoint_url=S3, region_name="us-east-1",
                        aws_access_key_id=creds[0], aws_secret_access_key=creds[1], aws_session_token=creds[2],
                        config=Config(s3={"addressing_style": "path"}, retries={"max_attempts": 1}))


def can(fn):
    try:
        fn()
        return "OK"
    except ClientError as e:
        return e.response["Error"]["Code"]


def access(creds, b):
    c = s3(creds)
    return {"put": can(lambda: c.put_object(Bucket=b, Key="probe.txt", Body=b"x")),
            "get": can(lambda: c.get_object(Bucket=b, Key="seed.txt")["Body"].read()),
            "list": can(lambda: c.list_objects_v2(Bucket=b))}


def bearer_get(tok, b):
    req = urllib.request.Request(f"{S3}/{b}/seed.txt", headers={"Authorization": "Bearer " + tok})
    try:
        return f"HTTP {urllib.request.urlopen(req, timeout=20).status}"
    except urllib.error.HTTPError as e:
        return f"HTTP {e.code}"


def start_swfs(cfg, tmp):
    sh("docker", "rm", "-f", SWFS, check=False)
    p = os.path.join(tmp, "iam.json")
    json.dump(cfg, open(p, "w"))
    sh("docker", "create", "--name", SWFS, "--network", NET, "-p", "127.0.0.1:18333:8333", IMAGE,
       "server", "-dir=/data", "-s3", "-s3.port=8333", "-s3.iam.config=/iam.json",
       "-master.volumeSizeLimitMB=32", "-volume.max=8")
    sh("docker", "cp", p, f"{SWFS}:/iam.json")
    sh("docker", "start", SWFS)
    for _ in range(60):
        time.sleep(2)
        r = sh("docker", "exec", SWFS, "sh", "-c",
               "printf 's3.bucket.create -name tempo\\ns3.bucket.create -name loki\\n' | weed shell 2>&1", check=False)
        try:
            urllib.request.urlopen(S3 + "/", timeout=3)
        except urllib.error.HTTPError:
            pass  # any HTTP answer means S3 is up
        except Exception:
            continue
        ls = sh("docker", "exec", SWFS, "sh", "-c", "echo s3.bucket.list | weed shell 2>&1", check=False).stdout
        if "tempo" in ls and "loki" in ls:
            for b in ("tempo", "loki"):
                sh("docker", "exec", SWFS, "sh", "-c",
                   f"echo seed > /tmp/seed.txt && weed filer.copy /tmp/seed.txt http://127.0.0.1:8888/buckets/{b}/")
            return
    raise RuntimeError("seaweedfs did not come up:\n" + sh("docker", "logs", SWFS, check=False).stderr[-3000:])


def main():
    tmp = tempfile.mkdtemp()
    www = os.path.join(tmp, "www", ".well-known")
    os.makedirs(www)
    json.dump({"issuer": ISSUER, "jwks_uri": ISSUER + "/.well-known/jwks.json",
               "id_token_signing_alg_values_supported": ["RS256"]}, open(os.path.join(www, "openid-configuration"), "w"))
    json.dump(jwks, open(os.path.join(www, "jwks.json"), "w"))
    sh("docker", "network", "create", NET)
    sh("docker", "create", "--name", OIDC, "--network", NET, "python:3.12-alpine",
       "python", "-m", "http.server", "8080", "-d", "/srv")
    sh("docker", "cp", os.path.join(tmp, "www", "."), f"{OIDC}:/srv")
    sh("docker", "start", OIDC)

    tempo, loki, evil = token("tempo"), token("loki"), token("evil")
    forged = token("tempo", signer=rogue)
    minio_aud = token("tempo", aud="minio")
    other_ns = token("tempo", ns="prod")

    print(f"== Config A: roles + trust policies on oidc:nomad_job_id and oidc:sub, roleMapping, no policyClaim ({IMAGE})")
    start_swfs(iam_config(policy_claim=False), tmp)
    c, d = assume(tempo, ROLE("TempoRole"))
    record("A1 tempo token -> TempoRole issues creds", True, c is not None, d)
    tempo_creds = c
    c, d = assume(loki, ROLE("TempoRole"))
    record("A2 loki token -> TempoRole REFUSED", True, c is None, d)
    c, d = assume(loki, ROLE("OpenRole"))
    record("A2c control: loki token -> OpenRole (no condition) issues creds", True, c is not None, d)
    c, d = assume(forged, ROLE("TempoRole"))
    record("A3 forged tempo token (rogue key) -> TempoRole REFUSED", True, c is None, d)
    c, d = assume(minio_aud, ROLE("TempoRole"))
    record("A3b tempo token aud=minio -> TempoRole REFUSED", True, c is None, d)
    c, d = assume(other_ns, ROLE("TempoRole"))
    record("A3c job tempo in namespace prod -> TempoRole REFUSED (sub condition)", True, c is None, d)
    if tempo_creds:
        a_t, a_l = access(tempo_creds, "tempo"), access(tempo_creds, "loki")
        record("A4 TempoRole creds: put/get/list tempo OK", True, set(a_t.values()) == {"OK"}, str(a_t))
        record("A4 TempoRole creds: put/get/list loki AccessDenied", True, set(a_l.values()) == {"AccessDenied"}, str(a_l))
    c, d = assume(loki, ROLE("LokiRole"))
    record("A5 loki token -> LokiRole issues creds", True, c is not None, d)
    if c:
        a_l, a_t = access(c, "loki"), access(c, "tempo")
        record("A5 LokiRole creds: loki OK, tempo AccessDenied", True,
               set(a_l.values()) == {"OK"} and set(a_t.values()) == {"AccessDenied"}, f"loki={a_l} tempo={a_t}")
    c, d = assume(tempo)
    record("A6 tempo token, no RoleArn, no policyClaim -> refused (roleMapping not used by STS)", True, c is None, d)
    if c:
        record("A6x creds from no-RoleArn call", False, True, str(access(c, "tempo")) + str(access(c, "loki")))
    record("A7 Bearer: loki JWT GET tempo/seed.txt denied", True, bearer_get(loki, "tempo") in ("HTTP 403", "HTTP 401"), bearer_get(loki, "tempo"))
    record("A7b Bearer: evil JWT (roleMapping -> TempoRole) GET tempo denied by trust gate", True,
           bearer_get(evil, "tempo") in ("HTTP 403", "HTTP 401"), bearer_get(evil, "tempo"))
    record("A7c Bearer: tempo JWT GET tempo (informational)", False, True, bearer_get(tempo, "tempo"))
    record("A7d Bearer: forged tempo JWT GET tempo denied", True, bearer_get(forged, "tempo") in ("HTTP 403", "HTTP 401"), bearer_get(forged, "tempo"))

    print("== Config B: same, plus provider policyClaim = nomad_job_id (claim mode, MinIO-like)")
    start_swfs(iam_config(policy_claim=True), tmp)
    c, d = assume(tempo)
    record("B1 tempo token, no RoleArn -> claim-mode creds", False, c is not None, d)
    if c:
        record("B1 claim creds: tempo vs loki", True,
               set(access(c, "tempo").values()) == {"OK"} and set(access(c, "loki").values()) == {"AccessDenied"},
               f"tempo={access(c, 'tempo')} loki={access(c, 'loki')}")
    c, d = assume(loki)
    if c:
        record("B2 loki claim creds: loki OK, tempo denied", True,
               set(access(c, "loki").values()) == {"OK"} and set(access(c, "tempo").values()) == {"AccessDenied"},
               f"loki={access(c, 'loki')} tempo={access(c, 'tempo')}")
    else:
        record("B2 loki token no RoleArn -> creds", False, False, d)
    c, d = assume(loki, ROLE("TempoRole"))
    record("B3 claim mode on: loki token -> TempoRole still REFUSED", True, c is None, d)
    c, d = assume(token("evil,tempo"))
    record("B4 job id 'evil,tempo' (comma) in claim mode (informational: gets tempo?)", False, True,
           d + ("" if c is None else " tempo=" + str(access(c, "tempo"))))
    sh("docker", "logs", SWFS, check=False)

    failed = [r for r in results if r[1] and not r[2]]
    print(f"\nrequired checks: {sum(1 for r in results if r[1])}, failed: {len(failed)}")
    return 0 if not failed else 1


if __name__ == "__main__":
    try:
        rc = main()
    except Exception as e:
        print("ERROR:", e, file=sys.stderr)
        rc = 2
    finally:
        for n in (SWFS, OIDC):
            if os.environ.get("KEEP") != "1":
                sh("docker", "rm", "-f", n, check=False)
        if os.environ.get("KEEP") != "1":
            sh("docker", "network", "rm", NET, check=False)
    sys.exit(rc)
