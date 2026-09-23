/**
 * 骨架占位文件：只声明职责与契约，尚无实现。
 * 后端 SSE 回合流的客户端：用 fetch + ReadableStream，不用 EventSource
 * （需要 POST 触发与自定义头，如 Idempotency-Key）。
 */

export const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8010";

/** 后端 SSE 事件名的唯一枚举——新增事件必须先在后端发出并同步此枚举，再上前端消费方 */
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

/** 骨架：帧解析与重连待 DebateStream 落地时补，此处只固定事件名枚举与后端地址口径 */
export async function* postTurn(
  _sid: string,
  _body: unknown,
  _idempotencyKey: string,
): AsyncGenerator<SseFrame> {
  throw new Error("该端点尚未实现（骨架占位）");
}
