"""骨架占位文件：只声明职责与契约，尚无实现。

 - 跨会话 pattern_memory：opt-in，只有用户在设置里勾选开启跨会话记忆才写；
   会话结束时才把 contradictions 与高频撤回类型聚合成 patterns。
 - 属默认关闭的可选增强，关掉后主干功能的验收判据不得受影响；
   可导出、可一次性确认 token 后清空，路径一律不带客户端声明的身份。
 - v0 用 SQLite 模拟的实现标 [DEV ONLY]，v1 换 Chroma 时旧实现保留并加 marker。
"""
