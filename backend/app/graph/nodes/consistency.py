"""consistency 节点：用户本回合断言与他自己历史断言的矛盾。

按首版范围本节点是空实现：`predicate_match` 尚未接入（backend/app/memory/predicate_match.py
还是空壳），台账也还没有表（backend/app/memory/sqlite.py 未接线），所以没有可比对的历史。
空实现的口径是"不产生命中"，不是"产出了没命中的结论"——两者对前端是一样的，
对评测不一样，因此这里明确写着：本节点在台账接线前不参与判定。
`user_contradiction_hit` 即便将来产出也是即弃值（契约里标了「即弃」）：它的落点是矛盾台账
`contradictions(who='user')`，不占 state 槽，所以本节点没有对应输出字段。
"""

from collections.abc import Mapping
from typing import Any


async def consistency_node(state: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "ledger_hits": list(state["ledger_hits"]),
        "cited_claim_ids": list(state["cited_claim_ids"]),
    }
