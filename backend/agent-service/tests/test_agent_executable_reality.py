"""Agent executable ops must use real anchors/registry — no runtime fallback fake data."""

from __future__ import annotations

import subprocess
from pathlib import Path

PLATFORM_ROOT = Path(__file__).resolve().parents[3]
FRONTEND_ROOT = PLATFORM_ROOT / "frontend"
CONTROLLER = FRONTEND_ROOT / "src/components/AgentShell/AgentPageController.ts"
RUNNER = Path(__file__).resolve().parents[1] / "services/agentic_runner.py"


def _run_node_script(script_name: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["node", str(FRONTEND_ROOT / "scripts" / script_name)],
        cwd=str(FRONTEND_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )


def test_no_page_controller_selector_fallback() -> None:
    source = CONTROLLER.read_text(encoding="utf-8")
    assert "defaultActionSelector" not in source
    assert "resolveActionSelector" in source
    assert "action?.selector" in source


def test_no_mock_page_result_auto_success() -> None:
    source = RUNNER.read_text(encoding="utf-8")
    assert "mock page ok" not in source


def test_verify_agent_page_anchors_passes() -> None:
    result = _run_node_script("verify-agent-page-anchors.mjs")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "missing explicit anchor: 0" in result.stdout


def test_verify_agent_registry_passes() -> None:
    result = _run_node_script("verify-agent-registry.mjs")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "missing registry entry: 0" in result.stdout


def test_verify_agent_executable_bundle_passes() -> None:
    result = _run_node_script("verify-agent-executable.mjs")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "no fallback" in result.stdout


def test_backend_catalog_matches_frontend() -> None:
    backend_catalog = Path(__file__).resolve().parents[1] / "data/platform_operations_catalog.json"
    frontend_catalog = FRONTEND_ROOT / "src/components/AgentShell/platformOperationsCatalog.json"
    assert backend_catalog.read_text(encoding="utf-8") == frontend_catalog.read_text(encoding="utf-8")
