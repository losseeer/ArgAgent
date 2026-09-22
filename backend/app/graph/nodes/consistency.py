"""骨架文件：只声明归属与契约指针，实现见 §13.2 对应期。

 - T1（§6.11）：对用户 predicates 跑 match() 比对同 topic 历史 user claims
   → contradictions(who='user') + ledger_hits。
 - 字段名用 user_contradiction_hit（Q1 已决，勿与 agent 侧自查同名）。
 - P1 留空实现（不产生命中即可），P2 接 predicate_match（§13.2）。
"""
