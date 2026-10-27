import io
import json
import urllib.error
from email.message import Message

import pytest

from scripts import verify_azure


class Response(io.BytesIO):
    status = 200


def mock_requests(monkeypatch, *, resource=None, status=401, challenge=True):
    def open_url(request, timeout):
        if request == verify_azure.BASE + "/healthz":
            return Response(b'{"status":"ok"}')
        if request == verify_azure.METADATA:
            return Response(
                json.dumps(
                    {
                        "resource": resource or verify_azure.BASE + "/mcp",
                        "authorization_servers": ["https://issuer.example"],
                        "scopes_supported": ["scope"],
                    }
                ).encode()
            )
        assert request.full_url == verify_azure.BASE + "/mcp"
        assert request.get_method() == "POST"
        assert "Authorization" not in request.headers
        if status == 200:
            return Response(b"{}")
        headers = Message()
        if challenge:
            headers["WWW-Authenticate"] = f'Bearer resource_metadata="{verify_azure.METADATA}"'
        raise urllib.error.HTTPError(request.full_url, status, "test", headers, None)

    monkeypatch.setattr(verify_azure.urllib.request, "urlopen", open_url)


def test_public_probe_accepts_only_expected_contract(monkeypatch):
    mock_requests(monkeypatch)
    verify_azure.check()


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
        verify_azure.check()
