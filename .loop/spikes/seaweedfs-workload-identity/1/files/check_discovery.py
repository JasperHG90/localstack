"""Risk 3: can SeaweedFS (4.40..4.48 weed/iam/oidc) discover and parse Nomad's JWKS?
Read-only: GETs public discovery + JWKS with system CA verification, and
fetches SeaweedFS source to confirm which key types it parses. Exit 0 = risk does not hold."""
import json, re, ssl, sys, urllib.request

ISSUER = "https://nomad.lab.orangecluster.nl"
ctx = ssl.create_default_context()  # system roots only, like Go's SystemCertPool

def get(url):
    with urllib.request.urlopen(url, timeout=15, context=ctx) as r:
        return r.read().decode()

fail = []
doc = json.loads(get(ISSUER + "/.well-known/openid-configuration"))
print("issuer:", doc.get("issuer"))
print("jwks_uri:", doc.get("jwks_uri"))
print("id_token_signing_alg_values_supported:", doc.get("id_token_signing_alg_values_supported"))
if doc.get("issuer", "").rstrip("/") != ISSUER:
    fail.append("discovery issuer differs from configured issuer (SeaweedFS rejects)")
if doc.get("jwks_uri") != ISSUER + "/.well-known/jwks.json":
    fail.append("jwks_uri != issuer + /.well-known/jwks.json")

jwks = json.loads(get(doc["jwks_uri"]))
keys = jwks.get("keys", [])
print("keys:", [(k.get("kid"), k.get("kty"), k.get("alg")) for k in keys])
if not keys:
    fail.append("JWKS has no keys")

for tag in ("4.40", "4.48"):
    src = get(f"https://raw.githubusercontent.com/seaweedfs/seaweedfs/{tag}/weed/iam/oidc/oidc_provider.go")
    ktys = re.findall(r'case "(\w+)":\s*\n\s*return p\.parse\w+Key', src)
    meth = re.search(r'case (\*jwt\.SigningMethod\w+(?:, \*jwt\.SigningMethod\w+)*):\s*\n\s*return publicKey', src)
    print(f"seaweedfs {tag}: parseJWK kty={ktys} signing methods={meth.group(1) if meth else None}")
    bad = [k for k in keys if k.get("kty") not in ktys]
    if bad:
        fail.append(f"{tag}: unparseable keys {[(k['kid'], k['kty']) for k in bad]}")
    if meth and "RSA" not in meth.group(1):
        fail.append(f"{tag}: RS256 not accepted")

print("FAIL:" if fail else "OK: discovery, issuer match, all JWKS keys parseable by SeaweedFS", *fail, sep="\n  ")
sys.exit(1 if fail else 0)
