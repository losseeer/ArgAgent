# Debate Arena

结构化论辩练习：一个会记住你说过什么的对抗式对话 Agent。三条主线能力——

1. **断言台账**：每句话按 `[FACT]` / `[ANALOGY]` / `[LOGIC]` 三层标注，事实断言带来源与可信度档位。
2. **矛盾检测**：与你本会话早前的断言、以及 Agent 自己的断言做比对，命中即出卡；Agent 自己改口会当场认错并在台账留痕。
3. **谬误标注**：指出论证的**支撑边**哪里断了，不给你的结论定性。

技术栈：LangGraph + FastAPI + SQLite（后端）· Next.js + Tailwind（前端）· ChromaDB（本地向量层）。全部可 CPU 跑，所有 API key 都可空。

## 5 分钟启动

```bash
git clone https://github.com/yourname/debate-arena.git
cd debate-arena

cp .env.example .env      # 全空也能起；填 DEEPSEEK_API_KEY 走云端主模型
make up                   # 需要 Docker；不用 Docker 见下
open http://localhost:3005
```

本地开发模式（不装 Docker，需要 host 上的 python 3.12+ / node 20.9+）：

```bash
make dev
```

`make` 只有六个目标：`up` / `down` / `dev` / `logs` / `eval` / `reset-db`（`reset-db` 清运行时数据，保留 `data/seed/`）。

## 能力边界（请先读完这一段）

这一段不是客套话，它决定了你该拿这个项目做什么、不做什么：

1. **矛盾检测只覆盖受控词表内的断言**。`data/seed/predicate_vocab.jsonl` 未命中的句子不参与判定，也不会出现在矛盾卡里。同一条款也限缩"AI 自动认错"：Agent 若用词表外的措辞换边，系统抓不到，那次改口不会被记录。
2. **不声称核查完整**。启用检索时，标注的是事实断言的来源与可信度档位（`academic` > `reference` > `news` > `generic_web`），不是"这句话已验证为真"。
3. **贡献是集成 + 一致性约束 + 领域自建评测**，不是新算法。指标与阈值集中在 `docs/eval-report.md` 的结果总表，样本量撑得住什么话就说什么话。

## 数据流向

只有你勾选 `[FACT]` 层断言且触发检索时，被抽出的断言文本才会发给所配置的检索服务；其余情况数据不出本机。本地运行时数据落在 `./data`（SQLite + Chroma），清库用 `make reset-db`。

## 目录与上手代码

- 架构与数据流：`docs/ARCHITECTURE.md`
- 后端：`backend/app/`（`graph/` 状态机、`memory/` 三张台账、`rag/` 检索分层、`eval/` 五族指标）
- 前端：`frontend/`（`components/` 一组件一文件）

## License

MIT
