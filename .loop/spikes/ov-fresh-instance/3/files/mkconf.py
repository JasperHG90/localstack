"""Write a local ov.conf from the repo's ov.conf.json. Args: src dst auth_mode"""
import json, sys
src, dst, mode = sys.argv[1:4]
c = json.load(open(src))
s3 = c["storage"]["agfs"]["s3"]
s3.update(bucket="openviking-v2", endpoint="http://swfs:8333",
          access_key="SPIKEADMINKEY0000001", secret_key="spikeAdminSecret0000000000000000000000001")
cp = c["storage"]["vectordb"]["custom_params"]
cp.update(dsn="postgresql://ov:ov@pg:5432/openviking", schema="openviking_v2")
for sect in ("embedding",):
    c[sect]["dense"].update(api_base="http://fake:8080/v1", api_key="k")
c["rerank"].update(api_base="http://fake:8080/v1/rerank", api_key="k")
for sect in ("vlm", "query_planner"):
    c[sect].update(api_base="http://fake:8080/v1", api_key="k")
sv = c["server"]
sv["auth_mode"] = mode
sv["root_api_key"] = "spike-root-key-0123456789abcdef0123456789"
sv["oidc"]["issuer"] = "http://fake:8000"
sv["public_base_url"] = "http://ov:1933"
sv["observability"]["traces"]["enabled"] = False
if mode != "oidc":
    sv.pop("oidc")
json.dump(c, open(dst, "w"), indent=1)
