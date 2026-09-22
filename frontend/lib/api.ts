/**
 * §6.12 的 SSE 客户端：用 fetch + ReadableStream，不用 EventSource
 * （需要 POST 触发与自定义头，如 Idempotency-Key）。
 */

export const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8010";

/** §6.12 事件表的事件名唯一枚举——新增事件必须先改设计文档那张表 */
export type SseEvent =
  | "turn.started"
  | "retrieval.started"
  | "retrieval.item"
  | "retrieval.status"
  | "message.delta"
  | "message.layer"
  | "fallacy.flags"
  | "ledger.appended"
  | "contradiction.hit"
  | "validation.failed"
  | "llm.fallback"
  | "safety.status"
  | "safety.hold"
  | "turn.done"
  | "error";

export interface SseFrame {
  event: SseEvent;
  data: Record<string, unknown>;
}

/** 骨架：帧解析与重连随 §13.2 P1 的 DebateStream 实现，此处只固定事件名枚举与地址口径 */
export async function* postTurn(
  _sid: string,
  _body: unknown,
  _idempotencyKey: string,
): AsyncGenerator<SseFrame> {
  throw new Error("not implemented: 见 §6.12（P1 交付）");
}
