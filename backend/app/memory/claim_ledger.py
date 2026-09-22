"""骨架文件：只声明归属与契约指针，实现见 §13.2 对应期。

 - §7.2 claims 表读写。**retracted=1 全库只有两个写入点**：
   self_check（T2）与 rebut（T4），
   由 retract_source + 建表 CHECK + N6 断言三层收口（§6.4#11）。
 - 中止（abort）发生在 OUTPUT 之前 → 该轮 agent claim 不入台账；
   **不得**用 retracted=1 表达中止（§6.12 abort 行）。
"""
