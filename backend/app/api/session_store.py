"""会话登记表：只在进程内存里放，当前没有落库。

放在 api/ 是因为它现在不含任何台账语义——它记的是"这个会话归哪个身份、旋钮定到哪、开到第几个回合"，
三个动作都是发一个回合的前置判；`backend/app/memory/` 那个目录按职责只装三张台账。
落库之后这一层换成 backend/app/memory/sqlite.py 的会话仓储，本文件只留 HTTP 侧要的那三个调用。

逐回合正文不在这里——那是 backend/app/memory/claim_ledger.py 的活，表还没建，
所以现在每个回合都从 `initial_state` 起步，图本身不带跨回合记忆。

**进程重启即丢会话**：端点对已消失的 sid 返回 `SESSION_NOT_FOUND`。
"恢复会话"要的是持久化 + checkpoint 游标，两件都还没接。
"""

from dataclasses import dataclass, field
from threading import Lock
from uuid import uuid4

from ..graph.builder import default_config
from ..graph.state import DebateConfig


@dataclass
class Session:
    session_id: str
    # 服务端生成的 device-local id；来源是 cookie，任何端点都不接受客户端传的同名字段
    user_id: str
    topic: str
    stance: str
    config: DebateConfig
    turn_count: int = 0
    seen_keys: set[str] = field(default_factory=set)


class SessionStore:
    """不做淘汰、不做过期：一台机器一个使用者，键只用来挡重放。"""

    def __init__(self) -> None:
        self._lock = Lock()
        self._sessions: dict[str, Session] = {}

    def create(
        self, *, user_id: str, topic: str, stance: str, config: DebateConfig | None = None
    ) -> Session:
        session = Session(
            session_id=uuid4().hex[:12],
            user_id=user_id,
            topic=topic,
            stance=stance,
            config=config or default_config(),
        )
        with self._lock:
            self._sessions[session.session_id] = session
        return session

    def get(self, session_id: str) -> Session | None:
        with self._lock:
            return self._sessions.get(session_id)

    def open_turn(self, session: Session, idempotency_key: str) -> int | None:
        """占住幂等键并返回本回合序号；键用过即返回 None。

        放行的后果是同一次提交跑两个回合、同句用户原话进台账两次，所以宁可拒。
        代价是回合中途失败后拿原键重试会被判重放，必须换新键。
        """
        with self._lock:
            if idempotency_key in session.seen_keys:
                return None
            session.seen_keys.add(idempotency_key)
            session.turn_count += 1
            return session.turn_count
