"""骨架文件：只声明归属与契约指针，实现见 §13.2 对应期。

 - Tavily 0.3（§5.2）。key 缺失则跳过 web 层并降级 DuckDuckGo，且 retrieval.status 必须有事件（§13.2 P3）。
 - 出境边界：启用的检索工具会收到被抽出的 fact_claims 文本（§11「除所选检索工具的 query 外，用户数据不出本机」）。
"""
