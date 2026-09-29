"""classify 节点：意图 + 三层断言 + 待核查断言 + 谓词，同一次结构化调用产出。

字段口径见 backend/app/graph/state.py，契约断言见 backend/tests/unit/test_contracts.py。

三处"算出来但不写状态"的，都是 backend/app/graph/state.py 里没有槽位的东西：
 - `intent` / `layer_hint`：这是有意即弃而非漏配——`intent` 的落点是路由条件边、`layer_hint` 只影响
   下一句措辞，都不跨节点，所以契约里标了「即弃」（见节点契约表的两种归宿说明）；
   请求的 schema 里仍带着它们，是为了出口契约一次到位、免得后续期再改出口。
 - `predicates`：词表尚未接入（backend/app/memory/predicate_match.py 是空壳），恒为空数组；
 - 用户断言入台账：那是 backend/app/memory/claim_ledger.py 的活，尚未接线，
   故 `user_claim_ids` 本版本恒为空。
没有可用模型时不猜意图：`fact_claims` 置空、流程照走，classify 的失败兜底就是"当普通论证处理"。
"""

import json
from collections.abc import Mapping
from typing import Any

from langchain_core.runnables import RunnableConfig

from ...llm.factory import from_config
from ...prompts.system_main import CLASSIFY_TASK, persona


def parse_json_object(raw: str) -> dict[str, Any]:
    """模型偶尔会包一层 ```json；剥掉后仍不是对象就返回空对象。"""
    text = raw.strip().strip("`")
    if text.lower().startswith("json"):
        text = text[4:]
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        return {}
    try:
        loaded = json.loads(text[start : end + 1])
    except ValueError:
        return {}
    return loaded if isinstance(loaded, dict) else {}


def _clean_claims(raw: Any) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        return []
    claims = []
    for item in raw:
        text = item.get("text") if isinstance(item, Mapping) else None
        if isinstance(text, str) and text.strip():
            claims.append({"text": text.strip(), "kind": str(item.get("kind") or "other")})
    return claims


def last_user_text(state: Mapping[str, Any]) -> str:
    for message in reversed(state["messages"]):
        if message.get("role") == "user":
            return str(message.get("content", ""))
    return ""


async def classify_node(state: Mapping[str, Any], config: RunnableConfig) -> dict[str, Any]:
    chain = from_config(config)
    cfg = state["config"]
    result = await chain.complete(
        system=f"{persona(cfg['difficulty'], cfg['strictness'])}\n\n{CLASSIFY_TASK}",
        user=last_user_text(state),
        temperature=0.0,
        max_tokens=400,
        json_mode=True,
        template="{}",
    )
    parsed = parse_json_object(result.text)
    return {
        "fact_claims": _clean_claims(parsed.get("fact_claims")),
        "predicates": [],
        "user_claim_ids": [],
        "pending_events": list(state["pending_events"]) + chain.drain_events(),
    }
