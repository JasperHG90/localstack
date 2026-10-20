"""Live checks for seaweedfs-service: S3 ops with the admin key, six buckets, LAN ports."""
import os
import socket
import sys

import boto3

ep = "http://192.168.2.29:8333"
s3 = boto3.client("s3", endpoint_url=ep, aws_access_key_id=os.environ["AK"], aws_secret_access_key=os.environ["SK"], region_name="us-east-1")
ok = True
s3.create_bucket(Bucket="verify-ops")
s3.put_object(Bucket="verify-ops", Key="hello.txt", Body=b"hi")
keys = [o["Key"] for o in s3.list_objects_v2(Bucket="verify-ops").get("Contents", [])]
s3.delete_object(Bucket="verify-ops", Key="hello.txt")
s3.delete_bucket(Bucket="verify-ops")
print("mb/cp/ls/rb:", keys)
ok &= keys == ["hello.txt"]
names = [f"verify-{i}" for i in range(6)]
for n in names:
    s3.create_bucket(Bucket=n)
    s3.put_object(Bucket=n, Key="k", Body=b"x" * 1024)
wrote = [n for n in names if s3.get_object(Bucket=n, Key="k")["Body"].read() == b"x" * 1024]
print("six buckets written:", len(wrote))
ok &= len(wrote) == 6
for n in names:
    s3.delete_object(Bucket=n, Key="k")
    s3.delete_bucket(Bucket=n)
print("left over buckets:", [b["Name"] for b in s3.list_buckets()["Buckets"]])

# Seen from this LAN host: only 8333 (S3) and 9327 (metrics) may answer.
ports = {8333: True, 9327: True, 9333: False, 19333: False, 8080: False, 18080: False, 8888: False, 18888: False, 18333: False, 23646: False}
for port, want in ports.items():
    s = socket.socket()
    s.settimeout(3)
    got = s.connect_ex(("192.168.2.29", port)) == 0
    s.close()
    print(f"port {port}: {'open' if got else 'closed'} (want {'open' if want else 'closed'})")
    ok &= got == want
sys.exit(0 if ok else 1)
