"""JWT identity merges role baseline with core-fetched permissions."""

from __future__ import annotations

from services.identity_service import AgentIdentity, IdentityService
from services.agentic_tool_schema import build_agentic_openai_tools
from services.operation_tools import is_operation_tool, operation_tool_name
from services.platform_operations_catalog import clear_catalog_cache
from p6.security_policy import permissions_for_role


def setup_function() -> None:
    clear_catalog_cache()


def test_load_permissions_unions_role_baseline_when_core_returns_empty(monkeypatch) -> None:
    svc = IdentityService()

    class _EmptyResponse:
        status_code = 200

        @staticmethod
        def json() -> dict:
            return {"data": []}

    class _FakeClient:
        def __init__(self, *_args, **_kwargs) -> None:
            pass

        def __enter__(self) -> "_FakeClient":
            return self

        def __exit__(self, *_args) -> None:
            return None

        def get(self, _url: str, **_kwargs) -> _EmptyResponse:
            return _EmptyResponse()

    monkeypatch.setattr("services.identity_service.httpx.Client", _FakeClient)
    perms = svc._load_permissions(username="alice", role="APPROVER", token="jwt-token")
    assert permissions_for_role("APPROVER").issubset(perms)


def test_hierarchical_navigate_tools_not_empty_for_sparse_identity() -> None:
    sparse = AgentIdentity(username="u", role="APPROVER", permissions=set(), auth_source="jwt")
    tools = build_agentic_openai_tools(
        [],
        identity=sparse,
        user_text="打开数据源管理",
        ui_intent="page",
    )
    navigate_tools = [t for t in tools if is_operation_tool(t["function"]["name"])]
    assert navigate_tools
    names = {t["function"]["name"] for t in navigate_tools}
    assert operation_tool_name("dg.sources") in names
