"""agent-service: Agentic multi-turn LLM + MCP + HAP page actions."""

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, PlainTextResponse

from config import settings
from routers.agent import router as agent_router
from services.identity_service import IdentityError
from services.observability_metrics import compute_rates, to_prometheus_lines

logger = logging.getLogger(__name__)


app = FastAPI(
  title=settings.service_name,
  version=settings.version,
  description="Platform Agent: multi-turn LLM selects MCP tools and HAP page actions via run/stream SSE.",
)


@app.on_event("startup")
def _validate_security_config() -> None:
  runtime = str(settings.runtime_env or "development").strip().lower()
  if runtime == "production":
    if not settings.auth_required:
      logger.error("AGENT_RUNTIME_ENV=production but AGENT_AUTH_REQUIRED=false")
    if settings.auth_dev_bypass:
      logger.error("AGENT_RUNTIME_ENV=production but AGENT_AUTH_DEV_BYPASS=true")
    if not str(settings.jwt_secret or "").strip():
      logger.error("AGENT_RUNTIME_ENV=production but AGENT_JWT_SECRET is empty")
  elif not settings.auth_required:
    logger.warning(
      "AGENT_AUTH_REQUIRED=false: unauthenticated requests use dev identity when AGENT_AUTH_DEV_BYPASS=true",
    )


@app.exception_handler(PermissionError)
async def permission_error_handler(_request: Request, exc: PermissionError) -> JSONResponse:
  if isinstance(exc, IdentityError):
    return JSONResponse(
      status_code=401,
      content={"detail": str(exc)},
      headers={"WWW-Authenticate": "Bearer"},
    )
  return JSONResponse(status_code=403, content={"detail": str(exc)})


def _agent_model_health() -> dict[str, Any]:
  configured = bool(settings.agent_model_api_key) or settings.agent_model_provider == "mock"
  return {
    "enabled": settings.agent_model_enabled,
    "provider": settings.agent_model_provider,
    "model": settings.agent_model_name,
    "configured": configured,
  }


@app.get("/metrics")
def prometheus_metrics() -> PlainTextResponse:
  rates = compute_rates()
  return PlainTextResponse(content=to_prometheus_lines(rates), media_type="text/plain; version=0.0.4")


@app.get("/health")
def health_check() -> dict[str, Any]:
  return {
    "status": "ok",
    "service": settings.service_name,
    "version": settings.version,
    "architecture": "mcp_agentic",
    "agent_model": _agent_model_health(),
  }


app.include_router(agent_router)
