"""骨架占位文件：只声明职责与契约，尚无实现。

 - tavily-python 0.8（该版本已实测）。key 缺失则跳过 web 层并降级 DuckDuckGo，
   且必须有 retrieval.status 事件把降级告诉前端，不静默切换。
 - 出境边界：启用的检索工具会收到被抽出的 fact_claims 文本——
   除所选检索工具的 query 外，用户数据不出本机；首次开启检索须显式告知。
"""
