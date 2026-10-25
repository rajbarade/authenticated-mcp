"""Fail-closed configuration for the single-tenant Entra pilot."""

from urllib.parse import urlsplit
from uuid import UUID

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    mcp_public_url: str
    auth_provider: str = "entra"
    tenant_id: str
    oidc_issuer: str
    oidc_discovery_url: str | None = None
    jwt_audience: str
    required_scopes: str = "mcp.access"
    allowed_group_ids: str
    log_level: str = "INFO"

    @model_validator(mode="after")
    def validate_trust(self) -> "Settings":
        if self.auth_provider != "entra":
            raise ValueError("Only entra is implemented")
        if str(UUID(self.tenant_id)) != self.tenant_id:
            raise ValueError("TENANT_ID must be a canonical UUID")
        expected = f"https://login.microsoftonline.com/{self.tenant_id}/v2.0"
        if self.oidc_issuer != expected:
            raise ValueError("OIDC_ISSUER must be the exact tenant v2 issuer")
        discovery = expected + "/.well-known/openid-configuration"
        if self.oidc_discovery_url not in (None, discovery):
            raise ValueError("Discovery override must match trusted tenant discovery")
        self.oidc_discovery_url = discovery
        url = urlsplit(self.mcp_public_url)
        if (
            url.scheme != "https"
            or not url.hostname
            or url.path != "/mcp"
            or url.query
            or url.fragment
            or url.username
            or url.password
        ):
            raise ValueError("MCP_PUBLIC_URL must be an HTTPS origin plus /mcp")
        if not self.jwt_audience.strip() or any(c.isspace() for c in self.jwt_audience):
            raise ValueError("JWT_AUDIENCE must be one exact audience")
        if not self.scopes or any(
            not s.replace(".", "").replace("_", "").isalnum() for s in self.scopes
        ):
            raise ValueError("REQUIRED_SCOPES must contain short scope claim values")
        if not self.groups:
            raise ValueError("At least one group ID is required")
        for group in self.groups:
            if str(UUID(group)) != group:
                raise ValueError("Group IDs must be canonical UUIDs")
        if self.log_level not in {"INFO", "WARNING", "ERROR", "CRITICAL"}:
            raise ValueError("Verbose logging is disabled to protect credentials")
        return self

    @property
    def scopes(self) -> frozenset[str]:
        return frozenset(self.required_scopes.split())

    @property
    def groups(self) -> frozenset[str]:
        return frozenset(g.strip() for g in self.allowed_group_ids.split(",") if g.strip())

    @property
    def metadata_url(self) -> str:
        return (
            self.mcp_public_url.removesuffix("/mcp") + "/.well-known/oauth-protected-resource/mcp"
        )

    @property
    def oauth_scopes(self) -> list[str]:
        return [f"{self.mcp_public_url}/{s}" for s in sorted(self.scopes)]
