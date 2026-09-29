"""降级链的末端：没有可用模型时说什么，以及降级事件的唯一构造点。

降级不静默：每降一层都要发一条 `llm.fallback`，由 `backend/app/llm/factory.py` 产出、
节点收进 `DebateState.pending_events`（见 backend/app/graph/state.py），前端据此挂顶栏角标。
事件的字段名只在本文件拼一次，避免各处写出第三种拼法。
"""

TIER_PRIMARY = 0
TIER_LOCAL = 1
TIER_TEMPLATE = 2

TEMPLATE_REPLY = "请先确认你的核心断言。"


def fallback_event(tier: int, reason: str) -> dict:
    """构造一条待推送的降级事件（只在真的降了层时调用）。"""
    return {"event": "llm.fallback", "data": {"tier": tier, "reason": reason}}
