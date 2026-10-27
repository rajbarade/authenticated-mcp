from starlette.testclient import TestClient

from app.main import build_app


def test_real_mcp_flow(settings, issuer, monkeypatch):
    calls = []

    def hello_world(name: str = "world") -> str:
        calls.append(name)
        return f"Hello, {name}!"

    monkeypatch.setattr("app.main.hello_world", hello_world)
    with TestClient(build_app(settings, issuer.client())) as client:
        metadata = client.get("/.well-known/oauth-protected-resource/mcp").json()
        assert metadata["resource"] == settings.mcp_public_url
        assert metadata["authorization_servers"] == [settings.oidc_issuer]
        assert metadata["scopes_supported"] == ["https://mcp.example.com/mcp/mcp.access"]
        assert client.get("/healthz").status_code == 200
        headers = {
            "Authorization": "Bearer " + issuer.token(),
            "Accept": "application/json, text/event-stream",
        }

        def rpc(method, params, ident=1, auth=headers):
            return client.post(
                "/mcp",
                headers=auth,
                json={"jsonrpc": "2.0", "id": ident, "method": method, "params": params},
            )

        init = rpc(
            "initialize",
            {
                "protocolVersion": "2025-11-25",
                "capabilities": {},
                "clientInfo": {"name": "test", "version": "1"},
            },
        )
        assert init.status_code == 200, init.text
        assert "serverInfo" in init.json()["result"]
        headers["MCP-Protocol-Version"] = init.json()["result"]["protocolVersion"]
        notified = client.post(
            "/mcp", headers=headers, json={"jsonrpc": "2.0", "method": "notifications/initialized"}
        )
        assert notified.status_code == 202
        listing = rpc("tools/list", {})
        assert listing.json()["result"]["tools"][0]["name"] == "hello_world"
        response = rpc("tools/call", {"name": "hello_world", "arguments": {}})
        assert response.json()["result"]["content"][0]["text"] == "Hello, world!"
        response = rpc("tools/call", {"name": "hello_world", "arguments": {"name": "Rani"}})
        assert response.json()["result"]["content"][0]["text"] == "Hello, Rani!"
        for token, status in [
            ("bad", 401),
            (issuer.token({"groups": []}), 403),
            (issuer.token({"exp": 1}), 401),
            (issuer.token({"scp": "other"}), 403),
        ]:
            assert (
                rpc(
                    "tools/call",
                    {"name": "hello_world", "arguments": {}},
                    auth={**headers, "Authorization": "Bearer " + token},
                ).status_code
                == status
            )
        assert calls == ["world", "Rani"]
        # Fresh token membership changes need no redeployment.
        assert (
            rpc(
                "tools/call",
                {"name": "hello_world", "arguments": {}},
                auth={**headers, "Authorization": "Bearer " + issuer.token()},
            ).status_code
            == 200
        )


def test_business_greeting():
    from app.tools.hello import hello_world

    assert hello_world() == "Hello, world!"
    assert hello_world("Rani") == "Hello, Rani!"
