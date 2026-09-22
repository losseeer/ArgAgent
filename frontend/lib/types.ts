// 骨架：类型由 backend OpenAPI 生成（docs/openapi.json → 本文件），勿手改契约字段。
// §6.11 的 DebateConfig / DebateState 字段与 §6.12 事件 payload 是生成源。

export type LayerTag = "FACT" | "ANALOGY" | "LOGIC";

export type Tier = "academic" | "reference" | "news" | "generic_web";
