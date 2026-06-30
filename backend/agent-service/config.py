from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_SERVICE_ROOT = Path(__file__).resolve().parent
_PLATFORM_ENV = _SERVICE_ROOT.parent.parent / ".env"


def _read_dotenv_file(path: Path | None = None) -> dict[str, str]:
    """Load key=value pairs from a .env file."""
    env_path = path or (_SERVICE_ROOT / ".env")
    if not env_path.is_file():
        return {}
    values: dict[str, str] = {}
    for line in env_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, _, raw_value = stripped.partition("=")
        values[key.strip()] = raw_value.strip()
    return values


def _merged_env_files() -> dict[str, str]:
    """Platform root .env first, then service .env overrides."""
    merged = _read_dotenv_file(_PLATFORM_ENV)
    merged.update(_read_dotenv_file(_SERVICE_ROOT / ".env"))
    return merged


class Settings(BaseSettings):
    """Runtime configuration for agent-service."""

    service_name: str = "agent-service"
    version: str = "0.1.0"
    host: str = "0.0.0.0"
    port: int = 8010
    audit_store_path: Optional[str] = Field(default="data/audit/audit_events.sqlite3", description="SQLite path for formal append-only audit storage.")
    jwt_secret: Optional[str] = Field(default=None, description="Platform JWT secret (shared with core-service SSO).")
    runtime_env: str = Field(
        default="development",
        description="Runtime environment label: development | production. Used for security startup checks.",
    )
    auth_required: bool = Field(default=False, description="Require Bearer JWT on protected agent endpoints.")
    auth_dev_bypass: bool = Field(default=True, description="Allow dev identity when auth_required=false and no Bearer token.")
    auth_dev_username: str = Field(default="dev-operator", description="Username used by auth dev bypass.")
    auth_dev_role: str = Field(default="APPROVER", description="Role used by auth dev bypass.")
    auth_fetch_permissions_from_core: bool = Field(
        default=True,
        description="Hydrate permission codes from core-service /api/auth/permissions when Bearer present.",
    )
    core_service_url: str = "http://127.0.0.1:8085"
    internal_api_token: Optional[str] = None
    core_api_key: Optional[str] = None
    platform_api_mode: str = "hybrid"  # mock | live | hybrid
    session_store_path: Optional[str] = Field(
        default="data/sessions",
        description="Directory for durable session/message JSONL storage. Set empty to disable persistence.",
    )
    session_context_window: int = Field(default=12, description="Recent messages included in session context.")
    run_store_path: Optional[str] = Field(
        default="data/run_state",
        description="Directory for cross-instance run handoff state (page-result/confirm/clarify). Set empty to disable.",
    )
    long_term_memory_enabled: bool = Field(default=True, description="Enable cross-session vector memory retrieval.")
    long_term_memory_search_limit: int = Field(default=5, description="Top-K long-term memories injected into chat context.")
    long_term_memory_min_score: float = Field(
        default=0.12,
        description="Minimum cosine score for a long-term memory to be injected into chat context (avoids prompt noise).",
    )
    prometheus_url: Optional[str] = Field(default=None, description="Optional Prometheus UI base URL for trace deep-links.")
    grafana_url: Optional[str] = Field(default=None, description="Optional Grafana base URL for trace dashboards.")
    loki_url: Optional[str] = Field(default=None, description="Optional Loki/Grafana Explore base URL for log queries.")
    agentic_max_turns: int = Field(default=100, ge=1, le=100, description="Max LLM turns per run/stream session.")
    agentic_max_tools_per_turn: int = Field(default=8, description="Max tool calls per LLM turn.")
    agentic_tools_schema_limit: int = Field(
        default=36,
        description="Max MCP tools exposed in each LLM request (execution allowlist unchanged).",
    )
    agentic_ui_actions_schema_limit: int = Field(
        default=64,
        description="Legacy flat hap_ui_action cap (hierarchical mode uses page_roots/actions limits).",
    )
    agentic_page_roots_schema_limit: int = Field(
        default=48,
        description="Max page root operation tools exposed per LLM turn.",
    )
    agentic_page_actions_schema_limit: int = Field(
        default=60,
        description="Max page child operation tools exposed per LLM turn.",
    )
    agentic_ui_action_desc_max_chars: int = Field(
        default=256,
        description="Max chars per ui_action agent description line in tool schema glossary.",
    )
    agentic_ui_action_glossary_max_chars: int = Field(
        default=12000,
        description="Max total chars for ui_action glossary (legacy flat mode).",
    )
    agentic_stream_enabled: bool = Field(default=True, description="Enable SSE streaming for run/stream.")
    agentic_page_result_timeout_seconds: float = Field(
        default=30.0,
        description="Max wait for POST /run/{id}/page-result during hap_ui_action.",
    )
    agentic_confirm_timeout_seconds: float = Field(
        default=30.0,
        description="Fallback confirm wait (seconds) for unknown/low-risk confirm gates.",
    )
    agentic_confirm_timeout_medium_seconds: float = Field(
        default=90.0,
        description="Max wait for user confirm on medium-risk tool/page actions.",
    )
    agentic_confirm_timeout_high_seconds: float = Field(
        default=180.0,
        description="Max wait for user confirm on high-risk tool/page actions.",
    )
    agentic_clarify_timeout_seconds: float = Field(
        default=120.0,
        description="Max wait for user clarification during hap_request_clarification.",
    )
    agent_model_enabled: bool = Field(default=True, description="Enable agentic LLM path.")
    agent_model_provider: str = Field(default="mock", description="mock | openai_compatible")
    agent_model_base_url: str = Field(
        default="https://api.deepseek.com",
        description="OpenAI-compatible API base URL (DeepSeek / 豆包 / OpenAI).",
    )
    agent_model_api_key: Optional[str] = Field(default=None)
    agent_model_name: str = Field(default="deepseek-v4-pro")
    agent_model_timeout_seconds: float = Field(default=60.0)
    agent_model_temperature: float = Field(default=0.1)
    agent_model_max_tokens: int = Field(default=2048)
    agent_model_use_tools: bool = Field(default=True)
    agent_model_thinking_enabled: bool = Field(default=True)
    agent_model_reasoning_effort: str = Field(
        default="high",
        description="DeepSeek thinking mode effort: low | high | max.",
    )
    agent_model_fallback_to_rules: bool = Field(default=True, description="Fallback to MockAgenticLlm when LLM fails.")
    agent_model_stream_enabled: bool = Field(
        default=True,
        description="Stream LLM tokens via SSE (reasoning_delta / assistant_delta) instead of waiting for full response.",
    )

    model_config = SettingsConfigDict(env_file=".env", env_prefix="AGENT_", extra="ignore")

    @model_validator(mode="after")
    def _apply_platform_env_aliases(self) -> "Settings":
        if not self.internal_api_token:
            self.internal_api_token = (
                os.getenv("AGENT_INTERNAL_API_TOKEN")
                or os.getenv("INTERNAL_API_TOKEN")
                or None
            )
        if self.core_service_url == "http://127.0.0.1:8085":
            override = os.getenv("AGENT_CORE_SERVICE_URL") or os.getenv("CORE_SERVICE_URL")
            if override:
                self.core_service_url = override
        mode = os.getenv("AGENT_PLATFORM_API_MODE")
        if mode:
            self.platform_api_mode = mode
        if not self.jwt_secret:
            file_env = _merged_env_files()
            self.jwt_secret = (
                os.getenv("AGENT_JWT_SECRET")
                or os.getenv("JWT_SECRET")
                or file_env.get("AGENT_JWT_SECRET")
                or file_env.get("JWT_SECRET")
            )
        auth_required = os.getenv("AGENT_AUTH_REQUIRED")
        if auth_required is not None:
            self.auth_required = auth_required.strip().lower() in {"1", "true", "yes", "on"}
        dev_bypass = os.getenv("AGENT_AUTH_DEV_BYPASS")
        if dev_bypass is not None:
            self.auth_dev_bypass = dev_bypass.strip().lower() in {"1", "true", "yes", "on"}
        if os.getenv("AGENT_AUTH_DEV_USERNAME"):
            self.auth_dev_username = os.getenv("AGENT_AUTH_DEV_USERNAME", self.auth_dev_username)
        if os.getenv("AGENT_AUTH_DEV_ROLE"):
            self.auth_dev_role = os.getenv("AGENT_AUTH_DEV_ROLE", self.auth_dev_role)
        fetch_perms = os.getenv("AGENT_AUTH_FETCH_PERMISSIONS")
        if fetch_perms is not None:
            self.auth_fetch_permissions_from_core = fetch_perms.strip().lower() in {"1", "true", "yes", "on"}
        self._apply_agent_model_env_aliases()
        return self

    def _apply_agent_model_env_aliases(self) -> None:
        """AGENT_MODEL_* overrides (not covered by AGENT_ prefix on field names)."""
        mapping = {
            "agent_model_enabled": "AGENT_MODEL_ENABLED",
            "agent_model_provider": "AGENT_MODEL_PROVIDER",
            "agent_model_base_url": "AGENT_MODEL_BASE_URL",
            "agent_model_api_key": "AGENT_MODEL_API_KEY",
            "agent_model_name": "AGENT_MODEL_NAME",
            "agent_model_timeout_seconds": "AGENT_MODEL_TIMEOUT_SECONDS",
            "agent_model_temperature": "AGENT_MODEL_TEMPERATURE",
            "agent_model_max_tokens": "AGENT_MODEL_MAX_TOKENS",
            "agent_model_use_tools": "AGENT_MODEL_USE_TOOLS",
            "agent_model_thinking_enabled": "AGENT_MODEL_THINKING_ENABLED",
            "agent_model_reasoning_effort": "AGENT_MODEL_REASONING_EFFORT",
            "agent_model_fallback_to_rules": "AGENT_MODEL_FALLBACK_TO_RULES",
            "agent_model_stream_enabled": "AGENT_MODEL_STREAM_ENABLED",
        }
        file_env = _merged_env_files()
        for attr, env_key in mapping.items():
            raw = os.getenv(env_key) or file_env.get(env_key)
            if raw is None or raw == "":
                continue
            current = getattr(self, attr)
            if isinstance(current, bool):
                setattr(self, attr, raw.strip().lower() in {"1", "true", "yes", "on"})
            elif isinstance(current, int):
                setattr(self, attr, int(raw))
            elif isinstance(current, float):
                setattr(self, attr, float(raw))
            else:
                setattr(self, attr, raw.strip())


settings = Settings()
