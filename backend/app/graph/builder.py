"""Workflow 状态机的唯一装配点（agent-loop 模式另有 builder，见 builder_agent.py）。

首版范围按状态机图落地：classify → consistency → attack → fallacy → self_check，
self_check 不过且未到上限就回 attack 重写，到限走 fallback 模板分支，两条路都汇到 OUTPUT。
`retrieve` 节点与 safety_hold 分流尚未接入，所以图上没有它们的边——接进来时要改的就是本文件。

`fallback_node` 与 `output_node` 写在本文件：它们不发请求、不碰模型，只做图的收尾，
仓库结构里也没有为它们单开 nodes/ 文件。

一个回合只有一条降级链：由调用方建好 `LlmChain` 经 `config.configurable.llm` 传进来
（取用见 backend/app/llm/factory.py 的 `from_config`），于是这个回合里 classify 与 attack
用的是同一层模型，不会出现"前半句主模型、后半句本地"的拼接。
"""

from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph

from ..llm.factory import from_config
from ..llm.fallback import TEMPLATE_REPLY
from .nodes.attack import attack_node
from .nodes.classify import classify_node
from .nodes.consistency import consistency_node
from .nodes.fallacy import fallacy_node
from .nodes.self_check import self_check_node
from .routing import route_after_self_check
from .state import DebateConfig, DebateState


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


async def fallback_node(state: Mapping[str, Any]) -> dict[str, Any]:
    """出口校验到限仍不过：落模板，并把缺什么原样推给前端（宁缺不藏）。

    这段文字是模板不是模型输出，所以不打层标签——补一个 [LOGIC] 之类就等于把
    "我们没答上来"伪装成"我们打的是逻辑层"。它也不进 agent 台账：台账只收过校验的版本。
    这里发的是 `validation.failed`（校验没过），不是 `llm.fallback`（模型降层），两者不混用。

    模板正文走 `message.delta` 排在 failed 之后，而不是经流式写入：这一稿从没在流里吐过字
    （前面积攒的草稿已被判作废），而前端的口径是"见 failed 清缓冲、之后的 delta 就是终稿"，
    顺序由 pending_events 的追加顺序保证，所以这两条都发在队列里。
    """
    validation = state["validation"]
    attempt = validation.get("attempt", 0)
    events = list(state["pending_events"])
    events.append(
        {
            "event": "validation.failed",
            "data": {"missing": list(validation.get("missing") or []), "attempt": attempt},
        }
    )
    events.append(
        {"event": "message.delta", "data": {"text": TEMPLATE_REPLY, "attempt": attempt}}
    )
    return {"attack_draft": TEMPLATE_REPLY, "attack_layer": None, "pending_events": events}


async def output_node(state: Mapping[str, Any], config: RunnableConfig) -> dict[str, Any]:
    """回合出口：补上 agent 消息，再排好这个回合的收尾事件。

    "先写台账、后推送"的顺序约定要求的写入点就在这个函数，但
    backend/app/memory/claim_ledger.py 目前还是空壳（表都还没建），所以此处暂时无处可写：
    等 ledger 落地时，`validation.passed` 为真的那一版正文要在这里 append 之后再推 SSE，
    被校验否决的重试草稿不留痕。
    """
    chain = from_config(config)
    draft = str(state["attack_draft"])
    msg_id = f"m{state['turn_index']}a"
    message: dict[str, str] = {"role": "agent", "content": draft, "ts": _now(), "msg_id": msg_id}
    layer = state["attack_layer"]
    if layer:
        message["layer"] = str(layer)
    events = list(state["pending_events"])
    if layer:
        events.append(
            {
                "event": "message.layer",
                "data": {"msg_id": msg_id, "spans": [{"text": draft, "layer": layer}]},
            }
        )
    if state["fallacy_flags"]:
        flags = [dict(flag, i=index) for index, flag in enumerate(state["fallacy_flags"])]
        events.append({"event": "fallacy.flags", "data": {"flags": flags}})
    events.append(
        {
            "event": "turn.done",
            "data": {
                "stop_reason": state["stop_reason"],
                "breadth_target": state["breadth_target"],
                "depth_target": state["depth_target"],
                "usage": dict(chain.usage_total),
            },
        }
    )
    return {"messages": list(state["messages"]) + [message], "pending_events": events}


def build_workflow():
    graph = StateGraph(DebateState)
    graph.add_node("classify", classify_node)
    graph.add_node("consistency", consistency_node)
    graph.add_node("attack", attack_node)
    graph.add_node("fallacy", fallacy_node)
    graph.add_node("self_check", self_check_node)
    graph.add_node("fallback", fallback_node)
    graph.add_node("output", output_node)
    graph.add_edge(START, "classify")
    graph.add_edge("classify", "consistency")
    graph.add_edge("consistency", "attack")
    graph.add_edge("attack", "fallacy")
    graph.add_edge("fallacy", "self_check")
    graph.add_conditional_edges(
        "self_check",
        route_after_self_check,
        {"retry": "attack", "fallback": "fallback", "output": "output"},
    )
    graph.add_edge("fallback", "output")
    graph.add_edge("output", END)
    return graph.compile()


_compiled: Any = None


def get_workflow():
    """进程内单例：图本身无状态，状态一律由 initial_state 传进去。

    这里只有 workflow 模式的图。`config.mode` 为 agent-loop 时会静默跑成这张图，
    所以那道分流已经挪到建会话的一格当场拒掉（见 backend/app/api/routes.py 的 create_session），
    能走到这里的 mode 恒为 workflow。agent-loop 的图真装配起来时，分流该回到这里按 mode 选 builder。
    """
    global _compiled
    if _compiled is None:
        _compiled = build_workflow()
    return _compiled


def initial_state(
    *,
    session_id: str,
    user_id: str,
    trace_id: str,
    turn_index: int,
    topic: str,
    stance: str,
    config: DebateConfig,
    user_text: str,
) -> dict[str, Any]:
    """键齐全的初始 state：少一个键，后面的节点就会读到 KeyError 而不是空值。"""
    message = {"role": "user", "content": user_text, "ts": _now(), "msg_id": f"m{turn_index}u"}
    return {
        "session_id": session_id,
        "user_id": user_id,
        "trace_id": trace_id,
        "turn_index": turn_index,
        "topic": topic,
        "stance": stance,
        "config": config,
        "messages": [message],
        "user_claim_ids": [],
        "fact_claims": [],
        "predicates": [],
        "attack_predicates": [],
        "evidence": [],
        "retrieval_status": "skipped",
        "attack_draft": "",
        "attack_layer": None,
        "breadth_target": 1,
        "depth_target": 1,
        "stop_reason": None,
        "fallacy_flags": [],
        "ledger_hits": [],
        "cited_claim_ids": [],
        "agent_self_contradiction": None,
        "validation": {"passed": False, "missing": [], "attempt": 0},
        "safety": None,
        "pending_events": [],
    }


def default_config() -> DebateConfig:
    """新会话的默认旋钮：persona 恒为 opponent，不是用户可写的键。"""
    return {
        "persona": "opponent",
        "difficulty": "competitive",
        "strictness": "strict",
        "mode": "workflow",
        "retrieve_thresholds": {},
        "fallacy_alert_at": 0.5,
        "temperature": 0.2,
        "budget_caps": {},
    }
