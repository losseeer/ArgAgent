"""骨架占位文件：只声明职责与契约，尚无实现。

 - 用户断言入库后：对用户 predicates 跑 match() 比对同 topic 历史 user claims
   → contradictions(who='user') + ledger_hits。
 - 字段名用 user_contradiction_hit，勿与 agent 侧自查同名。
 - 首版留空实现（不产生命中即可）；predicate_match 尚未接入。
"""
