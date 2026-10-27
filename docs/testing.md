# Testing and acceptance

Run `make check`: locked installation, Ruff lint/format, strict mypy for production code, and pytest. Tests use ephemeral RSA keys and an httpx mock at the real trusted URL shape. No network or credentials are required for the test suite. The actual FastMCP transport runs in Starlette TestClient, including lifespan, initialize, initialized notification, list and tool call. Separate middleware tests count downstream invocations and prove denials cannot execute tools.

Covered locally: valid delegated member; malformed/unsigned/HS256/tampered/expired tokens; wrong issuer/audience/tenant/version; missing required claims; future timestamps; missing or wrong delegated scopes; app-only rejection; missing/malformed/foreign/overage groups; duplicate authorization headers; all MCP methods; metadata discovery; trusted discovery URL/issuer and redirect rejection; cache reuse, rollover cooldown and unavailable issuer; fresh-token membership changes; request-by-request revalidation. Inspect the test files for exact assertions. Scope absence produces 401; valid delegated insufficient scope produces 403 with a scope challenge.

## Live owner procedure — all UNTESTED

Complete [Entra setup](entra-setup.md) and [client setup](oauth-clients.md). Acquire an API access token through the client's authorization-code + S256 PKCE flow and its exact registered redirect, requesting the qualified delegated scope and canonical resource. Use the client's flow or a maintained MSAL client, never password/client-credentials grants. Validate state and the exact redirect during any manual client implementation. [Microsoft's flow documentation](https://learn.microsoft.com/en-us/entra/identity-platform/v2-oauth2-auth-code-flow) is the reference. Do not paste tokens into third-party decoders.

To send a diagnostic request without putting a token in shell history or process arguments, use Python `getpass` and httpx in a local trusted terminal:

```python
from getpass import getpass
import httpx
url = input("Canonical HTTPS MCP URL: ")
headers = {"Authorization": "Bearer " + getpass("Access token: "),
           "Accept": "application/json, text/event-stream"}
with httpx.Client(timeout=20) as client:
    response = client.post(url, headers=headers, json={
        "jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
            "protocolVersion": "2025-11-25", "capabilities": {},
            "clientInfo": {"name": "owner-acceptance", "version": "1"}}})
    response.raise_for_status()
    headers["MCP-Protocol-Version"] = response.json()["result"]["protocolVersion"]
    client.post(url, headers=headers, json={"jsonrpc": "2.0", "method": "notifications/initialized"}).raise_for_status()
    response = client.post(url, headers=headers, json={"jsonrpc": "2.0", "id": 2,
        "method": "tools/call", "params": {"name": "hello_world", "arguments": {"name": "owner"}}})
    print(response.status_code, response.json())
```

Record date, deployed commit, tenant/resource/verified audience (private if needed), tool result and HTTP statuses. Never preserve token/header dumps. Repeat with expired, wrong-API and non-member tokens; expect 401 for invalid authentication and 403 for denied membership. Add a second user to the group, acquire a new token and prove success without redeploy; remove that user and acquire a genuinely newly issued token and prove 403. A cached token can still authorize until expiry. Test missing groups/overage with suitable tenant users. Real Microsoft signing-key rotation is provider-controlled: observe a rotation when available, do not attempt to change Microsoft's keys. Local rollover is simulated and passed separately.

| Gate | Current evidence |
| --- | --- |
| Synthetic local security and MCP tests | Automated; run `make check` |
| Actual Entra v2 aud inspection | UNTESTED / owner-required |
| Real consent, group add/remove, non-member | UNTESTED / owner-required |
| ChatGPT login and invocation | UNTESTED / owner-required |
| Claude login and invocation | UNTESTED / owner-required |
| Public HTTPS / Azure hosting | UNTESTED / owner-required |

Do not mark live acceptance complete based on synthetic tests.
