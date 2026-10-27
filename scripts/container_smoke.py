"""Run via docker exec with stdin; requires only Python's standard library."""

import json
import os
import time
import urllib.error
import urllib.request

assert os.getuid() == 10001, "Container must run as the non-root application user"
for attempt in range(50):
    try:
        with urllib.request.urlopen("http://127.0.0.1:8000/healthz", timeout=2) as response:
            assert response.status == 200
        break
    except OSError:
        if attempt == 49:
            raise
        time.sleep(0.2)
with urllib.request.urlopen(
    "http://127.0.0.1:8000/.well-known/oauth-protected-resource/mcp", timeout=2
) as response:
    assert json.load(response)["resource"] == "https://mcp.example.com/mcp"
try:
    urllib.request.urlopen(
        urllib.request.Request("http://127.0.0.1:8000/mcp", data=b"{}"), timeout=2
    )
except urllib.error.HTTPError as error:
    assert error.code == 401
    assert "resource_metadata" in error.headers["WWW-Authenticate"]
else:
    raise AssertionError("Unauthenticated MCP call must fail")
print("Container smoke passed: non-root, health, metadata, 401 discovery")
