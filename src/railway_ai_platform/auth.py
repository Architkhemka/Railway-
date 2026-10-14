"""JWT authentication primitives and role-based authorization."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import Enum

import jwt

from railway_ai_platform.config import Settings

_ISSUER = "railway-ai-platform"


class Role(str, Enum):
    PASSENGER = "passenger"
    ANALYST = "analyst"
    GOVERNANCE_ADMIN = "governance-admin"
    AUDITOR = "auditor"


@dataclass(frozen=True)
class Principal:
    subject: str
    role: Role


class AuthenticationError(Exception):
    """Raised when credentials cannot be authenticated."""


class AuthorizationError(Exception):
    """Raised when an authenticated principal lacks a required role."""


class JWTAuth:
    """Issue and verify HS256 access tokens using explicitly configured secrets."""

    def __init__(self, settings: Settings) -> None:
        if settings.jwt_secret is None:
            raise ValueError("JWT_SECRET must be configured before using JWT authentication")
        secret = settings.jwt_secret.get_secret_value()
        if len(secret) < 32:
            raise ValueError("JWT_SECRET must contain at least 32 characters")
        self._secret = secret
        self._expires = timedelta(minutes=settings.jwt_access_token_expire_minutes)

    def issue_token(self, subject: str, role: Role) -> str:
        if not subject.strip():
            raise ValueError("subject must not be empty")
        issued_at = datetime.now(UTC)
        payload = {
            "sub": subject,
            "role": role.value,
            "iss": _ISSUER,
            "iat": issued_at,
            "exp": issued_at + self._expires,
        }
        return jwt.encode(payload, self._secret, algorithm="HS256")

    def verify_token(self, token: str) -> Principal:
        try:
            payload = jwt.decode(token, self._secret, algorithms=["HS256"], issuer=_ISSUER)
            subject = payload["sub"]
            role = Role(payload["role"])
        except (jwt.PyJWTError, KeyError, TypeError, ValueError) as error:
            raise AuthenticationError("invalid or expired access token") from error
        if not isinstance(subject, str) or not subject:
            raise AuthenticationError("invalid or expired access token")
        return Principal(subject=subject, role=role)


def authorize(principal: Principal, *allowed_roles: Role) -> None:
    """Raise when the principal's role is not in the allowed role set."""
    if principal.role not in allowed_roles:
        raise AuthorizationError("the authenticated role is not permitted for this action")
