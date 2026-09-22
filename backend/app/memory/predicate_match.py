"""骨架文件：只声明归属与契约指针，实现见 §13.2 对应期。

 - §7.3 match() / unify() / merged_into 重定向的**唯一实现点**，
   两侧（T1 用户 / T2 agent）共用
   （Q5 已决：谓词化，embedding 方案废弃）。
 - 只加载 status='accepted'；喂 candidate 条目应直接报错（§13.2 P2）。
 - 归属 P2。
"""
