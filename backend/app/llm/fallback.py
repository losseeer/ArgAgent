"""骨架占位文件：只声明职责与契约，尚无实现。

 - 两级兜底：tier1 换本地模型、tier2 固定模板；
   每次降级必发 SSE llm.fallback{tier, reason} 并在顶栏挂角标，不静默替换。
 - 当前降级层级同时由 GET /api/healthz 报告。
"""
