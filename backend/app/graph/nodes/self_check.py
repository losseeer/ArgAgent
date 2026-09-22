"""骨架文件：只声明归属与契约指针，实现见 §13.2 对应期。

 - T2 + OUTPUT 前轻校验（§6.11）：agent 侧矛盾写 contradictions(who='agent')，
   被推翻旧 claim 置 retracted=1 + retract_source='self_check'。
 - **同轮回复必须含认错文案**，缺文案不得放行（§6.4#11 / §10.2 N6，前缀正则识别，零 LLM 成本）。
 - validation.missing 含 safety 时不重试（§6.2 出口校验行的例外规则，枚举见 §6.11）。
 - attempt >= 2 后不再重试，改走 §6.5 fallback 并把 missing 原样推给前端（宁缺不藏）。
"""
