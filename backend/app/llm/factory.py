"""骨架占位文件：只声明职责与契约，尚无实现。

 - 三级降级链：primary=$DEEPSEEK_MODEL（默认 deepseek-flash）
   → 本地 Ollama qwen2.5 → 兜底模板。
 - 模型名唯一出处是 .env 的 DEEPSEEK_MODEL，
   **代码与文档都不得写死营销代际**。
 - 空 key 也必须能走完一轮：一路降到兜底模板，不抛错中断会话。
"""
