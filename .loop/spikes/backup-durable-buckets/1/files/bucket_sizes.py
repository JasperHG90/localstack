"""Read MinIO per-bucket usage from its public bucket metrics endpoint.

Read-only GET. Exits 0 when the four durable buckets together hold under
LIMIT_GB, so the first sync and GCS cost are not a concern; exits 1 otherwise.
"""
import re
import sys
import urllib.request

URL = "http://192.168.2.29:9000/minio/v2/metrics/bucket"
DURABLE = ("openviking", "registry", "models", "datalake")
LIMIT_GB = 100
GCS_STANDARD_EUW4_PER_GB_MONTH = 0.020

text = urllib.request.urlopen(URL, timeout=10).read().decode()
pat = re.compile(r'^(minio_bucket_usage_(?:total_bytes|object_total))\{bucket="([^"]+)"[^}]*\} (\S+)$', re.M)
usage: dict[str, dict[str, float]] = {}
for metric, bucket, val in pat.findall(text):
    usage.setdefault(bucket, {})[metric.rsplit("_", 2)[-2]] = float(val)

print(f"{'bucket':18} {'bytes':>16} {'GiB':>9} {'objects':>10}")
for b in sorted(usage):
    by = usage[b].get("total", 0)
    ob = usage[b].get("object", 0)
    mark = "*" if b in DURABLE else " "
    print(f"{b:18}{mark}{int(by):>16} {by/2**30:>9.3f} {int(ob):>10}")
dur = sum(usage.get(b, {}).get("total", 0) for b in DURABLE)
missing = [b for b in DURABLE if b not in usage]
print(f"durable (*) total: {int(dur)} bytes = {dur/2**30:.3f} GiB = {dur/1e9:.3f} GB")
print(f"GCS Standard europe-west4 @ ${GCS_STANDARD_EUW4_PER_GB_MONTH}/GB-month: ${dur/2**30*GCS_STANDARD_EUW4_PER_GB_MONTH:.2f}/month")
if missing:
    print("missing buckets:", missing)
    sys.exit(2)
sys.exit(0 if dur / 1e9 < LIMIT_GB else 1)
