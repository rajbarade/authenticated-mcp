import logging

from starlette.datastructures import Headers
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from app.auth.policies import group_allowed
from app.auth.principal import InsufficientScope, InvalidToken, TokenValidator
from app.config import Settings

logger = logging.getLogger("auth")


class AuthMiddleware:
    def __init__(self, app: ASGIApp, settings: Settings, validator: TokenValidator) -> None:
        self.app, self.settings, self.validator = app, settings, validator

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        path = scope["path"]
        if path in {
            "/.well-known/oauth-protected-resource/mcp",
            "/.well-known/oauth-protected-resource",
        } and scope["method"] in {"GET", "HEAD"}:
            await JSONResponse(
                {
                    "resource": self.settings.mcp_public_url,
                    "authorization_servers": [self.settings.oidc_issuer],
                    "scopes_supported": self.settings.oauth_scopes,
                    "bearer_methods_supported": ["header"],
                }
            )(scope, receive, send)
            return
        if path == "/healthz" and scope["method"] in {"GET", "HEAD"}:
            await JSONResponse({"status": "ok"})(scope, receive, send)
            return
        # Protect all remaining paths and methods, including MCP transport redirects.
        headers = Headers(scope=scope).getlist("authorization")
        challenge = f'Bearer resource_metadata="{self.settings.metadata_url}"'
        status, error = 401, "invalid_token"
        try:
            if len(headers) != 1:
                raise InvalidToken()
            scheme, separator, token = headers[0].partition(" ")
            if (
                scheme.lower() != "bearer"
                or not separator
                or not token
                or any(c.isspace() for c in token)
            ):
                raise InvalidToken()
            principal = await self.validator.validate(token)
            if not group_allowed(principal, self.settings.groups):
                status, error = 403, "access_denied"
            else:
                scope.setdefault("state", {})["principal"] = principal
                logger.info('{"event":"auth_allowed"}')
                await self.app(scope, receive, send)
                return
        except InsufficientScope:
            status, error = 403, "insufficient_scope"
        except InvalidToken:
            pass
        logger.warning('{"event":"auth_denied","status":%d,"reason":"%s"}', status, error)
        response_headers = {"Cache-Control": "no-store"}
        if status == 401:
            response_headers["WWW-Authenticate"] = challenge + (
                ', error="invalid_token"' if headers else ""
            )
        elif error == "insufficient_scope":
            scopes = " ".join(self.settings.oauth_scopes)
            response_headers["WWW-Authenticate"] = (
                challenge + f', error="insufficient_scope", scope="{scopes}"'
            )
        await JSONResponse({"error": error}, status_code=status, headers=response_headers)(
            scope, receive, send
        )
