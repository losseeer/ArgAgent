"""骨架文件：只声明归属与契约指针，实现见 §13.2 对应期。

 - §6.13 内容安全过滤：输入侧（classify 出口的 gate）+ 输出侧（self_check 的校验项）都在这一个模块。
 - 本地模式表 data/seed/safety_patterns.jsonl；配了 MODERATION_API_KEY 才叠加远端二次判。
 - 缺 key 时必须**显式降级**：SSE 发 safety.status{mode: heuristic_only} 且 BadgeBar 角标可见（N8 断言）。
 - 两类处置不同：op_guidance 硬拦（precision 优先）、self_harm 只软提示且会话可继续（Q9 已决）。
 - 归属 P1（§13.2 P1 交付物含本文件与安全用例集 60 条）。
"""
