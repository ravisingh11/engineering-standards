import requests

# ok: guardrails.python-disabled-tls-verification
requests.get("https://example.test", verify=True)
