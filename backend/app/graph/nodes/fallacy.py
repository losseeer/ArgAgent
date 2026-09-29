"""fallacy 节点：给这句用户输入标论证谬误，产出的是"候选"而不是判决。

红线：标注落在支撑关系上，不落在结论上；本节点永不抛错——解析不出 JSON 就当没有谬误。
置信度低于 config['fallacy_alert_at'] 的进 `candidate`，够线的进 `flagged`；
两档怎么渲染（灰色候选 / 红色提示）是前端的事，本文件不复制任何阈值数字。

谬误样例库 `data/seed/fallacy_examples.jsonl` 尚未填数据，所以现在没有任何命中案例可验，
本节点的真实产出精度要等那份标注集落地才谈得上。
"""

import json
from collections.abc import Mapping
from typing import Any

from langchain_core.runnables import RunnableConfig

from ...llm.factory import from_config
from ...prompts.system_main import FALLACY_TASK, persona
from .classify import last_user_text, parse_json_object


def _parse_flags(raw: str) -> list[Any]:
    text = raw.strip().strip("`")
    if text.lower().startswith("json"):
        text = text[4:]
    try:
        loaded = json.loads(text)
    except ValueError:
        nested = parse_json_object(text)
        loaded = nested.get("flags") if nested else None
    if isinstance(loaded, dict):
        loaded = loaded.get("flags")
    return loaded if isinstance(loaded, list) else []


def _normalize(item: Any, msg_id: str, alert_at: float) -> dict[str, Any] | None:
    if not isinstance(item, Mapping):
        return None
    span = item.get("span")
    if not isinstance(span, str) or not span.strip():
        return None
    try:
        confidence = float(item.get("confidence", 0))
    except (TypeError, ValueError):
        return None
    return {
        "type": str(item.get("type") or "unknown"),
        "span": span.strip(),
        "reason": str(item.get("reason") or ""),
        "confidence": max(0.0, min(1.0, confidence)),
        "msg_id": msg_id,
        "status": "flagged" if confidence >= alert_at else "candidate",
    }


async def fallacy_node(state: Mapping[str, Any], config: RunnableConfig) -> dict[str, Any]:
    chain = from_config(config)
    cfg = state["config"]
    user_text = last_user_text(state)
    target_id = state["messages"][-1].get("msg_id", "") if state["messages"] else ""
    result = await chain.complete(
        system=f"{persona(cfg['difficulty'], cfg['strictness'])}\n\n{FALLACY_TASK}",
        user=user_text,
        temperature=0.0,
        max_tokens=300,
        json_mode=True,
        template="[]",
    )
    alert_at = cfg["fallacy_alert_at"]
    flags = [
        flag
        for raw in _parse_flags(result.text)
        if (flag := _normalize(raw, target_id, alert_at))
    ]
    return {
        "fallacy_flags": flags,
        "pending_events": list(state["pending_events"]) + chain.drain_events(),
    }
