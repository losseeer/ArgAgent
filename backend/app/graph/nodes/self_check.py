"""self_check 节点：出口轻校验（在谬误标注之后、推送之前）。

校验项与 `validation.missing` 的取值口径见 backend/app/graph/state.py 的注释。
本版本真正在查的有三项：

 - `layer_tag`：正文首行没有 [FACT]/[ANALOGY]/[LOGIC] 就没打过层，判不过。
 - `url_unverified`：fact 层、本回合无证据，正文却没标 [UNVERIFIED]——静默即缺陷。
   两档同等要求，不在宽松档放行：能放行就等于允许"没核查也不说"。
   （"强制给 URL、否则打回"那一档要等检索节点接入后才谈得上，现在整个回合不会有证据。）
 - `conclusion_hit`：收尾落在结论上（"你犯了 X 谬误""你错了"）——红线要求打支撑不打结论。

还没接的校验项，`missing` 里就不会出现，别当成已通过：
 `over_budget` 只提示不拦（是 token 预算，不是论证宽度预算，两格不同名同义）；
 `drift` 要看有没有被外部正文带跑，检索未接入时无从判；
 `safety` 由 backend/app/graph/safety.py 提供，见该文件。

agent 侧自查（自己前后矛盾）要读台账，台账还没表，故 `agent_self_contradiction` 恒为 None、
不产认错文案。这条不影响重试判定，但意味着"AI 自动认错"目前还没有实现。
"""

import re
from collections.abc import Mapping
from typing import Any

from langchain_core.runnables import RunnableConfig

MAX_ATTEMPTS = 2

_UNVERIFIED = "[UNVERIFIED]"
# 打的是"结论"而不是"支撑"的句式。宁可少判，也不在这儿引入一个误拦率不明的正则大军。
_CONCLUSION_HIT = re.compile(
    r"(你(其实|根本|明明)?(错了|不对)|你犯了.{0,12}谬误|这个结论(不成立|是错的))"
)


def check_draft(state: Mapping[str, Any]) -> list[str]:
    missing: list[str] = []
    draft = str(state["attack_draft"])
    if state["attack_layer"] is None:
        missing.append("layer_tag")
    if state["attack_layer"] == "fact" and not state["evidence"] and _UNVERIFIED not in draft:
        missing.append("url_unverified")
    tail = draft.strip().splitlines()[-1] if draft.strip() else ""
    if _CONCLUSION_HIT.search(tail):
        missing.append("conclusion_hit")
    return missing


async def self_check_node(state: Mapping[str, Any], config: RunnableConfig) -> dict[str, Any]:
    attempt = int(state["validation"].get("attempt", 0)) + 1
    missing = check_draft(state)
    passed = not missing
    events = list(state["pending_events"])
    if not passed and attempt < MAX_ATTEMPTS:
        # 到限那一次不发这个事件：前端此时要看到的是终态，不是"正在补全标注"。
        events.append(
            {"event": "validation.failed", "data": {"missing": missing, "attempt": attempt}}
        )
    return {
        "validation": {"passed": passed, "missing": missing, "attempt": attempt},
        "agent_self_contradiction": None,
        "pending_events": events,
    }
