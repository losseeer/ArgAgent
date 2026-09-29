"""三级降级链：主模型 → 本地 Ollama → 兜底模板。

模型名、地址、key 的唯一出处是 backend/app/config.py，本文件不写死任何模型名。
三条硬约束：

 1. 缺 key / 主模型不可达 / 本地模型不可达，任何一种都必须能把这个回合走完，
    链尾落到模板而不是抛错中断会话。
 2. 降级不静默：每降一层产出一条 `llm.fallback` 事件，由调用方 `drain_events()` 收进
    `DebateState.pending_events`（见 backend/app/graph/state.py）。
 3. 一个回合只确认一次层级：某层一旦可用就整个回合复用它，某层一旦失败就在本回合内跳过，
    免得每次调用都重付一次失败层的超时。

流式输出只在"还没吐出第一个字"时降级；中途断开不重发，直接抛 `LlmError`——
换模型续写半句话会被当成静默替换，比断流更难查。第一个字的等待上限见 `FIRST_TOKEN_TIMEOUT`：
一层"接了但不回"时，读超时（90s）救不了首字指标，只有这根线能把它判死并继续降。
非流式（分类、谬误标注）没有"字"可看，改给整份响应配一根 `RESPONSE_TIMEOUT`，同样是一判死就继续降。
"""

import asyncio
import json
from collections.abc import AsyncIterator, Mapping
from contextlib import suppress
from dataclasses import dataclass, field
from typing import Any

import httpx

from ..config import Settings, get_settings
from .fallback import TEMPLATE_REPLY, TIER_LOCAL, TIER_PRIMARY, TIER_TEMPLATE, fallback_event

ANTHROPIC_VERSION = "2023-06-01"
LLM_CONFIG_KEY = "llm"
# 本地 Ollama 未起时应当"立刻"失败，故连接超时给得很短；读超时放宽到能吃下一个慢首字。
_TIMEOUT = httpx.Timeout(connect=3.0, read=90.0, write=10.0, pool=3.0)
#: 首字等多久就判这一层不可用并继续降。与首字指标的 6s 线同值，所以它一响就是门禁会红的那类回合。
FIRST_TOKEN_TIMEOUT = 6.0
#: 非流式调用（分类、谬误标注那两次结构化输出）没有"字"可看，只能给整份响应配一根上限。
#: 比首字线宽是应该的：一份 512 token 的 JSON 正常生成就要 3–6s，套 6s 会误杀还能救的回合。
RESPONSE_TIMEOUT = 15.0

ERROR_ALL_FAILED = "LLM_ALL_TIERS_FAILED"

_ZERO_USAGE: dict[str, int] = {"prompt": 0, "completion": 0}


def from_config(config: Mapping[str, Any] | None) -> "LlmChain":
    """从 LangGraph 传进节点的 config 里取出本回合那条链；装配点见 backend/app/graph/builder.py。

    没注入就直接 KeyError：那是调用方漏传，换一条新链会把"一个回合一个层级"的口径悄悄改掉。
    """
    return (config or {})["configurable"][LLM_CONFIG_KEY]


class LlmError(RuntimeError):
    """整条链都不可用（或流被拦腰截断）时抛出，`code` 即响应体里的错误码。"""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class TierUnavailable(Exception):
    """单层失败，链上一律吞掉继续降；只在没有任何内容产出时才算这一类。"""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True)
class Completion:
    """一次非流式调用的结果：`tier` 是实际用的层级，`usage` 是本调用的 token 数。"""

    text: str
    tier: int
    reason: str
    usage: dict[str, int]


@dataclass
class _Attempt:
    """流式调用的旁路累加器：token 数在最后一个事件里才到，生成器只能往外带文本。"""

    usage: dict[str, int] = field(default_factory=lambda: dict(_ZERO_USAGE))


def _request_primary(
    s: Settings,
    system: str,
    user: str,
    temperature: float,
    max_tokens: int,
    json_mode: bool,
) -> tuple[str, dict[str, str], dict[str, Any]]:
    if json_mode:
        system = f"{system}\n\n只输出一个 JSON 对象，不要解释、不要代码块标记。"
    url = f"{s.deepseek_base_url.rstrip('/')}/v1/messages"
    headers = {"x-api-key": s.deepseek_api_key, "anthropic-version": ANTHROPIC_VERSION}
    body = {
        "model": s.deepseek_model,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "system": system,
        "messages": [{"role": "user", "content": user}],
    }
    return url, headers, body


def _request_local(
    s: Settings,
    system: str,
    user: str,
    temperature: float,
    max_tokens: int,
    json_mode: bool,
) -> tuple[str, dict[str, Any]]:
    url = f"{s.ollama_host.rstrip('/')}/api/chat"
    body: dict[str, Any] = {
        "model": s.ollama_model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "options": {"temperature": temperature, "num_predict": max_tokens},
    }
    if json_mode:
        body["format"] = "json"
    return url, body


def _sse_json(line: str) -> dict[str, Any] | None:
    if not line.startswith("data:"):
        return None
    payload = line[5:].strip()
    if not payload or payload == "[DONE]":
        return None
    try:
        parsed = json.loads(payload)
    except ValueError:
        return None
    return parsed if isinstance(parsed, dict) else None


def _tier_name(tier: int) -> str:
    return "primary" if tier == TIER_PRIMARY else "local"


def _empty_reason(tier: int) -> str:
    return f"{_tier_name(tier)}_empty"


async def _abandon(deltas: Any) -> None:
    """首字超时后关掉这条流：连接要当场还回去，不能等垃圾回收。"""
    with suppress(Exception):
        await deltas.aclose()


def _text_of_anthropic(data: dict[str, Any]) -> str:
    blocks = data.get("content") or []
    return "".join(b.get("text", "") for b in blocks if b.get("type") == "text")


def _usage_of(prompt: Any, completion: Any) -> dict[str, int]:
    return {
        "prompt": int(prompt or 0),
        "completion": int(completion or 0),
    }


async def _complete_primary(
    s: Settings, system: str, user: str, temperature: float, max_tokens: int, json_mode: bool
) -> tuple[str, dict[str, int]]:
    url, headers, body = _request_primary(s, system, user, temperature, max_tokens, json_mode)
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.post(url, headers=headers, json=body)
    except httpx.HTTPError as exc:
        raise TierUnavailable("primary_unreachable") from exc
    if resp.status_code >= 300:
        raise TierUnavailable(f"primary_http_{resp.status_code}")
    data = resp.json()
    usage = data.get("usage") or {}
    return (
        _text_of_anthropic(data),
        _usage_of(usage.get("input_tokens"), usage.get("output_tokens")),
    )


async def _complete_local(
    s: Settings, system: str, user: str, temperature: float, max_tokens: int, json_mode: bool
) -> tuple[str, dict[str, int]]:
    url, body = _request_local(s, system, user, temperature, max_tokens, json_mode)
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.post(url, json={**body, "stream": False})
    except httpx.HTTPError as exc:
        raise TierUnavailable("local_unreachable") from exc
    if resp.status_code >= 300:
        raise TierUnavailable(f"local_http_{resp.status_code}")
    data = resp.json()
    return (
        (data.get("message") or {}).get("content", ""),
        _usage_of(data.get("prompt_eval_count"), data.get("eval_count")),
    )


async def _stream_primary(
    s: Settings,
    system: str,
    user: str,
    temperature: float,
    max_tokens: int,
    json_mode: bool,
    attempt: _Attempt,
) -> AsyncIterator[str]:
    url, headers, body = _request_primary(s, system, user, temperature, max_tokens, json_mode)
    body["stream"] = True
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            async with client.stream("POST", url, headers=headers, json=body) as resp:
                if resp.status_code >= 300:
                    raise TierUnavailable(f"primary_http_{resp.status_code}")
                async for line in resp.aiter_lines():
                    event = _sse_json(line)
                    if not event:
                        continue
                    kind = event.get("type")
                    if kind == "content_block_delta":
                        text = (event.get("delta") or {}).get("text")
                        if text:
                            yield text
                    elif kind == "message_start":
                        usage = (event.get("message") or {}).get("usage") or {}
                        attempt.usage["prompt"] = int(usage.get("input_tokens") or 0)
                    elif kind == "message_delta":
                        usage = event.get("usage") or {}
                        attempt.usage["completion"] = int(usage.get("output_tokens") or 0)
                    elif kind == "error":
                        raise TierUnavailable("primary_stream_error")
    except httpx.HTTPError as exc:
        raise TierUnavailable("primary_unreachable") from exc


async def _stream_local(
    s: Settings,
    system: str,
    user: str,
    temperature: float,
    max_tokens: int,
    json_mode: bool,
    attempt: _Attempt,
) -> AsyncIterator[str]:
    url, body = _request_local(s, system, user, temperature, max_tokens, json_mode)
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            async with client.stream("POST", url, json=body) as resp:
                if resp.status_code >= 300:
                    raise TierUnavailable(f"local_http_{resp.status_code}")
                async for line in resp.aiter_lines():
                    if not line.strip():
                        continue
                    try:
                        event = json.loads(line)
                    except ValueError:
                        continue
                    text = (event.get("message") or {}).get("content")
                    if text:
                        yield text
                    if event.get("done"):
                        attempt.usage["prompt"] = int(event.get("prompt_eval_count") or 0)
                        attempt.usage["completion"] = int(event.get("eval_count") or 0)
    except httpx.HTTPError as exc:
        raise TierUnavailable("local_unreachable") from exc


class LlmChain:
    """一个回合一条链：层级确认一次、失败层本回合不再重试。"""

    def __init__(self, settings: Settings | None = None) -> None:
        self._s = settings or get_settings()
        self._confirmed: int | None = None
        self._failed: dict[int, str] = {}
        self._events: list[dict] = []
        #: 本回合累计 token 数，由 OUTPUT 出口随 `turn.done` 一起报出（按会话累加在前端）
        self.usage_total: dict[str, int] = dict(_ZERO_USAGE)
        if not self._s.deepseek_api_key:
            self._failed[TIER_PRIMARY] = "primary_key_missing"

    @property
    def tier(self) -> int | None:
        """本回合已确认的层级；None 表示还没调用过任何模型。"""
        return self._confirmed

    @property
    def reason(self) -> str:
        """已失败层级的原因，按层级顺序拼成一句；没有失败时为空串。"""
        return "; ".join(self._failed[t] for t in sorted(self._failed))

    def drain_events(self) -> list[dict]:
        """取走并清空待发的降级事件，由节点放进 `pending_events`。"""
        events, self._events = self._events, []
        return events

    def _candidates(self) -> list[int]:
        if self._confirmed is not None:
            return [] if self._confirmed == TIER_TEMPLATE else [self._confirmed]
        return [t for t in (TIER_PRIMARY, TIER_LOCAL) if t not in self._failed]

    def _settle(self, tier: int) -> None:
        if self._confirmed == tier:
            return
        self._confirmed = tier
        if tier > TIER_PRIMARY:
            self._events.append(fallback_event(tier, self.reason))

    def _tally(self, usage: dict[str, int]) -> None:
        self.usage_total["prompt"] += int(usage.get("prompt") or 0)
        self.usage_total["completion"] += int(usage.get("completion") or 0)

    def _mark_failed(self, tier: int, reason: str) -> None:
        self._failed[tier] = reason
        if self._confirmed == tier:
            self._confirmed = None

    async def complete(
        self,
        *,
        system: str,
        user: str,
        temperature: float = 0.2,
        max_tokens: int = 512,
        json_mode: bool = False,
        template: str = TEMPLATE_REPLY,
    ) -> Completion:
        for tier in self._candidates():
            call = _complete_primary if tier == TIER_PRIMARY else _complete_local
            try:
                text, usage = await asyncio.wait_for(
                    call(self._s, system, user, temperature, max_tokens, json_mode),
                    RESPONSE_TIMEOUT,
                )
            except TierUnavailable as exc:
                self._mark_failed(tier, exc.reason)
                continue
            except TimeoutError:
                self._mark_failed(tier, f"{_tier_name(tier)}_response_timeout")
                continue
            self._settle(tier)
            self._tally(usage)
            return Completion(text=text, tier=tier, reason=self.reason, usage=usage)
        self._settle(TIER_TEMPLATE)
        return Completion(
            text=template, tier=TIER_TEMPLATE, reason=self.reason, usage=dict(_ZERO_USAGE)
        )

    async def stream(
        self,
        *,
        system: str,
        user: str,
        temperature: float = 0.2,
        max_tokens: int = 512,
        json_mode: bool = False,
        template: str = TEMPLATE_REPLY,
    ) -> AsyncIterator[tuple[str, Any]]:
        """依次产出 `("fallback", 事件)` → `("delta", 文本)`* → `("done", Completion)`。

        降级事件一定排在第一个字之前，所以前端不会先看到正文再看到角标。
        """
        for tier in self._candidates():
            stream_fn = _stream_primary if tier == TIER_PRIMARY else _stream_local
            attempt = _Attempt()
            parts: list[str] = []
            deltas = stream_fn(self._s, system, user, temperature, max_tokens, json_mode, attempt)
            try:
                while True:
                    if parts:
                        delta = await deltas.__anext__()
                    else:
                        # 只有第一个字带这根线：后面的读超时（90s）管的是"已经 in 的流别断太久"。
                        delta = await asyncio.wait_for(deltas.__anext__(), FIRST_TOKEN_TIMEOUT)
                    if not parts:
                        self._settle(tier)
                        for event in self.drain_events():
                            yield ("fallback", event)
                    parts.append(delta)
                    yield ("delta", delta)
            except StopAsyncIteration:
                pass
            except TimeoutError:
                await _abandon(deltas)
                self._mark_failed(tier, f"{_tier_name(tier)}_first_token_timeout")
                continue
            except TierUnavailable as exc:
                self._mark_failed(tier, exc.reason)
                if parts:
                    raise LlmError(
                        ERROR_ALL_FAILED, f"输出中途断开，未换层续写：{exc.reason}"
                    ) from exc
                continue
            if not parts:
                self._mark_failed(tier, _empty_reason(tier))
                continue
            self._tally(attempt.usage)
            yield (
                "done",
                Completion(
                    text="".join(parts),
                    tier=tier,
                    reason=self.reason,
                    usage=attempt.usage,
                ),
            )
            return
        self._settle(TIER_TEMPLATE)
        for event in self.drain_events():
            yield ("fallback", event)
        yield ("delta", template)
        yield (
            "done",
            Completion(
                text=template, tier=TIER_TEMPLATE, reason=self.reason, usage=dict(_ZERO_USAGE)
            ),
        )
