"""首版状态机的验收测试：空 key 走完一个回合、重试恰好到限、到限落模板。

用假链（FakeChain）替掉真模型，网络一律不打；只验图的走向与出口事件。
真链的降级行为在 test_llm_chain.py，服务起不来的问题在手工验收里查。
"""

from test_contracts import CONFIG_KEYS, STATE_KEYS

from app.config import Settings
from app.graph.builder import default_config, get_workflow, initial_state
from app.llm.factory import LlmChain
from app.llm.fallback import TEMPLATE_REPLY


class FakeChain:
    """按需返回固定正文的链：`drafts` 里的第 n 条给第 n 次 attack 调用。"""

    def __init__(self, *, classify_json="{}", drafts=None, tiers=None):
        self.classify_json = classify_json
        self.drafts = drafts or []
        self.tiers = tiers or []
        self.calls = {"complete": 0, "stream": 0}
        self.usage_total = {"prompt": 0, "completion": 0}
        self.tier = 0
        self._events = []

    def drain_events(self):
        events, self._events = self._events, []
        return events

    async def complete(self, *, system, user, temperature=0.2, max_tokens=512,
                       json_mode=False, template=""):
        self.calls["complete"] += 1
        text = self.classify_json if json_mode else template
        return _Completion(text=text, tier=0, reason="", usage={"prompt": 1, "completion": 1})

    async def stream(self, *, system, user, temperature=0.2, max_tokens=512,
                     json_mode=False, template=""):
        self.calls["stream"] += 1
        index = self.calls["stream"] - 1
        text = self.drafts[index] if index < len(self.drafts) else TEMPLATE_REPLY
        tier = self.tiers[index] if index < len(self.tiers) else 0
        if tier:
            self._events.append({"event": "llm.fallback", "data": {"tier": tier, "reason": "x"}})
        yield ("delta", text)
        usage = {"prompt": 2, "completion": 3}
        yield ("done", _Completion(text=text, tier=tier, reason="", usage=usage))


class _Completion:
    def __init__(self, text, tier, reason, usage):
        self.text = text
        self.tier = tier
        self.reason = reason
        self.usage = usage


def make_state(**overrides):
    base = initial_state(
        session_id="s1",
        user_id="u1",
        trace_id="t1",
        turn_index=1,
        topic="远程办公应当成为默认选项",
        stance="pro",
        config=default_config(),
        user_text="数据显示远程办公效率更高，所以所有人都该回家办公。",
    )
    base.update(overrides)
    return base


async def run(chain, state=None):
    state = state or make_state()
    final = await get_workflow().ainvoke(state, config={"configurable": {"llm": chain}})
    return state, final


async def test_real_empty_key_chain_still_completes_a_turn():
    """真链、真空配置：不设任何 key，也不 mock，落到模板并把这个回合走完。"""
    settings = Settings(deepseek_api_key="", ollama_host="http://127.0.0.1:9")
    chain = LlmChain(settings)
    state, final = await run(chain)

    names = [e["event"] for e in final["pending_events"]]
    assert final["attack_draft"] == TEMPLATE_REPLY
    assert [m["role"] for m in final["messages"]] == ["user", "agent"]
    assert names[-1] == "turn.done"
    assert chain.tier == 2, "两层都不可用时应停在模板层"
    assert names.count("llm.fallback") == 1, "一个回合只吭一声降层"
    # 模板没有层标签，所以这个回合既是降级到底、又被出口校验拦过一次：两件事各自成立
    assert final["validation"]["missing"] == ["layer_tag"]


async def test_retry_happens_exactly_twice_then_falls_back():
    """每稿都缺层标签 → 必然校验失败：attack 只应被执行两次，第二次后走模板。"""
    chain = FakeChain(drafts=["没有标签的一稿", "还是没有标签"])
    state, final = await run(chain)

    assert chain.calls["stream"] == 2, "重试上限是 2 次，图内不得出现第三次"
    assert final["validation"]["attempt"] == 2
    assert final["validation"]["passed"] is False
    assert final["validation"]["missing"] == ["layer_tag"]
    assert final["attack_draft"] == TEMPLATE_REPLY
    assert final["attack_layer"] is None, "模板不补层标签，免得把没答上来伪装成打了某层"
    names = [e["event"] for e in final["pending_events"]]
    assert names.count("validation.failed") == 2, "重试时一次、终态一次，前端不静默"
    assert names[-1] == "turn.done"


async def test_first_draft_passing_skips_retry_and_carries_layer():
    chain = FakeChain(drafts=["[FACT] 你引的那份样本只有 12 人 [UNVERIFIED]"])
    state, final = await run(chain)

    assert chain.calls["stream"] == 1
    assert final["validation"] == {"passed": True, "missing": [], "attempt": 1}
    assert final["attack_layer"] == "fact"
    assert final["messages"][-1]["layer"] == "fact"
    names = [e["event"] for e in final["pending_events"]]
    assert "validation.failed" not in names
    assert "message.layer" in names


async def test_fact_layer_without_evidence_must_say_unverified_in_both_modes():
    """fact 层、无证据、又没标 UNVERIFIED：严格与宽松两档都不放行（静默即缺陷）。"""
    draft = "[FACT] 所有研究都支持远程办公更高效"
    for strictness in ("strict", "loose"):
        config = default_config()
        config["strictness"] = strictness
        chain = FakeChain(drafts=[draft, draft])
        _, final = await run(chain, make_state(config=config))

        assert final["validation"]["missing"] == ["url_unverified"], strictness


async def test_attacking_the_conclusion_is_a_validation_failure():
    """两稿都打结论：重试到限后落模板，缺项原样带出而不是藏起来。"""
    chain = FakeChain(drafts=["[LOGIC] 所以你错了", "[LOGIC] 这个结论不成立"])
    _, final = await run(chain)

    assert chain.calls["stream"] == 2
    assert final["validation"]["missing"] == ["conclusion_hit"]
    assert final["attack_draft"] == TEMPLATE_REPLY
    assert final["attack_layer"] is None, "模板不是模型输出，不补层标签"


async def test_classify_products_feed_the_attack_context():
    raw = '{"intent":"argument","layer_hint":"fact","fact_claims":[{"text":"效率提升 23%"}]}'
    chain = FakeChain(classify_json=raw, drafts=["[FACT] 那个 23% 是哪年的样本 [UNVERIFIED]"])
    state, final = await run(chain)

    assert final["fact_claims"] == [{"text": "效率提升 23%", "kind": "other"}]
    assert final["breadth_target"] == 1, "单条断言只有主攻，不开副点"
    assert final["validation"]["passed"] is True


async def test_unparsable_classify_output_does_not_break_the_turn():
    chain = FakeChain(classify_json="抱歉我不确定", drafts=["[LOGIC] 你的推理跳了一步"])
    _, final = await run(chain)

    assert final["fact_claims"] == []
    assert final["validation"]["passed"] is True


def test_config_keys_are_the_frozen_eight():
    assert set(default_config()) == CONFIG_KEYS


def test_initial_state_covers_every_contracted_key():
    assert set(make_state()) == STATE_KEYS
