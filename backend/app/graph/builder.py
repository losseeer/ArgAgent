"""骨架文件：只声明归属与契约指针，实现见 §13.2 对应期。

 - §6.1 状态机装配（唯一 StateGraph 装配点）。
 - P1 首版范围（§13.2 P1）：只跑 classify → attack → fallacy → self_check → OUTPUT，consistency 留空实现。
 - 必含 self_check → attack 重试边，attempt 上限 2（§6.11 校验↔重试边）；重试路径不重跑 retrieve。
"""
