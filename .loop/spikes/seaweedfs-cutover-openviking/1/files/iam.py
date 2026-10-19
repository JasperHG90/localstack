# Creates bucket openviking and a static IAM user with an inline s3:* policy
# on it, the shape of today's MinIO read-write policy. Prints "AK SK".
import json, sys, boto3
from botocore.config import Config
ep = f"http://127.0.0.1:{sys.argv[1]}"
cfg = Config(s3={"addressing_style": "path"})
kw = dict(endpoint_url=ep, aws_access_key_id="SPIKEADMINKEY0000001",
          aws_secret_access_key="spikeAdminSecret0000000000000000000000001",
          region_name="us-east-1", config=cfg)
boto3.client("s3", **kw).create_bucket(Bucket="openviking")
iam = boto3.client("iam", **kw)
iam.create_user(UserName="openviking")
k = iam.create_access_key(UserName="openviking")["AccessKey"]
pol = {"Version": "2012-10-17", "Statement": [{"Effect": "Allow", "Action": ["s3:*"],
       "Resource": ["arn:aws:s3:::openviking", "arn:aws:s3:::openviking/*"]}]}
iam.put_user_policy(UserName="openviking", PolicyName="rw", PolicyDocument=json.dumps(pol))
print(k["AccessKeyId"], k["SecretAccessKey"])
