"""§6.12 的 14 个端点骨架：路径 / 方法 / 请求契约已按表落齐，处理逻辑随 §13.2 P1 起逐期填。

统一响应包（SSE 除外）：{"ok": true, "data": {...}, "error": null, "trace_id": "..."}。

两条契约在这里就是可断言的（tests/unit/test_contracts.py）：
 1. 任何端点不接受客户端传来的 user_id（路径/查询/请求体），出现即 422（Q7 已决）。
 2. PUT config 只接受 difficulty 与 strictness 两个键，其余键（含 persona / mode）422，不静默忽略（Q6 已决）。
"""

from typing import Literal, Optional

from fastapi import APIRouter, Header, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict

router = APIRouter(prefix="/api")

_FORBIDDEN_IDENTITY = {"user_id", "userId", "uid"}


def deny_identity_params(request: Request) -> None:
    """查询参数里出现任何身份字段即 422（身份只从 cookie 解析，§6.12 鉴权第 1 条）。"""
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


class ConfigUpdate(NoIdentityBody):
    difficulty: Optional[Literal["casual", "competitive", "brutal"]] = None
    strictness: Optional[Literal["strict", "loose"]] = None


class RebutBody(NoIdentityBody):
    reason: str
    qualifier: Optional[str] = None  # 非空 → retract_source='user_qualifier'（§6.11 T4）


def _not_implemented(name: str) -> "HTTPException":
    return HTTPException(status_code=501, detail=f"skeleton: {name} 待 §13.2 对应期实现")


@router.get("/healthz")
async def healthz(request: Request):
    """就绪探针（compose 等它）。

    只报告**配置层面**的可用性与当前降级层级；真正的连通性探测随 §13.2 P1 的 llm/factory 落地。
    """
    deny_identity_params(request)
    from ..config import get_settings

    s = get_settings()
    return {
        "ok": True,
        "data": {
            "primary": {"model": s.deepseek_model, "configured": s.primary_configured},
            "backup": {"model": s.ollama_model, "configured": bool(s.ollama_host)},
            "safety_mode": s.moderation_mode,
        },
        "error": None,
        "trace_id": None,
    }


@router.post("/sessions")
async def create_session(body: SessionCreate, request: Request):
    deny_identity_params(request)
    raise _not_implemented("POST /sessions")


@router.get("/sessions/{sid}")
async def get_session(sid: str, request: Request):
    deny_identity_params(request)
    raise _not_implemented("GET /sessions/{sid}")


@router.post("/sessions/{sid}/turns")
async def create_turn(
    sid: str,
    request: Request,
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
):
    """发一轮，返回 SSE 流；Idempotency-Key 必填（防重试双写 ledger）。"""
    deny_identity_params(request)
    raise _not_implemented("POST /sessions/{sid}/turns (SSE)")


@router.post("/turns/{tid}/abort")
async def abort_turn(tid: str, request: Request):
    """中止在 OUTPUT 之前 → 该轮 agent claim 不入台账；不得用 retracted=1 表达中止（§6.12）。"""
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
    """用户回驳谬误标注或矛盾卡：用户侧唯一的撤回写入口，重复提交幂等（Q14 已决）。"""
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
    """一次性确认 token：TTL 5 分钟、单次消费（§6.12 鉴权第 2 条）。"""
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
