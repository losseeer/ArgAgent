"""骨架占位文件：只声明职责与契约，尚无实现。

 - ≤2 步 ReAct 按需检索；触发判据不在这里，在 backend/app/graph/routing.py（唯一实现点）。
 - 尚未实现（骨架占位）。
 - 网页/论文正文必须以 <retrieved source="url"> 包裹注入，
   并在 self_check 查话题漂移（注入边界）。
 - 来源可信度用离散 tier（academic > reference > news > generic_web，
   映射表 data/seed/source_tiers.jsonl），
   **禁止复用 Tavily 相关性 score**（红线）。
"""
