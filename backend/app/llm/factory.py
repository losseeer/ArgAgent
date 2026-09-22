"""骨架文件：只声明归属与契约指针，实现见 §13.2 对应期。

 - §5.1 / §6.5：三级降级链 primary=$DEEPSEEK_MODEL（默认 deepseek-flash）
   → Ollama qwen2.5 → 兜底模板。
 - 模型名唯一出处是 .env 的 DEEPSEEK_MODEL，
   **代码与文档都不得写死营销代际**（Q20 已决 · 第十九轮）。
 - 空 key 也必须能走完一轮（落到 fallback2 模板，§13.2 P1 验收）。
"""
