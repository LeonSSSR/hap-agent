"""FastAPI auth dependencies for agent-service."""

from __future__ import annotations

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from config import settings
from services.identity_service import AgentIdentity, IdentityError, identity_service

_bearer_optional = HTTPBearer(auto_error=False)


async def get_optional_agent_identity(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_optional),
) -> AgentIdentity | None:
    token = credentials.credentials if credentials and credentials.credentials else None
    if not token:
        if settings.auth_dev_bypass and not settings.auth_required:
            return identity_service._dev_identity()
        return None
    try:
        return identity_service.resolve_bearer(token)
    except IdentityError:
        return None


async def require_agent_identity(
    identity: AgentIdentity | None = Depends(get_optional_agent_identity),
) -> AgentIdentity:
    if identity is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return identity
