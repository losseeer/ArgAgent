"""骨架占位文件：只声明职责与契约，尚无实现。

 - 内容安全过滤：输入侧（classify 出口的 gate）和输出侧（self_check 的校验项）都在这一个模块。
 - 本地模式表 data/seed/safety_patterns.jsonl；配了 MODERATION_API_KEY 才叠加远端二次判。
 - 缺 key 时必须**显式降级**：SSE 发 safety.status{mode: heuristic_only}
   且 BadgeBar 角标可见（缺角标即视为缺陷；对它的断言尚未进 CI）。
 - 两类处置不同：op_guidance 硬拦（precision 优先）、self_harm 只软提示且会话可继续。
 - 本文件与 60 条自造安全用例集属同一批交付；用例集在 data/seed/ 下，目前为空文件。
"""
