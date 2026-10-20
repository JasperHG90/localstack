#!/usr/bin/env bash
# After cleanup: no probe role in the job list, six buckets, IAM config still loaded.
set -euo pipefail
cd /home/vscode/workspace.worktrees/seaweedfs-workload-identity
echo "## wi-probe in the keyless job list: $(grep -c 'wi-probe' deployments/infrastructure/services.tf || true)"
cd /home/vscode/workspace
eval "$(uv run localstack env)" 2>/dev/null
AK="$(vault kv get -field=access_key secret/default/seaweedfs/admin)" SK="$(vault kv get -field=secret_key secret/default/seaweedfs/admin)" \
uv run --no-project --quiet --with boto3 python -I -c "
import os, sys, urllib.request, urllib.error, boto3
s3 = boto3.client('s3', endpoint_url='http://192.168.2.29:8333', aws_access_key_id=os.environ['AK'], aws_secret_access_key=os.environ['SK'], region_name='us-east-1')
names = sorted(b['Name'] for b in s3.list_buckets()['Buckets'])
print('buckets:', names)
# An STS call with a junk token must be refused, which shows the IAM config is loaded.
req = urllib.request.Request('http://192.168.2.29:8333/?Action=AssumeRoleWithWebIdentity&Version=2011-06-15&RoleArn=arn:aws:iam::role/tempo&RoleSessionName=x&WebIdentityToken=junk', data=b'', method='POST')
try:
    urllib.request.urlopen(req); code = 200
except urllib.error.HTTPError as e:
    code = e.code
print('sts with a junk token:', code)
sys.exit(0 if names == ['datalake','loki','models','openviking','registry','tempo'] and code in (400, 401, 403) else 1)
"
