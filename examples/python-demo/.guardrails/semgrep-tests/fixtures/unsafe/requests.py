import requests

# ruleid: guardrails.python-disabled-tls-verification
requests.get("https://example.test", verify=False)
