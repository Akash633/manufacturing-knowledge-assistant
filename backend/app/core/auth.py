from dataclasses import dataclass
from functools import lru_cache
from typing import Callable, FrozenSet, Optional
from urllib.parse import urlparse

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWKClient, PyJWKClientConnectionError, PyJWKClientError

from app.core.config import settings
from app.core.logging import logger


@dataclass(frozen=True)
class AuthenticatedUser:
    subject: str
    roles: FrozenSet[str]


bearer_scheme = HTTPBearer(auto_error=False)


@lru_cache(maxsize=4)
def _get_jwks_client(jwks_url: str) -> PyJWKClient:
    return PyJWKClient(jwks_url)


def oidc_is_configured() -> bool:
    issuer_value = (settings.OIDC_ISSUER or "").strip()
    audience_value = (settings.OIDC_AUDIENCE or "").strip()
    jwks_value = (settings.OIDC_JWKS_URL or "").strip()
    if not issuer_value or not audience_value or not jwks_value:
        return False

    issuer = urlparse(issuer_value)
    jwks_url = urlparse(jwks_value)
    return all(
        parsed.scheme == "https" and parsed.netloc
        for parsed in (issuer, jwks_url)
    )


def _authenticate(
    credentials: Optional[HTTPAuthorizationCredentials],
) -> AuthenticatedUser:
    if not oidc_is_configured():
        raise HTTPException(
            status_code=503,
            detail="Protected actions are unavailable because OIDC authentication is not configured.",
        )
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=401,
            detail="A valid bearer token is required.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        signing_key = _get_jwks_client(settings.OIDC_JWKS_URL).get_signing_key_from_jwt(
            credentials.credentials
        )
        claims = jwt.decode(
            credentials.credentials,
            signing_key.key,
            algorithms=["RS256"],
            audience=settings.OIDC_AUDIENCE,
            issuer=settings.OIDC_ISSUER,
            options={"require": ["exp"]},
        )
    except PyJWKClientConnectionError as exc:
        logger.warning("OIDC signing keys are temporarily unavailable.")
        raise HTTPException(status_code=503, detail="Authentication service is unavailable.") from exc
    except (PyJWKClientError, jwt.PyJWTError) as exc:
        raise HTTPException(
            status_code=401,
            detail="Bearer token is invalid or expired.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    if not isinstance(claims, dict):
        raise HTTPException(
            status_code=401,
            detail="Bearer token has an invalid payload.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    subject = claims.get("sub")
    if not isinstance(subject, str) or not subject.strip():
        raise HTTPException(
            status_code=401,
            detail="Bearer token does not contain a valid subject.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    raw_roles = claims.get(settings.OIDC_ROLES_CLAIM, [])
    if isinstance(raw_roles, str):
        roles = frozenset({raw_roles})
    elif isinstance(raw_roles, list) and all(isinstance(role, str) for role in raw_roles):
        roles = frozenset(raw_roles)
    else:
        raise HTTPException(status_code=403, detail="Bearer token has an invalid roles claim.")

    return AuthenticatedUser(subject=subject, roles=roles)


def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
) -> Optional[AuthenticatedUser]:
    if credentials is None:
        return None
    return _authenticate(credentials)


def require_roles(*required_roles: str) -> Callable:
    def dependency(
        credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    ) -> AuthenticatedUser:
        user = _authenticate(credentials)
        if required_roles and "admin" not in user.roles and not user.roles.intersection(required_roles):
            raise HTTPException(status_code=403, detail="Insufficient role for this action.")
        return user

    return dependency


def require_user_role(user: AuthenticatedUser, *required_roles: str) -> None:
    if "admin" not in user.roles and not user.roles.intersection(required_roles):
        raise HTTPException(status_code=403, detail="Insufficient role for this action.")


def require_optional_user_role(
    user: Optional[AuthenticatedUser], *required_roles: str
) -> AuthenticatedUser:
    if not oidc_is_configured():
        raise HTTPException(
            status_code=503,
            detail="Protected actions are unavailable because OIDC authentication is not configured.",
        )
    if user is None:
        raise HTTPException(
            status_code=401,
            detail="A valid bearer token is required.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    require_user_role(user, *required_roles)
    return user
