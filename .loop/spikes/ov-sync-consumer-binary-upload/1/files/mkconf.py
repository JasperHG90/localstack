"""Write a local ov.conf from the repo's ov.conf.json. Args: src dst bucket schema"""
import json, sys
src, dst, bucket, schema = sys.argv[1:5]
c = json.load(open(src))
c["storage"]["agfs"]["s3"].update(bucket=bucket, endpoint="http://swfs:8333",
                                  access_key="SPIKEADMINKEY0000001",
                                  secret_key="spikeAdminSecret0000000000000000000000001")
c["storage"]["vectordb"]["custom_params"].update(dsn="postgresql://ov:ov@pg:5432/openviking", schema=schema)
c["embedding"]["dense"].update(api_base="http://fake:8080/v1", api_key="k")
c["rerank"].update(api_base="http://fake:8080/v1/rerank", api_key="k")
for sect in ("vlm", "query_planner"):
    c[sect].update(api_base="http://fake:8080/v1", api_key="k")
sv = c["server"]
sv["auth_mode"] = "oidc"
sv["root_api_key"] = "spike-root-key-0123456789abcdef0123456789"
sv["oidc"]["issuer"] = "http://fake:8000"
sv["public_base_url"] = "http://ov:1933"
sv["observability"]["traces"]["enabled"] = False
json.dump(c, open(dst, "w"), indent=1)
