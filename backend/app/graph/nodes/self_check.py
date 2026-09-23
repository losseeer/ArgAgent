"""骨架占位文件：只声明职责与契约，尚无实现。

 - 出口校验（在谬误标注之后、发送之前的轻校验）：agent 侧矛盾写
   contradictions(who='agent')，被推翻旧 claim 置 retracted=1 + retract_source='self_check'。
 - **同轮回复必须含认错文案**，缺文案不得放行（前缀正则识别，零 LLM 成本）。
 - validation.missing 含 safety 时不重试（出口校验重试规则的例外）。
 - attempt >= 2 后不再重试，改走 fallback 并把 missing 原样推给前端（宁缺不藏）。
"""
