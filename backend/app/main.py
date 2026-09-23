"""FastAPI 入口：lifespan 内装配 LangGraph 状态机与 SQLite / Chroma 连接。

启动顺序契约：无任何 API key 时也必须能起来并走完一轮；
安全过滤器降级信息在会话首轮由 SSE `safety.status` 发出，不依赖本文件。
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from .api.routes import router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # TODO（先做）：装配 backend/app/graph/builder.py 的 StateGraph，挂到 app.state.graph
    # TODO（随后）：backend/app/memory/sqlite.py 建表 +
    #   backend/app/rag/vocab_store.py 载入 accepted 词表
    yield


app = FastAPI(title="Debate Arena", version="0.1.0", lifespan=lifespan)
app.include_router(router)
