from dataclasses import dataclass
from typing import Protocol


class InvalidToken(Exception):
    """No authenticated identity; never expose validation internals."""


class InsufficientScope(Exception):
    """Authenticated delegated token lacks a required scope."""


@dataclass(frozen=True)
class Principal:
    subject: str
    tenant: str
    scopes: frozenset[str]
    groups: frozenset[str]
    groups_overage: bool = False


class TokenValidator(Protocol):
    async def validate(self, token: str) -> Principal: ...
