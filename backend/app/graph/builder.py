"""骨架占位文件：只声明职责与契约，尚无实现。

 - 本文件是状态机的唯一 StateGraph 装配点。
 - 首版范围：只跑 classify → attack → fallacy → self_check → OUTPUT，
   consistency 留空实现。
 - 必含 self_check → attack 重试边，attempt 上限 2；重试路径不重跑 retrieve。
"""
