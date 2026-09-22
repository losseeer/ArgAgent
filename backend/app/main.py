"""FastAPI 入口：lifespan 内装配 LangGraph（§6.1）与 SQLite / Chroma 连接（§4）。

启动顺序契约（§13.2 P1 验收）：无任何 API key 时也必须能起来并走完一轮；
安全过滤器降级信息在会话首轮由 SSE `safety.status` 发出，不依赖本文件。
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from .api.routes import router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # TODO(P1): 装配 graph/builder.py 的 StateGraph 并挂到 app.state.graph
    # TODO(P2): memory/sqlite.py 建表 + rag/vocab_store.py 载入 accepted 词表
    yield


app = FastAPI(title="Debate Arena", version="0.1.0", lifespan=lifespan)
app.include_router(router)
