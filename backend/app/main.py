"""FastAPI 入口：lifespan 内装配 LangGraph 状态机与进程内会话表（SQLite / Chroma 连接尚未接入）。

启动顺序契约：无任何 API key 时也必须能起来并走完一个回合；
安全过滤器降级信息在会话首个回合由 SSE `safety.status` 发出，不依赖本文件。
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api.routes import router
from .api.session_store import SessionStore
from .config import get_settings
from .graph.builder import get_workflow


def _frontend_origins() -> list[str]:
    """开发态前端直连后端端口，属跨源请求，而身份要落在这台机器的 cookie 上 → 必须带凭证。

    生产态走反代把前后端并到同源（见 docs/ARCHITECTURE.md 的部署一节），那时这些头不参与判断。
    端口只从 backend/app/config.py 读，不在这里重复写死默认值。
    """
    port = get_settings().frontend_port
    return [f"http://localhost:{port}", f"http://127.0.0.1:{port}"]


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 图在这里装配而不是 import 时：编译不过要让启动当场红，而不是等第一个回合的 SSE 里
    app.state.graph = get_workflow()
    # 会话只在进程内存里，重启即丢；替换成表结构时这里换成 backend/app/memory/sqlite.py 的会话仓储
    app.state.sessions = SessionStore()
    # TODO（随后）：backend/app/memory/sqlite.py 建表 +
    #   backend/app/rag/vocab_store.py 载入 accepted 词表
    yield


app = FastAPI(title="Debate Arena", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_frontend_origins(),
    allow_credentials=True,
    allow_headers=["*"],
    allow_methods=["*"],
)
app.include_router(router)
