"""attack 节点：一个回合的关键攻击正文，边生成边推 `message.delta`。

降级链用哪一层由 `chain.stream()` 决定；降层的 `llm.fallback` 事件一定排在第一个字之前，
所以顶栏角标不会晚于正文——这是"不静默替换"在本节点的实现点。

口径写在这里：
 - 层标签从正文首行解析，解析不出就置 `attack_layer=None`，由 self_check 判为不过；
   本节点不自检也不替模型补标签。
 - `breadth_target` 按"1 个主攻 + 副点数"算，副点数 = clamp(断言数-1, 0, 难度上限)；
   本节点只把目标写进 state 供断言用，早停回调尚未接入，故 `stop_reason` 恒为 None。
 - `attack_predicates` 与用户侧同理：词表未接入前恒为空数组，schema 先到位。
 - 生成长度用 factory 的默认值，不去读 `budget_caps`——那一格是"超了只提示不拦"的
   token 预算（见 backend/app/graph/state.py 的注释），拿它当硬截断会把提示变成拦截。
"""

from collections.abc import Mapping
from typing import Any

from langchain_core.runnables import RunnableConfig
from langgraph.config import get_stream_writer

from ...llm.factory import from_config
from ...llm.fallback import TEMPLATE_REPLY
from ...prompts.system_main import ATTACK_TASK, persona
from .classify import last_user_text

_LAYERS = {"[FACT]": "fact", "[ANALOGY]": "analogy", "[LOGIC]": "logic"}
_SIDE_POINT_CAP = {"casual": 0, "competitive": 1, "brutal": 2}


def detect_layer(text: str) -> str | None:
    head = text.lstrip()[:12].upper()
    for tag, layer in _LAYERS.items():
        if head.startswith(tag):
            return layer
    return None


def breadth_target(state: Mapping[str, Any]) -> int:
    cap = _SIDE_POINT_CAP.get(str(state["config"]["difficulty"]), 1)
    return 1 + max(0, min(len(state["fact_claims"]) - 1, cap))


def attack_context(state: Mapping[str, Any]) -> str:
    lines = [f"辩题：{state['topic']}", f"我的立场：{state['stance']}"]
    claims = [str(c["text"]) for c in state["fact_claims"]]
    if claims:
        lines.append("对方给出的断言：" + "；".join(claims))
    lines.append(f"对方这轮的原话：{last_user_text(state)}")
    return "\n".join(lines)


async def attack_node(state: Mapping[str, Any], config: RunnableConfig) -> dict[str, Any]:
    chain = from_config(config)
    cfg = state["config"]
    writer = get_stream_writer()
    attempt = int(state["validation"].get("attempt", 0))
    text = ""
    async for kind, payload in chain.stream(
        system=f"{persona(cfg['difficulty'], cfg['strictness'])}\n\n{ATTACK_TASK}",
        user=attack_context(state),
        temperature=cfg["temperature"],
        template=TEMPLATE_REPLY,
    ):
        if kind == "fallback":
            writer(payload)
        elif kind == "delta":
            writer({"event": "message.delta", "data": {"text": payload, "attempt": attempt}})
        elif kind == "done":
            text = str(payload.text)
    return {
        "attack_draft": text,
        "attack_layer": detect_layer(text),
        "attack_predicates": [],
        "breadth_target": breadth_target(state),
        "depth_target": 1,
        "stop_reason": None,
        "pending_events": list(state["pending_events"]) + chain.drain_events(),
    }
