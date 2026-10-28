import io
import json
import urllib.error
from email.message import Message

import pytest

from scripts import verify_azure

BASE = "https://work-mcp.example.com"
RESOURCE = BASE + "/mcp"
METADATA = BASE + "/.well-known/oauth-protected-resource/mcp"


class Response(io.BytesIO):
    status = 200


def mock_requests(monkeypatch, *, resource=None, status=401, challenge=True):
    def open_url(request, timeout):
        if request == BASE + "/healthz":
            return Response(b'{"status":"ok"}')
        if request == METADATA:
            return Response(
                json.dumps(
                    {
                        "resource": resource or BASE + "/mcp",
                        "authorization_servers": ["https://issuer.example"],
                        "scopes_supported": ["scope"],
                    }
                ).encode()
            )
        assert request.full_url == BASE + "/mcp"
        assert request.get_method() == "POST"
        assert "Authorization" not in request.headers
        if status == 200:
            return Response(b"{}")
        headers = Message()
        if challenge:
            headers["WWW-Authenticate"] = f'Bearer resource_metadata="{METADATA}"'
        raise urllib.error.HTTPError(request.full_url, status, "test", headers, None)

    monkeypatch.setattr(verify_azure.urllib.request, "urlopen", open_url)


def test_public_probe_accepts_only_expected_contract(monkeypatch):
    mock_requests(monkeypatch)
    verify_azure.check(RESOURCE)


@pytest.mark.parametrize(
    "changes",
    [
        {"resource": "https://wrong.example/mcp"},
        {"status": 200},
        {"status": 403},
        {"challenge": False},
    ],
)
def test_public_probe_cannot_report_false_success(monkeypatch, changes):
    mock_requests(monkeypatch, **changes)
    with pytest.raises(ValueError):
        verify_azure.check(RESOURCE)


@pytest.mark.parametrize(
    "resource",
    [
        "",
        "http://work.example/mcp",
        "https://work.example/",
        "https://user:password@work.example/mcp",
        "https://work.example/mcp?token=x",
        "https://work.example/mcp#fragment",
    ],
)
def test_no_default_or_unsafe_deployment_destination(monkeypatch, resource):
    monkeypatch.setenv("MCP_PUBLIC_URL", resource)

    def never(*args, **kwargs):
        pytest.fail("Invalid deployment configuration must not make network requests")

    monkeypatch.setattr(verify_azure.urllib.request, "urlopen", never)
    with pytest.raises(ValueError):
        verify_azure.main()


def test_resource_comes_from_owner_configuration(monkeypatch):
    monkeypatch.setenv("MCP_PUBLIC_URL", RESOURCE)
    assert verify_azure.configured_resource() == RESOURCE
