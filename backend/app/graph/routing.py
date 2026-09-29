"""条件边路由：控制流只在这一个文件里决定（不引入 MCP，工具层就是这里的 if-else）。

`state_after_self_check` 是首版唯一生效的路由：通过 → OUTPUT；
不过且自检次数未到上限 → 回 attack 重写；到限 → 走 fallback 模板分支。

还没实现在这里的路由，都写明了缺什么，不装作已经判得出来：
 - `state_after_classify` 的 safety_hold 分流：等 backend/app/graph/safety.py 的输入侧判定；
 - 检索触发判据（哪几类断言值得联网核查）：等检索层，见 backend/app/graph/nodes/retrieve.py；
   在此之前 `retrieval_status` 恒为 skipped，图的走向也就不经过 retrieve。
strict/loose 在这里不改图：两档只换阈值与 Prompt，任何"宽松就跳过某节点"的写法都是错的。
"""

from collections.abc import Mapping
from typing import Any

from .nodes.self_check import MAX_ATTEMPTS


def route_after_self_check(state: Mapping[str, Any]) -> str:
    """返回值即 builder.py 里挂的三条边之一。"""
    validation = state["validation"]
    if validation.get("passed"):
        return "output"
    if int(validation.get("attempt", 0)) >= MAX_ATTEMPTS:
        return "fallback"
    return "retry"
