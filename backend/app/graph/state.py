"""§6.11 状态与配置契约的落地（字段级唯一真源是 §6.11，§6.3 只是概念示意）。

硬约束（§6.11 抬头）：每个节点的输出字段必须在 DebateState 有槽位，
反之 state 里的字段必须有明确写入节点——缺字段视为 bug，不做兜底推断。
CI 的契约静态断言见 tests/unit/test_contracts.py。
"""

from typing import Literal, TypedDict

Persona = Literal["opponent", "coach", "balanced"]
Difficulty = Literal["casual", "competitive", "brutal"]
Strictness = Literal["strict", "loose"]
Mode = Literal["workflow", "agent-loop"]
Layer = Literal["fact", "analogy", "logic"]
RetrievalStatus = Literal["skipped", "ok", "unavailable", "rate_limited"]


class DebateConfig(TypedDict):
    """会话级 config；中途可写的只有 difficulty / strictness（Q6 已决），其余新会话才生效。"""

    persona: Persona                    # 常量 `opponent`，不进 PUT /config
    difficulty: Difficulty              # 可中途改，自下一回合生效
    strictness: Strictness              # 可中途改；只改阈值 + Prompt + 采样，不改图（§6.8）
    mode: Mode                          # 选 builder（§6.10），只能新会话定
    retrieve_thresholds: dict[str, float]  # 每类一个 confidence 阈值，只对 §6.14 五类生效
    fallacy_alert_at: float             # strict 0.50 / loose 0.75（§6.8）
    temperature: float                  # strict 0.2 / loose 0.6
    budget_caps: dict[str, int]         # 超了只在 UsagePanel 提示、不拦（Q10 已决）


class DebateState(TypedDict):
    # —— 身份与追踪 ——
    session_id: str
    # 服务端生成的 device-local id；任何端点不接受客户端传来的同名字段（Q7）
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
    predicates: list[dict]              # §7.3 v0 判定输入；pred_id 为 None 即该句不判
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

    # —— 出口校验与安全（§6.4#9 / §6.2 OUTPUT 行）——
    validation: dict                    # {passed, missing[], attempt}；missing 枚举见 §6.11
    # {mode, input_hit, output_hit}——SSE safety.* 与 N8 的唯一数据源
    safety: dict | None
    pending_events: list[dict]          # 待推送 SSE 事件队列（§6.12）
