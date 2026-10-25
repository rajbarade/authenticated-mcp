import time
from contextlib import nullcontext

import httpx
import jwt
import pytest
from starlette.testclient import TestClient

from app.auth.jwt_validator import JWTValidator
from app.auth.middleware import AuthMiddleware
from app.config import Settings
from tests.conftest import GROUP


@pytest.mark.parametrize(
    ("changes", "omit", "status"),
    [
        ({}, (), 200),
        ({"exp": 1}, (), 401),
        ({"nbf": int(time.time()) + 3600}, (), 401),
        ({"iat": int(time.time()) + 3600}, (), 401),
        ({"iss": "https://foreign.invalid"}, (), 401),
        ({"aud": "other-api"}, (), 401),
        ({"aud": ["test-api-audience"]}, (), 401),
        ({"tid": "foreign"}, (), 401),
        ({"ver": "1.0"}, (), 401),
        ({"scp": "other"}, (), 403),
        ({}, ("scp",), 401),
        ({"idtyp": "app", "roles": ["mcp.access"]}, (), 401),
        ({}, ("exp",), 401),
        ({}, ("nbf",), 401),
        ({}, ("iat",), 401),
        ({}, ("sub",), 401),
        ({}, ("oid",), 401),
        ({"groups": ["not-authorized"]}, (), 403),
        ({}, ("groups",), 403),
        ({"groups": GROUP}, (), 403),
        ({"hasgroups": True}, (), 403),
        ({"_claim_names": {"groups": "src1"}}, (), 403),
        ({"_claim_sources": {"src1": {"endpoint": "https://evil.invalid"}}}, (), 403),
    ],
)
def test_gate_before_execution(settings, issuer, changes, omit, status, caplog):
    executions = []

    async def tool(scope, receive, send):
        executions.append(True)
        from starlette.responses import JSONResponse

        await JSONResponse({"ok": True})(scope, receive, send)

    token = issuer.token(changes, omit=omit)
    app = AuthMiddleware(tool, settings, JWTValidator(settings, issuer.client()))
    with nullcontext(TestClient(app)) as client:
        response = client.post("/mcp", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == status
    assert len(executions) == (1 if status == 200 else 0)
    assert token not in caplog.text


@pytest.mark.parametrize("method", ["GET", "POST", "DELETE", "PUT", "OPTIONS"])
@pytest.mark.parametrize("path", ["/mcp", "/mcp/", "/unknown"])
def test_missing_auth_all_methods(settings, issuer, method, path):
    async def never(*args):
        pytest.fail("Unauthorized execution")

    with nullcontext(
        TestClient(AuthMiddleware(never, settings, JWTValidator(settings, issuer.client())))
    ) as c:
        response = c.request(method, path)
        assert response.status_code == 401
        assert settings.metadata_url in response.headers["www-authenticate"]


async def test_bad_tokens(settings, issuer):
    validator = JWTValidator(settings, issuer.client())
    from app.auth.principal import InvalidToken

    original = issuer.token()
    parts = original.split(".")
    parts[1] = parts[1][:-5] + "AAAAA"
    tokens = [
        "bad",
        ".".join(parts),
        "a" * 32769,
        jwt.encode({"exp": 9999999999}, "a" * 32, algorithm="HS256", headers={"kid": "first"}),
        jwt.encode({}, key="", algorithm="none"),
    ]
    for token in tokens:
        with pytest.raises(InvalidToken):
            await validator.validate(token)


async def test_cache_rollover_and_outage(settings, issuer):
    from app.auth.principal import InvalidToken

    validator = JWTValidator(settings, issuer.client())
    await validator.validate(issuer.token())
    await validator.validate(issuer.token())
    assert len(issuer.requests) == 2
    issuer.published = ["second"]
    with pytest.raises(InvalidToken):  # bounded rollover delay
        await validator.validate(issuer.token(kid="second"))
    assert len(issuer.requests) == 2
    validator._next_refresh = 0
    await validator.validate(issuer.token(kid="second"))
    assert len(issuer.requests) == 4
    with pytest.raises(InvalidToken):
        await validator.validate(issuer.token())
    issuer.unavailable = True
    validator._expires = 0
    validator._next_refresh = 0
    with pytest.raises(InvalidToken):
        await validator.validate(issuer.token(kid="second"))


@pytest.mark.parametrize("attack", ["issuer", "jwks", "redirect"])
async def test_discovery_trust(settings, issuer, attack):
    from app.auth.principal import InvalidToken

    if attack == "issuer":
        issuer.discovery_issuer = "https://evil.invalid"
    if attack == "jwks":
        issuer.jwks_uri = "https://evil.invalid/keys"
    client = (
        issuer.client()
        if attack != "redirect"
        else httpx.AsyncClient(
            transport=httpx.MockTransport(
                lambda r: httpx.Response(302, headers={"location": "https://evil.invalid"})
            )
        )
    )
    with pytest.raises(InvalidToken):
        await JWTValidator(settings, client).validate(issuer.token())
    assert len(issuer.requests) <= 1


@pytest.mark.parametrize("header", ["Basic abc", "Bearer ", "Bearer a b"])
def test_malformed_header(settings, issuer, header):
    async def never(*args):
        pytest.fail("Unauthorized execution")

    with nullcontext(
        TestClient(AuthMiddleware(never, settings, JWTValidator(settings, issuer.client())))
    ) as c:
        assert c.post("/mcp", headers={"authorization": header}).status_code == 401
        assert (
            c.post(
                "/mcp",
                headers=[
                    ("authorization", "Bearer " + issuer.token()),
                    ("authorization", "Bearer " + issuer.token()),
                ],
            ).status_code
            == 401
        )


@pytest.mark.parametrize(
    "changes",
    [
        {"auth_provider": "other"},
        {"oidc_issuer": "https://login.microsoftonline.com/common/v2.0"},
        {"oidc_discovery_url": "https://evil.invalid"},
        {"allowed_group_ids": ""},
        {"allowed_group_ids": "group-name"},
        {"mcp_public_url": "http://example.com/mcp"},
        {"mcp_public_url": "https://example.com/mcp?token=x"},
        {"required_scopes": ""},
        {"jwt_audience": ""},
        {"log_level": "DEBUG"},
    ],
)
def test_config_rejects_unsafe(settings: Settings, changes):
    with pytest.raises(ValueError):
        Settings(**(settings.model_dump() | changes))


async def test_concurrent_refresh_and_untrusted_header_urls(settings, issuer):
    import asyncio

    validator = JWTValidator(settings, issuer.client())
    token = issuer.token()
    claims = jwt.decode(token, options={"verify_signature": False})
    token = jwt.encode(
        claims,
        issuer.keys["first"],
        algorithm="RS256",
        headers={
            "kid": "first",
            "jku": "https://evil.invalid/jwks",
            "x5u": "https://evil.invalid/cert",
        },
    )
    await asyncio.gather(*(validator.validate(token) for _ in range(10)))
    assert len(issuer.requests) == 2
    assert all(url.startswith("https://login.microsoftonline.com/") for url in issuer.requests)


@pytest.mark.parametrize(
    "kind", ["duplicate", "weak", "malformed", "oversized", "wrong-key-issuer"]
)
async def test_bad_jwks_fails_closed(settings, issuer, kind):
    import json

    from cryptography.hazmat.primitives.asymmetric import rsa

    from app.auth.principal import InvalidToken

    def respond(request):
        response = issuer.respond(request)
        if str(request.url) != issuer.jwks_uri:
            return response
        doc = response.json()
        if kind == "duplicate":
            doc["keys"].append(doc["keys"][0])
        elif kind == "weak":
            key = rsa.generate_private_key(public_exponent=65537, key_size=1024)
            doc["keys"] = [
                {**json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(key.public_key())), "kid": "first"}
            ]
        elif kind == "malformed":
            doc = {"keys": [None]}
        elif kind == "wrong-key-issuer":
            doc["keys"][0]["issuer"] = "https://evil.invalid"
        else:
            return httpx.Response(200, content=b" " * 262145)
        return httpx.Response(200, json=doc)

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        with pytest.raises(InvalidToken):
            await JWTValidator(settings, client).validate(issuer.token())
