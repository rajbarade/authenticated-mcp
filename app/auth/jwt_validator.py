"""PyJWT verification with a bounded, trusted, async discovery/JWKS cache."""

import asyncio
import time
from typing import Any

import httpx
import jwt

from app.auth.principal import InsufficientScope, InvalidToken, Principal
from app.auth.providers.entra import map_principal, trusted_jwks_url
from app.config import Settings


class JWTValidator:
    def __init__(self, settings: Settings, client: httpx.AsyncClient) -> None:
        self.settings = settings
        self.client = client
        self._keys: dict[str, Any] = {}
        self._expires = 0.0
        self._next_refresh = 0.0
        self._lock = asyncio.Lock()

    async def _json(self, url: str) -> dict[str, Any]:
        # Never follow issuer redirects; cap response bytes before parsing JSON.
        async with (
            asyncio.timeout(10),
            self.client.stream("GET", url, follow_redirects=False, timeout=5) as response,
        ):
            response.raise_for_status()
            data = bytearray()
            async for chunk in response.aiter_bytes():
                data.extend(chunk)
                if len(data) > 262144:
                    raise InvalidToken()
        import json

        value = json.loads(data)
        if not isinstance(value, dict):
            raise InvalidToken()
        return value

    async def _key(self, kid: str) -> Any:
        async with self._lock:
            now = time.monotonic()
            if now < self._expires and kid in self._keys:
                return self._keys[kid]
            if now < self._next_refresh:
                raise InvalidToken()
            # Unknown-kid floods cause at most one refresh per 30s per process.
            self._next_refresh = now + 30
            discovery = await self._json(str(self.settings.oidc_discovery_url))
            if discovery.get("issuer") != self.settings.oidc_issuer:
                raise InvalidToken()
            uri = discovery.get("jwks_uri")
            if not isinstance(uri, str) or not trusted_jwks_url(uri, self.settings.tenant_id):
                raise InvalidToken()
            document = await self._json(uri)
            keys: dict[str, Any] = {}
            for key in document.get("keys", []):
                if not isinstance(key, dict):
                    raise InvalidToken()
                key_id = key.get("kid")
                if (
                    key.get("kty") != "RSA"
                    or key.get("use", "sig") != "sig"
                    or key.get("alg", "RS256") != "RS256"
                    or "verify" not in key.get("key_ops", ["verify"])
                ):
                    continue
                key_issuer = key.get("issuer", self.settings.oidc_issuer)
                if (
                    not isinstance(key_issuer, str)
                    or key_issuer.replace("{tenantid}", self.settings.tenant_id)
                    != self.settings.oidc_issuer
                ):
                    continue
                if not isinstance(key_id, str) or not key_id or key_id in keys:
                    raise InvalidToken()
                parsed = jwt.PyJWK.from_dict(key, algorithm="RS256").key
                if parsed.key_size < 2048:
                    raise InvalidToken()
                keys[key_id] = parsed
            if not keys:
                raise InvalidToken()
            self._keys = keys
            self._expires = time.monotonic() + 300
            if kid not in keys:
                raise InvalidToken()
            return keys[kid]

    async def validate(self, token: str) -> Principal:
        try:
            if len(token) > 32768:
                raise InvalidToken()
            header = jwt.get_unverified_header(token)
            if header.get("alg") != "RS256" or header.get("crit"):
                raise InvalidToken()
            kid = header.get("kid")
            if not isinstance(kid, str) or not kid or len(kid) > 256:
                raise InvalidToken()
            key = await self._key(kid)
            claims = jwt.decode(
                token,
                key,
                algorithms=["RS256"],
                audience=self.settings.jwt_audience,
                issuer=self.settings.oidc_issuer,
                options={"require": ["exp", "iat", "nbf", "iss", "aud", "sub"], "strict_aud": True},
            )
            if any(type(claims[k]) is not int for k in ("exp", "iat", "nbf")):
                raise InvalidToken()
            principal = map_principal(claims, self.settings.tenant_id)
        except (
            TimeoutError,
            jwt.PyJWTError,
            httpx.HTTPError,
            ValueError,
            TypeError,
            KeyError,
            AttributeError,
        ) as exc:
            raise InvalidToken() from exc
        if not self.settings.scopes <= principal.scopes:
            raise InsufficientScope()
        return principal
