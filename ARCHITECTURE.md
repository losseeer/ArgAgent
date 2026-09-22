# 架构与数据流

> 本文件是公开仓库的结构性说明；阈值与验收判据不在此重复（结果总表见 `docs/eval-report.md`，计算口径见 `backend/app/eval/metrics.py`）。
> 下方代码块是数据流的唯一真源；`docs/architecture.svg` 由它导出，导出脚本待 P1 随 CI 落地。

## 主图（workflow 模式）

```
用户消息
  → classify            意图分类 + 三层断言 + 谓词抽取（同一次结构化调用）
  → safety_filter       输入侧 gate（本地模式表 + 可选远端二次判）
  → consistency         与用户本会话早前断言比对（T1）
  → retrieve?           按五类判据（数值 / 时间 / 人名 / 机构 / 因果）触发，≤2 步
  → attack              短轮次关键攻击 + 本轮自身断言谓词
  → fallacy             谬误标注，confidence 三档
  → self_check          agent 侧矛盾（T2）+ OUTPUT 前轻校验；含 safety 输出侧
      ↺ attack          校验不过则重试，上限 2 次；仍不过走兜底模板并把缺失项原样推给前端
  → OUTPUT              校验通过后才写 agent claim 入台账（T3）
```

`agent-loop` 模式（LLM 直接持工具）是**默认关闭**的第二条装配路径，其输出不受上述出口校验覆盖，界面须显式标注"无护栏"。

## 三条不变量

1. **被否决的草稿不入台账**：重试发生在 OUTPUT 之前，故只有校验通过的当轮断言会写库。
2. **撤回是单向棘轮，且只有两个合法写入点**：`self_check`（Agent 认错，必须同轮带认错文案）与用户回驳端点。谁让 `retracted` 变成 1 的，由 `retract_source` 记录并被建表约束与常驻断言双重校验。
3. **降级必须可见**：模型降级、检索受限、审核缺 key、预算超出都会在顶栏角标呈现，不静默替换。

## 模块归属

| 目录 | 职责 | 唯一实现点 |
|---|---|---|
| `backend/app/graph/` | 状态机装配、条件边、安全过滤 | 触发判据在 `graph/routing.py`；谓词判定不在图里 |
| `backend/app/memory/` | 三张台账（claims / contradictions / patterns） | 矛盾判定统一走 `memory/predicate_match.py` |
| `backend/app/rag/` | 检索分层（web / 学术 / 百科 / 向量 / 词表） | 词表层不进 Chroma，是内存精确匹配 |
| `backend/app/llm/` | 三级降级链（主模型 → 本地 Ollama → 兜底模板） | 模型名只从 `.env` 的 `DEEPSEEK_MODEL` 读 |
| `backend/app/eval/` | 五族指标 N/K/V/R/O | 阈值只写在内部规格里，本文件与代码注释都不复制数字 |
| `frontend/components/` | 一组件一职责 | 角标只允许 `BadgeBar.tsx` 一个挂载点 |

## 契约即测试

`backend/tests/unit/test_contracts.py` 对状态字段集合与端点集合做**相等**断言：
字段多一个或少一个都算失败，请求体带 `user_id` 必须被拒，14 个契约端点必须全部装配。
**这两份文件（`state.py` 的键集合 + 该测试的期望集合）就是对外生效的契约真源**，改契约即改它们。

## 评测与诚实口径

`make eval` 覆盖五个指标族（结构断言、构造式真值剧本、小金标、鲁棒性、时延），产出 `docs/eval-report.md`，
逐项给红/绿与 ±置信区间。样本量与能支撑什么结论的边界写在报告里；本项目不声称核查完整，也不主张方法创新。
