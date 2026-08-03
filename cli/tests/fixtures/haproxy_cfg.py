"""A rendered `haproxy.cfg` in the live shape, with a fake credential in it.

Copied structurally from the running job's `local/haproxy.cfg` template on
2026-08-03: ten routes, the same ACL and backend layout, the same
`userlist` block. The password here is obviously fake. The real one is a
24-character value that the running jobspec carries in plaintext, so any
command that fetches the haproxy job holds a live credential in memory, and
one `--json` dump or one traceback would print it.

That is why this fixture keeps the `insecure-password` line: the guardrail
tests need something real to catch.
"""

# Deliberately not a plausible secret. If this string ever appears in output,
# a test has found a leak.
FAKE_PASSWORD = "not-a-real-password-0000"  # noqa: S105

LIVE_SHAPE = f"""global
    log stdout format raw local0

defaults
    log     global
    mode    http

userlist openfang_users
    user admin insecure-password {FAKE_PASSWORD}

frontend https_in
    bind *:443 ssl crt /secrets/haproxy.pem

    acl is_minio      hdr(host) -i minio.lab.example
    acl is_s3         hdr(host) -i s3.lab.example
    acl is_vault      hdr(host) -i vault.lab.example
    acl is_nomad      hdr(host) -i nomad.lab.example
    acl is_consul     hdr(host) -i consul.lab.example
    acl is_phoenix    hdr(host) -i phoenix.lab.example
    acl is_memex      hdr(host) -i memex.lab.example
    acl is_grafana    hdr(host) -i grafana.lab.example
    acl is_mlflow     hdr(host) -i mlflow.lab.example
    acl is_bifrost    hdr(host) -i bifrost.lab.example

    use_backend minio      if is_minio
    use_backend s3         if is_s3
    use_backend vault      if is_vault
    use_backend nomad      if is_nomad
    use_backend consul     if is_consul
    use_backend phoenix    if is_phoenix
    use_backend memex      if is_memex
    use_backend grafana    if is_grafana
    use_backend mlflow     if is_mlflow
    use_backend bifrost    if is_bifrost

frontend stats
    bind *:8404
    stats enable

backend minio
    server minio1 10.0.0.29:9001 check

backend s3
    server s3_1 10.0.0.29:9000 check

backend vault
    server vault1 10.0.0.30:8200 check

backend nomad
    server nomad1 10.0.0.30:4646 check

backend consul
    server consul1 10.0.0.30:8500 check

backend phoenix
    http-request auth unless {{ http_auth(openfang_users) }}
    server phoenix1 10.0.0.29:6006 check

backend memex
    server memex1 10.0.0.30:8080 check

backend grafana
    server grafana1 10.0.0.30:3000 check

backend mlflow
    http-request auth unless {{ http_auth(openfang_users) }}
    server mlflow1 10.0.0.29:5000 check

backend bifrost
    server bifrost1 10.0.0.30:8081 check
"""

# A config that cannot be parsed into routes, for the error-path leak test.
# It still carries the credential, so a parser that echoes its input into an
# exception message leaks it.
MALFORMED = f"""userlist openfang_users
    user admin insecure-password {FAKE_PASSWORD}

frontend https_in
    acl is_broken hdr(host)
    use_backend nowhere if is_broken
"""
