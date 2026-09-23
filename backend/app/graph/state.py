"""状态与配置契约的落地：本文件是字段级唯一真源，其余描述仅为概念示意。

硬约束：每个节点的输出字段必须在 DebateState 有槽位，
反之 state 里的字段必须有明确写入节点——缺字段视为 bug，不做兜底推断。
CI 的契约静态断言见 backend/tests/unit/test_contracts.py。
"""

from typing import Literal, TypedDict

Persona = Literal["opponent", "coach", "balanced"]
Difficulty = Literal["casual", "competitive", "brutal"]
Strictness = Literal["strict", "loose"]
Mode = Literal["workflow", "agent-loop"]
Layer = Literal["fact", "analogy", "logic"]
RetrievalStatus = Literal["skipped", "ok", "unavailable", "rate_limited"]


class DebateConfig(TypedDict):
    """会话级 config；中途可写的只有 difficulty / strictness，其余新会话才生效。"""

    persona: Persona                    # 常量 `opponent`，不进 PUT /config
    difficulty: Difficulty              # 可中途改，自下一回合生效
    strictness: Strictness              # 可中途改；只改阈值 + Prompt + 采样，不改图
    mode: Mode                          # 选 builder，只能新会话定
    retrieve_thresholds: dict[str, float]  # 每类一个 confidence 阈值，只对五类检索触发判据生效
    fallacy_alert_at: float             # strict 0.50 / loose 0.75
    temperature: float                  # strict 0.2 / loose 0.6
    budget_caps: dict[str, int]         # 超了只在 UsagePanel 提示、不拦


class DebateState(TypedDict):
    # —— 身份与追踪 ——
    session_id: str
    # 服务端生成的 device-local id；任何端点不接受客户端传来的同名字段
    user_id: str
    trace_id: str
    turn_index: int
    topic: str
    stance: Literal["pro", "con"]
    config: DebateConfig

    # —— 轮内产物（节点写入）——
    messages: list[dict[str, str]]      # [{role, content, ts, msg_id, layer?, fallacy?}]
    user_claim_ids: list[int]
    fact_claims: list[dict]
    predicates: list[dict]              # 谓词比对的判定输入；pred_id 为 None 即该句不判
    attack_predicates: list[dict]
    evidence: list[dict]                # [{url, snippet, score, src, tier}]
    retrieval_status: RetrievalStatus
    attack_draft: str
    attack_layer: Layer | None
    breadth_target: int
    depth_target: int
    stop_reason: str | None
    fallacy_flags: list[dict]           # [{type, span, reason, confidence, msg_id, status}]
    ledger_hits: list[dict]
    cited_claim_ids: list[int]
    agent_self_contradiction: dict | None  # {turn_i, turn_j}

    # —— 出口校验与安全 ——
    validation: dict                    # {passed, missing[], attempt}；missing 取各校验项名
    # {mode, input_hit, output_hit}——SSE safety.* 与角标可见性的唯一数据源
    safety: dict | None
    pending_events: list[dict]          # 待推送 SSE 事件队列
