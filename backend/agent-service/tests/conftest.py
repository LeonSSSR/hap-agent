"""Pytest fixtures for Agentic agent-service."""

from __future__ import annotations

import pytest

from config import settings
from services.platform_operations_catalog import clear_catalog_cache


@pytest.fixture(autouse=True)
def _contract_hybrid_platform_mode(request: pytest.FixtureRequest) -> None:
    original_mode = settings.platform_api_mode
    original_provider = settings.agent_model_provider
    settings.platform_api_mode = "hybrid"
    if request.node.get_closest_marker("live") is None:
        settings.agent_model_provider = "mock"
    try:
        yield
    finally:
        settings.platform_api_mode = original_mode
        settings.agent_model_provider = original_provider


@pytest.fixture(autouse=True)
def _reset_catalog_cache() -> None:
    clear_catalog_cache()
    yield
    clear_catalog_cache()


@pytest.fixture(autouse=True)
def _fast_run_waits() -> None:
    original_page = settings.agentic_page_result_timeout_seconds
    settings.agentic_page_result_timeout_seconds = 2.0
    try:
        yield
    finally:
        settings.agentic_page_result_timeout_seconds = original_page
