"""Resolve platform SSO/JWT identity and permissions."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from dataclasses import dataclass, field
from threading import Lock
from typing import Any

import httpx

from config import settings
from p6.security_policy import permissions_for_role


class IdentityError(PermissionError):
    pass


@dataclass(slots=True)
class AgentIdentity:
    username: str
    role: str
    permissions: set[str] = field(default_factory=set)
    tenant_id: str | None = None
    org_id: str | None = None
    auth_source: str = "jwt"
    raw_token: str | None = None


class IdentityService:
    def __init__(self) -> None:
        self._perm_cache: dict[str, tuple[float, set[str]]] = {}
        self._lock = Lock()
        self._cache_ttl = 300

    def resolve_bearer(self, token: str | None) -> AgentIdentity:
        raw = str(token or "").strip()
        if not raw:
            if settings.auth_required and not settings.auth_dev_bypass:
                raise IdentityError("authentication required | blocked_by=auth")
            return self._dev_identity()
        if settings.internal_api_token and hmac.compare_digest(raw, settings.internal_api_token):
            perms = permissions_for_role("SYSTEM")
            return AgentIdentity(
                username="__internal__",
                role="SYSTEM",
                permissions=perms,
                auth_source="internal",
                raw_token=raw,
            )
        payload = self._decode_jwt(raw)
        username = str(payload.get("sub") or "").strip()
        if not username:
            raise IdentityError("token missing subject | blocked_by=auth")
        role = str(payload.get("role") or "USER").strip().upper()
        perms = self._load_permissions(username=username, role=role, token=raw)
        return AgentIdentity(
            username=username,
            role=role,
            permissions=perms,
            tenant_id=str(payload.get("tenant_id") or "") or None,
            org_id=str(payload.get("org_id") or "") or None,
            auth_source="jwt",
            raw_token=raw,
        )

    def _dev_identity(self) -> AgentIdentity:
        role = str(settings.auth_dev_role or "APPROVER").strip().upper()
        return AgentIdentity(
            username=str(settings.auth_dev_username or "dev-operator"),
            role=role,
            permissions=permissions_for_role(role),
            auth_source="dev_bypass",
        )

    def _decode_jwt(self, token: str) -> dict[str, Any]:
        secret = str(settings.jwt_secret or "").strip()
        if not secret:
            raise IdentityError("JWT secret not configured | blocked_by=auth")
        parts = token.split(".")
        if len(parts) != 3:
            raise IdentityError("invalid bearer token | blocked_by=auth")
        header_b64, payload_b64, signature = parts
        signing_input = f"{header_b64}.{payload_b64}".encode("utf-8")
        expected = (
            base64.urlsafe_b64encode(hmac.new(secret.encode("utf-8"), signing_input, hashlib.sha256).digest())
            .rstrip(b"=")
            .decode("ascii")
        )
        if not hmac.compare_digest(signature, expected):
            raise IdentityError("invalid bearer signature | blocked_by=auth")
        padded = payload_b64 + "=" * (-len(payload_b64) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded.encode("ascii")))
        exp = payload.get("exp")
        if exp is not None and int(exp) < int(time.time()):
            raise IdentityError("token expired | blocked_by=auth")
        return payload if isinstance(payload, dict) else {}

    def _load_permissions(self, *, username: str, role: str, token: str) -> set[str]:
        base = permissions_for_role(role)
        if not settings.auth_fetch_permissions_from_core or not settings.core_service_url:
            return base
        cache_key = f"{username}:{role}"
        now = time.time()
        with self._lock:
            cached = self._perm_cache.get(cache_key)
            if cached and cached[0] > now:
                return set(cached[1])
        merged = set(base)
        try:
            url = settings.core_service_url.rstrip("/") + "/api/auth/permissions"
            headers = {"Authorization": f"Bearer {token}"}
            with httpx.Client(timeout=5.0) as client:
                res = client.get(url, headers=headers)
            if res.status_code == 200:
                body = res.json()
                items = body.get("data") if isinstance(body, dict) else body
                if isinstance(items, list):
                    merged.update(str(item).strip() for item in items if str(item).strip())
        except Exception:
            pass
        with self._lock:
            self._perm_cache[cache_key] = (now + self._cache_ttl, set(merged))
        return merged


identity_service = IdentityService()
