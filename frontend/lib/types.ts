// 骨架：类型口径来自后端契约——backend/app/graph/state.py 的 DebateConfig / DebateState 字段，
// 以及后端 SSE 事件的 payload；勿手改契约字段。

export type LayerTag = "FACT" | "ANALOGY" | "LOGIC";

export type Tier = "academic" | "reference" | "news" | "generic_web";
