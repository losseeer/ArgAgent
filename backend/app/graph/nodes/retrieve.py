"""骨架文件：只声明归属与契约指针，实现见 §13.2 对应期。

 - §6.2 / §6.14：≤2 步 ReAct 按需检索；触发判据不在这里，在 graph/routing.py（唯一实现点）。
 - 归属 P3（§13.2 P3）。
 - 网页/论文正文必须以 <retrieved source="url"> 包裹注入，并在 self_check 查话题漂移（§6.12 注入边界）。
 - 来源可信度用离散 tier（academic > reference > news > generic_web，映射表 data/seed/source_tiers.jsonl），**禁止复用 Tavily 相关性 score**（§6.12 红线 3）。
"""
