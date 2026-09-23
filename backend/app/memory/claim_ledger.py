"""骨架占位文件：只声明职责与契约，尚无实现。

 - claims 表读写。**retracted=1 全库只有两个写入点**：
   self_check（出口校验时 agent 自查出自相矛盾）与 rebut（用户回驳该卡），
   由 retract_source 取值 + 建表 CHECK 约束 + 台账不变量断言三层收口。
 - 中止（abort）发生在 OUTPUT 之前 → 该轮 agent claim 不入台账；
   **不得**用 retracted=1 表达中止——那是第三条路，会绕过来源判校验。
"""
