"""lineage_project_create live/mock behavior."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from services.lineage_project_tool import build_create_project_body, normalize_project_datatype
from services.mcp_server import mcp_server


def test_normalize_project_datatype_maps_text() -> None:
    assert normalize_project_datatype("TEXT") == "text"
    assert normalize_project_datatype("文本") == "text"
    assert normalize_project_datatype("text") == "text"


def test_build_create_project_body() -> None:
    body = build_create_project_body({"name": "测试数据", "dataType": "TEXT"})
    assert body == {"name": "测试数据", "dataType": "text"}


def test_lineage_project_create_live_success(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("config.settings.platform_api_mode", "live")

    client = MagicMock()
    client.create_lineage_project.return_value = {
        "code": 0,
        "data": {"id": 42, "name": "测试数据", "dataType": "text"},
    }

    def fake_get_client():
        return client

    monkeypatch.setattr("services.platform_api_client.get_platform_api_client", fake_get_client)

    result = mcp_server.invoke(
        "lineage_project_create",
        {"name": "测试数据", "dataType": "TEXT"},
    )
    assert result["status"] == "ok"
    assert result["real_execution"] is True
    assert result["mock_only"] is False
    assert result["project_id"] == "42"
    assert result["name"] == "测试数据"
    client.create_lineage_project.assert_called_once()
    call_body = client.create_lineage_project.call_args[0][0]
    assert call_body["dataType"] == "text"


def test_lineage_project_create_mock_mode_flags_mock_only(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("config.settings.platform_api_mode", "mock")
    result = mcp_server.invoke(
        "lineage_project_create",
        {"name": "测试数据", "dataType": "TEXT"},
    )
    assert result["status"] == "ok"
    assert result.get("mock_only") is True
    assert result.get("real_execution") is False
