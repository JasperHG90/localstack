"""The `localstack monitor` panel.

Imports `localstack_cli.api` for every read. There is deliberately no HTTP
client here: two fetch layers would mean two places deciding what a 403
means, and they would disagree.
"""
