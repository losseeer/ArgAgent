"""路由层：契约端点的装配点，处理逻辑按端点分批补齐。

14 个契约端点的路径 / 方法 / 请求契约已落齐。已实现四个：`GET /healthz`、`POST /sessions`、
`GET /sessions/{sid}`、`POST /sessions/{sid}/turns`（SSE 回合流：编帧见
backend/app/api/turn_stream.py，会话与幂等键见 backend/app/api/session_store.py）；
其余仍返回 501，detail 里写明缺什么。

统一响应包（SSE 除外）：{"ok": true, "data": {...}, "error": null, "trace_id": "..."}。
失败时 data=null、error={code, message, detail}——状态码之外的语义全在 code 里。

四条契约在这里就是可断言的（backend/tests/unit/test_contracts.py、
backend/tests/unit/test_turn_stream.py）：
 1. 任何端点不接受客户端传来的 user_id（路径/查询/请求体），出现即 422。
 2. PUT config 只接受 difficulty 与 strictness 两个键，
    其余键（含 persona / mode）422，不静默忽略。
 3. 身份只认服务端下发的 device cookie：缺 cookie 或它与会话绑定的不是同一个 → IDENTITY_MISMATCH。
 4. 发回合必带 Idempotency-Key；同一个键第二次提交判 IDEMPOTENCY_REPLAY，不会重跑一个回合。
"""

from typing import Any, Literal
from uuid import uuid4

from fastapi import APIRouter, Header, HTTPException, Query, Request, Response
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, ConfigDict

from ..graph.builder import default_config, initial_state
from ..graph.state import DebateConfig
from . import turn_stream
from .session_store import Session

router = APIRouter(prefix="/api")

_FORBIDDEN_IDENTITY = {"user_id", "userId", "uid"}
#: 服务端生成的 device-local id 的唯一存放处。HttpOnly + SameSite=Lax，调用方改不了也读不到。
DEVICE_COOKIE = "arena_device"
#: 一年而不是会话级 cookie：清 cookie 即换身份这条已写在文档的"不挡的场景"里，
#: 但关浏览器就丢掉全部会话不在其中。
DEVICE_COOKIE_MAX_AGE = 365 * 24 * 3600


def deny_identity_params(request: Request) -> None:
    """查询参数里出现任何身份字段即 422：身份只从服务端解析出的 cookie 来，不由调用方声明。"""
    bad = _FORBIDDEN_IDENTITY.intersection(request.query_params.keys())
    if bad:
        raise HTTPException(status_code=422, detail=f"identity params not accepted: {sorted(bad)}")


class NoIdentityBody(BaseModel):
    """请求体一律 extra='forbid'：带 user_id 或 PUT /config 带 persona / mode 当场 422。"""

    model_config = ConfigDict(extra="forbid")


class SessionCreate(NoIdentityBody):
    topic: str
    stance: Literal["pro", "con"]
    difficulty: Literal["casual", "competitive", "brutal"] = "competitive"
    strictness: Literal["strict", "loose"] = "strict"
    mode: Literal["workflow", "agent-loop"] = "workflow"


class TurnCreate(NoIdentityBody):
    """用户本回合的原话走请求体，不从别处送、也不先存消息再由回合引用 `msg_id`。

    `client_ts` 收下但本版本不读：首字延迟的两端时间戳都取服务端，客户端时钟进不了那个指标。
    """

    content: str
    client_ts: str | None = None


class ConfigUpdate(NoIdentityBody):
    difficulty: Literal["casual", "competitive", "brutal"] | None = None
    strictness: Literal["strict", "loose"] | None = None


class RebutBody(NoIdentityBody):
    reason: str
    qualifier: str | None = None  # 非空即用户补了限定前提 → retract_source='user_qualifier'


def _not_implemented(name: str) -> "HTTPException":
    return HTTPException(status_code=501, detail=f"骨架占位：{name} 尚未实现")


def _envelope(data: Any, trace_id: str | None = None) -> dict[str, Any]:
    return {"ok": True, "data": data, "error": None, "trace_id": trace_id}


def _failure(status_code: int, code: str, message: str, detail: Any = None) -> JSONResponse:
    """错误响应走统一包：状态码只表粗分类，客户端要判的语义全在 error.code。"""
    return JSONResponse(
        status_code=status_code,
        content={
            "ok": False,
            "data": None,
            "error": {"code": code, "message": message, "detail": detail},
            "trace_id": None,
        },
    )


def _device_id(request: Request) -> str | None:
    return request.cookies.get(DEVICE_COOKIE)


def _bind_device(response: Response, request: Request, device: str) -> None:
    response.set_cookie(
        DEVICE_COOKIE,
        device,
        max_age=DEVICE_COOKIE_MAX_AGE,
        httponly=True,
        samesite="lax",
        secure=request.url.is_secure,
    )


def _session_config(body: "SessionCreate") -> DebateConfig:
    """config 的定稿权在服务端：默认旋钮由图那边给，这里只覆盖会话创建时允许声明的两格。"""
    config = default_config()
    config["difficulty"] = body.difficulty
    config["strictness"] = body.strictness
    config["mode"] = body.mode
    return config


def _public_session(session: Session) -> dict[str, Any]:
    """对外只回会话自己那几项；user_id 是服务端身份，不进响应体（前端不需要，回了也不该回）。"""
    return {
        "session_id": session.session_id,
        "topic": session.topic,
        "stance": session.stance,
        "config": dict(session.config),
        "turn_count": session.turn_count,
    }


@router.get("/healthz")
async def healthz(request: Request):
    """就绪探针（compose 等它）。

    只报告**配置层面**的事实：主模型有没有 key、备模型的模型名与地址、当前审核档位。
    备模型不给"是否可用"的结论——它有默认地址，地址在并不代表连得上。
    这里刻意不打模型：探针每被拉一次就多一次外呼，会把 compose 的探活变成对上游的轰炸。
    实际可用层级由降级链在回合内确认（backend/app/llm/factory.py），并经 SSE 角标可见。
    """
    deny_identity_params(request)
    from ..config import get_settings

    s = get_settings()
    return _envelope(
        {
            "primary": {"model": s.deepseek_model, "configured": s.primary_configured},
            "backup": {"model": s.ollama_model, "host": s.ollama_host},
            "safety_mode": s.moderation_mode,
        }
    )


@router.post("/sessions")
async def create_session(body: SessionCreate, request: Request, response: Response):
    """建会话，顺带把身份 cookie 发出去——首次访问就是在这一格发生的。

    `mode` 只能在新会话定，而 agent-loop 那张图还没装配：这里当场拒掉，
    不在收下之后静默按另一张图跑（同一层模型那种"看不见的替换"是本仓库最不能要的东西）。
    """
    deny_identity_params(request)
    if body.mode == "agent-loop":
        raise _not_implemented("agent-loop 会话（该模式的图尚未装配）")

    device = _device_id(request) or uuid4().hex
    session = request.app.state.sessions.create(
        user_id=device, topic=body.topic, stance=body.stance, config=_session_config(body)
    )
    if _device_id(request) is None:
        _bind_device(response, request, device)
    return _envelope(_public_session(session))


@router.get("/sessions/{sid}")
async def get_session(sid: str, request: Request):
    """恢复会话：当前只回进程内存里的那份，没有持久化、也没有 checkpoint 游标可回。

    进程重启后这里必然是 SESSION_NOT_FOUND——写清楚，别让调用方以为拿到了旧会话。
    """
    deny_identity_params(request)
    session = request.app.state.sessions.get(sid)
    if session is None:
        return _failure(404, "SESSION_NOT_FOUND", "会话不存在（进程重启过，或 sid 不属于本进程）")
    return _envelope(_public_session(session))


@router.post("/sessions/{sid}/turns")
async def create_turn(
    sid: str,
    body: TurnCreate,
    request: Request,
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
):
    """发一个回合，返回 SSE 流；`Idempotency-Key` 必填（防重试双写 ledger）。

    三道前置判在开回合之前：会话在不在、身份 cookie 绑不绑得上、幂等键有没有用过。
    判过了才占键、分配 `turn_index`，于是"重放被拒"和"跑了一半失败"是两种看得开的状态。
    降级链在这一格建（一个回合一条链），流式编帧见 backend/app/api/turn_stream.py。
    """
    deny_identity_params(request)
    store = request.app.state.sessions
    session = store.get(sid)
    if session is None:
        return _failure(404, "SESSION_NOT_FOUND", "会话不存在（进程重启过，或 sid 不属于本进程）")

    device = _device_id(request)
    if device is None or device != session.user_id:
        return _failure(403, "IDENTITY_MISMATCH", "身份 cookie 缺失或与该会话绑定的不是同一个")

    turn_index = store.open_turn(session, idempotency_key)
    if turn_index is None:
        return _failure(409, "IDEMPOTENCY_REPLAY", "该 Idempotency-Key 已用过，重跑请换新键")

    state = initial_state(
        session_id=session.session_id,
        user_id=session.user_id,
        trace_id=uuid4().hex[:12],
        turn_index=turn_index,
        topic=session.topic,
        stance=session.stance,
        config=session.config,
        user_text=body.content,
    )
    return StreamingResponse(
        turn_stream.turn_frames(
            graph=request.app.state.graph, state=state, chain=turn_stream.build_chain()
        ),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache"},
    )


@router.post("/turns/{tid}/abort")
async def abort_turn(tid: str, request: Request):
    """中止在 OUTPUT 之前 → 本回合 agent claim 不入台账；不得用 retracted=1 表达中止。"""
    deny_identity_params(request)
    raise _not_implemented("POST /turns/{tid}/abort")


@router.post("/turns/{tid}/{target}/{i}/rebut")
async def rebut(
    tid: str,
    target: Literal["flags", "contradictions"],
    i: int,
    body: RebutBody,
    request: Request,
):
    """用户回驳谬误标注或矛盾卡：用户侧唯一的撤回写入口，同一张卡重复提交幂等。"""
    deny_identity_params(request)
    raise _not_implemented("POST /turns/{tid}/{target}/{i}/rebut")


@router.get("/sessions/{sid}/ledger")
async def get_ledger(
    sid: str,
    request: Request,
    include_retracted: bool = Query(False),
    page: int = Query(1, ge=1),
):
    deny_identity_params(request)
    raise _not_implemented("GET /sessions/{sid}/ledger")


@router.get("/config")
async def get_config(request: Request):
    deny_identity_params(request)
    raise _not_implemented("GET /config")


@router.put("/sessions/{sid}/config")
async def put_config(sid: str, body: ConfigUpdate, request: Request):
    """只接受 difficulty / strictness；extra='forbid' 让其他键当场 422。"""
    deny_identity_params(request)
    raise _not_implemented("PUT /sessions/{sid}/config")


@router.get("/memory/patterns")
async def export_patterns(request: Request):
    deny_identity_params(request)
    raise _not_implemented("GET /memory/patterns")


@router.post("/memory/patterns/confirmation")
async def request_confirmation(request: Request):
    """一次性确认 token：TTL 5 分钟、单次消费，清空跨会话记忆前必须先拿到它。"""
    deny_identity_params(request)
    raise _not_implemented("POST /memory/patterns/confirmation")


@router.delete("/memory/patterns")
async def clear_patterns(request: Request):
    """缺 token / 过期 / 重放 → CONFIRMATION_REQUIRED 且不执行任何删除。"""
    deny_identity_params(request)
    raise _not_implemented("DELETE /memory/patterns")


@router.post("/eval/runs")
async def start_eval_run(request: Request):
    deny_identity_params(request)
    raise _not_implemented("POST /eval/runs")


@router.get("/eval/runs/{rid}")
async def get_eval_run(rid: str, request: Request):
    deny_identity_params(request)
    raise _not_implemented("GET /eval/runs/{rid}")
