import json
import time
from collections.abc import Iterator
from typing import Any

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from app.config import Settings

TENANT = "11111111-1111-4111-8111-111111111111"
GROUP = "22222222-2222-4222-8222-222222222222"


@pytest.fixture
def settings() -> Settings:
    return Settings(
        _env_file=None,
        mcp_public_url="https://mcp.example.com/mcp",
        tenant_id=TENANT,
        oidc_issuer=f"https://login.microsoftonline.com/{TENANT}/v2.0",
        jwt_audience="test-api-audience",
        allowed_group_ids=GROUP,
    )


class Issuer:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.keys = {
            k: rsa.generate_private_key(public_exponent=65537, key_size=2048)
            for k in ("first", "second")
        }
        self.published = ["first"]
        self.requests: list[str] = []
        self.discovery_issuer = settings.oidc_issuer
        self.jwks_uri = f"https://login.microsoftonline.com/{TENANT}/discovery/v2.0/keys"
        self.unavailable = False

    def token(
        self, changes: dict[str, Any] | None = None, kid: str = "first", omit: tuple[str, ...] = ()
    ) -> str:
        now = int(time.time())
        claims = dict(
            iss=self.settings.oidc_issuer,
            aud=self.settings.jwt_audience,
            sub="test-user",
            oid="33333333-3333-4333-8333-333333333333",
            tid=TENANT,
            ver="2.0",
            scp="mcp.access",
            groups=[GROUP],
            iat=now,
            nbf=now,
            exp=now + 300,
        )
        claims.update(changes or {})
        for name in omit:
            claims.pop(name, None)
        return jwt.encode(claims, self.keys[kid], algorithm="RS256", headers={"kid": kid})

    def respond(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(str(request.url))
        if self.unavailable:
            return httpx.Response(503)
        if str(request.url) == self.settings.oidc_discovery_url:
            return httpx.Response(
                200, json={"issuer": self.discovery_issuer, "jwks_uri": self.jwks_uri}
            )
        if str(request.url) == self.jwks_uri:
            keys = []
            for name in self.published:
                key = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(self.keys[name].public_key()))
                keys.append({**key, "kid": name, "use": "sig", "alg": "RS256"})
            return httpx.Response(200, json={"keys": keys})
        raise AssertionError("Untrusted request")

    def client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(transport=httpx.MockTransport(self.respond))


@pytest.fixture
def issuer(settings: Settings) -> Iterator[Issuer]:
    yield Issuer(settings)
