"""回合的 SSE 出口：把图吐出的一串事件按契约顺序编码成帧。

事件有两个来源，顺序口径不同：
 - 节点里 `get_stream_writer()` 的实时写入（流式正文、降层角标）——到了就发，不等回合收尾，
   否则顶栏角标会晚于正文，"降级不静默"就成了空话；
 - `DebateState.pending_events` 的累计队列——每个超步结束只发它新增的尾巴，
   节点都是"读旧列表 + 追加"，所以尾巴的顺序就是节点写入的顺序。

`turn.started` 由本文件发、不等图：它的服务端时间戳是首字延迟的计时起点。
每个 `data` 都带一个回合内单调递增的 `seq`（含本文件自己发的那一帧），前端据此发现断帧。

未预期异常直接向上抛，不塞进流：错误码那张表里没有"服务端内部异常"这一格，
临时造一个码等于给未定义的行为发一个看起来像契约的东西；客户端以缺少 `turn.done` 判失败。
"""

import json
from collections.abc import AsyncIterator, Mapping
from datetime import UTC, datetime
from typing import Any

from ..llm.factory import LlmChain, LlmError


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def build_chain() -> LlmChain:
    """一个回合一条链，在端点里建、经 `config.configurable.llm` 传给节点：
    同一个回合里 classify 与 attack 用同一层模型，不会前半句主模型、后半句本地。
    """
    return LlmChain()


def _frame(event: str, data: Mapping[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(dict(data), ensure_ascii=False)}\n\n"


def _started(state: Mapping[str, Any]) -> dict[str, Any]:
    cfg = state["config"]
    return {
        "trace_id": state["trace_id"],
        "turn_index": state["turn_index"],
        "ts": _now(),
        "cfg": {
            "difficulty": cfg["difficulty"],
            "strictness": cfg["strictness"],
            "mode": cfg["mode"],
        },
    }


async def turn_frames(
    *, graph: Any, state: dict[str, Any], chain: LlmChain
) -> AsyncIterator[str]:
    seq = 0

    def emit(event: str, data: Mapping[str, Any]) -> str:
        nonlocal seq
        seq += 1
        return _frame(event, {"seq": seq, **data})

    yield emit("turn.started", _started(state))

    sent = 0
    stream = graph.astream(
        state,
        config={"configurable": {"llm": chain}},
        stream_mode=["custom", "values"],
    )
    try:
        async for mode, chunk in stream:
            if mode == "custom":
                yield emit(chunk["event"], chunk["data"])
                continue
            events = chunk["pending_events"]
            for event in events[sent:]:
                yield emit(event["event"], event["data"])
            sent = len(events)
    except LlmError as exc:
        # 已经吐过字又断流：换模型续写半句话会被当成静默替换，比断流更难查，所以只报终态。
        yield emit("error", {"code": exc.code, "message": exc.message, "retryable": False})
