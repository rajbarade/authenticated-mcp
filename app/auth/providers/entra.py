"""Only this adapter understands Entra-specific claims and key URLs."""

from typing import Any
from urllib.parse import urlsplit
from uuid import UUID

from app.auth.principal import InvalidToken, Principal


def trusted_jwks_url(url: str, tenant: str) -> bool:
    parsed = urlsplit(url)
    return (
        parsed.scheme == "https"
        and parsed.netloc == "login.microsoftonline.com"
        and parsed.path in {f"/{tenant}/discovery/v2.0/keys", "/common/discovery/v2.0/keys"}
        and not parsed.query
        and not parsed.fragment
    )


def map_principal(claims: dict[str, Any], tenant: str) -> Principal:
    if claims.get("tid") != tenant or claims.get("ver") != "2.0":
        raise InvalidToken()
    if claims.get("idtyp") == "app" or not isinstance(claims.get("scp"), str):
        raise InvalidToken()
    if not claims["scp"].strip():
        raise InvalidToken()
    try:
        subject = str(UUID(claims["oid"]))
    except (KeyError, ValueError, TypeError, AttributeError) as exc:
        raise InvalidToken() from exc
    groups = claims.get("groups", [])
    # Malformed or absent groups carry no authorization.
    if not isinstance(groups, list) or not all(isinstance(g, str) for g in groups):
        groups = []
    overage = "hasgroups" in claims or "_claim_names" in claims or "_claim_sources" in claims
    return Principal(subject, tenant, frozenset(claims["scp"].split()), frozenset(groups), overage)
