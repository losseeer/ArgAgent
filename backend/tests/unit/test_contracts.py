"""契约静态断言：state 字段与节点输出无缺失（每次 PR 的 CI 必跑项）。

用集合相等而不是"包含"：多一个字段同样要红——硬约束是"state 里的字段必须有明确写入节点"。
契约真源是 backend/app/graph/state.py 的键集合与本文件的期望集合，两者必须同步改。
"""

import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from app.graph.state import DebateConfig, DebateState  # noqa: E402

# —— 契约字段的唯一真源：改字段必须同步 app/graph/state.py，否则本文件即红 ——
CONFIG_KEYS = {
    "persona",
    "difficulty",
    "strictness",
    "mode",
    "retrieve_thresholds",
    "fallacy_alert_at",
    "temperature",
    "budget_caps",
}

STATE_KEYS = {
    "session_id",
    "user_id",
    "trace_id",
    "turn_index",
    "topic",
    "stance",
    "config",
    "messages",
    "user_claim_ids",
    "fact_claims",
    "predicates",
    "attack_predicates",
    "evidence",
    "retrieval_status",
    "attack_draft",
    "attack_layer",
    "breadth_target",
    "depth_target",
    "stop_reason",
    "fallacy_flags",
    "ledger_hits",
    "cited_claim_ids",
    "agent_self_contradiction",
    "validation",
    "safety",
    "pending_events",
}

# 契约冻结的 14 个端点（方法 + 路径）
ROUTES = {
    ("GET", "/api/healthz"),
    ("POST", "/api/sessions"),
    ("GET", "/api/sessions/{sid}"),
    ("POST", "/api/sessions/{sid}/turns"),
    ("POST", "/api/turns/{tid}/abort"),
    ("POST", "/api/turns/{tid}/{target}/{i}/rebut"),
    ("GET", "/api/sessions/{sid}/ledger"),
    ("GET", "/api/config"),
    ("PUT", "/api/sessions/{sid}/config"),
    ("GET", "/api/memory/patterns"),
    ("POST", "/api/memory/patterns/confirmation"),
    ("DELETE", "/api/memory/patterns"),
    ("POST", "/api/eval/runs"),
    ("GET", "/api/eval/runs/{rid}"),
}


def test_debate_config_keys_match_contract():
    assert set(DebateConfig.__annotations__) == CONFIG_KEYS


def test_debate_state_keys_match_contract():
    assert set(DebateState.__annotations__) == STATE_KEYS


def test_safety_and_validation_slots_exist():
    """safety / validation 两个槽位：降级角标与出口校验的结果都挂在它们上面。"""
    assert {"safety", "validation"} <= STATE_KEYS


def test_endpoint_count_is_fourteen():
    assert len(ROUTES) == 14


def test_routes_expose_all_contracted_endpoints():
    pytest.importorskip("fastapi")
    from app.main import app

    exposed = {
        (method.upper(), path)
        for path, ops in app.openapi()["paths"].items()
        for method in ops
    }
    missing = ROUTES - exposed
    assert not missing, f"契约端点未装配: {missing}"


def test_request_bodies_reject_identity_and_immutable_keys():
    pytest.importorskip("pydantic")
    from pydantic import ValidationError

    from app.api.routes import ConfigUpdate, SessionCreate

    with pytest.raises(ValidationError):
        SessionCreate.model_validate({"topic": "t", "stance": "pro", "user_id": "someone"})
    with pytest.raises(ValidationError):
        ConfigUpdate.model_validate({"difficulty": "brutal", "persona": "coach"})
    with pytest.raises(ValidationError):
        ConfigUpdate.model_validate({"mode": "agent-loop"})
    assert ConfigUpdate.model_validate({"strictness": "loose"}).strictness == "loose"


def test_every_request_body_model_forbids_identity():
    """按模型类扫，不点名：点名那条只覆盖写它时已存在的请求体，后来加的会静默漏在断言之外。

    报错类型必须是 `extra_forbidden`：光看 ValidationError 会被"缺必填字段"顶包，
    一个忘了写 extra='forbid' 的新模型照样绿。
    """
    pytest.importorskip("pydantic")
    import inspect

    from pydantic import BaseModel, ValidationError

    from app.api import routes

    models = [
        obj
        for obj in vars(routes).values()
        if inspect.isclass(obj)
        and issubclass(obj, BaseModel)
        and obj.__module__ == routes.__name__
    ]
    assert len(models) >= 4, "扫描本身没找到请求体模型，这条断言就是空的"

    for model in models:
        with pytest.raises(ValidationError) as caught:
            model.model_validate({"user_id": "someone"})
        assert "extra_forbidden" in [err["type"] for err in caught.value.errors()], model.__name__
