"""S3 helper. copy EP SRC DST PREFIX: copy every key under PREFIX key for key. merge EP SRC DST: copy SRC's blogs/ keys to DST as-is, then
blog-scraper/ keys remapped to blogs/, skipping keys already in DST (ignore-existing).
show EP BUCKET KEY...: print objects.  grep EP BUCKET PREFIX WORD: list keys whose
body contains WORD."""
import sys
import boto3
cmd, ep, b = sys.argv[1:4]
s = boto3.client("s3", endpoint_url=ep, region_name="us-east-1", aws_access_key_id="SPIKEADMINKEY0000001",
                 aws_secret_access_key="spikeAdminSecret0000000000000000000000001")
P = "lab/user/jasper/resources/"


def keys(bucket, prefix):
    return sorted(o["Key"] for p in s.get_paginator("list_objects_v2").paginate(Bucket=bucket, Prefix=prefix)
                  for o in p.get("Contents", []))


def body(bucket, k):
    return s.get_object(Bucket=bucket, Key=k)["Body"].read()


if cmd == "copy":
    dst, pre = sys.argv[4], sys.argv[5]
    ks = keys(b, P + pre)
    for k in ks:  # SeaweedFS refuses CopyObject on dir markers, so get and put
        s.put_object(Bucket=dst, Key=k, Body=body(b, k))
    print(f"copied {len(ks)} keys under {pre}:")
    for k in ks:
        print("  ", k)
elif cmd == "merge":
    dst = sys.argv[4]
    n = 0
    for k in keys(b, P + "blogs/"):  # SeaweedFS refuses CopyObject on dir markers, so get and put
        s.put_object(Bucket=dst, Key=k, Body=body(b, k)); n += 1
    print(f"copied {n} blogs/ keys as-is")
    have = set(keys(dst, P))
    copied, skipped = [], []
    for k in keys(b, P + "blog-scraper/"):
        nk = P + "blogs/" + k[len(P + "blog-scraper/"):]
        if nk in have:
            skipped.append(nk); continue
        s.put_object(Bucket=dst, Key=nk, Body=body(b, k)); copied.append(nk)
    print(f"blog-scraper/ remapped: copied {len(copied)}, skipped (exists) {len(skipped)}:")
    for k in skipped:
        print("  SKIP", k)
    print("dst blog-scraper keys:", len(keys(dst, P + "blog-scraper")))
    print("dst blogs keys:", len(keys(dst, P + "blogs/")))
elif cmd == "show":
    for k in sys.argv[4:]:
        print(f"----- {k}"); print(body(b, P + k).decode(errors="replace"))
elif cmd == "grep":
    prefix, word = sys.argv[4], sys.argv[5]
    hits = [k for k in keys(b, P + prefix) if word.encode() in body(b, k)]
    for k in hits:
        print("HIT", k)
    print(f"{len(hits)} keys under {prefix} contain {word!r}")
