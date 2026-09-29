"""降级链的单测：不打网络，只验"降不降、降几层、降了有没有吭声"。

判据对着 backend/app/llm/factory.py 的三条硬约束写：
空 key 必须走完一个回合、层级一个回合只确认一次、降级必发事件且不静默。
"""

import asyncio

import pytest

from app.config import Settings
from app.llm import factory
from app.llm.factory import LlmChain, LlmError
from app.llm.fallback import TEMPLATE_REPLY, TIER_LOCAL, TIER_PRIMARY, TIER_TEMPLATE

_COMPLETE = {"primary": "_complete_primary", "local": "_complete_local"}
_STREAM = {"primary": "_stream_primary", "local": "_stream_local"}


def make_settings(**overrides) -> Settings:
    base = {
        "deepseek_api_key": "",
        "deepseek_model": "unit-test-primary",
        "ollama_model": "unit-test-local",
        "ollama_host": "http://127.0.0.1:9",
    }
    base.update(overrides)
    return Settings(**base)


def patch_complete(monkeypatch, calls: dict, tier: str, result):
    """非流式替身：`result` 为异常则抛出，为元组则返回。"""
    calls[tier] = 0

    async def fake(*args, **kwargs):
        calls[tier] += 1
        if isinstance(result, Exception):
            raise result
        return result

    monkeypatch.setattr(factory, _COMPLETE[tier], fake)


def patch_complete_stall(monkeypatch, calls: dict, tier: str) -> None:
    """非流式替身：接了请求但整份响应永远不回（本地模型加载卡住时也会这样挂住）。"""
    calls[tier] = 0

    async def fake(*args, **kwargs):
        calls[tier] += 1
        await asyncio.sleep(30)
        return "永远不会到的响应", {"prompt": 0, "completion": 0}

    monkeypatch.setattr(factory, _COMPLETE[tier], fake)


def patch_stream(monkeypatch, calls: dict, tier: str, chunks, failure=None):
    """流式替身：先吐 `chunks`，吐完再抛 `failure`（`chunks` 为空即"一个字段都没出"）。"""
    calls[tier] = 0

    async def fake(*args, **kwargs):
        calls[tier] += 1
        for chunk in chunks:
            yield chunk
        if failure is not None:
            raise failure

    monkeypatch.setattr(factory, _STREAM[tier], fake)


def patch_stream_stall(monkeypatch, calls: dict, tier: str) -> None:
    """流式替身：接了请求但永远不吐第一个字（本地模型加载中最常见的那种挂法）。"""
    calls[tier] = 0

    async def fake(*args, **kwargs):
        calls[tier] += 1
        await asyncio.sleep(30)
        yield "永远不会到的第一个字"

    monkeypatch.setattr(factory, _STREAM[tier], fake)


def new_chain(**settings_overrides) -> LlmChain:
    return LlmChain(make_settings(**settings_overrides))


async def test_empty_key_and_dead_local_land_on_template(monkeypatch):
    calls: dict = {}
    patch_complete(monkeypatch, calls, "primary", factory.TierUnavailable("primary_unreachable"))
    patch_complete(monkeypatch, calls, "local", factory.TierUnavailable("local_unreachable"))
    chain = new_chain()

    result = await chain.complete(system="s", user="u")

    assert result.tier == TIER_TEMPLATE
    assert result.text == TEMPLATE_REPLY
    assert result.usage == {"prompt": 0, "completion": 0}
    assert calls == {"primary": 0, "local": 1}, "缺 key 就不该去敲主模型的接口"
    assert chain.drain_events() == [
        {
            "event": "llm.fallback",
            "data": {"tier": TIER_TEMPLATE, "reason": "primary_key_missing; local_unreachable"},
        }
    ]


async def test_local_alive_degrades_once_and_is_reused(monkeypatch):
    calls: dict = {}
    patch_complete(monkeypatch, calls, "primary", factory.TierUnavailable("primary_unreachable"))
    patch_complete(monkeypatch, calls, "local", ("本地答复", {"prompt": 3, "completion": 5}))
    chain = new_chain(deepseek_api_key="sk-test")

    first = await chain.complete(system="s", user="u")
    second = await chain.complete(system="s", user="u")

    assert (first.text, first.tier) == ("本地答复", TIER_LOCAL)
    assert first.usage == {"prompt": 3, "completion": 5}
    assert second.text == "本地答复"
    assert calls == {"primary": 1, "local": 2}, "确认过的层级不再回头探主模型"
    assert [e["data"]["tier"] for e in chain.drain_events()] == [TIER_LOCAL]
    assert chain.drain_events() == [], "同一次降级只吭一声"


async def test_primary_alive_emits_nothing(monkeypatch):
    calls: dict = {}
    patch_complete(monkeypatch, calls, "primary", ("主模型答复", {"prompt": 1, "completion": 2}))
    chain = new_chain(deepseek_api_key="sk-test")

    result = await chain.complete(system="s", user="u")

    assert result.tier == TIER_PRIMARY
    assert result.reason == ""
    assert chain.drain_events() == []


async def test_each_node_keeps_its_own_template_wording(monkeypatch):
    calls: dict = {}
    patch_complete(monkeypatch, calls, "primary", factory.TierUnavailable("primary_unreachable"))
    patch_complete(monkeypatch, calls, "local", factory.TierUnavailable("local_unreachable"))
    chain = new_chain()

    result = await chain.complete(system="s", user="u", template="这一点的依据是？")

    assert result.text == "这一点的依据是？"


async def test_stream_announces_degradation_before_first_delta(monkeypatch):
    calls: dict = {}
    patch_stream(monkeypatch, calls, "primary", [], factory.TierUnavailable("primary_unreachable"))
    patch_stream(monkeypatch, calls, "local", ["前半", "后半"])
    chain = new_chain(deepseek_api_key="sk-test")

    events = [item async for item in chain.stream(system="s", user="u")]

    assert [kind for kind, _ in events] == ["fallback", "delta", "delta", "done"]
    assert events[0][1]["data"]["tier"] == TIER_LOCAL
    assert "primary_unreachable" in events[0][1]["data"]["reason"]
    assert events[-1][1].text == "前半后半"
    assert events[-1][1].tier == TIER_LOCAL


async def test_stream_without_any_tier_sends_template_as_single_delta(monkeypatch):
    calls: dict = {}
    patch_stream(monkeypatch, calls, "primary", [], factory.TierUnavailable("primary_unreachable"))
    patch_stream(monkeypatch, calls, "local", [], factory.TierUnavailable("local_unreachable"))
    chain = new_chain(deepseek_api_key="sk-test")

    events = [item async for item in chain.stream(system="s", user="u")]

    assert [kind for kind, _ in events] == ["fallback", "delta", "done"]
    assert events[1][1] == TEMPLATE_REPLY
    assert events[-1][1].tier == TIER_TEMPLATE
    assert calls == {"primary": 1, "local": 1}


async def test_first_token_timeout_kills_the_stalled_tier_only(monkeypatch):
    """主模型接了请求但不吐字：等满首字线就判它死，继续降到本地，而不是拖满 90s 读超时。"""
    monkeypatch.setattr(factory, "FIRST_TOKEN_TIMEOUT", 0.05)
    calls: dict = {}
    patch_stream_stall(monkeypatch, calls, "primary")
    patch_stream(monkeypatch, calls, "local", ["本地答复"])
    chain = new_chain(deepseek_api_key="sk-test")

    events = [item async for item in chain.stream(system="s", user="u")]

    assert [kind for kind, _ in events] == ["fallback", "delta", "done"]
    assert events[0][1]["data"]["reason"] == "primary_first_token_timeout"
    assert events[-1][1].tier == TIER_LOCAL
    assert calls == {"primary": 1, "local": 1}, "被砍的那层不留悬挂的流，也不在本回合再敲第二次"


async def test_every_tier_stalling_lands_on_template(monkeypatch):
    monkeypatch.setattr(factory, "FIRST_TOKEN_TIMEOUT", 0.05)
    calls: dict = {}
    patch_stream_stall(monkeypatch, calls, "primary")
    patch_stream_stall(monkeypatch, calls, "local")
    chain = new_chain(deepseek_api_key="sk-test")

    events = [item async for item in chain.stream(system="s", user="u")]

    assert events[1][1] == TEMPLATE_REPLY
    assert events[-1][1].tier == TIER_TEMPLATE
    assert events[0][1]["data"]["reason"] == (
        "primary_first_token_timeout; local_first_token_timeout"
    )
    assert chain.tier == TIER_TEMPLATE


async def test_response_timeout_kills_the_stalled_tier_only(monkeypatch):
    """非流式没有"字"可看：整份响应等满 RESPONSE_TIMEOUT 就判这层死，继续降到本地。"""
    monkeypatch.setattr(factory, "RESPONSE_TIMEOUT", 0.05)
    calls: dict = {}
    patch_complete_stall(monkeypatch, calls, "primary")
    patch_complete(monkeypatch, calls, "local", ("本地答复", {"prompt": 3, "completion": 5}))
    chain = new_chain(deepseek_api_key="sk-test")

    result = await chain.complete(system="s", user="u")

    assert (result.text, result.tier) == ("本地答复", TIER_LOCAL)
    assert result.reason == "primary_response_timeout"
    assert calls == {"primary": 1, "local": 1}, "卡住的主模型在本回合不再敲第二次"


async def test_every_tier_timing_out_lands_on_template(monkeypatch):
    monkeypatch.setattr(factory, "RESPONSE_TIMEOUT", 0.05)
    calls: dict = {}
    patch_complete_stall(monkeypatch, calls, "primary")
    patch_complete_stall(monkeypatch, calls, "local")
    chain = new_chain(deepseek_api_key="sk-test")

    result = await chain.complete(system="s", user="u")

    assert result.tier == TIER_TEMPLATE
    assert result.text == TEMPLATE_REPLY
    assert result.reason == "primary_response_timeout; local_response_timeout"


async def test_stream_breaking_midway_raises_instead_of_switching_tier(monkeypatch):
    calls: dict = {}
    patch_stream(monkeypatch, calls, "primary", [], factory.TierUnavailable("primary_unreachable"))
    patch_stream(monkeypatch, calls, "local", ["已经给出的部分"], factory.TierUnavailable("err"))
    chain = new_chain(deepseek_api_key="sk-test")

    with pytest.raises(LlmError) as excinfo:
        [item async for item in chain.stream(system="s", user="u")]

    assert excinfo.value.code == "LLM_ALL_TIERS_FAILED"
    assert chain.tier is None, "半句话不算一层可用，下一回合仍要重新探"
