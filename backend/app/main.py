"""FastAPI 入口：lifespan 内装配 LangGraph 状态机（SQLite / Chroma 连接尚未接入）。

启动顺序契约：无任何 API key 时也必须能起来并走完一个回合；
安全过滤器降级信息在会话首个回合由 SSE `safety.status` 发出，不依赖本文件。
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from .api.routes import router
from .graph.builder import get_workflow


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 图在这里装配而不是 import 时：编译不过要让启动当场红，而不是等第一个回合的 SSE 里
    app.state.graph = get_workflow()
    # TODO（随后）：backend/app/memory/sqlite.py 建表 +
    #   backend/app/rag/vocab_store.py 载入 accepted 词表
    yield


app = FastAPI(title="Debate Arena", version="0.1.0", lifespan=lifespan)
app.include_router(router)
