import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from fastmcp import FastMCP
from starlette.applications import Starlette
from starlette.types import ASGIApp

from app.auth.jwt_validator import JWTValidator
from app.auth.middleware import AuthMiddleware
from app.config import Settings
from app.tools.hello import hello_world


def create_app() -> ASGIApp:
    settings = Settings()  # type: ignore[call-arg]
    logging.basicConfig(level=settings.log_level, format="%(message)s")
    for name in ("httpx", "httpcore", "fastmcp", "mcp"):
        logging.getLogger(name).setLevel(logging.WARNING)
    return build_app(settings, httpx.AsyncClient(trust_env=False))


def build_app(settings: Settings, client: httpx.AsyncClient) -> ASGIApp:
    mcp = FastMCP("Authenticated Hello World", mask_error_details=True)
    mcp.tool(hello_world)
    transport = mcp.http_app(path="/mcp", stateless_http=True, json_response=True)

    transport_lifespan = transport.lifespan

    @asynccontextmanager
    async def lifespan(app: Starlette) -> AsyncIterator[None]:
        async with client, transport_lifespan(app):
            yield

    transport.router.lifespan_context = lifespan
    return AuthMiddleware(transport, settings, JWTValidator(settings, client))
