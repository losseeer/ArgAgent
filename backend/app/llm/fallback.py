"""骨架文件：只声明归属与契约指针，实现见 §13.2 对应期。

 - §6.5 两级 fallback：tier1 换本地模型、tier2 固定模板；每次降级必发 SSE llm.fallback{tier, reason} 并挂角标（§6.12）。
 - 降级层级同时由 GET /api/healthz 报告（§6.12 首行）。
"""
